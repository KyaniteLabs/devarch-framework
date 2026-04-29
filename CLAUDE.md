# DevArch Framework

Forensic archaeology framework for git repositories. Extracts commit history, detects signals, runs analysis vectors, and generates reports.

## Identity

DevArch is a productized framework for repository archaeology. It transforms git history into structured insights through a pipeline of 8 stages. Supports supplementary data correlation to surface patterns across commit history and external data sources.

## Folder Map

```
setup/               -- Initial project questionnaire
_config/             -- Developer profile templates
shared/              -- Framework-wide reference docs
skills/              -- Bundled skill for CLI usage
stages/              -- Analysis pipeline
  01-setup/         -- Initialize project configuration
  02-mine/          -- Extract git data
  03-build/         -- Build SQLite database
  04-detect/        -- Detect signals
  05-analyze/       -- Run analysis vectors
  06-visualize/     -- Generate visualizations
  07-report/        -- Compile reports
  08-audit/         -- Quality gate
```

## Trigger Keywords

- `setup` -- Launch setup questionnaire, initialize project
- `status` -- Show current stage, checkpoint status
- `mine <repo>` -- Extract git data from repository
- `audit` -- Run audit stage, validate outputs
- `add-supplement <type>` -- Add supplementary data source for correlation

## Routing Table

| Intent                        | Stage     | Action                              |
|-------------------------------|-----------|-------------------------------------|
| Initialize new project        | 01-setup  | Run questionnaire, create config    |
| Extract commit data           | 02-mine   | Run git log extraction              |
| Build database                | 03-build  | Create SQLite DB from CSV           |
| Find patterns                 | 04-detect | Run signal detection                |
| Analyze specific aspects      | 05-analyze| Run analysis vectors                |
| Generate HTML report          | 06-visualize + 07-report | Create visualization and report |
| Validate results              | 08-audit  | Run consistency checks              |
| Add external data correlation | 05-analyze| Configure supplementary data source |

## Core Concepts

**Signal Detection**: 5 heuristics identify noteworthy patterns (gaps, velocity shifts, author changes, scope changes, supplementary correlations).

**Analysis Vectors**: Specialized analyzers extract specific insights (SDLC gaps, ML patterns, formal terms, source archaeology, supplementary correlation).

**Supplementary Data**: Any external data with dates can be correlated against commit history to surface patterns.

**Checkpoints**: Stages 04 and 05 include manual review checkpoints before proceeding.

## ICM Compliance

Layer 0: CLAUDE.md (this file)
Layer 1: CONTEXT.md (task routing)
Layer 2: Stage CONTEXT.md files (input/process/output contracts)
Layer 3: references/ and shared/ folders
Layer 4: output/ folders with .gitkeep
