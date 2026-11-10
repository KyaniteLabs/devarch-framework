"""AG4TE for Hermes: dig a git repository's history and read its strata.

AG4TE is the Hermes face of DevArch (devarch-framework). A *dig* reads one local repository's
history with ``git log`` (identities, author time with its offset, merge parents,
co-author trailers, per-file line counts, tags) and runs the DevArch pipeline (init, mine,
build-db, signals) into a private workspace under ``<HERMES_HOME>/plugin-data/ag4te/``. It
then folds both into one ``dig.json`` (schema 2, with a manifest: HEAD, ref, DevArch pin,
time zone, thresholds, config hash) that the Desktop page draws: commits per day stacked by
kind of work, eras, quiet gaps, releases, turning points, the hour-by-weekday rhythm,
people (humans, coding agents, bots), the most-changed files and practice health.

Surfaces:
* ``/ag4te list | show <project> | status <project> | dig <repo> [project]``
* ``ag4te_dig`` tool: read-only summary of a finished dig (or the list of digs).
* Desktop page (``desktop/plugin.js``) backed by ``dashboard/plugin_api.py``.

Safety: repositories must sit under ``repo_roots``; project names are validated; DevArch runs
with a scrubbed environment (no API keys or tokens) and a per-step timeout; one dig runs at a
time; DevArch's LLM, network and serve commands are never invoked.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shlex
import subprocess
import tempfile
import threading
import time
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

PLUGIN_NAME = "ag4te"
DEVARCH_PIN = "b44430e198e45bfaee1edb2f3473f7d50ce17bc2"
DEFAULTS: Dict[str, Any] = {
    "devarch_command": f"uvx --from git+https://github.com/KyaniteLabs/devarch-framework@{DEVARCH_PIN} devarch",
    "repo_roots": "~/workspaces",
    "data_dir": "",
    "timeout_seconds": 600,
    "time_zone": "",
    "history": "head",
    "bots": "",
    "allow_dig_on_gateway": False,
}

DIG_FILE = "dig.json"
STATUS_FILE = "ag4te-status.json"
META_FILE = "ag4te-meta.json"
MAX_COMMITS = 4000
MAX_SIGNALS = 400
MAX_DAYS = 365 * 30
GAP_MIN_DAYS = 3        # idle days that make a quiet gap; gaps also cut eras
SIGNAL_MERGE_DAYS = 7   # same-kind signals closer than this fold into one
ERA_MIN_COMMITS = 10    # eras this big get a number and a colour
_PROJECT_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")

# Kinds of work, in the fixed order the chart stacks and colours them.
KINDS = ("feat", "fix", "refactor", "docs", "ops", "test", "other")
_PREFIX_KIND = {
    "feat": "feat", "feature": "feat", "add": "feat",
    "fix": "fix", "bugfix": "fix", "hotfix": "fix",
    "refactor": "refactor", "perf": "refactor", "style": "refactor", "cleanup": "refactor",
    "docs": "docs", "doc": "docs",
    "test": "test", "tests": "test",
    "chore": "ops", "ci": "ops", "build": "ops", "deps": "ops", "release": "ops", "revert": "fix",
    "ops": "ops", "infra": "ops",
}
_CONVENTIONAL_RE = re.compile(r"^\s*([A-Za-z]+)(?:\([^)]*\))?!?\s*:")
_WORD_KIND = (
    (re.compile(r"^\s*(bump|upgrade|release|version)\b", re.I), "ops"),
    (re.compile(r"^\s*(fix|fixes|fixed|repair|resolve|hotfix|correct)\b", re.I), "fix"),
    (re.compile(r"^\s*(refactor|rename|move|extract|simplify|clean|tidy|restructure)\b", re.I), "refactor"),
    (re.compile(r"^\s*(test|tests|cover)\b", re.I), "test"),
    (re.compile(r"\b(readme|docs?|changelog|documentation)\b", re.I), "docs"),
    (re.compile(r"^\s*(add|adds|added|implement|introduce|create|support|new|feat)\b", re.I), "feat"),
)

_ctx = None
_jobs_lock = threading.Lock()
_jobs: Dict[str, threading.Thread] = {}
_cancels: Dict[str, threading.Event] = {}


class DigError(ValueError):
    """A dig request that cannot run (bad project name, repo outside the roots, …)."""


# --------------------------------------------------------------------------- settings


def _cfg(key: str, settings: Optional[Dict[str, Any]] = None) -> Any:
    if settings is not None and key in settings:
        return settings[key]
    try:
        val = _ctx.get_config(key, None) if _ctx is not None else None
    except Exception:  # noqa: BLE001
        val = None
    return DEFAULTS[key] if val is None else val


def snapshot_settings() -> Dict[str, Any]:
    return {k: _cfg(k) for k in DEFAULTS}


def _hermes_root() -> Path:
    try:
        from hermes_constants import get_default_hermes_root  # type: ignore
        return Path(get_default_hermes_root())
    except Exception:  # noqa: BLE001
        raw = (os.environ.get("HERMES_HOME") or "").strip()
        if not raw:
            return Path.home() / ".hermes"
        home = Path(os.path.expanduser(raw))
        return home.parent.parent if home.parent.name == "profiles" else home


def workspace(settings: Optional[Dict[str, Any]] = None) -> Path:
    """DevArch workspace root: ``data_dir`` or ``<HERMES_HOME>/plugin-data/ag4te``."""
    configured = str(_cfg("data_dir", settings) or "").strip()
    return Path(os.path.expanduser(configured)) if configured else _hermes_root() / "plugin-data" / PLUGIN_NAME


def project_dir(project: str, settings: Optional[Dict[str, Any]] = None) -> Path:
    validate_project(project)
    return workspace(settings) / "projects" / project


def repo_roots(settings: Optional[Dict[str, Any]] = None) -> List[Path]:
    raw = _cfg("repo_roots", settings)
    items = raw if isinstance(raw, (list, tuple)) else re.split(r"[,\n" + re.escape(os.pathsep) + r"]", str(raw or ""))
    out = []
    for item in items:
        item = str(item).strip()
        if item:
            try:
                out.append(Path(os.path.expanduser(item)).resolve())
            except (OSError, RuntimeError):
                continue
    return out


# --------------------------------------------------------------------------- validation


def validate_project(name: Any) -> str:
    if not isinstance(name, str) or not _PROJECT_RE.match(name):
        raise DigError("project names are 1-63 lowercase letters, digits, '-' or '_', starting with a letter or digit")
    return name


def project_from_repo(repo: Path) -> str:
    slug = re.sub(r"[^a-z0-9_-]+", "-", repo.name.lower()).strip("-_") or "repo"
    return slug[:63]


def resolve_repo(path: Any, settings: Optional[Dict[str, Any]] = None) -> Path:
    """The repository as a resolved path inside one of ``repo_roots``, holding a ``.git``."""
    if not isinstance(path, str) or not path.strip() or "\x00" in path or len(path) > 1024:
        raise DigError("give a local repository path")
    try:
        repo = Path(os.path.expanduser(path.strip())).resolve(strict=True)
    except (OSError, RuntimeError):
        raise DigError("that path does not exist on the Hermes host") from None
    roots = repo_roots(settings)
    if not any(repo == r or r in repo.parents for r in roots):
        shown = ", ".join(str(r) for r in roots) or "(none configured)"
        raise DigError(f"repositories must live under repo_roots: {shown}")
    if not (repo / ".git").exists():
        raise DigError("that folder is not a git repository (no .git)")
    return repo


def candidate_repos(settings: Optional[Dict[str, Any]] = None, limit: int = 200) -> List[Dict[str, str]]:
    """Git repositories directly in, or one level below, each repo root."""
    seen, out = set(), []
    for root in repo_roots(settings):
        layers = [root]
        try:
            layers += sorted((p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")), key=lambda p: p.name.lower())
        except OSError:
            continue
        for d in layers:
            try:
                rd = d.resolve()
                inside = rd == root or root in rd.parents
                if inside and (rd / ".git").exists() and rd not in seen:
                    seen.add(rd)
                    out.append({"path": str(rd), "name": rd.name, "project": project_from_repo(rd)})
            except (OSError, RuntimeError):
                continue
            if len(out) >= limit:
                return out
    return out


# --------------------------------------------------------------------------- DevArch CLI

_ENV_ALLOW = (
    "PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "LC_CTYPE", "TZ",
    "TMPDIR", "TMP", "TEMP", "SYSTEMROOT", "COMSPEC", "PATHEXT", "APPDATA", "LOCALAPPDATA",
    "USERPROFILE", "XDG_CACHE_HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME",
    "UV_CACHE_DIR", "UV_PYTHON", "UV_INDEX_URL", "UV_EXTRA_INDEX_URL", "PIP_INDEX_URL",
    "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy",
    "SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE",
)


def _scrubbed_env(settings: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    env = {k: os.environ[k] for k in _ENV_ALLOW if os.environ.get(k)}
    ws = workspace(settings)
    (ws / "projects").mkdir(parents=True, exist_ok=True)
    env["DEVARCH_WORKSPACE"] = str(ws)
    env["NO_COLOR"] = "1"
    env["PYTHONUNBUFFERED"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def _wait_proc(proc: subprocess.Popen, timeout: float,
               cancel: Optional[threading.Event] = None) -> Tuple[Optional[str], str, str]:
    """Wait for ``proc``; stop it (TERM, then KILL after 5 s) on cancel or timeout.

    Returns ``(why it was stopped or None, stdout, stderr)``.
    """
    deadline = time.monotonic() + timeout
    why = None
    while True:
        try:
            out, err = proc.communicate(timeout=0.5)
            return why, out or "", err or ""
        except subprocess.TimeoutExpired:
            if cancel is not None and cancel.is_set():
                why = "cancelled"
            elif time.monotonic() > deadline:
                why = f"timed out after {timeout:g}s"
            if why:
                proc.terminate()
                try:
                    out, err = proc.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    out, err = proc.communicate()
                return why, out or "", err or ""


def run_devarch(args: List[str], settings: Optional[Dict[str, Any]] = None,
                cancel: Optional[threading.Event] = None) -> Dict[str, Any]:
    """Run one DevArch command. Never raises: returns ``{ok, code, out, err}``.

    ``cancel`` set while the command runs stops it (TERM, then KILL after 5 s).
    """
    try:
        cmd = shlex.split(str(_cfg("devarch_command", settings))) + [str(a) for a in args]
    except ValueError as exc:
        return {"ok": False, "code": None, "out": "", "err": f"invalid devarch_command: {exc}"}
    if not cmd:
        return {"ok": False, "code": None, "out": "", "err": "devarch_command is empty"}
    try:
        env = _scrubbed_env(settings)
    except OSError as exc:
        return {"ok": False, "code": None, "out": "", "err": f"workspace unavailable: {exc}"}
    try:
        timeout = max(10.0, float(_cfg("timeout_seconds", settings)))
    except (TypeError, ValueError):
        timeout = float(DEFAULTS["timeout_seconds"])
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env,
                                cwd=env["DEVARCH_WORKSPACE"], stdin=subprocess.DEVNULL)
    except (FileNotFoundError, PermissionError) as exc:
        return {"ok": False, "code": None, "out": "", "err": f"devarch not runnable: {exc}"}
    except OSError as exc:
        return {"ok": False, "code": None, "out": "", "err": f"devarch failed to start: {exc}"}
    why, out, err = _wait_proc(proc, timeout, cancel)
    if why:
        return {"ok": False, "code": proc.returncode, "out": "", "err": why, "cancelled": why == "cancelled"}
    return {"ok": proc.returncode == 0, "code": proc.returncode,
            "out": (out or "")[-4000:], "err": (err or "")[-4000:]}


# --------------------------------------------------------------------------- files


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, separators=(",", ":"))
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# --------------------------------------------------------------------------- git history
#
# AG4TE reads git itself (one ``git log``) so the dig rests on full identities, one clock,
# merge parents, paths and tags. DevArch still mines, builds its database and finds
# signals; its subject-only CSV is only the fallback for digs made before schema 2.

SCHEMA_VERSION = 2
GIT_FILE = "ag4te-git.txt"
REPO_FILE = "ag4te-repo.json"
# One record per commit: U+001E starts it, U+001F splits fields, U+001D splits co-authors.
_GIT_FORMAT = ("%x1e%H%x1f%P%x1f%aI%x1f%cI%x1f%aN%x1f%aE%x1f%cN%x1f%cE%x1f%s%x1f"
               "%(trailers:key=Co-authored-by,valueonly,separator=%x1d)")
_GIT_ENV_ALLOW = ("PATH", "HOME", "USER", "LOGNAME", "TMPDIR", "SYSTEMROOT")


def _git_env() -> Dict[str, str]:
    env = {k: os.environ[k] for k in _GIT_ENV_ALLOW if os.environ.get(k)}
    env.update(GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0", LC_ALL="C", GIT_PAGER="cat")
    return env


def _git(repo: Path, *args: str, timeout: float = 30.0) -> Optional[str]:
    try:
        res = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, env=_git_env(),
                             timeout=timeout, stdin=subprocess.DEVNULL, errors="replace")
    except (OSError, subprocess.TimeoutExpired):
        return None
    return res.stdout if res.returncode == 0 else None


def mine_git(repo: Path, pdir: Path, settings: Optional[Dict[str, Any]] = None,
             cancel: Optional[threading.Event] = None) -> Dict[str, Any]:
    """Write ``data/ag4te-git.txt`` (commits with numstat) and ``data/ag4te-repo.json``.

    Never raises: returns ``{ok, err}`` like ``run_devarch``.
    """
    data = pdir / "data"
    data.mkdir(parents=True, exist_ok=True)
    head = (_git(repo, "rev-parse", "--verify", "-q", "HEAD") or "").strip()
    if not head:
        return {"ok": False, "err": "git could not read HEAD (empty or not a repository)"}
    history = "all" if str(_cfg("history", settings)).strip().lower() == "all" else "head"
    cmd = ["git", "-C", str(repo), "-c", "core.quotepath=off", "log", "--no-color", "--no-renames",
           "--numstat", f"--format={_GIT_FORMAT}", "--all" if history == "all" else "HEAD"]
    try:
        timeout = max(10.0, float(_cfg("timeout_seconds", settings)))
    except (TypeError, ValueError):
        timeout = float(DEFAULTS["timeout_seconds"])
    tmp = data / (GIT_FILE + ".part")
    try:
        with tmp.open("w", encoding="utf-8") as fh:
            proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.PIPE, text=True, env=_git_env(),
                                    stdin=subprocess.DEVNULL)
            why, _, err = _wait_proc(proc, timeout, cancel)
    except OSError as exc:
        return {"ok": False, "err": f"git failed to start: {exc}"}
    if why or proc.returncode != 0:
        try:
            tmp.unlink()
        except OSError:
            pass
        return {"ok": False, "err": why or (err.strip().splitlines() or ["git log failed"])[-1],
                "cancelled": why == "cancelled"}
    os.replace(tmp, data / GIT_FILE)
    tags = []
    raw = _git(repo, "for-each-ref", "--sort=creatordate", "refs/tags",
               "--format=%(refname:short)%1f%(creatordate:iso-strict)%1f%(*objectname)%1f%(objectname)") or ""
    for line in raw.splitlines():
        parts = line.split("\x1f")
        if len(parts) == 4 and parts[0]:
            tags.append({"name": parts[0][:80], "t": parts[1], "sha": (parts[2] or parts[3])[:40]})
    _write_json(data / REPO_FILE, {
        "head_sha": head, "ref": (_git(repo, "symbolic-ref", "--short", "-q", "HEAD") or "").strip() or None,
        "history": history, "mailmap": (repo / ".mailmap").exists(), "tags": tags[-500:],
    })
    return {"ok": True, "err": ""}


def parse_git(text: str) -> List[Dict[str, Any]]:
    """Commits from ``ag4te-git.txt``: identities, both dates, parents, co-authors, paths."""
    commits: List[Dict[str, Any]] = []
    for rec in text.split("\x1e"):
        if not rec.strip():
            continue
        head, _, body = rec.partition("\n")
        f = head.split("\x1f")
        if len(f) < 10:
            continue
        try:
            adt = datetime.fromisoformat(f[2].strip())
            cdt = datetime.fromisoformat(f[3].strip())
        except ValueError:
            continue
        if adt.tzinfo is None or cdt.tzinfo is None:
            continue
        co = []
        for item in f[9].split("\x1d"):
            m = re.match(r"\s*(.*?)\s*<([^>]*)>\s*$", item)
            if m and (m.group(1) or m.group(2)):
                co.append((m.group(1), m.group(2).strip()))
        paths, ins, dels = [], 0, 0
        for line in body.splitlines():
            parts = line.split("\t", 2)
            if len(parts) == 3:
                a = int(parts[0]) if parts[0].isdigit() else 0
                d = int(parts[1]) if parts[1].isdigit() else 0
                paths.append((parts[2], a, d))
                ins += a
                dels += d
        commits.append({"sha": f[0].strip()[:40], "parents": f[1].split(), "dt": adt, "cdt": cdt,
                        "name": f[4].strip(), "email": f[5].strip(), "msg": f[8].strip(), "co": co,
                        "files": len(paths), "ins": ins, "del": dels, "paths": paths})
    return commits


# --------------------------------------------------------------------------- identities

_SCOPE_RE = re.compile(r"^\s*[A-Za-z]+\(([^)]{1,40})\)!?\s*:")

_BOT_RE = re.compile(r"\[bot\]|(?:^|[\s._+-])bot(?:$|[\s@._+-])|renovate|dependabot|github-actions|"
                     r"greenkeeper|snyk-bot|semantic-release|pre-commit-ci|web-flow", re.I)
# Coding agents credited as authors or co-authors. Matched on the email, not the name.
_AGENT_RE = re.compile(r"noreply@anthropic\.com|codex@openai\.com|@openai\.com$|cursoragent@cursor\.com|"
                       r"copilot|devin-ai-integration|noreply@google\.com|aider@aider\.chat|noreply@factory\.ai", re.I)
_SHARED_EMAILS = {"noreply@github.com", ""}
_GH_NOREPLY = re.compile(r"^(?:\d+\+)?([^@]+)@users\.noreply\.github\.com$", re.I)


def _norm_name(n: str) -> str:
    return " ".join(re.sub(r"[-_.]+", " ", (n or "").casefold()).split())


def build_identities(pairs: Counter, bots: Any = "") -> Tuple[Dict[Tuple[str, str], int], List[Dict[str, Any]]]:
    """Group (name, email) pairs into people, bots and agents.

    Pairs join when they share an email, a GitHub noreply login that matches a name, or a
    name (ignoring case and punctuation; a one-word name joins the single longer name that
    starts with it). Bots and agents never join humans by name. ``bots`` names extra bot
    or service accounts: comma separated names or emails, ``*`` wildcards allowed.
    ``.mailmap`` is already applied by git.
    """
    import fnmatch
    extra = [x.strip().casefold() for x in (bots if isinstance(bots, (list, tuple)) else str(bots or "").split(","))
             if x and str(x).strip()]
    keys = list(pairs)

    def kind(name: str, email: str) -> str:
        if any(fnmatch.fnmatchcase(name.casefold(), p) or fnmatch.fnmatchcase(email.casefold(), p) for p in extra):
            return "bot"
        if _BOT_RE.search(name) or _BOT_RE.search(email):
            return "bot"
        if _AGENT_RE.search(email):
            return "agent"
        return "human"

    kinds = {k: kind(*k) for k in keys}
    parent = list(range(len(keys)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        if kinds[keys[i]] != kinds[keys[j]]:
            return
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[rj] = ri

    by_email: Dict[str, int] = {}
    by_name: Dict[str, int] = {}
    for i, (name, email) in enumerate(keys):
        em = email.casefold()
        if em not in _SHARED_EMAILS:
            if em in by_email:
                union(by_email[em], i)
            else:
                by_email[em] = i
        nn = _norm_name(name)
        if nn and kinds[keys[i]] == "human":
            if nn in by_name:
                union(by_name[nn], i)
            else:
                by_name[nn] = i
    for i, (name, email) in enumerate(keys):  # a GitHub login that is also someone's name
        m = _GH_NOREPLY.match(email)
        if m and _norm_name(m.group(1)) in by_name:
            union(by_name[_norm_name(m.group(1))], i)
    multi = [n for n in by_name if " " in n]
    for n, i in by_name.items():  # "simon" joins the one "simon …" name
        if " " not in n:
            longer = [o for o in multi if o.split(" ", 1)[0] == n]
            if len(longer) == 1:
                union(by_name[longer[0]], i)

    groups: Dict[int, List[int]] = {}
    for i in range(len(keys)):
        groups.setdefault(find(i), []).append(i)
    ident_of: Dict[Tuple[str, str], int] = {}
    people: List[Dict[str, Any]] = []
    for members in sorted(groups.values(), key=lambda ms: -sum(pairs[keys[i]] for i in ms)):
        names = Counter()
        for i in members:
            names[keys[i][0]] += pairs[keys[i]]
        kd = kinds[keys[members[0]]]
        if kd == "human":
            name = max(names, key=lambda n: (len(n.split()), names[n], len(n)))
        else:  # "Claude Opus 4.7" + "Claude Fable 5" -> "Claude"
            words = [n.split() for n in names]
            common = []
            for col in zip(*words):
                if len({w.casefold() for w in col}) != 1:
                    break
                common.append(col[0])
            name = " ".join(common) if len(names) > 1 and common else names.most_common(1)[0][0]
        idx = len(people)
        people.append({"name": (name or keys[members[0]][1] or "unknown")[:80], "kind": kd,
                       "spellings": len(members)})
        for i in members:
            ident_of[keys[i]] = idx
    return ident_of, people


# --------------------------------------------------------------------------- classify


# A free-form area prefix ("eval: fix …", "site/docs: add …") that is not a conventional type.
_AREA_RE = re.compile(r"^\s*[\w./-]{1,30}:\s+")
_REVERT_RE = re.compile(r'^\s*(revert\b|revert:|Revert ")', re.I)
_MERGE_MSG_RE = re.compile(r"^\s*merge (pull request|branch|remote-tracking|tag)\b", re.I)
_PR_RE = re.compile(r"\(#(\d{1,7})\)\s*$|^Merge pull request #(\d{1,7})\b")


def kind_of(message: str) -> str:
    """The kind of work a commit subject describes. Reverts count as fixes."""
    msg = message or ""
    if _REVERT_RE.match(msg):
        return "fix"
    m = _CONVENTIONAL_RE.match(msg)
    if m:
        kind = _PREFIX_KIND.get(m.group(1).lower())
        if kind:
            return kind
    for text in (msg, _AREA_RE.sub("", msg, count=1)):
        for rx, kind in _WORD_KIND:
            if rx.search(text):
                return kind
    return "other"


_STATS_RE = re.compile(r"(\d+) files? changed(?:, (\d+) insertions?\(\+\))?(?:, (\d+) deletions?\(-\))?")


def parse_commits(text: str) -> List[Dict[str, Any]]:
    """Commits from DevArch's ``github-commits-with-stats.txt`` (fields split by U+001F).

    The pre-schema-2 fallback: no email, parents, co-authors or paths.
    """
    commits: List[Dict[str, Any]] = []
    for line in text.splitlines():
        if "\x1f" in line:
            parts = line.split("\x1f")
            if len(parts) < 4:
                continue
            sha, when, msg, author = parts[0].strip(), parts[1].strip(), parts[2], parts[3].strip()
            try:
                dt = datetime.strptime(when, "%Y-%m-%d %H:%M:%S %z")
            except ValueError:
                continue
            commits.append({"sha": sha[:40], "parents": None, "dt": dt, "cdt": dt, "name": author, "email": "",
                            "msg": msg.strip(), "co": [], "files": 0, "ins": 0, "del": 0, "paths": []})
        elif commits:
            m = _STATS_RE.search(line)
            if m:
                c = commits[-1]
                c["files"], c["ins"], c["del"] = int(m.group(1)), int(m.group(2) or 0), int(m.group(3) or 0)
    return commits


def parse_csv_commits(path: Path) -> List[Dict[str, Any]]:
    import csv
    out = []
    try:
        with path.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh):
                try:
                    dt = datetime.strptime((row.get("date") or "").strip(), "%Y-%m-%d %H:%M:%S %z")
                except ValueError:
                    continue
                out.append({"sha": (row.get("hash") or "")[:40], "parents": None, "dt": dt, "cdt": dt,
                            "name": (row.get("author") or "").strip(), "email": "",
                            "msg": (row.get("message") or "").strip(), "co": [], "files": 0, "ins": 0, "del": 0,
                            "paths": []})
    except OSError:
        pass
    return out


def author_aliases(counts: Counter) -> Dict[str, str]:
    """Name-only alias map (kept for callers without emails): name -> display name."""
    ident_of, people = build_identities(Counter({(n, ""): c for n, c in counts.items()}))
    return {n: people[ident_of[(n, "")]]["name"] for n in counts}


def project_zone(settings: Optional[Dict[str, Any]] = None):
    """The one clock a dig buckets days and hours by: ``time_zone`` or the host's zone."""
    name = str(_cfg("time_zone", settings) or "").strip() or (os.environ.get("TZ") or "").strip()
    if name:
        try:
            from zoneinfo import ZoneInfo
            return ZoneInfo(name), name
        except Exception:  # noqa: BLE001 - bad name: fall back to the host zone
            pass
    tz = datetime.now().astimezone().tzinfo
    return tz, str(tz or "local")


