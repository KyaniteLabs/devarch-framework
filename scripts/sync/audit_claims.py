#!/usr/bin/env python3
"""Audit high-risk published claims for stale archaeology metrics.

This is intentionally lightweight: it checks the current public/reporting
surface for literals that previously drifted out of sync with the canonical
metric spine. It does not scan raw historical audit inputs, where stale numbers
may be preserved as "original claim" evidence.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]  # scripts/sync/ → scripts/ → project root

CURRENT_SURFACE = [
    ROOT / "README.md",
    ROOT / "projects/demo-project/project.json",
    ROOT / "projects/demo-project/deliverables",
    ROOT / "pipeline/templates",
]


STALE_PATTERNS = [
    # ── Liminal commit counts (canonical-metrics.json) ──
    (re.compile(r"\b103 commits\b"), "stale Era 13 count; canonical commit-eras.json says ~169"),
    (re.compile(r"\b207 commits\b"), "stale peak-day count; canonical is 195 (Apr 3)"),
    (re.compile(r"\b182 commits\b"), "stale Apr 8 daily count; canonical daily data says 30"),
    (re.compile(r"\b4[,]?160\b"), "stale cross-repo commit count; canonical is 3,984"),
    # ── Liminal project span (canonical-metrics.json) ──
    (re.compile(r"\bPEAK DAY.*Apr 9\b", re.I), "stale peak day; canonical is Apr 3"),
    (re.compile(r"\b92\.4%\b"), "stale authorship %; canonical is 99.6% (Simon all identities)"),
    (re.compile(r"\b24 active days?\b", re.I), "stale active-day count; canonical is 40"),
    (re.compile(r"\b26 active days?\b", re.I), "stale active-day count; canonical is 40"),
    (re.compile(r"\b26/47\b"), "stale active/span ratio; canonical is 40/62"),
    # ── Old patterns (pre-reconciliation) ──
    (re.compile(r"\b2,?008\b"), "stale total commit count; canonical is 1,213"),
    (re.compile(r"\b1,?778\b"), "stale total commit count; canonical is 1,213"),
    (re.compile(r"\b64\.5%\b"), "stale dogfood success rate; canonical is 68.5%"),
    (re.compile(r"\b104K\b"), "ambiguous old LOC shorthand; use a defined LOC metric"),
    (re.compile(r"\b1615/1818\b|\b1,615 of 1,818\b|\b1,615 commits\b|\b1,655 commits\b"), "stale Cluster 4 numerator; canonical is 1,050/1,213"),
    (re.compile(r"\b4,762 tracked files\b"), "stale tracked file count"),
]


CONTEXTUAL_PATTERNS = [
    (
        re.compile(r"\b15 eras\b"),
        "stale era count; canonical commit-eras.json has 16 eras",
        re.compile(r"Previous|previous|before|was 15|old", re.I),
    ),
    (
        re.compile(r"\b49 days\b", re.I),
        "stale project span; canonical is 62 days",
        re.compile(r"Corrected To 49|Previous|previous|before|was 49|original|old", re.I),
    ),
    (
        re.compile(r"\b47 days\b", re.I),
        "stale project span; canonical is 62 days",
        re.compile(r"Previous|previous|before|was 47|original|old", re.I),
    ),
    (
        re.compile(r"\b44[- ]days?\b", re.I),
        "stale project span; canonical is 62 days",
        re.compile(r"Previous|previous|before|original|old", re.I),
    ),
    (
        re.compile(r"\b1,?148\+?\s+(?:human\s+)?messages\b", re.I),
        "ambiguous message count; canonical analyzed set is 920 unique human messages",
        re.compile(r"Original Claim|originally reported|stale|discrepanc|inflated|vs 920", re.I),
    ),
    (
        re.compile(r"\b60\s+unique sessions\b", re.I),
        "ambiguous session count; canonical analyzed set is 58 unique sessions",
        re.compile(r"raw|archive|session files|60\+|original", re.I),
    ),
    (
        re.compile(r"\b60\s+(?:Claude\s+)?sessions\b", re.I),
        "ambiguous session count; canonical analyzed set is 58 unique sessions",
        re.compile(r"raw|archive|session files|60\+|original", re.I),
    ),
]


def iter_files(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    for path in paths:
        if path.is_dir():
            out.extend(
                p
                for p in path.rglob("*")
            if p.is_file() and p.suffix.lower() in {".md", ".html", ".json", ".js", ".j2"}
            )
        elif path.exists():
            out.append(path)
    return sorted(set(out))


def audit_file(path: Path) -> list[str]:
    issues: list[str] = []
    try:
        lines = path.read_text(errors="ignore").splitlines()
    except OSError as exc:
        return [f"{path}: could not read: {exc}"]

    for lineno, line in enumerate(lines, 1):
        if "Lehman & Stanley (2008)" in line:
            continue
        for pattern, message in STALE_PATTERNS:
            if pattern.search(line):
                issues.append(f"{path.relative_to(ROOT)}:{lineno}: {message}: {line.strip()[:180]}")
        for pattern, message, allowed_context in CONTEXTUAL_PATTERNS:
            if pattern.search(line) and not allowed_context.search(line):
                issues.append(f"{path.relative_to(ROOT)}:{lineno}: {message}: {line.strip()[:180]}")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit current deliverable claims for stale canonical metrics.")
    parser.add_argument("paths", nargs="*", type=Path, help="Optional files/directories to audit")
    args = parser.parse_args()

    targets = iter_files([p if p.is_absolute() else ROOT / p for p in args.paths] if args.paths else CURRENT_SURFACE)
    issues: list[str] = []
    for path in targets:
        issues.extend(audit_file(path))

    if issues:
        print(f"Claim audit failed: {len(issues)} issue(s)")
        for issue in issues:
            print(f"  - {issue}")
        return 1

    print(f"Claim audit passed: {len(targets)} file(s) checked")
    return 0


if __name__ == "__main__":
    sys.exit(main())
