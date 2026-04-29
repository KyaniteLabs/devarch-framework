# Stage 04-Detect

Run 5 signal detection heuristics on commit history.

## Inputs

- stages/03-build/output/archaeology.db
- Signal definitions from shared/signal-heuristics.md

## Process

1. Load archaeology.db
2. Run gap detection: find periods > threshold days with no commits
3. Run velocity shift detection: find significant changes in commit frequency
4. Run author change detection: find commits from non-primary authors
5. Run scope change detection: find significant changes in files per commit
6. Run supplementary correlation: if supplementary data exists, date-join with commits
7. Output all signals to JSON

## Checkpoint

After generating detected-signals.json, review the signals before proceeding to stage 05.

Confirm signals are accurate and threshold values are appropriate.

## Outputs

- stages/04-detect/output/detected-signals.json

## Output Schema

```json
{
  "signals": [
    {
      "type": "gap|velocity_shift|author_change|scope_change|supplementary",
      "date": "YYYY-MM-DD",
      "value": "numeric or string value",
      "metadata": {}
    }
  ],
  "summary": {
    "total_signals": 0,
    "by_type": {}
  }
}
```

## Success Criteria

- All 5 signal types executed
- JSON output valid and non-empty (if signals exist)
- Checkpoint review completed

## Next Stage

After checkpoint review, proceed to 05-analyze.