def _date(s: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(s)[:10])
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- practices

_GEN_PATH_RE = re.compile(r"(^|/)(package-lock\.json|yarn\.lock|pnpm-lock\.yaml|poetry\.lock|uv\.lock|Cargo\.lock|"
                          r"go\.sum|composer\.lock|Gemfile\.lock|bun\.lockb?)$|(^|/)(dist|build|vendor|node_modules)/|\.min\.(js|css)$")
_PRACTICES = (
    # name, message pattern (word bounded), path pattern, target share of work commits, advice
    ("CI/CD pipeline", r"\b(ci|cd|ci/cd|github actions?|workflows?|deploy(s|ed|ing|ment)?|pipelines?|release)\b",
     r"(^|/)(\.github/workflows/|\.gitlab-ci\.yml$|\.circleci/|Jenkinsfile$|\.forgejo/workflows/|\.woodpecker)",
     0.04, "Run the quality gates on every push."),
    ("Tests", r"\b(tests?|specs?|coverage|vitest|pytest|jest|e2e)\b",
     r"(^|/)(tests?|__tests__|spec|e2e)/|(_test|\.test|\.spec)\.[a-z]+$|(^|/)test_[^/]+\.py$",
     0.15, "Land behaviour tests with the change, not after it."),
    ("Refactoring", None, None, 0.08, "Reserve time to simplify, not only to add."),
    ("Security review", r"\b(security|cve-?\d*|xss|csrf|injection|secrets?|vulnerab\w*|sanitiz\w*|auth[nz]?)\b",
     r"(^|/)SECURITY\.md$|(^|/)\.github/(dependabot\.yml|codeql)", 0.025,
     "Tie each security change to a check that would catch its return."),
    ("Documentation", None, r"(^|/)(docs?/|README|CHANGELOG)|\.mdx?$", 0.08,
     "Keep the README and docs moving with the code."),
)


