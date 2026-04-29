# DevArch Task Routing

Map user intent to the appropriate stage and action.

## Routing Table

| User Intent                                          | Stage       | Next Action                      |
|------------------------------------------------------|-------------|----------------------------------|
| "Start a new archaeology project"                    | 01-setup    | Run questionnaire in setup/      |
| "Analyze this repository"                            | 02-mine     | Extract git history              |
| "Find gaps or patterns in commits"                   | 04-detect   | Run signal detection             |
| "What changed in the codebase?"                      | 05-analyze  | Run source archaeology vector    |
| "Show ML patterns or SDLC gaps"                      | 05-analyze  | Run ML or SDLC vectors           |
| "Create HTML visualization"                          | 06-visualize| Generate charts                  |
| "Generate full report"                               | 07-report   | Compile markdown and HTML        |
| "Check if results are accurate"                      | 08-audit    | Run validation checks            |
| "Create go-to-market strategy"                       | 09-strategy | Generate GTM from archaeology    |
| "Add fitness/YouTube/calendar data"                  | 05-analyze  | Configure supplementary source   |
| "Show current project status"                        | --          | Check project.json, output/      |

## Stage Dependencies

Stages must execute in order. Each stage consumes outputs from the previous stage.

01-setup → 02-mine → 03-build → 04-detect → 05-analyze → 06-visualize → 07-report → 08-audit → (09-strategy optional)

## Checkpoints

Two stages include checkpoints for manual review:

- **04-detect**: Review detected signals before analysis
- **05-analyze**: Review analysis findings before visualization

## Suppementary Data

Any external data with dates can be added at any time. Correlation runs in 05-analyze.

To add supplementary data: Use the `add-supplement` keyword or edit project.json directly.
