# Stage 02-Mine

Extract git history from repository.

## Context Loading

| Layer | Load | Skip |
|-------|------|------|
| L3 (reference) | None needed | analysis-vectors/, shared/ |
| L4 (working) | project.json | stages/03+ outputs |

## Inputs

- project.json with repo_path
- Git repository at repo_path

## Process

1. Navigate to repository
2. Run git log extraction with --all --date=iso
3. Extract commit hash, date, author, message, files changed
4. Generate CSV with columns: hash, date, author, message, files_added, files_deleted, files_modified
5. Generate raw text dump with full commit details

## Commands

```bash
git -C <repo_path> log --all --date=iso --pretty=format:'%H|%ai|%an|%ae|%s' --numstat > <output>/github-commits-with-stats.txt
```

Then parse to CSV format.

## Outputs

- stages/02-mine/output/github-commits.csv
- stages/02-mine/output/github-commits-with-stats.txt (raw)

## CSV Schema

| Column | Type | Description |
|--------|------|-------------|
| hash | string | Commit SHA |
| date | string | ISO 8601 date |
| author | string | Author name |
| email | string | Author email |
| message | string | Commit message |
| files_added | integer | Files added |
| files_deleted | integer | Files deleted |
| files_modified | integer | Files modified |

## Success Criteria

- CSV generated with at least 1 commit
- All required columns present
- No parse errors in git log output

## Next Stage

Proceed to 03-build to create SQLite database.
