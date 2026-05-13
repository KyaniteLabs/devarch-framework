"""DevArch MCP Server — AI assistant integration for repository archaeology.

Exposes DevArch pipeline commands as MCP tools that Claude Code, Cursor,
and other AI assistants can call directly.

Run with: devarch-mcp (after pip install devarch-framework[mcp])

Configure in .mcp.json:
{
  "mcpServers": {
    "devarch": {
      "type": "stdio",
      "command": "devarch-mcp",
      "env": {
        "DEVARCH_WORKSPACE": "/path/to/workspace"
      }
    }
  }
}
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .tools import (
    devarch_analyze,
    devarch_audit,
    devarch_build_db,
    devarch_get_project,
    devarch_init,
    devarch_list_projects,
    devarch_mine,
    devarch_query_analysis,
    devarch_query_eras,
    devarch_query_metrics,
    devarch_report,
    devarch_run_pipeline,
    devarch_signals,
    devarch_visualize,
)

mcp = FastMCP(
    "DevArch",
    instructions=(
        "DevArch is a forensic archaeology framework for git repositories. "
        "Use these tools to initialize projects, mine git history, run analysis "
        "vectors, generate visualizations, and query results. "
        "Typical flow: init → mine → build-db → signals → analyze → visualize → report."
    ),
)


# ── Project tools ────────────────────────────────────────────────────────

@mcp.tool()
def init_project(project_name: str, description: str = "", repo_url: str = "") -> dict[str, Any]:
    """Initialize a new DevArch project with directory structure and config."""
    return devarch_init(project_name, description, repo_url)


@mcp.tool()
def list_projects() -> list[dict[str, Any]]:
    """List all DevArch projects in the workspace."""
    return devarch_list_projects()


@mcp.tool()
def get_project(project_name: str) -> dict[str, Any]:
    """Get detailed information about a project including config and metrics."""
    return devarch_get_project(project_name)


# ── Pipeline tools ───────────────────────────────────────────────────────

@mcp.tool()
def mine(repo_path: str, project_name: str) -> dict[str, Any]:
    """Extract git commit history from a repository into a DevArch project."""
    return devarch_mine(repo_path, project_name)


@mcp.tool()
def build_db(project_name: str) -> dict[str, Any]:
    """Build SQLite database from extracted git data for a project."""
    return devarch_build_db(project_name)


@mcp.tool()
def detect_signals(project_name: str, min_gap_days: int | None = None) -> dict[str, Any]:
    """Detect development signals and era boundaries from commit history."""
    return devarch_signals(project_name, min_gap_days)


@mcp.tool()
def analyze(project_name: str, vectors: list[str] | None = None) -> dict[str, Any]:
    """Run analysis vectors (sdlc-gap-finder, ml-pattern-mapper, etc.) on a project.

    Available vectors: sdlc-gap-finder, ml-pattern-mapper, agentic-workflow,
    formal-terms-mapper, source-archaeologist, youtube-correlator.
    If vectors is None, all vectors run.
    """
    return devarch_analyze(project_name, vectors)


@mcp.tool()
def run_pipeline(repo_path: str, project_name: str) -> dict[str, Any]:
    """Run the full DevArch pipeline: init → mine → build-db → signals → analyze.

    This is the one-shot tool for processing a repository end-to-end.
    """
    return devarch_run_pipeline(repo_path, project_name)


# ── Output tools ─────────────────────────────────────────────────────────

@mcp.tool()
def visualize(project_name: str) -> dict[str, Any]:
    """Generate HTML visualization dashboard for a project."""
    return devarch_visualize(project_name)


@mcp.tool()
def report(project_name: str, fmt: str = "html") -> dict[str, Any]:
    """Generate a report for a project. Format: 'html' or 'markdown'."""
    return devarch_report(project_name, fmt)


@mcp.tool()
def audit(project_name: str, fail_on: str = "HIGH") -> dict[str, Any]:
    """Run audit checks on a project's deliverables and data integrity."""
    return devarch_audit(project_name, fail_on)


# ── Query tools ──────────────────────────────────────────────────────────

@mcp.tool()
def query_metrics(project_name: str) -> dict[str, Any]:
    """Get canonical metrics (total commits, active days, span, etc.) for a project."""
    return devarch_query_metrics(project_name)


@mcp.tool()
def query_eras(project_name: str) -> dict[str, Any]:
    """Get era analysis (development phases and boundaries) for a project."""
    return devarch_query_eras(project_name)


@mcp.tool()
def query_analysis(project_name: str, vector: str) -> dict[str, Any]:
    """Get results of a specific analysis vector for a project."""
    return devarch_query_analysis(project_name, vector)
