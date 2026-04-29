# sqlite-utils Setup Guide

Using sqlite-utils for database operations in stage 03-build.

## Installation

```bash
pip install sqlite-utils
```

## Basic Operations

### Create Database

```bash
sqlite-utils create-table archaeology.db commits hash text date text author text
```

### Insert CSV Data

```bash
sqlite-utils insert archaeology.db commits github-commits.csv --csv
```

### Create Indexes

```bash
sqlite-utils create-index archaeology.db commits date
sqlite-utils create-index archaeology.db commits author
sqlite-utils create-index archaeology.db commits hash
```

### Verify Data

```bash
sqlite-utils tables archaeology.db
sqlite-utils rows archaeology.db commits --count
sqlite-utils schema archaeology.db
```

## Python API

```python
import sqlite_utils

db = sqlite_utils.Database("archaeology.db")

# Insert data
db["commits"].insert_all(
    csv_data,
    pk="hash",
    replace=True
)

# Create indexes
db["commits"].create_index("date")
db["commits"].create_index("author")
db["commits"].create_index("hash")

# Query data
rows = db["commits"].rows_where(order_by="date")
```

## Error Handling

- Duplicate hash: Use --replace flag or handle in code
- Invalid CSV: Validate before insert
- Type errors: Ensure CSV matches table schema
