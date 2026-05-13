"""Project path resolution for the DevArch MCP server."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def get_workspace_root() -> Path:
    """Resolve the workspace root from DEVARCH_WORKSPACE env var or CWD."""
    env = os.environ.get("DEVARCH_WORKSPACE")
    if env:
        return Path(env).resolve()
    return Path.cwd().resolve()


def get_projects_dir() -> Path:
    """Return the projects/ directory path."""
    return get_workspace_root() / "projects"


def get_project_dir(project_name: str) -> Path:
    """Return a specific project's directory path."""
    return get_projects_dir() / project_name


def get_project_config(project_name: str) -> dict[str, Any] | None:
    """Load a project's project.json config."""
    config_path = get_project_dir(project_name) / "project.json"
    if not config_path.exists():
        return None
    return json.loads(config_path.read_text(encoding="utf-8"))


def list_projects() -> list[dict[str, Any]]:
    """List all projects in the workspace with basic metadata."""
    projects_dir = get_projects_dir()
    if not projects_dir.exists():
        return []

    projects = []
    for project_dir in sorted(projects_dir.iterdir()):
        if not project_dir.is_dir() or project_dir.name.startswith((".", "_")):
            continue
        config = get_project_config(project_dir.name)
        projects.append({
            "name": project_dir.name,
            "path": str(project_dir),
            "has_data": (project_dir / "data").exists(),
            "has_deliverables": (project_dir / "deliverables").exists(),
            "has_database": (project_dir / "data" / "archaeology.db").exists(),
            "description": config.get("description", "") if config else "",
            "repo_url": config.get("repo_url", "") if config else "",
        })
    return projects


def read_json(path: Path) -> dict[str, Any] | None:
    """Read a JSON file, returning None if it doesn't exist."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
