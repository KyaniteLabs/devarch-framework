"""Master dashboard generator for dev-archaeology.

Generates the top-level index.html that shows all projects as cards
with links to their individual visualizations. Served by `archaeology serve`
or deployed as a static site.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from archaeology.visualization.design_system import (
    head_bundle, body_end_bundle, THEME_SWITCHER_HTML, THEME_SWITCHER_CSS
)

# Deliverable categories with display metadata and colors
# Colors reference design system tokens for theme consistency
CATEGORIES: dict[str, dict[str, str]] = {
    "visuals": {"icon": "&#128202;", "label": "Visualizations", "color": "var(--success)"},
    "analysis": {"icon": "&#128270;", "label": "Analysis", "color": "var(--secondary)"},
    "reports": {"icon": "&#128196;", "label": "Reports", "color": "var(--accent)"},
    "strategy": {"icon": "&#127919;", "label": "Strategy", "color": "var(--warning)"},
    "planning": {"icon": "&#128203;", "label": "Planning", "color": "var(--success)"},
    "learning": {"icon": "&#128218;", "label": "Learning", "color": "#ec4899"},
    "content": {"icon": "&#9997;", "label": "Content", "color": "var(--warning)"},
    "video": {"icon": "&#127909;", "label": "Video", "color": "var(--danger)"},
    "opportunity": {"icon": "&#128161;", "label": "Opportunity", "color": "var(--accent)"},
}


def _discover_all_deliverables(deliverables_dir: Path, project_name: str) -> dict[str, list[dict[str, str]]]:
    """Scan all deliverable subdirectories and categorize files."""
    result: dict[str, list[dict[str, str]]] = {}
    for cat_name in CATEGORIES:
        cat_dir = deliverables_dir / cat_name
        if not cat_dir.exists():
            continue
        files = []
        for f in sorted(cat_dir.iterdir()):
            if f.suffix not in (".html", ".md", ".json"):
                continue
            display = f.stem.replace("-", " ").replace("_", " ").title()
            href = f"{project_name}/{cat_name}/{f.name}"
            files.append({"name": display, "href": href, "ext": f.suffix, "filename": f.name})
        if files:
            result[cat_name] = files
    return result


def discover_projects(projects_dir: Path) -> list[dict[str, Any]]:
    """Scan projects/ directory and collect metadata for each project.

    Returns list of project dicts sorted by name.
    """
    projects = []
    if not projects_dir.exists():
        return projects

    for project_dir in sorted(projects_dir.iterdir()):
        if not project_dir.is_dir():
            continue
        if project_dir.name.startswith((".", "_")):
            continue

        deliverables_dir = project_dir / "deliverables"
        data_dir = project_dir / "data"
        if not deliverables_dir.exists() and not data_dir.exists():
            continue

        # Load project metadata from data.json or canonical-metrics.json
        meta = _load_project_meta(deliverables_dir, data_dir)

        # Discover HTML visualizations (backward compat)
        visuals = _discover_visuals(deliverables_dir, project_dir.name)

        # Discover all categorized deliverables
        deliverables = _discover_all_deliverables(deliverables_dir, project_dir.name)
        total_deliverables = sum(len(v) for v in deliverables.values())

        projects.append({
            "name": project_dir.name,
            "slug": project_dir.name,
            "meta": meta,
            "visuals": visuals,
            "deliverables": deliverables,
            "total_deliverables": total_deliverables,
            "has_data": (deliverables_dir / "data.json").exists() or (data_dir).exists(),
        })

    return projects


def _load_project_meta(deliverables_dir: Path, data_dir: Path) -> dict[str, Any]:
    """Load project metadata from available JSON files."""
    meta: dict[str, Any] = {}

    # Try data.json first (most comprehensive)
    data_json = deliverables_dir / "data.json"
    if data_json.exists():
        try:
            data = json.loads(data_json.read_text(encoding="utf-8"))
            summary = data.get("summary", {})
            meta["commits"] = summary.get("total_commits", 0)
            meta["active_days"] = summary.get("active_days", 0)
            meta["span_days"] = summary.get("span_days", 0)
            meta["era_count"] = len(data.get("eras", []))
            meta["authors"] = list(data.get("authors", {}).keys()) if isinstance(data.get("authors"), dict) else []
        except (json.JSONDecodeError, OSError):
            pass

    # Try canonical-metrics.json
    canonical = deliverables_dir / "canonical-metrics.json"
    if canonical.exists() and not meta.get("commits"):
        try:
            cm = json.loads(canonical.read_text(encoding="utf-8"))
            meta["commits"] = cm.get("total_commits", 0)
            meta["active_days"] = cm.get("active_days", 0)
            meta["span_days"] = cm.get("span_days", 0)
            meta["era_count"] = cm.get("era_count", 0)
        except (json.JSONDecodeError, OSError):
            pass

    # Fallback: compute metrics from CSV
    if not meta.get("commits"):
        meta.update(_load_git_metrics(data_dir))

    return meta


def _load_git_metrics(data_dir: Path) -> dict[str, Any]:
    """Fallback: compute basic metrics from github-commits.csv."""
    import csv as _csv

    csv_path = data_dir / "github-commits.csv"
    if not csv_path.exists():
        return {}
    commits = 0
    dates: set[str] = set()
    try:
        with open(csv_path, encoding="utf-8") as f:
            reader = _csv.DictReader(f)
            for row in reader:
                commits += 1
                d = row.get("date", "")[:10]
                if d:
                    dates.add(d)
    except OSError:
        return {}
    if commits == 0:
        return {}
    sorted_dates = sorted(dates)
    span = 0
    if len(sorted_dates) >= 2:
        from datetime import date as _date
        try:
            d0 = _date.fromisoformat(sorted_dates[0])
            d1 = _date.fromisoformat(sorted_dates[-1])
            span = (d1 - d0).days
        except ValueError:
            span = 0
    return {
        "commits": commits,
        "active_days": len(dates),
        "span_days": span or 1,
        "era_count": 0,
        "first_commit": sorted_dates[0],
        "last_commit": sorted_dates[-1],
    }


def _discover_visuals(deliverables_dir: Path, project_name: str) -> list[dict[str, str]]:
    """Find HTML visualization files for a project."""
    visuals = []
    seen = set()

    # Check visuals/ subdirectory (new structure)
    visuals_dir = deliverables_dir / "visuals"
    search_dirs = [visuals_dir, deliverables_dir] if visuals_dir.exists() else [deliverables_dir]

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for html_file in sorted(search_dir.glob("*.html")):
            name = html_file.stem
            if name in seen or name == "index":
                continue
            seen.add(name)

            display = name.replace("-", " ").replace("_", " ").title()
            if display == "Archaeology":
                display = "Dashboard"
                order = 0
            elif display == "Playbook":
                order = 1
            elif "Agent" in display or "Benchmark" in display:
                display = "Agents"
                order = 2
            elif display == "Report":
                order = 3
            else:
                order = 99

            # Relative href from master dashboard (flat — serve symlinks into project dir)
            href = f"{project_name}/{html_file.name}"

            visuals.append({"name": display, "href": href, "order": order})

    visuals.sort(key=lambda v: v["order"])
    return visuals


def _pluralize(n: int, singular: str, plural: str = "") -> str:
    """Return singular or plural form based on count."""
    if plural == "":
        plural = singular + "s"
    return singular if n == 1 else plural


def _format_stat(value: Any, singular: str, plural: str = "") -> str:
    """Format a stat value, using dash for zero/unknown and correct pluralization."""
    if value == 0 or value == "?" or value is None:
        return "—"
    n = int(value) if isinstance(value, (int, float)) else 0
    return f"{n:,} {_pluralize(n, singular, plural)}"


def _project_description(name: str, meta: dict) -> str:
    """Generate a project description from metadata."""
    commits = meta.get("commits", 0)
    eras = meta.get("era_count", 0)
    days = meta.get("active_days", 0)
    if not commits:
        return "Infrastructure project supporting the archaeology pipeline"
    parts = []
    if eras and eras > 1:
        parts.append(f"{eras} distinct development eras")
    elif not eras:
        pass  # Skip era mention for pipeline/infra projects
    if days:
        parts.append(f"{days} active days of development")
    if parts:
        return f"{commits:,} commits across " + " and ".join(parts)
    return f"{commits:,} commits of development history"


def generate_master_dashboard(projects: list[dict[str, Any]], api_section_html: str = "", api_repos: list[dict[str, Any]] | None = None) -> str:
    """Generate the master dashboard HTML."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    api_repos = api_repos or []

    api_commits = sum(r["commits"] for r in api_repos if isinstance(r["commits"], int))
    if api_repos:
        print(f"  API repos: {len(api_repos)} repos, {api_commits:,} commits")
    else:
        print(f"  WARNING: No API repos loaded")

    # Sort projects by commit count (descending) — richest first
    def _proj_commits(p: dict) -> int:
        c = p["meta"].get("commits", 0)
        return c if isinstance(c, int) else 0
    projects_sorted = sorted(projects, key=_proj_commits, reverse=True)

    # Separate featured (top project) from the rest
    featured = projects_sorted[0] if projects_sorted else None
    rest_projects = projects_sorted[1:] if len(projects_sorted) > 1 else []

    # ── Featured card ──
    featured_html = ""
    if featured:
        fm = featured["meta"]
        fc = fm.get("commits", "—")
        fc_fmt = f"{fc:,}" if isinstance(fc, int) else str(fc)
        fe = fm.get("era_count", 0)
        fad = fm.get("active_days", "—")
        fd = featured.get("total_deliverables", 0)
        fviz = ""
        for viz in featured["visuals"]:
            fviz += f'<a href="{viz["href"]}" class="fviz-link">{viz["name"]}</a>\n            '

        # Category pills
        cat_pills = ""
        for cat_name, cat_meta in CATEGORIES.items():
            count = len(featured.get("deliverables", {}).get(cat_name, []))
            if count:
                color = cat_meta["color"]
                cat_pills += f'<span class="cat-pill" style="background:{color}22;color:{color};border:1px solid {color}44">{cat_meta["label"]} {count}</span>\n'

        featured_html = f"""
<div class="section-wrap">
  <a href="{featured['name']}/" class="featured-card">
    <div class="featured-main">
      <span class="featured-badge">Featured Project</span>
      <h2 class="featured-title">{featured['name'].upper()}</h2>
      <p class="featured-desc">{_project_description(featured['name'], fm)}</p>
      <div class="featured-stats">
        <div class="fstat"><span class="fstat-val">{fc_fmt}</span><span class="fstat-lbl">{_pluralize(fc if isinstance(fc, int) else 0, 'commit')}</span></div>
        <div class="fstat"><span class="fstat-val">{fe if fe else '—'}</span><span class="fstat-lbl">{_pluralize(fe, 'era')}</span></div>
        <div class="fstat"><span class="fstat-val">{fad}</span><span class="fstat-lbl">{_pluralize(fad if isinstance(fad, int) else 0, 'active day')}</span></div>
        <div class="fstat"><span class="fstat-val">{fd}</span><span class="fstat-lbl">{_pluralize(fd, 'deliverable')}</span></div>
      </div>
      <div class="cat-pills">{cat_pills}</div>
    </div>
    <div class="featured-links" onclick="event.stopPropagation()">
      {fviz}
    </div>
  </a>
</div>"""

    # ── Project cards (rest) ──
    project_cards = ""
    for proj in rest_projects:
        meta = proj["meta"]
        commits = meta.get("commits", "—")
        eras = meta.get("era_count", 0)
        active_days = meta.get("active_days", "—")
        total_deliverables = proj.get("total_deliverables", 0)
        commits_fmt = f"{commits:,}" if isinstance(commits, int) else str(commits)
        viz_links = ""
        for viz in proj["visuals"]:
            viz_links += f'<a href="{viz["href"]}" class="viz-link">{viz["name"]}</a>\n              '

        # Category pills
        cat_pills = ""
        for cat_name, cat_meta in CATEGORIES.items():
            count = len(proj.get("deliverables", {}).get(cat_name, []))
            if count:
                color = cat_meta["color"]
                cat_pills += f'<span class="cat-pill" style="background:{color}22;color:{color};border:1px solid {color}44">{cat_meta["label"]} {count}</span>\n'

        project_cards += f"""
        <a href="{proj['name']}/" class="project-card">
          <div class="card-header">
            <h2 class="card-title">{proj['name'].upper()}</h2>
            <span class="card-badge">{total_deliverables} {_pluralize(total_deliverables, 'deliverable')}</span>
          </div>
          <div class="card-stats">
            <div class="stat"><span class="stat-value">{commits_fmt}</span><span class="stat-label">{_pluralize(commits if isinstance(commits, int) else 0, 'commit')}</span></div>
            <div class="stat"><span class="stat-value">{eras if eras else '—'}</span><span class="stat-label">{_pluralize(eras, 'era')}</span></div>
            <div class="stat"><span class="stat-value">{active_days}</span><span class="stat-label">{_pluralize(active_days if isinstance(active_days, int) else 0, 'active day')}</span></div>
          </div>
          <div class="cat-pills">{cat_pills}</div>
          <div class="card-links" onclick="event.stopPropagation()">
            {viz_links}
          </div>
        </a>"""

    # ── Aggregate stats ──
    mined_commits = sum(p["meta"].get("commits", 0) for p in projects if isinstance(p["meta"].get("commits"), int))
    total_repos = len(projects) + len(api_repos)
    total_commits = mined_commits + api_commits
    total_commits_fmt = f"{total_commits:,}"
    total_repos_fmt = f"{total_repos:,}"
    total_deliverables = sum(p.get("total_deliverables", 0) for p in projects)
    owners = set(r["owner"] for r in api_repos) | {"mined"}
    n_networks = len(owners)

    # ── Cross-project chart data ──
    all_repos_chart = []
    for p in projects:
        c = p["meta"].get("commits", 0)
        if isinstance(c, int) and c > 0:
            all_repos_chart.append({"name": p["name"].upper(), "commits": c})
    for r in api_repos:
        c = r.get("commits", 0)
        if isinstance(c, int) and c > 0:
            all_repos_chart.append({"name": r["name"], "commits": c})
    all_repos_chart.sort(key=lambda x: x["commits"], reverse=True)
    top_chart = all_repos_chart[:12]
    chart_repo_labels = json.dumps([r["name"][:22] for r in top_chart])
    chart_repo_commits = json.dumps([r["commits"] for r in top_chart])

    lang_dist: dict[str, int] = {}
    for r in api_repos:
        lang = r.get("language") or "Unknown"
        lang_dist[lang] = lang_dist.get(lang, 0) + 1
    chart_lang_labels = json.dumps(list(lang_dist.keys()))
    chart_lang_counts = json.dumps(list(lang_dist.values()))

    cat_totals: dict[str, int] = {}
    for p in projects:
        for cat_name, files in p.get("deliverables", {}).items():
            cat_totals[cat_name] = cat_totals.get(cat_name, 0) + len(files)
    cat_display = [CATEGORIES.get(k, {}).get("label", k.title()) for k in cat_totals]
    chart_cat_labels = json.dumps(cat_display)
    chart_cat_counts = json.dumps(list(cat_totals.values()))
    chart_cat_colors = json.dumps([CATEGORIES.get(k, {}).get("color", "#6a7888") for k in cat_totals])

    chart_proj_names = json.dumps([p["name"].upper() for p in projects_sorted])
    chart_proj_days = [p["meta"].get("active_days", 0) if isinstance(p["meta"].get("active_days"), int) else 0 for p in projects_sorted]
    chart_proj_eras = [p["meta"].get("era_count", 0) or 0 for p in projects_sorted]
    chart_proj_days_json = json.dumps(chart_proj_days)
    chart_proj_eras_json = json.dumps(chart_proj_eras)

    # ── API repos section (collapsed by default) ──
    api_section = ""
    if api_repos:
        # Build filter buttons
        owner_filters = ""
        for owner in sorted(set(r["owner"] for r in api_repos)):
            label = "KyaniteLabs" if "kyanite" in owner.lower() else "Personal"
            owner_filters += f'<button class="filter-btn" data-filter="{owner}">{label}</button>\n          '
        api_section = f"""
<div class="section-wrap">
  <h2 class="collapsible-header collapsed" id="api-toggle">
    <span>All GitHub Repos ({len(api_repos)})</span>
    <span class="api-summary">{api_commits:,} commits from {n_networks - 1} accounts</span>
  </h2>
  <div class="collapsible-body collapsed" id="api-body">
    <div class="filter-bar">
      <button class="filter-btn active" data-filter="all">All</button>
      {owner_filters}
    </div>
    <div class="api-grid">
      {api_section_html}
    </div>
  </div>
</div>"""

    # ── Cross-Repo Analysis section ──
    cross_repo_section = ""
    global_deliverables_dir = Path("global/deliverables")
    if global_deliverables_dir.exists():
        md_files = sorted(global_deliverables_dir.rglob("*.md"))
        if md_files:
            cards_html = ""
            for md in md_files:
                display = md.stem.replace("-", " ").replace("_", " ").title()
                rel = f"global/{md.relative_to(global_deliverables_dir)}"
                cards_html += f'<a href="md-viewer.html?file={rel}" class="cross-card"><span class="cross-name">{display}</span><span class="cross-path">{rel}</span></a>\n'
            cross_repo_section = f"""<div class="section-wrap">
  <h3 class="section-heading">Cross-Repository Analysis ({len(md_files)})</h3>
  <div class="cross-grid">{cards_html}</div>
</div>"""

    # ── Global viz cards ──
    global_viz_section = ""
    if api_repos:
        global_viz_section = """
<div class="section-wrap">
  <div class="global-viz-row">
    <a href="dashboard.html" class="global-viz-card">
      <span class="gv-icon">&#128202;</span>
      <div class="gv-info"><strong>Multi-Project Dashboard</strong><span class="gv-desc">Commit timeline, activity heatmap, repo comparison</span></div>
    </a>
    <a href="global.html" class="global-viz-card">
      <span class="gv-icon">&#127760;</span>
      <div class="gv-info"><strong>Global Network</strong><span class="gv-desc">Cross-repo connections, language breakdown</span></div>
    </a>
  </div>
</div>"""

    html = f"""<!DOCTYPE html>
<html lang="en" data-theme="editorial">
<head>
{head_bundle(
    title="Dev-Archaeology",
    description=f"Forensic analysis of development history across {total_repos} repositories",
    include_charts=True
)}
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --bg:#06090f;--surface:#0c1018;--surface2:#141a24;--surface3:#1c2432;
  --border:#1a2232;--border-hover:#2a3a52;
  --text:#e8ecf2;--text2:#8d99aa;--text3:#6a7888;
  --accent:#34d399;
  --font-display:'Space Grotesk',sans-serif;--font-body:'DM Sans',sans-serif;
  --font-mono:'JetBrains Mono',monospace;
  --radius-sm:6px;--radius-md:10px;--radius-lg:16px;
}}
html{{scroll-behavior:smooth;-webkit-font-smoothing:antialiased}}
body{{background:var(--bg);color:var(--text);font-family:var(--font-body);line-height:1.65;min-height:100vh}}

/* ── Nav ── */
.site-nav{{position:sticky;top:0;z-index:100;background:var(--surface);border-bottom:1px solid var(--border);padding:0 24px;display:flex;align-items:center;gap:12px;height:52px;font-family:var(--font-display);backdrop-filter:blur(12px)}}
.site-nav .nav-brand{{font-weight:700;font-size:16px;color:var(--text);letter-spacing:-.02em}}
.site-nav .nav-subtitle{{font-size:13px;color:var(--text3);margin-left:4px}}
.site-nav .nav-meta{{margin-left:auto;font-size:12px;color:var(--text3);font-family:var(--font-mono)}}

/* ── Hero ── */
.hero{{padding:40px 24px 24px;max-width:1200px;margin:0 auto;text-align:center}}
.hero h1{{font-family:var(--font-display);font-size:clamp(24px,4vw,36px);font-weight:700;letter-spacing:-.03em;color:var(--text);margin-bottom:4px}}
.hero p{{font-size:15px;color:var(--text2);margin-bottom:20px}}
.hero-stats{{display:flex;justify-content:center;gap:32px}}
.hero-stat{{text-align:center}}
.hero-stat .value{{display:block;font-family:var(--font-display);font-size:28px;font-weight:700;color:var(--accent)}}
.hero-stat .label{{font-size:12px;color:var(--text3);text-transform:uppercase;letter-spacing:.05em}}

/* ── Section wrapper ── */
.section-wrap{{max-width:1200px;margin:0 auto;padding:0 24px 32px}}

/* ── Featured project ── */
.featured-card{{
  display:grid;grid-template-columns:1fr auto;gap:24px;
  background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);
  padding:28px 32px;text-decoration:none;color:var(--text);
  transition:border-color .2s,box-shadow .2s;
}}
.featured-card:hover{{border-color:var(--border-hover);box-shadow:0 4px 24px rgba(0,0,0,.3)}}
.featured-badge{{font-size:11px;font-weight:600;color:var(--accent);text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px}}
.featured-title{{font-family:var(--font-display);font-size:clamp(24px,4vw,32px);font-weight:700;letter-spacing:-.02em;margin-bottom:4px}}
.featured-desc{{font-size:14px;color:var(--text2);margin-bottom:16px;max-width:500px}}
.featured-stats{{display:flex;gap:20px}}
.fstat{{display:flex;flex-direction:column}}
.fstat-val{{font-family:var(--font-display);font-size:22px;font-weight:600;color:var(--text)}}
.fstat-lbl{{font-size:11px;color:var(--text3);text-transform:uppercase;letter-spacing:.04em}}
.featured-links{{display:flex;flex-direction:column;gap:6px;justify-content:center}}
.fviz-link{{
  font-size:12px;font-weight:500;color:var(--text2);
  background:var(--surface2);padding:8px 14px;border-radius:var(--radius-sm);
  text-decoration:none;transition:color .15s,background .15s;white-space:nowrap;
}}
.fviz-link:hover{{color:var(--text);background:var(--surface3)}}

/* ── Section headings ── */
.section-heading{{
  font-family:var(--font-display);font-size:16px;font-weight:600;
  color:var(--text2);margin-bottom:16px;padding-top:8px;
}}

/* ── Project Grid ── */
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px}}

.project-card{{
  background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);
  padding:20px;text-decoration:none;color:var(--text);
  transition:border-color .2s,box-shadow .2s,transform .2s;
  display:flex;flex-direction:column;gap:12px;
}}
.project-card:hover{{
  border-color:var(--border-hover);
  box-shadow:0 4px 24px rgba(0,0,0,.3);
  transform:translateY(-2px);
}}

.card-header{{display:flex;align-items:center;justify-content:space-between}}
.card-title{{font-family:var(--font-display);font-size:16px;font-weight:600;letter-spacing:-.01em}}
.card-badge{{
  font-size:10px;font-weight:500;color:var(--text3);
  background:var(--surface2);padding:2px 8px;border-radius:20px;
  font-family:var(--font-mono);
}}

.card-stats{{display:flex;gap:16px}}
.stat{{display:flex;flex-direction:column}}
.stat-value{{font-family:var(--font-display);font-size:18px;font-weight:600;color:var(--text)}}
.stat-label{{font-size:10px;color:var(--text3);text-transform:uppercase;letter-spacing:.04em}}

.card-links{{display:flex;gap:4px;flex-wrap:wrap}}
.viz-link{{
  font-size:11px;font-weight:500;color:var(--text2);
  background:var(--surface2);padding:4px 10px;border-radius:var(--radius-sm);
  text-decoration:none;transition:color .15s,background .15s;
}}
.viz-link:hover{{color:var(--text);background:var(--surface3)}}

/* ── Category pills ── */
.cat-pills{{display:flex;gap:4px;flex-wrap:wrap;margin-top:8px}}
.cat-pill{{font-size:10px;font-weight:500;padding:2px 8px;border-radius:12px;font-family:var(--font-mono);white-space:nowrap}}

/* ── Cross-repo cards ── */
.cross-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px}}
.cross-card{{display:flex;flex-direction:column;gap:2px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-md);padding:12px 14px;text-decoration:none;color:var(--text);transition:border-color .2s}}
.cross-card:hover{{border-color:var(--border-hover)}}
.cross-name{{font-family:var(--font-display);font-size:13px;font-weight:600}}
.cross-path{{font-size:10px;color:var(--text3);font-family:var(--font-mono)}}

/* ── Deliverable sections (project index) ── */
.cat-section{{margin-bottom:28px}}
.cat-heading{{font-family:var(--font-display);font-size:16px;font-weight:600;color:var(--text2);margin-bottom:12px;display:flex;align-items:center;gap:8px}}
.cat-icon{{font-size:18px}}
.cat-count{{font-size:11px;font-weight:500;color:var(--text3);background:var(--surface2);padding:2px 8px;border-radius:12px;font-family:var(--font-mono)}}
.deliv-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:8px}}
.deliv-file{{display:flex;align-items:center;gap:10px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-sm);padding:10px 14px;text-decoration:none;color:var(--text);transition:border-color .15s,transform .15s}}
.deliv-file:hover{{border-color:var(--border-hover);transform:translateX(2px)}}
.deliv-icon{{font-size:16px;flex-shrink:0}}
.deliv-name{{flex:1;font-size:13px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.deliv-ext{{font-size:10px;font-weight:600;font-family:var(--font-mono);flex-shrink:0}}

/* ── Global viz cards ── */
.global-viz-row{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
.global-viz-card{{
  display:flex;align-items:center;gap:14px;
  background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);
  padding:18px 20px;text-decoration:none;color:var(--text);
  transition:border-color .2s,transform .2s;
}}
.global-viz-card:hover{{border-color:var(--border-hover);transform:translateY(-2px)}}
.gv-icon{{font-size:28px;flex-shrink:0}}
.gv-info strong{{font-family:var(--font-display);font-size:14px;display:block;margin-bottom:2px}}
.gv-desc{{font-size:12px;color:var(--text3);display:block}}

/* ── Collapsible ── */
.collapsible-header{{
  cursor:pointer;user-select:none;display:flex;align-items:baseline;gap:12px;
  font-family:var(--font-display);font-size:18px;font-weight:600;color:var(--text);
  padding:20px 0 12px;
}}
.collapsible-header::before{{
  content:'▾';display:inline-block;transition:transform .2s;font-size:14px;color:var(--text3);
}}
.collapsible-header.collapsed::before{{transform:rotate(-90deg)}}
.api-summary{{
  font-size:12px;font-weight:400;color:var(--text3);font-family:var(--font-mono);margin-left:4px;
}}
.collapsible-body{{
  overflow:hidden;transition:max-height .3s ease-out;
}}
.collapsible-body.collapsed{{max-height:0}}

/* ── Filter buttons ── */
.filter-bar{{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:16px}}
.filter-btn{{
  font-size:11px;font-weight:500;color:var(--text3);
  background:var(--surface2);padding:4px 12px;border-radius:20px;
  border:1px solid var(--border);cursor:pointer;transition:all .15s;
  font-family:var(--font-body);
}}
.filter-btn:hover,.filter-btn.active{{color:var(--text);background:var(--surface3);border-color:var(--border-hover)}}

/* ── API repos ── */
.api-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:10px}}
.api-card{{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-md);padding:12px 14px;transition:border-color .2s}}
.api-card:hover{{border-color:var(--border-hover)}}
.api-header{{display:flex;align-items:center;justify-content:space-between;gap:8px}}
.api-name{{font-family:var(--font-display);font-size:13px;font-weight:600;color:var(--text);text-decoration:none;letter-spacing:-.01em}}
.api-name:hover{{text-decoration:underline}}
.api-badge{{font-size:10px;font-weight:500;color:var(--text3);background:var(--surface2);padding:2px 8px;border-radius:20px;font-family:var(--font-mono);white-space:nowrap}}
.api-meta{{font-size:11px;color:var(--text3);margin-top:3px;font-family:var(--font-mono)}}
.api-desc{{font-size:12px;color:var(--text2);margin-top:4px;line-height:1.4}}
.owner-section{{margin-bottom:24px}}
.owner-title{{font-family:var(--font-display);font-size:14px;font-weight:600;color:var(--text2);margin-bottom:10px;display:flex;align-items:center;gap:10px}}
.owner-count{{font-size:11px;font-weight:400;color:var(--text3);font-family:var(--font-mono)}}

/* ── Footer ── */
.footer{{text-align:center;padding:24px;color:var(--text3);font-size:12px;font-family:var(--font-mono);border-top:1px solid var(--border)}}

/* ── Category pills ── */
.cat-pills{{display:flex;gap:4px;flex-wrap:wrap;margin-top:8px}}
.cat-pill{{font-size:10px;font-weight:500;padding:2px 8px;border-radius:12px;font-family:var(--font-mono);white-space:nowrap}}

/* ── Cross-repo analysis ── */
.cross-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px}}
.cross-card{{display:flex;flex-direction:column;gap:2px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-md);padding:12px 14px;text-decoration:none;color:var(--text);transition:border-color .2s}}
.cross-card:hover{{border-color:var(--border-hover)}}
.cross-name{{font-family:var(--font-display);font-size:13px;font-weight:600}}
.cross-path{{font-size:10px;color:var(--text3);font-family:var(--font-mono)}}

/* ── Homepage Visualizations ── */
.homepage-viz-section{{max-width:1200px;margin:0 auto;padding:0 24px 28px}}
.homepage-viz-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:16px}}
.homepage-viz-card{{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);overflow:hidden;transition:border-color .2s}}
.homepage-viz-card:hover{{border-color:var(--border-hover)}}
.hviz-head{{padding:14px 18px 0;font-family:var(--font-display);font-size:13px;font-weight:600;color:var(--text2);display:flex;align-items:center;gap:8px}}
.hviz-head .hviz-icon{{font-size:18px}}
.hviz-body{{padding:12px 14px 14px;height:280px;position:relative}}
.hviz-body canvas{{width:100%!important;height:100%!important}}

/* ── Mobile ── */
@media(max-width:768px){{
  .section-wrap{{padding:0 16px 24px}}
  .hero{{padding:28px 16px 16px}}
  .hero-stats{{gap:20px}}
  .hero-stat .value{{font-size:22px}}
  .site-nav{{padding:0 16px}}
  .grid{{grid-template-columns:1fr}}
  .featured-card{{grid-template-columns:1fr;padding:20px 16px}}
  .featured-links{{flex-direction:row;flex-wrap:wrap}}
  .global-viz-row{{grid-template-columns:1fr}}
  .api-grid{{grid-template-columns:1fr}}
  .homepage-viz-grid{{grid-template-columns:1fr}}
}}
</style>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
</head>
<body>

<a class="skip-link" href="#root">Skip to content</a>

<nav class="site-nav">
  <span class="nav-brand">Dev-Archaeology</span>
  <span class="nav-subtitle">Forensic Mining Dashboard</span>
  <span class="nav-meta">{total_repos} repos &middot; updated {now}</span>
  {THEME_SWITCHER_HTML}
</nav>

<main id="root">
<div class="hero">
  <h1>Development Fossil Record</h1>
  <p>Forensic archaeology of {total_repos} repositories — {total_commits_fmt} commits mined, analyzed, and visualized</p>
  <div class="hero-stats">
    <div class="hero-stat"><span class="value">{total_repos_fmt}</span><span class="label">{_pluralize(total_repos, 'Repository', 'Repositories')}</span></div>
    <div class="hero-stat"><span class="value">{total_commits_fmt}</span><span class="label">{_pluralize(total_commits, 'Commit')}</span></div>
    <div class="hero-stat"><span class="value">{total_deliverables}</span><span class="label">{_pluralize(total_deliverables, 'Deliverable')}</span></div>
    <div class="hero-stat"><span class="value">{n_networks}</span><span class="label">{_pluralize(n_networks, 'Network')}</span></div>
  </div>
</div>

<div class="homepage-viz-section">
  <h3 class="section-heading">Cross-Project Analytics</h3>
  <div class="homepage-viz-grid">
    <div class="homepage-viz-card">
      <div class="hviz-head"><span class="hviz-icon">&#128202;</span>Commit Distribution</div>
      <div class="hviz-body"><canvas id="chart-repo-commits"></canvas></div>
    </div>
    <div class="homepage-viz-card">
      <div class="hviz-head"><span class="hviz-icon">&#127760;</span>Language Map</div>
      <div class="hviz-body"><canvas id="chart-languages"></canvas></div>
    </div>
    <div class="homepage-viz-card">
      <div class="hviz-head"><span class="hviz-icon">&#128218;</span>Deliverable Types</div>
      <div class="hviz-body"><canvas id="chart-deliverables"></canvas></div>
    </div>
    <div class="homepage-viz-card">
      <div class="hviz-head"><span class="hviz-icon">&#128197;</span>Project Activity</div>
      <div class="hviz-body"><canvas id="chart-activity"></canvas></div>
    </div>
  </div>
</div>

{featured_html}

{f'''<div class="section-wrap">
  <h3 class="section-heading">Analyzed Projects ({len(rest_projects)})</h3>
  <div class="grid">
  {project_cards}
  </div>
</div>''' if rest_projects else ""}

{cross_repo_section}

{global_viz_section}

{api_section}

</main>

<div class="footer">
  Generated by dev-archaeology &middot; {now}
</div>

{body_end_bundle()}

<script>
// Collapsible toggle
document.querySelectorAll('.collapsible-header').forEach(function(h) {{
  h.addEventListener('click', function() {{
    h.classList.toggle('collapsed');
    var body = h.nextElementSibling;
    if (body) body.classList.toggle('collapsed');
  }});
}});
// Filter buttons
document.querySelectorAll('.filter-bar').forEach(function(bar) {{
  bar.querySelectorAll('.filter-btn').forEach(function(btn) {{
    btn.addEventListener('click', function() {{
      bar.querySelectorAll('.filter-btn').forEach(function(b) {{ b.classList.remove('active'); }});
      btn.classList.add('active');
      var filter = btn.dataset.filter;
      document.querySelectorAll('.api-card').forEach(function(card) {{
        card.style.display = (filter === 'all' || card.dataset.owner === filter) ? '' : 'none';
      }});
      document.querySelectorAll('.owner-section').forEach(function(sec) {{
        if (filter === 'all') {{ sec.style.display = ''; return; }}
        sec.style.display = sec.dataset.owner === filter ? '' : 'none';
      }});
    }});
  }});
}});
</script>

<script>
// Cross-project charts
document.addEventListener('DOMContentLoaded', function() {{
  var colors = getThemeColors();
  Chart.defaults.color = colors.muted;
  Chart.defaults.borderColor = colors.border;
  Chart.defaults.font.family = "'Source Sans 3', sans-serif";
  Chart.defaults.plugins.legend.display = false;
  Chart.defaults.responsive = true;
  Chart.defaults.maintainAspectRatio = false;
  var PALETTE=[colors.accent,colors.secondary,colors.success,colors.warning,colors.danger,'#818cf8','#38bdf8','#4ade80','#e879f9'];

  // Chart 1: Commit Distribution
  var ctx1 = document.getElementById('chart-repo-commits');
  if (ctx1) new Chart(ctx1, {{ type:'bar', data: {{
    labels: {chart_repo_labels},
    datasets:[{{ label:'Commits', data:{chart_repo_commits},
      backgroundColor:function(ctx){{ var i=ctx.dataIndex; var v=ctx.raw; var max={chart_repo_commits}[0]||1;
        var pct=v/max; return pct>0.6?colors.accent:pct>0.3?colors.secondary:colors.muted; }},
      borderRadius:4, barPercentage:0.7 }}]
  }}, options:{{ indexAxis:'y', scales:{{ x:{{beginAtZero:true,grid:{{color:colors.border}}}}, y:{{grid:{{display:false}}}} }},
    plugins:{{tooltip:{{callbacks:{{label:function(c){{return c.raw.toLocaleString()+' commits';}}}}}}}} }} }});

  // Chart 2: Language Map
  var ctx2 = document.getElementById('chart-languages');
  if (ctx2) new Chart(ctx2, {{ type:'doughnut', data: {{
    labels:{chart_lang_labels}, datasets:[{{ data:{chart_lang_counts},
      backgroundColor:{chart_lang_labels}.map(function(_,i){{return PALETTE[i%PALETTE.length];}}), borderWidth:0 }}]
  }}, options:{{ cutout:'55%', plugins:{{ legend:{{display:true,position:'right',labels:{{boxWidth:10,padding:8,font:{{size:10}}}}}} }} }} }});

  // Chart 3: Deliverable Types
  var ctx3 = document.getElementById('chart-deliverables');
  if (ctx3) new Chart(ctx3, {{ type:'bar', data: {{
    labels:{chart_cat_labels}, datasets:[{{ label:'Count', data:{chart_cat_counts},
      backgroundColor:{chart_cat_colors}, borderRadius:4, barPercentage:0.6 }}]
  }}, options:{{ scales:{{ y:{{beginAtZero:true,grid:{{color:colors.border}}}}, x:{{grid:{{display:false}}}} }} }} }});

  // Chart 4: Project Activity
  var ctx4 = document.getElementById('chart-activity');
  if (ctx4) new Chart(ctx4, {{ type:'bar', data: {{
    labels:{chart_proj_names},
    datasets:[
      {{ label:'Active Days', data:{chart_proj_days_json}, backgroundColor:colors.success, borderRadius:4, barPercentage:0.4 }},
      {{ label:'Eras', data:{chart_proj_eras_json}, backgroundColor:colors.warning, borderRadius:4, barPercentage:0.4 }}
    ]
  }}, options:{{ scales:{{ y:{{beginAtZero:true,grid:{{color:colors.border}}}}, x:{{grid:{{display:false}}}} }},
    plugins:{{ legend:{{display:true, labels:{{boxWidth:10,padding:8}}}} }} }} }});
}});
</script>
</body>
</html>"""
    return html


