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
shallow clones. Analysis vectors are investigation leads, not verified conclusions.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shlex
import sys
import time
from contextlib import contextmanager, redirect_stdout, redirect_stderr
from pathlib import Path
from typing import Any, Dict, List, Optional

# Vendored archaeology/ lives beside this file; ensure absolute imports resolve
# after Hermes installs only the plugin subdirectory.
_PLUGIN_DIR = Path(__file__).resolve().parent
if str(_PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_DIR))

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
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def _on_gateway() -> bool:
    plat = (os.environ.get("HERMES_PLATFORM") or os.environ.get("HERMES_SESSION_PLATFORM") or "").lower()
    return bool(plat) and plat not in {"cli", "tui", "desktop", "local", "acp"}


@contextmanager
def _in_workspace():
    """Point DevArch at the plugin-data workspace and chdir there for CWD-relative APIs."""
    ws = _workspace()
    saved_cwd = os.getcwd()
    saved_env = os.environ.get("DEVARCH_WORKSPACE")
    os.environ["DEVARCH_WORKSPACE"] = str(ws)
    os.chdir(str(ws))
    try:
        yield ws
    finally:
        os.chdir(saved_cwd)
        if saved_env is None:
            os.environ.pop("DEVARCH_WORKSPACE", None)
        else:
            os.environ["DEVARCH_WORKSPACE"] = saved_env


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
        "integrity": "rejects shallow; vectors are leads not conclusions",
    }


def list_projects() -> Dict[str, Any]:
    projects_dir = _workspace() / "projects"
    projects: List[Dict[str, Any]] = []
    if projects_dir.exists():
        for project_dir in sorted(projects_dir.iterdir()):
            if not project_dir.is_dir() or project_dir.name.startswith((".", "_")):
                continue
            config = _load_json(project_dir / "project.json", {}) or {}
            projects.append({
                "name": project_dir.name,
                "path": str(project_dir),
                "has_data": (project_dir / "data").exists(),
                "has_deliverables": (project_dir / "deliverables").exists(),
                "has_database": (project_dir / "data" / "archaeology.db").exists(),
                "description": config.get("description", ""),
                "repo_url": config.get("repo_url", ""),
            })
    return {"ok": True, "projects": projects, "workspace": str(_workspace())}


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
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return {"status": "created", "project": project, "path": str(project_dir)}


def mine(repo_path: str, project: Optional[str] = None) -> Dict[str, Any]:
    """Mine local git history into a DevArch project under plugin-data."""
    proj = _project_name(project)
    repo = _resolve_repo(repo_path)
    cov = _coverage(repo)
    shallow_err = _reject_shallow(cov)
    if shallow_err:
        return {"ok": False, "error": shallow_err, "coverage": cov}

    warn = None
    count = int(cov.get("commit_count") or 0)
    threshold = int(_cfg("max_commits_warn") or 0)
    if threshold and count > threshold:
        warn = (
            f"Local commit count {count} exceeds max_commits_warn={threshold}; "
            "mining still runs — expect longer wall-clock."
        )

    _init_project(proj, description=f"Hermes archaeology of {repo}", repo_url=str(repo))

    with _in_workspace():
        from archaeology.extractors.git import extract_git_log, extract_git_log_with_stats

        project_dir = _project_dir(proj)
        data_dir = project_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        csv_path = str(data_dir / "github-commits.csv")
        stats_path = str(data_dir / "github-commits-with-stats.txt")
        try:
            extracted = extract_git_log(str(repo), csv_path)
            extract_git_log_with_stats(str(repo), stats_path)
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}", "coverage": cov}

        # Bind coverage next to the extraction for integrity.
        _save_json(data_dir / "repository-coverage.json", cov)

        # Build SQLite so signals/report can run next.
        try:
            from archaeology.db.builder import build_db
            import io

            sink = io.StringIO()
            with redirect_stdout(sink), redirect_stderr(sink):
                build_db(project_root=project_dir, verbose=False)
            db_status = "complete" if (project_dir / "data" / "archaeology.db").exists() else "missing"
        except Exception as exc:
            db_status = f"failed: {type(exc).__name__}: {exc}"

    res: Dict[str, Any] = {
        "ok": True,
        "status": "complete",
        "project": proj,
        "repo": str(repo),
        "commits_extracted": extracted,
        "coverage": {
            "commit_count": cov.get("commit_count"),
            "shallow": cov.get("shallow"),
            "scope": cov.get("scope"),
            "head": cov.get("head"),
        },
        "database": db_status,
        "workspace": str(_workspace()),
    }
    if warn:
        res["warning"] = warn
    return res


def signals(project: Optional[str] = None, min_gap_days: Optional[int] = None) -> Dict[str, Any]:
    proj = _project_name(project)
    with _in_workspace():
        from archaeology.classifiers.era_detector import detect_signals

        project_dir = _project_dir(proj)
        db_path = project_dir / "data" / "archaeology.db"
        if not db_path.exists():
            return {"ok": False, "error": "Database not found. Run devarch_mine first."}
        config: Dict[str, Any] = {}
        if min_gap_days is not None:
            config["min_gap_days"] = int(min_gap_days)
        try:
            out = detect_signals(proj, config=config or None)
        except Exception as exc:
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    signal_list = out.get("signals", []) if isinstance(out, dict) else (out or [])
    # Keep the payload small for the agent — summarize.
    summary = []
    for s in list(signal_list)[:25]:
        if isinstance(s, dict):
            summary.append({
                "type": s.get("type") or s.get("kind") or s.get("signal"),
                "date": s.get("date") or s.get("when"),
                "detail": str(s.get("description") or s.get("message") or s)[:240],
            })
        else:
            summary.append({"detail": str(s)[:240]})
    return {
        "ok": True,
        "status": "complete",
        "project": proj,
        "signal_count": len(signal_list),
        "signals": summary,
        "note": "Signals are heuristic investigation leads, not verified conclusions.",
        "output_path": str((_workspace() / "projects" / proj / "data" / "detected-signals.json")),
    }


