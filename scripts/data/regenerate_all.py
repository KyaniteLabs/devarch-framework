#!/usr/bin/env python3
"""Regenerate Dev-Archaeology's current Liminal deliverable surface.

This is the repeatable "do everything" entrypoint:

1. Fetch the Liminal source repo without pruning historical remote-tracking refs.
2. Recompute canonical git metrics from archived commit hashes union current refs.
3. Update canonical metrics/config/browser data directly from the archival scope.
4. Synchronize derived deliverables from the canonical metrics artifact.
5. Sync `data.js`.
6. Validate metrics, claims, and HTML.
7. Optionally regenerate PNG screenshots.

The canonical commit scope is archival: `projects/liminal/data/github-commits.csv` union current `git log --all`. This prevents upstream-deleted remote PR refs from erasing historical archaeology.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]  # scripts/data/ → scripts/ → project root

def _get_source_repo() -> Path:
    if env_val := os.environ.get("ARCHAEOLOGY_SOURCE_REPO", ""):
        return Path(env_val)
    raise OSError(
        "ARCHAEOLOGY_SOURCE_REPO environment variable not set. "
        "Please set it to your Liminal source repository path."
    )

DEFAULT_SOURCE_REPO = _get_source_repo()
DATA_JSON = ROOT / "projects/liminal/deliverables/data.json"
DATA_JS = ROOT / "projects/liminal/deliverables/data.js"
VERIFIED_STATS = ROOT / "projects/liminal/data/VERIFIED-STATS.md"
PROJECT_JSON = ROOT / "projects/liminal/project.json"


def run(cmd: list[str], *, cwd: Path = ROOT, capture: bool = False) -> str:
    result = subprocess.run(cmd, cwd=cwd, text=True, capture_output=capture, check=True, timeout=300)
    return result.stdout if capture else ""


def git(repo: Path, *args: str) -> str:
    return run(["git", "-C", str(repo), *args], capture=True).strip()


def git_lines(repo: Path, *args: str) -> list[str]:
    out = git(repo, *args)
    return [line for line in out.splitlines() if line.strip()]


def count_lines(repo: Path, ref: str = "origin/main") -> tuple[int, int, int]:
    raw = run(["git", "-C", str(repo), "log", "--all", "--numstat", "--format="], capture=True)
    add = delete = 0
    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
            add += int(parts[0])
            delete += int(parts[1])
    return add, delete, add - delete


def ts_loc(repo: Path, ref: str = "origin/main") -> int:
    files = git_lines(repo, "ls-tree", "-r", "--name-only", ref)
    total = 0
    for file in files:
        if not file.endswith((".ts", ".tsx")) or file.endswith(".d.ts"):
            continue
        try:
            content = git(repo, "show", f"{ref}:{file}")
        except subprocess.CalledProcessError:
            continue
        total += sum(1 for line in content.splitlines() if line.strip() and not line.strip().startswith("//"))
    return total


def test_count(repo: Path, ref: str = "origin/main") -> int:
    return sum(
        1
        for file in git_lines(repo, "ls-tree", "-r", "--name-only", ref)
        if ".test." in file or ".spec." in file
    )


def dep_count(repo: Path, ref: str = "origin/main") -> int:
    try:
        pkg = json.loads(git(repo, "show", f"{ref}:package.json"))
    except (subprocess.CalledProcessError, json.JSONDecodeError, OSError):
        return 0
    return len(pkg.get("dependencies", {})) + len(pkg.get("devDependencies", {}))


def commit_types(subjects: list[str]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for subject in subjects:
        if subject.startswith("feat(") or subject.startswith("feat:"):
            counts["feat"] += 1
        elif subject.startswith("fix(") or subject.startswith("fix:"):
            counts["fix"] += 1
        elif subject.startswith("docs(") or subject.startswith("docs:"):
            counts["docs"] += 1
        elif subject.startswith("test(") or subject.startswith("test:"):
            counts["test"] += 1
        elif subject.startswith("chore(") or subject.startswith("chore:"):
            counts["chore"] += 1
        elif subject.startswith("refactor(") or subject.startswith("refactor:"):
            counts["refactor"] += 1
        elif subject.startswith("perf(") or subject.startswith("perf:"):
            counts["perf"] += 1
        elif subject.startswith("security(") or subject.startswith("security:"):
            counts["security"] += 1
        elif subject.startswith("ci(") or subject.startswith("ci:"):
            counts["ci"] += 1
        elif subject.startswith("style(") or subject.startswith("style:"):
            counts["style"] += 1
        elif subject.startswith("Merge ") or subject.startswith("merge"):
            counts["merge"] += 1
        else:
            counts["other"] += 1
    for key in ["other", "feat", "fix", "docs", "test", "chore", "refactor", "merge", "security", "ci", "style", "perf"]:
        counts.setdefault(key, 0)
    return dict(counts)


def compute(repo: Path, *, fetch: bool) -> dict[str, Any]:
    if fetch:
        run(["git", "-C", str(repo), "fetch", "--all", "--tags"])

    known_commits: dict[str, dict[str, str]] = {}
    archive_path = ROOT / "projects/liminal/data/github-commits.csv"
    if archive_path.exists():
        import csv
        with archive_path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("hash"):
                    known_commits[row["hash"]] = {
                        "date": row.get("date", "")[:10],
                        "subject": row.get("message", ""),
                        "author": row.get("author", ""),
                    }

    current_lines = git_lines(repo, "log", "--all", "--format=%H%x00%ad%x00%s%x00%aN", "--date=iso-strict")
    for line in current_lines:
        parts = line.split("\x00", 3)
        if len(parts) == 4:
            commit_hash, commit_date, subject, author = parts
            known_commits[commit_hash] = {"date": commit_date[:10], "subject": subject, "author": author}

    daily = Counter(c["date"] for c in known_commits.values() if c.get("date"))
    # Hour-level data is only available from currently reachable git refs; keep it advisory.
    hours = Counter(git_lines(repo, "log", "--all", "--format=%ad", "--date=format:%H"))
    active_dates = sorted(daily)
    if not active_dates:
        raise ValueError("No active dates found in commit history")
    first = active_dates[0]
    last = active_dates[-1]
    span = (datetime.strptime(last, "%Y-%m-%d") - datetime.strptime(first, "%Y-%m-%d")).days + 1
    total = len(known_commits)
    origin_main = len(git_lines(repo, "log", "origin/main", "--oneline"))
    non_main = total - origin_main
    peak_day, peak_commits = max(daily.items(), key=lambda item: item[1]) if daily else ("", 0)
    add, delete, net = count_lines(repo)
    subjects = [c["subject"] for c in known_commits.values()]
    types = commit_types(subjects)

    author_names = [c["author"] for c in known_commits.values()]
    authors = Counter(author_names)
    simon = authors.get("Simon", 0)
    sgdc = authors.get("Simon Gonzalez De Cruz", 0)
    pastor = authors.get("Pastorsimon1798", 0)
    liminal = authors.get("Liminal", 0)
    claude = authors.get("Claude", 0)
    dependabot = authors.get("dependabot[bot]", 0)
    coauth = len(git_lines(repo, "log", "--all", "--grep=Co-Authored-By", "-i", "--oneline"))
    ai_involved = coauth + liminal + claude

    origin_files = len(git_lines(repo, "ls-tree", "-r", "--name-only", "origin/main"))
    loc = ts_loc(repo)
    tests = test_count(repo)
    deps = dep_count(repo)
    remote_pr = len(git_lines(repo, "branch", "-r", "--list", "origin/pr/*"))
    local_sessions = len(git_lines(repo, "branch", "--list", "liminal/sess-*"))

    cluster4 = sum(count for day, count in daily.items() if day >= "2026-03-28")

    return {
        "generated": date.today().isoformat(),
        "scope": "archived github-commits.csv ∪ current git log --all (no prune)",
        "total_commits": total,
        "origin_main_commits": origin_main,
        "non_main_commits": non_main,
        "first_date": first,
        "last_date": last,
        "span_days": span,
        "active_days": len(active_dates),
        "active_rate_pct": round(len(active_dates) / span * 100, 1) if span > 0 else 0,
        "commits_per_active_day": round(total / len(active_dates), 1) if active_dates else 0,
        "commits_per_day_span": round(total / span, 1) if span > 0 else 0,
        "peak_day": peak_day,
        "peak_day_commits": peak_commits,
        "daily_commits": dict(sorted(daily.items())),
        "hourly_commits": {str(hour).zfill(2): hours.get(str(hour).zfill(2), 0) for hour in range(24)},
        "insertions": add,
        "deletions": delete,
        "net_lines": net,
        "files_tracked": origin_files,
        "tracked_ts_loc": loc,
        "tracked_ts_loc_label": f"{round(loc / 1000):.0f}K tracked TS LOC",
        "net_line_label": f"{round(net / 1000):.0f}K net line delta",
        "test_files": tests,
        "dependencies": deps,
        "commit_types": types,
        "simon_commits": simon,
        "sgdc_commits": sgdc,
        "pastorsimon1798_commits": pastor,
        "liminal_commits": liminal,
        "claude_commits": claude,
        "dependabot_commits": dependabot,
        "simon_all": simon + sgdc + pastor,
        "simon_all_pct": round((simon + sgdc + pastor) / total * 100, 1) if total > 0 else 0,
        "simon_liminal": simon + sgdc + pastor + liminal,
        "simon_liminal_pct": round((simon + sgdc + pastor + liminal) / total * 100, 1) if total > 0 else 0,
        "coauth_commits": coauth,
        "coauth_pct": round(coauth / total * 100, 1) if total > 0 else 0,
        "ai_involved_commits": ai_involved,
        "ai_involved_pct": round(ai_involved / total * 100, 1) if total > 0 else 0,
        "fix_ratio_pct": round(types["fix"] / total * 100, 1) if total > 0 else 0,
        "feat_fix_ratio": f"{types['feat'] / types['fix']:.2f}:1" if types["fix"] else "n/a",
        "remote_pr_branches": remote_pr,
        "local_session_branches": local_sessions,
        "cluster4_commits": cluster4,
        "cluster4_pct": round(cluster4 / total * 100, 1) if total > 0 else 0,
        "threshold_pre": sum(count for day, count in daily.items() if day < "2026-04-11"),
        "threshold_post": sum(count for day, count in daily.items() if day >= "2026-04-11"),
        "nocturnal_pct": round(
            sum(count for hour, count in hours.items() if int(hour) >= 21 or int(hour) <= 5) / total * 100,
            1,
        ) if total > 0 else 0,
        "after_midnight_pct": round(
            sum(count for hour, count in hours.items() if 0 <= int(hour) <= 5) / total * 100,
            1,
        ) if total > 0 else 0,
        "weekend_pct": round(
            sum(count for day, count in daily.items() if datetime.strptime(day, "%Y-%m-%d").weekday() >= 5) / total * 100,
            1,
        ) if total > 0 else 0,
    }


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def update_verified_stats(stats: dict[str, Any]) -> None:
    rows = "\n".join(f"| {day} | {count} |" for day, count in stats["daily_commits"].items())
    type_rows = "\n".join(
        f"| {kind} | {stats['commit_types'][kind]} | {round(stats['commit_types'][kind] / stats['total_commits'] * 100, 1)}% |"
        for kind in ["other", "feat", "fix", "docs", "test", "chore", "refactor", "merge", "security", "ci", "style", "perf"]
    )
    content = f"""# Verified Statistics — LIMINAL Project
