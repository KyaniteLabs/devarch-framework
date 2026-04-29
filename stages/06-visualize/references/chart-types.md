# Chart Types

Available visualizations for archaeology reports.

## Timeline Chart

### Purpose

Show commit activity and signals over time.

### Data Format

```json
{
  "type": "timeline",
  "data": {
    "dates": ["2024-01-01", "2024-01-02", ...],
    "commits": [5, 3, 0, 8, ...],
    "signals": [
      {"date": "2024-01-03", "type": "gap", "label": "3 day gap"}
    ]
  }
}
```

### Rendering

- X-axis: Date
- Y-axis: Commit count
- Signal markers: Vertical lines with labels
- Color: Use theme accent color

## Velocity Chart

### Purpose

Show changes in commit frequency over time.

### Data Format

```json
{
  "type": "velocity",
  "data": {
    "periods": ["Week 1", "Week 2", ...],
    "velocity": [2.5, 5.0, 3.2, ...],
    "shifts": [
      {"period": "Week 2", "direction": "increase", "magnitude": 100}
    ]
  }
}
```

### Rendering

- X-axis: Time period
- Y-axis: Commits per period
- Shift markers: Highlighted points
- Color: Use theme primary color

## Author Distribution

### Purpose

Show commit distribution by author.

### Data Format

```json
{
  "type": "author_distribution",
  "data": {
    "authors": ["Primary", "External 1", "External 2"],
    "commits": [145, 12, 5],
    "percentages": [89.0, 7.4, 3.6]
  }
}
```

### Rendering

- Chart type: Bar chart or pie chart
- Colors: Distinct colors per author
- Labels: Author names with percentages

## Correlation Scatter Plot

### Purpose

Show relationship between commits and supplementary data.

### Data Format

```json
{
  "type": "correlation",
  "data": {
    "points": [
      {"x": "2024-01-15", "y": 10000, "label": "10k steps"},
      {"x": "2024-01-16", "y": 5, "label": "5 commits"}
    ],
    "correlation_type": "fitness"
  }
}
```

### Rendering

- X-axis: Date
- Y-axis: Supplementary value
- Commit markers: Overlay on same timeline
- Color: Use distinct colors for each data type

## Activity Heatmap

### Purpose

Show activity patterns by day of week and hour.

### Data Format

```json
{
  "type": "heatmap",
  "data": {
    "rows": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "cols": ["0-4", "4-8", "8-12", "12-16", "16-20", "20-24"],
    "values": [[0, 1, 5, 8, 3, 0], ...]
  }
}
```

### Rendering

- Color scale: Light to dark based on activity
- Labels: Day and time period
- Tooltip: Exact commit count

## Chart Library

Use lightweight vanilla JS library (e.g. Chart.js, Plotly) or custom SVG rendering.

All charts must support theme colors from shared/visualization-themes.md.
