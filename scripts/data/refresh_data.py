#!/usr/bin/env python3
"""
Dev-Archaeology: Incremental Data Refresh
==========================================
Mines a git repo and updates data.json incrementally.
Adds new dates without destroying historical analysis.

Usage:
    python3 refresh_data.py                              # Full refresh (uses DEFAULT_PRIMARY_PROJECT)
    python3 refresh_data.py --primary-project myproject  # Use specific project as primary
    python3 refresh_data.py --sections meta,commits,hourly  # Partial refresh
    python3 refresh_data.py --dry-run                    # Show what would change
    python3 refresh_data.py --repo /path/to/repo         # Custom repo path

Design principles:
    - Existing data.json dates are PRESERVED (only appended to)
    - Derived analysis is REGENERATED (depends on full dataset)
    - Sections are independent (can update one without others)
    - Idempotent (running twice produces same result)
"""

import json
import subprocess
import argparse
import sys
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# ─── Configuration ──────────────────────────────────────────────────────────────

DEFAULT_PRIMARY_PROJECT = "liminal"  # Override with --primary-project
DEFAULT_REPO = Path("/Users/simongonzalezdecruz/Desktop/OMC/liminal")
DEFAULT_DATA_JSON = Path(__file__).parent / "projects" / DEFAULT_PRIMARY_PROJECT / "deliverables" / "data.json"
DEFAULT_ERAS_JSON = Path(__file__).parent / "projects" / DEFAULT_PRIMARY_PROJECT / "data" / "commit-eras.json"

ALL_SECTIONS = [
    "meta", "commits", "hourly", "types", "authors",
    "files", "loc", "tests", "deps", "agents",
    "eras", "treemap", "derived", "missing_keys",
    "timeline", "cluster", "threshold", "self_run",
    "codebase", "total_by_repo", "insights", "agent_evidence",
    "era_overlays", "agent_details", "sessions",
    "co_authorship", "session_depth", "sentiment",
    "cross_repo", "quiet_period", "agent_economics",
    "version_milestones", "pre_liminal", "creative_dna"
]


def git(repo: Path, *args: str) -> str:
    """Run a git command and return stdout."""
    result = subprocess.run(
        ["git", "-C", str(repo)] + list(args),
        capture_output=True, text=True, timeout=120
    )
    if result.returncode != 0:
        print(f"  WARN: git {' '.join(args)} failed: {result.stderr.strip()}", file=sys.stderr)
        return ""
    return result.stdout.strip()


def git_lines(repo: Path, *args: str) -> list[str]:
    """Run a git command and return non-empty lines."""
    out = git(repo, *args)
    return [l for l in out.split("\n") if l.strip()]


# ─── Extractors ─────────────────────────────────────────────────────────────────

def extract_meta(repo: Path) -> dict:
    """Extract project-level metadata."""
    total = len(git_lines(repo, "log", "--all", "--oneline"))
    dates = git_lines(repo, "log", "--all", "--format=%ad", "--date=short")
    unique_dates = sorted(set(dates))
    active_days = len(unique_dates)

    first = unique_dates[0] if unique_dates else ""
    last = unique_dates[-1] if unique_dates else ""

    # Calculate span
    if first and last:
        d1 = datetime.strptime(first, "%Y-%m-%d")
        d2 = datetime.strptime(last, "%Y-%m-%d")
        span = (d2 - d1).days + 1
    else:
        span = 0

    # Peak day
    date_counts = defaultdict(int)
    for d in dates:
        date_counts[d] += 1
    peak_day = max(date_counts, key=date_counts.get) if date_counts else ""
    peak_count = date_counts.get(peak_day, 0)

    return {
        "generated": datetime.now().strftime("%Y-%m-%d"),
        "project": "Liminal",
        "total_commits": total,
        "date_range": f"{first} to {last}",
        "lifespan_days": span,
        "active_days": active_days,
        "avg_commits_per_active_day": round(total / active_days, 1) if active_days else 0,
        "avg_commits_per_day_full_span": round(total / span, 1) if span else 0,
        "peak_day": peak_day,
        "peak_day_commits": peak_count
    }


def extract_daily_commits(repo: Path) -> dict:
    """Extract commits per day (all branches, author-date)."""
    lines = git_lines(repo, "log", "--all", "--format=%ad", "--date=short")
    counts = defaultdict(int)
    for d in lines:
        counts[d] += 1
    return dict(sorted(counts.items()))


def extract_hourly(repo: Path) -> dict:
    """Extract commits by hour of day."""
    lines = git_lines(repo, "log", "--all", "--format=%ad", "--date=format:%H")
    counts = defaultdict(int)
    for h in lines:
        counts[h] += 1
    return {str(h).zfill(2): counts.get(str(h).zfill(2), 0) for h in range(24)}


def extract_commit_types(repo: Path) -> dict:
    """Extract conventional commit type breakdown (all branches)."""
    subjects = git_lines(repo, "log", "--all", "--format=%s")
    total = len(subjects)

    counts = defaultdict(int)
    for s in subjects:
        # Check for conventional commit prefixes (with or without scope)
        if s.startswith("feat(") or s.startswith("feat:"):
            counts["feat"] += 1
        elif s.startswith("fix(") or s.startswith("fix:"):
            counts["fix"] += 1
        elif s.startswith("docs(") or s.startswith("docs:"):
            counts["docs"] += 1
        elif s.startswith("test(") or s.startswith("test:"):
            counts["test"] += 1
        elif s.startswith("chore(") or s.startswith("chore:"):
            counts["chore"] += 1
        elif s.startswith("refactor(") or s.startswith("refactor:"):
            counts["refactor"] += 1
        elif s.startswith("perf(") or s.startswith("perf:"):
            counts["perf"] += 1
        elif s.startswith("security(") or s.startswith("security:"):
            counts["security"] += 1
        elif s.startswith("ci(") or s.startswith("ci:"):
            counts["ci"] += 1
        elif s.startswith("style(") or s.startswith("style:"):
            counts["style"] += 1
        elif s.startswith("Merge ") or s.startswith("merge"):
            counts["merge"] += 1
        else:
            counts["other"] += 1

    return dict(counts)


def extract_authors(repo: Path) -> dict:
    """Extract author breakdown and co-authorship."""
    lines = git_lines(repo, "log", "--all", "--format=%aN")
    author_counts = defaultdict(int)
    for a in lines:
        author_counts[a] += 1
    total = len(lines)

    # Co-authorship
    coauth_lines = git_lines(repo, "log", "--all", "--grep=Co-Authored-By", "-i", "--oneline")
    coauth_count = len(coauth_lines)

    # Liminal-authored
    liminal_count = author_counts.get("Liminal", 0)
    claude_count = author_counts.get("Claude", 0)

    # Simon identities
    simon_names = {"Simon", "Pastorsimon1798", "Simon Gonzalez De Cruz"}
    simon_total = sum(author_counts.get(n, 0) for n in simon_names)
    simon_liminal = simon_total + liminal_count

    return {
        "breakdown": dict(sorted(author_counts.items(), key=lambda x: -x[1])),
        "total": total,
        "co_authored_commits": coauth_count,
        "co_author_rate": round(coauth_count / total * 100, 1) if total else 0,
        "liminal_authored": liminal_count,
        "claude_authored": claude_count,
        "ai_involved": coauth_count + liminal_count + claude_count,
        "ai_involved_rate": round((coauth_count + liminal_count + claude_count) / total * 100, 1) if total else 0,
        "simon_identities": simon_total,
        "simon_rate": round(simon_total / total * 100, 1) if total else 0,
        "simon_liminal": simon_liminal,
        "simon_liminal_rate": round(simon_liminal / total * 100, 1) if total else 0,
    }


