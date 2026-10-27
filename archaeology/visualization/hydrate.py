"""HTML template hydration for the CLI's visualization step.

Moved from archaeology/pipeline.py (L6: the hydrator is a renderer and
belongs beside the templates it fills; pipeline.py keeps the service
surface, this module owns the HTML mechanics). Behavior unchanged —
pinned byte-for-byte by tests/test_pipeline.py's visualization tests."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..pipeline import ProjectRef

DEFAULT_TEMPLATE = os.path.join("archaeology", "visualization", "template.html")


@dataclass(frozen=True)
class VisualizationResult:
    output_path: str
    warning: str | None = None


def _load_json(path: str) -> Any:
    from ..pipeline import PipelineError  # local: hydrate must not import pipeline at module load

    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise PipelineError(f"Invalid JSON in {path}: {e}", kind="invalid-json")


def render_visualization(project: ProjectRef, template: str = DEFAULT_TEMPLATE) -> VisualizationResult:
    """Hydrate the HTML template from project config and data (the CLI renderer)."""
    from ..pipeline import PipelineError  # local: see module header

    project_dir = str(project.resolve())
    data_json = os.path.join(project_dir, "deliverables", "data.json")
    output_html = os.path.join(project_dir, "deliverables", "visuals", "archaeology.html")

    if not os.path.exists(template):
        raise PipelineError(f"Template not found at {template}", kind="template-missing")

    # Load project config for hydration
    config_path = os.path.join(project_dir, "project.json")
    project_config = _load_json(config_path) if os.path.exists(config_path) else {}

    vis = project_config.get("visualization", {})

    # Read template and inject project-specific values
    with open(template, encoding="utf-8") as f:
        html = f.read()

    # Compute stats from commit-eras.json for template hydration
    total_commits = 0
    total_lines = 0
    first_date = ""
    last_date = ""
    agent_count = 0
    eras_data = None
    eras_json = os.path.join(project_dir, "data", "commit-eras.json")
    if os.path.exists(eras_json):
        eras_data = _load_json(eras_json)
        total_commits = eras_data.get("total_commits", 0)
        lifespan = eras_data.get("lifespan", "")
        # Parse "43 days (Feb 28 - Apr 11, 2026)" format
        if "(" in lifespan and ")" in lifespan:
            date_part = lifespan.split("(")[1].split(")")[0]
            parts = date_part.split(" - ")
            first_date = parts[0].strip() if parts else ""
            last_date = parts[-1].strip() if len(parts) > 1 else ""
        # Count unique agents from agent_evidence
        agent_evidence = eras_data.get("agent_evidence", {})
        agent_count = len(agent_evidence)
        if not agent_count:
            agent_count = 6  # Claude, Kai, Cursor, Kimi, Codex, dogfood
        # Get file count from codebase_growth last entry
        growth = eras_data.get("codebase_growth", [])
        if growth:
            total_lines = growth[-1].get("files", 0)
    elif os.path.exists(data_json):
        pdata = _load_json(data_json)
        total_commits = pdata.get("total_commits", 0)

    # Hydrate template variables
    title = vis.get("title", project.name.upper())
    duration = vis.get("duration", f"{first_date} — {last_date}" if first_date else "")
    html = html.replace("{{PROJECT_NAME}}", title)
    html = html.replace("{{PROJECT_DURATION}}", duration)
    html = html.replace("{{TOTAL_COMMITS}}", str(total_commits or 803))
    html = html.replace("{{TOTAL_LINES}}", str(total_lines or "35,600"))
    html = html.replace("{{AGENT_COUNT}}", str(agent_count or 6))
    # Compute era count for meta description
    era_count = len(eras_data.get("eras", [])) if os.path.exists(eras_json) else 0
    html = html.replace("{{ERA_COUNT}}", str(era_count))

    # Also update <title> tag if it still has the old format
    html = html.replace(
        "<title>DevArch Framework</title>",
        f"<title>{title} — DevArch Framework</title>",
    )

    # Generate era color CSS variables from config
    era_colors = vis.get("era_colors", {})
    if era_colors:
        era_css = "\n".join(
            f"  --{era_key}: {color};"
            for era_key, color in era_colors.items()
        )
        # Insert era colors after :root block opens
        html = html.replace(
            "/* ERA COLORS */",
            f"/* ERA COLORS — from project.json */\n{era_css}",
        )

    # Generate agent color CSS variables
    agent_colors = vis.get("agent_colors", {})
    if agent_colors:
        agent_css = "\n".join(
            f"  --{name.lower()}: {color};"
            for name, color in agent_colors.items()
        )
        html = html.replace(
            "/* AGENT COLORS */",
            f"/* AGENT COLORS — from project.json */\n{agent_css}",
        )

    # Inline data.json so the HTML works from file:// (no CORS issues)
    if os.path.exists(data_json):
        with open(data_json, encoding="utf-8") as f:
            data_payload = json.load(f)

        # Merge commit_eras and top-level fields from commit-eras.json into PROJECT_DATA
        # so the era timeline visualization has real data to render.
        if eras_data is not None:
            data_payload.setdefault("commit_eras", eras_data.get("eras", []))
            data_payload.setdefault("total_commits", eras_data.get("total_commits", 0))
            data_payload.setdefault("first_commit_date", eras_data.get("first_commit_date", ""))
            data_payload.setdefault("last_commit_date", eras_data.get("last_commit_date", ""))

        data_content = json.dumps(data_payload)
        safe_data_content = data_content.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
        inline_script = f'<script>window.PROJECT_DATA = {safe_data_content}; window.dispatchEvent(new Event("data-loaded"));</script>'
        html = html.replace(
            '<script>\n  // Load project data from external JSON file\n  // The data.json file contains all visualization data (telemetry, sessions, eras, etc.)\n  // Original inline data was ~6870 lines (272KB)\n  fetch("data.json")\n    .then(function(r) { return r.json(); })\n    .then(function(d) {\n      window.PROJECT_DATA = d;\n      window.dispatchEvent(new Event("data-loaded"));\n    })\n    .catch(function(e) { console.error("Failed to load data.json:", e); });\n</script>',
            inline_script,
        )

    # Write hydrated HTML
    os.makedirs(os.path.dirname(output_html), exist_ok=True)
    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html)

    warning = None
    if not os.path.exists(data_json):
        warning = f"Warning: {data_json} not found. Visualization will be empty."
    return VisualizationResult(output_html, warning)


