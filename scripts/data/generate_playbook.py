#!/usr/bin/env python3
"""Generate playbook.html for any archaeology project.

Creates a self-contained HTML page with era navigation, commit charts,
and narrative content derived from the project's data files.

Usage:
    python3 scripts/data/generate_playbook.py <project_name>
    python3 scripts/data/generate_playbook.py --all
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from archaeology.visualization.design_system import (
    head_bundle, body_end_bundle, THEME_SWITCHER_HTML
)

ROOT = Path(__file__).resolve().parents[2]

ERA_COLORS = [
    "#4ade80", "#f87171", "#fb923c", "#60a5fa", "#a78bfa",
    "#34d399", "#fbbf24", "#f472b6", "#38bdf8", "#a3e635",
    "#e879f9", "#2dd4bf", "#facc15", "#818cf8", "#fb7185",
]


def load_project(name: str) -> dict:
    pdir = ROOT / "projects" / name
    data = {"name": name}
    for key, path in [
        ("config", pdir / "project.json"),
        ("eras_data", pdir / "data" / "commit-eras.json"),
        ("metrics", pdir / "deliverables" / "canonical-metrics.json"),
    ]:
        if path.exists():
            data[key] = json.loads(path.read_text(encoding="utf-8"))

    ed = data.get("eras_data", {})
    data["eras"] = ed.get("eras", [])
    data["total_commits"] = ed.get("total_commits", 0)
    data["contributors"] = ed.get("contributors", [])
    data["commit_types"] = ed.get("commit_types", {})
    data["daily_freq"] = ed.get("daily_commit_frequency", {})
    data["lifespan"] = ed.get("lifespan", "")
    data["description"] = data.get("config", {}).get("description", "")
    m = data.get("metrics", {})
    data["active_days"] = m.get("active_days", len(data["daily_freq"]))
    data["span_days"] = m.get("span_days", 0)
    data["peak_day"] = m.get("peak_day", "")
    data["peak_day_commits"] = m.get("peak_day_commits", 0)
    data["era_count"] = len(data["eras"])
    return data


def generate_playbook(p: dict) -> str:
    name = p["name"]
    eras = p["eras"]
    era_colors_css = "\n".join(
        f"  --era-{e['id']:02d}:{ERA_COLORS[(e['id'] - 1) % len(ERA_COLORS)]};"
        for e in eras
    )

    # Era navigation strip
    era_strip_items = "\n".join(
        f'<a href="#era-{e["id"]}" class="era-segment" style="flex:{e.get("commits", 1)};background:var(--era-{e["id"]:02d})" title="{e.get("name", "")} ({e.get("dates", "")})">{e.get("name", "")[:12]}</a>'
        for e in eras
    )

    # Era sections
    era_sections = "\n".join(generate_era_section(e, p) for e in eras)

    # Commit type chart data
    commit_types = p.get("commit_types", {})
    type_labels = json.dumps(list(commit_types.keys()))
    type_values = json.dumps(list(commit_types.values()))
    type_colors = json.dumps([ERA_COLORS[i % len(ERA_COLORS)] for i in range(len(commit_types))])

    # Daily commit data for timeline chart
    daily = p.get("daily_freq", {})
    daily_labels = json.dumps(sorted(daily.keys()))
    daily_values = json.dumps([daily[d] for d in sorted(daily.keys())])

    return f"""<!DOCTYPE html>
<html lang="en" data-theme="editorial">
<head>
{head_bundle(
    title=f"{name} — Development Playbook",
    description=f"Narrative archaeology playbook for {name} — {p['total_commits']} commits across {p['era_count']} eras",
    include_charts=True
)}
<style>
/* Era-specific colors (domain-specific, defined after theme tokens) */
:root, [data-theme="warm"], [data-theme="editorial"], [data-theme="modern"] {{
{era_colors_css}
}}

/* Playbook-specific styles */
.chart-container{{position:relative;height:200px;width:100%}}