# ── Opportunity Visualization Constants ──

_OPP_FEATURES: list[dict[str, str]] = [
    {"slug": "learning-velocity", "title": "Learning Velocity", "icon": "&#128200;"},
    {"slug": "frustration-to-automation", "title": "Frustration &#8594; Automation", "icon": "&#9889;"},
    {"slug": "knowledge-gap", "title": "Knowledge Gap Detector", "icon": "&#128270;"},
    {"slug": "token-efficiency", "title": "Token Efficiency Coach", "icon": "&#127919;"},
    {"slug": "session-quality", "title": "Session Quality Scorer", "icon": "&#11088;"},
    {"slug": "ai-agent-mastery", "title": "AI Agent Mastery", "icon": "&#129302;"},
    {"slug": "creative-dna", "title": "Creative DNA Transfer", "icon": "&#127912;"},
    {"slug": "neurodivergent-profile", "title": "Neurodivergent Profile", "icon": "&#129504;"},
    {"slug": "model-selection-advisor", "title": "Model Selection Advisor", "icon": "&#128187;"},
    {"slug": "before-after-snapshot", "title": "Before / After Snapshot", "icon": "&#128065;"},
    {"slug": "cross-repo-transfer", "title": "Cross-Repo Transfer", "icon": "&#128279;"},
    {"slug": "youtube-learning-graph", "title": "YouTube Learning Graph", "icon": "&#127909;"},
    {"slug": "architecture-timelapse", "title": "Architecture Timelapse", "icon": "&#127959;"},
    {"slug": "commit-cognitive-load", "title": "Cognitive Load Proxy", "icon": "&#129704;"},
]

