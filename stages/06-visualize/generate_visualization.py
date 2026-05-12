#!/usr/bin/env python3
"""Stage 06-Visualize: Generate HTML Visualization"""

import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Paths - using relative paths from script location
STAGES_DIR = Path(__file__).resolve().parent.parent.parent
SIGNALS_PATH = STAGES_DIR / "stages" / "04-detect" / "output" / "detected-signals.json"
ANALYSIS_DIR = STAGES_DIR / "stages" / "05-analyze" / "output"
OUTPUT_PATH = Path(__file__).resolve().parent / "output" / "archaeology.html"

# Ensure output directory exists
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

def load_data():
    """Load all analysis data"""
    with open(SIGNALS_PATH, 'r') as f:
        signals = json.load(f)

    analyses = {}
    for analysis_file in ANALYSIS_DIR.glob('analysis-*.json'):
        with open(analysis_file, 'r') as f:
            analyses[analysis_file.stem] = json.load(f)

    return signals, analyses

def prepare_chart_data(signals, analyses):
    """Prepare data for all charts"""

    # Timeline chart data
    daily_breakdown = signals.get('daily_breakdown', {})
    sorted_days = sorted(daily_breakdown.keys())

    timeline_data = {
        'type': 'timeline',
        'data': {
            'dates': sorted_days,
            'commits': [daily_breakdown[day] for day in sorted_days],
            'signals': [
                {
                    'date': s['date'],
                    'type': s['type'],
                    'label': s.get('metadata', {}).get('description', s['type'])
                }
                for s in signals.get('signals', [])
                if s['type'] in ['gap', 'velocity_shift']
            ]
        }
    }

    # Author distribution data
    author_data = {
        'type': 'author_distribution',
        'data': {
            'authors': ['Simon Gonzalez De Cruz', 'Simon'],
            'commits': [98, 25],
            'percentages': [79.7, 20.3]
        }
    }

    # Commit type pie chart (from commit messages in signals)
    commit_type_data = {
        'type': 'commit_type_distribution',
        'data': {
            'types': ['feat', 'fix', 'test', 'docs', 'chore', 'refactor', 'other'],
            'counts': [0, 0, 0, 0, 0, 0, 0]  # Will be calculated
        }
    }

    # We need to parse commit messages - let's get them from the database
    import sqlite3
    DB_PATH = STAGES_DIR / "stages" / "03-build" / "output" / "archaeology.db"
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT message FROM commits")
    commit_messages = [row[0] for row in cursor.fetchall()]
    conn.close()

    type_counts = defaultdict(int)
    for msg in commit_messages:
        msg_lower = msg.lower()
        if msg_lower.startswith('feat:'):
            type_counts['feat'] += 1
        elif msg_lower.startswith('fix:'):
            type_counts['fix'] += 1
        elif msg_lower.startswith('test:'):
            type_counts['test'] += 1
        elif msg_lower.startswith('docs:'):
            type_counts['docs'] += 1
        elif msg_lower.startswith('chore:'):
            type_counts['chore'] += 1
        elif msg_lower.startswith('refactor:'):
            type_counts['refactor'] += 1
        else:
            type_counts['other'] += 1

    commit_type_data['data']['counts'] = [
        type_counts['feat'],
        type_counts['fix'],
        type_counts['test'],
        type_counts['docs'],
        type_counts['chore'],
        type_counts['refactor'],
        type_counts['other']
    ]

    # Signal summary chart
    signal_summary = {
        'type': 'signal_summary',
        'data': signals.get('summary', {}).get('by_type', {})
    }

    return {
        'timeline': timeline_data,
        'author_distribution': author_data,
        'commit_type': commit_type_data,
        'signal_summary': signal_summary
    }

