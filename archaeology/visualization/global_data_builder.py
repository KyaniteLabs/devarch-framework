"""Build visualization-ready JSON from aggregated global data."""

import csv
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from ..utils import _parse_date


def _safe_parse_date(s, fmt="%Y-%m-%d"):
    """Parse date string, returning None on failure."""
    if not s or not isinstance(s, str):
        return None
    try:
        return datetime.strptime(s[:10], fmt)
    except (ValueError, TypeError):
        return None

LANG_MAP = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript",
    ".jsx": "JavaScript", ".html": "HTML", ".css": "CSS", ".scss": "CSS",
    ".json": "JSON", ".md": "Markdown", ".yaml": "YAML", ".yml": "YAML",
    ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell",
    ".rs": "Rust", ".go": "Go", ".rb": "Ruby", ".java": "Java",
    ".c": "C", ".cpp": "C++", ".h": "C/C++ Header",
    ".sql": "SQL", ".graphql": "GraphQL",
    ".vue": "Vue", ".svelte": "Svelte",
    ".toml": "TOML", ".ini": "INI", ".cfg": "Config",
    ".txt": "Text", ".rst": "reStructuredText",
    ".svg": "SVG", ".png": "Image", ".jpg": "Image",
}

def _repo_color(name, index=0):
    """Generate a consistent color for a repository name."""
    # Fixed palette for known repos
    _KNOWN = {
        "liminal": "#51cf66",
        "dev-archaeology": "#74c0fc",
        "github-pipeline": "#ffa94d",
        "voice-to-sculpture": "#cc5de8",
    }
    if name in _KNOWN:
        return _KNOWN[name]
    # Generate from hash for unknown repos
    palette = ["#51cf66", "#74c0fc", "#ffa94d", "#cc5de8", "#ff6b6b", "#ffd43b", "#20c997", "#845ef7"]
    return palette[hash(name) % len(palette)]


def prepare_global_visualization_data(global_dir, top_n=None, year=None):
    """Read global data files and produce a single viz-ready JSON dict.

    Prefers GitHub API data (github-repos.json) when available for full repo
    coverage. Falls back to local CSV data otherwise.
    """
    global_dir = Path(global_dir)
    data_dir = global_dir / "data"
    github_json = data_dir / "github-repos.json"

    if github_json.exists():
        return prepare_from_github(github_json, top_n=top_n, year=year)

    # Fallback to local CSV data
    projects_dir = global_dir.parent / "projects"
    commits_csv = data_dir / "global-commits.csv"
    summaries_json = data_dir / "project-summaries.json"
    signals_json = data_dir / "global-signals.json"

    if not commits_csv.exists():
        raise FileNotFoundError(
            f"No data in {data_dir}. Run 'archaeology fetch-github' or 'archaeology sync' first."
        )

    # Load raw data
    commits = _load_commits(commits_csv)
    summaries = _load_json(summaries_json) if summaries_json.exists() else []
    signals = _load_json(signals_json) if signals_json.exists() else []

    # Assign colors
    repo_names = sorted({c["_project"] for c in commits})
    colors = {}
    for i, name in enumerate(repo_names):
        colors[name] = _repo_color(name)

    # Build sections
    result = {
        "meta": _build_meta(commits, summaries, repo_names),
        "repos": _build_repo_cards(commits, summaries, colors, projects_dir),
        "timeline": _build_global_timeline(commits, colors),
        "authors": _build_author_universe(commits, colors),
        "languages": _build_language_breakdown(projects_dir, repo_names, colors),
        "velocity": _build_velocity_comparison(commits, summaries, colors),
        "heatmap": _build_activity_heatmap(commits),
        "commit_types": _build_commit_types(commits, colors),
        "correlation": _build_correlation(commits, colors),
    }

    return result


