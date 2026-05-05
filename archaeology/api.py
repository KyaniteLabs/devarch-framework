"""JSON API for dev-archaeology strategic insights.

Lightweight API that serves strategic analysis data to The-Factory
and other consumers. Stdlib-only — no Flask/FastAPI dependency.

Endpoints:
  GET /api/health              — System status
  GET /api/projects            — All projects with summary metrics
  GET /api/insights/<project>  — All strategic analyses for a project
  GET /api/swot/<project>      — SWOT analysis
  GET /api/wardley/<project>   — Wardley Map
  GET /api/value-chain/<project> — Porter's Value Chain
  GET /api/bridge              — Full bridge file for Factory consumption
"""

import json
import re
import sqlite3
from datetime import datetime
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]  # dev-archaeology/
PROJECTS_DIR = ROOT / "projects"
BRIDGE_PATH = ROOT / "global" / "data" / "factory-bridge.json"

__version__ = "1.0.0"


def _validate_project_name(name):
    """Reject path traversal and invalid characters in project names."""
    if not name or not re.match(r'^[a-zA-Z0-9._-]+$', name):
        return False
    # Double-check no path traversal
    resolved = (PROJECTS_DIR / name).resolve()
    try:
        resolved.relative_to(PROJECTS_DIR.resolve())
    except ValueError:
        return False
    return True


def _json_response(handler, data, status=200):
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Access-Control-Allow-Origin", "*")
    payload = json.dumps(data, indent=2, default=str).encode()
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def _error_response(handler, message, status=404):
    _json_response(handler, {"error": message, "status": status}, status)


