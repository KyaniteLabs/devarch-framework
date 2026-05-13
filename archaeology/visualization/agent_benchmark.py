"""Agent performance benchmark analysis for archaeology projects.

This module analyzes commit data to produce per-agent metrics across different
development eras, providing insights into AI agent contribution patterns.
"""

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

from archaeology.visualization.design_system import (
    head_bundle, body_end_bundle, THEME_SWITCHER_HTML
)


def analyze_agent_benchmarks(db_path: str) -> Dict[str, Any]:
    """Analyze agent performance metrics from archaeology database.

    Args:
        db_path: Path to archaeology.db SQLite database

    Returns:
        Dictionary containing benchmark data for all agents:
        {
            "agents": [
                {
                    "name": "Agent Name",
                    "total_commits": 123,
                    "commits_per_era": {"era_name": count, ...},
                    "avg_files_changed": 2.5,
                    "rework_rate": 0.15,
                    "avg_message_length": 45.3,
                    "first_commit": "2026-03-19",
                    "last_commit": "2026-04-30"
                },
                ...
            ],
            "eras": ["era1", "era2", ...],
            "meta": {
                "total_commits": 803,
                "total_agents": 5,
                "date_range": "2026-02-28 to 2026-05-01"
            }
        }
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Check if eras table exists
    has_eras = cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='eras'"
    ).fetchone() is not None

    # Get era information (optional)
    eras = {}
    era_date_ranges = {}
    if has_eras:
        eras_data = cursor.execute(
            "SELECT id, name FROM eras ORDER BY id"
        ).fetchall()
        eras = {row["id"]: row["name"] for row in eras_data}
    era_ids = list(eras.keys())

    # Build era date ranges for mapping commits
    era_date_ranges = {}
    if has_eras:
        for row in eras_data:
            era_id = row["id"]
            dates_str = cursor.execute(
                f"SELECT dates FROM eras WHERE id = {era_id}"
            ).fetchone()["dates"]
            era_date_ranges[era_id] = dates_str

    # Simpler approach: get all commits and map to eras in Python
    commits = cursor.execute(
        "SELECT hash, date, message, author FROM commits ORDER BY date"
    ).fetchall()

    # Build era date mappings manually
    era_mappings = []
    if has_eras:
        for era_id, era_name in eras.items():
            era_row = cursor.execute(
                f"SELECT dates, sub_phases FROM eras WHERE id = {era_id}"
            ).fetchone()

            dates_str = era_row["dates"]
            sub_phases_str = era_row["sub_phases"]

        # Parse the main era date range
        # Format: "Feb 28 - Mar 18"
        if " - " in dates_str:
            start_str, end_str = dates_str.split(" - ")
            # Add year
            start_date = f"{start_str}, 2026"
            end_date = f"{end_str}, 2026"
        else:
            start_date = None
            end_date = None

        era_mappings.append({
            "id": era_id,
            "name": era_name,
            "start": start_date,
            "end": end_date
        })

    # Map commits to eras
    import re
    from datetime import datetime

    def parse_abbreviated_date(date_str: str) -> datetime:
        """Parse dates like 'Feb 28, 2026' or 'Mar 19, 2026'."""
        # Remove weekday names if present
        date_str = re.sub(r'^[A-Z][a-z]{2}\s+', '', date_str)
        # Parse with format
        try:
            return datetime.strptime(date_str, "%b %d, %Y")
        except ValueError:
            # Try parsing from git log format
            return datetime.strptime(date_str.split()[0], "%Y-%m-%d")

    # Normalize agent names - treat Simon variants as "Simon"
    def normalize_author(author: str) -> str:
        """Normalize author names to canonical agent names."""
        author_lower = author.lower()
        if "simon" in author_lower:
            return "Simon"
        elif author_lower == "claude":
            return "Claude"
        elif author_lower == "kai":
            return "Kai"
        elif author_lower == "cursor":
            return "Cursor"
        elif author_lower == "kimicode":
            return "KimiCode"
        elif author_lower == "codex":
            return "Codex"
        elif author_lower == "demo-project":
            return "demo-project"
        else:
            return author

    # Group commits by agent and era
    agent_stats: Dict[str, Dict[str, Any]] = {}

    for commit in commits:
        author = normalize_author(commit["author"])
        commit_date_str = commit["date"]

        # Parse commit date
        try:
            # Git log format: "2026-03-19 21:30:56 -0700"
            commit_date = datetime.strptime(commit_date_str.split()[0], "%Y-%m-%d")
        except (ValueError, IndexError):
            continue

        # Find which era this commit belongs to
        commit_era = None
        for era_mapping in era_mappings:
            if era_mapping["start"] and era_mapping["end"]:
                try:
                    start_dt = parse_abbreviated_date(era_mapping["start"])
                    end_dt = parse_abbreviated_date(era_mapping["end"])
                    if start_dt <= commit_date <= end_dt:
                        commit_era = era_mapping["name"]
                        break
                except ValueError:
                    continue

        # Initialize agent stats if needed
        if author not in agent_stats:
            agent_stats[author] = {
                "name": author,
                "total_commits": 0,
                "commits_per_era": {},
                "message_lengths": [],
                "rework_commits": 0,
                "first_commit": commit_date_str,
                "last_commit": commit_date_str,
                "all_dates": []
            }

        # Update stats
        agent_stats[author]["total_commits"] += 1
        agent_stats[author]["all_dates"].append(commit_date_str)

        if commit_era:
            if commit_era not in agent_stats[author]["commits_per_era"]:
                agent_stats[author]["commits_per_era"][commit_era] = 0
            agent_stats[author]["commits_per_era"][commit_era] += 1

        # Track message length
        message = commit["message"] or ""
        agent_stats[author]["message_lengths"].append(len(message))

        # Track rework (fix/revert commits)
        if re.search(r'\bfix|revert|oops|undo\b', message, re.IGNORECASE):
            agent_stats[author]["rework_commits"] += 1

        # Update date range
        try:
            commit_dt = datetime.strptime(commit_date_str.split()[0], "%Y-%m-%d")
            first_dt = datetime.strptime(agent_stats[author]["first_commit"].split()[0], "%Y-%m-%d")
            last_dt = datetime.strptime(agent_stats[author]["last_commit"].split()[0], "%Y-%m-%d")
            if commit_dt < first_dt:
                agent_stats[author]["first_commit"] = commit_date_str
            if commit_dt > last_dt:
                agent_stats[author]["last_commit"] = commit_date_str
        except (ValueError, IndexError):
            pass

    # Compute final metrics per agent
    agents_list = []
    for agent_name, stats in agent_stats.items():
        avg_message_length = (
            sum(stats["message_lengths"]) / len(stats["message_lengths"])
            if stats["message_lengths"] else 0
        )
        rework_rate = (
            stats["rework_commits"] / stats["total_commits"]
            if stats["total_commits"] > 0 else 0
        )

        # Parse first and last commit dates for display
        try:
            first_date = datetime.strptime(stats["first_commit"].split()[0], "%Y-%m-%d").strftime("%Y-%m-%d")
            last_date = datetime.strptime(stats["last_commit"].split()[0], "%Y-%m-%d").strftime("%Y-%m-%d")
        except (ValueError, IndexError):
            first_date = stats["first_commit"][:10]
            last_date = stats["last_commit"][:10]

        agent_data = {
            "name": agent_name,
            "total_commits": stats["total_commits"],
            "commits_per_era": stats["commits_per_era"],
            "avg_files_changed": 0,  # Would need git log --numstat for this
            "rework_rate": round(rework_rate * 100, 1),  # Percentage
            "avg_message_length": round(avg_message_length, 1),
            "first_commit": first_date,
            "last_commit": last_date
        }
        agents_list.append(agent_data)

    # Sort by total commits
    agents_list.sort(key=lambda x: x["total_commits"], reverse=True)

    # Compute metadata
    total_commits = sum(a["total_commits"] for a in agents_list)

    # Get overall date range
    all_dates = []
    for stats in agent_stats.values():
        all_dates.extend(stats["all_dates"])

    date_range = "Unknown"
    if all_dates:
        try:
            dates_sorted = sorted(set(
                datetime.strptime(d.split()[0], "%Y-%m-%d") for d in all_dates
            ))
            if dates_sorted:
                date_range = f"{dates_sorted[0].strftime('%Y-%m-%d')} to {dates_sorted[-1].strftime('%Y-%m-%d')}"
        except ValueError:
            pass

    return {
        "agents": agents_list,
        "eras": list(eras.values()),
        "meta": {
            "total_commits": total_commits,
            "total_agents": len(agents_list),
            "date_range": date_range
        }
    }


def generate_benchmark_html(benchmark_data: Dict[str, Any], project_name: str) -> str:
    """Generate standalone HTML file for agent benchmark visualization.

    Args:
        benchmark_data: Output from analyze_agent_benchmarks()
        project_name: Name of the project for title

    Returns:
        Complete HTML document as string
    """
    agents = benchmark_data["agents"]
    eras = benchmark_data["eras"]
    meta = benchmark_data["meta"]

    # Prepare data for D3.js
    agents_json = json.dumps(agents)
    eras_json = json.dumps(eras)

    title = f"{project_name.upper()} — Agent Performance Benchmark"
    description = f"AI agent contribution analysis for {project_name.upper()}"

    # Custom CSS for benchmark-specific elements
    custom_css = """