Computed from git source on {stats['generated']}

## Source
- Repo: {DEFAULT_SOURCE_REPO}
- Git scope: `{stats['scope']}`
- Method: author-date for daily counts (`git log --all --format=\"%ad\" --date=short`)
- Tree metrics: `origin/main` after fetch/prune

## Core Numbers
| Metric | Value | Source |
|--------|-------|--------|
| Total commits (fetch-pruned all refs) | {stats['total_commits']:,} | git log --all --oneline |
| Total commits (origin/main) | {stats['origin_main_commits']:,} | git log origin/main --oneline |
| Non-main unique commits | {stats['non_main_commits']:,} | git log --all --not origin/main --oneline |
| Calendar span | {stats['span_days']} days ({stats['first_date']} – {stats['last_date']}) | git log --all --format=%ai |
| Active days | {stats['active_days']} | unique author-dates in git log |
| Active rate | {stats['active_rate_pct']}% | active/span |
| Commits per active day | {stats['commits_per_active_day']} | total/active |
| Commits per day (full span) | {stats['commits_per_day_span']} | total/span |
| Files tracked | {stats['files_tracked']:,} | git ls-tree -r --name-only origin/main |
| Tracked TS LOC | {stats['tracked_ts_loc']:,} | non-empty non-comment .ts/.tsx lines at origin/main |
| Total insertions | {stats['insertions']:,} | git numstat |
| Total deletions | {stats['deletions']:,} | git numstat |
| Net lines | {stats['net_lines']:,} | insertions - deletions |

