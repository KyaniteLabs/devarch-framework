# Visualization Themes

Generic color schemes and chart configurations for stage 06-visualize.

## Color Schemes

### Dark Theme

Background: #1a1a2e
Primary: #0f3460
Accent: #e94560
Text: #edf2f4
Muted: #8d99ae

### Light Theme

Background: #f8f9fa
Primary: #495057
Accent: #fa5252
Text: #212529
Muted: #adb5bd

### High Contrast

Background: #000000
Primary: #ffffff
Accent: #00ff00
Text: #ffffff
Muted: #666666

## Chart Types

### Timeline

- Use: Commit history, gaps, velocity
- X-axis: Date
- Y-axis: Commits or velocity metric

### Bar Chart

- Use: Files changed, author distribution
- X-axis: Category
- Y-axis: Count or percentage

### Scatter Plot

- Use: Correlation analysis
- X-axis: Date or numeric value
- Y-axis: Corresponding metric

### Heatmap

- Use: Activity patterns, day-of-week analysis
- X-axis: Time (hour or day)
- Y-axis: Date or category

### Network Graph

- Use: File relationships, co-occurrence
- Nodes: Files or concepts
- Edges: Relationships or co-changes

## Configuration

Chart configuration is in stages/06-visualize/references/chart-types.md.

Themes are applied in the HTML template during stage 06-visualize.
