"""MCP tools wrapping DevArch pipeline functions.

Each tool calls the underlying Python function directly — no subprocess
or CLI invocation. Returns structured data for AI assistant consumption.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .project_utils import (
    get_project_config,
    get_project_dir,
    get_projects_dir,
    get_workspace_root,
    list_projects,
    read_json,
)


@contextmanager
def _in_workspace():
    """Temporarily chdir to the workspace root for CWD-relative function calls."""
    saved = os.getcwd()
    os.chdir(str(get_workspace_root()))
    try:
        yield
    finally:
        os.chdir(saved)


# ── Project tools ────────────────────────────────────────────────────────


def devarch_init(project_name: str, description: str = "", repo_url: str = "") -> dict[str, Any]:
    """Initialize a new DevArch project with directory structure and config."""
    project_dir = get_project_dir(project_name)
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "data").mkdir(exist_ok=True)
    (project_dir / "deliverables").mkdir(exist_ok=True)

    config_path = project_dir / "project.json"
    if config_path.exists():
        return {"status": "exists", "project": project_name, "path": str(project_dir)}

    config = {
        "name": project_name,
        "description": description,
        "repo_url": repo_url,
        "developer": {},
        "timeline": {},
        "overrides": {},
        "visualization": {},
        "data_sources": {},
    }
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return {"status": "created", "project": project_name, "path": str(project_dir)}


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
    from archaeology.extractors.git import extract_git_log, extract_git_log_with_stats

    expanded = os.path.expanduser(repo_path)
    if not os.path.isdir(expanded):
        return {"error": f"Repository not found: {repo_path}"}
    if not os.path.isdir(os.path.join(expanded, ".git")):
        return {"error": f"Not a git repository: {repo_path}"}

    project_dir = get_project_dir(project_name)
    data_dir = project_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    csv_path = str(data_dir / "github-commits.csv")
    count = extract_git_log(expanded, csv_path)

    stats_path = str(data_dir / "github-commits-with-stats.txt")
    extract_git_log_with_stats(expanded, stats_path)

    return {
        "status": "complete",
        "project": project_name,
        "commits_extracted": count,
        "csv_path": csv_path,
    }


def devarch_build_db(project_name: str) -> dict[str, Any]:
    """Build SQLite database from extracted git data."""
    from archaeology.db.builder import build_db

    project_dir = get_project_dir(project_name)
    db_path = project_dir / "data" / "archaeology.db"

    try:
        build_db(project_root=project_dir, verbose=False)
    except Exception as e:
        return {
            "status": "failed",
            "project": project_name,
            "error": str(e),
        }

    if db_path.exists():
        return {
            "status": "complete",
            "project": project_name,
            "database_path": str(db_path),
        }
    return {
        "status": "failed",
        "project": project_name,
        "error": "Database file not created after build",
    }


def devarch_signals(project_name: str, min_gap_days: int | None = None) -> dict[str, Any]:
    """Detect development signals from commit history."""
    from archaeology.classifiers.era_detector import detect_signals

    project_dir = get_project_dir(project_name)
    db_path = project_dir / "data" / "archaeology.db"
    if not db_path.exists():
        return {"error": "Database not found. Run build-db first."}

    config = {}
    if min_gap_days is not None:
        config["min_gap_days"] = min_gap_days

    with _in_workspace():
        signals = detect_signals(project_name, config=config or None)

    signal_list = signals.get("signals", []) if isinstance(signals, dict) else signals
    return {
        "status": "complete",
        "project": project_name,
        "signal_count": len(signal_list),
        "output_path": str(project_dir / "data" / "detected-signals.json"),
    }


def devarch_analyze(project_name: str, vectors: list[str] | None = None) -> dict[str, Any]:
    """Run analysis vectors on a project's data."""
    from archaeology.analysis_runner import run_analysis_vectors

    with _in_workspace():
        result = run_analysis_vectors(
            project_name,
            verbose=False,
            vectors=vectors,
        )

    return {
        "status": "complete",
        "project": project_name,
        "vectors_run": list(result.keys()) if result else [],
        "results": result,
    }


