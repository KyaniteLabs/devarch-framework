# Stage 07-Report

Compile markdown and HTML text reports from all outputs.

## Inputs

- All outputs from stages 02-06
- stages/07-report/references/report-structure.md
- _config/developer-profile.md

## Process

1. Load all previous stage outputs
2. Load report structure template
3. Compile markdown sections
4. Generate HTML version
5. Include supplementary data insights if applicable
6. Output both formats

## Outputs

- stages/07-report/output/ARCHAEOLOGY-REPORT.md
- stages/07-report/output/ARCHAEOLOGY-REPORT.html

## Report Structure

1. Executive Summary
2. Project Overview
3. Data Collection Summary
4. Signal Detection Results
5. Analysis Findings
6. Supplementary Correlations (if applicable)
7. Visualizations
8. Recommendations
9. Appendix

## Success Criteria

- Both markdown and HTML reports generated
- All sections present and populated
- Numbers consistent with source data
- Supplementary correlations section included if configured

## Next Stage

Proceed to 08-audit for validation.