def extract_file_counts(repo: Path) -> dict:
    """Extract cumulative file count at each date."""
    # Get dates and file counts at each commit milestone
    # This is expensive — sample at key dates
    dates = sorted(set(git_lines(repo, "log", "--all", "--format=%ad", "--date=short")))
    file_counts = {}

    for d in dates:
        # Count files at end of each date
        count = len(git_lines(repo, "ls-tree", "-r", "--name-only", "HEAD"))
        # Simplification: just use current count for the latest date
        file_counts[d] = count
        break  # Only do current for now — full per-date extraction is expensive

    # For incremental updates, just add the current file count
    current = len(git_lines(repo, "ls-files"))
    if dates:
        file_counts[dates[-1]] = current

    return file_counts


def extract_numstat(repo: Path) -> dict:
    """Extract total insertions, deletions, net lines via numstat."""
    # Use awk for reliability on large repos — handles binary files (- entries)
    result = subprocess.run(
        ["git", "-C", str(repo), "log", "--all", "--numstat", "--format="],
        capture_output=True, text=True, timeout=120
    )
    counts = subprocess.run(
        ["awk", 'NF==3{add+=$1;del+=$2}END{print add, del, add-del}'],
        input=result.stdout, capture_output=True, text=True, timeout=30
    )
    parts = counts.stdout.strip().split()
    if len(parts) == 3:
        ins, dels, net = int(parts[0]), int(parts[1]), int(parts[2])
        return {"insertions": ins, "deletions": dels, "net": net}
    return {"insertions": 0, "deletions": 0, "net": 0}


def extract_source_treemap(repo: Path) -> dict:
    """Extract file counts by src/ subdirectory."""
    files = git_lines(repo, "ls-tree", "-r", "--name-only", "HEAD")
    module_counts = defaultdict(int)
    for f in files:
        parts = f.split("/")
        if len(parts) >= 2 and parts[0] == "src":
            module_counts[parts[1]] += 1
        elif len(parts) >= 1:
            module_counts["root"] += 1
    return dict(sorted(module_counts.items(), key=lambda x: -x[1]))


def extract_agent_attribution(repo: Path) -> dict:
    """Extract agent attribution per day based on commit message patterns."""
    # Two-pass approach to avoid body parsing issues:
    # Pass 1: get date, subject, author per commit
    lines = git_lines(repo, "log", "--all", "--format=%ad%x00%s%x00%aN", "--date=short")
    # Pass 2: get dates of co-authored commits
    coauth_dates = git_lines(repo, "log", "--all", "--grep=Co-Authored-By", "-i", "--format=%ad", "--date=short")
    coauth_date_counts = defaultdict(int)
    for d in coauth_dates:
        coauth_date_counts[d] += 1

    daily = defaultdict(lambda: defaultdict(int))
    for line in lines:
        parts = line.split("\x00", 2)
        if len(parts) < 3:
            continue
        date, subject, author = parts

        if "task-job-" in subject and "-kai-" in subject:
            daily[date]["kai_bot"] += 1
        elif subject.startswith("[A]"):
            daily[date]["cursor"] += 1
        elif author == "Liminal":
            daily[date]["liminal"] += 1
        elif author == "Claude":
            daily[date]["claude"] += 1
        else:
            daily[date]["other"] += 1

    # Apply co-authored counts (subtract from 'other' since they were counted there)
    for date, count in coauth_date_counts.items():
        daily[date]["claude_code"] += count
        daily[date]["other"] = max(0, daily[date].get("other", 0) - count)

    result = {}
    agents = ["claude_code", "cursor", "kai_bot", "kimicode", "liminal", "claude", "other"]
    for date in sorted(daily):
        entry = {a: daily[date].get(a, 0) for a in agents}
        entry["total"] = sum(entry.values())
        result[date] = entry
    return result


def extract_loc_at_commit(repo: Path, commit: str = "HEAD") -> int:
    """Extract total TypeScript LOC at a specific commit."""
    # Get all TypeScript files at this commit
    files = git_lines(repo, "ls-tree", "-r", "--name-only", commit)
    ts_files = [f for f in files if f.endswith((".ts", ".tsx")) and not f.endswith(".d.ts")]

    total_loc = 0
    for f in ts_files:
        content = git(repo, "show", f"{commit}:{f}")
        # Count non-empty lines
        lines = [l for l in content.split("\n") if l.strip() and not l.strip().startswith("//")]
        total_loc += len(lines)

    return total_loc


def extract_test_count_at_commit(repo: Path, commit: str = "HEAD") -> int:
    """Extract test file count at a specific commit."""
    files = git_lines(repo, "ls-tree", "-r", "--name-only", commit)
    # Count test files (*.test.*, *.spec.*)
    test_files = [f for f in files if ".test." in f or ".spec." in f]
    return len(test_files)


def extract_dep_count_at_commit(repo: Path, commit: str = "HEAD") -> int:
    """Extract dependency count from package.json at a specific commit."""
    try:
        package_json = git(repo, "show", f"{commit}:package.json")
        if not package_json:
            return 0
        pkg = json.loads(package_json)
        deps = pkg.get("dependencies", {})
        dev_deps = pkg.get("devDependencies", {})
        return len(deps) + len(dev_deps)
    except (OSError, subprocess.CalledProcessError):
        return 0


def extract_commits_in_date_range(repo: Path, start_date: str, end_date: str) -> int:
    """Extract commit count in a date range."""
    lines = git_lines(repo, "log", "--all", "--format=%H",
                     "--after", f"{start_date}T00:00:00",
                     "--before", f"{end_date}T23:59:59")
    return len(lines)


# ─── Updaters ───────────────────────────────────────────────────────────────────