## Author Breakdown (git --all)
| Author | Commits |
|--------|---------|
| Simon | {stats['simon_commits']:,} |
| Simon Gonzalez De Cruz | {stats['sgdc_commits']:,} |
| Pastorsimon1798 | {stats['pastorsimon1798_commits']:,} |
| Liminal | {stats['liminal_commits']:,} |
| Claude | {stats['claude_commits']:,} |
| dependabot[bot] | {stats['dependabot_commits']:,} |

### Aggregated Identities
| Category | Commits | Percentage |
|----------|---------|-----------|
| Simon (all identities) | {stats['simon_all']:,} | {stats['simon_all_pct']}% |
| Simon + Liminal | {stats['simon_liminal']:,} | {stats['simon_liminal_pct']}% |

## Commit Type Distribution
| Type | Count | Percentage |
|------|-------|-----------|
{type_rows}

## Co-Authorship
| Metric | Value |
|--------|-------|
| Co-Authored-By commits | {stats['coauth_commits']:,} ({stats['coauth_pct']}%) |
| AI-involved commits (co-authored + Liminal-authored + Claude-authored) | {stats['ai_involved_commits']:,} ({stats['ai_involved_pct']}%) |

## Peak Day
| Date | Commits |
|------|---------|
| {stats['peak_day']} | {stats['peak_day_commits']} |

