# Stage 03-Build

Build SQLite database from extracted CSV data.

## Inputs

- stages/02-mine/output/github-commits.csv
- Table definitions from references/table-registry.md

## Process

1. Install sqlite-utils if needed
2. Create archaeology.db database
3. Create commits table with schema from table-registry.md
4. Import CSV data into commits table
5. Create indexes on date, author, hash columns
6. Verify row count matches CSV row count

## Commands

```bash
sqlite-utils insert archaeology.db commits <path-to-csv.csv --csv
sqlite-utils create-index archaeology.db commits date
sqlite-utils create-index archaeology.db commits author
sqlite-utils create-index archaeology.db commits hash
```

## Outputs

- stages/03-build/output/archaeology.db

## Table Schema

```sql
CREATE TABLE commits (
  hash TEXT PRIMARY KEY,
  date TEXT NOT NULL,
  author TEXT NOT NULL,
  email TEXT NOT NULL,
  message TEXT NOT NULL,
  files_added INTEGER DEFAULT 0,
  files_deleted INTEGER DEFAULT 0,
  files_modified INTEGER DEFAULT 0
);

CREATE INDEX idx_date ON commits(date);
CREATE INDEX idx_author ON commits(author);
CREATE INDEX idx_hash ON commits(hash);
```

## Success Criteria

- Database file created
- Commits table exists with correct schema
- Row count matches input CSV
- Indexes created on key columns

## Next Stage

Proceed to 04-detect to run signal detection.