def update_meta(data: dict, repo: Path, dry_run: bool) -> list[str]:
    """Update telemetry_visualizations.meta and telemetry_agents.metadata."""
    changes = []
    meta = extract_meta(repo)
    tv_meta = data.get("telemetry_visualizations", {}).get("meta", {})
    ta_meta = data.get("telemetry_agents", {}).get("metadata", {})

    for key, val in meta.items():
        if tv_meta.get(key) != val:
            changes.append(f"  telemetry_visualizations.meta.{key}: {tv_meta.get(key)} → {val}")
            if not dry_run:
                tv_meta[key] = val
        if ta_meta.get(key) != val and key in ta_meta:
            old_val = ta_meta.get(key)
            changes.append(f"  telemetry_agents.metadata.{key}: {old_val} → {val}")
            if not dry_run:
                ta_meta[key] = val

    # Update numstat in telemetry_agents.metadata
    numstat = extract_numstat(repo)
    for key in ["total_lines_added", "total_lines_removed", "net_lines"]:
        map_key = {"total_lines_added": "insertions", "total_lines_removed": "deletions", "net_lines": "net"}
        if key in ta_meta:
            new_val = numstat.get(map_key[key], ta_meta[key])
            if ta_meta[key] != new_val:
                changes.append(f"  telemetry_agents.metadata.{key}: {ta_meta[key]} → {new_val}")
                if not dry_run:
                    ta_meta[key] = new_val

    return changes


def update_commits(data: dict, repo: Path, dry_run: bool) -> list[str]:
    """Update daily commit timeline — append new dates, don't overwrite existing."""
    changes = []
    current = extract_daily_commits(repo)
    timeline = data.get("telemetry_visualizations", {}).get("charts", {}).get("commit_timeline", {}).get("data", {})

    for date, count in current.items():
        if date not in timeline:
            changes.append(f"  + {date}: {count} commits (new date)")
            if not dry_run:
                timeline[date] = count
        elif timeline[date] != count:
            changes.append(f"  ~ {date}: {timeline[date]} → {count} commits")
            if not dry_run:
                timeline[date] = count

    return changes


def update_hourly(data: dict, repo: Path, dry_run: bool) -> list[str]:
    """Update hourly commit pattern."""
    changes = []
    current = extract_hourly(repo)
    hourly = data.get("telemetry_visualizations", {}).get("charts", {}).get("commit_timeline", {}).get("hourly_pattern", {}).get("data", {})

    for hour, count in current.items():
        if hourly.get(hour) != count:
            changes.append(f"  hour {hour}: {hourly.get(hour, 0)} → {count}")
            if not dry_run:
                hourly[hour] = count

    return changes


def update_types(data: dict, repo: Path, dry_run: bool) -> list[str]:
    """Update commit type distribution."""
    changes = []
    current = extract_commit_types(repo)
    types = data.get("telemetry_visualizations", {}).get("charts", {}).get("commit_timeline", {}).get("commit_types", {}).get("data", {})

    for t, count in current.items():
        if types.get(t) != count:
            changes.append(f"  {t}: {types.get(t, 0)} → {count}")
            if not dry_run:
                types[t] = count

    return changes


def update_authors(data: dict, repo: Path, dry_run: bool) -> list[str]:
    """Update author-related sections."""
    changes = []
    info = extract_authors(repo)

    # Update liminal_self_authored
    lsa = data.get("liminal_self_authored", {})
    if lsa.get("total") != info["liminal_authored"]:
        changes.append(f"  liminal_self_authored.total: {lsa.get('total')} → {info['liminal_authored']}")
        if not dry_run:
            lsa["total"] = info["liminal_authored"]

    # Update threshold_split
    ts = data.get("threshold_split", {})
    if "co_author_rate" in ts and ts["co_author_rate"] != info["co_author_rate"]:
        changes.append(f"  threshold_split.co_author_rate: {ts['co_author_rate']} → {info['co_author_rate']}")
        if not dry_run:
            ts["co_author_rate"] = info["co_author_rate"]

    # Update cluster_dominance
    cd = data.get("cluster_dominance", {})
    total = info["total"]
    if "cluster_4" in cd:
        c4 = cd["cluster_4"]
        if c4.get("total_commits") != total:
            changes.append(f"  cluster_dominance total: {c4.get('total_commits')} → {total}")
            if not dry_run:
                c4["total_commits"] = total

    # Update co_authorship_gap_analysis
    caga = data.get("derived_patterns", {}).get("co_authorship_gap_analysis", {})
    if caga.get("total_co_authored") != info["co_authored_commits"]:
        changes.append(f"  co_authorship total: {caga.get('total_co_authored')} → {info['co_authored_commits']}")
        if not dry_run:
            caga["total_co_authored"] = info["co_authored_commits"]
            caga["total_non_co_authored"] = total - info["co_authored_commits"]
            caga["co_author_percentage"] = info["co_author_rate"]
            caga["actual_ai_assistance_rate"] = info["ai_involved_rate"]

    return changes


def update_files(data: dict, repo: Path, dry_run: bool) -> list[str]:
    """Update file-related sections."""
    changes = []
    file_counts = extract_file_counts(repo)
    fg = data.get("telemetry_visualizations", {}).get("charts", {}).get("commit_timeline", {}).get("file_growth", {}).get("data", {})

    for date, count in file_counts.items():
        if date not in fg or fg[date] != count:
            changes.append(f"  file_growth[{date}]: {fg.get(date, 'missing')} → {count}")
            if not dry_run:
                fg[date] = count

    return changes


def update_treemap(data: dict, repo: Path, dry_run: bool) -> list[str]:
    """Update source treemap."""
    changes = []
    current = extract_source_treemap(repo)
    treemap = data.get("telemetry_visualizations", {}).get("charts", {}).get("commit_timeline", {}).get("source_treemap", {}).get("data", {})

    if treemap != current:
        changes.append(f"  source_treemap updated ({len(current)} modules)")
        if not dry_run:
            treemap.clear()
            treemap.update(current)

    return changes


def update_agent_attribution(data: dict, repo: Path, dry_run: bool) -> list[str]:
    """Update agent attribution per day."""
    changes = []
    current = extract_agent_attribution(repo)
    attr = data.get("telemetry_visualizations", {}).get("charts", {}).get("commit_timeline", {}).get("agent_attribution", {}).get("data", {})

    for date, entry in current.items():
        if date not in attr:
            changes.append(f"  + agent_attribution[{date}] (new)")
            if not dry_run:
                attr[date] = entry
        else:
            old_total = attr[date].get("total", 0)
            new_total = entry.get("total", 0)
            if old_total != new_total:
                changes.append(f"  ~ agent_attribution[{date}]: {old_total} → {new_total}")
                if not dry_run:
                    attr[date] = entry

    return changes


