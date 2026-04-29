# CSV Format Specification

Output format for github-commits.csv from stage 02-mine.

## Columns

| Column Name | Type | Required | Description |
|-------------|------|----------|-------------|
| hash | string | Yes | Commit SHA (full 40 character) |
| date | string | Yes | ISO 8601 date (YYYY-MM-DD) |
| author | string | Yes | Author name |
| email | string | Yes | Author email address |
| message | string | Yes | Commit message (first line) |
| files_added | integer | Yes | Count of files added |
| files_deleted | integer | Yes | Count of files deleted |
| files_modified | integer | Yes | Count of files modified |

## Example Row

```csv
abc123def456789...,2024-01-15,Developer Name,dev@example.com,Fix authentication bug,1,0,3
```

## Parsing Notes

- Date format: YYYY-MM-DD (time component stripped)
- Message: First line only, newlines escaped
- File counts: Derived from --numstat output
- Empty counts default to 0

## Validation

- All rows must have exactly 8 columns
- hash must be unique (primary key)
- date must be valid ISO 8601
- file counts must be non-negative integers