def prepare_from_github(github_json_path, top_n=None, year=None):
    """Build visualization data from GitHub API JSON (all repos, no cloning)."""
    with open(github_json_path, encoding="utf-8") as f:
        gh_data = json.load(f)

    repos = gh_data.get("repos", [])

    # Filter by year (repos updated in that year)
    if year:
        repos = [r for r in repos if r.get("updated", "")[:4] == str(year)]

    # Sort by commits descending, then take top N
    repos.sort(key=lambda x: x["total_commits"], reverse=True)
    if top_n:
        repos = repos[:top_n]

    # Assign colors
    repo_names = sorted(r["name"] for r in repos)
    colors = {}
    for i, name in enumerate(repo_names):
        colors[name] = _repo_color(name)

    total_commits = sum(r["total_commits"] for r in repos)
    all_dates = set()
    for r in repos:
        if r.get("created"):
            all_dates.add(r["created"][:10])
        if r.get("updated"):
            all_dates.add(r["updated"][:10])

    # Unique authors across all repos
    all_authors = set()
    for r in repos:
        all_authors.update(r.get("authors", {}).keys())

    created_dates = [r["created"][:10] for r in repos if r.get("created")]
    updated_dates = [r["updated"][:10] for r in repos if r.get("updated")]
    first = min(created_dates) if created_dates else ""
    last = max(updated_dates) if updated_dates else ""

    d1, d2 = _safe_parse_date(first), _safe_parse_date(last)
    calendar_days = (d2 - d1).days + 1 if d1 and d2 else 0

    meta = {
        "total_commits": total_commits,
        "total_repos": len(repos),
        "total_active_days": None,  # not available from API
        "total_calendar_days": calendar_days,
        "total_authors": len(all_authors),
        "first_date": first,
        "last_date": last,
        "repo_names": repo_names,
    }

    # Repo cards
    repo_cards = []
    for r in sorted(repos, key=lambda x: x["total_commits"], reverse=True):
        name = r["name"]
        top_lang_bytes = sorted(r.get("languages", {}).items(), key=lambda x: x[1], reverse=True)
        top_language = top_lang_bytes[0][0] if top_lang_bytes else "Unknown"
        top_author = sorted(r.get("authors", {}).items(), key=lambda x: x[1], reverse=True)
        top_author_name = top_author[0][0] if top_author else "Unknown"

        created = r.get("created", "")[:10]
        updated = r.get("updated", "")[:10]
        dc, du = _safe_parse_date(created), _safe_parse_date(updated)
        repo_calendar_days = (du - dc).days + 1 if dc and du else 0

        repo_cards.append({
            "name": name,
            "color": colors.get(name, "#888"),
            "total_commits": r["total_commits"],
            "active_days": None,
            "calendar_days": repo_calendar_days,
            "first_date": r.get("created", "")[:10],
            "last_date": r.get("updated", "")[:10],
            "authors": len(r.get("authors", {})),
            "top_author": top_author_name,
            "top_language": top_language,
            "description": r.get("description", ""),
            "size_kb": r.get("size_kb", 0),
        })

    # Language breakdown (aggregate bytes across all repos)
    lang_by_repo = []
    for r in repos:
        name = r["name"]
        langs = r.get("languages", {})
        total_bytes = sum(langs.values())
        if not langs:
            continue
        lang_list = []
        for lang, bytes_count in sorted(langs.items(), key=lambda x: x[1], reverse=True)[:8]:
            lang_list.append({
                "language": lang,
                "count": bytes_count,
                "pct": round(bytes_count / total_bytes * 100, 1) if total_bytes else 0,
            })
        lang_by_repo.append({
            "repo": name,
            "color": colors.get(name, "#888"),
            "languages": lang_list,
            "total_files": total_bytes,
        })

    # Velocity comparison
    velocity = []
    for r in repos:
        name = r["name"]
        dc, du = _safe_parse_date(r.get("created", "")), _safe_parse_date(r.get("updated", ""))
        span_days = (du - dc).days + 1 if dc and du else 1
        velocity.append({
            "repo": name,
            "color": colors.get(name, "#888"),
            "total_commits": r["total_commits"],
            "active_days": None,
            "commits_per_day": round(r["total_commits"] / max(span_days, 1), 2),
            "peak_day": "",
            "peak_count": 0,
            "span_days": span_days,
        })
    velocity.sort(key=lambda x: x["total_commits"], reverse=True)

    # Author universe (graph)
    author_nodes_dict = {}  # Use dict for O(1) lookups instead of O(n) list scans
    repo_nodes = []
    links = []
    for r in repos:
        repo_nodes.append({
            "id": r["name"],
            "type": "repo",
            "color": colors.get(r["name"], "#888"),
        })
        for author, count in r.get("authors", {}).items():
            # O(1) dict lookup instead of O(n) list scan
            if author not in author_nodes_dict:
                author_nodes_dict[author] = {
                    "id": author,
                    "type": "author",
                    "commits": count,
                    "repos": [r["name"]],
                }
            else:
                node = author_nodes_dict[author]
                node["commits"] += count
                node["repos"].append(r["name"])
            links.append({
                "source": author,
                "target": r["name"],
                "value": count,
            })

    # Convert dict back to list for JSON serialization
    author_nodes = list(author_nodes_dict.values())

    # Commit types not available from GitHub API
    # Heatmap not available from GitHub API
    # Timeline correlation not available from GitHub API (no per-date data)

    return {
        "meta": meta,
        "repos": repo_cards,
        "timeline": None,  # requires per-commit dates
        "authors": {"nodes": author_nodes + repo_nodes, "links": links},
        "languages": lang_by_repo,
        "velocity": velocity,
        "heatmap": None,  # requires per-commit hourly data
        "commit_types": None,  # requires commit messages
        "correlation": None,  # requires per-date data
        "source": "github-api",
        "total_repos_on_github": gh_data.get("total_repos", len(repos)),
    }