_PROJECT_INDEX_CSS = """
/* Score Cards */
.score-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:28px}
.score-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-md);padding:18px 16px;text-align:center;position:relative;overflow:hidden;transition:border-color .3s,transform .3s}
.score-card:hover{border-color:var(--border-hover);transform:translateY(-2px)}
.score-card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px}
.score-card:nth-child(1)::before{background:linear-gradient(90deg,#06b6d4,#34d399)}
.score-card:nth-child(2)::before{background:linear-gradient(90deg,#a78bfa,#f472b6)}
.score-card:nth-child(3)::before{background:linear-gradient(90deg,#fbbf24,#fb923c)}
.score-card:nth-child(4)::before{background:linear-gradient(90deg,#f87171,#ef4444)}
.score-ring{width:72px;height:72px;margin:0 auto 8px;transform:rotate(-90deg)}
.score-ring-bg{fill:none;stroke:var(--surface3);stroke-width:5}
.score-ring-fill{fill:none;stroke-width:5;stroke-linecap:round;stroke-dasharray:264;stroke-dashoffset:264;transition:stroke-dashoffset 1.5s cubic-bezier(0.16,1,0.3,1)}
.score-value{font-family:var(--font-display);font-size:24px;font-weight:700;color:var(--text);margin-bottom:2px}
.score-label{font-size:11px;color:var(--text3);text-transform:uppercase;letter-spacing:.06em;font-weight:500}
.score-sub{font-size:10px;color:var(--text3);margin-top:4px;font-family:var(--font-mono)}

/* Visualization Grid */
.viz-section{margin-bottom:32px}
.viz-section-title{font-family:var(--font-display);font-size:16px;font-weight:600;color:var(--text2);margin-bottom:16px;display:flex;align-items:center;gap:8px}
.viz-section-title .count{font-size:11px;font-weight:500;color:var(--text3);background:var(--surface2);padding:2px 8px;border-radius:12px;font-family:var(--font-mono)}
.viz-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}
.viz-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-md);overflow:hidden;transition:border-color .3s,box-shadow .3s}
.viz-card:hover{border-color:var(--border-hover);box-shadow:0 4px 24px rgba(0,0,0,.3)}
.viz-card-head{padding:12px 16px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:8px;background:linear-gradient(180deg,rgba(6,182,212,.04) 0%,transparent 100%)}
.viz-card-icon{font-size:16px}
.viz-card-title{font-family:var(--font-display);font-size:13px;font-weight:600;color:var(--text);flex:1}
.viz-card-badge{font-size:10px;color:#06b6d4;background:rgba(6,182,212,.1);padding:2px 8px;border-radius:12px;font-family:var(--font-mono)}
.viz-card-body{padding:14px 16px;position:relative;height:280px}
.viz-card-body canvas{width:100%!important;height:100%!important}
.viz-card-foot{padding:8px 16px 10px;border-top:1px solid var(--border);font-size:11px;color:var(--text3);line-height:1.5}

/* Collapsible Files */
.files-toggle{cursor:pointer;user-select:none;display:flex;align-items:center;gap:8px;padding:16px 0 12px;font-family:var(--font-display);font-size:15px;font-weight:600;color:var(--text2);border:none;background:none;width:100%}
.files-toggle::before{content:'\\25BE';font-size:14px;color:var(--text3);transition:transform .2s;display:inline-block}
.files-toggle.collapsed::before{transform:rotate(-90deg)}
.files-body{overflow:hidden;transition:max-height .3s ease-out}
.files-body.collapsed{max-height:0}

@media(max-width:768px){
  .score-row{grid-template-columns:repeat(2,1fr)}
  .viz-grid{grid-template-columns:1fr}
  .viz-card-body{height:200px}
}
@media(max-width:480px){
  .score-row{grid-template-columns:1fr}
}
"""

