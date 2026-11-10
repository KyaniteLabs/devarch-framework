"""AG4TE REST API, mounted by Hermes at /api/plugins/ag4te/."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException, Query

router = APIRouter()


def _plugin():
    # The private copy is checked too: loading it again would reset the running-dig registry,
    # and every dig would then read as interrupted.
    for name in ("ag4te", "hermes_plugins.ag4te", "plugins.ag4te", "_ag4te_private"):
        mod = sys.modules.get(name)
        if mod is not None and hasattr(mod, "start_dig"):
            return mod
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
        return p.cancel_dig(body.get("project") or "")
    except p.DigError as exc:
        _bad(exc, 409)
