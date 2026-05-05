"""Report export utilities for dev-archaeology."""

from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path
from typing import Any


ANALYSIS_FILES = [
    "analysis-sdlc-gap-finder.json",
    "analysis-ml-pattern-mapper.json",
    "analysis-agentic-workflow.json",
    "analysis-formal-terms-mapper.json",
    "analysis-source-archaeologist.json",
    "analysis-youtube-correlator.json",
]


def _load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _bullet(value: str) -> str:
    return f"- {value}\n"


def _fmt_count(value: Any) -> str:
    if isinstance(value, int):
        return f"{value:,}"
    return str(value) if value is not None else "unknown"


def export_markdown_report(project_name: str, project_root: str | Path, output_path: str | Path | None = None) -> Path:
    """Export a concise Markdown report from canonical metrics + analysis JSON."""
    project_root = Path(project_root)
    deliverables = project_root / "deliverables"
    analysis_dir = deliverables / "analysis"
    data_dir = project_root / "data"
    project = _load_json(project_root / "project.json") or {}
    canonical = _load_json(deliverables / "canonical-metrics.json") or {}
    eras = _load_json(data_dir / "commit-eras.json") or {}
    # Look for analysis files in analysis/ subdirectory first, then fall back to deliverables root
    analysis_search = [analysis_dir, deliverables]
    analyses = {}
    for name in ANALYSIS_FILES:
        for search_dir in analysis_search:
            loaded = _load_json(search_dir / name)
            if loaded:
                analyses[name.replace("analysis-", "").replace(".json", "")] = loaded
                break

    title = project.get("visualization", {}).get("title") or project.get("name") or project_name
    out = []
    out.append(f"# {title} Archaeology Report\n\n")
    out.append(f"Generated: {datetime.now().isoformat()}\n\n")
    out.append("## Executive Summary\n\n")
    out.append(
        f"This report summarizes the `{project_name}` development archaeology from canonical project metrics, era data, and automated analysis vectors.\n\n"
    )

    out.append("## Canonical Metrics\n\n")
    metric_rows = [
        ("Total commits", canonical.get("total_commits") or eras.get("total_commits")),
        ("Span days", canonical.get("span_days")),
        ("Active days", canonical.get("active_days")),
        ("Sessions", canonical.get("session_count")),
        ("Human messages", canonical.get("human_messages")),
        ("Peak day", canonical.get("peak_day")),
        ("Peak day commits", canonical.get("peak_day_commits")),
    ]
    for label, value in metric_rows:
        out.append(_bullet(f"**{label}:** {_fmt_count(value)}"))
    out.append("\n")

    era_list = eras.get("eras") if isinstance(eras, dict) else []
    if era_list:
        out.append("## Development Eras\n\n")
        for era in era_list:
            out.append(_bullet(f"**Era {era.get('id')}: {era.get('name')}** — {era.get('dates', 'unknown dates')}; {era.get('commits', 'unknown')} commits. {era.get('description') or era.get('narrative_arc') or ''}"))
        out.append("\n")

    sdlc = analyses.get("sdlc-gap-finder") or {}
    gaps = sdlc.get("gaps") or []
    if gaps:
        out.append("## SDLC / Process Gaps\n\n")
        for gap in gaps[:10]:
            out.append(_bullet(f"**{gap.get('practice')}** — {gap.get('status')} ({gap.get('severity')}). {gap.get('recommendation')}"))
        out.append("\n")

    ml = analyses.get("ml-pattern-mapper") or {}
    mappings = ml.get("mappings") or []
    if mappings:
        out.append("## Formal ML / Architecture Patterns\n\n")
        for mapping in mappings[:10]:
            out.append(_bullet(f"**{mapping.get('intuitive_name')}** → {mapping.get('formal_term')} (confidence: {mapping.get('confidence')})"))
        out.append("\n")

    formal = analyses.get("formal-terms-mapper") or {}
    terms = formal.get("term_dictionary") or []
    if terms:
        out.append("## Vocabulary Translation\n\n")
        for term in terms[:10]:
            out.append(_bullet(f"**{term.get('code_name')}** → {term.get('formal_term')} ({term.get('similarity_score')})"))
        out.append("\n")

    source = analyses.get("source-archaeologist") or {}
    improvements = source.get("improvements") or []
    if improvements:
        out.append("## Remediation Priorities\n\n")
        for item in improvements:
            out.append(_bullet(f"P{item.get('rank')}: **{item.get('title')}** — effort {item.get('effort')}, impact {item.get('impact')}"))
        out.append("\n")

    youtube = analyses.get("youtube-correlator") or {}
    yt_summary = youtube.get("summary") or {}
    out.append("## Behavioral / External Data\n\n")
    out.append(_bullet(f"YouTube/behavioral data available: {bool(yt_summary.get('data_available'))}"))
    out.append(_bullet(f"Correlations found: {_fmt_count(yt_summary.get('correlation_count'))}"))
    out.append(_bullet(f"Creator count: {_fmt_count(yt_summary.get('creator_count'))}"))
    out.append("\n")

    out.append("## Provenance\n\n")
    out.append(_bullet(f"Source scope: {canonical.get('source_scope', 'project data')}"))
    out.append(_bullet("Generated from automated `archaeology analyze` JSON outputs."))
    out.append(_bullet("Run `archaeology audit <project> --fail-on HIGH` before publishing."))

    if output_path is None:
        output_path = deliverables / "ARCHAEOLOGY-REPORT.md"
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(out), encoding="utf-8")
    return output


