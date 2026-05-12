# DevArch Framework

Forensic archaeology framework for git repositories. Python CLI with 20+ commands for extracting commit history, detecting signals, running 6 analysis vectors, and generating reports.

## ICM Layers

| Layer | File | Purpose | Loads |
|-------|------|---------|-------|
| L0 | CLAUDE.md (this file) | Where am I? | Always |
| L1 | CONTEXT.md | Where do I go? | On entry |
| L2 | stages/*/CONTEXT.md | What do I do? | Per task |
| L3 | shared/, analysis-vectors/, stages/*/references/ | What rules apply? | Selectively |
| L4 | stages/*/output/ | What am I working with? | Selectively |

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
config/               -- Configuration templates and schemas
scripts/              -- Utility scripts
setup/                -- Project setup questionnaire
shared/               -- Framework-wide reference docs (L3)
skills/               -- Bundled skill for Claude Code CLI usage
stages/               -- Stage-based pipeline contracts (L2)
_config/              -- Developer profile templates
```

## Routing Table

| Intent | CLI Command | Read | Skip |
|--------|-------------|------|------|
| Initialize new project | `devarch init` | CONTEXT.md → setup stage | analysis-vectors/, shared/ |
| Create demo project | `devarch demo` | CONTEXT.md → setup stage | stages/04+ |
| Extract commit data | `devarch mine` | CONTEXT.md → extraction workspace | analysis-vectors/, shared/ |
| Build database | `devarch build-db` | CONTEXT.md → extraction workspace | stages/04+ |
| Find patterns | `devarch signals` | CONTEXT.md → analysis workspace | visualization/ |
| Detect eras | `devarch cascade` | CONTEXT.md → analysis workspace | stages/01-03 |
| Run analysis vectors | `devarch analyze` | CONTEXT.md → analysis workspace + analysis-vectors/ | stages/01-03 |
| Generate visualization | `devarch visualize` | CONTEXT.md → reporting workspace | stages/01-05 |
| Export report | `devarch export-report` | CONTEXT.md → reporting workspace | stages/01-05 |
| Run audit | `devarch audit` | CONTEXT.md → reporting workspace | stages/01-07 |
| Inspect database | `devarch serve` | CONTEXT.md → extraction workspace | analysis-vectors/ |
| Sync multiple projects | `devarch sync` | CONTEXT.md → multi-project section | stages/ |
| Create public case study | `devarch public-case-study` | CONTEXT.md → reporting workspace | analysis-vectors/ |

## Token Management

**Each workspace is siloed. Don't load everything.**

- Running `devarch mine`? → Load extraction workspace only. Skip analysis-vectors/, shared/, stages/04+.
- Running `devarch analyze`? → Load analysis workspace + relevant analysis vectors. Skip stages/01-03, visualization/.
- Running `devarch visualize`? → Load reporting workspace only. Skip stages/01-05, analysis-vectors/.
- Editing the framework itself? → Load shared/concepts.md + shared/sync-rules.md.

The CONTEXT.md files tell you which workspace you're in. Trust them.

## Naming Conventions

| Type | Pattern | Example |
|------|---------|---------|
| Project configs | `project.json` | `project.json` |
| Mined data | `github-commits.csv` | `github-commits.csv` |
| Databases | `archaeology.db` | `archaeology.db` |
| Signals | `detected-signals.json` | `detected-signals.json` |
| Analysis output | `analysis-<vector>.json` | `analysis-sdlc-gap-finder.json` |
| Visualizations | `<project>-viz.html` | `demo-project-viz.html` |
| Reports | `<project>-report.md` | `demo-project-report.md` |

## File Placement

- **Project data**: `projects/<name>/`
- **Stage outputs**: `stages/<NN>-<name>/output/`
- **Reference docs**: `shared/`
- **Sync rules**: `shared/sync-rules.md`
- **Concepts**: `shared/concepts.md`
- **Decisions log**: `docs/decisions.md`