<style>
/* ── Agent-specific color tokens ── */
:root, [data-theme="warm"], [data-theme="editorial"], [data-theme="modern"] {
  --kai: #ff6b6b;
  --cursor: #ffa94d;
  --claude: #51cf66;
  --unknown: #495057;
  --kimicode: #a78bfa;
  --codex: #60a5fa;
  --simon: #fbbf24;
}

/* ── Layout ── */
.container {
  max-width: var(--max-width);
  margin: 0 auto;
  padding: var(--space-8) var(--space-4);
}

/* ── Navigation ── */
.site-nav {
  position: sticky;
  top: 0;
  z-index: 100;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border);
  padding: 0 var(--space-6);
  display: flex;
  align-items: center;
  gap: var(--space-3);
  height: 52px;
  font-family: var(--font-display);
  backdrop-filter: blur(12px);
}

.site-nav .nav-back {
  font-weight: 500;
  font-size: 13px;
  color: var(--text-muted);
  text-decoration: none;
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-sm);
  transition: background var(--transition);
  white-space: nowrap;
}

.site-nav .nav-back:hover {
  color: var(--text);
  background: var(--bg-card);
}

.site-nav .nav-sep {
  width: 1px;
  height: 24px;
  background: var(--border);
}

.site-nav .nav-title {
  font-weight: 600;
  font-size: 15px;
  color: var(--text);
  letter-spacing: -0.01em;
}

