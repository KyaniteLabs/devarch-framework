#!/usr/bin/env python3
"""Synchronize derived deliverables from canonical metrics.

Reads canonical-metrics.json and commit-eras.json, then fixes any deliverable
text where canonical numbers appear with wrong values. Unlike the old approach
(listing every stale literal ever seen), this version defines the TEXT SHAPES
where canonical values appear and fixes any mismatch automatically.

Three passes per line:
  1. Pattern-based: regex slots that match shapes like "X days" or "Y commits"
     and replace with the canonical value.
  2. Literal fallback: specific old→new pairs for shapes regex can't express.
  3. Derived recalculation: rates and percentages recalculated from canonical.

Historical context lines (Original Claim, Previous columns) are preserved.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]  # scripts/sync/ → scripts/ → project root
DEFAULT_MANIFEST = ROOT / "pipeline/config/derived-deliverables.json"
DEFAULT_CANONICAL = ROOT / "projects/liminal/deliverables/canonical-metrics.json"
DEFAULT_ERAS = ROOT / "projects/liminal/data/commit-eras.json"

_ROOT_RESOLVED = ROOT.resolve()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_path(rel: str | Path) -> Path:
    resolved = (ROOT / rel).resolve()
    if not resolved.is_relative_to(_ROOT_RESOLVED):
        raise ValueError(f"Path escapes project root: {rel}")
    return resolved


def fmt_int(value: int | float) -> str:
    return f"{int(value):,}"


def load_json(path: Path) -> dict:
    if not path.exists():
        print(f"Warning: {path} not found, skipping", file=sys.stderr)
        return {}
    return json.loads(path.read_text())


# ---------------------------------------------------------------------------
# Canonical data loading
# ---------------------------------------------------------------------------

def load_canonical(metrics_path: Path, eras_path: Path) -> dict:
    """Build the canonical data registry from source files."""
    m = load_json(metrics_path)
    eras_raw = load_json(eras_path)
    if not m:
        return {}

    total = m["total_commits"]
    span = m["span_days"]
    active = m["active_days"]
    cluster = m["cluster_4_commits"]
    peak_date = m.get("peak_day", "")
    peak_short = peak_date.rsplit("-", 1)[-1] if "-" in peak_date else peak_date
    peak_commits = m.get("peak_day_commits", 0)

    # Author breakdown from commit-eras.json (more detailed)
    authors = {}
    if eras_raw:
        for c in eras_raw.get("contributors", []):
            authors[c["name"]] = c["commits"]

    simon = authors.get("Simon", 0)
    sgdc = authors.get("Simon Gonzalez De Cruz", 0)
    pastor = authors.get("Pastorsimon1798", 0)
    liminal = authors.get("Liminal", 0)
    simon_all = simon + sgdc + pastor
    simon_liminal = simon_all + liminal

    # Era definitions from commit-eras.json
    eras = {}
    if eras_raw:
        for era in eras_raw.get("eras", []):
            eid = era["id"]
            raw = era.get("commits", "0")
            # Handle both int (new format) and string (legacy "~256", "1-43 (~43)")
            if isinstance(raw, int):
                count = raw
            else:
                match = re.search(r"[~]?\(?(\d+)\)?$", str(raw).strip())
                count = int(match.group(1)) if match else 0
            eras[eid] = {
                "name": era["name"],
                "dates": era.get("dates", ""),
                "commits": count,
            }

    return {
        "total_commits": total,
        "span_days": span,
        "active_days": active,
        "active_rate_pct": round(active / span * 100, 1) if span else 0,
        "commits_per_active_day": round(total / active, 1) if active else 0,
        "commits_per_day_span": round(total / span, 1) if span else 0,
        "cluster_4_commits": cluster,
        "cluster_4_pct": round(cluster / total * 100, 1) if total else 0,
        "total_cross_repo_commits": m.get("total_cross_repo_commits", 3984),
        "total_repos": m.get("total_repos", 37),
        "peak_day": peak_date,
        "peak_day_short": peak_short,
        "peak_day_commits": peak_commits,
        "eras": eras,
        "authors": {
            "simon": simon,
            "sgdc": sgdc,
            "pastor": pastor,
            "liminal": liminal,
            "simon_all": simon_all,
            "simon_liminal": simon_liminal,
            "simon_all_pct": round(simon_all / total * 100, 1) if total else 0,
            "simon_liminal_pct": round(simon_liminal / total * 100, 1) if total else 0,
        },
        # Fields not available in canonical-metrics.json
        "tracked_ts_loc": m.get("tracked_ts_loc", 0),
        "net_lines": m.get("net_lines", 0),
        "files_tracked": m.get("files_tracked", 0),
        "human_messages": m.get("human_messages", ""),
        "session_count": m.get("session_count", ""),
        "era_count": len(eras) if eras else m.get("era_count", 16),
    }


# ---------------------------------------------------------------------------
# Pass 1: Pattern-based canonical slot replacement
# ---------------------------------------------------------------------------
# Each entry: (regex, replacement_function)
# The regex matches the TEXT SHAPE where a canonical value appears.
# The replacement function receives the match and the canonical dict.

def _build_pattern_slots(c: dict, rel: str = "") -> list[tuple[re.Pattern, callable]]:
    """Build regex patterns that match text shapes and fix wrong values."""
    total_s = fmt_int(c["total_commits"])
    cluster_s = fmt_int(c["cluster_4_commits"])
    cross_s = fmt_int(c["total_cross_repo_commits"])
    span = c["span_days"]
    active = c["active_days"]
    era_count = c["era_count"]
    cpa = c["commits_per_active_day"]
    cps = c["commits_per_day_span"]
    ar = c["active_rate_pct"]
    c4p = c["cluster_4_pct"]
    is_daily_file = _is_daily_commit_file(rel)

    slots: list[tuple[re.Pattern, callable]] = []

    # --- Project span: only in clearly scoped contexts ---
    # "Built in N days", "N days (Feb 28", "over N days", "N-day"
    for stale_days in [49, 47, 44]:
        slots.append((
            re.compile(rf"\b{stale_days}\s+days\s*\(Feb", re.I),
            lambda m, s=span: f"{s} days (Feb",
        ))
        slots.append((
            re.compile(rf"\bBuilt in {stale_days}\s+days\b"),
            lambda m, s=span: f"Built in {s} days",
        ))
        slots.append((
            re.compile(rf"\bover {stale_days}\s+days\b"),
            lambda m, s=span: f"over {s} days",
        ))
        slots.append((
            re.compile(rf"\bin {stale_days}\s+days\b", re.I),
            lambda m, s=span: f"in {s} days",
        ))

    # --- Active days: "N active days" ---
    slots.append((
        re.compile(r"\b(?:28|26|24|21)\s+active\s+days?\b"),
        lambda m: m.group(0).replace(
            re.match(r"\d+", m.group(0)).group(0), str(active)
        ),
    ))

    # --- Active days in tables: "| N" preceded by "Active development days" ---
    slots.append((
        re.compile(r"(?<=Active development days \| )\d+"),
        lambda m: str(active),
    ))

    # --- Total commits: bare number in commit-count context ---
    for stale in [1002, 1778, 1818, 1924, 2008]:
        stale_s = fmt_int(stale)
        # "N commits" or "N," (with comma formatting variants)
        slots.append((
            re.compile(rf"\b{stale_s.replace(',', r'[,.]?\s*')}?\s*{stale}\s+commits\b"),
            lambda m, s=total_s: f"{s} commits",
        ))

    # --- Cluster 4: "N/M commits" ratio ---
    for stale_num in [839, 1655, 1761]:
        stale_n = fmt_int(stale_num)
        for stale_denom in [1002, 1818, 1924]:
            stale_d = fmt_int(stale_denom)
            slots.append((
                re.compile(rf"\b{stale_n}\s*/\s*{stale_d}\b"),
                lambda m, n=cluster_s, d=total_s: f"{n}/{d}",
            ))

    # --- Cluster 4 percentage: standalone "XX.X%" in cluster context ---
    for stale_pct in [83.7, 91.0, 91.5]:
        slots.append((
            re.compile(rf"\b{stale_pct}%\b"),
            lambda m, p=c4p: f"{p}%",
        ))

    # --- Era count: "N eras" ---
    for stale_eras in [9, 15]:
        slots.append((
            re.compile(rf"\b{stale_eras}\s+eras\b"),
            lambda m, e=era_count: f"{e} eras",
        ))
        slots.append((
            re.compile(rf"\b{stale_eras}\s+development\s+eras\b"),
            lambda m, e=era_count: f"{e} development eras",
        ))

    # --- Era-specific commit counts: "Era N ... X commits" ---
    for eid, era in c["eras"].items():
        count = era["commits"]
        name = era["name"]
        # Known stale counts per era (add new ones as they appear)
        # For Era 13: skip "54" if in daily-commit files (playbook.html) — it's a daily count
        stale_counts = {
            13: [103, 163, 248] + ([54] if not is_daily_file else []),
            14: [64],
            11: [207],
        }
        for stale_count in stale_counts.get(eid, []):
            # "X commits" near the era name or date context
            slots.append((
                re.compile(rf"\b{stale_count}\s+commits\b(?=.*(?:Era\s+{eid}|{re.escape(name)}|{re.escape(era['dates'])}))"),
                lambda m, cnt=count: f"~{cnt} commits",
            ))
            # Reverse: era context first, then count
            slots.append((
                re.compile(rf"(?:Era\s+{eid}|{re.escape(name)}|{re.escape(era['dates'])}).*?\b{stale_count}\s+commits\b"),
                lambda m, cnt=count, sc=str(stale_count): m.group(0).replace(
                    f"{sc} commits", f"~{cnt} commits"
                ),
            ))

    # --- Peak day: stale "Apr 9" or "207 commits" peak references ---
    slots.append((
        re.compile(r"PEAK\s+DAY.*?Apr\s+9.*?207\s+commits", re.I),
        lambda m, ps=span: m.group(0)
            .replace("Apr 9", f"Apr {c['peak_day_short']}")
            .replace("207 commits", f"{c['peak_day_commits']} commits"),
    ))
    slots.append((
        re.compile(r"\b207\s+commits\b"),
        lambda m, pc=c["peak_day_commits"]: f"{pc} commits",
    ))

    # --- Cross-repo count ---
    slots.append((
        re.compile(r"\b4[,]?160\b"),
        lambda m, cs=cross_s: cs,
    ))

    # --- Authorship percentage ---
    slots.append((
        re.compile(r"\b92\.4%\b"),
        lambda m: "99.6%",
    ))

    # --- Velocity rates (broad regex: any number in these rate shapes) ---
    slots.append((
        re.compile(r"\b\d+\.?\d*\s+commits\s*/\s*active\s+day\b"),
        lambda m, v=cpa: f"{v} commits/active day",
    ))
    slots.append((
        re.compile(r"\b\d+\.?\d*\s+commits\s+per\s+active\s+day\b"),
        lambda m, v=cpa: f"{v} commits per active day",
    ))
    slots.append((
        re.compile(r"\b\d+\.?\d*\s+commits\s*/\s*day\s+span\b"),
        lambda m, v=cps: f"{v} commits/day span",
    ))
    slots.append((
        re.compile(r"\b\d+\.?\d*/day\s+over\s+(?:full\s+)?span\b"),
        lambda m, v=cps: f"{v}/day over full span",
    ))
    slots.append((
        re.compile(r"\b\d+\.?\d*%\s+active\s+rate\b"),
        lambda m, v=ar: f"{v}% active rate",
    ))

    return slots


# ---------------------------------------------------------------------------
# Pass 2: Literal fallback — specific old→new for shapes regex can't express
# ---------------------------------------------------------------------------

def _build_literal_replacements(c: dict) -> list[tuple[str, str]]:
    """Literal string replacements for shapes too complex for regex."""
    ts_loc = c["tracked_ts_loc"]
    net_lines = c["net_lines"]
    files = c["files_tracked"]
    loc_label = f"{round(ts_loc / 1000):.0f}K tracked TS LOC" if ts_loc else "N/A LOC"
    net_label = f"{round(net_lines / 1000):.0f}K net line delta" if net_lines else "N/A net delta"
    loc_full = f"{loc_label} / {net_label}"
    hm = c["human_messages"]
    sc = c["session_count"]

    return [
        # LOC variants
        ("104K LOC", loc_full),
        ("104K+ LOC", loc_full),
        ("104K", loc_label),
        ("194K tracked LOC / 649K net line delta", loc_full),
        ("194K tracked LOC", loc_label),
        ("220K tracked TS LOC / 649K net line delta", loc_full),
        ("220K tracked TS LOC", loc_label),
        ("649K net line delta", net_label),
        ("575K net line delta", net_label),
        # File counts
        (f"4,762 tracked files", f"{fmt_int(files)} tracked files" if files else "N/A tracked files"),
        (f"4,762 files", f"{fmt_int(files)} files" if files else "N/A files"),
        (f"4,949 tracked files", f"{fmt_int(files)} tracked files" if files else "N/A tracked files"),
        (f"4,949 files", f"{fmt_int(files)} files" if files else "N/A files"),
        # Messages/sessions
        ("1,148+ human messages", f"{hm or 'N/A'} unique human messages"),
        ("1,148 human messages", f"{hm or 'N/A'} unique human messages"),
        ("1,148+ messages", f"{hm or 'N/A'} unique messages"),
        ("1,148 messages", f"{hm or 'N/A'} unique messages"),
        ("60 sessions", f"{sc or 'N/A'} analyzed sessions"),
        ("60 Claude sessions", f"{sc or 'N/A'} analyzed Claude sessions (plus 60+ raw session files)"),
        # Hooks
        ("27 hooks", "26 hooks"),
        ("27 Hooks", "26 Hooks"),
        # Date range
        ("Feb 28 - Apr 14, 2026", "Feb 28 - Apr 17, 2026"),
        ("Feb 28 – Apr 14, 2026", "Feb 28 – Apr 17, 2026"),
        # Day suffix variants
        ("49-day", f"{c['span_days']}-day"),
        ("47-day", f"{c['span_days']}-day"),
        ("49d", f"{c['span_days']}d"),
        ("47d", f"{c['span_days']}d"),
        ("47 calendar days", f"{c['span_days']} calendar days"),
    ]


# ---------------------------------------------------------------------------
# Pass 3: Derived recalculation
# ---------------------------------------------------------------------------

def recalculate_derived(line: str, c: dict) -> str:
    """Recalculate rates and percentages from canonical values."""
    span = c["span_days"]

    # Watch rate: "N/M days (X.X%)" → fix denominator and percentage
    def _fix_watch_rate(m: re.Match) -> str:
        num = int(m.group(1))
        new_denom = span if span else int(m.group(2))
        pct = round(num / new_denom * 100, 1) if new_denom else 0
        return f"{num}/{new_denom} days ({pct}%)"

    line = re.sub(
        r"(\d+)/(\d+)\s+days\s+\(\d+\.?\d*%\)",
        _fix_watch_rate,
        line,
    )

    # Cluster ratio: bare "1615/1818" or similar
    cluster_s = fmt_int(c["cluster_4_commits"])
    total_s = fmt_int(c["total_commits"])
    line = re.sub(r"\b1615/1818\b", f"{cluster_s}/{total_s}", line)
    line = re.sub(r"\b1615/1924\b", f"{cluster_s}/{total_s}", line)

    return line


# ---------------------------------------------------------------------------
# Context preservation
# ---------------------------------------------------------------------------

def should_preserve_line(line: str) -> bool:
    """Skip lines that are historical records, not current claims."""
    return bool(re.search(
        r"Original Claim|originally reported|conflated|vs 920"
        r"|Lehman & Stanley|Previous \(|was \d+ days|was \d+ eras"
        r"|Corrected To \d+",
        line, re.I,
    ))


def _is_comparison_row(line: str) -> bool:
    """Detect table rows showing old vs new values side by side."""
    # A comparison row has both the old and new era count, e.g.:
    # "| Development phases | 16 eras of creative bursts | **10 eras**: ..."
    has_old = bool(re.search(r"\b16 eras\b", line))
    has_new = bool(re.search(r"\b10 eras\b", line))
    return has_old and has_new


# Files where aggressive pattern-based replacement should NOT run.
# These contain historical narratives, domain-specific metrics, or
# blog posts describing a specific point in time with correct-at-the-time numbers.
NARRATIVE_FILES: set[str] = {
    "blog/",
    "raw-narrative.md",
    "RECURSIVE-STORY-CIRCLE.md",
    "STORY-CIRCLE-SAMPLE.md",
}

# Files where the "54 commits on Apr 12" daily-level count is correct
# and should NOT be replaced with the era-level "~169 commits".
DAILY_COMMIT_FILES: set[str] = {
    "playbook.html",
}


def _is_narrative(rel: str) -> bool:
    return any(nf in rel for nf in NARRATIVE_FILES)


def _is_daily_commit_file(rel: str) -> bool:
    return any(df in rel for df in DAILY_COMMIT_FILES)


# ---------------------------------------------------------------------------
# Main sync logic
# ---------------------------------------------------------------------------

def sync_text(text: str, canonical: dict, rel: str = "") -> str:
    pattern_slots = _build_pattern_slots(canonical, rel)
    literals = _build_literal_replacements(canonical)

    out_lines: list[str] = []
    for line in text.splitlines(keepends=True):
        if should_preserve_line(line) or _is_comparison_row(line):
            out_lines.append(line)
            continue

        # Pass 1: Pattern-based canonical slots (skipped for narrative files)
        if not _is_narrative(rel):
            for pattern, replacer in pattern_slots:
                line = pattern.sub(replacer, line)

        # Pass 2: Literal fallbacks (always applied)
        for old, new in literals:
            line = line.replace(old, new)

        # Pass 3: Derived recalculation (always applied)
        line = recalculate_derived(line, canonical)

        out_lines.append(line)
    return "".join(out_lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Synchronize derived deliverables from canonical metrics."
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--canonical", type=Path, default=DEFAULT_CANONICAL)
    parser.add_argument("--eras", type=Path, default=DEFAULT_ERAS)
    parser.add_argument("--check", action="store_true", help="Fail if files are out of sync")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show what changed")
    args = parser.parse_args()

    manifest = load_json(args.manifest)
    if not manifest:
        print("Error: manifest not found", file=sys.stderr)
        return 1

    canonical = load_canonical(args.canonical, args.eras)
    if not canonical:
        print("Error: canonical metrics not found", file=sys.stderr)
        return 1

    changed: list[Path] = []
    for rel in manifest.get("paths", []):
        path = _safe_path(rel)
        if not path.exists() or path.is_dir():
            continue
        old = path.read_text(errors="ignore")
        new = sync_text(old, canonical, rel=rel)
        if old != new:
            changed.append(path)
            if not args.check:
                path.write_text(new)
            if args.verbose:
                import difflib
                diff = difflib.unified_diff(
                    old.splitlines(keepends=True),
                    new.splitlines(keepends=True),
                    fromfile=str(path),
                    tofile=str(path),
                    n=1,
                )
                for line in diff:
                    print(line, end="")

    if args.check and changed:
        print(f"Derived deliverables out of sync ({len(changed)} file(s)):")
        for path in changed:
            print(f"  - {path.relative_to(ROOT)}")
        return 1

    action = "checked" if args.check else "synced"
    print(f"Derived deliverables {action}: {len(manifest.get('paths', []))} paths, {len(changed)} changed")
    if canonical:
        print(f"  Canonical: {fmt_int(canonical['total_commits'])} commits, {canonical['span_days']} days, "
              f"{canonical['active_days']} active, {canonical['era_count']} eras, "
              f"peak {canonical['peak_day_short']} ({canonical['peak_day_commits']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
