"""AG4TE REST API, mounted by Hermes at /api/plugins/ag4te/."""

from __future__ import annotations

import importlib.util
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

from fastapi import APIRouter, Body, HTTPException, Query

router = APIRouter()


_load_lock = threading.Lock()
_module_scan_size = -1
_registered_plugin = None
_fallback_plugin = None


def _plugin():
    # Hermes gives secondary profiles a __home_<digest> module suffix. Resolve
    # by this plugin's source file so the dashboard shares the registered context.
    global _module_scan_size, _registered_plugin, _fallback_plugin
    registered = _registered_plugin
    if registered is not None and sys.modules.get(registered.__name__) is registered:
        return registered
    fallback = _fallback_plugin
    if fallback is not None and sys.modules.get(fallback.__name__) is fallback:
        if len(sys.modules) == _module_scan_size:
            return fallback
    if len(sys.modules) == _module_scan_size and fallback is not None:
        return fallback

    target = (Path(__file__).resolve().parent.parent / "__init__.py").resolve()
    registered = fallback = None
    private = None
    for name, mod in tuple(sys.modules.items()):
        if name == "_ag4te_private":
            private = mod
            continue
        filename = getattr(mod, "__file__", None)
        if not filename or not hasattr(mod, "start_dig"):
            continue
        try:
            if Path(filename).resolve() != target:
                continue
        except OSError:
            continue
        if getattr(mod, "_ctx", None) is not None:
            registered = mod
            break
        fallback = fallback or mod
    if registered is not None:
        _registered_plugin = registered
        _fallback_plugin = registered
        _module_scan_size = len(sys.modules)
        return registered
    fallback = fallback or private
    if fallback is not None and hasattr(fallback, "start_dig"):
        _fallback_plugin = fallback
        _module_scan_size = len(sys.modules)
        return fallback
    with _load_lock:
        mod = sys.modules.get("_ag4te_private")
        if mod is not None and hasattr(mod, "start_dig"):
            fallback = mod
        else:
            fallback = _load_private()
    _fallback_plugin = fallback
    _module_scan_size = len(sys.modules)
    return fallback


def _load_private():
    pkg_dir = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location("_ag4te_private", pkg_dir / "__init__.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_ag4te_private"] = mod
    try:
        spec.loader.exec_module(mod)
        settings = dict(mod.DEFAULTS)
        try:
            from hermes_cli.config import load_config_readonly  # type: ignore

            entry = ((load_config_readonly() or {}).get("plugins") or {}).get("entries", {}).get(
                "ag4te"
            ) or {}
            for key, value in (entry.get("settings") or {}).items():
                if key in settings and value is not None:
                    settings[key] = value
        except Exception:  # noqa: BLE001 - standalone API inspection uses defaults
            pass
        mod._ctx = SimpleNamespace(get_config=lambda key, default=None: settings.get(key, default))
    except BaseException:
        sys.modules.pop("_ag4te_private", None)
        raise
    return mod


def _bad(exc: Exception, code: int = 400):
    raise HTTPException(status_code=code, detail=str(exc))


@router.get("/projects")
def projects():
    return {"projects": _plugin().list_projects()}


@router.get("/repos")
def repos():
    p = _plugin()
    return {"roots": [str(r) for r in p.repo_roots()], "repos": p.candidate_repos()}


@router.get("/dig")
def dig(project: str = Query(...)):
    p = _plugin()
    try:
        d = p.load_dig(p.validate_project(project))
    except p.DigError as exc:
        _bad(exc)
    if d is None:
        raise HTTPException(status_code=404, detail=f"no finished dig named {project}")
    return d


@router.get("/status")
def status(project: str = Query(...)):
    p = _plugin()
    try:
        return p.read_status(p.validate_project(project))
    except p.DigError as exc:
        _bad(exc)


@router.post("/dig")
def start(body: dict = Body(...)):
    p = _plugin()
    repo, project = body.get("repo"), body.get("project") or None
    try:
        return p.start_dig(repo, project, resume=bool(body.get("resume")))
    except p.DigError as exc:
        _bad(exc, 409 if "already running" in str(exc) else 400)


@router.post("/cancel")
def cancel(body: dict = Body(...)):
    p = _plugin()
    try:
        project = p.validate_project(body.get("project") or "")
    except p.DigError as exc:
        _bad(exc)
    try:
        return p.cancel_dig(project)
    except p.DigError as exc:
        _bad(exc, 409)
