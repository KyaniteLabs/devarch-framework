# Content Engine for DevArch

Automated content generation system that transforms archaeological analysis outputs into publishable weekly excavation reports.

## Overview

The content engine scans project deliverables for analysis outputs and generates:

- **Excavation Report** (`excavation-report-YYYY-MM-DD.md`) - Comprehensive weekly analysis summary
- **Twitter Thread** (`twitter-thread-YYYY-MM-DD.md`) - Social media content outline
- **Blog Draft** (`blog-draft-YYYY-MM-DD.md`) - Long-form content starter

## Usage

### Basic Usage

Generate a report for a project:

```bash
python scripts/content/generate_excavation_report.py <project-name>
```

### Custom Date Range

Specify a custom date range:

```bash
python scripts/content/generate_excavation_report.py <project-name> 2026-04-23 2026-04-30
```

### Available Projects

The script works with any project in the `projects/` directory that has archaeological analysis outputs.

## Output Locations

Generated reports are saved to: `projects/<project>/deliverables/content/`

```
projects/<project>/deliverables/content/
├── excavation-report-2026-04-30.md
├── twitter-thread-2026-04-30.md
└── blog-draft-2026-04-30.md
```

## Scheduling

### Cron Job (Weekly Execution)

Add to your crontab (`crontab -e`):

```bash
# Generate excavation reports every Friday at 6 PM
0 18 * * 5 cd /path/to/devarch-framework && python3 scripts/content/generate_excavation_report.py <project> >> logs/content-engine.log 2>&1
```

### GitHub Actions Workflow

Create `.github/workflows/excavation-report.yml`:

```yaml
name: Weekly Excavation Report

on:
  schedule:
    - cron: '0 18 * * 5'
  workflow_dispatch:
    inputs:
      project:
        description: 'Project name to analyze'
        required: true
        type: string

jobs:
  generate-report:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: python scripts/content/generate_excavation_report.py "${{ github.event.inputs.project }}"
      - run: |
          git config --local user.email "action@github.com"
          git config --local user.name "GitHub Action"
          git add projects/*/deliverables/content/
          git diff --staged --quiet || git commit -m "chore: generate weekly excavation report [automated]"
          git push
```

## Report Structure

### Excavation Report

- This Week's Findings (narrative summary)
- By the Numbers (commits, signals, vectors, audit status)
- Key Insights (top findings from each vector)
- Agent Activity (session statistics)
- Recommended Actions (SDLC improvements by ROI)
- Content Opportunities (blog topics, video ideas)

### Twitter Thread

5-7 tweet thread: hook with statistics, insight tweets, call-to-action.

### Blog Draft

Long-form starter: headline from top finding, detailed analysis, implications, next steps.

## Data Sources

Reads from existing deliverable files:

- `canonical-metrics.json` - Commit counts and statistics
- `analysis-*.json` - Analysis vector outputs
- `AUDIT-REPORT.md` - Audit status and quality ratings

## Customization

Edit generation methods in `generate_excavation_report.py`:

- `generate_excavation_report()` - Main report structure
- `generate_twitter_thread()` - Social media content
- `generate_blog_draft()` - Blog post template

## Dependencies

Python standard library only. No external dependencies.
