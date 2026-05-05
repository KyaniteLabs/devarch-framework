# Content Engine for Dev-Archaeology

Automated content generation system that transforms archaeological analysis outputs into publishable weekly excavation reports.

## Overview

The content engine scans project deliverables for analysis outputs and generates:

- **Excavation Report** (`excavation-report-YYYY-MM-DD.md`) - Comprehensive weekly analysis summary
- **Twitter Thread** (`twitter-thread-YYYY-MM-DD.md`) - Social media content outline
- **Blog Draft** (`blog-draft-YYYY-MM-DD.md`) - Long-form content starter

## Usage

### Basic Usage

Generate a report for the past week:

```bash
python scripts/content/generate_excavation_report.py liminal
```

### Custom Date Range

Specify a custom date range:

```bash
python scripts/content/generate_excavation_report.py liminal 2026-04-23 2026-04-30
```

### Available Projects

The script works with any project in the `projects/` directory that has archaeological analysis outputs:

- `liminal` - Main Liminal project analysis
- `demo-archaeology` - Demo archaeology project
- `dev-archaeology` - Dev-archaeology self-analysis
- `github-pipeline` - GitHub pipeline analysis
- `voice-to-sculpture` - Voice-to-sculpture project analysis

## Output Locations

Generated reports are saved to: `projects/<project>/deliverables/content/`

Example:
```
projects/liminal/deliverables/content/
├── excavation-report-2026-04-30.md
├── twitter-thread-2026-04-30.md
└── blog-draft-2026-04-30.md
```

## Scheduling

### Option 1: Cron Job (Weekly Execution)

Add to your crontab (`crontab -e`):

```bash
# Generate excavation reports every Friday at 6 PM
0 18 * * 5 cd /Users/simongonzalezdecruz/workspaces/dev-archaeology && /usr/bin/python3 scripts/content/generate_excavation_report.py liminal >> logs/content-engine.log 2>&1
```

To run for multiple projects:

```bash
# Generate reports for all projects every Friday at 6 PM
0 18 * * 5 cd /Users/simongonzalezdecruz/workspaces/dev-archaeology && for project in liminal demo-archaeology dev-archaeology; do /usr/bin/python3 scripts/content/generate_excavation_report.py $project >> logs/content-engine.log 2>&1; done
```

### Option 2: GitHub Actions Workflow

Create `.github/workflows/excavation-report.yml`:

```yaml
name: Weekly Excavation Report

on:
  schedule:
    # Runs every Friday at 6 PM UTC
    - cron: '0 18 * * 5'
  workflow_dispatch:
    inputs:
      project:
        description: 'Project name to analyze'
        required: true
        default: 'liminal'
        type: choice
        options:
          - liminal
          - demo-archaeology
          - dev-archaeology
          - github-pipeline
          - voice-to-sculpture
      start_date:
        description: 'Start date (YYYY-MM-DD, optional)'
        required: false
        type: string
      end_date:
        description: 'End date (YYYY-MM-DD, optional)'
        required: false
        type: string

jobs:
  generate-report:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Generate excavation report
        run: |
          PROJECT="${{ github.event.inputs.project || 'liminal' }}"
          START_DATE="${{ github.event.inputs.start_date }}"
          END_DATE="${{ github.event.inputs.end_date }}"

          python scripts/content/generate_excavation_report.py "$PROJECT" "$START_DATE" "$END_DATE"

      - name: Commit and push reports
        run: |
          git config --local user.email "action@github.com"
          git config --local user.name "GitHub Action"
          git add projects/*/deliverables/content/
          git diff --staged --quiet || git commit -m "chore: generate weekly excavation report [automated]"
          git push
```

### Option 3: Integration with Cascade Pipeline

Add the content engine as a final step in your analysis cascade:

```bash
# In your analysis pipeline script
#!/bin/bash

# Run all analysis vectors
python scripts/analysis/source_archaeologist.py "$PROJECT"
python scripts/analysis/sdlc_gap_finder.py "$PROJECT"
python scripts/analysis/ml_pattern_mapper.py "$PROJECT"
# ... other analysis scripts

# Generate content from results
python scripts/content/generate_excavation_report.py "$PROJECT"

echo "Analysis complete. Reports generated in projects/$PROJECT/deliverables/content/"
```

