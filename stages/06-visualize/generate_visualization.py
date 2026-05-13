#!/usr/bin/env python3
"""Stage 06-Visualize: Generate HTML Visualization using DevArch design system."""

import json
import sys
from pathlib import Path
from collections import defaultdict

# Resolve repo root: stages/06-visualize/generate_visualization.py -> repo root
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SIGNALS_PATH = REPO_ROOT / "stages" / "04-detect" / "output" / "detected-signals.json"
ANALYSIS_DIR = REPO_ROOT / "stages" / "05-analyze" / "output"
OUTPUT_PATH = Path(__file__).resolve().parent / "output" / "archaeology.html"

# Add repo root to path so we can import the design system
sys.path.insert(0, str(REPO_ROOT))

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_data():
    """Load all analysis data."""
    with open(SIGNALS_PATH, "r") as f:
        signals = json.load(f)

    analyses = {}
    for analysis_file in ANALYSIS_DIR.glob("analysis-*.json"):
        with open(analysis_file, "r") as f:
            analyses[analysis_file.stem] = json.load(f)

    return signals, analyses


def prepare_chart_data(signals, analyses):
    """Prepare data for all charts."""
    daily_breakdown = signals.get("daily_breakdown", {})
    sorted_days = sorted(daily_breakdown.keys())

    timeline_data = {
        "type": "timeline",
        "data": {
            "dates": sorted_days,
            "commits": [daily_breakdown[day] for day in sorted_days],
            "signals": [
                {
                    "date": s["date"],
                    "type": s["type"],
                    "label": s.get("metadata", {}).get("description", s["type"]),
                }
                for s in signals.get("signals", [])
                if s["type"] in ["gap", "velocity_shift"]
            ],
        },
    }

    # Author distribution — computed from database, not hardcoded
    import sqlite3

    DB_PATH = REPO_ROOT / "stages" / "03-build" / "output" / "archaeology.db"
    if DB_PATH.exists():
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT author, COUNT(*) as cnt FROM commits GROUP BY author ORDER BY cnt DESC")
        author_rows = cursor.fetchall()
        cursor.execute("SELECT message FROM commits")
        commit_messages = [row[0] for row in cursor.fetchall()]
        conn.close()
    else:
        author_rows = []
        commit_messages = []

    authors = [row[0] for row in author_rows]
    author_counts = [row[1] for row in author_rows]
    total_author_commits = sum(author_counts) or 1
    author_percentages = [round(c / total_author_commits * 100, 1) for c in author_counts]

    author_data = {
        "type": "author_distribution",
        "data": {
            "authors": authors,
            "commits": author_counts,
            "percentages": author_percentages,
        },
    }

    # Commit type distribution
    type_counts = defaultdict(int)
    for msg in commit_messages:
        msg_lower = msg.lower()
        for prefix in ("feat:", "fix:", "test:", "docs:", "chore:", "refactor:"):
            if msg_lower.startswith(prefix):
                type_counts[prefix.rstrip(":")] += 1
                break
        else:
            type_counts["other"] += 1

    commit_type_data = {
        "type": "commit_type_distribution",
        "data": {
            "types": ["feat", "fix", "test", "docs", "chore", "refactor", "other"],
            "counts": [
                type_counts["feat"],
                type_counts["fix"],
                type_counts["test"],
                type_counts["docs"],
                type_counts["chore"],
                type_counts["refactor"],
                type_counts["other"],
            ],
        },
    }

    signal_summary = {
        "type": "signal_summary",
        "data": signals.get("summary", {}).get("by_type", {}),
    }

    return {
        "timeline": timeline_data,
        "author_distribution": author_data,
        "commit_type": commit_type_data,
        "signal_summary": signal_summary,
    }