/* ── Header ── */
.header {
  margin-bottom: var(--space-12);
  padding-top: var(--space-4);
}

.header h1 {
  font-size: 2.5rem;
  margin-bottom: var(--space-2);
  font-family: var(--font-display);
  font-weight: 600;
  letter-spacing: -0.01em;
}

.header p {
  color: var(--text-muted);
  font-size: 1.1rem;
}

/* ── Stats Grid ── */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--space-4);
  margin-bottom: var(--space-12);
}

.stat-card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: var(--space-6);
}

.stat-value {
  font-size: 2rem;
  font-weight: 700;
  font-family: var(--font-display);
  color: var(--text);
}

.stat-label {
  color: var(--text-muted);
  font-size: 0.875rem;
  margin-top: var(--space-1);
}

/* ── Charts ── */
.chart-section {
  margin-bottom: var(--space-12);
}

.chart-container {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: var(--space-8);
}

.chart-title {
  font-size: 1.25rem;
  margin-bottom: var(--space-6);
  font-family: var(--font-display);
  font-weight: 600;
}

/* ── Table ── */
table {
  width: 100%;
  border-collapse: collapse;
  margin-top: var(--space-4);
}

th {
  text-align: left;
  padding: var(--space-3) var(--space-4);
  border-bottom: 2px solid var(--border);
  color: var(--text-muted);
  font-size: 0.875rem;
  font-weight: 500;
}