## Report Structure

### Excavation Report

```markdown
# Excavation Report: Week of YYYY-MM-DD to YYYY-MM-DD
## Project: [Project Name]

### This Week's Findings
[Narrative summary of the week's analysis]

### By the Numbers
- Total commits analyzed: X
- New signals detected: X
- Analysis vectors run: X/6
- Audit status: [PASS/FAIL]

### Key Insights
[Top findings from each analysis vector]

### Agent Activity
[Session statistics and contributor breakdown]

### Recommended Actions
[SDLC improvement recommendations sorted by ROI]

### Content Opportunities
[Blog topics, video ideas, social post suggestions]
```

### Twitter Thread

5-7 tweet thread optimized for engagement:
- Hook tweet with key statistics
- 3-5 insight tweets
- Call-to-action with report link

### Blog Draft

Long-form content starter with:
- Compelling headline based on top finding
- Introduction with context
- Detailed finding analysis
- Broader implications section
- Conclusion and next steps

## Data Sources

The content engine reads from existing deliverable files:

- `canonical-metrics.json` - Commit counts and project statistics
- `analysis-source-archaeologist.json` - Quality trajectory and architecture drift
- `analysis-sdlc-gap-finder.json` - Practice gaps and recommendations
- `analysis-ml-pattern-mapper.json` - Pattern recognition and formal terms
- `analysis-agentic-workflow.json` - Agent activity and session taxonomy
- `analysis-formal-terms-mapper.json` - Formal terminology mapping
- `analysis-youtube-correlator.json` - Video content correlations
- `AUDIT-REPORT.md` - Audit status and quality ratings

## Customization

### Modifying Report Templates

Edit the generation methods in `generate_excavation_report.py`:

- `generate_excavation_report()` - Main report structure
- `generate_twitter_thread()` - Social media content
- `generate_blog_draft()` - Blog post template
- `generate_content_opportunities()` - Content suggestions

### Adding New Analysis Vectors

When adding new analysis scripts, update the `count_analysis_vectors()` method to include the new output file.

### Extending Content Types

Add new content generation methods following the existing pattern:

```python
def generate_custom_content(self) -> str:
    """Generate custom content format."""
    # Extract relevant data
    # Build content structure
    # Return formatted string
```

Then call from `save_reports()` and save the output.

## Troubleshooting

### Missing Data Files

If analysis outputs don't exist, the script handles missing files gracefully:

```
Warning: Could not load analysis-file.json: [Errno 2] No such file or directory
```

Run the missing analysis script first:

```bash
python scripts/analysis/source_archaeologist.py liminal
```

### Permission Errors

Ensure the script has execute permissions:

```bash
chmod +x scripts/content/generate_excavation_report.py
```

### Python Version

Requires Python 3.10+. Check your version:

```bash
python3 --version
```

## Logging

For scheduled executions, redirect output to a log file:

```bash
python scripts/content/generate_excavation_report.py liminal >> logs/content-engine.log 2>&1
```

Create the logs directory if it doesn't exist:

```bash
mkdir -p logs
```

## Dependencies

The content engine uses only Python standard library modules:

- `argparse` - Command-line argument parsing
- `json` - JSON file handling
- `pathlib` - Cross-platform path handling
- `datetime` - Date/time operations
- `re` - Regular expression parsing

No external dependencies required.

## Future Enhancements

Potential improvements to the content engine:

- [ ] Add JSON output format for API integration
- [ ] Support for multiple output formats (PDF, HTML)
- [ ] Email notification of new reports
- [ ] Integration with CMS platforms (WordPress, Hugo)
- [ ] Historical trend analysis across multiple reports
- [ ] Custom report templates via configuration
- [ ] Multi-project comparative reports
- [ ] RSS feed generation from reports

## Contributing

When extending the content engine:

1. Maintain backward compatibility with existing data formats
2. Handle missing data gracefully with sensible defaults
3. Follow Python standard library conventions
4. Add clear docstrings for new methods
5. Update this README with new features

## License

Part of the dev-archaeology project. See project LICENSE for details.