def _load_commits(csv_path):
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            clean = {k: v for k, v in row.items() if k is not None}
            rows.append(clean)
    return rows


def _load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _classify_commit(message):
    """Classify commit message into type."""
    if not message:
        return "other"
    msg = message.lower().strip()
    prefixes = {
        "feat": "feature", "add": "feature", "implement": "feature", "new": "feature",
        "fix": "fix", "bug": "fix", "patch": "fix", "hotfix": "fix",
        "test": "test", "spec": "test",
        "doc": "docs", "readme": "docs",
        "refactor": "refactor", "clean": "refactor", "remove": "refactor", "simplify": "refactor",
        "chore": "chore", "build": "chore", "ci": "chore", "deps": "chore",
        "perf": "perf", "optim": "perf",
        "style": "style", "format": "style", "lint": "style",
    }
    for prefix, category in prefixes.items():
        if msg.startswith(prefix) or msg.startswith(f"[{prefix}]"):
            return category
    # Check for conventional commit prefix
    match = re.match(r"^(\w+)(\(.+\))?\!?:", msg)
    if match:
        tag = match.group(1)
        for prefix, category in prefixes.items():
            if tag.startswith(prefix):
                return category
    # Common patterns
    if any(w in msg for w in ["merge", "pull request"]):
        return "merge"
    if any(w in msg for w in ["initial", "init", "bootstrap"]):
        return "feature"
    return "other"


# ── Section builders ──────────────────────────────────────────────────


def _build_meta(commits, summaries, repo_names):
    """Build hero counters."""
    total_commits = len(commits)
    dates = set()
    authors = set()
    for c in commits:
        dt = _parse_date(c.get("date", ""))
        if dt:
            dates.add(dt.strftime("%Y-%m-%d"))
        if c.get("author"):
            authors.add(c["author"])

    first = min(dates) if dates else ""
    last = max(dates) if dates else ""
    span = 0
    if first and last:
        d1, d2 = _safe_parse_date(first), _safe_parse_date(last)
        span = (d2 - d1).days + 1

    return {
        "total_commits": total_commits,
        "total_repos": len(repo_names),
        "total_active_days": len(dates),
        "total_calendar_days": span,
        "total_authors": len(authors),
        "first_date": first,
        "last_date": last,
        "repo_names": repo_names,
    }


