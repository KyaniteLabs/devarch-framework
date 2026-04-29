# SDLC Gap Finder Vector

Identify gaps in software development lifecycle practices.

## Purpose

Detect missing or weak SDLC practices: testing, documentation, code review, deployment.

## Detection Patterns

### Test Coverage

Search commit messages for test-related keywords:

- Patterns: test, spec, pytest, unittest, jest, test-driven
- Identify periods without test commits
- Calculate test-to-feature commit ratio

### Documentation

Search for documentation keywords:

- Patterns: doc, readme, changelog, api-doc, comments
- Identify gaps in documentation updates
- Calculate documentation freshness

### Code Review

Search for review indicators:

- Patterns: pr, pull-request, review, refactor
- Identify direct-to-main commits
- Calculate review coverage

### Deployment

Search for deployment markers:

- Patterns: deploy, release, version, prod, staging
- Identify deployment frequency
- Calculate deploy-to-commit ratio

## Output Schema

```json
{
  "vector_name": "sdlc-gap-finder",
  "findings": [
    {
      "type": "test_coverage",
      "description": "Low test coverage in Q1",
      "evidence": ["commit hashes"],
      "confidence": "high",
      "metrics": {
        "test_commits": 5,
        "total_commits": 50,
        "ratio": 0.1
      }
    }
  ],
  "summary": {
    "total_findings": 4,
    "by_type": {
      "test_coverage": 1,
      "documentation": 1,
      "code_review": 1,
      "deployment": 1
    }
  }
}
```

## Confidence Levels

- High: Clear pattern with strong evidence
- Medium: Pattern present but incomplete
- Low: Insufficient data for conclusion