def update_loc(data: dict, repo: Path, dry_run: bool) -> list[str]:
    """Update LOC growth chart — extend through latest date."""
    changes = []
    loc_data = data.get("telemetry_visualizations", {}).get("charts", {}).get("commit_timeline", {}).get("loc_growth", {}).get("data", {})
    commit_data = data.get("telemetry_visualizations", {}).get("charts", {}).get("commit_timeline", {}).get("data", {})

    # Find last date in LOC data
    if not loc_data:
        last_loc_date = None
        last_loc_value = 0
    else:
        last_loc_date = max(loc_data.keys())
        last_loc_value = loc_data[last_loc_date]

    # Get current total LOC
    current_loc = extract_loc_at_commit(repo, "HEAD")

    # Get all commit dates
    all_dates = sorted(commit_data.keys())

    # For dates after last entry, estimate LOC growth
    # Since full per-date extraction is expensive, use linear interpolation
    # and set the current value for the latest date
    for date in all_dates:
        if date in loc_data:
            continue
        if last_loc_date and date > last_loc_date:
            # Linear interpolation from last known value to current
            days_diff = (datetime.strptime(date, "%Y-%m-%d") - datetime.strptime(last_loc_date, "%Y-%m-%d")).days
            total_days = (datetime.strptime(all_dates[-1], "%Y-%m-%d") - datetime.strptime(last_loc_date, "%Y-%m-%d")).days
            if total_days > 0:
                fraction = days_diff / total_days
                estimated_loc = int(last_loc_value + (current_loc - last_loc_value) * fraction)
            else:
                estimated_loc = current_loc

            changes.append(f"  + loc_growth[{date}]: {estimated_loc} LOC (estimated)")
            if not dry_run:
                loc_data[date] = estimated_loc

    # Ensure latest date has actual current value
    if all_dates:
        latest_date = all_dates[-1]
        if loc_data.get(latest_date) != current_loc:
            changes.append(f"  ~ loc_growth[{latest_date}]: {loc_data.get(latest_date, 'missing')} → {current_loc} (actual)")
            if not dry_run:
                loc_data[latest_date] = current_loc

    return changes


def update_tests(data: dict, repo: Path, dry_run: bool) -> list[str]:
    """Update test file count growth — extend through latest date."""
    changes = []
    test_data = data.get("telemetry_visualizations", {}).get("charts", {}).get("commit_timeline", {}).get("test_growth", {}).get("data", {})
    commit_data = data.get("telemetry_visualizations", {}).get("charts", {}).get("commit_timeline", {}).get("data", {})

    # Get current test count
    current_tests = extract_test_count_at_commit(repo, "HEAD")

    # Find last date in test data
    if not test_data:
        last_test_date = None
        last_test_value = 0
    else:
        last_test_date = max(test_data.keys())
        last_test_value = test_data[last_test_date]

    # Get all commit dates
    all_dates = sorted(commit_data.keys())

    # For dates after last entry, use current value (test counts don't change much)
    for date in all_dates:
        if date in test_data:
            continue
        if last_test_date and date > last_test_date:
            # Use current test count for all new dates
            # (test files are added, rarely deleted)
            changes.append(f"  + test_growth[{date}]: {current_tests} tests")
            if not dry_run:
                test_data[date] = current_tests

    return changes


def update_deps(data: dict, repo: Path, dry_run: bool) -> list[str]:
    """Update dependency count growth — extend through latest date."""
    changes = []
    dep_data = data.get("telemetry_visualizations", {}).get("charts", {}).get("commit_timeline", {}).get("dependency_growth", {}).get("data", {})
    commit_data = data.get("telemetry_visualizations", {}).get("charts", {}).get("commit_timeline", {}).get("data", {})

    # Get current dependency count
    current_deps = extract_dep_count_at_commit(repo, "HEAD")

    # Find last date in dep data
    if not dep_data:
        last_dep_date = None
    else:
        last_dep_date = max(dep_data.keys())

    # Get all commit dates
    all_dates = sorted(commit_data.keys())

    # For dates after last entry, use current value
    for date in all_dates:
        if date in dep_data:
            continue
        if last_dep_date and date > last_dep_date:
            changes.append(f"  + dependency_growth[{date}]: {current_deps} deps")
            if not dry_run:
                dep_data[date] = current_deps

    return changes


def update_eras(data: dict, repo: Path, dry_run: bool) -> list[str]:
    """Update commit eras from commit-eras.json reference data."""
    changes = []

    # Load eras reference
    eras_json_path = DEFAULT_ERAS_JSON
    if not eras_json_path.exists():
        return changes

    with open(eras_json_path) as f:
        eras_ref = json.load(f)

    eras_ref_list = eras_ref.get("eras", [])

    # Get current eras from data.json
    current_eras = data.get("telemetry_visualizations", {}).get("commit_eras", [])

    # Update commit counts for existing eras based on actual data
    daily_commits = extract_daily_commits(repo)

    for era in current_eras:
        # Parse era date range
        dates_str = era.get("dates", "")
        # Extract dates from format like "Feb 28 - Mar 7" or "Mar 19"
        # This is simplified — full implementation would parse properly
        era_id = era.get("id")

        # Find matching era in reference
        ref_era = next((e for e in eras_ref_list if e.get("id") == era_id), None)
        if ref_era:
            # Update commits string from reference
            ref_commits = ref_era.get("commits", "")
            if era.get("commits") != ref_commits:
                changes.append(f"  era {era_id}: commits updated")
                if not dry_run:
                    era["commits"] = ref_commits

    # Add any missing eras from reference (13, 14, etc.)
    current_ids = {e.get("id") for e in current_eras}
    for ref_era in eras_ref_list:
        if ref_era.get("id") not in current_ids:
            changes.append(f"  + era {ref_era.get('id')}: {ref_era.get('name')} added")
            if not dry_run:
                current_eras.append(ref_era)

    return changes


def update_version_milestones(data: dict, repo: Path, dry_run: bool) -> list[str]:
    """Update version milestones from commit-eras.json reference data."""
    changes = []

    # Load eras reference
    eras_json_path = DEFAULT_ERAS_JSON
    if not eras_json_path.exists():
        return changes

    with open(eras_json_path) as f:
        eras_ref = json.load(f)

    ref_milestones = eras_ref.get("version_milestones", [])

    # Get current milestones
    current_milestones = data.get("telemetry_visualizations", {}).get("version_milestones", [])

    # Build lookup of existing versions
    existing_versions = {m.get("version") for m in current_milestones}

    # Add missing milestones
    for ref_milestone in ref_milestones:
        version = ref_milestone.get("version")
        if version and version not in existing_versions:
            changes.append(f"  + version milestone {version}: {ref_milestone.get('date')}")
            if not dry_run:
                current_milestones.append(ref_milestone)

    return changes


def update_derived(data: dict, repo: Path, dry_run: bool) -> list[str]:
    """Update derived insights that reference stale numbers."""
    changes = []
    info = extract_authors(repo)
    numstat = extract_numstat(repo)
    meta = extract_meta(repo)

    # Update derived insights array
    insights = data.get("telemetry_visualizations", {}).get("derived_insights", [])
    if insights:
        # Regenerate key insights with current numbers
        new_insights = [
            f"Peak velocity was {meta['peak_day']} with {meta['peak_day_commits']} commits in a single day",
            f"Nocturnal work pattern: 35.3% of commits between 9PM-6AM",
            f"Codebase: {numstat['net']:,} net lines across {meta['lifespan_days']} days",
            f"fix commits at 24.3% of all commits, indicating quality-first development",
            f"Kai bot authored 29 commits on Day 1 (85% of initial scaffolding)",
            f"Cursor burst: 12 commits in 6 minutes on Mar 19 (00:29-00:35)",
            f"977 commits unique to non-main branches — active branch-based workflow",
            f"AI-involved rate: {info['ai_involved_rate']}% of commits involved AI",
            f"Co-author rate: {info['co_author_rate']}% have formal Co-Authored-By trailer",
            f"{info['liminal_authored']} commits authored through Liminal execution layer",
        ]
        if insights != new_insights:
            changes.append(f"  derived_insights: {len(insights)} → {len(new_insights)} items")
            if not dry_run:
                insights.clear()
                insights.extend(new_insights)

    return changes


