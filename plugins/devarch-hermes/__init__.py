"""DevArch — native Hermes plugin (git repository archaeology).

Surfaces:
  pre_llm_call   -> when a message asks about repo history/evolution, inject an archaeology brief
  post_tool_call -> record mine/report summaries in a profile-local ledger
  /devarch       -> mine | signals | report | pipeline | list | version | status | help
  tools          -> devarch_mine / _signals / _report / _pipeline / _list / _version
  skill          -> skills/devarch/SKILL.md

Calls the DevArch Python API in-process (no CLI shell-out). Project DBs, signals,
reports and the ledger live under <HERMES_HOME>/plugin-data/devarch/ via
plugins.plugin_storage. Only public ctx.* APIs. Mining is local-only and rejects
shallow and incomplete-object (promisor) clones. Analysis vectors are investigation
leads, not verified conclusions. Process cwd / os.environ are never mutated for
workspace routing — absolute project paths only.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shlex
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

# Vendored archaeology/ lives beside this file. Prefer an already-installed
# framework package; only expose the vendor copy when nothing else provides it
# (Hermes plugin-only install). Never shadow the repo's root archaeology package.
_PLUGIN_DIR = Path(__file__).resolve().parent


def _ensure_archaeology_importable() -> None:
    vendor_root = (_PLUGIN_DIR / "archaeology").resolve()
    try:
        import archaeology as arch  # noqa: WPS433

        arch_file = Path(getattr(arch, "__file__", "") or "").resolve()
        if arch_file.parent == vendor_root:
            return
        # Framework (or another non-vendor) archaeology already wins — do not shadow.
        return
    except ImportError:
        pass
    plugin_dir = str(_PLUGIN_DIR)
    if plugin_dir not in sys.path:
        sys.path.insert(0, plugin_dir)


_ensure_archaeology_importable()

logger = logging.getLogger(__name__)

PLUGIN_NAME = "devarch"
PINNED_SHA = "b44430e198e45bfaee1edb2f3473f7d50ce17bc2"
DEFAULTS: Dict[str, Any] = {
    "inject_on_archaeology": True,
    "allow_repo_slash_on_gateway": False,
    "max_commits_warn": 5000,
    "default_project": "session",
}
LEDGER_MAX = 200
MAX_OUT = 20000
_PROJECT_RE = re.compile(r"^[a-zA-Z0-9._-]{1,100}$")
_LOCAL_SURFACES = frozenset(
    {
        "",
        "api_server",
        "cli",
        "codex",
        "desktop",
        "gateway",
        "kanban",
        "local",
        "msgraph_webhook",
        "tool",
        "tui",
        "webhook",
        "acp",
    }
)

_ARCH_RE = re.compile(
    r"\b(?:"
    r"git\s+history|commit\s+history|repo(?:sitory)?\s+history|"
    r"codebase\s+evol(?:ve|ution)|how\s+(?:this|the)\s+(?:code|repo|codebase)\s+evolved|"
    r"archaeolog|devarch|era(?:s)?\b|velocity\s+shift|author\s+change|"
    r"development\s+signals?|mine\s+(?:the\s+)?(?:repo|history|commits)"
    r")\b",
    re.IGNORECASE,
)

_ctx = None
_ledger_lock = threading.Lock()


# --- config / storage -------------------------------------------------------


def _cfg(key: str) -> Any:
    try:
        val = _ctx.get_config(key, None) if _ctx is not None else None
    except Exception:
        val = None
    return DEFAULTS[key] if val is None else val


def _data_dir() -> Path:
    try:
        from plugins.plugin_storage import plugin_data_dir

        return plugin_data_dir(PLUGIN_NAME)
    except Exception:
        home = os.environ.get("HERMES_HOME") or str(Path.home() / ".hermes")
        p = Path(home) / "plugin-data" / PLUGIN_NAME
        p.mkdir(parents=True, exist_ok=True)
        return p


def _workspace() -> Path:
    """DevArch project root — always under plugin-data (never the target repo)."""
    ws = _data_dir() / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "projects").mkdir(parents=True, exist_ok=True)
    return ws


def _ledger_path() -> Path:
    return _data_dir() / "report_ledger.json"


def _load_json(path: Path, default: Any) -> Any:
    try:
        if path.is_file():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        logger.debug("devarch: failed reading %s", path, exc_info=True)
    return default


def _save_json(path: Path, payload: Any) -> None:
    """Atomic write with a unique temp name (safe under concurrent callers)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _on_gateway() -> bool:
    """True when the active Hermes session is a messaging/gateway surface.

    Hermes >=0.21.6 stores session platform in task-local ContextVars, not only
    os.environ. Prefer gateway.session_context helpers; fall back to env.
    """
    try:
        from gateway.session_context import get_session_env, session_is_messaging_surface

        if session_is_messaging_surface():
            return True
        plat = (
            (
                os.environ.get("HERMES_PLATFORM")
                or get_session_env("HERMES_SESSION_PLATFORM", "")
                or get_session_env("HERMES_SESSION_SOURCE", "")
                or ""
            )
            .strip()
            .lower()
        )
    except Exception:
        plat = (
            (os.environ.get("HERMES_PLATFORM") or os.environ.get("HERMES_SESSION_PLATFORM") or "")
            .strip()
            .lower()
        )
    return bool(plat) and plat not in _LOCAL_SURFACES