def devarch_run_pipeline(repo_path: str, project_name: str) -> dict[str, Any]:
    """Run the full DevArch pipeline: mine → build-db → signals → analyze."""
    results = {}

    # Step 1: Init
    init_result = devarch_init(project_name)
    results["init"] = init_result["status"]

    # Step 2: Mine
    mine_result = devarch_mine(repo_path, project_name)
    results["mine"] = mine_result
    if "error" in mine_result:
        results["status"] = "failed"
        results["failed_at"] = "mine"
        return results
    results["commits_extracted"] = mine_result.get("commits_extracted", 0)

    # Step 3: Build DB
    db_result = devarch_build_db(project_name)
    results["build_db"] = db_result.get("status", "unknown")
    if db_result.get("status") == "failed":
        results["status"] = "failed"
        results["failed_at"] = "build_db"
        return results

    # Step 4: Signals
    sig_result = devarch_signals(project_name)
    results["signals"] = sig_result.get("signal_count", 0)

    # Step 5: Analyze
    try:
        analyze_result = devarch_analyze(project_name)
        results["analysis"] = analyze_result.get("vectors_run", [])
    except Exception as e:
        results["analysis"] = f"skipped: {e}"

    results["status"] = "complete"
    results["project"] = project_name
    return results


# ── Output tools ─────────────────────────────────────────────────────────


def devarch_visualize(project_name: str) -> dict[str, Any]:
    """Generate HTML visualization for a project."""
    project_dir = get_project_dir(project_name)
    if not project_dir.exists():
        return {"error": f"Project '{project_name}' not found"}

    from archaeology.visualization.dashboard import generate_project_index

    projects_dir = get_projects_dir()
    projects = []
    if projects_dir.exists():
        from archaeology.visualization.dashboard import discover_projects
        projects = discover_projects(projects_dir)

    # Find the matching project
    project_data = None
    for p in projects:
        if p["name"] == project_name:
            project_data = p
            break

    if not project_data:
        return {"error": f"Project '{project_name}' not found in discovered projects"}

    html = generate_project_index(project_data)
    output_dir = project_dir / "deliverables" / "visuals"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "index.html"
    output_path.write_text(html, encoding="utf-8")

    return {
        "status": "complete",
        "project": project_name,
        "output_path": str(output_path),
    }


def devarch_report(project_name: str, fmt: str = "html") -> dict[str, Any]:
    """Generate a report (html or markdown) for a project."""
    fmt = fmt.lower().strip()
    if fmt not in ("html", "markdown"):
        return {"error": f"Invalid format '{fmt}'. Use 'html' or 'markdown'."}

    project_dir = get_project_dir(project_name)
    if not project_dir.exists():
        return {"error": f"Project '{project_name}' not found"}

    from archaeology.report import export_markdown_report, _markdown_to_html

    md_path = export_markdown_report(project_name, str(project_dir))

    if fmt == "html":
        title = project_name
        config = get_project_config(project_name)
        if config:
            title = config.get("visualization", {}).get("title", project_name)

        md_content = md_path.read_text(encoding="utf-8")
        html_content = _markdown_to_html(md_content, title)

        output_dir = project_dir / "deliverables" / "visuals"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "report.html"
        output_path.write_text(html_content, encoding="utf-8")
        return {"status": "complete", "format": "html", "output_path": str(output_path)}

    return {"status": "complete", "format": "markdown", "output_path": str(md_path)}


def devarch_audit(project_name: str, fail_on: str = "HIGH") -> dict[str, Any]:
    """Run audit checks on a project."""
    from archaeology.audit import run_audit

    findings = run_audit(project_name, str(get_workspace_root()))

    passed = sum(1 for f in findings if f.severity == "PASS")
    failed = sum(1 for f in findings if f.severity != "PASS")

    return {
        "status": "complete",
        "project": project_name,
        "total_checks": len(findings),
        "passed": passed,
        "failed": failed,
        "findings": [
            {"check": f.code, "severity": f.severity, "message": f.message}
            for f in findings
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
