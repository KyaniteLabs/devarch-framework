# DevArch Framework

Forensic archaeology framework for git repositories. Full Python package with 20+ CLI commands for extracting commit history, detecting signals, running analysis vectors, and generating reports.

## Identity

DevArch is a productized framework for repository archaeology. It transforms git history into structured insights through a comprehensive CLI with 6 analysis vectors, era detection, signal detection, and multi-project sync capabilities. Supports supplementary data correlation to surface patterns across commit history and external data sources.

## Folder Map

```
archaeology/          -- Main Python package (entry point: devarch command)
  cli.py              -- CLI with 20+ commands
  analysis_runner.py  -- Analysis vector orchestration
  audit.py            -- Audit system with severity levels
  era_scanner.py      -- Era transition detection
  era_cascade.py      -- Era label propagation
  era_mapper.py       -- Era boundary mapping
  report.py           -- Report generation (markdown/HTML)
  demo.py             -- Demo project generation
  local_pipeline.py   -- Local GitHub pipeline inspection
  utils.py            -- Utilities
  db/                 -- Database utilities and schema
  classifiers/        -- Signal classification logic
  extractors/         -- Data extraction (git, logs, etc.)
  validators/         -- Output validation
  visualization/      -- Template-based visualization generation
analysis-vectors/     -- Analysis vector definitions and prompts
  sdlc-gap-finder.md
  ml-pattern-mapper.md
  agentic-workflow.md
  formal-terms-mapper.md
  source-archaeologist.md
  youtube-correlator.md
config/               -- Configuration templates and schemas
  defaults.json       -- Default configuration values
  project-schema.json -- Project configuration schema
  datasette-metadata.yaml -- Datasette server metadata
scripts/              -- Utility scripts
setup/                -- Project setup questionnaire
shared/               -- Framework-wide reference docs
skills/               -- Bundled skill for Claude Code CLI usage
stages/               -- Stage-based pipeline (legacy, kept for reference)
_config/              -- Developer profile templates
setup.py              -- Package installation configuration
```

## Trigger Keywords

### Project Management
- `init <name>` -- Initialize a new archaeology project
- `demo [--build-db]` -- Create a demo project with synthetic data
- `status` -- Show project status

### Data Extraction
- `mine <repo-path>` -- Extract git history from repository
- `build-db <project>` -- Build SQLite database from mined data
- `ingest-pipeline` -- Ingest GitHub Actions logs

### Signal Detection
- `signals <project>` -- Run signal detection heuristics
- `extract-sessions` -- Extract coding sessions from commits

### Analysis
- `analyze <project>` -- Run analysis vectors
- `cascade <project>` -- Cascade era labels across repos

### Visualization & Reporting
- `visualize <project>` -- Generate HTML visualization
- `export-report <project>` -- Export report (markdown/HTML)
- `public-case-study` -- Create sanitized public case study

### Database & Inspection
- `serve <project>` -- Start Datasette server for database inspection

### Audit & Validation
- `audit <project>` -- Run audit checks with severity levels
- `validate <project>` -- Validate project configuration

### Multi-Project Operations
- `sync` -- Sync multiple projects
- `global-viz` -- Generate global visualization across projects
- `fetch-github` -- Fetch repository metadata from GitHub

### Local Pipeline
- `local-pipeline` -- Inspect local GitHub pipeline

## Routing Table

| Intent                        | CLI Command                  | Action                              |
|-------------------------------|------------------------------|-------------------------------------|
| Initialize new project        | `devarch init`              | Create project configuration        |
| Create demo project           | `devarch demo`              | Generate synthetic project          |
| Extract commit data           | `devarch mine`              | Run git log extraction              |
| Build database                | `devarch build-db`          | Create SQLite DB from mined data    |
| Find patterns                 | `devarch signals`           | Run signal detection                |
| Detect eras                   | `devarch cascade`           | Scan and cascade era labels         |
| Analyze specific aspects      | `devarch analyze`           | Run analysis vectors                |
| Generate visualization        | `devarch visualize`         | Create HTML visualization           |
| Export report                 | `devarch export-report`     | Export markdown/HTML report         |
| Validate results              | `devarch audit`             | Run consistency checks              |
| Inspect database              | `devarch serve`             | Start Datasette server              |
| Sync multiple projects        | `devarch sync`              | Aggregate multi-project data        |
| Create public case study      | `devarch public-case-study` | Generate sanitized demo             |

## Core Concepts

**Signal Detection**: 5 heuristics identify noteworthy patterns (gaps, velocity shifts, author changes, scope changes, supplementary correlations).

