# Signal Types Specification

Detailed specifications for the 5 signal detection heuristics.

## 1. Gap Detection

Identify periods of inactivity exceeding threshold.

### Algorithm

1. Sort commits by date ascending
2. Calculate days between consecutive commits
3. Flag gaps where days >= signal_gap_threshold

### Output Format

```json
{
  "type": "gap",
  "start_date": "YYYY-MM-DD",
  "end_date": "YYYY-MM-DD",
  "duration_days": 7,
  "threshold": 3
}
```

## 2. Velocity Shift

Identify significant changes in commit frequency.

### Algorithm

1. Calculate commits per week for entire history
2. Use sliding window (4 weeks)
3. Compare velocity before/after window
4. Flag shifts where change >= 50%

### Output Format

```json
{
  "type": "velocity_shift",
  "date": "YYYY-MM-DD",
  "direction": "increase|decrease",
  "before_velocity": 2.5,
  "after_velocity": 5.0,
  "percent_change": 100
}
```

## 3. Author Change

Identify commits from non-primary authors.

### Algorithm

1. Determine primary author (most commits)
2. Flag commits where author != primary author
3. Group by external author

### Output Format

```json
{
  "type": "author_change",
  "date": "YYYY-MM-DD",
  "author": "External Author",
  "email": "external@example.com",
  "files_changed": 5
}
```

## 4. Scope Change

Identify significant changes in files touched per commit.

### Algorithm

1. Calculate average files changed per commit
2. Use sliding window (10 commits)
3. Compare scope before/after window
4. Flag shifts where change >= 2x

### Output Format

```json
{
  "type": "scope_change",
  "date": "YYYY-MM-DD",
  "direction": "expansion|contraction",
  "before_avg": 2.0,
  "after_avg": 5.0,
  "percent_change": 150
}
```

## 5. Supplementary Correlation

Identify patterns between commits and external data.

### Algorithm

1. Load supplementary data sources
2. Date-join with commit dates
3. Flag events within 24 hours of commit
4. Group by correlation type

### Output Format

```json
{
  "type": "supplementary",
  "date": "YYYY-MM-DD",
  "commit_hash": "abc123...",
  "source_type": "fitness|media|calendar|weather|astronomical",
  "event_value": "string or number",
  "correlation_type": "coincident|preceding|following"
}
```

## Thresholds

All thresholds configurable via project.json:

- signal_gap_threshold: days for gap detection (default 3)
- velocity_change_threshold: percent for velocity (default 50)
- scope_change_threshold: multiplier for scope (default 2.0)
