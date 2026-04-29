# Audit Checks

Validation checks for stage 08-audit.

## Check 1: Number Reconciliation

Validate that commit counts match across all stages.

### Procedure

1. Count rows in stages/02-mine/output/github-commits.csv
2. Count rows in archaeology.db commits table
3. Verify commit_count in reports matches
4. Check all calculated aggregates (sums, averages)

### Success Criteria

- All commit counts equal
- No missing or duplicate commits
- Aggregate calculations accurate

### Failure Handling

Document discrepancy, identify source stage, recommend re-run.

## Check 2: Schema Validation

Validate all JSON files against schemas.

### Procedure

1. Validate detected-signals.json schema
2. Validate all analysis-*.json files
3. Check required fields present
4. Validate data types (strings, integers, arrays)

### Success Criteria

- All JSON files parse without errors
- Required fields present
- Data types match schema
- No null values in required fields

### Failure Handling

Document validation errors, identify malformed JSON, fix schema violations.

## Check 3: Date Consistency

Validate date ranges across outputs.

### Procedure

1. Extract min/max dates from CSV
2. Verify date range in reports matches
3. Check date format consistency (YYYY-MM-DD)
4. Validate chronological order in timelines

### Success Criteria

- Date ranges match across stages
- All dates in ISO 8601 format
- Timeline chronologically ordered
- No future dates present

### Failure Handling

Document date mismatches, identify parsing errors, standardize format.

## Check 4: File Integrity

Validate all output files exist and are valid.

### Procedure

1. Check all expected output files exist
2. Verify files are non-empty
3. Validate HTML file renders
4. Check markdown file formatting

### Success Criteria

- All expected files present
- All files non-empty (except where allowed)
- HTML renders without errors
- Markdown parses correctly

### Failure Handling

Document missing or empty files, identify generation errors, re-run failed stages.

## Check 5: Correlation Accuracy

Validate supplementary data correlations.

### Procedure

1. Verify supplementary sources loaded
2. Check date-join logic
3. Validate correlation window (24 hours)
4. Spot-check correlation accuracy

### Success Criteria

- All supplementary sources processed
- Date joins accurate
- No orphaned correlations
- Correlation types correct

### Failure Handling

Document correlation errors, verify data formats, check date parsing.

## Audit Report Format

```markdown
# Audit Result

## Summary

- Checks Run: 5
- Checks Passed: 5
- Checks Failed: 0

## Detailed Results

### Check 1: Number Reconciliation
Status: PASS

### Check 2: Schema Validation
Status: PASS

...

## Issues Found

None.

## Recommendations

No issues to address.
```

## Remediation

If any check fails:

1. Document failure details
2. Identify root cause
3. Propose remediation steps
4. Re-run affected stages
5. Re-audit until all checks pass
