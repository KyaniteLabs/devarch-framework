# DevArch Framework

Forensic archaeology framework for git repositories. Extract commit history, detect signals, run analysis vectors, and generate comprehensive reports.

## Public Discovery

**DevArch Framework** is a forensic repository archaeology system for understanding how software projects evolved. It mines git history, builds analyzable SQLite datasets, detects development signals, runs specialized analysis vectors, and generates reports for engineering, product, research, and AI-agent review.

**AI discovery:** [`llms.txt`](llms.txt) provides a compact project summary for AI assistants and search crawlers.

**Best-fit searches:** repository archaeology, git history analysis, software forensic analysis, development archaeology, agentic codebase review, ICM framework, engineering history reports, commit mining pipeline.

## What It Does

DevArch transforms git history into structured insights through an 8-stage pipeline:

1. **Setup** -- Initialize project configuration
2. **Mine** -- Extract git history
3. **Build** -- Create SQLite database
4. **Detect** -- Identify signals (gaps, velocity shifts, author changes)
5. **Analyze** -- Run analysis vectors (SDLC gaps, ML patterns, formal terms)
6. **Visualize** -- Generate HTML with charts
7. **Report** -- Compile markdown and HTML reports
8. **Audit** -- Validate all outputs

## Key Features

- **Signal Detection**: 5 heuristics identify noteworthy patterns
- **Analysis Vectors**: Specialized analyzers for SDLC, ML, formal methods
- **Supplementary Data**: Correlate any external data (fitness, YouTube, calendar) with commits
- **ICM Compliant**: Follows Interpretable Context Methodology conventions
- **Checkpoints**: Manual review at key stages for quality control

## Quick Start

### 1. Setup

Run the setup questionnaire:

```
Answer questions in setup/questionnaire.md
Stage 01-setup creates project.json
```

### 2. Run Pipeline

Execute stages manually or use CLI:

```bash
# Manual: Read each stage's CONTEXT.md and follow instructions
# CLI: Run commands sequentially
python archaeology/cli.py setup
python archaeology/cli.py mine
python archaeology/cli.py build
python archaeology/cli.py detect
# Review checkpoint
python archaeology/cli.py analyze
# Review checkpoint
python archaeology/cli.py visualize
python archaeology/cli.py report
python archaeology/cli.py audit
```

### 3. View Results

Final reports in stages/07-report/output/:

- ARCHAEOLOGY-REPORT.md
- ARCHAEOLOGY-REPORT.html

## Supplementary Data

Add external data sources to correlate with commits:

- Fitness tracker data (CSV/JSON)
- YouTube watch history (JSON)
- Calendar events (CSV/JSON)
- Weather data (CSV)
- Lunar phases (JSON)
- Any data with dates

Configure in project.json:

```json
{
  "supplementary_sources": [
    {
      "name": "fitness-data",
      "path": "/path/to/fitness.json",
      "format": "json",
      "type": "fitness"
    }
  ]
}
```

## ICM Compliance

This framework follows ICM conventions:

- **Layer 0**: CLAUDE.md (identity + folder map + trigger keywords)
- **Layer 1**: CONTEXT.md (task routing)
- **Layer 2**: Stage CONTEXT.md files (input/process/output contracts)
- **Layer 3**: references/ and shared/ folders
- **Layer 4**: output/ folders with .gitkeep

## Folder Structure

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

- `setup` -- Launch setup questionnaire
- `status` -- Show current stage, checkpoint status
- `mine <repo>` -- Extract git data from repository
- `audit` -- Run audit stage, validate outputs
- `add-supplement <type>` -- Add supplementary data source

## Requirements

- Git repository with commit history
- Python 3.8+ (for CLI automation)
- sqlite-utils (for database creation)
- Write permissions in workspace directory

## License

This framework is provided as-is for repository archaeology and analysis.

## Support

For issues or questions:

1. Review stage CONTEXT.md files for specifications
2. Check references/ folders for detailed documentation
3. Run audit stage to validate outputs
4. Examine intermediate outputs in each stage folder
