# Developer Profile Template

Template for developer identity in DevArch reports.

## Profile Fields

```json
{
  "name": "{{DEVELOPER_NAME}}",
  "handle": "{{GITHUB_USERNAME}}",
  "timezone": "{{TIMEZONE}}",
  "session_logs_available": {{SESSION_LOGS_BOOL}},
  "areas_of_interest": [
    "{{INTEREST_1}}",
    "{{INTEREST_2}}"
  ]
}
```

## Usage

This template is populated during setup (stage 01-setup) from questionnaire answers.

The profile is referenced in report generation (stage 07-report) to personalize outputs.

## Fields Explained

- **name**: Display name for reports
- **handle**: GitHub username for API calls and attribution
- **timezone**: Used for date localization (optional)
- **session_logs_available**: Whether Claude Code session data exists
- **areas_of_interest**: Guides which analysis vectors to prioritize