def _load_json(path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
        return None


def _discover_projects():
    """Return list of project directories with data."""
    projects = []
    if not PROJECTS_DIR.exists():
        return projects
    for d in sorted(PROJECTS_DIR.iterdir()):
        if not d.is_dir():
            continue
        eras_path = d / "data" / "commit-eras.json"
        if eras_path.exists():
            projects.append(d)
    return projects


def _project_metrics(project_dir):
    """Extract core metrics for a project."""
    name = project_dir.name
    eras_data = _load_json(project_dir / "data" / "commit-eras.json") or {}
    metrics = _load_json(project_dir / "deliverables" / "canonical-metrics.json") or {}
    config = _load_json(project_dir / "project.json") or {}

    return {
        "name": name,
        "description": config.get("description", ""),
        "total_commits": eras_data.get("total_commits", 0),
        "era_count": len(eras_data.get("eras", [])),
        "active_days": metrics.get("active_days", 0),
        "span_days": metrics.get("span_days", 0),
        "contributors": len(eras_data.get("contributors", [])),
        "commit_types": eras_data.get("commit_types", {}),
        "lifespan": eras_data.get("lifespan", ""),
        "repo_url": config.get("repo_url", ""),
    }


def _parse_md_sections(md_path):
    """Parse a markdown file into {heading: [lines]} dict."""
    if not md_path.exists():
        return {}
    text = md_path.read_text(encoding="utf-8")
    sections = {}
    current_heading = "header"
    current_lines = []

    for line in text.splitlines():
        if line.startswith("## "):
            if current_lines:
                sections[current_heading] = "\n".join(current_lines)
            current_heading = line[3:].strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines:
        sections[current_heading] = "\n".join(current_lines)
    return sections


def _parse_list_items(text):
    """Extract numbered or bulleted list items from text."""
    items = []
    for line in text.splitlines():
        line = line.strip()
        if re.match(r"^(\d+\.|[-*])\s+", line):
            clean = re.sub(r"^(\d+\.|[-*])\s+", "", line)
            clean = re.sub(r"\*\*([^*]+)\*\*", r"\1", clean)
            if clean:
                items.append(clean)
    return items


def _extract_score(text, label):
    """Extract a score like 'Margin: 58/100' from text."""
    pattern = rf"{re.escape(label)}[^0-9]*(\d+)/100"
    m = re.search(pattern, text, re.IGNORECASE)
    return int(m.group(1)) if m else None


def _parse_swot(project_dir):
    """Parse SWOT-ANALYSIS.md into structured data."""
    md_path = project_dir / "deliverables" / "strategy" / "SWOT-ANALYSIS.md"
    sections = _parse_md_sections(md_path)
    if not sections:
        return None

    result = {"project": project_dir.name}
    for key in ("Strengths", "Weaknesses", "Opportunities", "Threats"):
        section = sections.get(key, "")
        result[key.lower()] = _parse_list_items(section)

    # Extract matrix counts
    matrix_text = sections.get("header", "")
    for quadrant in ("strengths", "weaknesses", "opportunities", "threats"):
        pattern = rf"{quadrant}.*?(\d+)\s+found"
        m = re.search(pattern, matrix_text, re.IGNORECASE)
        if m:
            result.setdefault(f"{quadrangle if quadrant == 'strengths' else quadrant}_count", int(m.group(1)))

    return result


def _parse_wardley(project_dir):
    """Parse WARDLEY-MAP.md into structured data."""
    md_path = project_dir / "deliverables" / "strategy" / "WARDLEY-MAP.md"
    sections = _parse_md_sections(md_path)
    if not sections:
        return None

    overview = sections.get("Overview", "")
    result = {
        "project": project_dir.name,
        "maturity": None,
        "avg_evolution": None,
    }

    m = re.search(r"Maturity:\s+(\w+)", overview)
    if m:
        result["maturity"] = m.group(1)
    m = re.search(r"avg evolution:\s+([\d.]+)", overview)
    if m:
        result["avg_evolution"] = float(m.group(1))

    # Parse component table
    table_text = sections.get("Component Evolution Table", "")
    components = []
    for line in table_text.splitlines():
        if "|" in line and not line.strip().startswith("|-") and not line.strip().startswith("| Component"):
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if len(cells) >= 3:
                components.append({
                    "component": cells[0],
                    "stage": cells[1],
                    "evidence": cells[2] if len(cells) > 2 else "",
                })
    result["components"] = components

    # Parse recommendations
    recs_text = sections.get("Movement Recommendations", "")
    result["recommendations"] = _parse_list_items(recs_text)

    return result


def _parse_value_chain(project_dir):
    """Parse VALUE-CHAIN-ANALYSIS.md into structured data."""
    md_path = project_dir / "deliverables" / "strategy" / "VALUE-CHAIN-ANALYSIS.md"
    sections = _parse_md_sections(md_path)
    if not sections:
        return None

    summary = sections.get("Value Chain Summary", sections.get("header", ""))
    result = {
        "project": project_dir.name,
        "margin_score": _extract_score(summary, "MARGIN"),
        "primary_activities": {},
        "support_activities": {},
    }

    # Primary activities with scores
    primary = [
        ("Inbound Logistics", "inbound_logistics"),
        ("Operations", "operations"),
        ("Outbound Logistics", "outbound_logistics"),
        ("Marketing & Sales", "marketing_sales"),
        ("Service", "service"),
    ]
    for heading, key in primary:
        section_text = sections.get(heading, "")
        result["primary_activities"][key] = {
            "score": _extract_score(section_text, heading.split()[0]),
            "details": _parse_list_items(section_text)[:5],
        }

    # Support activities
    support = [
        ("Infrastructure", "infrastructure"),
        ("Technology Development", "technology"),
        ("Human Resource Management", "hr"),
        ("Procurement", "procurement"),
    ]
    for heading, key in support:
        section_text = sections.get(heading, "")
        result["support_activities"][key] = {
            "score": _extract_score(section_text, heading.split()[0]),
            "details": _parse_list_items(section_text)[:3],
        }

    # Recommendations
    recs = sections.get("Recommendations", "")
    result["recommendations"] = _parse_list_items(recs)

    return result


def _parse_bcg(project_dir):
    """Parse BCG-MATRIX.md into structured data."""
    md_path = project_dir / "deliverables" / "strategy" / "BCG-MATRIX.md"
    sections = _parse_md_sections(md_path)
    if not sections:
        return None

    overview = sections.get("Overview", "")
    result = {"project": project_dir.name}

    m = re.search(r"Total commits\*\*: (\d+)", overview)
    if m:
        result["total_commits"] = int(m.group(1))
    m = re.search(r"Velocity trend\*\*: (\w+)", overview)
    if m:
        result["velocity_trend"] = m.group(1)

    components = []
    table_text = sections.get("Component Classification", "")
    for line in table_text.splitlines():
        if "|" in line and not line.strip().startswith("|-") and not line.strip().startswith("| Component"):
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if len(cells) >= 4:
                components.append({
                    "component": cells[0],
                    "commits": cells[1],
                    "share": cells[2],
                    "quadrant": cells[3],
                })
    result["components"] = components

    for quadrant_key in ("Stars", "Cash Cows", "Question Marks", "Dogs"):
        section = sections.get(f"{quadrant_key}", "")
        count_match = re.search(rf"\((\d+)\)", sections.get("Quadrant Analysis", ""))
        result[quadrant_key.lower().replace(" ", "_")] = _parse_list_items(section)

    result["recommendations"] = _parse_list_items(sections.get("Strategic Recommendations", ""))
    return result


def _parse_ansoff(project_dir):
    """Parse ANSOFF-MATRIX.md into structured data."""
    md_path = project_dir / "deliverables" / "strategy" / "ANSOFF-MATRIX.md"
    sections = _parse_md_sections(md_path)
    if not sections:
        return None

    overview = sections.get("Overview", "")
    result = {"project": project_dir.name}

    m = re.search(r"Primary strategy\*\*: ([\w\s]+)", overview)
    if m:
        result["primary_strategy"] = m.group(1).strip()
    m = re.search(r"Secondary strategy\*\*: ([\w\s]+)", overview)
    if m:
        result["secondary_strategy"] = m.group(1).strip()

    scores = {}
    table_text = sections.get("Quadrant Scores", "")
    for line in table_text.splitlines():
        if "|" in line and "Strategy" not in line and not line.strip().startswith("|-"):
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if len(cells) >= 2:
                strategy = cells[0]
                score_match = re.match(r"(\d+)/100", cells[1])
                if score_match:
                    scores[strategy] = int(score_match.group(1))
    result["scores"] = scores

    result["recommendations"] = _parse_list_items(sections.get("Recommendations", ""))
    return result


def _parse_blue_ocean(project_dir):
    """Parse BLUE-OCEAN.md into structured data."""
    md_path = project_dir / "deliverables" / "strategy" / "BLUE-OCEAN.md"
    sections = _parse_md_sections(md_path)
    if not sections:
        return None

    overview = sections.get("Overview", "")
    result = {"project": project_dir.name}

    m = re.search(r"Average value score\*\*: ([\d.]+)/10", overview)
    if m:
        result["avg_value_score"] = float(m.group(1))
    m = re.search(r"Critical gaps\*\*: (\d+)", overview)
    if m:
        result["critical_gaps"] = int(m.group(1))

    factors = []
    table_text = sections.get("Strategy Canvas", "")
    for line in table_text.splitlines():
        if "|" in line and "Value Factor" not in line and not line.strip().startswith("|-"):
            cells = [c.strip() for c in line.split("|") if c.strip()]
            if len(cells) >= 2:
                score_match = re.match(r"(\d+)/10", cells[1])
                if score_match:
                    factors.append({"factor": cells[0], "score": int(score_match.group(1))})
    result["factors"] = factors

    for action in ("Eliminate", "Reduce", "Raise", "Create"):
        section_key = f"{action} — What to {'stop doing' if action == 'Eliminate' else 'do less of' if action == 'Reduce' else 'do more of' if action == 'Raise' else 'build that doesn'}"
        section = sections.get(section_key, "")
        if not section:
            section = sections.get(action, "")
        result[action.lower()] = _parse_list_items(section)

    result["recommendations"] = _parse_list_items(sections.get("Recommendations", ""))
    return result


def _get_pipeline_status(project_dir):
    """Get latest pipeline run status from archaeology.db."""
    db_path = project_dir / "data" / "archaeology.db"
    if not db_path.exists():
        return None
    try:
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT run_timestamp, status FROM pipeline_runs "
                "ORDER BY run_timestamp DESC LIMIT 1"
            ).fetchone()
            if row:
                return {"last_run": row["run_timestamp"], "status": row["status"]}
    except sqlite3.OperationalError:
        pass
    return None


