# DevArch Task Routing

Route user intent to the appropriate workspace. Each workspace loads only its own context.

## Workspaces

| Workspace | Commands | Mental Mode |
|-----------|----------|-------------|
| **Extraction** | `mine`, `build-db`, `serve`, `ingest-pipeline` | Get raw data from git repos |
| **Analysis** | `signals`, `analyze`, `cascade`, `extract-sessions` | Find patterns and insights |
| **Reporting** | `visualize`, `export-report`, `audit`, `validate`, `public-case-study` | Generate human-readable output |
| **Multi-Project** | `sync`, `global-viz`, `fetch-github`, `benchmark` | Aggregate across repos |
| **Setup** | `init`, `demo`, `status` | Configure new projects |

## Task Routing

| Your Task | Go Here | Read | You'll Also Need |
|-----------|---------|------|------------------|
| **Mine a repo** | stages/02-mine/CONTEXT.md | Stage contract | — |
| **Build the database** | stages/03-build/CONTEXT.md | Stage contract | — |
| **Run signal detection** | stages/04-detect/CONTEXT.md | Stage contract | shared/signal-heuristics.md |
| **Run analysis vectors** | stages/05-analyze/CONTEXT.md | Stage contract | analysis-vectors/<vector>.md |
| **Detect eras** | stages/04-detect/CONTEXT.md | Stage contract | shared/concepts.md (Era System) |
| **Generate visualization** | stages/06-visualize/CONTEXT.md | Stage contract | — |
| **Export report** | stages/07-report/CONTEXT.md | Stage contract | — |
| **Run audit** | stages/08-audit/CONTEXT.md | Stage contract | — |
| **Sync multiple projects** | Multi-project section below | config/profile.json | — |
| **Create demo** | stages/01-setup/CONTEXT.md | Stage contract | setup/questionnaire.md |

## Pipeline Flow

```
setup → mine → build-db → signals → analyze → visualize → report → audit
                                                                    ↓
                                                              strategy (optional)

Optional at any point:
  cascade, serve, public-case-study, sync, global-viz
```

## Cross-Workspace Flow

```
Setup (init, demo)
    ↓ project.json created
Extraction (mine → build-db)
    ↓ archaeology.db created
Analysis (signals → cascade → analyze)
    ↓ detected-signals.json + analysis-*.json created
Reporting (visualize → report → audit)
    ↓ HTML + markdown reports + audit result
Strategy (optional GTM from archaeology data)
```

Each workspace consumes output from the previous workspace. An agent in extraction never needs analysis vectors. An agent in analysis never needs visualization templates.

## Checkpoints

- **After signals**: Review detected signals before running analysis. Human checks threshold values.
- **After analyze**: Review findings before generating visualizations. Human checks for meaningful results.
- **After audit**: Review severity issues before considering pipeline complete. Human addresses CRITICAL/HIGH.

## Supplementary Data

Any external data with timestamps can be added at any stage. Configure in `project.json` under `supplementary_sources`. Correlation runs automatically during signal detection (stage 04) and analysis (stage 05).

Supported: fitness data, YouTube history, calendar events, weather, lunar phases, any timestamped CSV/JSON.

## Multi-Project

For multi-project analysis, configure `config/profile.json` with project paths, then run `devarch sync` or `devarch global-viz`.

## Analysis Vectors

`devarch analyze` supports 6 vectors (run all or specify with `-v`):
- `sdlc-gap-finder` — SDLC practice gaps
- `ml-pattern-mapper` — ML pattern detection
- `agentic-workflow` — AI/agent workflow identification
- `formal-terms-mapper` — Formal methods terminology
- `source-archaeologist` — Deep code archaeology
- `youtube-correlator` — YouTube watch history correlation