def _build_repo_cards(commits, summaries, colors, projects_dir):
    """Build per-repo summary cards."""
    by_repo = defaultdict(list)
    for c in commits:
        by_repo[c["_project"]].append(c)

    cards = []
    for name in sorted(by_repo.keys()):
        repo_commits = by_repo[name]
        dates = set()
        authors = Counter()
        for c in repo_commits:
            dt = _parse_date(c.get("date", ""))
            if dt:
                dates.add(dt.strftime("%Y-%m-%d"))
            if c.get("author"):
                authors[c["author"]] += 1

        sorted_dates = sorted(dates)
        first = sorted_dates[0] if sorted_dates else ""
        last = sorted_dates[-1] if sorted_dates else ""
        span = 0
        if first and last:
            d1, d2 = _safe_parse_date(first), _safe_parse_date(last)
            span = (d2 - d1).days + 1

        # Top language
        top_lang = _get_top_language(projects_dir, name)

        # Summary lookup
        summary = {}
        for s in summaries:
            if s["name"] == name:
                summary = s
                break

        cards.append({
            "name": name,
            "color": colors.get(name, "#888"),
            "total_commits": len(repo_commits),
            "active_days": len(dates),
            "calendar_days": span,
            "first_date": first,
            "last_date": last,
            "authors": len(authors),
            "top_author": authors.most_common(1)[0][0] if authors else "",
            "top_language": top_lang,
        })

    return cards


def _get_top_language(projects_dir, repo_name):
    """Get top language for a repo from file extensions."""
    repo_dir = projects_dir / repo_name
    if not repo_dir.exists():
        return "Unknown"

    ext_counter = Counter()
    for root, _, files in os.walk(str(repo_dir)):
        # Skip hidden dirs and common non-source dirs
        # Only check repo-relative parts, not absolute path prefix
        try:
            rel_path = Path(root).relative_to(repo_dir)
        except ValueError:
            # root is not relative to repo_dir (shouldn't happen with os.walk)
            continue
        if any(p.startswith(".") for p in rel_path.parts):
            continue
        if any(p in ("node_modules", "__pycache__", ".venv", "dist", "build")
               for p in rel_path.parts):
            continue
        for f in files:
            ext = Path(f).suffix.lower()
            if ext in LANG_MAP:
                ext_counter[LANG_MAP[ext]] += 1

    if not ext_counter:
        return "Unknown"
    return ext_counter.most_common(1)[0][0]


def _build_global_timeline(commits, colors):
    """Build stacked area data: date → repo → count."""
    by_date_repo = Counter()
    for c in commits:
        dt = _parse_date(c.get("date", ""))
        if dt:
            key = (dt.strftime("%Y-%m-%d"), c.get("_project", "unknown"))
            by_date_repo[key] += 1

    if not by_date_repo:
        return {"dates": [], "repos": {}, "repo_colors": colors}

    all_dates = sorted({k[0] for k in by_date_repo})
    repo_names = sorted({k[1] for k in by_date_repo})

    repos = {}
    for name in repo_names:
        repos[name] = [by_date_repo.get((d, name), 0) for d in all_dates]

    return {
        "dates": all_dates,
        "repos": repos,
        "repo_colors": colors,
    }


def _build_author_universe(commits, colors):
    """Build author-repo membership graph."""
    author_repos = defaultdict(set)
    author_commits = Counter()

    for c in commits:
        author = c.get("author", "Unknown")
        repo = c.get("_project", "unknown")
        author_repos[author].add(repo)
        author_commits[author] += 1

    nodes = []
    links = []
    for author, repos in sorted(author_repos.items()):
        nodes.append({
            "id": author,
            "type": "author",
            "commits": author_commits[author],
            "repos": list(repos),
        })
        for repo in repos:
            links.append({
                "source": author,
                "target": repo,
                "value": sum(
                    1 for c in commits
                    if c.get("author") == author and c.get("_project") == repo
                ),
            })

    # Add repo nodes
    for repo_name in sorted({c.get("_project", "") for c in commits}):
        nodes.append({
            "id": repo_name,
            "type": "repo",
            "color": colors.get(repo_name, "#888"),
        })

    return {"nodes": nodes, "links": links}


