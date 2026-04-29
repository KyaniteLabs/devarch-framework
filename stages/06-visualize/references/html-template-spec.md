# HTML Template Specification

Template variables and structure for archaeology.html.

## Template Variables

### Project Metadata

- {{developer_name}}: Developer display name
- {{project_name}}: Project short name
- {{project_description}}: Project description
- {{repo_path}}: Repository path

### Data Summary

- {{commit_count}}: Total number of commits
- {{date_start}}: Earliest commit date
- {{date_end}}: Latest commit date
- {{author_count}}: Number of unique authors
- {{file_count}}: Total unique files touched

### Signals Data

- {{signals_summary}}: Summary of detected signals
- {{signals_by_type}}: Signal counts grouped by type
- {{signals_timeline}}: Signals in chronological order

### Analysis Findings

- {{sdlc_findings}}: SDLC gap analysis results
- {{ml_findings}}: ML pattern analysis results
- {{formal_findings}}: Formal terms analysis results
- {{archaeology_findings}}: Source archaeology results

### Chart Data

- {{timeline_chart_data}}: JSON for timeline visualization
- {{velocity_chart_data}}: JSON for velocity charts
- {{author_chart_data}}: JSON for author distribution
- {{correlation_chart_data}}: JSON for supplementary correlations

### Supplementary Data

- {{supplementary_enabled}}: Boolean flag
- {{supplementary_sources}}: List of configured sources
- {{correlation_findings}}: Correlation analysis results

## Template Structure

```html
<!DOCTYPE html>
<html>
<head>
  <title>{{project_name}} Archaeology Report</title>
  <style>/* theme CSS */</style>
</head>
<body>
  <header>
    <h1>{{project_name}}</h1>
    <p>{{project_description}}</p>
  </header>

  <section id="summary">
    <!-- Data summary cards -->
  </section>

  <section id="signals">
    <!-- Signal detection results -->
  </section>

  <section id="analysis">
    <!-- Analysis vector findings -->
  </section>

  <section id="supplementary">
    <!-- Supplementary correlations (if enabled) -->
  </section>

  <section id="visualizations">
    <!-- Charts and graphs -->
  </section>
</body>
</html>
```

## Rendering

- Use Jinja2 or similar template engine
- Escape all user-provided data
- Validate JSON before embedding in scripts
- Support both light and dark themes
