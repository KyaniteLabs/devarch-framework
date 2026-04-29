# Supplementary Data Schema

Generic schema for external data sources that correlate with commit history.

## Required Fields

Every supplementary data record must have:

- **date**: ISO 8601 date string (YYYY-MM-DD)
- **value**: Numeric or string value to correlate
- **type**: Category of data (fitness, media, calendar, weather, etc.)

## Optional Fields

- **category**: Sub-category within type (e.g. "running" within fitness)
- **tags**: Array of tags for filtering
- **duration**: Numeric duration in minutes (for events)
- **notes**: Free text field for context

## Supported Formats

### JSON

Array of objects with required fields:

```json
[
  {
    "date": "2024-01-15",
    "value": 5.2,
    "type": "fitness",
    "category": "running",
    "duration": 42,
    "tags": ["outdoor", "morning"]
  }
]
```

### CSV

Header row with required columns:

```csv
date,value,type,category,duration,tags
2024-01-15,5.2,fitness,running,42,"outdoor,morning"
```

### Markdown

Structured list with key-value pairs:

```markdown
## 2024-01-15

- type: fitness
- category: running
- value: 5.2
- duration: 42
- tags: outdoor, morning
```

## Correlation Method

DevArch uses date-join to correlate supplementary data with commits:

1. Extract date from each commit
2. Join with supplementary data on date
3. Flag events within 24 hours of commit
4. Generate correlation insights in stage 05-analyze

## Example Data Sources

### YouTube Watch History

```json
{
  "date": "2024-01-15",
  "value": "tutorial-video-id",
  "type": "media",
  "category": "youtube"
}
```

### Fitness Tracker Data

```json
{
  "date": "2024-01-15",
  "value": 10000,
  "type": "fitness",
  "category": "steps"
}
```

### Calendar Events

```json
{
  "date": "2024-01-15",
  "value": "team-meeting",
  "type": "calendar",
  "duration": 60
}
```

### Weather Data

```json
{
  "date": "2024-01-15",
  "value": 72,
  "type": "weather",
  "category": "temperature"
}
```

### Lunar Phases

```json
{
  "date": "2024-01-15",
  "value": "full-moon",
  "type": "astronomical",
  "category": "lunar"
}
```

## Configuration

Add supplementary data sources in project.json:

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

## Custom Sources

To add a custom data source:

1. Ensure data has date, value, type fields
2. Convert to JSON, CSV, or Markdown format
3. Add entry to project.json supplementary_sources
4. Run stage 05-analyze to generate correlations
