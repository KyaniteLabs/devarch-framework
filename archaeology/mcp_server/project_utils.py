"""Project path resolution for the DevArch MCP server."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from archaeology.pipeline import (  # noqa: F401  (re-exported: the pipeline owns resolution)
    get_project_dir,
    get_projects_dir,
    get_workspace_root,
    validate_project_name,
)

logger = logging.getLogger(__name__)


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
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to decode JSON from {path}: {e}")
        return None
    except OSError as e:
        logger.warning(f"Failed to read file {path}: {e}")
        return None
