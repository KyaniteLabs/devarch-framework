"""Project path resolution for the DevArch MCP server."""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def get_workspace_root() -> Path:
    """Resolve the workspace root from DEVARCH_WORKSPACE env var or CWD."""
    env = os.environ.get("DEVARCH_WORKSPACE")
    if env:
        path = Path(env).resolve()
        # Validate workspace path
        if not path.exists():
            raise ValueError(f"DEVARCH_WORKSPACE path does not exist: {path}")
        if not path.is_dir():
            raise ValueError(f"DEVARCH_WORKSPACE path is not a directory: {path}")
        return path
    return Path.cwd().resolve()


def get_projects_dir() -> Path:
    """Return the projects/ directory path."""
    return get_workspace_root() / "projects"


def validate_project_name(name: str) -> None:
    """Validate project name for security.

    Args:
        name: The project name to validate

    Raises:
        ValueError: If the project name is invalid
    """
    if not name:
        raise ValueError("Project name cannot be empty")

    if len(name) > 100:
        raise ValueError(f"Project name too long (max 100 chars): {len(name)}")

    # Only allow alphanumeric, dot, underscore, hyphen
    if not re.match(r'^[a-zA-Z0-9._-]+$', name):
        raise ValueError(f"Project name contains invalid characters: {name!r}")

    # Reject path traversal attempts
    if '..' in name:
        raise ValueError(f"Project name cannot contain '..': {name!r}")

    if name.startswith('/'):
        raise ValueError(f"Project name cannot start with '/': {name!r}")


def get_project_dir(project_name: str) -> Path:
    """Return a specific project's directory path.

    Args:
        project_name: Validated project name

    Returns:
        Path to the project directory

    Raises:
        ValueError: If project name is invalid or path traversal detected
    """
    validate_project_name(project_name)

    projects_dir = get_projects_dir()
    project_path = (projects_dir / project_name).resolve()

    # Verify the resolved path is within projects directory
    try:
        project_path.relative_to(projects_dir.resolve())
    except ValueError:
        raise ValueError(f"Project path escape detected: {project_name!r}")

    return project_path


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
