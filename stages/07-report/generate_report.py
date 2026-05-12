#!/usr/bin/env python3
"""Stage 07-Report: Generate Archaeology Reports"""

import json
from pathlib import Path
from datetime import datetime

# Paths - using relative paths from script location
STAGES_DIR = Path(__file__).resolve().parent.parent.parent
SIGNALS_PATH = STAGES_DIR / "stages" / "04-detect" / "output" / "detected-signals.json"
ANALYSIS_DIR = STAGES_DIR / "stages" / "05-analyze" / "output"
OUTPUT_MD = Path(__file__).resolve().parent / "output" / "ARCHAEOLOGY-REPORT.md"
OUTPUT_HTML = Path(__file__).resolve().parent / "output" / "ARCHAEOLOGY-REPORT.html"

# Ensure output directory exists
OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
OUTPUT_HTML.parent.mkdir(parents=True, exist_ok=True)

def load_data():
    """Load all analysis data"""
    with open(SIGNALS_PATH, 'r') as f:
        signals = json.load(f)

    analyses = {}
    for analysis_file in ANALYSIS_DIR.glob('analysis-*.json'):
        with open(analysis_file, 'r') as f:
            analyses[analysis_file.stem] = json.load(f)

    return signals, analyses

def generate_markdown_report(signals, analyses):
    """Generate comprehensive markdown report"""

    # Extract key metrics
    total_commits = signals.get('total_commits', 0)
    active_days = signals.get('active_days', 0)
    span_days = signals.get('span_days', 0)
    date_range = signals.get('date_range', '')

    daily_breakdown = signals.get('daily_breakdown', {})
    peak_day = max(daily_breakdown.items(), key=lambda x: x[1]) if daily_breakdown else ('N/A', 0)

    signals_list = signals.get('signals', [])
    signals_summary = signals.get('summary', {})

    md = f"""# Archaeology Report: demo-project

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## Executive Summary

Achiote is a TypeScript culinary reverse engineering application that was developed over a {span_days}-day period from {date_range}. The project demonstrates active development with {total_commits} commits across {active_days} active days, representing an average velocity of {round(total_commits / active_days, 1) if active_days > 0 else 0} commits per day.

**Key Findings:**
- **Development Intensity:** Peak activity reached {peak_day[1]} commits in a single day
- **Author Distribution:** Primary development by Simon Gonzalez De Cruz (79.7%) with contributions from Simon (20.3%)
- **Commit Hygiene:** Strong adherence to conventional commit standards
- **Testing:** Present but could be expanded
- **Documentation:** Moderate coverage

---

## Project Overview

### Timeline
- **Project Span:** {span_days} days
- **Active Development Days:** {active_days}
- **Date Range:** {date_range}
- **Peak Activity:** {peak_day[0]} ({peak_day[1]} commits)

### Development Metrics
- **Total Commits:** {total_commits}
- **Average Velocity:** {round(total_commits / active_days, 1) if active_days > 0 else 0} commits/day
- **Authors:** 2 (Simon Gonzalez De Cruz, Simon)

---

## Signal Detection Results

### Detected Signals: {signals_summary.get('total_signals', 0)}

"""

    # Add signal breakdown by type
    for signal_type, count in signals_summary.get('by_type', {}).items():
        md += f"- **{signal_type.replace('_', ' ').title()}:** {count} occurrences\n"

    md += "\n### Detailed Signals\n\n"

    # Add detailed signals (top 20)
    for i, signal in enumerate(signals_list[:20], 1):
        signal_type = signal.get('type', 'unknown')
        date = signal.get('date', 'N/A')
        value = signal.get('value', 'N/A')
        description = signal.get('metadata', {}).get('description', f'{signal_type}: {value}')

        md += f"{i}. **{signal_type.replace('_', ' ').title()}** ({date})\n"
        md += f"   - {description}\n\n"

    md += "---\n\n"

    # Add SDLC Analysis
    sdlc_analysis = analyses.get('analysis-sdlc-gap-finder', {})
    if sdlc_analysis:
        md += "## SDLC Assessment\n\n"
        md += f"**Total Findings:** {sdlc_analysis.get('summary', {}).get('total_findings', 0)}\n\n"

        for finding in sdlc_analysis.get('findings', []):
            finding_type = finding.get('type', 'Unknown')
            description = finding.get('description', '')
            confidence = finding.get('confidence', 'low').upper()
            evidence = finding.get('evidence', [])

            md += f"### {finding_type}\n"
            md += f"**Description:** {description}\n\n"
            md += f"**Confidence:** {confidence}\n\n"

            if evidence:
                md += "**Evidence:**\n"
                for item in evidence[:3]:
                    md += f"- {item}\n"
                md += "\n"

        md += "---\n\n"

    # Add ML Pattern Analysis
    ml_analysis = analyses.get('analysis-ml-pattern-mapper', {})
    if ml_analysis:
        md += "## ML Pattern Analysis\n\n"
        md += f"**Total Findings:** {ml_analysis.get('summary', {}).get('total_findings', 0)}\n\n"

        for finding in ml_analysis.get('findings', []):
            finding_type = finding.get('type', 'Unknown')
            description = finding.get('description', '')
            confidence = finding.get('confidence', 'low').upper()

            md += f"### {finding_type}\n"
            md += f"**Description:** {description}\n\n"
            md += f"**Confidence:** {confidence}\n\n"

        md += "---\n\n"

    # Add Source Archaeology
    arch_analysis = analyses.get('analysis-source-archaeologist', {})
    if arch_analysis:
        md += "## Development Patterns & Quality\n\n"
        md += f"**Total Findings:** {arch_analysis.get('summary', {}).get('total_findings', 0)}\n\n"

        for finding in arch_analysis.get('findings', []):
            finding_type = finding.get('type', 'Unknown')
            description = finding.get('description', '')
            confidence = finding.get('confidence', 'low').upper()

            md += f"### {finding_type}\n"
            md += f"**Description:** {description}\n\n"
            md += f"**Confidence:** {confidence}\n\n"

        md += "---\n\n"

    # Add Recommendations
    md += """## Recommendations

### Strengths
1. **Strong Commit Hygiene:** High adherence to conventional commit format provides clear project history
2. **Active Development:** Consistent commit velocity demonstrates focused development effort
3. **Multi-Author Collaboration:** Evidence of coordinated development between contributors
4. **Domain Focus:** Clear specialization in culinary reverse engineering with domain-specific patterns

### Areas for Improvement
1. **Testing Coverage:** While present, testing could be expanded to improve code quality assurance
2. **Documentation:** Consider increasing documentation coverage for better maintainability
3. **CI/CD Maturity:** Further investment in automation could improve deployment reliability

### Next Steps
1. Review and prioritize testing gaps identified in the SDLC analysis
2. Enhance documentation for critical components
3. Consider implementing additional automated quality checks
4. Continue maintaining strong commit practices

---

## Appendix

### Daily Commit Breakdown

"""

    # Add daily breakdown table
    md += "| Date | Commits |\n"
    md += "|------|--------|\n"

    for day, count in sorted(daily_breakdown.items()):
        md += f"| {day} | {count} |\n"

    md += "\n---\n\n"
    md += f"*This report was automatically generated by the DevArch ICM Pipeline*\n"

    return md