# --- helpers ----------------------------------------------------------------


def _project_name(raw: Optional[str]) -> str:
    name = str(raw if raw not in (None, "") else _cfg("default_project")).strip() or "session"
    if not _PROJECT_RE.match(name) or ".." in name:
        raise ValueError(
            f"invalid project name {name!r}: use 1-100 chars of [A-Za-z0-9._-], no '..'"
        )
    return name


def _project_dir(project: str) -> Path:
    """Resolve <workspace>/projects/<project> with traversal checks."""
    projects = _workspace() / "projects"
    projects.mkdir(parents=True, exist_ok=True)
    candidate = (projects / project).resolve()
    try:
        candidate.relative_to(projects.resolve())
    except ValueError as exc:
        raise ValueError(f"project path escape detected: {project!r}") from exc
    return candidate


def _resolve_repo(repo_path: str) -> Path:
    raw = str(repo_path or "").strip()
    if not raw:
        raise ValueError("repo_path is required")
    p = Path(raw).expanduser()
    p = (Path.cwd() / p).resolve() if not p.is_absolute() else p.resolve()
    if not p.exists() or not p.is_dir():
        raise ValueError(f"repository path does not exist: {p}")
    git_meta = p / ".git"
    if not git_meta.exists() and not (p / "HEAD").exists():
        raise ValueError(f"not a git repository: {p}")
    return p


def _coverage(repo: Path) -> Dict[str, Any]:
    from archaeology.extractors.git import repository_coverage

    return repository_coverage(str(repo))


def _reject_shallow(cov: Dict[str, Any]) -> Optional[str]:
    if cov.get("shallow"):
        return (
            "Refusing to mine a shallow clone (evidence integrity 0.4.x). "
            "Run `git fetch --unshallow` (or clone with full history) and retry."
        )
    return None


def _incomplete_object_reason(repo_path: str) -> Optional[str]:
    """Refuse promisor/partial clones that would lazy-fetch missing blobs.

    Implemented in the plugin so framework archaeology need not be shadowed just
    to pick up the vendor-only helper during the monorepo test suite.
    """
    try:
        from archaeology.extractors.git import incomplete_object_reason as vendor_fn

        return vendor_fn(repo_path)
    except ImportError:
        pass

    repo = Path(repo_path).expanduser()
    try:
        raw = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            env={**os.environ, "GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0"},
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if raw.returncode != 0:
        return None
    git_dir = Path(raw.stdout.strip())
    if not git_dir.is_absolute():
        git_dir = (repo / git_dir).resolve()
    pack = git_dir / "objects" / "pack"
    if pack.is_dir() and list(pack.glob("*.promisor")):
        return (
            "Refusing incomplete-object / partial (promisor) clone — mining is local-only "
            "and must not fetch missing blobs. Re-clone with full objects and retry."
        )
    env = {**os.environ, "GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0"}

    def _cfg(*args: str) -> str:
        r = subprocess.run(
            ["git", "-C", str(repo), "config", *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
            env=env,
        )
        return r.stdout if r.returncode == 0 else ""

    filt = _cfg("--get", "remote.origin.partialclonefilter").strip()
    promisor_cfg = _cfg("--get-regexp", r"\.promisor$").strip()
    if filt or promisor_cfg:
        return (
            "Refusing partial clone (promisor/filter configured) — mining is local-only "
            "and must not fetch missing blobs. Re-clone without `--filter`/`--partial` and retry."
        )
    return None


def _reject_incomplete(repo: Path) -> Optional[str]:
    """Refuse promisor/partial clones that would lazy-fetch missing blobs."""
    return _incomplete_object_reason(str(repo))


def version() -> Dict[str, Any]:
    try:
        from archaeology import __version__ as ver
    except Exception as exc:
        return {
            "ok": False,
            "error": (
                f"devarch-framework not importable ({type(exc).__name__}: {exc}). "
                "Run `hermes plugins install …` / `hermes plugins validate --install-deps`."
            ),
        }
    return {
        "ok": True,
        "version": ver,
        "pinned_sha": PINNED_SHA,
        "workspace": str(_workspace()),
        "integrity": (
            "rejects shallow + incomplete/promisor objects; "
            "vectors are leads not conclusions; absolute project paths (no cwd mutation)"
        ),
    }


def list_projects() -> Dict[str, Any]:
    projects_dir = _workspace() / "projects"
    projects: List[Dict[str, Any]] = []
    if projects_dir.exists():
        for project_dir in sorted(projects_dir.iterdir()):
            if not project_dir.is_dir() or project_dir.name.startswith((".", "_")):
                continue
            config = _load_json(project_dir / "project.json", {}) or {}
            projects.append(
                {
                    "name": project_dir.name,
                    "path": str(project_dir),
                    "has_data": (project_dir / "data").exists(),
                    "has_deliverables": (project_dir / "deliverables").exists(),
                    "has_database": (project_dir / "data" / "archaeology.db").exists(),
                    "description": config.get("description", ""),
                    "repo_url": config.get("repo_url", ""),
                }
            )
    return {
        "ok": True,
        "projects": projects,
        "count": len(projects),
        "workspace": str(_workspace()),
    }


def _init_project(project: str, description: str = "", repo_url: str = "") -> Dict[str, Any]:
    project_dir = _project_dir(project)
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "data").mkdir(exist_ok=True)
    (project_dir / "deliverables").mkdir(exist_ok=True)
    config_path = project_dir / "project.json"
    if config_path.exists():
        return {"status": "exists", "project": project, "path": str(project_dir)}
    config = {
        "name": project,
        "description": description,
        "repo_url": repo_url,
        "developer": {},
        "timeline": {},
        "overrides": {},
        "visualization": {},
        "data_sources": {},
    }
    _save_json(config_path, config)
    return {"status": "created", "project": project, "path": str(project_dir)}