def _compute_health_score(metrics, swot, wardley, value_chain):
    """Compute a 0-100 health score from available data."""
    score = 50  # baseline

    # Positive signals
    ct = metrics.get("commit_types", {})
    if ct.get("test", 0) > 0:
        score += 10
    if ct.get("ci", 0) > 0:
        score += 10
    if ct.get("docs", 0) > 5:
        score += 5
    if metrics.get("era_count", 0) >= 3:
        score += 5
    if metrics.get("active_days", 0) > 10:
        score += 5

    # Negative signals
    if ct.get("test", 0) == 0:
        score -= 10
    if ct.get("ci", 0) == 0:
        score -= 10

    # SWOT balance (more strengths than weaknesses = healthy)
    if swot:
        s = len(swot.get("strengths", []))
        w = len(swot.get("weaknesses", []))
        if s > w:
            score += 5
        elif w > s:
            score -= 5

    # Value chain margin
    if value_chain and value_chain.get("margin_score"):
        margin = value_chain["margin_score"]
        if margin > 60:
            score += 5
        elif margin < 30:
            score -= 5

    return max(0, min(100, score))


# ── Endpoint handlers ──────────────────────────────────────────


def handle_health(handler):
    """GET /api/health"""
    projects = _discover_projects()
    _json_response(handler, {
        "status": "ok",
        "version": __version__,
        "projects": len(projects),
        "bridge_available": BRIDGE_PATH.exists(),
    })


