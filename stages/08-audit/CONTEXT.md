# Stage 08-Audit

Quality gate validation for all generated outputs.

## Inputs

- All outputs from stages 02-07
- stages/08-audit/references/audit-checks.md

## Process

1. Run consistency checks across all outputs
2. Validate number reconciliation (commit counts match across stages)
3. Check for data drift between stages
4. Validate JSON schemas
5. Verify HTML rendering
6. Check supplementary data correlation accuracy
7. Generate audit result report

## Outputs

- stages/08-audit/output/audit-result.md

## Audit Checks

1. **Number Reconciliation**: Commit count matches CSV, database, and reports
2. **Schema Validation**: All JSON files valid against schemas
3. **Date Consistency**: Date ranges consistent across outputs
4. **File Integrity**: All output files exist and are non-empty
5. **Correlation Accuracy**: Supplementary data correlations correctly date-joined

## Success Criteria

- All audit checks pass
- Any failures documented with remediation steps
- Audit report generated

## Completion

If audit passes, archaeology analysis is complete.

If audit fails, address issues and re-run affected stages.