td {
  padding: var(--space-3) var(--space-4);
  border-bottom: 1px solid var(--border);
}

tr:last-child td {
  border-bottom: none;
}

tr:hover td {
  background: var(--bg-card);
}

/* ── Typography ── */
.mono {
  font-family: var(--font-mono);
  font-size: 0.875rem;
}

/* ── Responsive ── */
@media (max-width: 768px) {
  .stats-grid {
    grid-template-columns: 1fr;
  }

  table {
    font-size: 0.875rem;
  }

  th, td {
    padding: var(--space-2);
  }

  .header h1 {
    font-size: 1.75rem;
  }
}
</style>
"""

    # JavaScript with theme-aware colors
    js_code = f"""
<script>
// Data
const agents = {agents_json};
const eras = {eras_json};

// Get theme colors from CSS variables
function getThemeColors() {{
  const s = getComputedStyle(document.documentElement);
  return {{
    accent:    s.getPropertyValue('--accent').trim(),
    secondary: s.getPropertyValue('--secondary').trim(),
    text:      s.getPropertyValue('--text').trim(),
    text2:     s.getPropertyValue('--text-2').trim(),
    muted:     s.getPropertyValue('--text-muted').trim(),
    border:    s.getPropertyValue('--border').trim(),
    bg:        s.getPropertyValue('--bg-card').trim(),
    // Agent-specific colors
    kai:       s.getPropertyValue('--kai').trim(),
    cursor:    s.getPropertyValue('--cursor').trim(),
    claude:    s.getPropertyValue('--claude').trim(),
    simon:     s.getPropertyValue('--simon').trim(),
    kimicode:  s.getPropertyValue('--kimicode').trim(),
    codex:     s.getPropertyValue('--codex').trim(),
    unknown:   s.getPropertyValue('--unknown').trim(),
  }};
}}

// Agent color mapping using theme colors
function getAgentColor(name) {{
  const colors = getThemeColors();
  const colorMap = {{
    'Simon': colors.simon || colors.accent,
    'Claude': colors.claude || colors.secondary,
    'Kai': colors.kai || colors.text,
    'Cursor': colors.cursor || colors.text2,
    'KimiCode': colors.kimicode || colors.accent,
    'Codex': colors.codex || colors.secondary,
    'Liminal': colors.text,
    'Unknown': colors.unknown || colors.muted
  }};
  return colorMap[name] || colorMap['Unknown'];
}}

// Bar chart: commits by agent
function renderBarChart() {{
  const margin = {{top: 20, right: 20, bottom: 60, left: 180}};
  const width = 800 - margin.left - margin.right;
  const height = 400 - margin.top - margin.bottom;

  const svg = d3.select('#bar-chart')
    .append('svg')
    .attr('width', width + margin.left + margin.right)
    .attr('height', height + margin.top + margin.bottom)
    .append('g')
    .attr('transform', `translate(${{margin.left}},${{margin.top}})`);

  const x = d3.scaleLinear()
    .domain([0, d3.max(agents, d => d.total_commits)])
    .range([0, width]);

  const y = d3.scaleBand()
    .domain(agents.map(d => d.name))
    .range([0, height])
    .padding(0.2);

  const colors = getThemeColors();

  // Bars
  svg.selectAll('.bar')
    .data(agents)
    .enter()
    .append('rect')
    .attr('class', 'bar')
    .attr('y', d => y(d.name))
    .attr('height', y.bandwidth())
    .attr('x', 0)
    .attr('width', d => x(d.total_commits))
    .attr('fill', d => getAgentColor(d.name))
    .attr('rx', 4);

  // Labels
  svg.selectAll('.label')
    .data(agents)
    .enter()
    .append('text')
    .attr('class', 'mono')
    .attr('x', -10)
    .attr('y', d => y(d.name) + y.bandwidth() / 2)
    .attr('text-anchor', 'end')
    .attr('dominant-baseline', 'middle')
    .style('fill', colors.text)
    .text(d => d.name);

  // Values
  svg.selectAll('.value')
    .data(agents)
    .enter()
    .append('text')
    .attr('class', 'mono')
    .attr('x', d => x(d.total_commits) + 5)
    .attr('y', d => y(d.name) + y.bandwidth() / 2)
    .attr('dominant-baseline', 'middle')
    .style('fill', colors.text)
    .style('font-size', '12px')
    .text(d => d.total_commits);
}}

