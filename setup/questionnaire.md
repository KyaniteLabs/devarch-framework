# DevArch Setup Questionnaire

Answer these questions to initialize your archaeology project.

## Questions

1. **Name or handle**
   What name should appear in reports?

2. **GitHub username**
   Your GitHub username for API calls.

3. **Repository path**
   Local filesystem path to the git repository (e.g. /Users/you/projects/myapp).

4. **Project name**
   Short name for this project (used in filenames).

5. **Project description**
   One-sentence description of what this project does.

6. **Signal gap threshold**
   Minimum days of inactivity to flag as a gap (default: 3).

7. **Claude Code sessions available**
   Do you have access to Claude Code session logs? (y/n)

8. **Areas of interest**
   What aspects of development history matter most? (e.g. velocity, bug fixes, refactors, feature work)

9. **Supplementary data sources**
   Do you have any external data to correlate with your commits?
   Examples: YouTube watch history (JSON), fitness/sleep data (CSV), calendar events, weather data, lunar phases, trading activity, study logs.
   List file paths and types.

10. **Report preferences**
    What outputs do you need? (HTML report, markdown, raw data, visualizations)

## Next Steps

After answering these questions, stage 01-setup will generate:

- project.json with your configuration
- Directory structure for all stages
- Initial .gitkeep files in output folders