/* Hero */
.hero{{text-align:center;padding:4rem 2rem 2rem;border-bottom:1px solid var(--border)}}
.hero h1{{font-size:clamp(2rem,5vw,3.5rem);letter-spacing:-0.03em;margin-bottom:0.5rem}}
.hero .subtitle{{color:var(--text-2);font-size:1.1rem;margin-bottom:2rem}}
.stats-grid{{display:flex;justify-content:center;gap:2rem;flex-wrap:wrap}}
.stat{{text-align:center}}
.stat .value{{font-size:2rem;font-weight:700;font-family:var(--font-mono);color:var(--success)}}
.stat .label{{font-size:0.8rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.05em}}

/* Era strip */
.era-strip{{display:flex;height:48px;border-radius:var(--radius-md);overflow:hidden;border:1px solid var(--border);margin:2rem auto;max-width:900px}}
.era-strip a{{display:flex;align-items:center;justify-content:center;color:var(--bg-main);font-size:0.7rem;font-weight:600;font-family:var(--font-mono);text-decoration:none;text-shadow:0 1px 2px rgba(0,0,0,0.5);transition:filter .2s;min-width:40px;padding:0 8px;overflow:hidden;white-space:nowrap}}
.era-strip a:hover{{filter:brightness(1.2)}}

/* Era sections */
.era-section{{max-width:900px;margin:0 auto;padding:3rem 2rem;border-bottom:1px solid var(--border)}}
.era-header{{display:flex;align-items:center;gap:1rem;margin-bottom:1.5rem}}
.era-badge{{width:48px;height:48px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:1.2rem;font-weight:700;font-family:var(--font-mono);color:var(--bg-main);flex-shrink:0}}
.era-header h2{{font-size:1.5rem;margin:0}}
.era-header .dates{{color:var(--text-muted);font-size:0.85rem;font-family:var(--font-mono)}}
.era-stats{{display:flex;gap:1.5rem;margin:1rem 0;flex-wrap:wrap}}
.era-stats .stat .value{{font-size:1.3rem}}
.era-description{{color:var(--text-2);margin:1rem 0;line-height:1.8}}
.era-events{{list-style:none;padding:0}}
.era-events li{{padding:0.4rem 0 0.4rem 1.5rem;position:relative;color:var(--text-2);font-size:0.9rem}}
.era-events li::before{{content:'>';position:absolute;left:0;color:var(--secondary);font-family:var(--font-mono);font-weight:600}}

/* Charts section */
.charts-section{{max-width:900px;margin:0 auto;padding:3rem 2rem}}
.charts-section h2{{margin-bottom:1.5rem}}
.charts-grid{{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem}}
@media(max-width:700px){{.charts-grid{{grid-template-columns:1fr}}}}
.chart-card{{background:var(--bg-surface);border:1px solid var(--border);border-radius:var(--radius-md);padding:1rem}}
.chart-card h3{{font-size:0.9rem;color:var(--text-muted);margin-bottom:0.5rem}}

/* Footer */
footer{{text-align:center;padding:2rem;color:var(--text-muted);font-size:0.8rem;font-family:var(--font-mono);border-top:1px solid var(--border)}}
</style>
</head>
<body>

<a href="#main-content" class="skip-link">Skip to content</a>

<header style="padding: 1rem 2rem; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border);">
  <div style="font-family: var(--font-display); font-weight: 600; font-size: 1.2rem;">DevArch Playbook</div>
  {THEME_SWITCHER_HTML}
</header>

<main id="main-content">

<div class="hero">
  <h1>{name}</h1>
  <p class="subtitle">{p['description'] or 'DevArch Framework Playbook'}</p>
  <div class="stats-grid">
    <div class="stat"><div class="value">{p['total_commits']}</div><div class="label">Commits</div></div>
    <div class="stat"><div class="value">{p['era_count']}</div><div class="label">Eras</div></div>
    <div class="stat"><div class="value">{p['active_days']}</div><div class="label">Active Days</div></div>
    <div class="stat"><div class="value">{p['span_days']}</div><div class="label">Span (days)</div></div>
  </div>
</div>

<div class="era-strip">
  {era_strip_items}
</div>

{era_sections}

<div class="charts-section">
  <h2>Development Analytics</h2>
  <div class="charts-grid">
    <div class="chart-card">
      <h3>Commits per Day</h3>
      <div class="chart-container"><canvas id="timeline-chart"></canvas></div>
    </div>
    <div class="chart-card">
      <h3>Commit Types</h3>
      <div class="chart-container"><canvas id="types-chart"></canvas></div>
    </div>
  </div>
