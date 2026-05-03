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

        # Discover HTML visualizations
        visuals = _discover_visuals(deliverables_dir, project_dir.name)

        projects.append({
            "name": project_dir.name,
            "slug": project_dir.name,
            "meta": meta,
            "visuals": visuals,
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
        fc = fm.get("commits", "?")
        fc_fmt = f"{fc:,}" if isinstance(fc, int) else str(fc)
        fe = fm.get("era_count", "?")
        fad = fm.get("active_days", "?")
        fviz = ""
        for viz in featured["visuals"]:
            fviz += f'<a href="{viz["href"]}" class="fviz-link">{viz["name"]}</a>\n            '
        featured_html = f"""
<div class="section-wrap">
  <a href="{featured['name']}/" class="featured-card">
    <div class="featured-main">
      <span class="featured-badge">Featured Project</span>
      <h2 class="featured-title">{featured['name'].upper()}</h2>
      <p class="featured-desc">Full archaeological analysis with era timeline, telemetry, and agent benchmarks</p>
      <div class="featured-stats">
        <div class="fstat"><span class="fstat-val">{fc_fmt}</span><span class="fstat-lbl">commits</span></div>
        <div class="fstat"><span class="fstat-val">{fe}</span><span class="fstat-lbl">eras</span></div>
        <div class="fstat"><span class="fstat-val">{fad}</span><span class="fstat-lbl">active days</span></div>
      </div>
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
        commits = meta.get("commits", "?")
        eras = meta.get("era_count", "?")
        active_days = meta.get("active_days", "?")
        n_visuals = len(proj["visuals"])
        commits_fmt = f"{commits:,}" if isinstance(commits, int) else str(commits)
        viz_links = ""
        for viz in proj["visuals"]:
            viz_links += f'<a href="{viz["href"]}" class="viz-link">{viz["name"]}</a>\n              '
        project_cards += f"""
        <a href="{proj['name']}/" class="project-card">
          <div class="card-header">
            <h2 class="card-title">{proj['name'].upper()}</h2>
            <span class="card-badge">{n_visuals} {'page' if n_visuals == 1 else 'pages'}</span>
          </div>
          <div class="card-stats">
            <div class="stat"><span class="stat-value">{commits_fmt}</span><span class="stat-label">commits</span></div>
            <div class="stat"><span class="stat-value">{eras}</span><span class="stat-label">eras</span></div>
            <div class="stat"><span class="stat-value">{active_days}</span><span class="stat-label">active days</span></div>
          </div>
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
    owners = set(r["owner"] for r in api_repos) | {"mined"}
    n_networks = len(owners)

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
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dev-Archaeology</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&family=JetBrains+Mono:wght@400;500&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
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
}}
</style>
</head>
<body>

<nav class="site-nav">
  <span class="nav-brand">Dev-Archaeology</span>
  <span class="nav-subtitle">Forensic Mining Dashboard</span>
  <span class="nav-meta">{total_repos} repos &middot; updated {now}</span>
</nav>

<div class="hero">
  <h1>Your Development Fossil Record</h1>
  <p>Forensic analysis of {total_repos} repositories across your entire development ecosystem</p>
  <div class="hero-stats">
    <div class="hero-stat"><span class="value">{total_repos_fmt}</span><span class="label">Repos</span></div>
    <div class="hero-stat"><span class="value">{total_commits_fmt}</span><span class="label">Commits</span></div>
    <div class="hero-stat"><span class="value">{n_networks}</span><span class="label">Networks</span></div>
  </div>
</div>

{featured_html}

{f'''<div class="section-wrap">
  <h3 class="section-heading">Mined Projects ({len(rest_projects)})</h3>
  <div class="grid">
  {project_cards}
  </div>
</div>''' if rest_projects else ""}

{global_viz_section}

{api_section}

<div class="footer">
  Generated by dev-archaeology &middot; {now}