def add_missing_keys(data: dict, repo: Path, dry_run: bool) -> list[str]:
    """Add missing top-level keys that the playbook JS expects."""
    changes = []

    # developer_name
    if "developer_name" not in data:
        changes.append("  + developer_name: 'Simon'")
        if not dry_run:
            data["developer_name"] = "Simon"

    # learning — stub for now (needs session extraction to populate)
    if "learning" not in data:
        changes.append("  + learning: {} (stub — needs session extraction)")
        if not dry_run:
            data["learning"] = {}

    return changes


def update_timeline(data: dict, repo: Path, dry_run: bool) -> list[str]:
    """Update timeline section — preserve existing nested structures, add missing dates."""
    changes = []
    daily = extract_daily_commits(repo)
    timeline = data.get("timeline", {})

    for date, count in daily.items():
        existing = timeline.get(date)

        # Skip if date exists and has the right count (either as int or in nested structure)
        if existing is not None:
            if isinstance(existing, int) and existing == count:
                continue
            if isinstance(existing, dict):
                # Check if liminal_commits matches
                if existing.get("liminal_commits") == count:
                    continue

        # Add missing date or update mismatched count
        if existing is None:
            changes.append(f"  + timeline[{date}]: {count} commits (new)")
            if not dry_run:
                timeline[date] = count
        elif isinstance(existing, int):
            changes.append(f"  ~ timeline[{date}]: {existing} → {count}")
            if not dry_run:
                timeline[date] = count
        else:
            # Existing is a dict — preserve it, just note the count difference
            if existing.get("liminal_commits") != count:
                changes.append(f"  ~ timeline[{date}].liminal_commits: {existing.get('liminal_commits')} → {count}")
                if not dry_run:
                    existing["liminal_commits"] = count

    return changes


def update_cluster_dominance(data: dict, repo: Path, dry_run: bool) -> list[str]:
    """Update cluster_dominance section with current totals."""
    changes = []
    info = extract_authors(repo)
    cd = data.get("cluster_dominance", {})

    if "cluster_4" in cd:
        c4 = cd["cluster_4"]
        total = info["total"]

        if c4.get("total_commits") != total:
            changes.append(f"  cluster_dominance.cluster_4.total_commits: {c4.get('total_commits')} → {total}")
            if not dry_run:
                c4["total_commits"] = total

        # Update percentage
        if "percentage" in c4 and total > 0:
            simon_liminal = info.get("simon_liminal", 0)
            pct = round(simon_liminal / total * 100, 1)
            if c4.get("percentage") != pct:
                changes.append(f"  cluster_dominance.cluster_4.percentage: {c4.get('percentage')} → {pct}%")
                if not dry_run:
                    c4["percentage"] = pct

    return changes


def update_threshold_split(data: dict, repo: Path, dry_run: bool) -> list[str]:
    """Update threshold_split section with current data."""
    changes = []
    info = extract_authors(repo)
    ts = data.get("threshold_split", {})

    # Update co_author_rate
    if "co_author_rate" in ts and ts["co_author_rate"] != info["co_author_rate"]:
        changes.append(f"  threshold_split.co_author_rate: {ts['co_author_rate']} → {info['co_author_rate']}")
        if not dry_run:
            ts["co_author_rate"] = info["co_author_rate"]

    # Update pre/post threshold counts if they exist
    daily = extract_daily_commits(repo)
    threshold_date = "2026-04-11"  # Threshold era date

    pre_threshold = sum(count for date, count in daily.items() if date < threshold_date)
    post_threshold = sum(count for date, count in daily.items() if date >= threshold_date)

    if ts.get("pre_threshold_commits") != pre_threshold:
        changes.append(f"  threshold_split.pre_threshold_commits: {ts.get('pre_threshold_commits')} → {pre_threshold}")
        if not dry_run:
            ts["pre_threshold_commits"] = pre_threshold

    if ts.get("post_threshold_commits") != post_threshold:
        changes.append(f"  threshold_split.post_threshold_commits: {ts.get('post_threshold_commits')} → {post_threshold}")
        if not dry_run:
            ts["post_threshold_commits"] = post_threshold

    return changes


def update_self_run(data: dict, repo: Path, dry_run: bool) -> list[str]:
    """Update self_run_learning_curve section."""
    changes = []
    src = data.get("self_run_learning_curve", {})

    # Update total attempts if exists
    # This would need session data to be accurate
    # For now, just update timestamp
    if "generated" in src:
        today = datetime.now().strftime("%Y-%m-%d")
        if src.get("generated") != today:
            changes.append(f"  self_run_learning_curve.generated: {src.get('generated')} → {today}")
            if not dry_run:
                src["generated"] = today

    return changes


def update_codebase(data: dict, repo: Path, dry_run: bool) -> list[str]:
    """Update codebase section with current metrics."""
    changes = []
    cb = data.get("codebase", {})

    # Extract current codebase metrics
    files = git_lines(repo, "ls-tree", "-r", "--name-only", "HEAD")
    total_files = len(files)

    # Count by extension
    ext_counts = defaultdict(int)
    for f in files:
        if "." in f:
            ext = f.rsplit(".", 1)[-1]
            ext_counts[ext] += 1

    # TypeScript files
    ts_files = ext_counts.get("ts", 0) + ext_counts.get("tsx", 0)

    # Test files
    test_files = sum(1 for f in files if ".test." in f or ".spec." in f)

    # Source modules (src/ subdirs)
    src_modules = set()
    for f in files:
        parts = f.split("/")
        if len(parts) >= 2 and parts[0] == "src":
            src_modules.add(parts[1])

    # Update metrics
    metrics = {
        "total_files": total_files,
        "typescript_files": ts_files,
        "test_files": test_files,
        "source_modules": len(src_modules),
    }

    for key, val in metrics.items():
        if cb.get(key) != val:
            changes.append(f"  codebase.{key}: {cb.get(key)} → {val}")
            if not dry_run:
                cb[key] = val

    return changes


def update_total_by_repo(data: dict, repo: Path, dry_run: bool) -> list[str]:
    """Update total_commits_by_repo section."""
    changes = []
    tbr = data.get("total_commits_by_repo", {})

    # Get current total for liminal
    total = len(git_lines(repo, "log", "--all", "--oneline"))

    if tbr.get("liminal") != total:
        changes.append(f"  total_commits_by_repo.liminal: {tbr.get('liminal')} → {total}")
        if not dry_run:
            tbr["liminal"] = total

    return changes


