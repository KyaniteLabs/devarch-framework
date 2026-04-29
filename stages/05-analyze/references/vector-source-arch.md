# Source Archaeologist Vector

Deep dive into code evolution and file lifecycle.

## Purpose

Analyze codebase evolution, file patterns, and refactoring activity.

## Detection Patterns

### File Lifecycle

Track file creation, deletion, and renaming:

- Identify long-lived files vs short-lived
- Detect file renames and moves
- Track file churn rates

### Refactoring Patterns

Search for refactoring indicators:

- Patterns: refactor, cleanup, restructure, reorganize
- Identify major refactoring commits
- Track refactoring frequency

### Code Churn

Calculate code churn metrics:

- Lines added vs deleted over time
- Identify high-churn periods
- Track rewrite vs incremental change

### Module Evolution

Analyze module structure changes:

- Directory creation/deletion
- Module reorganization
- Dependency evolution

### Hotspots

Identify frequently changed files:

- Calculate change frequency per file
- Identify "hot" files requiring attention
- Track stability metrics

## Output Schema

```json
{
  "vector_name": "source-archaeologist",
  "findings": [
    {
      "type": "file_lifecycle",
      "description": "High churn in authentication module",
      "evidence": ["file paths"],
      "confidence": "high",
      "metrics": {
        "file_changes": 25,
        "timespan_days": 30,
        "churn_rate": 0.83
      }
    }
  ],
  "summary": {
    "total_findings": 5,
    "by_type": {
      "file_lifecycle": 2,
      "refactoring": 1,
      "code_churn": 1,
      "hotspot": 1
    }
  }
}
```

## Metrics

- Churn rate: commits per day for file/module
- Stability: inverse of churn
- Lifetime: days from creation to deletion
- Refactor intensity: files changed per refactoring commit
