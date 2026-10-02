"""Portable, self-contained visualization of measured history only."""
import html
import json
from pathlib import Path
from ..utils import atomic_write


def render_history(project_root: Path) -> Path:
    data_path = project_root / "deliverables" / "data.json"
    if not data_path.exists():
        raise ValueError("No measured visualization data; run devarch build-db first")
    data = json.loads(data_path.read_text(encoding="utf-8"))
    daily = data.get("daily_commits")
    if not isinstance(daily, dict):
        raise ValueError("Measured daily_commits missing; rebuild with devarch build-db")
    if sum(daily.values()) != data.get("total_commits"):
        raise ValueError("Daily activity does not reconcile with total_commits")
    config = json.loads((project_root / "project.json").read_text(encoding="utf-8"))
    title = html.escape(str(config.get("visualization", {}).get("title") or config.get("name") or project_root.name))
    maximum = max(daily.values(), default=1) or 1
    rows = ''.join(f'<tr><td>{html.escape(day)}</td><td>{count}</td><td><meter min="0" max="{maximum}" value="{count}">{count}</meter></td></tr>' for day, count in sorted(daily.items()))
    content = f'''<!doctype html><html lang="en"><meta charset="utf-8">
<title>{title} — history</title><meta name="viewport" content="width=device-width">
<style>body{{font:17px system-ui;max-width:1000px;margin:3rem auto;padding:1rem;color:#162b36;background:#f5f7f8}}td,th{{padding:.3rem 1rem;text-align:left}}meter{{width:35vw}}@media(prefers-color-scheme:dark){{body{{background:#15212b;color:#eef4f6}}}}</style>
<h1>{title}</h1><p><strong>{data['total_commits']:,} commits</strong> · {data.get('active_days', 0)} active UTC days</p>
<p>Author-date activity across locally available refs. Commits are not productivity, verified sessions, causal eras or evidence of implementation quality.</p>
<table><caption>Measured daily commit activity</caption><thead><tr><th>Date (UTC)</th><th>Commits</th><th>Activity</th></tr></thead><tbody>{rows}</tbody></table></html>'''
    output = project_root / "deliverables" / "visuals" / "archaeology.html"
    atomic_write(output, content)
    return output