_PROJECT_INDEX_JS = """
document.addEventListener('DOMContentLoaded', async function() {
  var BASE = 'opportunity/';
  var colors = getThemeColors();
  var PALETTE = [colors.accent, colors.secondary, colors.success, colors.warning, colors.danger, '#818cf8', '#38bdf8', '#4ade80', '#e879f9'];

  Chart.defaults.color = colors.muted;
  Chart.defaults.borderColor = colors.border;
  Chart.defaults.font.family = "'Source Sans 3', sans-serif";
  Chart.defaults.font.size = 11;
  Chart.defaults.plugins.legend.display = false;
  Chart.defaults.responsive = true;
  Chart.defaults.maintainAspectRatio = false;

  async function load(slug) {
    try {
      var r = await fetch(BASE + 'opportunity-' + slug + '.json');
      return r.ok ? await r.json() : null;
    } catch(e) { return null; }
  }

  function summary(slug, data) {
    var el = document.getElementById('summary-' + slug);
    if (!el || !data || !data.summary) return;
    var s = data.summary;
    el.textContent = s.text || s.one_liner || s.headline || '';
  }

  function animateScore(id, value, max, color) {
    var el = document.getElementById(id);
    if (!el) return;
    var pct = Math.min(value / max, 1);
    var ring = el.querySelector('.score-ring-fill');
    if (ring) {
      ring.style.stroke = color || CYAN;
      ring.style.strokeDasharray = 264;
      setTimeout(function() { ring.style.strokeDashoffset = 264 * (1 - pct); }, 100);
    }
    var val = el.querySelector('.score-value');
    if (val) val.textContent = (typeof value === 'number' && value % 1 !== 0) ? value.toFixed(1) : value;
  }

  function numVal(v) { return (typeof v === 'number') ? v : (typeof v === 'string' ? parseFloat(v) : 0) || 0; }

  // ── Score Cards ──
  var mastery = await load('ai-agent-mastery');
  if (mastery) animateScore('score-mastery', mastery.overall_score, 100, colors.accent);

  var session = await load('session-quality');
  if (session) animateScore('score-session', session.summary && (session.summary.avg_quality || session.summary.average_quality || 5), 10, colors.secondary);

  var velocity = await load('learning-velocity');
  if (velocity && velocity.summary) {
    var el = document.getElementById('score-velocity');
    if (el) {
      var ring = el.querySelector('.score-ring-fill');
      if (ring) { ring.style.stroke = colors.warning; ring.style.strokeDasharray = 264; setTimeout(function(){ ring.style.strokeDashoffset = 264 * 0.7; }, 100); }
      var val = el.querySelector('.score-value');
      if (val) val.textContent = (velocity.summary.learning_acceleration || 1.41).toFixed(2) + 'x';
    }
  }

  var frustration = await load('frustration-to-automation');
  if (frustration && frustration.summary) {
    var el = document.getElementById('score-frustration');
    if (el) {
      var ring = el.querySelector('.score-ring-fill');
      var rate = frustration.summary.conversion_rate || 1;
      if (ring) { ring.style.stroke = colors.success; ring.style.strokeDasharray = 264; setTimeout(function(){ ring.style.strokeDashoffset = 264 * (1 - rate); }, 100); }
      var val = el.querySelector('.score-value');
      if (val) val.textContent = Math.round(rate * 100) + '%';
    }
  }

  // ── Chart 1: Learning Velocity ──
  if (velocity && velocity.era_velocity) {
    var ctx = document.getElementById('chart-learning-velocity');
    if (ctx) { summary('learning-velocity', velocity);
      new Chart(ctx, { type:'line', data: {
        labels: velocity.era_velocity.map(function(e){return e.era||e.name||'';}),
        datasets:[{ label:'Commits/Day', data: velocity.era_velocity.map(function(e){return e.velocity_per_day||e.commits_per_day||0;}),
          borderColor:colors.accent, backgroundColor:colors.accent+'20', fill:true, tension:0.4, pointRadius:4, pointBackgroundColor:colors.accent }]
      }, options:{ scales:{ y:{beginAtZero:true, grid:{color:'#1e2a3a'}}, x:{grid:{display:false}} }, plugins:{tooltip:{mode:'index',intersect:false}} } });
    }
  }

  // ── Chart 2: Frustration → Automation ──
  if (frustration) {
    var ctx = document.getElementById('chart-frustration-to-automation');
    if (ctx) { summary('frustration-to-automation', frustration);
      var patterns = frustration.conversion_patterns || [];
      var labels = patterns.map(function(p){return (p.category||'').replace(/_/g,' ').substring(0,20);});
      var intensities = patterns.map(function(p){return p.frustration_level||0;});
      new Chart(ctx, { type:'bar', data: {
        labels: labels,
        datasets:[{ label:'Frustration Level', data:intensities, backgroundColor: patterns.map(function(p){return p.converted ? colors.success : colors.danger;}),
          borderRadius:4, barPercentage:0.7 }]
      }, options:{ indexAxis:'y', scales:{ x:{beginAtZero:true, max:5, grid:{color:'#1e2a3a'}}, y:{grid:{display:false}} },
        plugins:{tooltip:{callbacks:{label:function(c){return 'Level '+c.raw+' → '+(patterns[c.dataIndex].converted?'Automated':'Pending');}}}} } });
    }
  }

  // ── Chart 3: Knowledge Gap ──
  var gap = await load('knowledge-gap');
  if (gap && gap.reinvention_gaps) {
    var ctx = document.getElementById('chart-knowledge-gap');
    if (ctx) { summary('knowledge-gap', gap);
      var gaps = gap.reinvention_gaps;
      new Chart(ctx, { type:'bar', data: {
        labels: gaps.map(function(g){return g.intuitive_name||g.informal_term||'';}),
        datasets:[{ label:'Severity', data: gaps.map(function(g){return g.severity==='HIGH'?4:g.severity==='MEDIUM'?2:1;}),
          backgroundColor: gaps.map(function(g){return g.severity==='HIGH'?RED:ORANGE;}), borderRadius:4, barPercentage:0.6 }]
      }, options:{ indexAxis:'y', scales:{ x:{beginAtZero:true, max:5, grid:{color:'#1e2a3a'}}, y:{grid:{display:false}} },
        plugins:{tooltip:{callbacks:{label:function(c){var g=gaps[c.dataIndex];return g.severity+' — maps to '+g.formal_term;}}}} } });
    }
  }

  // ── Chart 4: Token Efficiency ──
  var token = await load('token-efficiency');
  if (token && token.era_efficiency) {
    var ctx = document.getElementById('chart-token-efficiency');
    if (ctx) { summary('token-efficiency', token);
      var effData = token.era_efficiency;
      var hasMsg = effData.some(function(e){return (e.messages_per_commit||0) > 0;});
      var metric = hasMsg ? 'messages_per_commit' : 'commits';
      var metricLabel = hasMsg ? 'Messages/Commit' : 'Commits per Era';
      new Chart(ctx, { type:'bar', data: {
        labels: effData.map(function(e){return (e.era||'').substring(0,12);}),
        datasets:[{ label:metricLabel, data: effData.map(function(e){return e[metric]||0;}),
          backgroundColor:colors.secondary, borderRadius:4, barPercentage:0.6 }]
      }, options:{ scales:{ y:{beginAtZero:true, grid:{color:'#1e2a3a'}}, x:{grid:{display:false}} }, plugins:{tooltip:{mode:'index',intersect:false}} } });
    }
  }

  // ── Chart 5: Session Quality ──
  if (session && session.type_distribution) {
    var ctx = document.getElementById('chart-session-quality');
    if (ctx) { summary('session-quality', session);
      var types = session.type_distribution;
      var typeLabels = Object.keys(types);
      var typeValues = Object.values(types);
      new Chart(ctx, { type:'doughnut', data: {
        labels: typeLabels, datasets:[{ data:typeValues,
          backgroundColor:typeLabels.map(function(_,i){return PALETTE[i%PALETTE.length];}), borderWidth:0 }]
      }, options:{ cutout:'55%', plugins:{ legend:{display:true, position:'right', labels:{boxWidth:10,padding:8,font:{size:10}}} } } });
    }
  }

  // ── Chart 6: AI Agent Mastery ──
  if (mastery && mastery.sub_scores) {
    var ctx = document.getElementById('chart-ai-agent-mastery');
    if (ctx) { summary('ai-agent-mastery', mastery);
      var subKeys = Object.keys(mastery.sub_scores);
      var subVals = subKeys.map(function(k){return numVal(mastery.sub_scores[k]);});
      new Chart(ctx, { type:'radar', data: {
        labels: subKeys.map(function(k){return k.replace(/_/g,' ');}),
        datasets:[{ label:'Score', data:subVals, borderColor:colors.accent, backgroundColor:colors.accent+'20',
          pointBackgroundColor:colors.accent, pointRadius:4 }]
      }, options:{ scales:{ r:{beginAtZero:true, max:100, grid:{color:'#1e2a3a'}, angleLines:{color:'#1e2a3a'}, pointLabels:{font:{size:10}}} } } });
    }
  }

  // ── Chart 7: Creative DNA ──
  var dna = await load('creative-dna');
  if (dna && dna.transfer_map) {
    var ctx = document.getElementById('chart-creative-dna');
    if (ctx) { summary('creative-dna', dna);
      var transfers = dna.transfer_map;
      new Chart(ctx, { type:'bar', data: {
        labels: transfers.map(function(t){return (t.creative_source||'').substring(0,22);}),
        datasets:[{ label:'Strength', data: transfers.map(function(t){return t.strength==='HIGH'?3:t.strength==='MEDIUM'?2:1;}),
          backgroundColor: transfers.map(function(t){return t.strength==='HIGH'?CYAN:TEAL;}), borderRadius:4, barPercentage:0.6 }]
      }, options:{ indexAxis:'y', scales:{ x:{beginAtZero:true, max:4, grid:{color:'#1e2a3a'}}, y:{grid:{display:false}} },
        plugins:{tooltip:{callbacks:{label:function(c){var t=transfers[c.dataIndex];return t.strength+' → '+(t.code_destination||'').substring(0,30);}}}} } });
    }
  }

  // ── Chart 8: Neurodivergent Profile ──
  var neuro = await load('neurodivergent-profile');
  if (neuro && neuro.hourly_pattern) {
    var ctx = document.getElementById('chart-neurodivergent-profile');
    if (ctx) { summary('neurodivergent-profile', neuro);
      var hours = Object.keys(neuro.hourly_pattern).sort(function(a,b){return parseInt(a)-parseInt(b);});
      var counts = hours.map(function(h){return neuro.hourly_pattern[h];});
      new Chart(ctx, { type:'bar', data: {
        labels: hours.map(function(h){return h+':00';}),
        datasets:[{ label:'Commits', data:counts,
          backgroundColor: hours.map(function(h){var hr=parseInt(h);return (hr>=21||hr<5)?colors.danger:(hr>=9backgroundColor: hours.map(function(h){var hr=parseInt(h);return (hr>=21||hr<5)?RED:(hr>=9&&hr<17)?CYAN:ORANGE;})backgroundColor: hours.map(function(h){var hr=parseInt(h);return (hr>=21||hr<5)?RED:(hr>=9&&hr<17)?CYAN:ORANGE;})hr<17)?colors.accent:colors.warning;}),
          borderRadius:2, barPercentage:0.8 }]
      }, options:{ scales:{ y:{beginAtZero:true, grid:{color:'#1e2a3a'}}, x:{grid:{display:false}, ticks:{maxRotation:0,autoSkip:true,maxTicksLimit:12}} },
        plugins:{tooltip:{callbacks:{label:function(c){var h=parseInt(hours[c.dataIndex]);return c.raw+' commits ('+(h>=21||h<5?'Witching hour':h>=9&&h<17?'Core hours':'Evening')+')';}}}} } });
    }
  }

  // ── Chart 9: Model Selection ──
  var model = await load('model-selection-advisor');
  if (model && model.recommendation_matrix) {
    var ctx = document.getElementById('chart-model-selection-advisor');
    if (ctx) { summary('model-selection-advisor', model);
      var recs = model.recommendation_matrix;
      new Chart(ctx, { type:'bar', data: {
        labels: recs.map(function(r){return (r.task_type||'').replace(/_/g,' ').substring(0,20);}),
        datasets:[{ label:'Confidence', data: recs.map(function(r){return Math.round((r.confidence||0)*100);}),
          backgroundColor: recs.map(function(r){var c=r.confidence||0;return c>0.8?colors.success:c>0.6?colors.warning:colors.warning;}),
          borderRadius:4, barPercentage:0.6 }]
      }, options:{ scales:{ y:{beginAtZero:true, max:100, grid:{color:'#1e2a3a'}, ticks:{callback:function(v){return v+'%';}}}, x:{grid:{display:false}} } } });
    }
  }

  // ── Chart 10: Before/After ──
  var snapshot = await load('before-after-snapshot');
  if (snapshot && snapshot.before && snapshot.after) {
    var ctx = document.getElementById('chart-before-after-snapshot');
    if (ctx) { summary('before-after-snapshot', snapshot);
      var metrics = ['commits', 'active_days', 'velocity'];
      var metricLabels = ['Total Commits', 'Active Days', 'Velocity/Day'];
      var beforeVals = metrics.map(function(m){return numVal(snapshot.before[m]);});
      var afterVals = metrics.map(function(m){return numVal(snapshot.after[m]);});
      new Chart(ctx, { type:'bar', data: {
        labels: metricLabels,
        datasets:[
          { label:'Before', data:beforeVals, backgroundColor:colors.danger+'b0', borderRadius:4 },
          { label:'After', data:afterVals, backgroundColor:colors.success+'b0', borderRadius:4 }
        ]
      }, options:{ plugins:{ legend:{display:true, labels:{boxWidth:10,padding:8}} },
        scales:{ y:{beginAtZero:true, grid:{color:'#1e2a3a'}}, x:{grid:{display:false}} } } });
    }
  }

  // ── Chart 11: Cross-Repo Transfer ──
  var cross = await load('cross-repo-transfer');
  if (cross && cross.top_repos) {
    var ctx = document.getElementById('chart-cross-repo-transfer');
    if (ctx) { summary('cross-repo-transfer', cross);
      var repos = cross.top_repos.slice(0, 8);
      new Chart(ctx, { type:'bar', data: {
        labels: repos.map(function(r){return (r.name||r.repo||'').substring(0,18);}),
        datasets:[{ label:'Commits', data:repos.map(function(r){return r.commits||r.count||0;}),
          backgroundColor: repos.map(function(_,i){return PALETTE[i%PALETTE.length];}), borderRadius:4, barPercentage:0.7 }]
      }, options:{ indexAxis:'y', scales:{ x:{beginAtZero:true, grid:{color:'#1e2a3a'}}, y:{grid:{display:false}} } } });
    }
  }

  // ── Chart 12: YouTube Learning ──
  var yt = await load('youtube-learning-graph');
  if (yt && yt.monthly_learning) {
    var ctx = document.getElementById('chart-youtube-learning-graph');
    if (ctx) { summary('youtube-learning-graph', yt);
      new Chart(ctx, { type:'line', data: {
        labels: yt.monthly_learning.map(function(m){return m.month||m.period||'';}),
        datasets:[{ label:'Videos Watched', data:yt.monthly_learning.map(function(m){return m.count||m.videos||0;}),
          borderColor:colors.danger, backgroundColor:'rgba(248,113,113,0.1)', fill:true, tension:0.3, pointRadius:3, pointBackgroundColor:colors.danger }]
      }, options:{ scales:{ y:{beginAtZero:true, grid:{color:'#1e2a3a'}}, x:{grid:{display:false}, ticks:{maxRotation:45}} },
        plugins:{tooltip:{mode:'index',intersect:false}} } });
    }
  }

  // ── Chart 13: Architecture Timelapse ──
  var arch = await load('architecture-timelapse');
  if (arch && arch.era_snapshots && arch.era_snapshots.length) {
    var ctx = document.getElementById('chart-architecture-timelapse');
    if (ctx) { summary('architecture-timelapse', arch);
      var snaps = arch.era_snapshots;
      new Chart(ctx, { type:'bar', data: {
        labels: snaps.map(function(s){return (s.era||'').substring(0,14);}),
        datasets:[
          { label:'Commits', data:snaps.map(function(s){return s.commits||0;}), backgroundColor:colors.accent, borderRadius:4, barPercentage:0.4 },
          { label:'Restructurings', data:snaps.map(function(s){return s.restructuring_signals||0;}), backgroundColor:colors.warning, borderRadius:4, barPercentage:0.4 }
        ]
      }, options:{ scales:{ y:{beginAtZero:true, grid:{color:'#1e2a3a'}}, x:{grid:{display:false}} },
        plugins:{ legend:{display:true, labels:{boxWidth:10,padding:8}} } } });
    }
  }

  // ── Chart 14: Cognitive Load ──
  var cog = await load('commit-cognitive-load');
  if (cog && cog.work_type_distribution) {
    var ctx = document.getElementById('chart-commit-cognitive-load');
    if (ctx) { summary('commit-cognitive-load', cog);
      var types = cog.work_type_distribution;
      var labels = Object.keys(types);
      var vals = Object.values(types);
      new Chart(ctx, { type:'doughnut', data: {
        labels: labels.map(function(l){return l.replace(/_/g,' ');}),
        datasets:[{ data:vals, backgroundColor:labels.map(function(_,i){return PALETTE[i%PALETTE.length];}), borderWidth:0 }]
      }, options:{ cutout:'55%', plugins:{ legend:{display:true, position:'right', labels:{boxWidth:10,padding:8,font:{size:10}}} } } });
    }
  }
});
"""