def handle_projects(handler):
    """GET /api/projects"""
    projects = []
    for pdir in _discover_projects():
        metrics = _project_metrics(pdir)
        pipeline = _get_pipeline_status(pdir)
        if pipeline:
            metrics["last_pipeline"] = pipeline
        projects.append(metrics)
    _json_response(handler, {"projects": projects, "count": len(projects)})


def handle_insights(handler, project_name):
    """GET /api/insights/<project>"""
    pdir = PROJECTS_DIR / project_name
    if not pdir.exists():
        return _error_response(handler, f"Project '{project_name}' not found")

    metrics = _project_metrics(pdir)
    swot = _parse_swot(pdir)
    wardley = _parse_wardley(pdir)
    value_chain = _parse_value_chain(pdir)
    bcg = _parse_bcg(pdir)
    ansoff = _parse_ansoff(pdir)
    blue_ocean = _parse_blue_ocean(pdir)
    pipeline = _get_pipeline_status(pdir)
    health = _compute_health_score(metrics, swot, wardley, value_chain)

    _json_response(handler, {
        "project": project_name,
        "health_score": health,
        "metrics": metrics,
        "swot": swot,
        "wardley": wardley,
        "value_chain": value_chain,
        "bcg": bcg,
        "ansoff": ansoff,
        "blue_ocean": blue_ocean,
        "pipeline": pipeline,
    })


def handle_swot(handler, project_name):
    """GET /api/swot/<project>"""
    pdir = PROJECTS_DIR / project_name
    if not pdir.exists():
        return _error_response(handler, f"Project '{project_name}' not found")
    data = _parse_swot(pdir)
    if not data:
        return _error_response(handler, f"SWOT analysis not found for '{project_name}'")
    _json_response(handler, data)


def handle_wardley(handler, project_name):
    """GET /api/wardley/<project>"""
    pdir = PROJECTS_DIR / project_name
    if not pdir.exists():
        return _error_response(handler, f"Project '{project_name}' not found")
    data = _parse_wardley(pdir)
    if not data:
        return _error_response(handler, f"Wardley Map not found for '{project_name}'")
    _json_response(handler, data)


def handle_value_chain(handler, project_name):
    """GET /api/value-chain/<project>"""
    pdir = PROJECTS_DIR / project_name
    if not pdir.exists():
        return _error_response(handler, f"Project '{project_name}' not found")
    data = _parse_value_chain(pdir)
    if not data:
        return _error_response(handler, f"Value Chain not found for '{project_name}'")
    _json_response(handler, data)