def _markdown_to_html(markdown: str, title: str) -> str:
    """Render the report's constrained Markdown subset to standalone HTML."""
    body: list[str] = []
    in_list = False

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            body.append("</ul>")
            in_list = False

    for raw_line in markdown.splitlines():
        line = raw_line.rstrip()
        if not line:
            close_list()
            continue
        if line.startswith("# "):
            close_list()
            body.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            close_list()
            body.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("- "):
            if not in_list:
                body.append("<ul>")
                in_list = True
            item = html.escape(line[2:]).replace("**", "")
            body.append(f"<li>{item}</li>")
        else:
            close_list()
            text = html.escape(line).replace("`", "")
            body.append(f"<p>{text}</p>")
    close_list()
    body_html = "\n    ".join(body)
    escaped_title = html.escape(title)
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>{escaped_title}</title>
  <style>
    :root {{ color-scheme: dark; --bg:#070a0f; --panel:#0f1623; --text:#edf2f7; --muted:#97a6ba; --accent:#74c0fc; --border:#233044; }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: radial-gradient(circle at top left, #102036, var(--bg) 42rem); color:var(--text); line-height:1.65; }}
    main {{ width:min(980px, calc(100% - 32px)); margin:0 auto; padding:56px 0 80px; }}
    h1 {{ font-size: clamp(2.2rem, 6vw, 4.5rem); line-height:0.95; letter-spacing:-0.06em; margin:0 0 1rem; }}
    h2 {{ margin-top:2.5rem; color:var(--accent); border-top:1px solid var(--border); padding-top:1.5rem; }}
    p, li {{ color:var(--muted); }}
    ul {{ padding:1rem 1.25rem; background:rgba(15,22,35,0.72); border:1px solid var(--border); border-radius:16px; }}
    li + li {{ margin-top:0.55rem; }}
    .badge {{ display:inline-block; margin-bottom:1rem; padding:0.35rem 0.7rem; border:1px solid var(--border); border-radius:999px; color:var(--accent); background:rgba(116,192,252,0.08); font-size:0.82rem; }}
  </style>
</head>
<body>
  <main>
    <div class=\"badge\">Generated by Dev-Archaeology</div>
    {body_html}
  </main>
</body>
</html>
"""


def export_html_report(project_name: str, project_root: str | Path, output_path: str | Path | None = None) -> Path:
    """Export a standalone HTML report from the Markdown report content."""
    project_root = Path(project_root)
    deliverables = project_root / "deliverables"
    markdown_path = export_markdown_report(project_name, project_root)
    markdown = markdown_path.read_text(encoding="utf-8")
    project = _load_json(project_root / "project.json") or {}
    title = project.get("visualization", {}).get("title") or project.get("name") or project_name
    if output_path is None:
        output_path = deliverables / "visuals" / "report.html"
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_markdown_to_html(markdown, f"{title} Archaeology Report"), encoding="utf-8")
    return output


def export_report(project_name: str, project_root: str | Path, output_path: str | Path | None = None, fmt: str = "markdown") -> Path:
    """Export a report in markdown or html format."""
    if fmt in {"markdown", "md"}:
        return export_markdown_report(project_name, project_root, output_path=output_path)
    if fmt == "html":
        return export_html_report(project_name, project_root, output_path=output_path)
    raise ValueError(f"Unsupported report format: {fmt}")


def export_public_case_study(root: str | Path = ".", output_dir: str | Path = "public-case-study", project_name: str = "demo-archaeology", force: bool = True) -> Path:
    """Generate a sanitized public case-study showroom from invented demo data."""
    from .analysis_runner import run_analysis_vectors
    from .db.builder import build_db
    from .demo import create_demo_project

    root = Path(root)
    output = root / output_dir
    work_project = create_demo_project(root, project_name=project_name, force=force)

    # Build database directly without mutating sys.argv
    build_db(work_project, verbose=False)

    run_analysis_vectors(project_name, vectors=None)
    md_report = export_markdown_report(project_name, work_project)
    html_report = export_html_report(project_name, work_project)

    output.mkdir(parents=True, exist_ok=True)
    data_out = output / "data"
    data_out.mkdir(parents=True, exist_ok=True)
    (output / "ARCHAEOLOGY-REPORT.md").write_text(md_report.read_text(encoding="utf-8"), encoding="utf-8")
    (output / "index.html").write_text(html_report.read_text(encoding="utf-8"), encoding="utf-8")
    for src, dst in [
        (work_project / "deliverables" / "canonical-metrics.json", data_out / "canonical-metrics.json"),
        (work_project / "data" / "commit-eras.json", data_out / "commit-eras.json"),
        (work_project / "data" / "github-commits.csv", data_out / "github-commits.csv"),
    ]:
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    (output / "README.md").write_text(
        "# Dev-Archaeology Public Case Study\n\n"
        "This is a sanitized, publishable demo generated from invented fixture data. "
        "It exists to show what Dev-Archaeology produces without exposing Liminal's private evidence archive.\n\n"
        "## Open the case study\n\n"
        "```text\npublic-case-study/index.html\n```\n\n"
        "## Regenerate locally\n\n"
        "```bash\narchaeology public-case-study --output public-case-study\n```\n\n"
        "## Data safety\n\n"
        "The files in `public-case-study/data/` are invented fixture data only:\n\n"
        "- no raw Liminal sessions\n"
        "- no YouTube export\n"
        "- no resume/profile data\n"
        "- no personal telemetry\n",
        encoding="utf-8",
    )
    return output