def generate_project_index(project: dict[str, Any]) -> str:
    """Generate per-project dashboard with data visualizations front and center."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    meta = project["meta"]
    proj_name = project["name"].upper()
    commits = meta.get("commits", "?")
    eras = meta.get("era_count", "?")
    active_days = meta.get("active_days", "?")
    span_days = meta.get("span_days", "?")
    commits_fmt = f"{commits:,}" if isinstance(commits, int) else str(commits)
    total_deliv = project.get("total_deliverables", 0)

    # Check for opportunity data
    deliverables = project.get("deliverables", {})
    opp_files = deliverables.get("opportunity", [])
    has_opportunity = len(opp_files) > 0

    # Build file cards HTML (for collapsible section)
    cat_sections = ""
    for cat_name, cat_meta in CATEGORIES.items():
        files = deliverables.get(cat_name, [])
        if not files:
            continue
        file_cards = ""
        for f in files:
            href = f["href"].split("/", 1)[-1]
            if f["ext"] == ".md":
                link = f"../md-viewer.html?file={project['name']}/{href}"
            else:
                link = href
            ext_color = {"html": "#14b8a6", "md": "#8b5cf6", "json": "#f59e0b"}.get(f["ext"].lstrip("."), "#6a7888")
            file_cards += f'<a href="{link}" class="deliv-file"><span class="deliv-icon">{cat_meta["icon"]}</span><span class="deliv-name">{f["name"]}</span><span class="deliv-ext" style="color:{ext_color}">{f["ext"].lstrip(".").upper()}</span></a>\n'
        cat_sections += f'<div class="cat-section"><h3 class="cat-heading" style="border-left:3px solid {cat_meta["color"]};padding-left:10px"><span class="cat-icon">{cat_meta["icon"]}</span>{cat_meta["label"]}<span class="cat-count">{len(files)}</span></h3><div class="deliv-grid">{file_cards}</div></div>\n'

    # Build opportunity section (if data exists)
    opp_html = ""
    if has_opportunity:
        # Score cards
        score_cards = """
        <div class="score-card" id="score-mastery">
          <svg class="score-ring" viewBox="0 0 100 100"><circle class="score-ring-bg" cx="50" cy="50" r="42"/><circle class="score-ring-fill" cx="50" cy="50" r="42"/></svg>
          <div class="score-value">--</div><div class="score-label">AI Mastery</div><div class="score-sub">/ 100</div>
        </div>
        <div class="score-card" id="score-session">
          <svg class="score-ring" viewBox="0 0 100 100"><circle class="score-ring-bg" cx="50" cy="50" r="42"/><circle class="score-ring-fill" cx="50" cy="50" r="42"/></svg>
          <div class="score-value">--</div><div class="score-label">Session Quality</div><div class="score-sub">/ 10</div>
        </div>
        <div class="score-card" id="score-velocity">
          <svg class="score-ring" viewBox="0 0 100 100"><circle class="score-ring-bg" cx="50" cy="50" r="42"/><circle class="score-ring-fill" cx="50" cy="50" r="42"/></svg>
          <div class="score-value">--</div><div class="score-label">Learning Accel.</div><div class="score-sub">x factor</div>
        </div>
        <div class="score-card" id="score-frustration">
          <svg class="score-ring" viewBox="0 0 100 100"><circle class="score-ring-bg" cx="50" cy="50" r="42"/><circle class="score-ring-fill" cx="50" cy="50" r="42"/></svg>
          <div class="score-value">--</div><div class="score-label">Frustration Conv.</div><div class="score-sub">automated</div>
        </div>
        """

        # Viz cards
        viz_cards = ""
        for feat in _OPP_FEATURES:
            viz_cards += f"""
        <div class="viz-card">
          <div class="viz-card-head">
            <span class="viz-card-icon">{feat["icon"]}</span>
            <span class="viz-card-title">{feat["title"]}</span>
          </div>
          <div class="viz-card-body"><canvas id="chart-{feat["slug"]}"></canvas></div>
          <div class="viz-card-foot"><span id="summary-{feat["slug"]}">Loading...</span></div>
        </div>"""

        opp_html = f"""
      <div class="score-row">{score_cards}</div>
      <div class="viz-section">
        <h3 class="viz-section-title">Opportunity Analysis <span class="count">{len(opp_files)}</span></h3>
        <div class="viz-grid">{viz_cards}</div>
      </div>"""

    # Assemble HTML
    css = _PROJECT_INDEX_CSS
    js = _PROJECT_INDEX_JS

    files_section = ""
    if has_opportunity:
        files_section = f"""
      <button class="files-toggle" id="files-toggle">All Deliverable Files ({total_deliv})</button>
      <div class="files-body collapsed" id="files-body">{cat_sections}</div>"""
    else:
        files_section = cat_sections

    html = f"""<!DOCTYPE html>