**Analysis Vectors**: 6 specialized analyzers extract specific insights:
- SDLC Gap Finder -- Identify gaps in software development lifecycle practices
- ML Pattern Mapper -- Detect machine learning patterns and practices
- Agentic Workflow Analyzer -- Identify AI/agent-based workflows
- Formal Terms Mapper -- Track formal methods and terminology usage
- Source Archaeologist -- Deep code archaeology and evolution tracking
- YouTube Correlator -- Correlate commit patterns with YouTube watch history

**Era System**: Detect and track distinct phases in repository evolution through scanner, cascade, and mapper components.

**Audit System**: Validate outputs with severity-based checks (CRITICAL, HIGH, MEDIUM, LOW).

**Supplementary Data**: Any external data with dates can be correlated against commit history to surface patterns.

**Multi-Project Sync**: Aggregate findings across multiple repositories with global visualization.

**Database**: SQLite database with FTS5 full-text search for commit and signal inspection.

**Visualization**: Template-based HTML generation with hydration for per-project visualizations.

**Demo Generation**: Create demo projects with synthetic data for testing and documentation.

## Sync Rules

### Parity with dev-archaeology
- This repo must maintain 100% feature parity with dev-archaeology
- dev-archaeology is the LAB (working version with real data)
- This repo is the PRODUCT (sterilized, publishable version)
- Never contain real project data (no LIMINAL, no sessions, no YouTube data)
- Use only synthetic/demo data in projects/

### When dev-archaeology changes
- New CLI commands → copy command function to this repo's cli.py
- New Python modules → copy to this repo's archaeology/ package
- New templates → copy to this repo's archaeology/visualization/
- New analysis vectors → copy analysis-vectors/*.md
- New config → copy config/ files
- After sync: run `python3 scripts/sync/check_parity.py` from dev-archaeology to verify

### Verification
- Run `python3 -m archaeology.cli demo --force --build-db` after changes
- Run `python3 -m archaeology.cli audit demo-project` to verify quality gate
- The demo project must always work end-to-end

### Git Workspace Hygiene
Agents must leave the repository in the same clean state they found it. No exceptions.

- **Delete feature branches** after merge — whether you merged via PR or locally. A merged branch that still exists is a failure.
- **Remove worktrees** when done. If you created a git worktree for isolated work, remove it when the work is complete or abandoned. No orphaned worktrees.
- **Clean up stale references** — prune remote-tracking branches that no longer exist upstream (`git remote prune origin`).
- **No abandoned work left behind** — if you started a branch, pushed it, and then the task was cancelled or superseded, delete the branch. Dead branches accumulate and confuse everyone.
- **Local branches stay current** — regularly rebase local tracking branches against their upstream. If a local branch has diverged and is no longer needed, delete it.
- **Worktree state matches intent** — if you're done with a task, the working directory should be clean (`git status` shows nothing). Staged changes, untracked files, and modified files from abandoned work are not acceptable.

The rule is simple: finish your work, merge or discard it, clean up every artifact you created. The main branch is the only permanent artifact. Everything else is temporary and must be treated as such.

### Epoch Data Tracking

Every project must use Epoch (KyaniteLabs/Epoch) for time estimation and actively feed it data. Epoch only becomes useful when it has real estimate-vs-actual data from real projects.

### What This Means
- **Before starting a task**, get a time estimate from Epoch (via MCP, REST API at `localhost:3099`, or CLI)
- **After completing a task**, record the actual time spent using `record_actual` or `POST /v1/feedback/record-actual`
- **Include context** — task type, complexity, tools used, anything that helps the model learn
- **Batch submissions are fine** — use `batch_record_actuals` for multiple estimates at once

### Integration
- MCP: add `@puenteworks/epoch` to your project's `.mcp.json`
- REST API: `epoch serve --port 3099`
- CLI: `npx @puenteworks/epoch pert-estimate ...`

### Why This Is Non-Negotiable
Epoch's accuracy improves with data. Without estimate-vs-actual feedback from real projects, it's just a calculator with uncalibrated assumptions. Every project that uses Epoch and reports back makes every other project's estimates better. This is a collective intelligence system — it only works if everyone contributes.

The data stored in `~/.epoch/` (estimates.jsonl + feedback.jsonl) is the project's most valuable asset. Protect it, back it up, and keep feeding it.

## ICM Compliance

Layer 0: CLAUDE.md (this file)
Layer 1: CONTEXT.md (task routing)
Layer 2: Stage CONTEXT.md files (input/process/output contracts)
Layer 3: references/ and shared/ folders
Layer 4: output/ folders with .gitkeep