## Daily Commits
| Date | Commits |
|------|---------|
{rows}

## Key Ratios
| Ratio | Value |
|-------|-------|
| Fix commit ratio | {stats['fix_ratio_pct']}% ({stats['commit_types']['fix']}/{stats['total_commits']}) |
| feat:fix ratio | {stats['feat_fix_ratio']} ({stats['commit_types']['feat']}/{stats['commit_types']['fix']}) |
| Co-author rate | {stats['coauth_pct']}% |
| AI-involved rate | {stats['ai_involved_pct']}% |
| Evening/night commits (21:00-05:59) | {stats['nocturnal_pct']}% |
| After midnight (00:00-05:59) | {stats['after_midnight_pct']}% |
| Weekend commits (Sat+Sun) | {stats['weekend_pct']}% |

## Branch Landscape
| Category | Count |
|----------|-------|
| Remote PR branches (origin/pr/*) | {stats['remote_pr_branches']} |
| Local session branches (liminal/sess-*) | {stats['local_session_branches']} |
"""
    VERIFIED_STATS.write_text(content)


def update_structured_files(stats: dict[str, Any]) -> None:
    project = json.loads(PROJECT_JSON.read_text())
    project["timeline"]["end_date"] = stats["last_date"]
    project["timeline"]["total_days"] = stats["span_days"]
    project["overrides"]["total_commits"] = stats["total_commits"]
    project["overrides"]["active_days"] = stats["active_days"]
    for counter in project.get("visualization", {}).get("counters", []):
        if counter.get("label") == "commits":
            counter["value"] = stats["total_commits"]
        elif counter.get("label") in {"Lines of Code", "Tracked LOC"}:
            counter["label"] = "Tracked TS LOC"
            counter["value"] = stats["tracked_ts_loc_label"].split()[0]
    write_json(PROJECT_JSON, project)

    metrics = json.loads((ROOT / "pipeline/config/metrics.json").read_text())
    values = {
        "total_commits": stats["total_commits"],
        "total_commits_main": stats["origin_main_commits"],
        "non_main_commits": stats["non_main_commits"],
        "span_days": stats["span_days"],
        "active_days": stats["active_days"],
        "active_rate_pct": stats["active_rate_pct"],
        "commits_per_active_day": stats["commits_per_active_day"],
        "commits_per_day_span": stats["commits_per_day_span"],
        "files_tracked": stats["files_tracked"],
        "total_insertions": stats["insertions"],
        "total_deletions": stats["deletions"],
        "net_lines": stats["net_lines"],
        "fix_ratio_pct": stats["fix_ratio_pct"],
        "feat_fix_ratio": stats["feat_fix_ratio"],
        "simon_commits": stats["simon_commits"],
        "liminal_commits": stats["liminal_commits"],
        "pastorsimon1798_commits": stats["pastorsimon1798_commits"],
        "sgdc_commits": stats["sgdc_commits"],
        "claude_commits": stats["claude_commits"],
        "dependabot_commits": stats["dependabot_commits"],
        "simon_all_pct": stats["simon_all_pct"],
        "simon_liminal_pct": stats["simon_liminal_pct"],
        "co_authored_commits": stats["coauth_commits"],
        "co_author_rate_pct": stats["coauth_pct"],
        "ai_involved_commits": stats["ai_involved_commits"],
        "ai_involved_pct": stats["ai_involved_pct"],
        "peak_day": stats["peak_day"],
        "peak_day_commits": stats["peak_day_commits"],
        "nocturnal_pct": stats["nocturnal_pct"],
        "after_midnight_pct": stats["after_midnight_pct"],
        "weekend_pct": stats["weekend_pct"],
        "remote_pr_branches": stats["remote_pr_branches"],
        "local_session_branches": stats["local_session_branches"],
        "daily_commits": stats["daily_commits"],
    }
    for name, value in {**stats["commit_types"], **values}.items():
        metric_name = f"{name}_commits" if name in {"feat", "fix", "docs", "test", "chore", "refactor", "security", "ci", "style", "perf", "merge", "other"} else name
        if metric_name in metrics:
            metrics[metric_name]["value"] = value
    write_json(ROOT / "pipeline/config/metrics.json", metrics)

    data = json.loads(DATA_JSON.read_text())
    tv = data["telemetry_visualizations"]
    meta = tv["meta"]
    meta.update(
        {
            "generated": stats["generated"],
            "source_scope": stats["scope"],
            "project": "Liminal",
            "total_commits": stats["total_commits"],
            "date_range": f"{stats['first_date']} to {stats['last_date']}",
            "lifespan_days": stats["span_days"],
            "active_days": stats["active_days"],
            "avg_commits_per_active_day": stats["commits_per_active_day"],
            "avg_commits_per_day_full_span": stats["commits_per_day_span"],
            "peak_day": stats["peak_day"],
            "peak_day_commits": stats["peak_day_commits"],
        }
    )
    ct = tv["charts"]["commit_timeline"]
    ct["data"] = stats["daily_commits"]
    ct["commit_types"]["data"] = stats["commit_types"]
    ct["file_growth"]["data"][stats["last_date"]] = stats["files_tracked"]
    ct["loc_growth"]["data"][stats["last_date"]] = stats["tracked_ts_loc"]
    ct["test_growth"]["data"][stats["last_date"]] = stats["test_files"]
    ct["dependency_growth"]["data"][stats["last_date"]] = stats["dependencies"]
    data["total_commits_by_repo"]["liminal"] = stats["total_commits"]
    data.setdefault("codebase", {})["total_commits"] = stats["total_commits"]
    data.setdefault("codebase", {})["lifespan"] = f"{stats['span_days']} days ({stats['first_date']} - {stats['last_date']})"
    data["cluster_dominance"] = {
        "cluster_4_pct": stats["cluster4_pct"],
        "cluster_4_commits": stats["cluster4_commits"],
        "period": f"Mar 28 - {datetime.strptime(stats['last_date'], '%Y-%m-%d').strftime('%b %-d')}",
        "narrative": f"Cluster 4 (Mar 28 - {stats['last_date']}) contains {stats['cluster4_commits']:,} of {stats['total_commits']:,} commits ({stats['cluster4_pct']}%). The story is sustained AI-orchestrated intensity after the early seed/build phases.",
    }
    data.setdefault("threshold_split", {})["pre_threshold_commits"] = stats["threshold_pre"]
    data.setdefault("threshold_split", {})["post_threshold_commits"] = stats["threshold_post"]

    write_json(DATA_JSON, data)
    DATA_JS.write_text("window.__EMBEDDED_DATA = " + json.dumps(data, separators=(",", ":"), ensure_ascii=False) + ";")
    write_canonical_metrics(stats)


def _count_sessions(data_dir: Path) -> int:
    """Count unique sessions from session JSONL files."""
    sessions_dir = data_dir / "sessions"
    if not sessions_dir.exists():
        # Fallback: count from raw-sessions.md
        sessions_file = data_dir / "raw-sessions.md"
        if sessions_file.exists():
            content = sessions_file.read_text(encoding="utf-8")
            return content.count("## Session ")
        return 0
    return sum(1 for f in sessions_dir.glob("*.jsonl") if f.stat().st_size > 0)


def _count_human_messages(data_dir: Path) -> int:
    """Count human messages from session data."""
    sessions_file = data_dir / "raw-sessions.md"
    if sessions_file.exists():
        content = sessions_file.read_text(encoding="utf-8")
        return content.count("**Human:**") + content.count("**User:**")
    return 0


def write_canonical_metrics(stats: dict[str, Any]) -> None:
    """Write browser and JSON canonical metrics consumed by derived outputs.

    NOTE: The following metrics require manual update from session analysis:
    - session_count: Run scripts/mine_conversations.py and count session files
    - human_messages: Parse session files for user message count
    - dogfood_tests: Run dogfood campaign and count test runs
    - dogfood_success_rate: Calculate from dogfood results
    """
    data_dir = ROOT / "projects/liminal/data"
    canonical = {
        "generated": stats["generated"],
        "source_scope": stats["scope"],
        "total_commits": stats["total_commits"],
        "origin_main_commits": stats["origin_main_commits"],
        "non_main_commits": stats["non_main_commits"],
        "span_days": stats["span_days"],
        "active_days": stats["active_days"],
        "active_rate_pct": stats["active_rate_pct"],
        "commits_per_active_day": stats["commits_per_active_day"],
        "commits_per_day_span": stats["commits_per_day_span"],
        "peak_day": stats["peak_day"],
        "peak_day_commits": stats["peak_day_commits"],
        "files_tracked": stats["files_tracked"],
        "tracked_ts_loc": stats["tracked_ts_loc"],
        "net_lines": stats["net_lines"],
        "cluster_4_commits": stats["cluster4_commits"],
        "cluster_4_pct": stats["cluster4_pct"],
        # Session analysis metrics - computed dynamically
        "session_count": _count_sessions(data_dir),
        "human_messages": _count_human_messages(data_dir),
        "dogfood_tests": 0,  # No dogfood data available
        "dogfood_success_rate": 0.0,  # No dogfood data available
    }
    metrics_json = ROOT / "projects/liminal/deliverables/canonical-metrics.json"
    metrics_js = ROOT / "projects/liminal/deliverables/canonical-metrics.js"
    write_json(metrics_json, canonical)
    metrics_js.write_text("window.CANONICAL_METRICS = " + json.dumps(canonical, separators=(",", ":"), ensure_ascii=False) + ";")


def update_text_surface(stats: dict[str, Any]) -> None:
    run([sys.executable, "scripts/sync/sync_derived_deliverables.py"])


def validate(skip_screenshots: bool) -> None:
    run([sys.executable, "pipeline/core/validate.py", "--strict"])
    run([sys.executable, "pipeline/core/run.py", "--validate"])
    run([sys.executable, "scripts/sync/audit_claims.py"])
    run(["node", "archaeology/validators/validate_html.cjs", "projects/liminal/deliverables/playbook.html", "--project-dir", "projects/liminal"])
    run([sys.executable, "-m", "archaeology.cli", "validate", "liminal"])
    run([sys.executable, "-m", "py_compile", "pipeline/core/validate.py", "pipeline/core/run.py", "scripts/sync/audit_claims.py", "scripts/data/regenerate_all.py", "scripts/data/capture_playbook.py", "scripts/sync/sync_derived_deliverables.py", "scripts/data/refresh_data.py", "archaeology/cli.py"])
    if not skip_screenshots:
        run([sys.executable, "scripts/data/capture_playbook.py"])


def mine_private_sessions(source_repo: Path) -> None:
    """Optionally refresh private/local conversation-derived datasets."""
    tasks = [
        [
            sys.executable,
            "scripts/data/mine_conversations.py",
            "claude",
            "--sessions-dir",
            str(Path("~/.claude/projects/-Users-simongonzalezdecruz-Desktop-OMC").expanduser()),
            "--prefix",
            "sessions",
        ],
        [
            sys.executable,
            "scripts/data/mine_conversations.py",
            "claude",
            "--sessions-dir",
            str(Path("~/.claude/projects/-Users-simongonzalezdecruz-workspaces-liminal").expanduser()),
            "--prefix",
            "liminal",
        ],
        [
            sys.executable,
            "scripts/data/mine_conversations.py",
            "chatgpt",
            "--input",
            str(Path("~/Desktop/MyStuff/Documents/ToReview/conversations.json").expanduser()),
        ],
    ]
    for cmd in tasks:
        try:
            run(cmd)
        except subprocess.CalledProcessError:
            print(f"Private mining step skipped/failed: {' '.join(cmd)}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch, recompute, refresh, validate, and recapture Liminal archaeology outputs.")
    parser.add_argument("--source-repo", type=Path, default=DEFAULT_SOURCE_REPO)
    parser.add_argument("--no-fetch", action="store_true", help="Skip git fetch --all --tags")
    parser.add_argument("--skip-screenshots", action="store_true")
    parser.add_argument("--skip-validate", action="store_true")
    parser.add_argument("--mine-private-sessions", action="store_true", help="Refresh private Claude/ChatGPT-derived data before recomputing reports")
    parser.add_argument(
        "--legacy-refresh-first",
        action="store_true",
        help="Run refresh_data.py first. Off by default because refresh_data.py only sees currently reachable git refs.",
    )
    args = parser.parse_args()

    if args.mine_private_sessions:
        mine_private_sessions(args.source_repo)

    stats = compute(args.source_repo, fetch=not args.no_fetch)
    print(f"Canonical scope: {stats['scope']}")
    print(f"Latest source: {stats['total_commits']:,} commits through {stats['last_date']} ({stats['span_days']} days)")

    if args.legacy_refresh_first:
        refresh_sections = "meta,commits,hourly,types,authors,files,loc,tests,deps,agents,derived,timeline,threshold,self_run,codebase,total_by_repo,agent_economics"
        run([sys.executable, "scripts/data/refresh_data.py", "--repo", str(args.source_repo), "--sections", refresh_sections])
    write_verified_stats(stats)
    update_structured_files(stats)
    update_text_surface(stats)

    if not args.skip_validate:
        validate(skip_screenshots=args.skip_screenshots)

    print("Regeneration complete.")
    return 0


def write_verified_stats(stats: dict[str, Any]) -> None:
    update_verified_stats(stats)


if __name__ == "__main__":
    sys.exit(main())