def generate_html(signals, analyses, chart_data):
    """Generate the complete HTML visualization"""

    # Extract key metrics
    total_commits = signals.get('total_commits', 0)
    active_days = signals.get('active_days', 0)
    span_days = signals.get('span_days', 0)
    date_range = signals.get('date_range', '')

    # Calculate peak day
    daily_breakdown = signals.get('daily_breakdown', {})
    peak_day = max(daily_breakdown.items(), key=lambda x: x[1]) if daily_breakdown else ('N/A', 0)

    # Get summary statistics
    signals_by_type = signals.get('summary', {}).get('by_type', {})

    # Calculate commit type distribution
    commit_type_counts = chart_data['commit_type']['data']['counts']
    total_type_commits = sum(commit_type_counts)
    commit_type_percentages = [
        round((c / total_type_commits * 100) if total_type_commits > 0 else 0, 1)
        for c in commit_type_counts
    ]

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>demo-project - Archaeology Report</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e4e4e7;
            line-height: 1.6;
            padding: 20px;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        header {{
            text-align: center;
            padding: 40px 0;
            border-bottom: 1px solid #3f3f46;
            margin-bottom: 40px;
        }}

        h1 {{
            font-size: 3em;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 10px;
        }}

        .subtitle {{
            font-size: 1.2em;
            color: #a1a1aa;
        }}

        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}

        .metric-card {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid #3f3f46;
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            transition: transform 0.2s, box-shadow 0.2s;
        }}

        .metric-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(102, 126, 234, 0.2);
        }}

        .metric-value {{
            font-size: 2.5em;
            font-weight: bold;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}

        .metric-label {{
            color: #a1a1aa;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-top: 5px;
        }}

        .chart-container {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid #3f3f46;
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 30px;
        }}

        .chart-title {{
            font-size: 1.5em;
            margin-bottom: 20px;
            color: #e4e4e7;
        }}

        .signals-list {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 15px;
        }}

        .signal-item {{
            background: rgba(255, 255, 255, 0.03);
            border-left: 4px solid #667eea;
            padding: 15px;
            border-radius: 0 8px 8px 0;
        }}

        .signal-type {{
            font-weight: bold;
            color: #667eea;
            margin-bottom: 5px;
        }}

        .signal-date {{
            color: #a1a1aa;
            font-size: 0.9em;
        }}

        .signal-description {{
            color: #e4e4e7;
            margin-top: 5px;
        }}

        .findings-section {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid #3f3f46;
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 30px;
        }}

        .finding-item {{
            margin-bottom: 15px;
            padding-bottom: 15px;
            border-bottom: 1px solid #3f3f46;
        }}

        .finding-item:last-child {{
            border-bottom: none;
        }}

        .finding-type {{
            font-weight: bold;
            color: #667eea;
            margin-bottom: 5px;
        }}

        .finding-description {{
            color: #e4e4e7;
            margin-bottom: 5px;
        }}

        .finding-confidence {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.8em;
            font-weight: bold;
        }}

        .confidence-high {{
            background: rgba(34, 197, 94, 0.2);
            color: #22c55e;
        }}

        .confidence-medium {{
            background: rgba(234, 179, 8, 0.2);
            color: #eab308;
        }}

        .confidence-low {{
            background: rgba(239, 68, 68, 0.2);
            color: #ef4444;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>demo-project</h1>
            <p class="subtitle">Archaeology Report</p>
        </header>

        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-value">{total_commits}</div>
                <div class="metric-label">Total Commits</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{active_days}</div>
                <div class="metric-label">Active Days</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{span_days}</div>
                <div class="metric-label">Project Span</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{peak_day[1]}</div>
                <div class="metric-label">Peak Day (Commits)</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{round(total_commits / active_days, 1) if active_days > 0 else 0}</div>
                <div class="metric-label">Avg Commits/Day</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{date_range}</div>
                <div class="metric-label">Date Range</div>
            </div>
        </div>

        <div class="chart-container">
            <h2 class="chart-title">Daily Commit Activity</h2>
            <canvas id="timelineChart"></canvas>
        </div>

        <div class="chart-container">
            <h2 class="chart-title">Author Distribution</h2>
            <canvas id="authorChart"></canvas>
        </div>

        <div class="chart-container">
            <h2 class="chart-title">Commit Type Distribution</h2>
            <canvas id="typeChart"></canvas>
        </div>

        <div class="chart-container">
            <h2 class="chart-title">Signal Detection Summary</h2>
            <canvas id="signalChart"></canvas>
        </div>

        <div class="findings-section">
            <h2 class="chart-title">Detected Signals</h2>
            <div class="signals-list">
                {generate_signals_html(signals.get('signals', [])[:20])}
            </div>
        </div>

        <div class="findings-section">
            <h2 class="chart-title">Key Analysis Findings</h2>
            {generate_findings_html(analyses)}
        </div>
    </div>

    <script>
        // Timeline Chart
        const timelineCtx = document.getElementById('timelineChart').getContext('2d');
        new Chart(timelineCtx, {{
            type: 'bar',
            data: {{
                labels: {json.dumps(sorted(daily_breakdown.keys()))},
                datasets: [{{
                    label: 'Commits',
                    data: {json.dumps([daily_breakdown[day] for day in sorted(daily_breakdown.keys())])},
                    backgroundColor: 'rgba(102, 126, 234, 0.8)',
                    borderColor: 'rgba(102, 126, 234, 1)',
                    borderWidth: 1
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{
                        display: false
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        ticks: {{
                            color: '#a1a1aa'
                        }},
                        grid: {{
                            color: 'rgba(255, 255, 255, 0.1)'
                        }}
                    }},
                    x: {{
                        ticks: {{
                            color: '#a1a1aa'
                        }},
                        grid: {{
                            color: 'rgba(255, 255, 255, 0.1)'
                        }}
                    }}
                }}
            }}
        }});

        // Author Distribution Chart
        const authorCtx = document.getElementById('authorChart').getContext('2d');
        new Chart(authorCtx, {{
            type: 'doughnut',
            data: {{
                labels: ['Simon Gonzalez De Cruz', 'Simon'],
                datasets: [{{
                    data: [98, 25],
                    backgroundColor: [
                        'rgba(102, 126, 234, 0.8)',
                        'rgba(118, 75, 162, 0.8)'
                    ],
                    borderColor: [
                        'rgba(102, 126, 234, 1)',
                        'rgba(118, 75, 162, 1)'
                    ],
                    borderWidth: 2
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{
                        position: 'bottom',
                        labels: {{
                            color: '#e4e4e7',
                            padding: 20
                        }}
                    }}
                }}
            }}
        }});

        // Commit Type Chart
        const typeCtx = document.getElementById('typeChart').getContext('2d');
        new Chart(typeCtx, {{
            type: 'pie',
            data: {{
                labels: ['feat', 'fix', 'test', 'docs', 'chore', 'refactor', 'other'],
                datasets: [{{
                    data: {json.dumps(commit_type_counts)},
                    backgroundColor: [
                        'rgba(34, 197, 94, 0.8)',
                        'rgba(239, 68, 68, 0.8)',
                        'rgba(102, 126, 234, 0.8)',
                        'rgba(234, 179, 8, 0.8)',
                        'rgba(168, 85, 247, 0.8)',
                        'rgba(20, 184, 166, 0.8)',
                        'rgba(113, 113, 122, 0.8)'
                    ],
                    borderColor: [
                        'rgba(34, 197, 94, 1)',
                        'rgba(239, 68, 68, 1)',
                        'rgba(102, 126, 234, 1)',
                        'rgba(234, 179, 8, 1)',
                        'rgba(168, 85, 247, 1)',
                        'rgba(20, 184, 166, 1)',
                        'rgba(113, 113, 122, 1)'
                    ],
                    borderWidth: 2
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{
                        position: 'bottom',
                        labels: {{
                            color: '#e4e4e7',
                            padding: 15,
                            generateLabels: function(chart) {{
                                const data = chart.data;
                                return data.labels.map((label, i) => ({{
                                    text: label + ' (' + {json.dumps(commit_type_percentages)}[i] + '%)',
                                    fillStyle: data.datasets[0].backgroundColor[i],
                                    hidden: false,
                                    index: i
                                }}));
                            }}
                        }}
                    }}
                }}
            }}
        }});

        // Signal Summary Chart
        const signalCtx = document.getElementById('signalChart').getContext('2d');
        new Chart(signalCtx, {{
            type: 'bar',
            data: {{
                labels: {json.dumps(list(signals_by_type.keys()))},
                datasets: [{{
                    label: 'Signals',
                    data: {json.dumps(list(signals_by_type.values()))},
                    backgroundColor: 'rgba(118, 75, 162, 0.8)',
                    borderColor: 'rgba(118, 75, 162, 1)',
                    borderWidth: 1
                }}]
            }},
            options: {{
                responsive: true,
                indexAxis: 'y',
                plugins: {{
                    legend: {{
                        display: false
                    }}
                }},
                scales: {{
                    x: {{
                        beginAtZero: true,
                        ticks: {{
                            color: '#a1a1aa'
                        }},
                        grid: {{
                            color: 'rgba(255, 255, 255, 0.1)'
                        }}
                    }},
                    y: {{
                        ticks: {{
                            color: '#a1a1aa'
                        }},
                        grid: {{
                            color: 'rgba(255, 255, 255, 0.1)'
                        }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>"""

    return html

def generate_signals_html(signals):
    """Generate HTML for signals list"""
    html = []
    for signal in signals:
        signal_type = signal.get('type', 'unknown')
        date = signal.get('date', 'N/A')
        description = signal.get('metadata', {}).get('description', signal_type)

        html.append(f"""
                <div class="signal-item">
                    <div class="signal-type">{signal_type.replace('_', ' ').title()}</div>
                    <div class="signal-date">{date}</div>
                    <div class="signal-description">{description}</div>
                </div>
        """)

    return ''.join(html)

def generate_findings_html(analyses):
    """Generate HTML for key findings"""
    html = []

    # Show top findings from each analysis
    for analysis_name, analysis_data in analyses.items():
        vector_name = analysis_data.get('vector_name', analysis_name)
        findings = analysis_data.get('findings', [])[:3]  # Top 3 findings

        html.append(f"<h3 style='color: #667eea; margin-top: 20px;'>{vector_name}</h3>")

        for finding in findings:
            finding_type = finding.get('type', 'Unknown')
            description = finding.get('description', '')
            confidence = finding.get('confidence', 'low')

            html.append(f"""
                <div class="finding-item">
                    <div class="finding-type">{finding_type}</div>
                    <div class="finding-description">{description}</div>
                    <span class="finding-confidence confidence-{confidence}">{confidence.upper()}</span>
                </div>
            """)

    return ''.join(html)

if __name__ == '__main__':
    print("Loading analysis data...")
    signals, analyses = load_data()

    print("Preparing chart data...")
    chart_data = prepare_chart_data(signals, analyses)

    print("Generating HTML visualization...")
    html = generate_html(signals, analyses, chart_data)

    with open(OUTPUT_PATH, 'w') as f:
        f.write(html)

    print(f"✓ Stage 06-Visualize completed")
    print(f"  Output written to: {OUTPUT_PATH}")