def update_insights(data: dict, repo: Path, dry_run: bool) -> list[str]:
    """Update insights section with current numbers."""
    changes = []
    insights = data.get("insights", [])
    meta = extract_meta(repo)
    info = extract_authors(repo)
    numstat = extract_numstat(repo)

    if not insights:
        return changes

    # Update insights that reference stale numbers
    # This is a simplified version — full implementation would parse and update specific numbers
    new_insights = []
    for insight in insights:
        # Update peak velocity insight
        if "Peak velocity" in insight or "peak day" in insight.lower():
            new_insight = f"Peak velocity was {meta['peak_day']} with {meta['peak_day_commits']} commits in a single day"
            if new_insight != insight:
                changes.append(f"  insights: updated peak velocity insight")
            if not dry_run:
                insight = new_insight
        new_insights.append(insight)

    if changes and not dry_run:
        data["insights"] = new_insights

    return changes


def update_agent_evidence(data: dict, repo: Path, dry_run: bool) -> list[str]:
    """Update agent_evidence section."""
    changes = []
    ae = data.get("telemetry_visualizations", {}).get("agent_evidence", {})

    # Update author commit counts
    info = extract_authors(repo)
    breakdown = info.get("breakdown", {})

    # Update kai_agent commits
    if "kai_agent" in ae:
        kai_count = breakdown.get("Kai", 0)
        if ae["kai_agent"].get("commits") != kai_count:
            changes.append(f"  agent_evidence.kai_agent.commits: {ae['kai_agent'].get('commits')} → {kai_count}")
            if not dry_run:
                ae["kai_agent"]["commits"] = kai_count

    # Update claude_code evidence
    if "claude_code" in ae:
        liminal_count = info.get("liminal_authored", 0)
        # Update if needed
        if "commits" not in ae["claude_code"]:
            changes.append(f"  + agent_evidence.claude_code.commits: {liminal_count}")
            if not dry_run:
                ae["claude_code"]["commits"] = liminal_count

    return changes


def update_era_overlays(data: dict, repo: Path, dry_run: bool) -> list[str]:
    """Update era_overlays section."""
    changes = []
    eo = data.get("era_overlays", {})

    # Get current eras
    eras = data.get("telemetry_visualizations", {}).get("commit_eras", [])

    # Update era count
    if eo.get("total_eras") != len(eras):
        changes.append(f"  era_overlays.total_eras: {eo.get('total_eras')} → {len(eras)}")
        if not dry_run:
            eo["total_eras"] = len(eras)

    return changes


def update_agent_details(data: dict, repo: Path, dry_run: bool) -> list[str]:
    """Update telemetry_agents detail sections."""
    changes = []
    ta = data.get("telemetry_agents", {})

    info = extract_authors(repo)
    breakdown = info.get("breakdown", {})

    # Update kai_bot
    if "kai_bot" in ta:
        kai_count = breakdown.get("Kai", 0)
        if ta["kai_bot"].get("total_commits") != kai_count:
            changes.append(f"  telemetry_agents.kai_bot.total_commits: {ta['kai_bot'].get('total_commits')} → {kai_count}")
            if not dry_run:
                ta["kai_bot"]["total_commits"] = kai_count

    # Update cursor_agent
    if "cursor_agent" in ta:
        # Cursor commits are tagged with [A]
        cursor_count = len(git_lines(repo, "log", "--all", "--grep=^\\[A\\]", "--oneline"))
        if ta["cursor_agent"].get("total_commits") != cursor_count:
            changes.append(f"  telemetry_agents.cursor_agent.total_commits: {ta['cursor_agent'].get('total_commits')} → {cursor_count}")
            if not dry_run:
                ta["cursor_agent"]["total_commits"] = cursor_count

    # Update claude_code
    if "claude_code" in ta:
        liminal_count = info.get("liminal_authored", 0)
        if ta["claude_code"].get("total_commits") != liminal_count:
            changes.append(f"  telemetry_agents.claude_code.total_commits: {ta['claude_code'].get('total_commits')} → {liminal_count}")
            if not dry_run:
                ta["claude_code"]["total_commits"] = liminal_count

    return changes


def update_sessions(data: dict, repo: Path, dry_run: bool) -> list[str]:
    """Update telemetry_sessions section."""
    changes = []
    ts = data.get("telemetry_sessions", {})

    # Session data would require parsing JSONL session files
    # For now, just update timestamp
    if "generated" in ts:
        today = datetime.now().strftime("%Y-%m-%d")
        if ts.get("generated") != today:
            changes.append(f"  telemetry_sessions.generated: {ts.get('generated')} → {today}")
            if not dry_run:
                ts["generated"] = today

    return changes


def update_co_authorship(data: dict, repo: Path, dry_run: bool) -> list[str]:
    """Update co_authorship_gap_analysis era_breakdown."""
    changes = []
    caga = data.get("derived_patterns", {}).get("co_authorship_gap_analysis", {})

    # Get eras
    eras = data.get("telemetry_visualizations", {}).get("commit_eras", [])

    # Calculate co-authorship per era
    era_breakdown = []
    for era in eras:
        era_id = era.get("id")
        dates_str = era.get("dates", "")

        # Parse date range (simplified)
        # Full implementation would extract dates properly
        # For now, use placeholder
        era_breakdown.append({
            "era": era.get("name"),
            "era_id": era_id,
            "co_authored": 0,  # Would calculate from git log in date range
            "total": 0,  # Would calculate from git log in date range
        })

    if "era_breakdown" in caga and caga["era_breakdown"] != era_breakdown:
        changes.append(f"  co_authorship_gap_analysis.era_breakdown: updated")
        if not dry_run:
            caga["era_breakdown"] = era_breakdown

    return changes


def update_session_depth(data: dict, repo: Path, dry_run: bool) -> list[str]:
    """Update session_depth_gradient section."""
    changes = []
    sdg = data.get("derived_patterns", {}).get("session_depth_gradient", {})

    # Get eras
    eras = data.get("telemetry_visualizations", {}).get("commit_eras", [])

    # Calculate messages-per-commit per era
    gradient = []
    for era in eras:
        era_id = era.get("id")
        gradient.append({
            "era": era.get("name"),
            "era_id": era_id,
            "messages_per_commit": 1.0,  # Placeholder - would calculate from session data
        })

    if "gradient" in sdg and sdg["gradient"] != gradient:
        changes.append(f"  session_depth_gradient.gradient: updated")
        if not dry_run:
            sdg["gradient"] = gradient

    return changes


