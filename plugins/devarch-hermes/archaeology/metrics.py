"""Canonical metrics from the mined commits, reconciled against SQLite."""

import csv
import json
import sqlite3
from collections import Counter
from pathlib import Path

from .utils import _parse_date, atomic_write


def write_metrics(project_root: Path, db_path: Path) -> dict:
    csv_path = project_root / "data" / "github-commits.csv"
    if not csv_path.exists():
        return {}
    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    hashes = [row["hash"] for row in rows]
    with sqlite3.connect(db_path) as conn:
        stored = [row[0] for row in conn.execute("SELECT hash FROM commits")]
    if len(set(hashes)) != len(hashes) or sorted(hashes) != sorted(stored):
        raise ValueError("CSV/SQLite commit identities differ or contain duplicates")
    metrics = calculate_metrics(rows)
    atomic_write(
        project_root / "deliverables" / "canonical-metrics.json", json.dumps(metrics, indent=2)
    )
    atomic_write(
        project_root / "deliverables" / "data.json",
        json.dumps(
            {
                **metrics,
                "telemetry_visualizations": {"meta": metrics},
            },
            indent=2,
        ),
    )
    return metrics


def calculate_metrics(rows: list[dict]) -> dict:
    """Derive canonical values from source rows without writing artifacts."""
    days = Counter()
    for row in rows:
        parsed = _parse_date(row["date"])
        if parsed is None:
            raise ValueError(f"Invalid commit date for {row['hash']}")
        days[parsed.date().isoformat()] += 1
    dates = sorted(days)
    peak = min(days, key=lambda d: (-days[d], d)) if days else None
    metrics = {
        "total_commits": len(rows),
        "active_days": len(days),
        "daily_commits": dict(sorted(days.items())),
        "first_commit_date": dates[0] if dates else None,
        "last_commit_date": dates[-1] if dates else None,
        "span_days": (_parse_date(dates[-1]) - _parse_date(dates[0])).days + 1 if dates else 0,
        "peak_day": peak,
        "peak_day_commits": days[peak] if peak else 0,
        "date_basis": "author timestamps normalized to UTC; inclusive calendar span",
        "source_scope": "all locally mined refs, not proof of all remote history",
    }
    return metrics
