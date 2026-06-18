# DevArch Framework

[![PyPI version](https://img.shields.io/pypi/v/devarch-framework.svg)](https://pypi.org/project/devarch-framework/)
[![Python](https://img.shields.io/pypi/pyversions/devarch-framework.svg)](https://pypi.org/project/devarch-framework/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)
[![GitHub stars](https://img.shields.io/github/stars/KyaniteLabs/devarch-framework.svg?style=social)](https://github.com/KyaniteLabs/devarch-framework)

**Forensic archaeology framework for git repositories.** Mine commit history, detect development signals, run 6 analysis vectors, and generate interactive engineering narrative reports — fully local, no external services required.

```bash
pip install devarch-framework
```

DevArch treats your git history as structured data. It extracts commits into a queryable SQLite database, runs heuristic signal detection (gaps, velocity shifts, author changes), executes specialized analysis vectors, and generates interactive HTML visualizations and markdown reports. Built for engineers, researchers, and AI agents that need to understand how a codebase evolved over time.

> **Just want a quick learning diagnostic?** [Dev Learning Archaeologist](https://github.com/KyaniteLabs/dev-learning-archaeologist) is a zero-setup ICM folder — drop it in any project and run through Claude Code, no install required.

---

## What Is This?

DevArch is a **Python CLI framework for software archaeology** — the practice of analyzing git repository history to uncover development patterns, productivity signals, and engineering narratives. It transforms raw `git log` data into a structured SQLite database, applies heuristic analysis to detect noteworthy events, and produces reports and interactive dashboards that tell the story of how a codebase was built.

**Primary language:** Python 3.10+  
**Core dependencies:** Click (CLI), sqlite-utils (database), Datasette (data exploration)

The framework is designed for:

- **Engineering managers** reviewing team velocity and development practices
- **Developers** understanding the evolution of a codebase before contributing
- **Researchers** studying software development patterns at scale
- **AI agents** that need structured access to repository history and analysis results

---

## Features

### Complete Pipeline

A 9-stage pipeline from raw repository to finished report:

| Stage | Description |
|-------|-------------|
| 01 — Setup | Initialize project scaffolding and configuration |
| 02 — Mine | Extract commits, files, and metadata from git history |
| 03 — Build | Assemble a queryable SQLite database |
| 04 — Detect | Run signal detection heuristics on mined data |
| 05 — Analyze | Execute specialized analysis vectors |
| 06 — Visualize | Generate interactive HTML charts and dashboards |
| 07 — Report | Export narrative markdown and HTML reports |
| 08 — Audit | Validate outputs with severity-based checks |
| 09 — Strategy | Synthesize findings into actionable recommendations |

### 6 Analysis Vectors

Specialized analyzers that each look at your repository through a different lens:

1. **SDLC Gap Finder** — Identifies gaps in software development lifecycle practices (missing tests, absent CI, undocumented changes)
2. **ML Pattern Mapper** — Detects machine learning workflows, model training patterns, and data pipeline structures
3. **Agentic Workflow Analyzer** — Identifies AI agent integrations, LLM usage, and autonomous workflow patterns
4. **Formal Terms Mapper** — Tracks formal methods, specification language, and domain-specific terminology across commits
5. **Source Archaeologist** — Deep code evolution analysis: file churn, refactor detection, dependency graph changes
6. **YouTube Correlator** — Correlates commit patterns with YouTube watch history to surface learning-to-code relationships

### Signal Detection

5 heuristic detectors scan for noteworthy development patterns:

- **Gap Detection** — Periods of inactivity beyond configurable thresholds
- **Velocity Shifts** — Sudden changes in commit frequency or code volume
- **Author Transitions** — Ownership changes, bus factor events, new contributors
- **Scope Changes** — Commits that touch unusually large numbers of files or modules
- **Cross-Source Correlations** — Patterns that align with supplementary external data

### Era System

Tracks distinct phases in repository evolution:

- **Era Scanner** — Detects transitions between development eras based on commit patterns and code characteristics
- **Era Cascade** — Propagates era labels across dependent files and modules
- **Era Mapper** — Visualizes era boundaries and transitions over time

### Additional Capabilities

- **Audit System** — Validates all pipeline outputs with severity-based checks (CRITICAL, HIGH, MEDIUM, LOW)
- **Supplementary Data** — Correlate any external time-series data (fitness trackers, YouTube history, calendar events, weather) with commit activity
- **Multi-Project Sync** — Aggregate findings across multiple repositories for portfolio-level analysis
- **MCP Server** — Model Context Protocol server for AI agent integration (`devarch-mcp`)
- **Demo Generation** — Create synthetic demo projects for testing and documentation
- **Datasette Integration** — One-command database inspection through a web UI

---

## Installation

### From PyPI

```bash
pip install devarch-framework
```

### From Source (editable)

```bash
git clone https://github.com/KyaniteLabs/devarch-framework.git
cd devarch-framework
pip install -e .
```

### With MCP Support

```bash
pip install "devarch-framework[mcp]"
```

### With Development Dependencies

```bash
pip install -e ".[dev]"
```

### Requirements

- Python 3.10 or later
- Git (must be available on `PATH`)

### Verify Installation

```bash
devarch --help
```

---

## Quick Start

### 1. Create a Demo Project

The fastest way to see DevArch in action is with the built-in demo:

```bash
devarch demo --build-db
```

This generates a synthetic project at `projects/demo-project/` with mined git data and a pre-built SQLite database.

### 2. Analyze a Real Repository

```bash
# Initialize a new project
devarch init my-project --description "Analysis of my repo" --repo-url https://github.com/user/repo

# Mine git history
devarch mine /path/to/local/repo --project my-project

# Build the database
devarch build-db my-project

# Run signal detection
devarch signals my-project

# Run all analysis vectors
devarch analyze my-project

# Generate visualizations
devarch visualize my-project

# Export a report
devarch export-report my-project --format markdown --output report.md
```

### 3. Explore the Database

```bash
devarch serve my-project --port 8001
```

Visit `http://localhost:8001` to interactively query your commits, signals, and analysis results.

---

## Usage

### CLI Commands

DevArch provides 20+ commands organized by pipeline stage:

#### Project Management

```bash
devarch init <name>                              # Initialize a new project
devarch demo [--build-db]                        # Create a demo project with synthetic data
devarch validate <project>                       # Validate project configuration
```

#### Data Extraction

```bash
devarch mine <repo-path> --project <name>        # Extract git history into structured data
devarch build-db <project>                       # Build SQLite database from mined data
devarch ingest-pipeline <project> --logs-dir <path>  # Ingest GitHub Actions logs
devarch extract-sessions <project> --sessions-dir <path>  # Extract coding sessions
```

#### Analysis

```bash
devarch signals <project>                        # Run signal detection heuristics
devarch analyze <project>                        # Run all analysis vectors
devarch analyze <project> --vector sdlc-gap-finder  # Run a specific vector
devarch cascade <project>                        # Cascade era labels across repos
```

#### Visualization & Reporting

```bash
devarch visualize <project>                      # Generate HTML visualization
devarch export-report <project> --format markdown  # Export as markdown
devarch export-report <project> --format html    # Export as HTML
devarch public-case-study <output-dir> [--project]  # Create sanitized public case study
```

#### Database Inspection

```bash
devarch serve <project> --port 8001              # Start Datasette server
```

#### Audit & Validation

```bash
devarch audit <project>                          # Run all audit checks
devarch audit <project> --fail-on MEDIUM         # Fail if MEDIUM or above issues found
```

#### Multi-Project Operations

```bash
devarch sync                                     # Sync all projects from profile.json
devarch sync --project proj-a --project proj-b   # Sync specific projects
devarch global-viz --output overview.html        # Generate cross-project visualization
devarch fetch-github <owner>                     # Fetch repository metadata from GitHub
```

#### Local Pipeline

```bash
devarch local-pipeline <repo-name>               # Inspect local GitHub pipeline data
```

### Makefile Targets

Common development tasks:

```bash
make install          # Install the package
make install-dev      # Install with development dependencies
make test             # Run tests
make test-cov         # Run tests with coverage report
make demo             # Create and run demo project
make lint             # Run syntax checking
make validate         # Validate project configuration
make serve            # Start Datasette for demo project
make clean            # Remove build artifacts
make reset            # Full reset (clean + remove demo)
```

### Multi-Project Configuration

Configure multiple repositories in `config/profile.json`:

```json
{
  "projects": [
    {
      "name": "project-one",
      "path": "/path/to/project-one"
    },
    {
      "name": "project-two",
      "path": "/path/to/project-two"
    }
  ],
  "developer": {
    "name": "Your Name",
    "github_username": "yourusername"
  }
}
```

### Supplementary Data

Correlate external time-series data with commit activity by adding data sources to your project:

- Fitness tracker exports (CSV/JSON)
- YouTube watch history (JSON)
- Calendar events (CSV/JSON)
- Weather data (CSV)
- Lunar phases (JSON)
- Any dataset with date-indexed records

### MCP Server (AI Agent Integration)

DevArch includes a Model Context Protocol server for integration with AI agents:

```bash
pip install "devarch-framework[mcp]"
devarch-mcp
```

This exposes the framework's analysis capabilities as MCP tools that agents can invoke programmatically.

---

## Project Structure

```
devarch-framework/
├── archaeology/           # Core Python package
│   ├── cli.py             # Click CLI entry point
│   ├── api.py             # Programmatic API
│   ├── mcp_server/        # Model Context Protocol server
│   ├── classifiers/       # Commit classification logic
│   ├── extractors/        # Data extraction from git
│   ├── validators/        # Output validation
│   ├── visualization/     # HTML chart templates
│   ├── templates/         # Report templates
│   └── db/                # Database utilities
├── analysis-vectors/      # Analysis vector specifications
├── config/                # Default configuration and schemas
├── stages/                # Pipeline stage documentation
├── shared/                # Shared concepts and design specs
├── projects/              # Project data directories
├── tests/                 # Test suite
├── scripts/               # Utility and automation scripts
├── skills/                # AI agent skill definitions
├── docs/                  # Documentation site
├── setup/                 # Setup questionnaire
└── _config/               # Developer profile configuration
```

---

## FAQ

### What does DevArch actually do?

DevArch extracts data from git repositories (commits, file changes, author history) into a SQLite database, then applies heuristic analysis to detect patterns like development gaps, velocity changes, and era transitions. It produces interactive visualizations and narrative reports that tell the story of how a codebase evolved.

### Do I need internet access or external services?

No. DevArch runs entirely locally. The only exception is the optional `fetch-github` command, which queries the GitHub API for repository metadata, and the YouTube Correlator vector, which processes locally-stored watch history files.

### What Python versions are supported?

Python 3.10, 3.11, and 3.12. Python 3.10 is the minimum required version.

### Can I analyze private repositories?

Yes. DevArch operates on local git clones. It never transmits your code or commit data to external services. All analysis happens on your machine.

### How is this different from `git log` or GitHub Insights?

DevArch goes beyond raw commit logs. It structures history into a queryable database, applies multi-dimensional analysis vectors (not just counts and graphs), detects semantic signals like era transitions and SDLC gaps, correlates with external data sources, and produces narrative reports designed for human understanding — not just dashboards.

### What is the "Era System"?

The Era System identifies distinct phases in a repository's evolution — for example, "initial scaffolding," "feature expansion," "refactoring phase," "maintenance mode." It detects transitions automatically from commit patterns and propagates era labels across the codebase for timeline analysis.

### Can AI agents use DevArch?

Yes. DevArch includes a Model Context Protocol (MCP) server that exposes its capabilities as tools AI agents can invoke. Install with `pip install "devarch-framework[mcp]"` and run `devarch-mcp` to start the server.

---

## Contributing

Contributions are welcome. Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:

- Setting up a development environment
- Running tests
- Submitting pull requests
- Code style and conventions

```bash
# Quick setup for contributors
git clone https://github.com/KyaniteLabs/devarch-framework.git
cd devarch-framework
make install-dev
make test
```

---

## License

This project is licensed under the **Apache License 2.0** — see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <sub>Built by <a href="https://github.com/KyaniteLabs">KyaniteLabs</a></sub>
</p>