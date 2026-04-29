# DevArch Skill

Bundled skill for using the DevArch framework with Claude Code.

## What This Skill Does

Provides shortcuts and patterns for running DevArch archaeology analysis on git repositories.

## When to Use This Skill

Use this skill when you want to:

- Analyze a git repository for development patterns
- Generate reports from commit history
- Correlate external data with commit activity
- Understand codebase evolution over time

## Usage Patterns

### Manual Stage Execution

Run stages individually for granular control:

1. Read stages/01-setup/CONTEXT.md for setup instructions
2. Execute setup by answering questionnaire
3. Proceed through each stage sequentially
4. Review checkpoints at stages 04 and 05

### CLI Automation

Use the Python CLI for automated execution:

```bash
cd /path/to/devarch-framework
python archaeology/cli.py setup
python archaeology/cli.py mine
python archaeology/cli.py build
python archaeology/cli.py detect
python archaeology/cli.py analyze
python archaeology/cli.py visualize
python archaeology/cli.py report
python archaeology/cli.py audit
```

### Keyword Triggers

Use these keywords with Claude Code:

- `setup` -- Initialize new project
- `status` -- Show current stage and progress
- `mine <repo>` -- Extract git data
- `audit` -- Run validation checks
- `add-supplement <type>` -- Add external data source

## Manual vs CLI

### Manual Execution

Best for:

- Learning the framework
- Customizing analysis
- Debugging issues
- Understanding intermediate outputs

Process:

- Read CONTEXT.md for current stage
- Follow inputs/process/outputs contract
- Use references/ for specifications
- Review outputs before proceeding

### CLI Automation

Best for:

- Repeatable analysis
- Large repositories
- Batch processing
- Production workflows

Process:

- Run CLI commands sequentially
- Outputs go to stage output/ folders
- Checkpoints still require manual review
- Audit validates all outputs

## Configuration

All configuration in project.json:

- Repository path
- Developer information
- Signal thresholds
- Supplementary data sources
- Analysis preferences

## Supplementary Data

To add external data correlation:

1. Ensure data has date, value, type fields
2. Convert to JSON, CSV, or Markdown format
3. Add entry to project.json supplementary_sources
4. Run stage 05-analyze to generate correlations

Supported data types:

- Fitness (steps, sleep, workouts)
- Media (YouTube history, reading)
- Calendar (events, meetings)
- Weather (temperature, conditions)
- Astronomical (lunar phases, solstices)
- Custom (any dated data)

## Outputs

Final outputs in stages/07-report/output/:

- ARCHAEOLOGY-REPORT.md -- Markdown report
- ARCHAEOLOGY-REPORT.html -- HTML with visualizations

Intermediate outputs available in each stage's output/ folder.

## Troubleshooting

### Setup fails

- Verify repository path is valid git repo
- Check write permissions in workspace
- Ensure questionnaire answers are complete

### Mining fails

- Verify git is installed
- Check repository has commits
- Ensure sufficient disk space

### Analysis fails

- Check database file exists
- Verify signals detected
- Review JSON schemas

### Visualization fails

- Verify analysis outputs exist
- Check template file present
- Review chart data format

## Best Practices

1. Always run stages in order
2. Review checkpoints before proceeding
3. Keep supplementary data simple (date, value, type)
4. Run audit after full pipeline
5. Back up project.json before changes
6. Use version control for customizations

## Integration with ICM

This skill follows ICM conventions:

- Layer 0: CLAUDE.md defines identity
- Layer 1: CONTEXT.md routes tasks
- Layer 2: Stage CONTEXT.md files specify contracts
- Layer 3: references/ provide specifications
- Layer 4: output/ folders contain results