def practices(work: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Practice health from human and agent work commits (no merges, no bots).

    Evidence is a commit whose subject names the practice (word bounded) or whose paths
    touch it. Status compares the share with a target; ROI is how far below target it
    sits (0 when healthy, 5 when there is no evidence at all).
    """
    total = len(work)
    out = []
    for name, msg_rx, path_rx, target, advice in _PRACTICES:
        mrx = re.compile(msg_rx, re.I) if msg_rx else None
        prx = re.compile(path_rx) if path_rx else None
        hits = []
        for c in work:
            if (name == "Refactoring" and c["kind"] == "refactor") or (name == "Documentation" and c["kind"] == "docs") \
                    or (mrx and mrx.search(c["msg"])) or (prx and any(prx.search(p[0]) for p in c["paths"])):
                hits.append(c)
        share = len(hits) / total if total else 0.0
        status = "PRESENT" if share >= target else "EMERGING" if share >= target / 4 else "ABSENT"
        need = max(0.0, target - share) / target
        out.append({
            "practice": name, "status": status,
            "severity": {"ABSENT": "HIGH", "EMERGING": "MEDIUM", "PRESENT": "LOW"}[status],
            "n": len(hits), "of": total, "share": round(share, 4), "target": target, "roi": round(5 * need, 1),
            "recommendation": f"{len(hits)} of {total} commits ({share:.0%}); healthy is {target:.0%} or more. {advice}",
            "advice": advice,
            "examples": [c["sha"][:10] for c in hits[-3:]][::-1],
        })
    return out


# --------------------------------------------------------------------------- signals

_DIR_RE = re.compile(r"(\d+(?:\.\d+)?)x (up|down)shift")


def fold_signals(raw: List[Any], merge_days: int) -> List[Dict[str, Any]]:
    """DevArch signals, deduplicated.

    Gap signals go (gaps are drawn from the commits). Author shifts go (AG4TE recomputes
    them from identities, per era). A run of same-type, same-direction signals less than
    ``merge_days`` apart becomes one signal with an onset, a peak and an end.
    """
    items = []
    for sg in raw or []:
        if not isinstance(sg, dict) or not _date(sg.get("date")):
            continue
        typ = str(sg.get("type") or "other")[:24]
        if typ in ("gap", "author"):
            continue
        detail = str(sg.get("detail") or "")[:240]
        m = _DIR_RE.search(detail)
        items.append({"d": str(sg["date"])[:10], "type": typ, "detail": detail,
                      "dir": m.group(2) if m else "", "mag": float(m.group(1)) if m else 0.0,
                      "strong": sg.get("strength") == "strong"})
    items.sort(key=lambda x: x["d"])
    out: List[Dict[str, Any]] = []
    open_runs: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for it in items:
        key = (it["type"], it["dir"])
        run = open_runs.get(key)
        if run and (_date(it["d"]) - _date(run["end"])).days < merge_days:
            run["end"] = it["d"]
            run["n"] += 1
            run["strong"] = run["strong"] or it["strong"]
            if it["mag"] > run["mag"] or (not run["mag"] and it["strong"]):
                run.update(peak=it["d"], detail=it["detail"], mag=it["mag"])
            continue
        run = {"d": it["d"], "peak": it["d"], "end": it["d"], "type": it["type"], "detail": it["detail"],
               "mag": it["mag"], "strong": it["strong"], "n": 1}
        open_runs[key] = run
        out.append(run)
    return [{"d": r["d"], "peak": r["peak"], "end": r["end"], "type": r["type"], "detail": r["detail"],
             "n": r["n"], "strength": "strong" if r["strong"] else "moderate"} for r in out]


def _restates_gap(sg: Dict[str, Any], gaps: List[Dict[str, Any]], slack: int = 2) -> bool:
    """A slowdown running into a quiet gap, or a speed-up right out of one, is that gap again."""
    s, e = _date(sg["d"]), _date(sg["end"])
    down = "downshift" in sg["detail"]
    for g in gaps:
        gs, ge = _date(g["start"]), _date(g["end"])
        if down and s - timedelta(days=slack) <= gs <= e + timedelta(days=slack):
            return True
        if not down and ge - timedelta(days=slack) <= s <= ge + timedelta(days=slack + 1):
            return True
    return False


# --------------------------------------------------------------------------- summary


def _sha(v: Any) -> str:
    import hashlib
    return hashlib.sha256(json.dumps(v, sort_keys=True, default=str).encode()).hexdigest()[:16]


def summarize(pdir: Path, *, repo: str = "", project: str = "",
              settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Fold a dig's project directory into the ``dig.json`` the Desktop page draws."""
    data = pdir / "data"
    repo_doc = _read_json(data / REPO_FILE)
    repo_doc = repo_doc if isinstance(repo_doc, dict) else {}
    source = "git"
    try:
        commits = parse_git((data / GIT_FILE).read_text(encoding="utf-8", errors="replace"))
    except OSError:
        commits = []
    has_stats = bool(commits)
    if not commits:
        source = "devarch"
        try:
            commits = parse_commits((data / "github-commits-with-stats.txt").read_text(encoding="utf-8", errors="replace"))
            has_stats = bool(commits)
        except OSError:
            commits = []
    if not commits:
        commits = parse_csv_commits(data / "github-commits.csv")
        has_stats = False
    if source == "devarch":  # DevArch mines --all: keep one copy of each commit
        seen, uniq = set(), []
        for c in commits:
            if c["sha"] not in seen:
                seen.add(c["sha"])
                uniq.append(c)
        commits = uniq
    commits.sort(key=lambda c: (c["dt"], c["sha"]))  # one instant order, whatever the offsets

    zone, zone_name = project_zone(settings)
    thresholds = {"quiet_gap_days": GAP_MIN_DAYS, "signal_merge_days": SIGNAL_MERGE_DAYS,
                  "era_min_commits": ERA_MIN_COMMITS, "max_commits_listed": MAX_COMMITS}
    bots = _cfg("bots", settings)
    manifest = {
        "schema_version": SCHEMA_VERSION, "source": source,
        "head_sha": repo_doc.get("head_sha"), "ref": repo_doc.get("ref"), "history": repo_doc.get("history"),
        "mailmap": bool(repo_doc.get("mailmap")), "devarch_pin": DEVARCH_PIN, "time_zone": zone_name,
        "thresholds": thresholds,
        "config_hash": _sha({"zone": zone_name, "bots": bots, "history": _cfg("history", settings),
                             "thresholds": thresholds, "devarch": _cfg("devarch_command", settings)}),
    }
    if not repo:
        meta = _read_json(pdir / META_FILE)
        repo = str((meta or {}).get("repo") or "") if isinstance(meta, dict) else ""
    out: Dict[str, Any] = {"project": project or pdir.name, "repo": repo, "kinds": list(KINDS),
                           "manifest": manifest, "thresholds": thresholds,
                           "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                           "has_line_stats": has_stats, "has_paths": source == "git"}

    # identities
    pairs = Counter()
    for c in commits:
        pairs[(c["name"], c["email"])] += 1
        for co in c["co"]:
            pairs[co] += 0
    ident_of, people = build_identities(pairs, bots)
    for p in people:
        p.update(n=0, co=0)

    for c in commits:
        c["who"] = ident_of[(c["name"], c["email"])]
        c["co_ids"] = sorted({ident_of[co] for co in c["co"]} - {c["who"]})
        c["merge"] = (len(c["parents"]) > 1) if c["parents"] is not None else bool(_MERGE_MSG_RE.match(c["msg"]))
        c["revert"] = bool(_REVERT_RE.match(c["msg"]))
        c["bot"] = people[c["who"]]["kind"] == "bot"
        c["kind"] = "merge" if c["merge"] else kind_of(c["msg"])
        c["local"] = c["dt"].astimezone(zone)
        m = _PR_RE.search(c["msg"])
        c["pr"] = int(m.group(1) or m.group(2)) if m else None
        if c["merge"]:  # merges are bookkeeping, not work: keep them out of per-person counts
            people[c["who"]]["m"] = people[c["who"]].get("m", 0) + 1
            continue
        people[c["who"]]["n"] += 1
        for i in c["co_ids"]:
            people[i]["co"] += 1

    work = [c for c in commits if not c["merge"]]
    merges = len(commits) - len(work)
    out.update(commit_count=len(work), merge_count=merges, total_commits=len(commits))
    if not work:
        out.update({"empty": True, "days": [], "commits": [], "clusters": [], "gaps": [], "signals": [],
                    "rhythm": [[0] * 24 for _ in range(7)], "authors": [], "sdlc": [], "load": None,
                    "paths": [], "releases": [], "people": {"human": 0, "agent": 0, "bot": 0}})
        return out

    first, last = work[0]["local"].date(), work[-1]["local"].date()
    if (last - first).days > MAX_DAYS:
        first = last - timedelta(days=MAX_DAYS)
    by_day: Dict[date, Dict[str, Any]] = {}
    rhythm = [[0] * 24 for _ in range(7)]
    kinds = Counter()
    for c in work:
        kinds[c["kind"]] += 1
        if not c["bot"]:
            rhythm[c["local"].weekday()][c["local"].hour] += 1
        d = c["local"].date()
        if d < first:
            continue
        slot = by_day.setdefault(d, {"n": 0, "k": Counter(), "ins": 0, "del": 0})
        slot["n"] += 1
        slot["k"][c["kind"]] += 1
        slot["ins"] += c["ins"]
        slot["del"] += c["del"]

    days, gaps, run_start = [], [], None
    longest_streak = streak = 0
    d = first
    while d <= last:
        slot = by_day.get(d)
        if slot:
            days.append({"d": d.isoformat(), "n": slot["n"], "k": [slot["k"].get(k, 0) for k in KINDS],
                         "ins": slot["ins"], "del": slot["del"]})
            streak += 1
            longest_streak = max(longest_streak, streak)
            if run_start is not None and (d - run_start).days >= GAP_MIN_DAYS:
                gaps.append({"start": run_start.isoformat(), "end": (d - timedelta(days=1)).isoformat(),
                             "days": (d - run_start).days})
            run_start = None
        else:
            days.append({"d": d.isoformat(), "n": 0, "k": [0] * len(KINDS), "ins": 0, "del": 0})
            streak = 0
            run_start = run_start or d
        d += timedelta(days=1)

    # Eras: the stretches between quiet gaps. One gap rule cuts eras and draws gaps.
    clusters = []
    start = first
    for g in sorted(gaps, key=lambda g: g["start"]) + [{"start": (last + timedelta(days=1)).isoformat(), "end": None}]:
        end = _date(g["start"]) - timedelta(days=1)
        if end >= start:
            s0, e0 = start.isoformat(), end.isoformat()
            inside = [c for c in work if s0 <= c["local"].date().isoformat() <= e0]
            k = Counter(c["kind"] for c in inside)
            humans = Counter(c["who"] for c in inside if people[c["who"]]["kind"] != "bot")
            scopes = Counter(m.group(1).strip().lower() for c in inside if not c["bot"]
                             for m in [_SCOPE_RE.match(c["msg"])] if m)
            clusters.append({"start": s0, "end": e0, "commits": len(inside),
                             "active_days": len({c["local"].date() for c in inside}),
                             "k": [k.get(x, 0) for x in KINDS],
                             "author": people[humans.most_common(1)[0][0]]["name"] if humans else "",
                             "scope": scopes.most_common(1)[0][0][:24] if scopes else ""})
        if g["end"]:
            start = _date(g["end"]) + timedelta(days=1)

    signals_doc = _read_json(data / "detected-signals.json") or {}
    raw_signals = signals_doc.get("signals") if isinstance(signals_doc, dict) else None
    signals = []
    for sg in fold_signals(raw_signals or [], SIGNAL_MERGE_DAYS):
        if sg["type"] == "velocity" and _restates_gap(sg, gaps):
            continue
        signals.append(sg)
    prev = None
    for cl in clusters:  # a hand-over between different people is a turning point
        if cl["author"] and prev and cl["author"] != prev and cl["commits"] >= ERA_MIN_COMMITS:
            signals.append({"d": cl["start"], "peak": cl["start"], "end": cl["start"], "type": "author", "n": 1,
                            "detail": f"most commits now by {cl['author']} (was {prev})", "strength": "strong"})
        if cl["author"] and cl["commits"] >= ERA_MIN_COMMITS:
            prev = cl["author"]
    signals.sort(key=lambda s: s["d"])
    signals = signals[:MAX_SIGNALS]

    # change size (lines touched, generated files left out) instead of message length
    sizes = Counter()
    order = ("TRIVIAL", "ROUTINE", "MODERATE", "HIGH", "INTENSE")
    load = None
    if has_stats:
        for c in work:
            if c["paths"]:
                n = sum(a + b for p, a, b in c["paths"] if not _GEN_PATH_RE.search(p))
            else:
                n = c["ins"] + c["del"]
            sizes[order[0] if n <= 10 else order[1] if n <= 50 else order[2] if n <= 200 else order[3] if n <= 800 else order[4]] += 1
        load = [{"level": k, "n": sizes.get(k, 0)} for k in order]

    churn: Dict[str, Dict[str, Any]] = {}
    for c in work:
        if c["bot"]:
            continue
        for p, a, b in c["paths"]:
            row = churn.setdefault(p, {"path": p[:160], "ins": 0, "del": 0, "commits": 0})
            row["ins"] += a
            row["del"] += b
            row["commits"] += 1
    # hotspots: the files changed in the most commits (generated files and lockfiles left out)
    paths = sorted((r for r in churn.values() if not _GEN_PATH_RE.search(r["path"])),
                   key=lambda r: (-r["commits"], -(r["ins"] + r["del"]), r["path"]))[:12]

    by_sha = {c["sha"]: c for c in commits}
    releases = []
    for t in repo_doc.get("tags") or []:
        if not isinstance(t, dict):
            continue
        c = by_sha.get(str(t.get("sha") or ""))
        try:
            when = c["local"] if c else datetime.fromisoformat(str(t.get("t"))).astimezone(zone)
        except ValueError:
            continue
        releases.append({"name": str(t.get("name"))[:80], "d": when.date().isoformat(),
                         "sha": str(t.get("sha") or "")[:10], "on_history": bool(c)})
    releases.sort(key=lambda r: r["d"])

    human_work = [c for c in work if not c["bot"]]
    agent_ids = {i for i, p in enumerate(people) if p["kind"] == "agent"}
    with_agent = sum(1 for c in human_work if c["who"] in agent_ids or agent_ids.intersection(c["co_ids"]))
    active = sum(1 for x in days if x["n"])
    busiest = max(days, key=lambda x: x["n"])
    ranked = sorted((p for p in people if p["n"] or p["co"]), key=lambda p: (-(p["n"] + p["co"]), -p["n"], p["name"]))
    out.update({
        "first": first.isoformat(), "last": last.isoformat(), "span_days": (last - first).days + 1,
        "active_days": active, "longest_streak": longest_streak,
        "longest_gap": max((g["days"] for g in gaps), default=0),
        "busiest_day": {"d": busiest["d"], "n": busiest["n"]},
        "insertions": sum(c["ins"] for c in work), "deletions": sum(c["del"] for c in work),
        "kind_totals": [kinds.get(k, 0) for k in KINDS],
        "authors": [{"name": p["name"], "n": p["n"], "co": p["co"], "kind": p["kind"], "spellings": p["spellings"],
                     "merges": p.get("m", 0)} for p in ranked[:10]],
        "author_count": sum(1 for p in people if p["kind"] == "human" and p["n"]),
        "people": {k: sum(1 for p in people if p["kind"] == k and (p["n"] or p["co"])) for k in ("human", "agent", "bot")},
        "agent_assisted": with_agent, "bot_commits": len(work) - len(human_work),
        "pr_count": len({c["pr"] for c in commits if c["pr"]}),
        "days": days, "gaps": sorted(gaps, key=lambda g: -g["days"])[:40], "clusters": clusters[:200],
        "signals": signals, "rhythm": rhythm, "sdlc": practices(human_work), "load": load,
        "paths": paths, "releases": releases[-200:],
        "commits_listed": min(len(commits), MAX_COMMITS), "commits_truncated": len(commits) > MAX_COMMITS,
        "commits": [{"sha": c["sha"][:10], "t": c["local"].isoformat(), "day": c["local"].date().isoformat(),
                     "tz": c["dt"].strftime("%z"), "kind": c["kind"], "msg": c["msg"][:200],
                     "author": people[c["who"]]["name"], "ak": people[c["who"]]["kind"][0],
                     "co": [people[i]["name"] for i in c["co_ids"]][:4],
                     "pr": c["pr"], "rv": c["revert"] or None,
                     "ins": c["ins"], "del": c["del"], "files": c["files"]}
                    for c in reversed(commits[-MAX_COMMITS:])],
    })
    return out


# --------------------------------------------------------------------------- digs


# The dig lifecycle, made explicit. ``interrupted`` is derived on read (never written):
# a status file says "running" but no thread in this process owns it.
#   none ──start──▶ running ──▶ done
#                      │  └───▶ failed
#                      └───▶ cancelled   (Stop pressed; the running command is killed)
#   done / failed / cancelled ──start──▶ running   (a re-dig replaces the old status)
#   failed / cancelled ──resume──▶ running        (skips the steps already finished)
DIG_STATES = ("none", "running", "done", "failed", "cancelled")
_TRANSITIONS = {
    "none": {"running"},
    "running": {"running", "done", "failed", "cancelled"},
    "done": {"running"},
    "failed": {"running"},
    "cancelled": {"running"},
}


def _set_status(pdir: Path, *, fresh: bool = False, **fields: Any) -> Dict[str, Any]:
    """Merge ``fields`` into the status file. ``fresh`` starts a new run's record.

    A state change outside ``_TRANSITIONS`` raises, so a late writer (say a crash
    handler racing a finished run) cannot flip a terminal state behind the UI's back.
    """
    cur = {} if fresh else _read_json(pdir / STATUS_FILE)
    cur = cur if isinstance(cur, dict) else {}
    if "state" in fields:
        was, to = cur.get("state") or "none", fields["state"]
        if to not in _TRANSITIONS.get(was, set()):
            raise DigError(f"dig state cannot go from {was} to {to}")
    cur.update(fields, updated_at=time.time())
    _write_json(pdir / STATUS_FILE, cur)
    return cur


def read_status(project: str, settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    pdir = project_dir(project, settings)
    st = _read_json(pdir / STATUS_FILE)
    st = st if isinstance(st, dict) else {"state": "none"}
    with _jobs_lock:
        alive = project in _jobs and _jobs[project].is_alive()
    if st.get("state") == "running" and not alive:
        st = {**st, "state": "failed", "interrupted": True,
              "error": st.get("error") or "the dig stopped when Hermes restarted; dig again to finish it"}
    return st


GIT_STEP = "__git__"


def dig_steps(repo: Path, project: str) -> List[Tuple[str, List[str], bool]]:
    """(label, args, required). A required step that fails stops the dig.

    ``__git__`` is AG4TE's own ``git log`` read; the rest are DevArch commands.
    """
    return [
        ("Opening the project", ["init", project, "--description", f"AG4TE dig of {repo.name}"], True),
        ("Reading git history", [GIT_STEP], True),
        ("Mining commits", ["mine", str(repo), "--project", project], False),
        ("Building the database", ["build-db", project], False),
        ("Finding signals", ["signals", project], False),
    ]


def run_dig(repo: Path, project: str, settings: Optional[Dict[str, Any]] = None,
            runner: Callable[..., Dict[str, Any]] = run_devarch,
            cancel: Optional[threading.Event] = None, skip: Optional[List[str]] = None) -> Dict[str, Any]:
    """Run the pipeline and write ``dig.json``. Returns the final status.

    ``skip`` lists step labels a resumed dig already finished. ``cancel`` stops the dig
    between steps and, for the real runner, kills the command in flight.
    """
    pdir = project_dir(project, settings)
    pdir.mkdir(parents=True, exist_ok=True)
    steps = dig_steps(repo, project)
    skip_set = set(skip or [])
    done_labels: List[str] = [lb for lb, _, _ in steps if lb in skip_set]
    warnings: List[str] = []
    _write_json(pdir / META_FILE, {"repo": str(repo), "project": project})
    prior = _read_json(pdir / STATUS_FILE)
    _set_status(pdir, fresh=not (isinstance(prior, dict) and prior.get("state") == "running"),
                state="running", repo=str(repo), step=0, steps=len(steps) + 1, label=steps[0][0],
                started_at=time.time(), error=None, warnings=[], completed=done_labels, resumed=bool(skip_set))

    def stopped() -> Dict[str, Any]:
        return _set_status(pdir, state="cancelled", error=None, cancelling=False, warnings=warnings,
                           completed=done_labels, finished_at=time.time())

    for i, (label, args, required) in enumerate(steps):
        if label in skip_set:
            continue
        if cancel is not None and cancel.is_set():
            return stopped()
        _set_status(pdir, step=i, label=label)
        if args == [GIT_STEP]:
            res = mine_git(repo, pdir, settings, cancel)
        else:
            res = runner(args, settings, cancel) if runner is run_devarch else runner(args, settings)
        if cancel is not None and cancel.is_set():
            return stopped()
        if not res.get("ok"):
            tail = (res.get("err") or res.get("out") or "").strip().splitlines()[-1:] or ["no output"]
            msg = f"{label}: {tail[0][:300]}"
            if required:
                return _set_status(pdir, state="failed", error=msg, warnings=warnings, finished_at=time.time())
            warnings.append(msg)
        done_labels.append(label)
        _set_status(pdir, completed=done_labels)
    _set_status(pdir, step=len(steps), label="Drawing the strata")
    try:
        _write_json(pdir / DIG_FILE, summarize(pdir, repo=str(repo), project=project, settings=settings))
    except Exception as exc:  # noqa: BLE001 - a summary bug must not leave the job "running"
        logger.exception("ag4te: summary failed")
        return _set_status(pdir, state="failed", error=f"summary failed: {type(exc).__name__}: {exc}"[:300],
                           warnings=warnings, finished_at=time.time())
    return _set_status(pdir, state="done", step=len(steps) + 1, label="Done", warnings=warnings,
                       finished_at=time.time())


def start_dig(repo_path: Optional[str], project: Optional[str] = None, settings: Optional[Dict[str, Any]] = None,
              *, resume: bool = False, runner: Callable[..., Dict[str, Any]] = run_devarch) -> Dict[str, Any]:
    """Validate and start a background dig. One dig runs at a time.

    ``resume`` picks up a failed, interrupted or cancelled dig of ``project`` from the
    first step it had not finished, on the repo it was digging.
    """
    settings = settings if settings is not None else snapshot_settings()
    skip: List[str] = []
    if resume:
        if not project:
            raise DigError("resume needs the project name")
        project = validate_project(project)
        st = read_status(project, settings)
        if st.get("state") not in ("failed", "cancelled"):
            raise DigError(f"nothing to resume: the dig of {project} is {st.get('state') or 'none'}")
        repo_path = repo_path or st.get("repo") or (_read_json(project_dir(project, settings) / META_FILE) or {}).get("repo")
        skip = [x for x in (st.get("completed") or []) if isinstance(x, str)]
    repo = resolve_repo(repo_path, settings)
    project = validate_project(project or project_from_repo(repo))
    with _jobs_lock:
        busy = [p for p, t in _jobs.items() if t.is_alive()]
        if busy:
            raise DigError(f"a dig is already running ({busy[0]}); one at a time keeps the host light")
        cancel = threading.Event()

        def job() -> None:
            try:
                run_dig(repo, project, settings, runner=runner, cancel=cancel, skip=skip)
            except Exception as exc:  # noqa: BLE001
                logger.exception("ag4te: dig crashed")
                try:
                    _set_status(project_dir(project, settings), state="failed", error=f"{type(exc).__name__}: {exc}"[:300],
                                finished_at=time.time())
                except Exception:  # noqa: BLE001
                    pass

        t = threading.Thread(target=job, name=f"ag4te-dig-{project}", daemon=True)
        _jobs[project] = t
        _cancels[project] = cancel
        # Mark running before the thread starts so a poll right after sees it.
        _set_status(project_dir(project, settings), fresh=True, state="running", repo=str(repo), step=0,
                    label="Resuming" if skip else "Starting", started_at=time.time(), error=None, warnings=[],
                    completed=skip, resumed=bool(skip))
        t.start()
    return {"project": project, "repo": str(repo), "state": "running", "resumed": bool(skip)}


def cancel_dig(project: str, settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Ask a running dig to stop. The job writes ``cancelled`` once the command dies."""
    project = validate_project(project)
    with _jobs_lock:
        t, ev = _jobs.get(project), _cancels.get(project)
        if not (t and t.is_alive() and ev):
            raise DigError(f"no dig of {project} is running")
        ev.set()
    try:
        _set_status(project_dir(project, settings), cancelling=True, label="Stopping")
    except DigError:
        pass
    return {"project": project, "state": "running", "cancelling": True}


def list_projects(settings: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    root = workspace(settings) / "projects"
    out = []
    try:
        dirs = sorted(p for p in root.iterdir() if p.is_dir() and _PROJECT_RE.match(p.name))
    except OSError:
        return []
    for p in dirs:
        if not ((p / DIG_FILE).exists() or (p / STATUS_FILE).exists()):
            continue
        st = read_status(p.name, settings)
        meta = _read_json(p / META_FILE) or {}
        head = {}
        dig = p / DIG_FILE
        if dig.exists():
            d = _read_json(dig) or {}
            head = {k: d.get(k) for k in ("commit_count", "first", "last", "active_days")}
        out.append({"project": p.name, "repo": meta.get("repo") if isinstance(meta, dict) else None,
                    "state": st.get("state"), "has_dig": dig.exists(), **head,
                    # enough for the page to offer Resume after a reload
                    **({"error": st.get("error"), "interrupted": bool(st.get("interrupted")),
                        "completed": st.get("completed") or []}
                       if st.get("state") in ("failed", "cancelled") else {})})
    return out


def load_dig(project: str, settings: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    d = _read_json(project_dir(project, settings) / DIG_FILE)
    return d if isinstance(d, dict) else None


# --------------------------------------------------------------------------- text summary


def brief(d: Dict[str, Any]) -> str:
    if not d or d.get("empty"):
        return "No commits found in that dig."
    tot = dict(zip(d["kinds"], d.get("kind_totals") or []))
    top = ", ".join(f"{k} {n}" for k, n in sorted(tot.items(), key=lambda kv: -kv[1]) if n)[:200]
    lines = [
        f"{d['project']}: {d['commit_count']} commits from {d['first']} to {d['last']} "
        f"({d['active_days']} active of {d['span_days']} days)"
        + (f", plus {d['merge_count']} merges" if d.get("merge_count") else "") + ".",
        f"Work: {top}.",
        f"Longest streak {d['longest_streak']} days; longest quiet gap {d['longest_gap']} days; "
        f"busiest day {d['busiest_day']['d']} with {d['busiest_day']['n']} commits.",
        f"Eras: {len(d.get('clusters') or [])}; signals: {len(d.get('signals') or [])}.",
    ]
    ppl = d.get("people") or {}
    if ppl:
        lines.append(f"People: {ppl.get('human', 0)} human, {ppl.get('agent', 0)} agent, {ppl.get('bot', 0)} bot; "
                     f"{d.get('agent_assisted', 0)} commits agent-assisted; {d.get('pr_count', 0)} PRs; "
                     f"{len(d.get('releases') or [])} releases.")
    weak = [g for g in d.get("sdlc") or [] if g.get("status") not in ("PRESENT", "")]
    if weak:
        lines.append("Practices to grow: " + "; ".join(f"{g['practice']} ({g['status'].lower()}, {g.get('n', 0)} of {g.get('of', 0)})" for g in weak[:4]) + ".")
    return "\n".join(lines)


# --------------------------------------------------------------------------- slash + tool

_LOCAL_PLATFORMS = frozenset({"", "cli", "local", "tui", "desktop", "acp"})


def _session_platform() -> str:
    try:
        from gateway.session_context import get_session_env  # type: ignore
        plat = get_session_env("HERMES_SESSION_PLATFORM", "") or ""
    except Exception:  # noqa: BLE001
        plat = os.environ.get("HERMES_SESSION_PLATFORM") or ""
    return str(os.environ.get("HERMES_PLATFORM") or plat or "").strip().lower()


USAGE = ("Usage: /ag4te list | show <project> | status <project> | dig <repo-path> [project] | stop <project> | resume <project>\n"
         "A dig mines a local repo's history; open AG4TE in Hermes Desktop to see its strata.")


def _slash(raw_args: str) -> str:
    try:
        args = shlex.split(raw_args or "")
    except ValueError as exc:
        return f"Could not parse arguments: {exc}"
    if not args or args[0] in ("help", "-h", "--help"):
        return USAGE
    cmd, rest = args[0], args[1:]
    try:
        if cmd == "list":
            rows = list_projects()
            if not rows:
                return "No digs yet. Start one with /ag4te dig <repo-path>."
            return "\n".join(f"{r['project']}: {r.get('state')}" + (f", {r['commit_count']} commits" if r.get("commit_count") else "")
                             for r in rows)
        if cmd in ("show", "status") and len(rest) == 1:
            if cmd == "status":
                st = read_status(validate_project(rest[0]))
                return json.dumps({k: st.get(k) for k in ("state", "label", "step", "steps", "error", "warnings", "interrupted", "cancelling")})
            d = load_dig(validate_project(rest[0]))
            return brief(d) if d else f"No finished dig named {rest[0]}."
        if cmd == "stop" and len(rest) == 1:
            cancel_dig(rest[0])
            return f"Stopping the dig of {rest[0]}."
        if cmd == "resume" and len(rest) == 1:
            if _session_platform() not in _LOCAL_PLATFORMS and not _cfg("allow_dig_on_gateway"):
                return "/ag4te resume reads a local repository and is off on chat platforms."
            r = start_dig(None, rest[0], resume=True)
            return f"Resuming the dig of '{r['project']}'."
        if cmd == "dig" and 1 <= len(rest) <= 2:
            if _session_platform() not in _LOCAL_PLATFORMS and not _cfg("allow_dig_on_gateway"):
                return ("/ag4te dig reads a local repository and is off on chat platforms. Run it from the "
                        "Hermes CLI or Desktop, or set allow_dig_on_gateway: true.")
            r = start_dig(rest[0], rest[1] if len(rest) > 1 else None)
            return f"Digging {r['repo']} as '{r['project']}'. Check with /ag4te status {r['project']} or open AG4TE in Desktop."
    except DigError as exc:
        return str(exc)
    return USAGE


TOOL_SCHEMA = {
    "name": "ag4te_dig",
    "description": ("Read a finished AG4TE dig: a repository's commit history summarised (commits, active days, "
                    "kinds of work, eras, quiet gaps, practice health). Without a project, lists the digs. Read-only."),
    "parameters": {"type": "object", "properties": {"project": {"type": "string"}}},
}


def _tool(args: Dict[str, Any], **_: Any) -> str:
    project = (args or {}).get("project")
    try:
        if not project:
            return json.dumps({"digs": list_projects()})
        d = load_dig(validate_project(project))
    except DigError as exc:
        return json.dumps({"error": str(exc)})
    if not d:
        return json.dumps({"error": f"no finished dig named {project}"})
    keep = ("project", "commit_count", "first", "last", "span_days", "active_days", "longest_streak", "longest_gap",
            "busiest_day", "kinds", "kind_totals", "merge_count", "total_commits", "author_count", "people",
            "authors", "agent_assisted", "bot_commits", "pr_count", "gaps", "sdlc", "load", "paths", "releases",
            "manifest")
    return json.dumps({"summary": brief(d), **{k: d.get(k) for k in keep},
                       "eras": (d.get("clusters") or [])[:20], "signals": (d.get("signals") or [])[:30]})


def register(ctx) -> None:
    global _ctx
    _ctx = ctx
    ctx.register_command("ag4te", handler=_slash, description="Dig a repository's history with AG4TE.",
                         args_hint="list | show <project> | dig <repo> | stop | resume")
    ctx.register_tool(name="ag4te_dig", toolset="ag4te", schema=TOOL_SCHEMA, handler=_tool,
                      description=TOOL_SCHEMA["description"], emoji="🪨")
