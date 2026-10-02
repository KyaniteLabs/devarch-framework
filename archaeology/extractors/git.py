"""Git log extraction for archaeology pipeline."""

import csv
import subprocess
from pathlib import Path


def _git(repo_path: str, *args: str) -> str:
    """Read Git metadata without invoking a shell or repository hooks."""
    try:
        result = subprocess.run(
            ["git", "-C", str(Path(repo_path).expanduser()), *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("git binary not found. Install git and ensure it's on PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("git read timed out after 300s") from exc
    if result.returncode:
        raise RuntimeError(f"git {args[0]} failed: {result.stderr.strip()}")
    return result.stdout


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
        "gaps": ["Deleted, inaccessible and unfetched remote refs are outside this local snapshot."],
    }


def extract_git_log(repo_path: str, output_path: str, verbose: bool = False) -> int:
    """Extract every reachable commit, with NUL-delimited fields and UTC dates.

    Subjects can contain tabs, pipes and unit separators. Git NUL delimiters
    preserve those values rather than silently shifting or dropping CSV fields.
    Empty histories write a header, replacing any stale previous extraction.
    """
    from datetime import datetime, timezone
    import io
    from ..utils import atomic_write

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
        sha, date, subject, author = fields[i:i + 4]
        normalized = datetime.fromisoformat(date.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
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
    """Extract git log with file change stats."""
    cmd = [
        "git", "-C", repo_path,
        "log", "--format=%H%x1f%ai%x1f%s%x1f%an", "--shortstat", "--all"
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    except FileNotFoundError:
        raise RuntimeError("git binary not found. Install git and ensure it's on PATH.")
    except subprocess.TimeoutExpired:
        raise RuntimeError("git log timed out after 300s. Repository may be too large.")

    if result.returncode != 0:
        raise RuntimeError(f"git log failed: {result.stderr}")

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
            capture_output=True, text=True, cwd=repo_path, timeout=60
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