</div>

</main>

<footer>
  Generated by devarch dev-archaeology &middot;middot; {datetime.now().strftime("%Y-%m-%d")} &middot; {p['total_commits']} commits across {p['era_count']} eras
</footer>

<script>
// Rebuild charts with theme colors when theme changes
window._rebuildCharts = function() {{
  var colors = getThemeColors();

  // Update timeline chart
  var timelineChart = Chart.getChart('timeline-chart');
  if (timelineChart) {{
    timelineChart.options.scales.x.ticks.color = colors.muted;
    timelineChart.options.scales.x.ticks.font.color = colors.muted;
    timelineChart.options.scales.x.grid.color = colors.border;
    timelineChart.options.scales.y.ticks.color = colors.muted;
    timelineChart.options.scales.y.ticks.font.color = colors.muted;
    timelineChart.options.scales.y.grid.color = colors.border;
    timelineChart.update();
  }}

  // Update types chart
  var typesChart = Chart.getChart('types-chart');
  if (typesChart) {{
    typesChart.options.plugins.legend.labels.color = colors.text;
    typesChart.update();
  }}
}};

// Timeline chart
new Chart(document.getElementById('timeline-chart'), {{
  type: 'bar',
  data: {{
    labels: {daily_labels},
    datasets: [{{label: 'Commits', data: {daily_values}, backgroundColor: 'var(--success)', borderColor: 'var(--success)', borderWidth: 1}}]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{legend: {{display: false}}}},
    scales: {{
      x: {{ticks: {{color: getThemeColors().muted, font: {{family: 'var(--font-mono)', size: 9}}}}, grid: {{color: getThemeColors().border}}}},
      y: {{ticks: {{color: getThemeColors().muted, font: {{family: 'var(--font-mono)'}}}}, grid: {{color: getThemeColors().border}}}}
    }}
  }}
}});

// Types chart
new Chart(document.getElementById('types-chart'), {{
  type: 'doughnut',
  data: {{
    labels: {type_labels},
    datasets: [{{data: {type_values}, backgroundColor: {type_colors}}}]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{legend: {{position: 'right', labels: {{color: getThemeColors().text, font: {{family: 'var(--font-mono)', size: 11}}}}}}}}
  }}
}});
</script>

{body_end_bundle()}
</body>
</html>"""


def generate_era_section(era: dict, p: dict) -> str:
    color = ERA_COLORS[(era["id"] - 1) % len(ERA_COLORS)]
    events = era.get("key_events", [])
    events_html = "\n".join(f"<li>{evt}</li>" for evt in events[:10])
    daily = era.get("daily", {})
    active = len(daily)

    return f"""<div class="era-section" id="era-{era['id']}">
  <div class="era-header">
    <div class="era-badge" style="background:{color}">{era['id']}</div>
    <div>
      <h2>{era.get('name', f'Era {era["id"]}')}</h2>
      <div class="dates">{era.get('dates', '')}</div>
    </div>
  </div>
  <div class="era-stats">
    <div class="stat"><div class="value" style="color:{color}">{era.get('commits', '?')}</div><div class="label">Commits</div></div>
    <div class="stat"><div class="value" style="color:{color}">{active}</div><div class="label">Active Days</div></div>
  </div>
  <p class="era-description">{era.get('description', '')}</p>
  {'<ul class="era-events">' + events_html + '</ul>' if events_html else ''}
</div>"""


def main():
    if len(sys.argv) < 2:
        print("Usage: generate_playbook.py <project_name> | --all")
        sys.exit(1)

    if sys.argv[1] == "--all":
        for name in ["Achiote", "DECLuTTER-AI", "DialectOS", "Epoch", "Fugax", "mcp-video", "openglaze"]:
            p = load_project(name)
            html = generate_playbook(p)
            out = ROOT / "projects" / name / "deliverables" / "visuals" / "playbook.html"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(html, encoding="utf-8")
            print(f"  + {name}/deliverables/visuals/playbook.html")
    else:
        name = sys.argv[1]
        p = load_project(name)
        html = generate_playbook(p)
        out = ROOT / "projects" / name / "deliverables" / "visuals" / "playbook.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        print(f"  + {name}/deliverables/visuals/playbook.html")


if __name__ == "__main__":
    main()
