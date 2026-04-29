# Stage 01-Setup

Initialize project configuration from questionnaire answers.

## Inputs

- Questionnaire responses from setup/questionnaire.md

## Process

1. Parse questionnaire answers
2. Validate repository path exists and is a git repo
3. Create project.json with configuration
4. Generate directory structure for all stages
5. Create .gitkeep files in all output/ folders
6. Copy developer profile template to _config/developer-profile.md

## Outputs

- project.json in workspace root
- _config/developer-profile.md (populated template)
- Directory structure for all 8 stages
- .gitkeep files in all output/ folders

## project.json Schema

```json
{
  "developer_name": "string",
  "github_username": "string",
  "repo_path": "/absolute/path/to/repo",
  "project_name": "string",
  "project_description": "string",
  "signal_gap_threshold": 3,
  "session_logs_available": false,
  "areas_of_interest": ["list"],
  "supplementary_sources": []
}
```

## Success Criteria

- project.json created with all required fields
- Repository path validated as git repository
- All stage directories exist with output/ subdirectories
- Developer profile template populated

## Next Stage

Proceed to 02-mine to extract git history.
