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


@mcp.tool()
def analyze(project_name: str, vectors: list[str] | None = None) -> dict[str, Any]:
    """Run analysis vectors (sdlc-gap-finder, ml-pattern-mapper, etc.) against a mined project.

    Returns JSON with per-vector results. Use after build_db and detect_signals have
    populated the project. Pass project_name from init_project/run_pipeline and
    optionally vectors to select a subset of available analyzers.
    """
    return devarch_analyze(project_name, vectors)


@mcp.tool()
def audit(project_name: str, fail_on: str = "HIGH") -> dict[str, Any]:
    """Run data-integrity and deliverable audit checks on a project.

    Returns JSON with findings grouped by severity. Use before trusting or publishing
    a project's artifacts. Pass project_name from init_project/run_pipeline and
    fail_on to set the severity gate (default HIGH).
    """
    return devarch_audit(project_name, fail_on)


@mcp.tool()
def build_db(project_name: str) -> dict[str, Any]:
    """Build the SQLite analysis database from a project's mined git history.

    Returns JSON with row counts and build status. Use after mine has extracted
    commits. Pass project_name from mine/run_pipeline.
    """
    return devarch_build_db(project_name)


@mcp.tool()
def detect_signals(project_name: str, min_gap_days: int | None = None) -> dict[str, Any]:
    """Detect development signals and era boundaries from a project's commit history.

    Returns JSON with detected eras and signal events. Use after build_db. Pass
    project_name from build_db/run_pipeline and optionally min_gap_days to tune
    era sensitivity.
    """
    return devarch_signals(project_name, min_gap_days)


@mcp.tool()
def get_project(project_name: str) -> dict[str, Any]:
    """Get detailed information about one project, including config and metrics.

    Returns JSON with project metadata and metrics. Use when you need a single
    project's status. Pass project_name from list_projects/init_project.
    """
    return devarch_get_project(project_name)


@mcp.tool()
def init_project(project_name: str, description: str = "", repo_url: str = "") -> dict[str, Any]:
    """Initialize a new DevArch project with its directory structure and config.

    Returns JSON with the created project path. Use first to create a project before
    mining or analysis. Pass project_name (unique), and optionally description and
    repo_url; the returned name feeds mine, build_db, and run_pipeline.
    """
    return devarch_init(project_name, description, repo_url)


@mcp.tool()
def list_projects() -> list[dict[str, Any]]:
    """List all DevArch projects in the workspace.

    Returns a list of project summary dicts. Use to discover existing project names.
    No parameters; the returned names feed get_project, mine, build_db, analyze, and
    the query tools.
    """
    return devarch_list_projects()


@mcp.tool()
def mine(repo_path: str, project_name: str) -> dict[str, Any]:
    """Extract git commit history from a repository into a DevArch project.

    Returns JSON with the commit count and extraction status. Use after init_project
    to load a repo's history. Pass repo_path as the local git checkout and
    project_name from init_project/run_pipeline.
    """
    return devarch_mine(repo_path, project_name)


@mcp.tool()
def query_analysis(project_name: str, vector: str) -> dict[str, Any]:
    """Get the stored results of one analysis vector for a project.

    Returns JSON with the vector's findings. Use after analyze has run. Pass
    project_name from init_project and vector (e.g. sdlc-gap-finder) from a prior
    analyze result.
    """
    return devarch_query_analysis(project_name, vector)


@mcp.tool()
def query_eras(project_name: str) -> dict[str, Any]:
    """Get the era analysis (development phases and boundaries) for a project.

    Returns JSON with eras and gap intervals. Use after detect_signals has run.
    Pass project_name from init_project/run_pipeline.
    """
    return devarch_query_eras(project_name)


@mcp.tool()
def query_metrics(project_name: str) -> dict[str, Any]:
    """Get the canonical metrics (total commits, active days, time span) for a project.

    Returns JSON with the metric set. Use to summarize a project's scale. Pass
    project_name from init_project/run_pipeline.
    """
    return devarch_query_metrics(project_name)


@mcp.tool()
def report(project_name: str, fmt: str = "html") -> dict[str, Any]:
    """Generate a report (HTML or markdown) for a project.

    Returns JSON with the output path. Use after the pipeline has produced analysis
    results. Pass project_name from init_project/run_pipeline and fmt as html or
    markdown (default html).
    """
    return devarch_report(project_name, fmt)


@mcp.tool()
def run_pipeline(repo_path: str, project_name: str) -> dict[str, Any]:
    """Run the full DevArch pipeline end to end: init, mine, build-db, signals, analyze.

    Returns JSON with per-stage status. Use to process a repo in one call. Pass
    repo_path as the local git checkout and project_name to create or reuse.
    """
    return devarch_run_pipeline(repo_path, project_name)


@mcp.tool()
def visualize(project_name: str) -> dict[str, Any]:
    """Generate an HTML visualization dashboard for a project.

    Returns JSON with the output path. Use after build_db/analyze to explore a
    project graphically. Pass project_name from init_project/run_pipeline.
    """
    return devarch_visualize(project_name)