def report(project: Optional[str] = None, fmt: str = "markdown") -> Dict[str, Any]:
    """Export a markdown (default) or html report; return a truncated body for the session."""
    proj = _project_name(project)
    fmt = (fmt or "markdown").lower().strip()
    if fmt not in {"markdown", "html", "md"}:
        return {"ok": False, "error": "fmt must be markdown or html"}
    if fmt == "md":
        fmt = "markdown"

    with _in_workspace():
        from archaeology.report import export_markdown_report, _markdown_to_html

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
            "heuristics — not verified source conclusions or productivity measurements."
        ),
    }


def pipeline(repo_path: str, project: Optional[str] = None) -> Dict[str, Any]:
    """mine → signals → markdown report (analyze vectors optional / best-effort)."""
    proj = _project_name(project)
    mined = mine(repo_path, proj)
    if not mined.get("ok"):
        return {"ok": False, "failed_at": "mine", **mined}
    sig = signals(proj)
    if not sig.get("ok"):
        return {"ok": False, "failed_at": "signals", "mine": mined, **sig}
    # Best-effort analysis vectors — never fail the pipeline on them.
    analysis: Dict[str, Any]
    try:
        with _in_workspace():
            from archaeology.analysis_runner import run_analysis_vectors

            result = run_analysis_vectors(proj, verbose=False, vectors=None)
        analysis = {
            "ok": True,
            "vectors_run": list(result.keys()) if isinstance(result, dict) else [],
            "note": "Keyword-based leads, not verified conclusions.",
        }
    except Exception as exc:
        analysis = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    rep = report(proj, fmt="markdown")
    return {
        "ok": bool(rep.get("ok")),
        "status": "complete" if rep.get("ok") else "partial",
        "project": proj,
        "mine": {
            "commits_extracted": mined.get("commits_extracted"),
            "coverage": mined.get("coverage"),
            "warning": mined.get("warning"),
        },
        "signals": {"signal_count": sig.get("signal_count"), "signals": sig.get("signals")},
        "analysis": analysis,
        "report": {
            "output_path": rep.get("output_path"),
            "markdown": rep.get("markdown"),
            "truncated": rep.get("truncated"),
            "note": rep.get("note"),
        },
    }


# --- hooks ------------------------------------------------------------------

_BRIEF = (
    "[DevArch archaeology] This message asks about repository history or how the codebase "
    "evolved. Before guessing from a few recent commits: (1) call `devarch_pipeline` (or "
    "`devarch_mine` → `devarch_signals` → `devarch_report`) on the local git checkout, "
    "(2) lead with eras + signals from the report, (3) label every automated vector as an "
    "investigation lead — not a verified conclusion or productivity measurement, "
    "(4) refuse shallow clones (integrity rule). Data stays under plugin-data/devarch/."
)


def _on_pre_llm(user_message: str = "", **_: Any) -> Optional[Dict[str, str]]:
    try:
        if _cfg("inject_on_archaeology") and user_message and _ARCH_RE.search(user_message):
            return {"context": _BRIEF}
    except Exception:
        logger.debug("devarch: pre_llm_call failed", exc_info=True)
    return None


def _on_post_tool(tool_name: str = "", args: Optional[Dict[str, Any]] = None, result: Any = None,
                  **_: Any) -> None:
    try:
        if tool_name not in {
            "devarch_mine", "devarch_signals", "devarch_report", "devarch_pipeline",
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
            "commits": payload.get("commits_extracted") or (payload.get("mine") or {}).get("commits_extracted"),
            "signals": payload.get("signal_count") or (payload.get("signals") or {}).get("signal_count"),
            "output_path": payload.get("output_path") or (payload.get("report") or {}).get("output_path"),
        }
        ledger = _load_json(_ledger_path(), [])
        ledger.append(entry)
        _save_json(_ledger_path(), ledger[-LEDGER_MAX:])
    except Exception:
        logger.debug("devarch: post_tool_call failed", exc_info=True)
    return None


# --- tools ------------------------------------------------------------------

MINE_SCHEMA = {
    "name": "devarch_mine",
    "description": (
        "Mine a local git repository's full commit history into a DevArch project under "
        "plugin-data. Rejects shallow clones. Returns commit count + coverage. Local-only "
        "(no network fetch)."
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
        "DevArch project. Heuristic leads — not verified conclusions."
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
        "project and return a truncated body for the session."
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
        "report. Prefer this when the user asks how a local repo evolved."
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


def _wrap(fn):
    def handler(args: Optional[Dict[str, Any]] = None, **_: Any) -> str:
        try:
            return json.dumps(fn(args or {}), ensure_ascii=False)[:MAX_OUT]
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
    "  /devarch mine <repo-path> [project]     Mine full history (rejects shallow)\n"
    "  /devarch signals [project]              Detect development signals (leads)\n"
    "  /devarch report [project] [markdown|html]\n"
    "  /devarch pipeline <repo-path> [project] Mine → signals → report\n"
    "  /devarch list                           Projects under plugin-data\n"
    "  /devarch version                        Framework version + pin\n"
    "  /devarch status                         Recent ledger entries\n"
    "Vectors are investigation leads, not verified conclusions. Data under plugin-data/devarch/.\n"
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
            _on_post_tool("devarch_mine", {"repo_path": rest[0], "project": rest[1] if len(rest) > 1 else None}, res)
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
            name=schema["name"], toolset="devarch", schema=schema, handler=handler,
            description=schema["description"], emoji=emoji,
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
