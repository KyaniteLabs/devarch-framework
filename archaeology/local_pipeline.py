"""Helpers for the local GITHUB_pipeline verification authority."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _get_dir(env_var: str, label: str) -> Path:
    """Resolve a directory from an environment variable."""
    env_val = os.environ.get(env_var, "")
    if env_val:
        return Path(env_val)
    raise OSError(
        f"{env_var} environment variable not set. "
        f"Please set it to {label}."
    )


DEFAULT_PIPELINE_DIR: Path | None = None
DEFAULT_REPOS_DIR: Path | None = None


@dataclass(frozen=True)
class LocalPipelineStatus:
    run_timestamp: str | None
    overall_health: str | None
    repo: str
    repo_health: str | None
    repo_verdict: str | None
    issues: dict[str, Any]
    open_prs: int | None
    open_issues: int | None
    latest_json: Path

    @property
    def issue_total(self) -> int:
        try:
            return int(self.issues.get("total", 0))
        except (TypeError, ValueError, AttributeError):
            return 0


def latest_json_path(pipeline_dir: str | Path) -> Path:
    return Path(pipeline_dir) / ".omc" / "logs" / "repo-pipeline" / "latest.json"


def run_local_pipeline(
    pipeline_dir: str | Path = DEFAULT_PIPELINE_DIR,
    repos_dir: str | Path = DEFAULT_REPOS_DIR,
    top_repos: int = 20,
    review_days: int = 30,
) -> None:
    """Run the deterministic local pipeline producer."""
    pipeline_dir = Path(pipeline_dir)
    cmd = [
        sys.executable,
        "scripts/run-pipeline-once.py",
        "--top-repos",
        str(top_repos),
        "--review-days",
        str(review_days),
    ]
    env = os.environ.copy()
    env.update(
        {
            "PIPELINE_REPOS_DIR": str(repos_dir),
            "PIPELINE_TOP_REPOS": str(top_repos),
            "PIPELINE_REVIEW_DAYS": str(review_days),
        }
    )
    subprocess.run(cmd, cwd=pipeline_dir, env=env, check=True, timeout=300)


def read_local_pipeline_status(pipeline_dir: str | Path, repo_name: str) -> LocalPipelineStatus:
    """Read latest local pipeline JSON and extract one repo's status."""
    path = latest_json_path(pipeline_dir)
    if not path.exists():
        raise FileNotFoundError(f"Local pipeline latest.json not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))

    # Try to find repo in supervision.missions first (new format)
    target = None
    supervision = payload.get("supervision", {})
    if isinstance(supervision, dict):
        missions = supervision.get("missions", [])
        if missions and isinstance(missions, list):
            for mission in missions:
                if isinstance(mission, dict):
                    mission_repo = mission.get("repo", "")
                    # Match against owner/repo or just repo name
                    if (mission_repo == repo_name or
                        mission_repo.endswith("/" + repo_name) or
                        repo_name.endswith("/" + mission_repo.split("/")[-1])):
                        target = mission
                        break

    # Fall back to repos array (old format)
    if target is None:
        for repo in payload.get("repos", []):
            names = {str(repo.get("name", "")), str(repo.get("full_name", "")), str(repo.get("path", ""))}
            if repo_name in names or repo_name.endswith("/" + str(repo.get("name", ""))):
                target = repo
                break

    if target is None:
        # Build helpful error message with available repos
        reviewed_repos = []
        supervision = payload.get("supervision", {})
        if isinstance(supervision, dict):
            missions = supervision.get("missions", [])
            if missions:
                reviewed_repos = [m.get("repo", "") for m in missions if isinstance(m, dict)]
        if not reviewed_repos:
            reviewed_repos = [repo.get("name", "") for repo in payload.get("repos", [])]
        reviewed = ", ".join(str(r) for r in reviewed_repos)
        raise ValueError(f"Repo '{repo_name}' not found in latest local pipeline reviewed repos. Reviewed: {reviewed}")

    summary = payload.get("summary", {})
    # Normalize issues to dict - pipeline may return list or dict
    raw_issues = target.get("issues")
    if isinstance(raw_issues, list):
        issues = {"items": raw_issues, "total": len(raw_issues)}
    else:
        issues = raw_issues or {}

    # Extract repo name from multiple possible fields
    repo_full_name = (
        target.get("repo") or  # new format
        target.get("full_name") or  # old format
        target.get("path") or
        target.get("name", "")
    )

    # Extract health/verdict from mission or repo data
    repo_health = target.get("health") or target.get("status")
    repo_verdict = target.get("verdict")

    return LocalPipelineStatus(
        run_timestamp=payload.get("run_timestamp"),
        overall_health=summary.get("overall_health"),
        repo=str(repo_full_name),
        repo_health=repo_health,
        repo_verdict=repo_verdict,
        issues=issues,
        open_prs=target.get("open_prs"),
        open_issues=target.get("open_issues"),
        latest_json=path,
    )


def status_lines(status: LocalPipelineStatus) -> list[str]:
    """Human-readable status lines for CLI output."""
    return [
        f"run_timestamp: {status.run_timestamp}",
        f"summary_overall_health: {status.overall_health}",
        f"repo: {status.repo}",
        f"health: {status.repo_health}",
        f"verdict: {status.repo_verdict}",
        f"issues: {json.dumps(status.issues, sort_keys=True)}",
        f"open_prs: {status.open_prs}",
        f"open_issues: {status.open_issues}",
        f"latest_json: {status.latest_json}",
    ]