def handle_bcg(handler, project_name):
    """GET /api/bcg/<project>"""
    pdir = PROJECTS_DIR / project_name
    if not pdir.exists():
        return _error_response(handler, f"Project '{project_name}' not found")
    data = _parse_bcg(pdir)
    if not data:
        return _error_response(handler, f"BCG Matrix not found for '{project_name}'")
    _json_response(handler, data)


def handle_ansoff(handler, project_name):
    """GET /api/ansoff/<project>"""
    pdir = PROJECTS_DIR / project_name
    if not pdir.exists():
        return _error_response(handler, f"Project '{project_name}' not found")
    data = _parse_ansoff(pdir)
    if not data:
        return _error_response(handler, f"Ansoff Matrix not found for '{project_name}'")
    _json_response(handler, data)


def handle_blue_ocean(handler, project_name):
    """GET /api/blue-ocean/<project>"""
    pdir = PROJECTS_DIR / project_name
    if not pdir.exists():
        return _error_response(handler, f"Project '{project_name}' not found")
    data = _parse_blue_ocean(pdir)
    if not data:
        return _error_response(handler, f"Blue Ocean analysis not found for '{project_name}'")
    _json_response(handler, data)


def handle_bridge(handler):
    """GET /api/bridge — Serve pre-generated bridge file or generate on the fly."""
    if BRIDGE_PATH.exists():
        data = _load_json(BRIDGE_PATH)
        if data:
            return _json_response(handler, data)

    # Fallback: generate on the fly
    bridge = _generate_bridge()
    _json_response(handler, bridge)


def handle_health_trend(handler, project_name):
    """GET /api/health-trend/<project> — Pipeline history from SQLite."""
    db_path = PROJECTS_DIR / project_name / "data" / "archaeology.db"
    if not db_path.exists():
        return _error_response(handler, f"No database for '{project_name}'")
    try:
        with sqlite3.connect(str(db_path)) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT r.run_timestamp, r.status, pr.issues_count, pr.fixes_applied "
                "FROM pipeline_runs r "
                "JOIN pipeline_repo_results pr ON r.id = pr.run_id "
                "WHERE pr.repo_name LIKE '%' || ? || '%' "
                "ORDER BY r.run_timestamp DESC LIMIT 50",
                (project_name,),
            ).fetchall()
            trend = [dict(r) for r in rows]
        _json_response(handler, {"project": project_name, "trend": trend})
    except sqlite3.OperationalError:
        _json_response(handler, {"project": project_name, "trend": []})


# ── Bridge generation ──────────────────────────────────────────


def _generate_bridge():
    """Generate the bridge data structure."""
    projects_data = {}
    for pdir in _discover_projects():
        metrics = _project_metrics(pdir)
        swot = _parse_swot(pdir)
        wardley = _parse_wardley(pdir)
        value_chain = _parse_value_chain(pdir)
        bcg = _parse_bcg(pdir)
        ansoff = _parse_ansoff(pdir)
        blue_ocean = _parse_blue_ocean(pdir)
        pipeline = _get_pipeline_status(pdir)
        health = _compute_health_score(metrics, swot, wardley, value_chain)

        projects_data[metrics["name"]] = {
            "health_score": health,
            "total_commits": metrics["total_commits"],
            "active_days": metrics["active_days"],
            "era_count": metrics["era_count"],
            "swot_summary": {
                "strengths": len(swot.get("strengths", [])) if swot else 0,
                "weaknesses": len(swot.get("weaknesses", [])) if swot else 0,
                "opportunities": len(swot.get("opportunities", [])) if swot else 0,
                "threats": len(swot.get("threats", [])) if swot else 0,
            } if swot else None,
            "wardley_maturity": wardley.get("maturity") if wardley else None,
            "value_chain_margin": value_chain.get("margin_score") if value_chain else None,
            "bcg_velocity_trend": bcg.get("velocity_trend") if bcg else None,
            "ansoff_primary": ansoff.get("primary_strategy") if ansoff else None,
            "blue_ocean_avg_score": blue_ocean.get("avg_value_score") if blue_ocean else None,
            "last_pipeline_status": pipeline.get("status") if pipeline else None,
            "recommendations": (
                (wardley.get("recommendations", []) if wardley else [])
                + (value_chain.get("recommendations", []) if value_chain else [])
            )[:5],
        }

    return {
        "generated_at": datetime.now().isoformat(),
        "version": __version__,
        "projects": projects_data,
        "cross_repo": {
            "total_repos": len(projects_data),
            "total_commits": sum(p["total_commits"] for p in projects_data.values()),
            "frameworks_available": ["swot", "wardley", "value-chain", "bcg", "ansoff", "blue-ocean"],
            "opportunity_features": [
                "learning-velocity", "frustration-to-automation", "knowledge-gap",
                "token-efficiency", "session-quality", "ai-agent-mastery",
                "creative-dna", "neurodivergent-profile", "model-selection-advisor",
                "before-after-snapshot", "cross-repo-transfer", "youtube-learning-graph",
                "architecture-timelapse", "commit-cognitive-load",
            ],
        },
    }