<html lang="en" data-theme="editorial">
<head>
{head_bundle(
    title=f"{proj_name} — Project Dashboard",
    description=f"Archaeological analysis of {proj_name} — {commits_fmt} commits across {eras} eras",
    include_charts=True
)}
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --bg:#06090f;--surface:#0c1018;--surface2:#141a24;--surface3:#1c2432;
  --border:#1a2232;--border-hover:#2a3a52;
  --text:#e8ecf2;--text2:#8d99aa;--text3:#6a7888;
  --accent:#34d399;
  --font-display:'Space Grotesk',sans-serif;--font-body:'DM Sans',sans-serif;
  --font-mono:'JetBrains Mono',monospace;
  --radius-sm:6px;--radius-md:10px;--radius-lg:16px;
}}
html{{scroll-behavior:smooth;-webkit-font-smoothing:antialiased}}
body{{background:var(--bg);color:var(--text);font-family:var(--font-body);line-height:1.65}}

/* ── Nav ── */
.site-nav{{position:sticky;top:0;z-index:100;background:var(--surface);border-bottom:1px solid var(--border);padding:0 24px;display:flex;align-items:center;gap:12px;height:52px;font-family:var(--font-display);backdrop-filter:blur(12px)}}
.site-nav .nav-home{{font-weight:700;font-size:14px;letter-spacing:.02em;color:var(--text3);text-decoration:none;white-space:nowrap;padding:4px 10px;border-radius:var(--radius-sm);transition:color .15s,background .15s}}
.site-nav .nav-home:hover{{color:var(--text);background:var(--surface2)}}
.site-nav .nav-sep{{width:1px;height:24px;background:var(--border)}}
.site-nav .nav-project{{font-weight:600;font-size:15px;color:var(--text);letter-spacing:-.01em}}
.site-nav .nav-links{{display:flex;gap:4px;align-items:center;margin-left:auto}}
.site-nav .nav-links a{{font-size:13px;font-weight:500;color:var(--text2);text-decoration:none;padding:6px 12px;border-radius:var(--radius-sm);transition:color .15s,background .15s;white-space:nowrap}}
.site-nav .nav-links a:hover{{color:var(--text);background:var(--surface2)}}
.nav-hamburger{{display:none;background:none;border:none;color:var(--text2);font-size:22px;cursor:pointer;padding:4px 8px;margin-left:auto}}
@media(max-width:768px){{
  .site-nav{{padding:0 16px;flex-wrap:wrap;height:auto;min-height:52px}}
  .site-nav .nav-links{{display:none;flex-direction:column;width:100%;padding:8px 0 12px;gap:2px}}
  .site-nav .nav-links.open{{display:flex}}
  .site-nav .nav-links a{{padding:10px 12px;font-size:15px}}
  .nav-hamburger{{display:block}}
}}

