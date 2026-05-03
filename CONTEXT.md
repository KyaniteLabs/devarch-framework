# DevArch Task Routing

Map user intent to the appropriate CLI command or action.

## Routing Table

| User Intent                                          | CLI Command                    | Action                              |
|------------------------------------------------------|--------------------------------|-------------------------------------|
| "Start a new archaeology project"                    | `devarch init <name>`          | Initialize project configuration    |
| "Create a demo project"                              | `devarch demo [--build-db]`    | Generate synthetic project          |
| "Analyze this repository"                            | `devarch mine <path>`          | Extract git history                 |
| "Build the database"                                 | `devarch build-db <project>`   | Create SQLite database              |
| "Find gaps or patterns in commits"                   | `devarch signals <project>`    | Run signal detection                |
| "Detect eras in the codebase"                        | `devarch cascade <project>`    | Scan and cascade era labels         |
| "What changed in the codebase?"                      | `devarch analyze <project>`    | Run source archaeology vector       |
| "Show ML patterns or SDLC gaps"                      | `devarch analyze -v <vector>`  | Run ML or SDLC vectors              |
| "Create HTML visualization"                          | `devarch visualize <project>`  | Generate charts and HTML            |
| "Generate full report"                               | `devarch export-report`        | Export markdown/HTML report         |
| "Check if results are accurate"                      | `devarch audit <project>`      | Run validation checks               |
| "Inspect the database"                               | `devarch serve <project>`      | Start Datasette server              |
| "Sync multiple projects"                             | `devarch sync`                 | Aggregate multi-project data        |
| "Create global visualization"                        | `devarch global-viz`           | Generate cross-project charts       |
| "Add fitness/YouTube/calendar data"                  | Configure in project.json      | Add supplementary data source       |
| "Show current project status"                        | `devarch status` (coming soon) | Check project state                 |

## Command Dependencies

Commands must execute in order. Each command consumes outputs from the previous command.

init → mine → build-db → signals → analyze → visualize → export-report → audit

Optional commands at any stage:
- `cascade` -- Era detection and propagation
- `serve` -- Database inspection (after build-db)
- `public-case-study` -- Create sanitized demo
- `sync` -- Multi-project aggregation
- `global-viz` -- Cross-project visualization

## Analysis Vectors

The `devarch analyze` command supports 6 analysis vectors:

- `sdlc-gap-finder` -- Identify gaps in SDLC practices
- `ml-pattern-mapper` -- Detect ML patterns and practices
- `agentic-workflow` -- Identify AI/agent-based workflows
- `formal-terms-mapper` -- Track formal methods terminology
- `source-archaeologist` -- Deep code archaeology
- `youtube-correlator` -- Correlate with YouTube watch history

Run all vectors: `devarch analyze <project>`
Run specific vectors: `devarch analyze <project> -v sdlc-gap-finder -v ml-pattern-mapper`

## Checkpoints

Review checkpoints are manual steps in the workflow:

- **After signals**: Review detected signals before running analysis vectors
- **After analyze**: Review analysis findings before generating visualizations

## Supplementary Data

Any external data with dates can be added at any time. Correlation runs automatically during analysis.

To add supplementary data: Edit project.json and add to `supplementary_sources` array.

Supported types:
- Fitness tracker data (CSV/JSON)
- YouTube watch history (JSON)
- Calendar events (CSV/JSON)
- Weather data (CSV)
- Lunar phases (JSON)
- Any timestamped data

## Multi-Project Sync

For multi-project analysis, configure `config/profile.json`:

```json
{
  "projects": [
    {"name": "project-one", "path": "/path/to/project-one"},
    {"name": "project-two", "path": "/path/to/project-two"}
  ],
  "developer": {
    "name": "Your Name",
    "github_username": "yourusername"
  }
}
```

Then run: `devarch sync` or `devarch sync --project project-one --project project-two`

## Database Inspection

Start a Datasette server to inspect your archaeology database:

```bash
devarch serve my-project --port 8001
```

Visit http://localhost:8001 to explore commits, signals, eras, and analysis results with full-text search.
