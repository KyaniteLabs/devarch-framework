#!/usr/bin/env python3
"""Generate data.json for any archaeology project from CSV + commit-eras.

Produces the minimal telemetry_visualizations structure needed by
the archaeology.html template to render charts.

Usage:
    python3 scripts/data/generate_data_json.py <project_name>
    python3 scripts/data/generate_data_json.py --all
"""

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CONVENTIONAL_TYPES = {
    "feat", "fix", "docs", "style", "refactor", "perf",
    "test", "build", "ci", "chore", "revert", "merge", "security",
}

AGENT_PATTERNS = [
    (r"\bclaude[_ ]?code\b", "claude_code"),
    (r"\bcursor\b", "cursor"),
    (r"\bkai[_ ]?bot\b", "kai_bot"),
    (r"\bkimicode\b", "kimicode"),
    (r"\bcopilot\b", "copilot"),
]


def classify_commit_type(message: str) -> str:
    m = re.match(r"^(\w+)(\([^)]*\))?!?:", message)
    if m and m.group(1) in CONVENTIONAL_TYPES:
        return m.group(1)
    if message.lower().startswith("merge"):
        return "merge"
    return "other"


def detect_agent(message: str) -> str:
    lower = message.lower()
    for pattern, agent in AGENT_PATTERNS:
        if re.search(pattern, lower):
            return agent
    return "other"