def generate_bridge_file():
    """Generate and write bridge file to disk. Called from pipeline."""
    bridge = _generate_bridge()
    BRIDGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BRIDGE_PATH.write_text(json.dumps(bridge, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"Bridge generated: {len(bridge['projects'])} projects → {BRIDGE_PATH}")
    return len(bridge["projects"])


# ── Opportunity endpoints ────────────────────────────────────────

OPPORTUNITY_FEATURES = [
    "learning-velocity",
    "frustration-to-automation",
    "knowledge-gap",
    "token-efficiency",
    "session-quality",
    "ai-agent-mastery",
    "creative-dna",
    "neurodivergent-profile",
    "model-selection-advisor",
    "before-after-snapshot",
    "cross-repo-transfer",
    "youtube-learning-graph",
    "architecture-timelapse",
    "commit-cognitive-load",
]


def _load_opportunity(project_name, feature):
    """Load a single opportunity analysis JSON."""
    path = PROJECTS_DIR / project_name / "deliverables" / "opportunity" / f"opportunity-{feature}.json"
    return _load_json(path)


def handle_opportunity_feature(handler, project_name, feature):
    """GET /api/opportunity/<feature>/<project>"""
    if feature not in OPPORTUNITY_FEATURES:
        return _error_response(handler, f"Unknown opportunity feature: {feature}", 404)
    pdir = PROJECTS_DIR / project_name
    if not pdir.exists():
        return _error_response(handler, f"Project '{project_name}' not found")
    data = _load_opportunity(project_name, feature)
    if not data:
        return _error_response(handler, f"Opportunity '{feature}' not generated for '{project_name}'", 404)
    _json_response(handler, data)


def handle_opportunity_all(handler, project_name):
    """GET /api/opportunity/all/<project> — All 14 opportunity analyses."""
    pdir = PROJECTS_DIR / project_name
    if not pdir.exists():
        return _error_response(handler, f"Project '{project_name}' not found")
    results = {}
    for feature in OPPORTUNITY_FEATURES:
        data = _load_opportunity(project_name, feature)
        results[feature] = data
    _json_response(handler, {
        "project": project_name,
        "features": OPPORTUNITY_FEATURES,
        "data": results,
        "generated_at": datetime.now().isoformat(),
    })


def handle_opportunity_index(handler, project_name):
    """GET /api/opportunity/<project> — Index of available features with status."""
    pdir = PROJECTS_DIR / project_name
    if not pdir.exists():
        return _error_response(handler, f"Project '{project_name}' not found")
    available = []
    for feature in OPPORTUNITY_FEATURES:
        data = _load_opportunity(project_name, feature)
        available.append({
            "feature": feature,
            "available": data is not None,
            "analysis_type": data.get("analysis_type") if data else None,
        })
    _json_response(handler, {
        "project": project_name,
        "total_features": len(OPPORTUNITY_FEATURES),
        "available_count": sum(1 for f in available if f["available"]),
        "features": available,
    })


# ── Router ─────────────────────────────────────────────────────


# Route table: (pattern, handler, needs_project)
ROUTES = [
    (r"^/api/health$", handle_health, False),
    (r"^/api/projects$", handle_projects, False),
    (r"^/api/bridge$", handle_bridge, False),
    (r"^/api/insights/(.+)$", handle_insights, True),
    (r"^/api/swot/(.+)$", handle_swot, True),
    (r"^/api/wardley/(.+)$", handle_wardley, True),
    (r"^/api/value-chain/(.+)$", handle_value_chain, True),
    (r"^/api/bcg/(.+)$", handle_bcg, True),
    (r"^/api/ansoff/(.+)$", handle_ansoff, True),
    (r"^/api/blue-ocean/(.+)$", handle_blue_ocean, True),
    (r"^/api/health-trend/(.+)$", handle_health_trend, True),
    # Opportunity endpoints (14 features) — specific routes FIRST, generic LAST
    (r"^/api/opportunity/all/(.+)$", lambda h, p: handle_opportunity_all(h, p), True),
    (r"^/api/opportunity/learning-velocity/(.+)$", lambda h, p: handle_opportunity_feature(h, p, "learning-velocity"), True),
    (r"^/api/opportunity/frustration-to-automation/(.+)$", lambda h, p: handle_opportunity_feature(h, p, "frustration-to-automation"), True),
    (r"^/api/opportunity/knowledge-gap/(.+)$", lambda h, p: handle_opportunity_feature(h, p, "knowledge-gap"), True),
    (r"^/api/opportunity/token-efficiency/(.+)$", lambda h, p: handle_opportunity_feature(h, p, "token-efficiency"), True),
    (r"^/api/opportunity/session-quality/(.+)$", lambda h, p: handle_opportunity_feature(h, p, "session-quality"), True),
    (r"^/api/opportunity/ai-agent-mastery/(.+)$", lambda h, p: handle_opportunity_feature(h, p, "ai-agent-mastery"), True),
    (r"^/api/opportunity/creative-dna/(.+)$", lambda h, p: handle_opportunity_feature(h, p, "creative-dna"), True),
    (r"^/api/opportunity/neurodivergent-profile/(.+)$", lambda h, p: handle_opportunity_feature(h, p, "neurodivergent-profile"), True),
    (r"^/api/opportunity/model-selection-advisor/(.+)$", lambda h, p: handle_opportunity_feature(h, p, "model-selection-advisor"), True),
    (r"^/api/opportunity/before-after-snapshot/(.+)$", lambda h, p: handle_opportunity_feature(h, p, "before-after-snapshot"), True),
    (r"^/api/opportunity/cross-repo-transfer/(.+)$", lambda h, p: handle_opportunity_feature(h, p, "cross-repo-transfer"), True),
    (r"^/api/opportunity/youtube-learning-graph/(.+)$", lambda h, p: handle_opportunity_feature(h, p, "youtube-learning-graph"), True),
    (r"^/api/opportunity/architecture-timelapse/(.+)$", lambda h, p: handle_opportunity_feature(h, p, "architecture-timelapse"), True),
    (r"^/api/opportunity/commit-cognitive-load/(.+)$", lambda h, p: handle_opportunity_feature(h, p, "commit-cognitive-load"), True),
    (r"^/api/opportunity/(.+)$", lambda h, p: handle_opportunity_index(h, p), True),
]


def route(handler):
    """Route an incoming /api/* request to the appropriate handler."""
    if handler.command != "GET":
        return _error_response(handler, "Method not allowed", 405)

    path = urlparse(handler.path).path

    for pattern, handler_func, needs_project in ROUTES:
        m = re.match(pattern, path)
        if m:
            if needs_project:
                project_name = m.group(1)
                if not _validate_project_name(project_name):
                    return _error_response(handler, "Invalid project name", 400)
                handler_func(handler, project_name)
            else:
                handler_func(handler)
            return

    _error_response(handler, f"Unknown endpoint: {path}", 404)
