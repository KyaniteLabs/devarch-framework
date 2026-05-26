"""Date-based era mapping and remapping for era cascade.

The key insight: era numbers in data files must be calculated from dates,
not assumed from previous structure. When eras merge, split, or renumber,
the only reliable remapping source is the timestamp.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class EraDef:
    id: int
    name: str
    start: datetime
    end: datetime
    commits: int


def _infer_year(raw: dict) -> int:
    """Infer the year from commit-eras.json data."""
    # Try first_commit_date or timeline metadata
    first = raw.get("first_commit_date", "")
    if first and len(first) >= 4:
        try:
            return int(first[:4])
        except (ValueError, TypeError):
            pass
    # Try daily data — find earliest date key
    for era in raw.get("eras", []):
        daily = era.get("daily", {})
        if isinstance(daily, dict):
            for date_key in sorted(daily.keys()):
                if len(date_key) >= 4:
                    try:
                        return int(date_key[:4])
                    except (ValueError, TypeError):
                        continue
    # Default to current year
    return datetime.now().year


def _parse_era_date(date_str: str, year: int, reference: datetime | None = None) -> datetime | None:
    """Parse a single date string supporting multiple formats."""
    s = date_str.strip()
    # ISO: 2026-01-15
    for fmt in ("%Y-%m-%d", "%Y-%m", "%b %d %Y", "%b %d"):
        try:
            if fmt == "%b %d":
                dt = datetime.strptime(f"{s} {year}", "%b %d %Y")
            else:
                dt = datetime.strptime(s, fmt)
            return dt
        except ValueError:
            continue
    return None


def load_eras(eras_path: Path) -> list[EraDef]:
    """Load era definitions from commit-eras.json.

    Handles date formats: "Jan 1 - Jan 5", "2026-01-01 to 2026-01-05",
    ISO single dates (era spans to next day), and month-only ranges.
    """
    if not eras_path.exists():
        return []
    import re as _re
    raw = json.loads(eras_path.read_text())
    year = _infer_year(raw)
    eras = []
    for era in raw.get("eras", []):
        dates = era.get("dates", "")
        # Split on " - ", " – ", " to " (ISO range), or handle single dates
        for sep in (" - ", " – ", " to "):
            if sep in dates:
                parts = dates.split(sep, 1)
                break
        else:
            parts = [dates, dates]  # single date → era spans that day

        start = _parse_era_date(parts[0], year)
        end = _parse_era_date(parts[1], year) if len(parts) > 1 else start
        if start is None or end is None:
            continue
        # If end is earlier than start, assume it wraps to next year
        if end < start:
            end = _parse_era_date(parts[1], year + 1) or end

        commits = era.get("commits", 0)
        if isinstance(commits, str):
            m = _re.search(r"(\d+)", commits)
            commits = int(m.group(1)) if m else 0
        eras.append(EraDef(
            id=era["id"],
            name=era["name"],
            start=start,
            end=end,
            commits=commits,
        ))
    return eras


def era_from_date(eras: list[EraDef], date_str: str) -> int | None:
    """Given a date string like '2026-03-30', return the era id it belongs to."""
    if not date_str or not isinstance(date_str, str):
        return None
    try:
        d = datetime.strptime(date_str[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return None
    for era in eras:
        if era.start <= d <= era.end:
            return era.id
    return None


def remap_json_era_fields(
    data: Any, eras: list[EraDef]
) -> list[tuple[int, int, str]]:
    """Walk JSON structure and remap all 'era' fields based on their date fields.

    Returns list of (old_era, new_era, date_string) for each change made.
    Modifies data in place.
    """
    changed: list[tuple[int, int, str]] = []
    _remap_walk(data, eras, changed)
    return changed


def _remap_walk(
    obj: Any, eras: list[EraDef], changed: list[tuple[int, int, str]]
) -> None:
    """Recursively walk and remap era fields."""
    if isinstance(obj, dict):
        if "era" in obj:
            # Try multiple date field names
            date_val = (
                obj.get("date")
                or obj.get("first_expression")
                or obj.get("estimated_hook_commit")
            )
            if date_val:
                new_era = era_from_date(eras, date_val)
                if new_era is not None and new_era != obj["era"]:
                    old = obj["era"]
                    obj["era"] = new_era
                    changed.append((old, new_era, date_val))
        for v in obj.values():
            _remap_walk(v, eras, changed)
    elif isinstance(obj, list):
        for item in obj:
            _remap_walk(item, eras, changed)


def get_current_era_names(eras: list[EraDef]) -> set[str]:
    """Return set of all current era names."""
    return {era.name for era in eras}


def era_count(eras: list[EraDef]) -> int:
    """Return the number of eras."""
    return len(eras)