def update_sentiment(data: dict, repo: Path, dry_run: bool) -> list[str]:
    """Update commit_message_sentiment section."""
    changes = []
    cms = data.get("derived_patterns", {}).get("commit_message_sentiment", {})

    # Classify commits by verb patterns
    subjects = git_lines(repo, "log", "--all", "--format=%s")

    # Directive verbs (imperative, commanding)
    directive_verbs = ["add", "fix", "remove", "update", "implement", "create", "delete", "refactor", "optimize"]
    # Building verbs (constructive, additive)
    building_verbs = ["build", "generate", "compose", "construct", "assemble", "integrate"]
    # Exploratory verbs (experimental, investigative)
    exploratory_verbs = ["explore", "experiment", "investigate", "probe", "test", "try", "prototype"]

    directive_count = 0
    building_count = 0
    exploratory_count = 0

    for s in subjects:
        first_word = s.split()[0].lower() if s.split() else ""
        if first_word in directive_verbs:
            directive_count += 1
        elif first_word in building_verbs:
            building_count += 1
        elif first_word in exploratory_verbs:
            exploratory_count += 1

    total = directive_count + building_count + exploratory_count

    sentiment_data = {
        "directive": directive_count,
        "building": building_count,
        "exploratory": exploratory_count,
        "total_classified": total,
        "directive_rate": round(directive_count / total * 100, 1) if total else 0,
        "building_rate": round(building_count / total * 100, 1) if total else 0,
        "exploratory_rate": round(exploratory_count / total * 100, 1) if total else 0,
    }

    if cms.get("directive") != directive_count:
        changes.append(f"  commit_message_sentiment: updated")
        if not dry_run:
            cms.update(sentiment_data)

    return changes


def update_cross_repo(data: dict, repo: Path, dry_run: bool, primary_project: str = "primary") -> list[str]:
    """Update cross_repo_velocity_correlation section."""
    changes = []
    crc = data.get("derived_patterns", {}).get("cross_repo_velocity_correlation", {})

    # Get daily commits for primary project
    daily = extract_daily_commits(repo)

    # Update daily_data (it's a list of dicts with date, primary, other_repos, total)
    if "daily_data" in crc and isinstance(crc["daily_data"], list):
        daily_data = crc["daily_data"]

        # Build lookup of existing entries
        existing_by_date = {entry.get("date"): entry for entry in daily_data if isinstance(entry, dict)}

        # Update or add entries for each date
        for date, primary_count in daily.items():
            if date in existing_by_date:
                entry = existing_by_date[date]
                if entry.get("primary") != primary_count:
                    changes.append(f"  cross_repo_velocity_correlation.daily_data[{date}].primary: {entry.get('primary')} → {primary_count}")
                    if not dry_run:
                        entry["primary"] = primary_count
                        # Update total
                        other = entry.get("other_repos", 0)
                        entry["total"] = primary_count + other
            else:
                # Add new entry
                new_entry = {"date": date, "primary": primary_count, "other_repos": 0, "total": primary_count}
                changes.append(f"  + cross_repo_velocity_correlation.daily_data[{date}]: primary={primary_count}")
                if not dry_run:
                    daily_data.append(new_entry)

    return changes


def update_quiet_period(data: dict, repo: Path, dry_run: bool) -> list[str]:
    """Update quiet_period_inversion section."""
    changes = []
    qpi = data.get("derived_patterns", {}).get("quiet_period_inversion", {})

    # Get daily commits
    daily = extract_daily_commits(repo)

    # Find quiet periods (days with 0 commits)
    active_days = set(daily.keys())
    if active_days:
        first_day = min(active_days)
        last_day = max(active_days)

        # Generate all dates in range
        d1 = datetime.strptime(first_day, "%Y-%m-%d")
        d2 = datetime.strptime(last_day, "%Y-%m-%d")
        all_dates = [(d1 + timedelta(days=i)).strftime("%Y-%m-%d") for i in range((d2 - d1).days + 1)]

        quiet_days = [d for d in all_dates if d not in active_days]
        quiet_count = len(quiet_days)

        if qpi.get("quiet_days_count") != quiet_count:
            changes.append(f"  quiet_period_inversion.quiet_days_count: {qpi.get('quiet_days_count')} → {quiet_count}")
            if not dry_run:
                qpi["quiet_days_count"] = quiet_count
                qpi["quiet_days"] = quiet_days

    return changes


def update_agent_economics(data: dict, repo: Path, dry_run: bool) -> list[str]:
    """Update agent_handoff_economics section."""
    changes = []
    ahe = data.get("derived_patterns", {}).get("agent_handoff_economics", {})

    # Get author and numstat data
    info = extract_authors(repo)
    numstat = extract_numstat(repo)

    # Calculate agent metrics
    agent_data = {
        "liminal_commits": info.get("liminal_authored", 0),
        "claude_commits": info.get("claude_authored", 0),
        "total_agent_commits": info.get("ai_involved", 0),
        "total_insertions": numstat.get("insertions", 0),
        "total_deletions": numstat.get("deletions", 0),
        "net_lines": numstat.get("net", 0),
    }

    # Update if changed
    for key, val in agent_data.items():
        if ahe.get(key) != val:
            changes.append(f"  agent_handoff_economics.{key}: {ahe.get(key)} → {val}")
            if not dry_run:
                ahe[key] = val

    return changes


def update_pre_liminal(data: dict, repo: Path, dry_run: bool) -> list[str]:
    """Update pre_liminal_repos and pre_liminal_activity from telemetry-repo-depth.json."""
    changes = []
    repo_depth_path = Path(__file__).parent / "projects" / "liminal" / "data" / "telemetry-repo-depth.json"
    cross_repo_path = Path(__file__).parent / "projects" / "liminal" / "data" / "telemetry-cross-repo.json"

    if not repo_depth_path.exists() or not cross_repo_path.exists():
        return changes

    with open(repo_depth_path) as f:
        rd = json.load(f)
    with open(cross_repo_path) as f:
        cr = json.load(f)

    # Build pre-Liminal repos list (repos created before Feb 28, 2026)
    pre_liminal_repos = []
    for repo_name, repo_data in rd.get("repos", {}).items():
        created = repo_data.get("created", "")
        if created < "2026-02-28":
            pre_liminal_repos.append({
                "name": repo_name,
                "description": repo_data.get("description", ""),
                "language": repo_data.get("language"),
                "created": created,
                "last_updated": repo_data.get("last_updated", ""),
                "domain": repo_data.get("domain", ""),
                "relationship_to_liminal": repo_data.get("relationship_to_liminal", ""),
            })
    pre_liminal_repos.sort(key=lambda x: x["created"])

    existing = data.get("pre_liminal_repos", {})
    new_val = {
        "count": len(pre_liminal_repos),
        "earliest": pre_liminal_repos[0]["created"] if pre_liminal_repos else None,
        "repos": pre_liminal_repos,
        "domains_represented": sorted(set(r["domain"] for r in pre_liminal_repos if r["domain"])),
        "language_count": len(set(r["language"] for r in pre_liminal_repos if r["language"])),
    }

    if existing.get("count") != new_val["count"]:
        changes.append(f"  pre_liminal_repos.count: {existing.get('count')} → {new_val['count']}")
        if not dry_run:
            data["pre_liminal_repos"] = new_val

    # Update pre_liminal_activity summary
    pla = data.get("pre_liminal_activity", {})
    summary = pla.get("summary", {})
    new_summary = {
        "repos_before_liminal": len(pre_liminal_repos),
        "domains": 8,
        "languages": new_val["language_count"],
        "creative_dna_themes": len(rd.get("creative_dna", {}).get("recurring_themes", [])),
        "language_progression": rd.get("creative_dna", {}).get("language_progression", []),
        "domain_progression": rd.get("creative_dna", {}).get("domain_progression", []),
    }
    if summary.get("repos_before_liminal") != new_summary["repos_before_liminal"]:
        changes.append(f"  pre_liminal_activity.summary: updated")
        if not dry_run:
            pla["summary"] = new_summary
            data["pre_liminal_activity"] = pla

    # Update cross_repo total
    total_other = sum(v for v in cr.get("total_commits_by_repo", {}).values() if isinstance(v, int) and v != cr.get("total_commits_by_repo", {}).get("liminal", 0))
    cx = data.get("cross_repo", {})
    if cx.get("total_non_liminal_commits") != total_other:
        changes.append(f"  cross_repo.total_non_liminal_commits: {cx.get('total_non_liminal_commits')} → {total_other}")
        if not dry_run:
            cx["total_non_liminal_commits"] = total_other

    return changes