</div>

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
</body>
</html>"""
    return html


def generate_project_index(project: dict[str, Any]) -> str:
    """Generate per-project index.html with overview and links to visualizations."""
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    meta = project["meta"]
    proj_name = project["name"].upper()

    commits = meta.get("commits", "?")
    eras = meta.get("era_count", "?")
    active_days = meta.get("active_days", "?")
    span_days = meta.get("span_days", "?")
    commits_fmt = f"{commits:,}" if isinstance(commits, int) else str(commits)

    # Build visualization cards
    viz_cards = ""
    for viz in project["visuals"]:
        href = viz["href"].split("/")[-1]  # Just the filename (same directory)
        desc = _viz_description(viz["name"])
        viz_cards += f"""
        <a href="{href}" class="viz-card">
          <div class="viz-icon">{_viz_icon(viz['name'])}</div>
          <div class="viz-info">
            <h3>{viz['name']}</h3>
            <p>{desc}</p>
          </div>
          <span class="viz-arrow">&rarr;</span>
        </a>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{proj_name} — Project Overview</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&family=JetBrains+Mono:wght@400;500&family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">

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
.container{{max-width:800px;margin:0 auto;padding:32px 24px 64px}}
.project-header{{margin-bottom:32px}}
.project-header h1{{font-family:var(--font-display);font-size:clamp(24px,4vw,32px);font-weight:700;letter-spacing:-.02em;margin-bottom:8px}}
.project-header p{{color:var(--text2);font-size:15px}}
.project-stats{{display:flex;gap:24px;margin-top:16px;flex-wrap:wrap}}
.pstat{{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-md);padding:12px 16px;min-width:100px}}
.pstat .val{{font-family:var(--font-display);font-size:22px;font-weight:600;color:var(--text)}}
.pstat .lbl{{font-size:11px;color:var(--text3);text-transform:uppercase;letter-spacing:.04em}}

.viz-list{{display:flex;flex-direction:column;gap:12px;margin-top:8px}}
.viz-card{{
  display:flex;align-items:center;gap:16px;
  background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-md);
  padding:16px 20px;text-decoration:none;color:var(--text);
  transition:border-color .2s,transform .2s;
}}
.viz-card:hover{{border-color:var(--border-hover);transform:translateX(4px)}}
.viz-icon{{font-size:24px;width:40px;text-align:center;flex-shrink:0}}
.viz-info{{flex:1}}
.viz-info h3{{font-family:var(--font-display);font-size:15px;font-weight:600;margin-bottom:2px}}
.viz-info p{{font-size:13px;color:var(--text3)}}
.viz-arrow{{color:var(--text3);font-size:18px}}

@media(max-width:768px){{
  .container{{padding:24px 16px 48px}}
  .project-stats{{gap:12px}}
  .pstat{{min-width:80px;padding:10px 12px}}
  .pstat .val{{font-size:18px}}
}}
</style>
</head>
<body>

<nav class="site-nav">
  <a href="/" class="nav-home">Home</a>
  <div class="nav-sep"></div>
  <span class="nav-project">{proj_name}</span>
  <button class="nav-hamburger" onclick="document.querySelector('.nav-links').classList.toggle('open')" aria-label="Menu">&#9776;</button>
</nav>

<div class="container">
  <div class="project-header">
    <h1>{proj_name}</h1>
    <p>Archaeological analysis of development history</p>
    <div class="project-stats">
      <div class="pstat"><span class="val">{commits_fmt}</span><span class="lbl">Commits</span></div>
      <div class="pstat"><span class="val">{eras}</span><span class="lbl">Eras</span></div>
      <div class="pstat"><span class="val">{active_days}</span><span class="lbl">Active Days</span></div>
      <div class="pstat"><span class="val">{span_days}</span><span class="lbl">Day Span</span></div>
    </div>
  </div>

  <h2 style="font-family:var(--font-display);font-size:16px;color:var(--text2);margin-bottom:16px">Visualizations</h2>
  <div class="viz-list">
    {viz_cards}
  </div>
</div>

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