def _build_language_breakdown(projects_dir, repo_names, colors):
    """Build language breakdown per repo."""
    result = []
    for name in repo_names:
        repo_dir = projects_dir / name
        if not repo_dir.exists():
            continue

        ext_counter = Counter()
        for root, _, files in os.walk(str(repo_dir)):
            # Only check repo-relative parts, not absolute path prefix
            try:
                rel_path = Path(root).relative_to(repo_dir)
            except ValueError:
                continue
            if any(p.startswith(".") for p in rel_path.parts):
                continue
            if any(p in ("node_modules", "__pycache__", ".venv", "dist", "build")
                   for p in rel_path.parts):
                continue
            for f in files:
                ext = Path(f).suffix.lower()
                if ext in LANG_MAP:
                    ext_counter[LANG_MAP[ext]] += 1

        total = sum(ext_counter.values())
        languages = []
        for lang, count in ext_counter.most_common(10):
            languages.append({
                "language": lang,
                "count": count,
                "pct": round(count / total * 100, 1) if total else 0,
            })

        if languages:
            result.append({
                "repo": name,
                "color": colors.get(name, "#888"),
                "languages": languages,
                "total_files": total,
            })

    return result


def _build_velocity_comparison(commits, summaries, colors):
    """Build per-repo velocity stats."""
    by_repo = defaultdict(list)
    for c in commits:
        by_repo[c["_project"]].append(c)

    result = []
    for name, repo_commits in sorted(by_repo.items()):
        dates = set()
        daily = Counter()
        for c in repo_commits:
            dt = _parse_date(c.get("date", ""))
            if dt:
                ds = dt.strftime("%Y-%m-%d")
                dates.add(ds)
                daily[ds] += 1

        active_days = len(dates)
        peak = daily.most_common(1)
        peak_day = peak[0] if peak else ("", 0)

        result.append({
            "repo": name,
            "color": colors.get(name, "#888"),
            "total_commits": len(repo_commits),
            "active_days": active_days,
            "commits_per_day": round(len(repo_commits) / active_days, 1) if active_days else 0,
            "peak_day": peak_day[0],
            "peak_count": peak_day[1],
        })

    # Sort by commits descending
    result.sort(key=lambda x: x["total_commits"], reverse=True)
    return result


def _build_activity_heatmap(commits):
    """Build day×hour matrix aggregated across all repos."""
    matrix = Counter()
    for c in commits:
        dt = _parse_date(c.get("date", ""))
        if dt:
            day = dt.strftime("%a")
            hour = dt.hour
            matrix[(day, hour)] += 1

    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    hours = list(range(24))

    cells = []
    for day in days:
        for hour in hours:
            count = matrix.get((day, hour), 0)
            if count > 0:
                cells.append({"day": day, "hour": hour, "count": count})

    return {
        "days": days,
        "hours": hours,
        "cells": cells,
        "max_count": max(matrix.values()) if matrix else 0,
    }


def _build_commit_types(commits, colors):
    """Build commit type breakdown per repo."""
    by_repo = defaultdict(Counter)
    for c in commits:
        repo = c.get("_project", "unknown")
        msg = c.get("message", "")
        ctype = _classify_commit(msg)
        by_repo[repo][ctype] += 1

    all_types = sorted({t for counter in by_repo.values() for t in counter})
    result = []
    for repo in sorted(by_repo.keys()):
        breakdown = {t: by_repo[repo].get(t, 0) for t in all_types}
        result.append({
            "repo": repo,
            "color": colors.get(repo, "#888"),
            "breakdown": breakdown,
        })

    return {"types": all_types, "repos": result}


