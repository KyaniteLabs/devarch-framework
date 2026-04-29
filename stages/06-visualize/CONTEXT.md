# Stage 06-Visualize

Generate HTML visualization from analysis outputs.

## Inputs

- stages/04-detect/output/detected-signals.json
- stages/05-analyze/output/analysis-*.json files
- stages/06-visualize/references/html-template-spec.md
- stages/06-visualize/references/chart-types.md

## Process

1. Load all analysis outputs
2. Load HTML template
3. Generate chart data for each visualization type
4. Hydrate template with data
5. Apply theme from shared/visualization-themes.md
6. Output HTML file

## Outputs

- stages/06-visualize/output/archaeology.html

## Template Variables

- {{developer_name}}
- {{project_name}}
- {{project_description}}
- {{commit_count}}
- {{date_range}}
- {{signals_data}}
- {{analysis_findings}}
- {{chart_data}}
- {{supplementary_correlations}} (if applicable)

## Chart Types

See references/chart-types.md for available chart types and configurations.

## Success Criteria

- HTML file generated
- All charts render without errors
- Data accurately reflects analysis outputs
- Supplementary correlations included if configured

## Next Stage

Proceed to 07-report to generate text reports.
