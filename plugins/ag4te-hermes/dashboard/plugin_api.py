"""AG4TE REST API, mounted by Hermes at /api/plugins/ag4te/."""

from __future__ import annotations

import importlib.util
import sys
import threading
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException, Query

router = APIRouter()


_load_lock = threading.Lock()


def _plugin():
    # The private copy is loaded once, under a lock; the running-dig registry is process-wide
    # (see _job_registry), so even a second copy would see the same digs.
    for name in ("ag4te", "hermes_plugins.ag4te", "plugins.ag4te"):
        mod = sys.modules.get(name)
        if mod is not None and hasattr(mod, "start_dig"):
            return mod
    with _load_lock:
        mod = sys.modules.get("_ag4te_private")
        if mod is not None and hasattr(mod, "start_dig"):
            return mod
        return _load_private()


def _load_private():
    pkg_dir = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location("_ag4te_private", pkg_dir / "__init__.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_ag4te_private"] = mod
    try:
        spec.loader.exec_module(mod)
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