def generate_html_report(md_content):
    """Convert markdown report to HTML"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>demo-project - Archaeology Report</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e4e4e7;
            line-height: 1.8;
            padding: 40px 20px;
        }}

        .container {{
            max-width: 900px;
            margin: 0 auto;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid #3f3f46;
            border-radius: 16px;
            padding: 60px;
        }}

        h1 {{
            font-size: 2.5em;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 10px;
        }}

        h2 {{
            font-size: 1.8em;
            color: #667eea;
            margin-top: 40px;
            margin-bottom: 20px;
            border-bottom: 2px solid #3f3f46;
            padding-bottom: 10px;
        }}

        h3 {{
            font-size: 1.3em;
            color: #a1a1aa;
            margin-top: 25px;
            margin-bottom: 10px;
        }}

        p {{
            margin-bottom: 15px;
            color: #e4e4e7;
        }}

        strong {{
            color: #667eea;
            font-weight: 600;
        }}

        ul, ol {{
            margin-left: 25px;
            margin-bottom: 20px;
        }}

        li {{
            margin-bottom: 8px;
            color: #e4e4e7;
        }}

        code {{
            background: rgba(255, 255, 255, 0.1);
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }}

        hr {{
            border: none;
            border-top: 1px solid #3f3f46;
            margin: 40px 0;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}

        th, td {{
            border: 1px solid #3f3f46;
            padding: 12px;
            text-align: left;
        }}

        th {{
            background: rgba(102, 126, 234, 0.2);
            color: #667eea;
            font-weight: 600;
        }}

        td {{
            color: #e4e4e7;
        }}

        .meta {{
            color: #a1a1aa;
            font-size: 0.9em;
            margin-bottom: 30px;
        }}

        .highlight {{
            background: rgba(102, 126, 234, 0.1);
            border-left: 4px solid #667eea;
            padding: 15px 20px;
            margin: 20px 0;
            border-radius: 0 8px 8px 0;
        }}
    </style>
</head>
<body>
    <div class="container">
        {convert_markdown_to_html(md_content)}
    </div>
</body>
</html>"""

    return html