def parse_csv(csv_path: Path) -> list[dict]:
    commits = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date_str = row.get("date", "").strip()
            if not date_str:
                continue
            for fmt in ("%Y-%m-%d %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
                try:
                    dt = datetime.strptime(date_str, fmt)
                    break
                except ValueError:
                    continue
            else:
                continue
            commits.append({
                "hash": row.get("hash", ""),
                "date": dt.strftime("%Y-%m-%d"),
                "hour": dt.hour,
                "message": row.get("message", ""),
                "author": row.get("author", "unknown"),
            })
    return commits


def generate_for_project(project_name: str) -> None:
    project_dir = ROOT / "projects" / project_name
    csv_path = project_dir / "data" / "github-commits.csv"
    eras_path = project_dir / "data" / "commit-eras.json"
    metrics_path = project_dir / "deliverables" / "canonical-metrics.json"
    config_path = project_dir / "project.json"
    output_path = project_dir / "deliverables" / "data.json"

    if not csv_path.exists():
        print(f"  SKIP: {csv_path} not found")
        return

    commits = parse_csv(csv_path)
    if not commits:
        print(f"  SKIP: no commits parsed from {csv_path}")
        return

    # Load eras
    eras_data = []
    if eras_path.exists():
        eras_json = json.loads(eras_path.read_text(encoding="utf-8"))
        eras_data = eras_json.get("eras", [])

    # Load project config
    project_config = {}
    if config_path.exists():
        project_config = json.loads(config_path.read_text(encoding="utf-8"))

    # Load canonical metrics
    metrics = {}
    if metrics_path.exists():
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))

    # Compute stats
    dates = [c["date"] for c in commits]
    date_counts = Counter(dates)
    hours = [c["hour"] for c in commits]
    hour_counts = Counter(hours)
    types = [classify_commit_type(c["message"]) for c in commits]
    type_counts = Counter(types)
    authors = Counter(c["author"] for c in commits)
    agents = [detect_agent(c["message"]) for c in commits]
    agent_counts = Counter(agents)

    # Date range
    sorted_dates = sorted(set(dates))
    first_date = sorted_dates[0] if sorted_dates else ""
    last_date = sorted_dates[-1] if sorted_dates else ""
    total_commits = len(commits)
    active_days = len(date_counts)
    peak_day = date_counts.most_common(1)[0][0] if date_counts else ""
    peak_day_commits = date_counts.most_common(1)[0][1] if date_counts else 0

    # Agent attribution by date
    agent_by_date = defaultdict(lambda: defaultdict(int))
    for c in commits:
        agent = detect_agent(c["message"])
        agent_by_date[c["date"]][agent] += 1
        agent_by_date[c["date"]]["total"] += 1

    # Commit timeline data
    timeline_data = {}
    for d in sorted_dates:
        timeline_data[d] = date_counts[d]

    # Hourly pattern
    hourly_data = {str(h).zfill(2): hour_counts.get(h, 0) for h in range(24)}

    # Build commit_eras for visualization
    viz_eras = []
    for era in eras_data:
        viz_eras.append({
            "id": era.get("id", 0),
            "name": era.get("name", f"Era {era.get('id', 0)}"),
            "dates": era.get("dates", ""),
            "commits": era.get("commits", 0),
            "author": ", ".join(era.get("authors", era.get("contributors", []))) if isinstance(era.get("authors", era.get("contributors", [])), list) else str(era.get("authors", "")),
            "description": era.get("description", ""),
            "key_events": era.get("key_events", []),
            "narrative_arc": era.get("narrative_arc", ""),
        })

    # Build the data.json structure
    data = {
        "telemetry_visualizations": {
            "meta": {
                "description": f"Visualization-ready telemetry data mined from {project_name} git history",
                "generated": datetime.now().strftime("%Y-%m-%d"),
                "project": project_name,
                "total_commits": total_commits,
                "date_range": f"{first_date} to {last_date}",
                "lifespan_days": metrics.get("span_days", 0),
                "active_days": active_days,
                "avg_commits_per_active_day": round(total_commits / max(active_days, 1), 1),
                "avg_commits_per_day_full_span": round(total_commits / max(metrics.get("span_days", 1), 1), 1),
                "peak_day": peak_day,
                "peak_day_commits": peak_day_commits,
                "source_scope": f"github-commits.csv ({total_commits} commits)",
            },
            "charts": {
                "commit_timeline": {
                    "type": "area",
                    "description": "Commits per day across project lifetime",
                    "x_label": "Date",
                    "y_label": "Commits",
                    "data": timeline_data,
                    "hourly_pattern": {
                        "type": "bar",
                        "description": "Commits by hour of day (0-23)",
                        "x_label": "Hour",
                        "y_label": "Commits",
                        "data": hourly_data,
                    },
                    "commit_types": {
                        "type": "bar",
                        "description": "Commit message type breakdown",
                        "data": dict(type_counts.most_common()),
                    },
                    "agent_attribution": {
                        "type": "stacked_bar",
                        "description": f"Agent attribution by day — {len(authors)} developer(s)",
                        "x_label": "Date",
                        "y_label": "Commits",
                        "agents": list(agent_counts.keys()),
                        "data": dict(sorted(agent_by_date.items())),
                    },
                },
                "derived_insights": [],
            },
            "commit_eras": viz_eras,
            "version_milestones": [],
            "agent_evidence": {
                "summary": {a: c for a, c in agent_counts.most_common()},
            },
        },
        "telemetry_agents": {
            "metadata": {"project": project_name, "generated": datetime.now().strftime("%Y-%m-%d")},
            "agent_comparison": {a: c for a, c in agent_counts.most_common()},
        },
        "codebase": {
            "project": project_name,
            "description": project_config.get("description", ""),
            "mined_at": datetime.now().strftime("%Y-%m-%d"),
            "total_commits": total_commits,
            "lifespan": f"{metrics.get('span_days', 0)} days",
            "active_days": active_days,
            "peak_day": peak_day,
            "peak_day_commits": peak_day_commits,
        },
        "developer_name": list(authors.keys())[0] if authors else "unknown",
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  OK: {output_path} ({total_commits} commits, {len(viz_eras)} eras, {active_days} active days)")


def main():
    if len(sys.argv) < 2:
        print("Usage: generate_data_json.py <project_name> | --all")
        sys.exit(1)

    if sys.argv[1] == "--all":
        projects_dir = ROOT / "projects"
        for proj_dir in sorted(projects_dir.iterdir()):
            if proj_dir.is_dir() and (proj_dir / "data" / "github-commits.csv").exists():
                name = proj_dir.name
                print(f"Generating data.json for {name}...")
                generate_for_project(name)
    else:
        name = sys.argv[1]
        print(f"Generating data.json for {name}...")
        generate_for_project(name)


if __name__ == "__main__":
    main()