def generate_html(signals, analyses, chart_data):
    """Generate the complete HTML visualization using the DevArch design system."""
    from archaeology.visualization.design_system import (
        ACCESSIBILITY_CSS,
        CHART_THEME_JS,
        FAVICON,
        GOOGLE_FONTS_LINK,
        THEME_CSS,
        THEME_SWITCHER_CSS,
        THEME_SWITCHER_HTML,
        THEME_SWITCHER_JS,
        head_bundle,
        seo_meta,
    )

    # Extract key metrics
    total_commits = signals.get("total_commits", 0)
    active_days = signals.get("active_days", 0)
    span_days = signals.get("span_days", 0)
    date_range = signals.get("date_range", "")

    daily_breakdown = signals.get("daily_breakdown", {})
    peak_day = max(daily_breakdown.items(), key=lambda x: x[1]) if daily_breakdown else ("N/A", 0)
    signals_by_type = signals.get("summary", {}).get("by_type", {})

    commit_type_counts = chart_data["commit_type"]["data"]["counts"]
    total_type_commits = sum(commit_type_counts) or 1
    commit_type_percentages = [
        round(c / total_type_commits * 100, 1) for c in commit_type_counts
    ]

    author_labels = json.dumps(chart_data["author_distribution"]["data"]["authors"])
    author_values = json.dumps(chart_data["author_distribution"]["data"]["commits"])

    project_name = "Achiote"
    page_title = f"{project_name} - Archaeology Visualization"
    page_description = f"Forensic archaeology visualization for {project_name}: {total_commits} commits across {active_days} active days over a {span_days}-day span."
    structured_data = {
        "@context": "https://schema.org",
        "@type": "Dataset",
        "name": f"{project_name} Git Archaeology",
        "description": page_description,
    }

    head = head_bundle(
        title=page_title,
        description=page_description,
        include_charts=True,
        json_ld=structured_data,
    )

    html = f"""<!DOCTYPE html>
<html lang="en" data-theme="editorial">
<head>
{head}
</head>
<body>
<a href="#main-content" class="skip-link">Skip to content</a>

<header style="padding: var(--space-10) var(--space-6); border-bottom: 1px solid var(--border);">
  <div style="max-width: 1200px; margin: 0 auto; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: var(--space-4);">
    <div>
      <h1 style="font-family: var(--font-display); font-size: clamp(1.8rem, 4vw, 2.8rem); margin: 0;">
        {project_name}
      </h1>
      <p style="color: var(--text-2); font-size: var(--text-lg); margin-top: var(--space-1);">
        Archaeology Visualization
      </p>
    </div>
    {THEME_SWITCHER_HTML}
  </div>
</header>

<main id="main-content" style="max-width: 1200px; margin: 0 auto; padding: var(--space-8) var(--space-6);">
  <section aria-label="Key Metrics" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: var(--space-4); margin-bottom: var(--space-10);">
    <div class="metric-card" style="background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: var(--space-5); text-align: center;">
      <div style="font-size: 2.2rem; font-weight: 700; color: var(--accent);">{total_commits}</div>
      <div style="color: var(--text-2); font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; margin-top: var(--space-1);">Total Commits</div>
    </div>
    <div class="metric-card" style="background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: var(--space-5); text-align: center;">
      <div style="font-size: 2.2rem; font-weight: 700; color: var(--accent);">{active_days}</div>
      <div style="color: var(--text-2); font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; margin-top: var(--space-1);">Active Days</div>
    </div>
    <div class="metric-card" style="background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: var(--space-5); text-align: center;">
      <div style="font-size: 2.2rem; font-weight: 700; color: var(--accent);">{span_days}</div>
      <div style="color: var(--text-2); font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; margin-top: var(--space-1);">Project Span (days)</div>
    </div>
    <div class="metric-card" style="background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: var(--space-5); text-align: center;">
      <div style="font-size: 2.2rem; font-weight: 700; color: var(--accent);">{peak_day[1]}</div>
      <div style="color: var(--text-2); font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; margin-top: var(--space-1);">Peak Day Commits</div>
    </div>
    <div class="metric-card" style="background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: var(--space-5); text-align: center;">
      <div style="font-size: 2.2rem; font-weight: 700; color: var(--accent);">{round(total_commits / active_days, 1) if active_days > 0 else 0}</div>
      <div style="color: var(--text-2); font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; margin-top: var(--space-1);">Avg Commits/Day</div>
    </div>
    <div class="metric-card" style="background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: var(--space-5); text-align: center;">
      <div style="font-size: 2.2rem; font-weight: 700; color: var(--accent);">{date_range}</div>
      <div style="color: var(--text-2); font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.05em; margin-top: var(--space-1);">Date Range</div>
    </div>
  </section>

  <section aria-label="Charts" style="display: grid; gap: var(--space-6);">
    <div style="background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: var(--space-6);">
      <h2 style="font-family: var(--font-display); margin-bottom: var(--space-4);">Daily Commit Activity</h2>
      <canvas id="timelineChart" role="img" aria-label="Bar chart showing daily commit activity"></canvas>
    </div>

    <div style="background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: var(--space-6);">
      <h2 style="font-family: var(--font-display); margin-bottom: var(--space-4);">Author Distribution</h2>
      <canvas id="authorChart" role="img" aria-label="Doughnut chart showing commit distribution by author"></canvas>
    </div>

    <div style="background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: var(--space-6);">
      <h2 style="font-family: var(--font-display); margin-bottom: var(--space-4);">Commit Type Distribution</h2>
      <canvas id="typeChart" role="img" aria-label="Pie chart showing commit types"></canvas>
    </div>

    <div style="background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: var(--space-6);">
      <h2 style="font-family: var(--font-display); margin-bottom: var(--space-4);">Signal Detection Summary</h2>
      <canvas id="signalChart" role="img" aria-label="Horizontal bar chart showing detected signals by type"></canvas>
    </div>
  </section>

  <section aria-label="Detected Signals" style="margin-top: var(--space-10);">
    <div style="background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: var(--space-6);">
      <h2 style="font-family: var(--font-display); margin-bottom: var(--space-4);">Detected Signals</h2>
      <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: var(--space-3);">
        {generate_signals_html(signals.get("signals", [])[:20])}
      </div>
    </div>
  </section>

  <section aria-label="Key Analysis Findings" style="margin-top: var(--space-6);">
    <div style="background: var(--bg-surface); border: 1px solid var(--border); border-radius: var(--radius-lg); padding: var(--space-6);">
      <h2 style="font-family: var(--font-display); margin-bottom: var(--space-4);">Key Analysis Findings</h2>
      {generate_findings_html(analyses)}
    </div>
  </section>
</main>

<footer style="padding: var(--space-6); text-align: center; color: var(--text-2); font-size: var(--text-sm); border-top: 1px solid var(--border); margin-top: var(--space-12);">
  Generated by <strong>DevArch Framework</strong> &mdash; Forensic Repository Archaeology
</footer>

<script>
  // Timeline Chart
  new Chart(document.getElementById('timelineChart').getContext('2d'), {{
    type: 'bar',
    data: {{
      labels: {json.dumps(sorted(daily_breakdown.keys()))},
      datasets: [{{label: 'Commits', data: {json.dumps([daily_breakdown[day] for day in sorted(daily_breakdown.keys())])}, backgroundColor: 'rgba(102, 126, 234, 0.8)', borderColor: 'rgba(102, 126, 234, 1)', borderWidth: 1}}]
    }},
    options: {{responsive: true, plugins: {{legend: {{display: false}}}}, scales: {{y: {{beginAtZero: true}}, x: {{}}}}}}
  }});

  // Author Distribution
  new Chart(document.getElementById('authorChart').getContext('2d'), {{
    type: 'doughnut',
    data: {{
      labels: {author_labels},
      datasets: [{{data: {author_values}, borderWidth: 2}}]
    }},
    options: {{responsive: true, plugins: {{legend: {{position: 'bottom'}}}}}}
  }});

  // Commit Type Distribution
  new Chart(document.getElementById('typeChart').getContext('2d'), {{
    type: 'pie',
    data: {{
      labels: ['feat', 'fix', 'test', 'docs', 'chore', 'refactor', 'other'],
      datasets: [{{data: {json.dumps(commit_type_counts)}, borderWidth: 2}}]
    }},
    options: {{responsive: true, plugins: {{legend: {{position: 'bottom', labels: {{generateLabels: function(chart) {{const data = chart.data; return data.labels.map((label, i) => ({{text: label + ' (' + {json.dumps(commit_type_percentages)}[i] + '%)', fillStyle: data.datasets[0].backgroundColor[i], hidden: false, index: i}}));}}}}}}}}}}
  }});

  // Signal Summary
  new Chart(document.getElementById('signalChart').getContext('2d'), {{
    type: 'bar',
    data: {{
      labels: {json.dumps(list(signals_by_type.keys()))},
      datasets: [{{label: 'Signals', data: {json.dumps(list(signals_by_type.values()))}, borderWidth: 1}}]
    }},
    options: {{responsive: true, indexAxis: 'y', plugins: {{legend: {{display: false}}}}, scales: {{x: {{beginAtZero: true}}}}}}
  }});
</script>
{THEME_SWITCHER_JS}
</body>
</html>"""

    return html