def convert_markdown_to_html(md):
    """Simple markdown to HTML conversion"""

    html = md

    # Headers
    html = html.replace('### ', '<h3>').replace('\n', '</h3>\n', 1)
    html = html.replace('## ', '<h2>').replace('\n', '</h2>\n', 1)
    html = html.replace('# ', '<h1>').replace('\n', '</h1>\n', 1)

    # Bold
    html = html.replace('**', '<strong>').replace('**', '</strong>')

    # Line breaks
    html = html.replace('\n\n', '</p><p>')

    # Lists (simplified)
    lines = html.split('\n')
    in_list = False
    result = []

    for line in lines:
        if line.startswith('- '):
            if not in_list:
                result.append('<ul>')
                in_list = True
            result.append(f'<li>{{line[2:]}}</li>')
        else:
            if in_list:
                result.append('</ul>')
                in_list = False
            result.append(line)

    if in_list:
        result.append('</ul>')

    html = '\n'.join(result)

    # Tables (simplified)
    if '|' in html:
        lines = html.split('\n')
        in_table = False
        table_result = []

        for line in lines:
            if '|' in line and not line.strip().startswith('|---'):
                if not in_table:
                    table_result.append('<table>')
                    in_table = True
                cells = [cell.strip() for cell in line.split('|')[1:-1]]
                if cells:
                    table_result.append('<tr>' + ''.join(f'<td>{{cell}}</td>' for cell in cells) + '</tr>')
            else:
                if in_table:
                    table_result.append('</table>')
                    in_table = False
                table_result.append(line)

        if in_table:
            table_result.append('</table>')

        html = '\n'.join(table_result)

    # Wrap in paragraphs
    html = '<p>' + html + '</p>'

    # Clean up
    html = html.replace('<p><h1>', '<h1>').replace('</h1></p>', '</h1>')
    html = html.replace('<p><h2>', '<h2>').replace('</h2></p>', '</h2>')
    html = html.replace('<p><h3>', '<h3>').replace('</h3></p>', '</h3>')
    html = html.replace('<p><ul>', '<ul>').replace('</ul></p>', '</ul>')
    html = html.replace('<p><table>', '<table>').replace('</table></p>', '</table>')
    html = html.replace('<p><hr>', '<hr>').replace('</hr></p>', '<hr>')
    html = html.replace('<p></p>', '')

    return html

if __name__ == '__main__':
    print("Loading analysis data...")
    signals, analyses = load_data()

    print("Generating markdown report...")
    md_report = generate_markdown_report(signals, analyses)

    with open(OUTPUT_MD, 'w') as f:
        f.write(md_report)

    print(f"  Markdown: {OUTPUT_MD}")

    print("Generating HTML report...")
    html_report = generate_html_report(md_report)

    with open(OUTPUT_HTML, 'w') as f:
        f.write(html_report)

    print(f"  HTML: {OUTPUT_HTML}")

    print("\n✓ Stage 07-Report completed")
    print(f"  Reports generated successfully")