/* ── Content ── */
.container{{max-width:1000px;margin:0 auto;padding:32px 24px 64px}}
.project-header{{margin-bottom:32px}}
.project-header h1{{font-family:var(--font-display);font-size:clamp(24px,4vw,32px);font-weight:700;letter-spacing:-.02em;margin-bottom:8px}}
.project-header p{{color:var(--text2);font-size:15px}}
.project-stats{{display:flex;gap:24px;margin-top:16px;flex-wrap:wrap}}
.pstat{{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-md);padding:12px 16px;min-width:100px}}
.pstat .val{{font-family:var(--font-display);font-size:22px;font-weight:600;color:var(--text)}}
.pstat .lbl{{font-size:11px;color:var(--text3);text-transform:uppercase;letter-spacing:.04em}}

/* ── Deliverable categories ── */
.cat-section{{margin-bottom:28px}}
.cat-heading{{font-family:var(--font-display);font-size:16px;font-weight:600;color:var(--text2);margin-bottom:12px;display:flex;align-items:center;gap:8px}}
.cat-icon{{font-size:18px}}
.cat-count{{font-size:11px;font-weight:500;color:var(--text3);background:var(--surface2);padding:2px 8px;border-radius:12px;font-family:var(--font-mono)}}
.deliv-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:8px}}
.deliv-file{{display:flex;align-items:center;gap:10px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-sm);padding:10px 14px;text-decoration:none;color:var(--text);transition:border-color .15s,transform .15s}}
.deliv-file:hover{{border-color:var(--border-hover);transform:translateX(2px)}}
.deliv-icon{{font-size:16px;flex-shrink:0}}
.deliv-name{{flex:1;font-size:13px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.deliv-ext{{font-size:10px;font-weight:600;font-family:var(--font-mono);flex-shrink:0}}

{css}

@media(max-width:768px){{
  .container{{padding:24px 16px 48px}}
  .project-stats{{gap:12px}}
  .pstat{{min-width:80px;padding:10px 12px}}
  .pstat .val{{font-size:18px}}
  .deliv-grid{{grid-template-columns:1fr}}
}}
</style>
</head>
<body>

<a class="skip-link" href="#root">Skip to content</a>

<nav class="site-nav">
  <a href="/" class="nav-home">Home</a>
  <div class="nav-sep"></div>
  <span class="nav-project">{proj_name}</span>
  <button class="nav-hamburger" onclick="document.querySelector('.nav-links').classList.toggle('open')" aria-label="Menu">&#9776;</button>
  {THEME_SWITCHER_HTML}
</nav>

<main id="root">
<div class="container">
  <div class="project-header">
    <h1>{proj_name}</h1>
    <p>{_project_description(project['name'], meta)}</p>
    <div class="project-stats">
      <div class="pstat"><span class="val">{commits_fmt}</span><span class="lbl">Commits</span></div>
      <div class="pstat"><span class="val">{eras if eras else '&mdash;'}</span><span class="lbl">Eras</span></div>
      <div class="pstat"><span class="val">{active_days}</span><span class="lbl">Active Days</span></div>
      <div class="pstat"><span class="val">{span_days}</span><span class="lbl">Day Span</span></div>
      <div class="pstat"><span class="val">{total_deliv if total_deliv else '&mdash;'}</span><span class="lbl">Deliverables</span></div>
    </div>
  </div>
  {opp_html}
  {files_section}
</div>
</main>

{body_end_bundle()}

<script>
// Toggle files section
(function(){{
  var toggle = document.getElementById('files-toggle');
  if (toggle) toggle.addEventListener('click', function() {{
    this.classList.toggle('collapsed');
    document.getElementById('files-body').classList.toggle('collapsed');
  }});
}})();
{js}
</script>
</body>
</html>"""
    return html


def _viz_description(name: str) -> str:
    """Return a short description for a visualization page."""
    descriptions = {
        "Dashboard": "Full archaeological dashboard with timeline, eras, heatmap, and telemetry",
        "Playbook": "Era-by-era narrative playbook with key events and patterns",
        "Agents": "AI agent performance benchmark comparing all coding agents",
        "Report": "Structured archaeological report with findings and analysis",
    }
    return descriptions.get(name, "Archaeological analysis visualization")


def _viz_icon(name: str) -> str:
    """Return an emoji icon for a visualization page."""
    icons = {
        "Dashboard": "&#128202;",
        "Playbook": "&#128214;",
        "Agents": "&#129302;",
        "Report": "&#128196;",
    }
    return icons.get(name, "&#128300;")


def load_api_repos(global_data_dir: Path) -> list[dict[str, Any]]:
    """Load repo metadata from fetch-github JSON files.

    Returns list of repo dicts sorted by commit count (descending).
    """
    repos = []
    for json_file in global_data_dir.glob("*-repos.json"):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            print(f"  WARNING: Failed to load {json_file.name}: {e}")
            continue
        for repo in data.get("repos", []):
            if repo.get("is_fork"):
                continue
            commits = repo.get("total_commits") or repo.get("commit_count", 0)
            repos.append({
                "name": repo.get("name", "?"),
                "commits": commits,
                "language": repo.get("language", ""),
                "description": repo.get("description", ""),
                "updated": (repo.get("updated_at") or repo.get("updated", ""))[:10],
                "owner": data.get("owner", ""),
                "html_url": repo.get("html_url", f"https://github.com/{data.get('owner', '')}/{repo.get('name', '')}"),
                "is_fork": repo.get("is_fork", False),
            })
    repos.sort(key=lambda r: r["commits"], reverse=True)
    return repos


def generate_global_section(api_repos: list[dict[str, Any]], owner_labels: dict[str, str] | None = None) -> str:
    """Generate an HTML section showing API-only repos (lightweight cards)."""
    if not api_repos:
        return ""

    labels = owner_labels or {}
    # Group by owner
    by_owner: dict[str, list] = {}
    for repo in api_repos:
        owner = repo["owner"]
        by_owner.setdefault(owner, []).append(repo)

    sections = ""
    for owner, owner_repos in by_owner.items():
        label = labels.get(owner, owner)
        total_commits = sum(r["commits"] for r in owner_repos)
        total_commits_fmt = f"{total_commits:,}"

        cards = ""
        for repo in owner_repos:
            commits_fmt = f"{repo['commits']:,}"
            lang = repo["language"] or ""
            desc = (repo["description"] or "")[:80]
            cards += f"""
            <div class="api-card" data-owner="{owner}">
              <div class="api-header">
                <a href="{repo['html_url']}" class="api-name" target="_blank">{repo['name']}</a>
                <span class="api-badge">{commits_fmt} commits</span>
              </div>
              <div class="api-meta">{lang} &middot; updated {repo['updated']}"</div>
              {f'<div class="api-desc">{desc}</div>' if desc else ''}
            </div>"""

        sections += f"""
      <div class="owner-section" data-owner="{owner}">
        <h3 class="owner-title">{label}<span class="owner-count">{len(owner_repos)} repos &middot; {total_commits_fmt} commits</span></h3>
        <div class="api-grid">
          {cards}
        </div>
      </div>"""

    return sections
