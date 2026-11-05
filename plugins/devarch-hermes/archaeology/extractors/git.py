"""Git log extraction for archaeology pipeline."""

import csv
import os
import subprocess
from pathlib import Path

# Never allow promisor/partial clones to pull missing blobs during mining.
_LOCAL_GIT_ENV = {
    "GIT_NO_LAZY_FETCH": "1",
    "GIT_TERMINAL_PROMPT": "0",
}


def _git_env() -> dict:
    env = os.environ.copy()
    env.update(_LOCAL_GIT_ENV)
    return env


def _git(repo_path: str, *args: str, check: bool = True) -> str:
    """Read Git metadata without invoking a shell or repository hooks."""
    try:
        result = subprocess.run(
            ["git", "-C", str(Path(repo_path).expanduser()), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            env=_git_env(),
        )
    except FileNotFoundError as exc:
        raise RuntimeError("git binary not found. Install git and ensure it's on PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("git read timed out after 300s") from exc
    if check and result.returncode:
        raise RuntimeError(f"git {args[0]} failed: {result.stderr.strip()}")
    return result.stdout


def _git_dir(repo_path: str) -> Path:
    raw = _git(repo_path, "rev-parse", "--git-dir").strip()
    p = Path(raw)
    if not p.is_absolute():
        p = Path(repo_path).expanduser().resolve() / p
    return p.resolve()


def incomplete_object_reason(repo_path: str) -> str | None:
    """Return an actionable error if the repo would lazy-fetch missing objects."""
    git_dir = _git_dir(repo_path)
    promisor_packs = (
        list((git_dir / "objects" / "pack").glob("*.promisor"))
        if (git_dir / "objects" / "pack").is_dir()
        else []
    )
    if promisor_packs:
        return (
            "Refusing incomplete-object / partial (promisor) clone — mining is local-only "
            "and must not fetch missing blobs. Re-clone with full objects "
            "(`git clone --no-partial` / omit `--filter`) or run "
            "`git fetch --refetch` / `git sparse-checkout disable` as appropriate, then retry."
        )
    # remote.*.promisor config (exit 1 = none)
    out = _git(repo_path, "config", "--get-regexp", r"^remote\..*\.promisor$", check=False)
    # Also probe filter config
    filt = _git(
        repo_path, "config", "--get", "remote.origin.partialclonefilter", check=False
    ).strip()
    promisor_cfg = _git(repo_path, "config", "--get-regexp", r"\.promisor$", check=False).strip()
    if filt or promisor_cfg or out.strip():
        return (
            "Refusing partial clone (promisor/filter configured) — mining is local-only "
            "and must not fetch missing blobs. Re-clone without `--filter`/`--partial` and retry."
        )
    # With GIT_NO_LAZY_FETCH=1, missing blobs make shortstat fail rather than fetch.
    # Probe HEAD tree readability when commits exist.
    count = int(_git(repo_path, "rev-list", "--all", "--count").strip() or "0")
    if count:
        probe = subprocess.run(
            [
                "git",
                "-C",
                str(Path(repo_path).expanduser()),
                "rev-list",
                "--objects",
                "--all",
                "--missing=print",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            env=_git_env(),
        )
        if probe.returncode == 0:
            missing = [ln for ln in probe.stdout.splitlines() if ln.startswith("?")]
            if missing:
                return (
                    f"Refusing incomplete-object repository ({len(missing)} missing object(s)). "
                    "Mining is local-only and will not fetch. Restore full objects and retry."
                )
        # Some git versions lack --missing=print; fall through.
    return None


def repository_coverage(repo_path: str) -> dict:
    """Record local reachability, never imply that remote/deleted refs were fetched."""
    _git(repo_path, "rev-parse", "--git-dir")
    refs = _git(repo_path, "for-each-ref", "--format=%(refname)%09%(objectname)")
    count = int(_git(repo_path, "rev-list", "--all", "--count").strip())
    return {
        "head": _git(repo_path, "rev-parse", "--verify", "HEAD").strip() if count else None,
        "scope": "all locally available refs plus HEAD; no automatic remote fetch",
        "shallow": _git(repo_path, "rev-parse", "--is-shallow-repository").strip() == "true",
        "bare": _git(repo_path, "rev-parse", "--is-bare-repository").strip() == "true",
        "commit_count": count,
        "refs": [dict(zip(("name", "object"), line.split("\t", 1))) for line in refs.splitlines()],
        "roots": _git(repo_path, "rev-list", "--all", "--max-parents=0").splitlines(),
        "gaps": [
            "Deleted, inaccessible and unfetched remote refs are outside this local snapshot."
        ],
    }


def extract_git_log(repo_path: str, output_path: str, verbose: bool = False) -> int:
    """Extract every reachable commit, with NUL-delimited fields and UTC dates.

    Subjects can contain tabs, pipes and unit separators. Git NUL delimiters
    preserve those values rather than silently shifting or dropping CSV fields.
    Empty histories write a header, replacing any stale previous extraction.
    """
    import io
    from datetime import datetime, timezone

    from ..utils import atomic_write

    reason = incomplete_object_reason(repo_path)
    if reason:
        raise RuntimeError(reason)

    raw = _git(repo_path, "log", "-z", "--all", "--format=%H%x00%aI%x00%s%x00%an")
    fields = raw.split("\0")
    if fields[-1] == "":
        fields.pop()
    if len(fields) % 4:
        raise RuntimeError("Malformed Git extraction; refusing partial history")
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(["hash", "date", "message", "author"])
    for i in range(0, len(fields), 4):
        sha, date, subject, author = fields[i : i + 4]
        normalized = (
            datetime.fromisoformat(date.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
        )
        writer.writerow([sha, normalized, subject, author])
    count = len(fields) // 4
    expected = int(_git(repo_path, "rev-list", "--all", "--count").strip())
    if count != expected:
        raise RuntimeError("Repository changed during extraction; retry against frozen refs")
    atomic_write(output_path, stream.getvalue())
    if verbose:
        print(f"Extracted {count} commits from {repo_path}")
    return count


def extract_git_log_with_stats(repo_path: str, output_path: str, verbose: bool = False) -> int:
    """Extract git log with file change stats (local-only; no lazy fetch)."""
    reason = incomplete_object_reason(repo_path)
    if reason:
        raise RuntimeError(reason)

    cmd = ["git", "-C", repo_path, "log", "--format=%H%x1f%ai%x1f%s%x1f%an", "--shortstat", "--all"]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            env=_git_env(),
        )
    except FileNotFoundError:
        raise RuntimeError("git binary not found. Install git and ensure it's on PATH.")
    except subprocess.TimeoutExpired:
        raise RuntimeError("git log timed out after 300s. Repository may be too large.")

    if result.returncode != 0:
        err = (result.stderr or "").strip()
        if "promisor" in err.lower() or "lazy" in err.lower() or "missing" in err.lower():
            raise RuntimeError(
                "git log --shortstat failed because objects are missing; "
                "refusing to fetch. Restore a complete local clone and retry. "
                f"Detail: {err}"
            )
        raise RuntimeError(f"git log failed: {err}")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result.stdout)

    if verbose:
        print(f"Extracted git log with stats from {repo_path}")
    return int(_git(repo_path, "rev-list", "--all", "--count").strip())


def get_repo_list(repo_path: str) -> list[str]:
    """Get list of all repos accessible from the given path (for multi-repo extraction)."""
    # If it's a GitHub user/org, use gh API
    try:
        result = subprocess.run(
            ["gh", "repo", "list", "--limit", "100", "--json", "name,url"],
            capture_output=True,
            text=True,
            cwd=repo_path,
            timeout=60,
            env=_git_env(),
        )
    except FileNotFoundError:
        raise RuntimeError("gh CLI not found. Install GitHub CLI and ensure it's on PATH.")
    except subprocess.TimeoutExpired:
        raise RuntimeError("gh repo list timed out after 60s.")

    if result.returncode == 0:
        import json

        repos = json.loads(result.stdout)
        return [r["name"] for r in repos]
    return []