// Grouped bar chart: commits per era by agent
function renderGroupedChart() {{
  const margin = {{top: 40, right: 120, bottom: 60, left: 180}};
  const width = 900 - margin.left - margin.right;
  const height = 500 - margin.top - margin.bottom;

  const svg = d3.select('#grouped-chart')
    .append('svg')
    .attr('width', width + margin.left + margin.right)
    .attr('height', height + margin.top + margin.bottom)
    .append('g')
    .attr('transform', `translate(${{margin.left}},${{margin.top}})`);

  // Flatten data for grouped chart
  const groupedData = [];
  agents.forEach(agent => {{
    Object.entries(agent.commits_per_era).forEach(([era, count]) => {{
      groupedData.push({{
        agent: agent.name,
        era: era,
        commits: count
      }});
    }});
  }});

  // Scales
  const x0 = d3.scaleBand()
    .domain(agents.map(d => d.name))
    .range([0, width])
    .padding(0.2);

  const x1 = d3.scaleBand()
    .domain(eras)
    .range([0, x0.bandwidth()])
    .padding(0.05);

  const y = d3.scaleLinear()
    .domain([0, d3.max(groupedData, d => d.commits) || 1])
    .range([height, 0]);

  const colors = getThemeColors();

  // X axis
  svg.append('g')
    .attr('transform', `translate(0,${{height}})`)
    .call(d3.axisBottom(x0))
    .selectAll('text')
    .style('fill', colors.text2)
    .style('font-size', '12px');

  // Y axis
  svg.append('g')
    .call(d3.axisLeft(y).ticks(5))
    .selectAll('text')
    .style('fill', colors.text2)
    .style('font-size', '12px');

  // Groups
  const groups = svg.selectAll('.g-group')
    .data(agents)
    .enter()
    .append('g')
    .attr('transform', d => `translate(${{x0(d.name)}},0)`);

  // Bars for each era
  groups.selectAll('.era-bar')
    .data(d => eras.map(era => ({{
      era,
      commits: d.commits_per_era[era] || 0,
      agent: d.name
    }})))
    .enter()
    .append('rect')
    .attr('class', 'era-bar')
    .attr('x', d => x1(d.era))
    .attr('y', d => y(d.commits))
    .attr('width', x1.bandwidth())
    .attr('height', d => height - y(d.commits))
    .attr('fill', d => getAgentColor(d.agent))
    .attr('opacity', 0.8)
    .attr('rx', 2);

  // Legend
  const legend = svg.selectAll('.legend')
    .data(eras)
    .enter()
    .append('g')
    .attr('class', 'legend')
    .attr('transform', (d, i) => `translate(${{width + 10}},${{i * 20}})`);

  legend.append('rect')
    .attr('width', 12)
    .attr('height', 12)
    .attr('rx', 2)
    .attr('fill', colors.muted);

  legend.append('text')
    .attr('x', 18)
    .attr('y', 10)
    .style('fill', colors.text2)
    .style('font-size', '11px')
    .text(d => d);
}}

// Metrics table
function renderMetricsTable() {{
  const tbody = d3.select('#metrics-table');
  const colors = getThemeColors();

  agents.forEach(agent => {{
    const row = tbody.append('tr');
    row.append('td').text(agent.name).style('font-weight', '600');
    row.append('td').text(agent.total_commits).classed('mono', true);

    // Rework rate with color coding
    const reworkCell = row.append('td').classed('mono', true);
    const reworkRate = agent.rework_rate;
    const reworkColor = reworkRate > 20 ? colors.kai : reworkRate > 10 ? colors.simon : colors.text;
    reworkCell.text(reworkRate + '%')
      .style('color', reworkColor);

    row.append('td').text(agent.avg_message_length + ' chars').classed('mono', true);
    row.append('td').text(agent.first_commit + ' → ' + agent.last_commit).classed('mono', true);
  }});
}}