def generate_signals_html(signals):
    """Generate HTML for signals list."""
    html = []
    for signal in signals:
        signal_type = signal.get("type", "unknown")
        date = signal.get("date", "N/A")
        description = signal.get("metadata", {}).get("description", signal_type)

        html.append(f"""
        <div style="background: var(--bg-main); border-left: 3px solid var(--accent); padding: var(--space-3) var(--space-4); border-radius: 0 var(--radius-sm) var(--radius-sm) 0;">
          <div style="font-weight: 600; color: var(--accent); margin-bottom: var(--space-1);">{signal_type.replace('_', ' ').title()}</div>
          <div style="color: var(--text-2); font-size: var(--text-sm);">{date}</div>
          <div style="margin-top: var(--space-1);">{description}</div>
        </div>""")

    return "".join(html)


def generate_findings_html(analyses):
    """Generate HTML for key findings."""
    html = []
    for analysis_name, analysis_data in analyses.items():
        vector_name = analysis_data.get("vector_name", analysis_name)
        findings = analysis_data.get("findings", [])[:3]

        html.append(f'<h3 style="font-family: var(--font-display); margin-top: var(--space-5); margin-bottom: var(--space-3);">{vector_name}</h3>')

        for finding in findings:
            finding_type = finding.get("type", "Unknown")
            description = finding.get("description", "")
            confidence = finding.get("confidence", "low")
            conf_color = {"high": "#22c55e", "medium": "#eab308", "low": "#ef4444"}.get(confidence, "#a1a1aa")

            html.append(f"""
        <div style="padding: var(--space-3) 0; border-bottom: 1px solid var(--border);">
          <div style="font-weight: 600; color: var(--accent); margin-bottom: var(--space-1);">{finding_type}</div>
          <div style="margin-bottom: var(--space-1);">{description}</div>
          <span style="display: inline-block; padding: 2px 8px; border-radius: var(--radius-sm); font-size: 0.8em; font-weight: 600; background: {conf_color}22; color: {conf_color};">{confidence.upper()}</span>
        </div>""")

    return "".join(html)


if __name__ == "__main__":
    print("Loading analysis data...")
    signals, analyses = load_data()

    print("Preparing chart data...")
    chart_data = prepare_chart_data(signals, analyses)

    print("Generating HTML visualization...")
    html = generate_html(signals, analyses, chart_data)

    with open(OUTPUT_PATH, "w") as f:
        f.write(html)

    print(f"Stage 06-Visualize completed")
    print(f"  Output written to: {OUTPUT_PATH}")