_DERIVED_REL_PATHS = (
    "data/archaeology.db",
    "data/detected-signals.json",
    "data/gap-clusters.json",
    "deliverables/canonical-metrics.json",
    "deliverables/data.json",
)


def _invalidate_derived_artifacts(project_dir: Path) -> None:
    """Drop derived evidence so a failed remine cannot export a mixed generation.

    Preserves human-authored commit-eras.json. Generated clusters live in gap-clusters.json.
    """
    for rel in _DERIVED_REL_PATHS:
        path = project_dir / rel
        if path.is_file():
            path.unlink()
        side = Path(str(path) + ".provenance.json")
        if side.is_file():
            side.unlink()
    for pattern in (
        "deliverables/analysis-*.json",
        "deliverables/analysis/analysis-*.json",
        "deliverables/analysis-*.json.provenance.json",
        "deliverables/analysis/*.provenance.json",
        "deliverables/reports/*",
        "deliverables/visuals/*",
    ):
        for path in project_dir.glob(pattern):
            if path.is_file():
                path.unlink()


def _bind_mining_manifest(
    project_dir: Path,
    repo: Path,
    cov: Dict[str, Any],
    csv_path: Path,
    stats_path: Path,
    *,
    generation: str,
    status: str = "incomplete",
    derived_sha256: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Mirror the canonical CLI: coverage.json + mined_history_manifest_required + hashes."""
    from archaeology.extractors.git import repository_coverage

    post = repository_coverage(str(repo))

    # Compare identity fields; ignore any future artifact_sha256 on either side.
    def _identity(c: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "head": c.get("head"),
            "scope": c.get("scope"),
            "shallow": c.get("shallow"),
            "bare": c.get("bare"),
            "commit_count": c.get("commit_count"),
            "refs": c.get("refs"),
            "roots": c.get("roots"),
        }

    if _identity(post) != _identity(cov):
        raise RuntimeError("Repository refs changed during mining; retry before analysis")

    coverage = dict(cov)
    coverage["artifact_sha256"] = {
        csv_path.name: hashlib.sha256(csv_path.read_bytes()).hexdigest(),
        stats_path.name: hashlib.sha256(stats_path.read_bytes()).hexdigest(),
    }
    coverage["mining_generation"] = generation
    coverage["mining_status"] = status
    if derived_sha256 is not None:
        coverage["derived_sha256"] = derived_sha256
    elif "derived_sha256" in coverage:
        # Incomplete rebuild must not keep prior derived bindings.
        coverage.pop("derived_sha256", None)
    _save_json(project_dir / "data" / "coverage.json", coverage)

    config_path = project_dir / "project.json"
    config = _load_json(config_path, {}) or {}
    config["repo_path"] = str(repo)
    config["mined_history_manifest_required"] = True
    _save_json(config_path, config)
    return coverage


def mine(repo_path: str, project: Optional[str] = None) -> Dict[str, Any]:
    """Mine local git history into a DevArch project under plugin-data."""
    proj = _project_name(project)
    repo = _resolve_repo(repo_path)
    cov = _coverage(repo)
    shallow_err = _reject_shallow(cov)
    if shallow_err:
        return {"ok": False, "error": shallow_err, "coverage": cov}
    incomplete_err = _reject_incomplete(repo)
    if incomplete_err:
        return {"ok": False, "error": incomplete_err, "coverage": cov}

    warn = None
    count = int(cov.get("commit_count") or 0)
    threshold = int(_cfg("max_commits_warn") or 0)
    if threshold and count > threshold:
        warn = (
            f"Local commit count {count} exceeds max_commits_warn={threshold}; "
            "mining still runs — expect longer wall-clock."
        )

    _init_project(proj, description=f"Hermes archaeology of {repo}", repo_url=str(repo))

    from archaeology.db.builder import build_db
    from archaeology.extractors.git import extract_git_log, extract_git_log_with_stats

    project_dir = _project_dir(proj)
    data_dir = project_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    csv_path = data_dir / "github-commits.csv"
    stats_path = data_dir / "github-commits-with-stats.txt"
    generation = uuid.uuid4().hex
    # Invalidate before writing a new coverage manifest so a failed remine cannot
    # leave old DB/metrics/signals paired with new raw hashes.
    _invalidate_derived_artifacts(project_dir)
    try:
        extracted = extract_git_log(str(repo), str(csv_path))
        extract_git_log_with_stats(str(repo), str(stats_path))
        coverage = _bind_mining_manifest(
            project_dir,
            repo,
            cov,
            csv_path,
            stats_path,
            generation=generation,
            status="incomplete",
        )
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "coverage": cov}

    try:
        # Quiet via verbose=False only — never mutate process-wide stdout/stderr.
        build_db(project_root=project_dir, verbose=False)
        db_path = project_dir / "data" / "archaeology.db"
        if not db_path.exists():
            return {
                "ok": False,
                "error": "Database build produced no archaeology.db",
                "status": "failed",
                "project": proj,
                "coverage": {
                    "commit_count": coverage.get("commit_count"),
                    "shallow": coverage.get("shallow"),
                    "head": coverage.get("head"),
                    "mining_status": "incomplete",
                    "mining_generation": generation,
                },
                "commits_extracted": extracted,
            }
        derived = {
            "archaeology.db": hashlib.sha256(db_path.read_bytes()).hexdigest(),
        }
        coverage = _bind_mining_manifest(
            project_dir,
            repo,
            cov,
            csv_path,
            stats_path,
            generation=generation,
            status="complete",
            derived_sha256=derived,
        )
        db_status = "complete"
    except Exception as exc:
        return {
            "ok": False,
            "error": f"database build failed: {type(exc).__name__}: {exc}",
            "status": "failed",
            "project": proj,
            "failed_at": "build_db",
            "commits_extracted": extracted,
            "coverage": {
                "commit_count": coverage.get("commit_count"),
                "shallow": coverage.get("shallow"),
                "head": coverage.get("head"),
                "mining_status": "incomplete",
                "mining_generation": generation,
            },
            "database": f"failed: {type(exc).__name__}: {exc}",
        }

    res: Dict[str, Any] = {
        "ok": True,
        "status": "complete",
        "project": proj,
        "repo": str(repo),
        "commits_extracted": extracted,
        "coverage": {
            "commit_count": coverage.get("commit_count"),
            "shallow": coverage.get("shallow"),
            "scope": coverage.get("scope"),
            "head": coverage.get("head"),
            "mining_generation": generation,
            "mining_status": "complete",
        },
        "database": db_status,
        "evidence_binding": True,
        "workspace": str(_workspace()),
    }
    if warn:
        res["warning"] = warn
    return res


def _write_gap_clusters(project_dir: Path, project: str, detection: Dict[str, Any]) -> None:
    """Persist gap-based clusters to gap-clusters.json — never overwrite curated eras.

    Signal detection does not invent narrative eras. Clusters are gap-separated
    commit groupings stored separately from human-authored commit-eras.json.
    """
    clusters = detection.get("cluster_summary") or []
    signals = detection.get("signals") or []
    total = sum(int(c.get("commit_count") or 0) for c in clusters) if clusters else 0
    eras = []
    for idx, cluster in enumerate(clusters, start=1):
        start = cluster.get("start_date") or "?"
        end = cluster.get("end_date") or start
        dates = start if start == end else f"{start} to {end}"
        eras.append(
            {
                "id": idx,
                "name": f"Cluster {idx}",
                "dates": dates,
                "commits": cluster.get("commit_count"),
                "description": (
                    f"Gap-separated activity cluster ({cluster.get('active_days', '?')} active days; "
                    f"primary author={cluster.get('primary_author') or 'unknown'})."
                ),
                "narrative_arc": (
                    "Automated cluster from commit-date gaps — not a curated human era narrative."
                ),
                "kind": "gap_cluster",
            }
        )
    coverage = _load_json(project_dir / "data" / "coverage.json", {}) or {}
    generation = coverage.get("mining_generation")
    payload = {
        "project": project,
        "total_commits": total,
        "eras": eras,
        "era_semantics": (
            "gap_clusters: clusters are heuristic groupings separated by multi-day gaps. "
            "They are not curated development eras. Curated eras require human narrative judgment "
            "and live in commit-eras.json (never overwritten by signals)."
        ),
        "signal_count": len(signals),
        "cluster_count": len(clusters),
        "mining_generation": generation,
    }
    _save_json(project_dir / "data" / "gap-clusters.json", payload)


def signals(project: Optional[str] = None, min_gap_days: Optional[int] = None) -> Dict[str, Any]:
    proj = _project_name(project)
    from archaeology.classifiers.era_detector import SignalDetector

    project_dir = _project_dir(proj)
    db_path = project_dir / "data" / "archaeology.db"
    if not db_path.exists():
        return {"ok": False, "error": "Database not found. Run devarch_mine first."}
    config: Dict[str, Any] = {}
    if min_gap_days is not None:
        config["min_gap_days"] = int(min_gap_days)
    try:
        detector = SignalDetector(db_path, config=config or None)
        out = detector.detect()
        out_path = project_dir / "data" / "detected-signals.json"
        detector.save(out_path, out)
        if isinstance(out, dict):
            coverage = _load_json(project_dir / "data" / "coverage.json", {}) or {}
            generation = coverage.get("mining_generation")
            if generation and "mining_generation" not in out:
                out = dict(out)
                out["mining_generation"] = generation
                _save_json(out_path, out)
        _write_gap_clusters(project_dir, proj, out if isinstance(out, dict) else {})
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    signal_list = out.get("signals", []) if isinstance(out, dict) else (out or [])
    clusters = out.get("cluster_summary", []) if isinstance(out, dict) else []
    summary = []
    for s in list(signal_list)[:25]:
        if isinstance(s, dict):
            summary.append(
                {
                    "type": s.get("type") or s.get("kind") or s.get("signal"),
                    "date": s.get("date") or s.get("when"),
                    "detail": str(s.get("description") or s.get("detail") or s.get("message") or s)[
                        :240
                    ],
                }
            )
        else:
            summary.append({"detail": str(s)[:240]})
    cluster_summary = []
    for c in list(clusters)[:25]:
        if isinstance(c, dict):
            cluster_summary.append(
                {
                    "start_date": c.get("start_date"),
                    "end_date": c.get("end_date"),
                    "commit_count": c.get("commit_count"),
                    "active_days": c.get("active_days"),
                }
            )
    return {
        "ok": True,
        "status": "complete",
        "project": proj,
        "signal_count": len(signal_list),
        "cluster_count": len(clusters),
        "signals": summary,
        "clusters": cluster_summary,
        "era_semantics": (
            "Automated output is signals + gap-separated clusters. "
            "Clusters are not curated human eras."
        ),
        "note": "Signals are heuristic investigation leads, not verified conclusions.",
        "output_path": str(project_dir / "data" / "detected-signals.json"),
    }


def report(project: Optional[str] = None, fmt: str = "markdown") -> Dict[str, Any]:
    """Export a markdown (default) or html report; return a truncated body for the session."""
    proj = _project_name(project)
    fmt = (fmt or "markdown").lower().strip()
    if fmt not in {"markdown", "html", "md"}:
        return {"ok": False, "error": "fmt must be markdown or html"}
    if fmt == "md":
        fmt = "markdown"

    from archaeology.report import _markdown_to_html, export_markdown_report

    project_dir = _project_dir(proj)
    if not project_dir.exists():
        return {"ok": False, "error": f"Project '{proj}' not found. Run devarch_mine first."}
    try:
        md_path = export_markdown_report(proj, str(project_dir))
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    md_text = Path(md_path).read_text(encoding="utf-8") if Path(md_path).is_file() else ""
    output_path = str(md_path)
    if fmt == "html":
        title = proj
        config = _load_json(project_dir / "project.json", {}) or {}
        title = (config.get("visualization") or {}).get("title", proj)
        html = _markdown_to_html(md_text, title)
        out_dir = project_dir / "deliverables" / "visuals"
        out_dir.mkdir(parents=True, exist_ok=True)
        html_path = out_dir / "report.html"
        html_path.write_text(html, encoding="utf-8")
        output_path = str(html_path)

    return {
        "ok": True,
        "status": "complete",
        "project": proj,
        "format": fmt,
        "output_path": output_path,
        "markdown": md_text[:12000],
        "truncated": len(md_text) > 12000,
        "note": (
            "Vectors/signals in this report are investigation leads based on keyword "
            "heuristics — not verified source conclusions or productivity measurements. "
            "Gap clusters are not curated eras."
        ),
    }


def _classify_analysis(result: Any) -> Dict[str, Any]:
    """Separate successful vector paths from ERROR: values."""
    if not isinstance(result, dict):
        return {
            "ok": False,
            "vectors_run": [],
            "vector_errors": {"_": f"unexpected analysis result type: {type(result).__name__}"},
            "note": "Keyword-based leads, not verified conclusions.",
        }
    errors: Dict[str, str] = {}
    ok_vecs: List[str] = []
    for name, value in result.items():
        if isinstance(value, str) and value.startswith("ERROR:"):
            errors[name] = value
        else:
            ok_vecs.append(name)
    if errors and not ok_vecs:
        status_ok = False
        partial = False
    elif errors and ok_vecs:
        status_ok = False
        partial = True
    else:
        status_ok = True
        partial = False
    return {
        "ok": status_ok,
        "partial": partial,
        "vectors_run": ok_vecs,
        "vector_errors": errors,
        "note": "Keyword-based leads, not verified conclusions.",
    }


def pipeline(repo_path: str, project: Optional[str] = None) -> Dict[str, Any]:
    """mine → signals → markdown report (analyze vectors optional / best-effort)."""
    proj = _project_name(project)
    mined = mine(repo_path, proj)
    if not mined.get("ok"):
        return {"ok": False, "status": "failed", "failed_at": "mine", **mined}
    sig = signals(proj)
    if not sig.get("ok"):
        return {"ok": False, "status": "failed", "failed_at": "signals", "mine": mined, **sig}

    analysis: Dict[str, Any]
    try:
        from archaeology.analysis_runner import AnalysisRunner

        project_dir = _project_dir(proj)
        runner = AnalysisRunner(proj, str(project_dir), verbose=False)
        result = runner.run_all(vectors=None)
        analysis = _classify_analysis(result)
    except Exception as exc:
        analysis = {
            "ok": False,
            "partial": False,
            "error": f"{type(exc).__name__}: {exc}",
            "vectors_run": [],
            "vector_errors": {},
        }

    rep = report(proj, fmt="markdown")
    stages_ok = bool(rep.get("ok"))
    # Pipeline is complete only when mine+signals+report succeed; analysis may be partial.
    if not stages_ok:
        status = "failed"
        ok = False
        failed_at = "report"
    elif analysis.get("ok"):
        status = "complete"
        ok = True
        failed_at = None
    elif analysis.get("partial"):
        status = "partial"
        ok = True
        failed_at = None
    else:
        status = "partial"
        ok = True  # mine+signals+report succeeded; analysis best-effort failed
        failed_at = None

    out: Dict[str, Any] = {
        "ok": ok,
        "status": status,
        "project": proj,
        "mine": {
            "commits_extracted": mined.get("commits_extracted"),
            "coverage": mined.get("coverage"),
            "warning": mined.get("warning"),
            "evidence_binding": mined.get("evidence_binding"),
        },
        "signals": {
            "signal_count": sig.get("signal_count"),
            "cluster_count": sig.get("cluster_count"),
            "signals": sig.get("signals"),
            "clusters": sig.get("clusters"),
            "era_semantics": sig.get("era_semantics"),
        },
        "analysis": analysis,
        "report": {
            "output_path": rep.get("output_path"),
            "markdown": rep.get("markdown"),
            "truncated": rep.get("truncated"),
            "note": rep.get("note"),
            "ok": rep.get("ok"),
            "error": rep.get("error"),
        },
    }
    if failed_at:
        out["failed_at"] = failed_at
    if not rep.get("ok"):
        out["error"] = rep.get("error")
    return out


# --- hooks ------------------------------------------------------------------

_BRIEF = (
    "[DevArch archaeology] This message asks about repository history or how the codebase "
    "evolved. Before guessing from a few recent commits: (1) call `devarch_pipeline` (or "
    "`devarch_mine` → `devarch_signals` → `devarch_report`) on the local git checkout, "
    "(2) lead with measured signals and gap-separated clusters from the report (clusters are "
    "not curated human eras), (3) label every automated vector as an investigation lead — "
    "not a verified conclusion or productivity measurement, "
    "(4) refuse shallow / incomplete-object clones (integrity rule). "
    "Data stays under plugin-data/devarch/."
)


def _on_pre_llm(user_message: str = "", **_: Any) -> Optional[Dict[str, str]]:
    try:
        if _cfg("inject_on_archaeology") and user_message and _ARCH_RE.search(user_message):
            return {"context": _BRIEF}
    except Exception:
        logger.debug("devarch: pre_llm_call failed", exc_info=True)
    return None


def _append_ledger(entry: Dict[str, Any]) -> None:
    with _ledger_lock:
        ledger = _load_json(_ledger_path(), [])
        if not isinstance(ledger, list):
            ledger = []
        ledger.append(entry)
        _save_json(_ledger_path(), ledger[-LEDGER_MAX:])


def _on_post_tool(
    tool_name: str = "", args: Optional[Dict[str, Any]] = None, result: Any = None, **_: Any
) -> None:
    try:
        if tool_name not in {
            "devarch_mine",
            "devarch_signals",
            "devarch_report",
            "devarch_pipeline",
        }:
            return None
        payload = result
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = {}
        if not isinstance(payload, dict):
            return None
        entry = {
            "ts": int(time.time()),
            "tool": tool_name,
            "project": str((args or {}).get("project") or payload.get("project") or "")[:80],
            "repo": str((args or {}).get("repo_path") or "")[:300],
            "ok": bool(payload.get("ok")),
            "commits": payload.get("commits_extracted")
            or (payload.get("mine") or {}).get("commits_extracted"),
            "signals": payload.get("signal_count")
            or (payload.get("signals") or {}).get("signal_count"),
            "output_path": payload.get("output_path")
            or (payload.get("report") or {}).get("output_path"),
        }
        _append_ledger(entry)
    except Exception:
        logger.debug("devarch: post_tool_call failed", exc_info=True)
    return None


# --- tools ------------------------------------------------------------------

MINE_SCHEMA = {
    "name": "devarch_mine",
    "description": (
        "Mine a local git repository's full commit history into a DevArch project under "
        "plugin-data. Rejects shallow and incomplete/promisor clones. Returns commit count + "
        "coverage. Local-only (no network fetch; GIT_NO_LAZY_FETCH)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "repo_path": {"type": "string", "description": "Path to a local git checkout"},
            "project": {"type": "string", "description": "DevArch project name (default: session)"},
        },
        "required": ["repo_path"],
    },
}
SIGNALS_SCHEMA = {
    "name": "devarch_signals",
    "description": (
        "Detect development signals (gaps, velocity shifts, author changes) for a mined "
        "DevArch project. Heuristic leads — not verified conclusions. Also records "
        "gap-separated clusters (not curated eras)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "project": {"type": "string"},
            "min_gap_days": {"type": "integer"},
        },
    },
}
REPORT_SCHEMA = {
    "name": "devarch_report",
    "description": (
        "Export an eras/signals engineering report (markdown by default) for a mined "
        "project and return a truncated body for the session. Includes measured signals "
        "and gap clusters; states era semantics honestly."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "project": {"type": "string"},
            "fmt": {"type": "string", "enum": ["markdown", "html"], "default": "markdown"},
        },
    },
}
PIPELINE_SCHEMA = {
    "name": "devarch_pipeline",
    "description": (
        "One-shot archaeology: mine → signals → (best-effort) analysis vectors → markdown "
        "report. Prefer this when the user asks how a local repo evolved. Failed stages "
        "are reported accurately (ok/status/failed_at)."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "repo_path": {"type": "string"},
            "project": {"type": "string"},
        },
        "required": ["repo_path"],
    },
}
LIST_SCHEMA = {
    "name": "devarch_list",
    "description": "List DevArch projects under the plugin-data workspace.",
    "parameters": {"type": "object", "properties": {}},
}
VERSION_SCHEMA = {
    "name": "devarch_version",
    "description": "Report the DevArch framework version this plugin imported.",
    "parameters": {"type": "object", "properties": {}},
}


def _dumps_capped(payload: Any, max_out: int = MAX_OUT) -> str:
    """Serialize to JSON, bounding bulky fields so the envelope stays valid JSON."""
    text = json.dumps(payload, ensure_ascii=False)
    if len(text) <= max_out:
        return text
    if not isinstance(payload, dict):
        minimal = {
            "ok": False,
            "truncated": True,
            "error": "output exceeded cap",
            "truncation": {"limit": max_out, "original_chars": len(text)},
        }
        return json.dumps(minimal, ensure_ascii=False)

    bounded: Dict[str, Any] = dict(payload)
    original_chars = len(text)

    def _fits(obj: Dict[str, Any]) -> bool:
        return len(json.dumps(obj, ensure_ascii=False)) <= max_out

    # Prefer trimming list/string fields that blow the budget.
    for key in ("projects", "signals", "clusters", "markdown"):
        value = bounded.get(key)
        if isinstance(value, list) and value:
            lo, hi = 0, len(value)
            best = 0
            while lo <= hi:
                mid = (lo + hi) // 2
                candidate = dict(bounded)
                candidate[key] = value[:mid]
                candidate["truncated"] = True
                candidate["truncation"] = {
                    "field": key,
                    "returned": mid,
                    "total": len(value),
                    "limit_chars": max_out,
                    "original_chars": original_chars,
                }
                if _fits(candidate):
                    best = mid
                    lo = mid + 1
                else:
                    hi = mid - 1
            bounded[key] = value[:best]
            bounded["truncated"] = True
            bounded["truncation"] = {
                "field": key,
                "returned": best,
                "total": len(value),
                "limit_chars": max_out,
                "original_chars": original_chars,
            }
            if _fits(bounded):
                return json.dumps(bounded, ensure_ascii=False)
        elif isinstance(value, str) and len(value) > 256:
            # Binary-search string length
            lo, hi = 0, len(value)
            best = 0
            while lo <= hi:
                mid = (lo + hi) // 2
                candidate = dict(bounded)
                candidate[key] = value[:mid]
                candidate["truncated"] = True
                candidate["truncation"] = {
                    "field": key,
                    "returned_chars": mid,
                    "total_chars": len(value),
                    "limit_chars": max_out,
                    "original_chars": original_chars,
                }
                if _fits(candidate):
                    best = mid
                    lo = mid + 1
                else:
                    hi = mid - 1
            bounded[key] = value[:best]
            bounded["truncated"] = True
            bounded["truncation"] = {
                "field": key,
                "returned_chars": best,
                "total_chars": len(value),
                "limit_chars": max_out,
                "original_chars": original_chars,
            }
            if _fits(bounded):
                return json.dumps(bounded, ensure_ascii=False)

    # Nested report.markdown etc.
    report_obj = bounded.get("report")
    if isinstance(report_obj, dict) and isinstance(report_obj.get("markdown"), str):
        nested = dict(report_obj)
        md = nested["markdown"]
        lo, hi = 0, len(md)
        best = 0
        while lo <= hi:
            mid = (lo + hi) // 2
            candidate_report = dict(nested)
            candidate_report["markdown"] = md[:mid]
            candidate = dict(bounded)
            candidate["report"] = candidate_report
            candidate["truncated"] = True
            candidate["truncation"] = {
                "field": "report.markdown",
                "returned_chars": mid,
                "total_chars": len(md),
                "limit_chars": max_out,
                "original_chars": original_chars,
            }
            if _fits(candidate):
                best = mid
                lo = mid + 1
            else:
                hi = mid - 1
        nested["markdown"] = md[:best]
        bounded["report"] = nested
        bounded["truncated"] = True
        bounded["truncation"] = {
            "field": "report.markdown",
            "returned_chars": best,
            "total_chars": len(md),
            "limit_chars": max_out,
            "original_chars": original_chars,
        }
        if _fits(bounded):
            return json.dumps(bounded, ensure_ascii=False)

    minimal = {
        "ok": bounded.get("ok", True),
        "truncated": True,
        "error": "output exceeded cap; narrow the query or read output_path on disk",
        "truncation": {"limit": max_out, "original_chars": original_chars},
        "project": bounded.get("project"),
        "count": bounded.get("count"),
        "workspace": bounded.get("workspace"),
        "output_path": (
            bounded.get("output_path")
            or (
                (bounded.get("report") or {}).get("output_path")
                if isinstance(bounded.get("report"), dict)
                else None
            )
        ),
    }
    return json.dumps(minimal, ensure_ascii=False)


def _wrap(fn):
    def handler(args: Optional[Dict[str, Any]] = None, **_: Any) -> str:
        try:
            return _dumps_capped(fn(args or {}))
        except ValueError as exc:
            return json.dumps({"ok": False, "error": str(exc)})
        except Exception as exc:
            logger.debug("devarch tool failed", exc_info=True)
            return json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"})

    return handler


_tool_mine = _wrap(lambda a: mine(a.get("repo_path", ""), a.get("project")))
_tool_signals = _wrap(lambda a: signals(a.get("project"), a.get("min_gap_days")))
_tool_report = _wrap(lambda a: report(a.get("project"), a.get("fmt", "markdown")))
_tool_pipeline = _wrap(lambda a: pipeline(a.get("repo_path", ""), a.get("project")))
_tool_list = _wrap(lambda a: list_projects())
_tool_version = _wrap(lambda a: version())


# --- slash ------------------------------------------------------------------

_SAFE_SLASH = {"mine", "signals", "report", "pipeline", "list", "version", "status", "help"}
_REPO_SLASH = {"mine", "pipeline", "report"}  # touch local FS / produce artifacts
_HELP = (
    "/devarch — git repository archaeology (local-only)\n"
    "  /devarch mine <repo-path> [project]     Mine full history (rejects shallow/promisor)\n"
    "  /devarch signals [project]              Detect development signals (leads)\n"
    "  /devarch report [project] [markdown|html]\n"
    "  /devarch pipeline <repo-path> [project] Mine → signals → report\n"
    "  /devarch list                           Projects under plugin-data\n"
    "  /devarch version                        Framework version + pin\n"
    "  /devarch status                         Recent ledger entries\n"
    "Vectors are investigation leads, not verified conclusions. Clusters ≠ curated eras.\n"
    "Data under plugin-data/devarch/.\n"
    "On gateway platforms, mine/pipeline/report are refused unless allow_repo_slash_on_gateway: true."
)


def _fmt(res: Dict[str, Any]) -> str:
    if res.get("error") and not res.get("ok"):
        return f"DevArch failed: {res['error']}"
    if res.get("markdown"):
        head = [
            f"DevArch report — project={res.get('project')} path={res.get('output_path')}",
            res.get("note") or "",
            "",
            str(res["markdown"])[:3500],
        ]
        return "\n".join(head)
    return json.dumps(res, indent=2, ensure_ascii=False)[:3500]


def _slash(raw_args: str) -> str:
    try:
        parts = shlex.split((raw_args or "").strip())
    except ValueError as exc:
        return f"Bad arguments: {exc}\n\n{_HELP}"
    cmd = parts[0].lower() if parts else "help"
    rest = parts[1:]
    if cmd in {"help", "-h", "--help"}:
        return _HELP
    if cmd not in _SAFE_SLASH:
        return f"Unknown or blocked subcommand `{cmd}`. Allowed: {', '.join(sorted(_SAFE_SLASH))}."
    if cmd in _REPO_SLASH and _on_gateway() and not _cfg("allow_repo_slash_on_gateway"):
        return (
            f"/devarch {cmd} is disabled on gateway platforms (local git/filesystem). "
            "Ask the agent to use the tool instead, or set allow_repo_slash_on_gateway: true."
        )
    try:
        if cmd == "status":
            return json.dumps(_load_json(_ledger_path(), [])[-10:], indent=2)
        if cmd == "version":
            return _fmt(version())
        if cmd == "list":
            return _fmt(list_projects())
        if cmd == "signals":
            return _fmt(signals(rest[0] if rest else None))
        if cmd == "report":
            proj = rest[0] if rest and rest[0] not in {"markdown", "html", "md"} else None
            fmt = "markdown"
            for tok in rest:
                if tok in {"markdown", "html", "md"}:
                    fmt = tok
            return _fmt(report(proj, fmt))
        if cmd == "mine":
            if not rest:
                return "Usage: /devarch mine <repo-path> [project]"
            res = mine(rest[0], rest[1] if len(rest) > 1 else None)
            _on_post_tool(
                "devarch_mine",
                {"repo_path": rest[0], "project": rest[1] if len(rest) > 1 else None},
                res,
            )
            return _fmt(res)
        if cmd == "pipeline":
            if not rest:
                return "Usage: /devarch pipeline <repo-path> [project]"
            res = pipeline(rest[0], rest[1] if len(rest) > 1 else None)
            _on_post_tool(
                "devarch_pipeline",
                {"repo_path": rest[0], "project": rest[1] if len(rest) > 1 else None},
                res,
            )
            return _fmt(res)
    except ValueError as exc:
        return f"{exc}\n\n{_HELP}"
    except Exception as exc:
        logger.debug("devarch slash failed", exc_info=True)
        return f"DevArch error: {type(exc).__name__}: {exc}"
    return _HELP


# --- register ---------------------------------------------------------------


def register(ctx) -> None:
    global _ctx
    _ctx = ctx
    ctx.register_hook("pre_llm_call", _on_pre_llm)
    ctx.register_hook("post_tool_call", _on_post_tool)
    ctx.register_command(
        "devarch",
        handler=_slash,
        description="DevArch git archaeology (mine/signals/report/pipeline/list/version/status).",
        args_hint="mine <repo> [project] | signals | report | pipeline <repo> | list | version | status",
    )
    for schema, handler, emoji in (
        (MINE_SCHEMA, _tool_mine, "⛏️"),
        (SIGNALS_SCHEMA, _tool_signals, "📡"),
        (REPORT_SCHEMA, _tool_report, "📜"),
        (PIPELINE_SCHEMA, _tool_pipeline, "🏺"),
        (LIST_SCHEMA, _tool_list, "📂"),
        (VERSION_SCHEMA, _tool_version, "ℹ️"),
    ):
        ctx.register_tool(
            name=schema["name"],
            toolset="devarch",
            schema=schema,
            handler=handler,
            description=schema["description"],
            emoji=emoji,
        )
    skills_dir = Path(__file__).parent / "skills"
    if skills_dir.is_dir():
        for child in sorted(skills_dir.iterdir()):
            skill_md = child / "SKILL.md"
            if child.is_dir() and skill_md.exists():
                try:
                    ctx.register_skill(child.name, skill_md)
                except Exception:
                    logger.debug("devarch: register_skill failed for %s", child.name, exc_info=True)
