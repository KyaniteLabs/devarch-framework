"""MCP tools wrapping DevArch pipeline functions.

Each tool is a thin adapter over ``archaeology.pipeline``: it names the project,
calls the operation and shapes the result into a dict for AI assistant
consumption. No subprocess or CLI invocation.
"""

from __future__ import annotations

from typing import Any

from archaeology import pipeline
from archaeology.pipeline import PipelineError, ProjectRef, RunStage

from .project_utils import (
    get_project_config,
    get_project_dir,
    list_projects,
    read_json,
)


def _ref(project_name: str) -> ProjectRef:
    return ProjectRef.for_workspace(project_name)


# ── Project tools ────────────────────────────────────────────────────────


def devarch_init(project_name: str, description: str = "", repo_url: str = "") -> dict[str, Any]:
    """Initialize a new DevArch project with directory structure and config."""
    result = pipeline.init(_ref(project_name), description, repo_url)
    return {
        "status": "created" if result.created else "exists",
        "project": project_name,
        "path": str(result.project_dir),
    }


def devarch_list_projects() -> list[dict[str, Any]]:
    """List all DevArch projects in the workspace."""
    return list_projects()


def devarch_get_project(project_name: str) -> dict[str, Any]:
    """Get detailed information about a project including config and metrics."""
    project_dir = get_project_dir(project_name)
    if not project_dir.exists():
        return {"error": f"Project '{project_name}' not found"}

    config = get_project_config(project_name) or {}
    metrics = read_json(project_dir / "deliverables" / "canonical-metrics.json")
    eras = read_json(project_dir / "data" / "commit-eras.json")
    signals = read_json(project_dir / "data" / "detected-signals.json")

    return {
        "name": project_name,
        "path": str(project_dir),
        "config": config,
        "metrics": metrics,
        "era_count": len(eras.get("eras", [])) if eras else 0,
        "signal_count": len(signals.get("signals", [])) if signals else 0,
        "has_database": (project_dir / "data" / "archaeology.db").exists(),
        "has_visualization": (project_dir / "deliverables" / "visuals").exists(),
    }


# ── Pipeline tools ───────────────────────────────────────────────────────


def devarch_mine(repo_path: str, project_name: str) -> dict[str, Any]:
    """Extract git commit history from a repository into a project."""
    try:
        return _mine_dict(project_name, pipeline.mine(repo_path, _ref(project_name)))
    except PipelineError as e:
        return {"error": e.message}


def _mine_dict(project_name: str, mined: pipeline.MineResult) -> dict[str, Any]:
    return {
        "status": "complete",
        "project": project_name,
        "commits_extracted": mined.commits,
        "csv_path": mined.csv_path,
    }


def devarch_build_db(project_name: str) -> dict[str, Any]:
    """Build SQLite database from extracted git data."""
    built = pipeline.build_db(_ref(project_name))
    return _build_dict(project_name, built)


def _build_dict(project_name: str, built: pipeline.BuildResult) -> dict[str, Any]:
    if built.error is not None:
        return {"status": "failed", "project": project_name, "error": built.error}
    return {"status": "complete", "project": project_name, "database_path": str(built.db_path)}


def devarch_signals(project_name: str, min_gap_days: int | None = None) -> dict[str, Any]:
    """Detect development signals from commit history."""
    try:
        found = pipeline.signals(_ref(project_name), min_gap_days=min_gap_days)
    except PipelineError as e:
        return {"error": e.message}
    return {
        "status": "complete",
        "project": project_name,
        "signal_count": len(found.signals),
        "output_path": str(found.output_path),
    }


def devarch_analyze(project_name: str, vectors: list[str] | None = None) -> dict[str, Any]:
    """Run analysis vectors on a project's data."""
    result = pipeline.analyze(_ref(project_name), vectors).results
    return {
        "status": "complete",
        "project": project_name,
        "vectors_run": list(result.keys()) if result else [],
        "results": result,
    }


def devarch_run_pipeline(repo_path: str, project_name: str) -> dict[str, Any]:
    """Run the full DevArch pipeline: mine → build-db → signals → analyze."""
    run = pipeline.run_pipeline(repo_path, _ref(project_name))
    results: dict[str, Any] = {"init": "created" if run.init_created else "exists"}

    if run.stage is RunStage.MINE_FAILED:
        results["mine"] = {"error": run.mine_error}
        results["status"] = "failed"
        results["failed_at"] = run.failed_at
        return results
    results["mine"] = _mine_dict(project_name, run.mine)
    results["commits_extracted"] = run.mine.commits

    if run.stage is RunStage.BUILD_FAILED:
        results["build_db"] = "failed"
        results["status"] = "failed"
        results["failed_at"] = run.failed_at
        return results
    results["build_db"] = "complete"

    results["signals"] = run.signal_count
    results["analysis"] = run.analysis
    results["status"] = "complete"
    results["project"] = project_name
    return results


# ── Output tools ─────────────────────────────────────────────────────────


def devarch_visualize(project_name: str) -> dict[str, Any]:
    """Generate HTML visualization for a project."""
    try:
        output_path = pipeline.render_project_index(_ref(project_name))
    except PipelineError as e:
        return {"error": e.message}
    return {"status": "complete", "project": project_name, "output_path": str(output_path)}


def devarch_report(project_name: str, fmt: str = "html") -> dict[str, Any]:
    """Generate a report (html or markdown) for a project."""
    try:
        report = pipeline.render_report(_ref(project_name), fmt)
    except PipelineError as e:
        return {"error": e.message}
    return {"status": "complete", "format": report.fmt, "output_path": str(report.output_path)}


def devarch_audit(project_name: str, fail_on: str = "HIGH") -> dict[str, Any]:
    """Run audit checks on a project.

    ``fail_on`` is accepted for tool-signature compatibility; this tool has
    always reported every finding and never used it to decide a verdict.
    """
    findings = pipeline.audit(_ref(project_name), fail_on=None).findings

    passed = sum(1 for f in findings if f.severity == "PASS")
    failed = sum(1 for f in findings if f.severity != "PASS")

    return {
        "status": "complete",
        "project": project_name,
        "total_checks": len(findings),
        "passed": passed,
        "failed": failed,
        "findings": [
            {"check": f.code, "severity": f.severity, "message": f.message} for f in findings
        ],
    }


# ── Query tools ──────────────────────────────────────────────────────────


def devarch_query_metrics(project_name: str) -> dict[str, Any]:
    """Get canonical metrics for a project."""
    project_dir = get_project_dir(project_name)
    metrics = read_json(project_dir / "deliverables" / "canonical-metrics.json")
    if metrics is None:
        return {"error": "Metrics not found. Run the pipeline first."}
    return metrics


def devarch_query_eras(project_name: str) -> dict[str, Any]:
    """Get era analysis for a project."""
    project_dir = get_project_dir(project_name)
    eras = read_json(project_dir / "data" / "commit-eras.json")
    if eras is None:
        return {"error": "Era data not found. Run signals first."}
    return eras


def devarch_query_analysis(project_name: str, vector: str) -> dict[str, Any]:
    """Get results of a specific analysis vector."""
    from archaeology.analysis_runner import AnalysisRunner

    if vector not in AnalysisRunner.VECTORS:
        return {
            "error": f"Unknown vector '{vector}'. Available: {', '.join(AnalysisRunner.VECTORS)}",
        }

    project_dir = get_project_dir(project_name)
    analysis_path = project_dir / "deliverables" / "analysis" / f"analysis-{vector}.json"
    result = read_json(analysis_path)
    if result is None:
        return {"error": f"Analysis '{vector}' not found. Run analyze first."}
    return result