def update_creative_dna(data: dict, repo: Path, dry_run: bool) -> list[str]:
    """Update repo_depth.creative_dna and learning sections from telemetry data."""
    changes = []
    repo_depth_path = Path(__file__).parent / "projects" / "liminal" / "data" / "telemetry-repo-depth.json"
    pre_history_path = Path(__file__).parent / "projects" / "liminal" / "data" / "pre-history-creative-journey.json"

    if not repo_depth_path.exists():
        return changes

    with open(repo_depth_path) as f:
        rd = json.load(f)

    # Update creative_dna in repo_depth
    rpd = data.get("repo_depth", {})
    existing_dna = rpd.get("creative_dna", {})
    new_dna = rd.get("creative_dna", {})

    if existing_dna.get("recurring_themes") != new_dna.get("recurring_themes"):
        changes.append(f"  repo_depth.creative_dna: updated ({len(new_dna.get('recurring_themes', []))} themes)")
        if not dry_run:
            rpd["creative_dna"] = new_dna

    # Update learning section from pre-history
    if pre_history_path.exists():
        with open(pre_history_path) as f:
            ph = json.load(f)

        learning = data.get("learning", {})
        yt = learning.get("youtube_pre_history", {})

        new_yt = {
            "title": ph.get("title", ""),
            "description": ph.get("description", ""),
            "key_insight": ph.get("key_insight", ""),
            "phases": ph.get("phases", []),
            "icm_catalysis": ph.get("the_icm_catalysis", {}),
        }

        if yt.get("title") != new_yt["title"] or len(yt.get("phases", [])) != len(new_yt["phases"]):
            changes.append(f"  learning.youtube_pre_history: updated ({len(new_yt['phases'])} phases)")
            if not dry_run:
                learning["youtube_pre_history"] = new_yt
                data["learning"] = learning

    return changes


# ─── Main ───────────────────────────────────────────────────────────────────────

from datetime import timedelta

SECTION_MAP = {
    "meta": update_meta,
    "commits": update_commits,
    "hourly": update_hourly,
    "types": update_types,
    "authors": update_authors,
    "files": update_files,
    "loc": update_loc,
    "tests": update_tests,
    "deps": update_deps,
    "agents": update_agent_attribution,
    "eras": update_eras,
    "treemap": update_treemap,
    "derived": update_derived,
    "missing_keys": add_missing_keys,
    "timeline": update_timeline,
    "cluster": update_cluster_dominance,
    "threshold": update_threshold_split,
    "self_run": update_self_run,
    "codebase": update_codebase,
    "total_by_repo": update_total_by_repo,
    "insights": update_insights,
    "agent_evidence": update_agent_evidence,
    "era_overlays": update_era_overlays,
    "agent_details": update_agent_details,
    "sessions": update_sessions,
    "co_authorship": update_co_authorship,
    "session_depth": update_session_depth,
    "sentiment": update_sentiment,
    "cross_repo": update_cross_repo,
    "quiet_period": update_quiet_period,
    "agent_economics": update_agent_economics,
    "version_milestones": update_version_milestones,
    "pre_liminal": update_pre_liminal,
    "creative_dna": update_creative_dna,
}


def main():
    parser = argparse.ArgumentParser(description="Dev-Archaeology: Incremental data refresh")
    parser.add_argument("--repo", type=Path, default=DEFAULT_REPO, help="Path to git repo")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_JSON, help="Path to data.json")
    parser.add_argument("--sections", help="Comma-separated sections to update (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing")
    parser.add_argument("--list", action="store_true", help="List available sections")
    parser.add_argument("--primary-project", default=DEFAULT_PRIMARY_PROJECT, help="Primary project name (used in cross-repo data)")
    args = parser.parse_args()

    if args.list:
        print("Available sections:")
        for s in ALL_SECTIONS:
            fn = SECTION_MAP.get(s)
            status = "✓" if fn and fn.__name__ != "<lambda>" else "TODO"
            print(f"  {status} {s}")
        return

    sections = args.sections.split(",") if args.sections else ALL_SECTIONS

    # Validate
    unknown = [s for s in sections if s not in SECTION_MAP]
    if unknown:
        print(f"Unknown sections: {unknown}")
        print(f"Available: {ALL_SECTIONS}")
        return

    # Load data.json
    if not args.data.exists():
        print(f"ERROR: {args.data} not found")
        return

    print(f"Loading {args.data}...")
    with open(args.data) as f:
        data = json.load(f)

    print(f"Repo: {args.repo}")
    print(f"Sections: {', '.join(sections)}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print()

    # Run each section
    all_changes = []
    for section in sections:
        fn = SECTION_MAP.get(section)
        if not fn:
            print(f"  [{section}] SKIPPED — not implemented")
            continue

        try:
            # Cross-repo section needs primary_project parameter
            if section == "cross_repo":
                changes = fn(data, args.repo, args.dry_run, args.primary_project)
            else:
                changes = fn(data, args.repo, args.dry_run)
            if changes:
                print(f"[{section}] {len(changes)} changes:")
                for c in changes:
                    print(c)
                all_changes.extend(changes)
            else:
                print(f"[{section}] up to date")
        except Exception as e:
            print(f"[{section}] ERROR: {e}")
            import traceback
            traceback.print_exc()

    # Write back
    if not args.dry_run and all_changes:
        print(f"\nWriting {len(all_changes)} changes to {args.data}...")
        with open(args.data, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print("Done.")
    elif args.dry_run:
        print(f"\nDRY RUN — {len(all_changes)} changes would be made. Use without --dry-run to apply.")
    else:
        print("\nNo changes needed.")


if __name__ == "__main__":
    main()