// Rebuild charts on theme switch
window._rebuildCharts = function() {{
  d3.select('#bar-chart').selectAll('*').remove();
  d3.select('#grouped-chart').selectAll('*').remove();
  d3.select('#metrics-table').selectAll('*').remove();
  renderBarChart();
  renderGroupedChart();
  renderMetricsTable();
}};

// Initialize
renderBarChart();
renderGroupedChart();
renderMetricsTable();
</script>
"""

    html_template = f"""<!DOCTYPE html>
<html lang="en" data-theme="editorial">
<head>
{head_bundle(title=title, description=description, include_d3=True)}
{custom_css}
</head>
<body>
<a href="#main-content" class="skip-link">Skip to content</a>

<nav class="site-nav">
  <a href="." class="nav-back">&larr; Back</a>
  <div class="nav-sep"></div>
  <span class="nav-title">{project_name.upper()} Agent Benchmark</span>
  <div style="margin-left: auto;">{THEME_SWITCHER_HTML}</div>
</nav>

<main id="main-content">
<div class="container">
  <div class="header">
    <h1>{project_name.upper()} — Agent Performance Benchmark</h1>
    <p>Analysis of AI agent contribution patterns across project eras</p>
  </div>

  <div class="stats-grid">
    <div class="stat-card">
      <div class="stat-value">{meta['total_commits']}</div>
      <div class="stat-label">Total Commits</div>
    </div>
    <div class="stat-card">
      <div class="stat-value">{meta['total_agents']}</div>
      <div class="stat-label">Active Agents</div>
    </div>
    <div class="stat-card">
      <div class="stat-value mono">{meta['date_range'].split(' to ')[0] if ' to ' in meta['date_range'] else meta['date_range']}</div>
      <div class="stat-label">Project Start</div>
    </div>
    <div class="stat-card">
      <div class="stat-value mono">{meta['date_range'].split(' to ')[1] if ' to ' in meta['date_range'] else ''}</div>
      <div class="stat-label">Latest Activity</div>
    </div>
  </div>

  <div class="chart-section">
    <div class="chart-container">
      <h2 class="chart-title">Commits by Agent</h2>
      <div id="bar-chart"></div>
    </div>
  </div>

  <div class="chart-section">
    <div class="chart-container">
      <h2 class="chart-title">Commits per Era by Agent</h2>
      <div id="grouped-chart"></div>
    </div>
  </div>

  <div class="chart-section">
    <div class="chart-container">
      <h2 class="chart-title">Detailed Metrics</h2>
      <table>
        <thead>
          <tr>
            <th>Agent</th>
            <th>Total Commits</th>
            <th>Rework Rate</th>
            <th>Avg Message Length</th>
            <th>Active Period</th>
          </tr>
        </thead>
        <tbody id="metrics-table">
        </tbody>
      </table>
    </div>
  </div>
</div>
</main>

{js_code}
{body_end_bundle()}
</body>
</html>"""

    return html_template


def run_benchmark_analysis(project_dir: str) -> str:
    """Run complete benchmark analysis and generate HTML.

    Args:
        project_dir: Path to project directory (e.g., "projects/demo-project")

    Returns:
        Path to generated HTML file
    """
    project_path = Path(project_dir)
    db_path = project_path / "data" / "archaeology.db"
    deliverables_dir = project_path / "deliverables"
    visuals_dir = deliverables_dir / "visuals"
    output_path = visuals_dir / "agent-benchmark.html"

    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    # Analyze
    benchmark_data = analyze_agent_benchmarks(str(db_path))

    # Get project name from directory
    project_name = project_path.name

    # Generate HTML
    html_content = generate_benchmark_html(benchmark_data, project_name)

    # Write output
    visuals_dir.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_content, encoding="utf-8")

    return str(output_path)
