# Core Concepts

Reference material (L3). Load when working on analysis, visualization, or framework modifications.

## Signal Detection

5 heuristics identify noteworthy patterns:
- **Gap detection** — Missing commits in expected time ranges
- **Velocity shifts** — Sudden changes in commit frequency
- **Author changes** — New contributors or missing regulars
- **Scope changes** — Sudden shifts in files/directories touched
- **Supplementary correlations** — Patterns matching external data

## Analysis Vectors

6 specialized analyzers extract specific insights:
- **SDLC Gap Finder** — Identify gaps in software development lifecycle practices
- **ML Pattern Mapper** — Detect machine learning patterns and practices
- **Agentic Workflow Analyzer** — Identify AI/agent-based workflows
- **Formals Terms Mapper** — Track formal methods and terminology usage
- **Source Archaeologist** — Deep code archaeology and evolution tracking
- **YouTube Correlator** — Correlate commit patterns with YouTube watch history

## Era System

Detect and track distinct phases in repository evolution through three components:
- **era_scanner.py** — Scans for era transition signals
- **era_cascade.py** — Propagates era labels across repos
- **era_mapper.py** — Maps era boundaries to time ranges

## Audit System

Validate outputs with severity-based checks:
- CRITICAL — Pipeline-breaking issues
- HIGH — Significant data quality problems
- MEDIUM — Non-critical but notable issues
- LOW — Informational findings

## Supplementary Data

Any external data with timestamps can be correlated against commit history. Supported types:
- Fitness tracker data (CSV/JSON)
- YouTube watch history (JSON)
- Calendar events (CSV/JSON)
- Weather data (CSV)
- Lunar phases (JSON)
- Any timestamped data with date fields

Configure in `project.json` under `supplementary_sources`.

## Database

SQLite database with FTS5 full-text search for commit and signal inspection. Schema includes commits, signals, eras, analysis results, and supplementary data tables.

## Visualization

Template-based HTML generation with Chart.js. Generates per-project interactive visualizations with score cards, commit timelines, and signal summaries.

## Demo Generation

Create demo projects with synthetic commit data. Supports `--force` to regenerate and `--build-db` to run full pipeline on demo data.
