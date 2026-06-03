# DevArch Framework

[![PyPI version](https://img.shields.io/pypi/v/devarch-framework.svg)](https://pypi.org/project/devarch-framework/)
[![Python](https://img.shields.io/pypi/pyversions/devarch-framework.svg)](https://pypi.org/project/devarch-framework/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![GitHub stars](https://img.shields.io/github/stars/KyaniteLabs/devarch-framework.svg?style=social)](https://github.com/KyaniteLabs/devarch-framework)

**Git repository archaeology framework.** Mine commit history, detect development signals, run 6 analysis vectors, and generate engineering narrative reports — from any git repository, fully local, no external services.

```bash
git clone https://github.com/KyaniteLabs/devarch-framework.git && cd devarch-framework && pip install -e .
```

DevArch treats your git history as structured data. It extracts commits into a queryable SQLite database, runs heuristic signal detection (gaps, velocity shifts, author changes), executes specialized analysis vectors, and generates interactive HTML visualizations and markdown reports. Built for engineers, researchers, and AI agents that need to understand how a codebase evolved.

> **Just want a quick learning diagnostic?** [Dev Learning Archaeologist](https://github.com/KyaniteLabs/dev-learning-archaeologist) is a zero-setup ICM folder — drop it in any project, run through Claude Code, no install required.

## What It Does

DevArch transforms git history into structured insights through a full-featured CLI with 20+ commands. The framework supports:

> **Just want the quick learning diagnostic?** [Dev Learning Archaeologist](https://github.com/KyaniteLabs/dev-learning-archaeologist) is a zero-setup ICM folder that drops into any project and runs the same analysis through Claude Code — no install required.

- **Complete Pipeline**: Initialize projects, mine git data, build SQLite databases, detect signals, analyze patterns, visualize results
- **6 Analysis Vectors**: SDLC Gap Finder, ML Pattern Mapper, Agentic Workflow Analyzer, Formal Terms Mapper, Source Archaeologist, YouTube Correlator
- **Era System**: Scan commits for era transitions, cascade era labels across codebases, map era boundaries
- **Audit System**: Validate outputs with severity-based checks (CRITICAL, HIGH, MEDIUM, LOW)
- **Signal Detection**: 5 heuristics identify noteworthy patterns (gaps, velocity shifts, author changes, scope changes, correlations)
- **Supplementary Data**: Correlate any external data (fitness, YouTube, calendar) with commits
- **Multi-Project Sync**: Aggregate findings across multiple repositories
- **Demo Generation**: Create demo projects for testing and documentation

## Installation

```bash
# Clone the repository
git clone https://github.com/KyaniteLabs/devarch-framework.git
cd devarch-framework

# Install in editable mode
pip install -e .

# Verify installation
devarch --help
```

## Quick Start

### 1. Initialize a Project

```bash
# Create a new archaeology project
devarch init my-project --description "My repo archaeology" --repo-url https://github.com/user/repo

# Or create a demo project with synthetic data
devarch demo --build-db
```

### 2. Mine Git History

```bash
# Extract commits from a repository
devarch mine /path/to/repo --project my-project

# Build the SQLite database
devarch build-db my-project
```

### 3. Detect Signals

```bash
# Run signal detection
devarch signals my-project

# Optionally configure signal thresholds
devarch signals my-project --config custom-signals.json --min-gap-days 14
```

### 4. Run Analysis

```bash
# Run all analysis vectors
devarch analyze my-project

# Run specific vectors
devarch analyze my-project --vector sdlc-gap-finder --vector ml-pattern-mapper

# Show legacy prompt instructions (for manual LLM execution)
devarch analyze my-project --prompts
```

### 5. Visualize Results

```bash
# Generate HTML visualization
devarch visualize my-project

# Export report in markdown or HTML
devarch export-report my-project --format markdown
devarch export-report my-project --format html --output my-report.html
```

### 6. Audit Outputs

```bash
# Run audit checks
devarch audit my-project

# Control failure threshold
devarch audit my-project --fail-on MEDIUM
```

## CLI Commands

### Project Management
- `devarch init <name>` -- Initialize a new archaeology project
- `devarch demo [--build-db]` -- Create a demo project with synthetic data

### Data Extraction
- `devarch mine <repo-path> --project <name>` -- Extract git history
- `devarch build-db <project>` -- Build SQLite database from mined data
- `devarch ingest-pipeline <project> --logs-dir <path>` -- Ingest GitHub Actions logs

### Signal Detection
- `devarch signals <project> [--config] [--min-gap-days]` -- Run signal detection heuristics
- `devarch extract-sessions <project> --sessions-dir <path>` -- Extract coding sessions

### Analysis
- `devarch analyze <project> [--vector] [--prompts]` -- Run analysis vectors
- `devarch cascade <project> [--dry-run] [--skip-mine]` -- Cascade era labels across repos

### Visualization & Reporting
- `devarch visualize <project>` -- Generate HTML visualization
- `devarch export-report <project> [--format] [--output]` -- Export report
- `devarch public-case-study <output-dir> [--project]` -- Create sanitized public case study

### Database & Inspection
- `devarch serve <project> [--port] [--unsafe-cors]` -- Start Datasette server for database inspection

### Audit & Validation
- `devarch audit <project> [--fail-on]` -- Run audit checks
- `devarch validate <project>` -- Validate project configuration

### Multi-Project Operations
- `devarch sync [--project] [--skip-mine] [--skip-signals]` -- Sync multiple projects
- `devarch global-viz [--output] [--top-n] [--year]` -- Generate global visualization
- `devarch fetch-github <owner> [--output]` -- Fetch repository metadata from GitHub

### Local Pipeline
- `devarch local-pipeline <repo-name> [--pipeline-dir] [--repos-dir] [--run]` -- Inspect local GitHub pipeline

## Analysis Vectors

DevArch includes 6 analysis vectors:

1. **SDLC Gap Finder** -- Identify gaps in software development lifecycle practices
2. **ML Pattern Mapper** -- Detect machine learning patterns and practices
3. **Agentic Workflow Analyzer** -- Identify AI/agent-based workflows
4. **Formal Terms Mapper** -- Track formal methods and terminology usage
5. **Source Archaeologist** -- Deep code archaeology and evolution tracking
6. **YouTube Correlator** -- Correlate commit patterns with YouTube watch history

## Era System

The era system identifies and tracks distinct phases in repository evolution:

- **Scanner**: Detect era transitions based on commit patterns
- **Cascade**: Propagate era labels across dependent files
- **Mapper**: Map era boundaries and transitions

## Multi-Project Sync

Configure multiple projects in `config/profile.json`:

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

Then run sync operations:

```bash
# Sync all projects
devarch sync

# Sync specific projects
devarch sync --project project-one --project project-two

# Skip mining (use cached data)
devarch sync --skip-mine
```

## Database Inspection

Start a Datasette server to inspect your archaeology database:

```bash
devarch serve my-project --port 8001
```

Visit http://localhost:8001 to explore commits, signals, and analysis results.

## Supplementary Data

Add external data sources to correlate with commits:

- Fitness tracker data (CSV/JSON)
- YouTube watch history (JSON)
- Calendar events (CSV/JSON)
- Weather data (CSV)
- Lunar phases (JSON)
- Any data with dates

Configure supplementary sources in your project configuration or via analysis vectors.

## ICM Compliance

This framework follows ICM (Interpretable Context Methodology) conventions with full 5-layer separation:

| Layer | File | Purpose |
|-------|------|---------|
| L0 | `CLAUDE.md` | Identity, folder map, routing table, naming conventions |
| L1 | `CONTEXT.md` | Workspace router with 5 siloed workspaces |
| L2 | `stages/*/CONTEXT.md` | Stage contracts with L3/L4 loading guidance |
| L3 | `shared/`, `analysis-vectors/`, `stages/*/references/` | Reference material loaded selectively |
| L4 | `stages/*/output/` | Working artifacts per stage |

Architecture decisions documented in `docs/decisions.md`.

## Requirements

- Python 3.10+
- Git repository with commit history
- Write permissions in workspace directory

## Dependencies

- `click>=8.1` -- CLI framework
- `sqlite-utils>=3.0` -- Database utilities
- `datasette>=0.64.0` -- Database inspection server

## Third-Party Acknowledgments

DevArch Framework integrates several excellent open-source libraries:

- **Click** (BSD License) — Elegant CLI framework for command-line interfaces
- **SQLite** (Public Domain) — Embedded SQL database engine with FTS5 full-text search
- **Chart.js** (MIT License) — Responsive JavaScript charting library
- **D3.js** (BSD License) — Document-driven data visualization framework
- **Google Fonts** (OFL License) — Open-source typography (Inter, JetBrains Mono)

We gratefully acknowledge the work of their respective authors and maintainers.

## Project Structure

```
archaeology/          -- Main Python package
  cli.py              -- CLI entry point (20+ commands)
  analysis_runner.py  -- Analysis vector orchestration
  audit.py            -- Audit system
  era_scanner.py      -- Era detection
  era_cascade.py      -- Era label propagation
  era_mapper.py       -- Era boundary mapping
  report.py           -- Report generation
  demo.py             -- Demo project generation
  local_pipeline.py   -- Local GitHub pipeline inspection
  db/                 -- Database utilities
  classifiers/        -- Signal classification
  extractors/         -- Data extraction
  validators/         -- Output validation
  visualization/      -- Template-based visualization
analysis-vectors/     -- Analysis vector definitions
config/               -- Configuration templates and schemas
scripts/              -- Utility scripts
setup/                -- Project setup questionnaire
shared/               -- Framework-wide reference docs
skills/               -- Bundled skill for CLI usage
stages/               -- 9-stage pipeline contracts (ICM L2)
docs/                 -- Architecture decisions
_config/              -- Developer profile templates
```

## License

MIT License -- See LICENSE file for details.

## Support

For issues or questions:

1. Check CONTEXT.md for task routing
2. Review analysis vector documentation in analysis-vectors/
3. Run `devarch validate <project>` to check configuration
4. Run `devarch audit <project>` to validate outputs
5. Use `devarch serve <project>` for database inspection

## FAQ

**What is repository archaeology?**
Repository archaeology treats git history as structured evidence. Instead of reading code, you read the sequence of changes — who changed what, when, at what velocity, and in response to what signals. DevArch automates the excavation.

**How is DevArch different from `git log`?**
`git log` produces raw output. DevArch mines commits into a queryable SQLite database, runs 5 signal-detection heuristics, executes 6 specialized analysis vectors, and produces interactive HTML visualizations and narrative reports. The output is evidence, not a log dump.

**Does DevArch work with any git repository?**
Yes. Any local git repository with commit history works. No GitHub API key, no cloud service, no configuration beyond pointing it at a path.

**Can AI agents use DevArch autonomously?**
Yes. The framework is ICM-compliant — it ships with structured context layers (`CLAUDE.md`, stage contracts, `llms.txt`) so Claude Code, Cursor, and other AI coding agents can understand and operate the pipeline without manual instruction. A bundled `skills/` folder enables one-command usage from the Claude Code CLI.

**What size repositories does DevArch handle?**
Tested on repositories from dozens to tens of thousands of commits. SQLite + FTS5 handles large git histories without any external infrastructure.

**Is my data sent anywhere?**
No. DevArch runs entirely locally. All mining, analysis, and report generation happens on your machine. No telemetry, no cloud API calls.

## Related Projects

- **[Dev Learning Archaeologist](https://github.com/KyaniteLabs/dev-learning-archaeologist)** — Zero-setup ICM folder for Claude Code. Drop it in, ask one question, get a full HTML learning diagnostic. The lightweight version of this framework.
- **[KyaniteLabs](https://github.com/KyaniteLabs)** — More AI-native developer tools: MCP servers, time estimation, and multi-agent orchestration.

---

## Part of KyaniteLabs

More from [KyaniteLabs](https://kyanitelabs.tech). Related projects:

- **[dev-learning-archaeologist](https://github.com/KyaniteLabs/dev-learning-archaeologist)** — forensic git-history learning diagnostic
- **[checkyourself](https://github.com/KyaniteLabs/checkyourself)** — local-first production-readiness checks for AI-built code
- **[Epoch](https://github.com/KyaniteLabs/Epoch)** — time-estimation MCP server (PERT) for AI agents

→ More at **[kyanitelabs.tech](https://kyanitelabs.tech)**
