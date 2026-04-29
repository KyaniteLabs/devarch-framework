# project.json Schema

Specification for project configuration file.

## Root Schema

```json
{
  "developer_name": "string (required)",
  "github_username": "string (required)",
  "repo_path": "string (required, absolute path)",
  "project_name": "string (required)",
  "project_description": "string (required)",
  "signal_gap_threshold": "integer (optional, default 3)",
  "session_logs_available": "boolean (optional, default false)",
  "areas_of_interest": "array of strings (optional)",
  "supplementary_sources": "array (optional)"
}
```

## Field Descriptions

### developer_name

Display name for reports. Can be real name or handle.

### github_username

GitHub username for API calls and attribution.

### repo_path

Absolute filesystem path to git repository. Must be a valid git repository.

### project_name

Short name for project. Used in filenames and references. lowercase-with-hyphens recommended.

### project_description

One-sentence description of project purpose.

### signal_gap_threshold

Minimum days of inactivity to flag as gap. Default: 3.

### session_logs_available

Whether Claude Code session logs are available for analysis.

### areas_of_interest

List of development aspects to prioritize in analysis. Examples: velocity, bugs, refactors, features.

### supplementary_sources

Array of supplementary data source configurations.

## Supplementary Source Schema

```json
{
  "name": "string (required)",
  "path": "string (required, absolute path)",
  "format": "string (required: json|csv|markdown)",
  "type": "string (required: fitness|media|calendar|weather|astronomical|custom)"
}
```

## Validation Rules

- repo_path must exist and be a git repository
- project_name must be non-empty
- supplementary_sources paths must exist if provided
- format must be one of: json, csv, markdown
