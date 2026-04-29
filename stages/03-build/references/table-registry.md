# Table Registry

Database table definitions for archaeology.db.

## Commits Table

Primary table storing all commit records.

### Schema

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
```

### Indexes

```sql
CREATE INDEX idx_date ON commits(date);
CREATE INDEX idx_author ON commits(author);
CREATE INDEX idx_hash ON commits(hash);
```

### Constraints

- hash: TEXT, primary key, unique
- date: TEXT, not null, format YYYY-MM-DD
- author: TEXT, not null
- email: TEXT, not null
- message: TEXT, not null
- files_*: INTEGER, default 0, non-negative

## Future Tables

Reserved for future expansion:

- supplementary_data: External data sources
- signals: Detected signals cache
- analysis_results: Analysis vector outputs

## Data Integrity

- All commits from CSV must be inserted
- No duplicate hashes allowed
- Date format validation on insert