def _build_correlation(commits, colors):
    """Build data showing which repos were active on which dates."""
    by_date_repo = defaultdict(lambda: defaultdict(int))
    for c in commits:
        dt = _parse_date(c.get("date", ""))
        if dt:
            by_date_repo[dt.strftime("%Y-%m-%d")][c.get("_project", "unknown")] += 1

    dates = sorted(by_date_repo.keys())
    repo_names = sorted({c.get("_project", "") for c in commits})

    rows = []
    for d in dates:
        row = {"date": d}
        for r in repo_names:
            row[r] = by_date_repo[d].get(r, 0)
        rows.append(row)

    return {
        "dates": dates,
        "repos": repo_names,
        "rows": rows,
        "repo_colors": colors,
    }


def prepare_dashboard_data(global_dir, top_n=None, year=None):
    """Prepare simplified data for multi-project dashboard.

    This function creates a streamlined dataset optimized for the dashboard
    visualizations, focusing on repository metadata and aggregate statistics.
    """
    global_dir = Path(global_dir)
    data_dir = global_dir / "data"
    github_json = data_dir / "github-repos.json"

    if not github_json.exists():
        raise FileNotFoundError(
            f"No GitHub data found at {github_json}. Run 'archaeology fetch-github' first."
        )

    with open(github_json, encoding="utf-8") as f:
        gh_data = json.load(f)

    repos = gh_data.get("repos", [])

    # Filter by year if specified
    if year:
        repos = [r for r in repos if r.get("updated", "")[:4] == str(year)]

    # Sort by commits descending and take top N
    repos.sort(key=lambda x: x["total_commits"], reverse=True)
    if top_n:
        repos = repos[:top_n]

    # Calculate metadata
    total_commits = sum(r["total_commits"] for r in repos)
    all_authors = set()
    for r in repos:
        all_authors.update(r.get("authors", {}).keys())

    created_dates = [r["created"][:10] for r in repos if r.get("created")]
    updated_dates = [r["updated"][:10] for r in repos if r.get("updated")]
    first = min(created_dates) if created_dates else ""
    last = max(updated_dates) if updated_dates else ""

    d1, d2 = _safe_parse_date(first), _safe_parse_date(last)
    calendar_days = (d2 - d1).days + 1 if d1 and d2 else 0

    # Build repo cards with additional metadata
    repo_cards = []
    for r in repos:
        name = r["name"]

        # Get top language by bytes
        top_lang_bytes = sorted(r.get("languages", {}).items(), key=lambda x: x[1], reverse=True)
        top_language = top_lang_bytes[0][0] if top_lang_bytes else r.get("language", "Unknown")

        # Get top author
        top_author = sorted(r.get("authors", {}).items(), key=lambda x: x[1], reverse=True)
        top_author_name = top_author[0][0] if top_author else "Unknown"

        created = r.get("created", "")[:10]
        updated = r.get("updated", "")[:10]
        dc, du = _safe_parse_date(created), _safe_parse_date(updated)
        repo_calendar_days = (du - dc).days + 1 if dc and du else 0

        repo_cards.append({
            "name": name,
            "total_commits": r["total_commits"],
            "calendar_days": repo_calendar_days,
            "first_date": created,
            "last_date": updated,
            "authors": len(r.get("authors", {})),
            "top_author": top_author_name,
            "top_language": top_language,
            "description": r.get("description", ""),
            "size_kb": r.get("size_kb", 0),
            "language": r.get("language", top_language),
        })

    # Build metadata
    meta = {
        "total_commits": total_commits,
        "total_repos": len(repos),
        "total_calendar_days": calendar_days,
        "total_authors": len(all_authors),
        "first_date": first,
        "last_date": last,
        "repo_names": sorted(r["name"] for r in repos),
    }

    return {
        "meta": meta,
        "repos": repo_cards,
        "source": "github-api",
        "total_repos_on_github": gh_data.get("total_repos", len(repos)),
    }
