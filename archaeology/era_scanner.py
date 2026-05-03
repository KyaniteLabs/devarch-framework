"""Stale era reference scanner for deliverable files.

Detects era numbers, names, CSS variables, count text, and semantic
drift (wrong canonical values, stale day counts, per-era commit mismatches)
that don't match the current era structure. Returns findings for audit
reporting and cascade fix decisions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .era_mapper import EraDef, get_current_era_names, era_count


# Files that legitimately contain historical era references (mapping docs)
HISTORICAL_FILES: frozenset[str] = frozenset({
    "ERA_UPDATE_SUMMARY.md",
})


def _load_canonical_metrics(project_dir: Path) -> dict:
    """Load canonical metrics from project.json for semantic drift detection."""
    import json
    pjson = project_dir / "project.json"
    if not pjson.exists():
        return {}
    try:
        raw = json.loads(pjson.read_text())
    except (json.JSONDecodeError, OSError):
        return {}
    return {
        "total_commits": raw.get("total_commits"),
        "span_days": raw.get("span_days"),
        "active_days": raw.get("active_days"),
        "era_count": raw.get("era_count"),
    }


@dataclass(frozen=True)
class EraRef:
    file: Path
    line: int
    kind: str       # "era_number" | "era_name" | "era_css_var" | "era_count" | "era_json_field"
    old_value: str
    expected: str   # what it should be, or "N/A" if unmappable


@dataclass
class ScanResult:
    refs: list[EraRef] = field(default_factory=list)
    files_scanned: int = 0
    lines_scanned: int = 0

    @property
    def has_findings(self) -> bool:
        return len(self.refs) > 0


def scan_deliverables(
    project_dir: Path, eras: list[EraDef]
) -> ScanResult:
    """Scan all deliverable files for stale era references."""
    deliverables_dir = project_dir / "deliverables"
    if not deliverables_dir.exists():
        return ScanResult()

    current_names = get_current_era_names(eras)
    n_eras = era_count(eras)
    metrics = _load_canonical_metrics(project_dir)
    result = ScanResult()

    for path in deliverables_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in {".md", ".html", ".json", ".js"}:
            continue
        if path.name in HISTORICAL_FILES:
            continue

        _scan_file(path, eras, current_names, n_eras, metrics, result)

    return result


def _scan_file(
    path: Path,
    eras: list[EraDef],
    current_names: set[str],
    n_eras: int,
    metrics: dict,
    result: ScanResult,
) -> None:
    """Scan a single file for stale era references and semantic drift."""
    result.files_scanned += 1
    try:
        lines = path.read_text(errors="ignore").splitlines()
    except OSError:
        return

    rel = path.relative_to(path.parents[2])  # relative to project dir
    is_historical = any(hf in str(rel) for hf in HISTORICAL_FILES)

    # Build per-era commit count map from canonical source
    era_commits = {e.id: e.commits for e in eras}

    for i, line in enumerate(lines, start=1):
        result.lines_scanned += 1

        # Skip historical/context lines
        if re.search(
            r"Original Claim|originally reported|was \d+ eras|Corrected To",
            line, re.I,
        ):
            continue

        # --- Structural checks (existing) ---

        # Check "Era N" where N > n_eras
        for m in re.finditer(r"\bEra\s+(\d+)\b", line):
            num = int(m.group(1))
            if num > n_eras:
                result.refs.append(EraRef(
                    file=path, line=i, kind="era_number",
                    old_value=f"Era {num}",
                    expected=f"Era 1-{n_eras} (remap by date)",
                ))

        # Check "era-NN" CSS variables where NN > n_eras
        for m in re.finditer(r"era-(\d{2})", line):
            num = int(m.group(1))
            if num > n_eras:
                result.refs.append(EraRef(
                    file=path, line=i, kind="era_css_var",
                    old_value=f"era-{m.group(1)}",
                    expected=f"era-01 through era-{n_eras:02d}",
                ))

        # Check "N eras" count text — only flag if clearly claiming to be the total
        # Known stale total counts from previous structures: 10, 14, 15, 16
        known_stale_totals = {10, 14, 15, 16}
        for m in re.finditer(r"\b(\d+)\s+eras\b", line, re.I):
            num = int(m.group(1))
            if num in known_stale_totals:
                result.refs.append(EraRef(
                    file=path, line=i, kind="era_count",
                    old_value=f"{num} eras",
                    expected=f"{n_eras} eras",
                ))

        # Check "Ten Eras" / "Fourteen Eras" style
        word_map = {
            "Ten": 10, "Eleven": 11, "Twelve": 12, "Thirteen": 13,
            "Fourteen": 14, "Fifteen": 15, "Sixteen": 16,
            "Seven": 7, "Eight": 8, "Nine": 9,
        }
        for m in re.finditer(r"\b(Ten|Eleven|Twelve|Thirteen|Fourteen|Fifteen|Sixteen)\s+Eras\b", line):
            num = word_map.get(m.group(1), 0)
            if num != n_eras:
                result.refs.append(EraRef(
                    file=path, line=i, kind="era_count",
                    old_value=f"{m.group(1)} Eras",
                    expected=f"{_number_word(n_eras)} Eras",
                ))

        # Check "era": N in JSON/JS where N > n_eras
        for m in re.finditer(r'"era":\s*(\d+)', line):
            num = int(m.group(1))
            if num > n_eras or num == 0:
                result.refs.append(EraRef(
                    file=path, line=i, kind="era_json_field",
                    old_value=f'"era": {num}',
                    expected=f'"era": 1-{n_eras} (remap by date)',
                ))

        # Check old era names (skip era names inside quotes that are
        # clearly part of a mapping table, sub-phase names, or blog titles)
        known_old_names = {
            "The Acceleration", "The Crusade", "The Hardening",
            "The Return",
        }
        for old_name in known_old_names:
            if old_name in line and old_name not in current_names:
                if "→" in line or "->" in line:
                    continue
                result.refs.append(EraRef(
                    file=path, line=i, kind="era_name",
                    old_value=old_name,
                    expected=", ".join(sorted(current_names)),
                ))

        # --- Semantic drift checks (new) ---

        # Note: THE_BIBLE, Plus Ultra, The Outer Loop are event/concept names,
        # NOT era names. They appear legitimately in narrative text and should
        # NOT be flagged. Only actual old era names (The Acceleration, The Crusade,
        # etc.) are flagged above in the known_old_names check.

        # Check "N chapters" / "N Chapters" where N != n_eras

        # Check "N chapters" / "N Chapters" where N != n_eras
        for m in re.finditer(r"\b(\d+)\s+[Cc]hapters?\b", line):
            num = int(m.group(1))
            if num != n_eras:
                result.refs.append(EraRef(
                    file=path, line=i, kind="era_count",
                    old_value=f"{num} chapters",
                    expected=f"{n_eras} (matches era count)",
                ))

        # Check "N-day development" / "N days" against canonical span_days
        canonical_span = metrics.get("span_days")
        if canonical_span:
            known_stale_spans = {canonical_span - 1, canonical_span + 1}
            for m in re.finditer(r"\b(\d+)[\s-]*day", line, re.I):
                num = int(m.group(1))
                if num in known_stale_spans and num != canonical_span:
                    result.refs.append(EraRef(
                        file=path, line=i, kind="semantic_drift",
                        old_value=f"{num} day",
                        expected=f"{canonical_span} days (from project.json)",
                    ))

        # Check "1,050 commits" / "1050 commits" (old Cluster 4 count)
        for m in re.finditer(r"\b1,?050\s+commits", line):
            result.refs.append(EraRef(
                file=path, line=i, kind="semantic_drift",
                old_value="1,050 commits",
                expected="972 commits (Eras 3-7) or era-specific count",
            ))

        # Check per-era commit count drift: only direct "Era N: X commits" patterns
        # Avoid matching combined counts like "Era 3-4: 691 commits" or sub-periods
        for m in re.finditer(r"\bEra\s+(\d+)\s*[:\(]\s*(\d[\d,]*)\s+commits", line, re.I):
            era_num = int(m.group(1))
            count_str = m.group(2).replace(",", "")
            try:
                count = int(count_str)
            except ValueError:
                continue
            if era_num in era_commits and count != era_commits[era_num]:
                result.refs.append(EraRef(
                    file=path, line=i, kind="semantic_drift",
                    old_value=f"Era {era_num}: {m.group(2)} commits",
                    expected=f"Era {era_num}: {era_commits[era_num]} commits",
                ))

        # Check "N development eras" / "across N eras" against canonical
        for m in re.finditer(r"across\s+(\d+)\s+(?:development\s+)?eras?\b", line, re.I):
            num = int(m.group(1))
            if num != n_eras:
                result.refs.append(EraRef(
                    file=path, line=i, kind="era_count",
                    old_value=f"across {num} eras",
                    expected=f"across {n_eras} eras",
                ))

    # Check JS/HTML script blocks for oversized era arrays
    if path.suffix in {".html", ".js"}:
        _scan_js_era_arrays(path, eras, current_names, n_eras, result)


def _number_word(n: int) -> str:
    """Convert a number to its English word form for era counts."""
    words = {
        1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five",
        6: "Six", 7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten",
        11: "Eleven", 12: "Twelve", 13: "Thirteen", 14: "Fourteen",
        15: "Fifteen", 16: "Sixteen",
    }
    return words.get(n, str(n))


def _scan_js_era_arrays(
    path: Path,
    eras: list[EraDef],
    current_names: set[str],
    n_eras: int,
    result: ScanResult,
) -> None:
    """Detect oversized or stale-named era arrays in JS/HTML script blocks.

    Catches patterns like:
      - const modelTimeline = [{era:1,...}, {era:2,...}, ... {era:12,...}]
      - const eraProfiles = [{era:'Seed',...}, {era:'Explosion',...}, ...]
    """
    try:
        content = path.read_text(errors="ignore")
    except OSError:
        return

    lines = content.splitlines()

    # Pattern 1: JS arrays with { era: N } where N > n_eras
    # Find array boundaries that contain era entries
    _check_era_number_arrays(path, lines, n_eras, result)

    # Pattern 2: JS arrays with {era:'Name'} using non-current era names
    _check_era_name_arrays(path, lines, current_names, n_eras, result)


def _check_era_number_arrays(
    path: Path, lines: list[str], n_eras: int, result: ScanResult
) -> None:
    """Find JS arrays containing { era: N } entries where N exceeds n_eras."""
    # Track array start lines and collect era numbers within them
    in_array = False
    array_start = 0
    era_numbers: list[int] = []
    brace_depth = 0

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()

        if not in_array:
            # Detect array start that will contain era entries
            # Look for = [...] or const xyz = [
            if re.search(r'=\s*\[', stripped) and not stripped.startswith('//'):
                in_array = True
                array_start = i
                era_numbers = []
                brace_depth = 0

        if in_array:
            # Collect era: N entries
            for m in re.finditer(r'\bera:\s*(\d+)', line):
                era_numbers.append(int(m.group(1)))

            # Track if array closes
            if ']' in stripped:
                # Check if this is the closing bracket (rough heuristic)
                open_brackets = stripped.count('[')
                close_brackets = stripped.count(']')
                if close_brackets > open_brackets:
                    in_array = False
                    # Evaluate collected era numbers
                    if era_numbers and max(era_numbers) > n_eras:
                        stale = [n for n in era_numbers if n > n_eras]
                        result.refs.append(EraRef(
                            file=path, line=array_start,
                            kind="js_era_array",
                            old_value=f"array with era entries {era_numbers} ({len(era_numbers)} entries, max={max(era_numbers)})",
                            expected=f"max {n_eras} entries (stale: {stale})",
                        ))


def _check_era_name_arrays(
    path: Path,
    lines: list[str],
    current_names: set[str],
    n_eras: int,
    result: ScanResult,
) -> None:
    """Find JS arrays with {era:'Name'} using names not in current eras."""
    in_array = False
    array_start = 0
    era_names: list[str] = []

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()

        if not in_array:
            if re.search(r'=\s*\[', stripped) and not stripped.startswith('//'):
                in_array = True
                array_start = i
                era_names = []

        if in_array:
            # Collect era:'Name' or era: 'Name' entries
            for m in re.finditer(r"\bera:\s*['\"]([^'\"]+)['\"]", line):
                era_names.append(m.group(1))

            if ']' in stripped:
                open_brackets = stripped.count('[')
                close_brackets = stripped.count(']')
                if close_brackets > open_brackets:
                    in_array = False
                    if era_names and len(era_names) > n_eras:
                        # Also check for non-current names
                        non_current = [n for n in era_names if n not in current_names]
                        if non_current or len(era_names) != n_eras:
                            desc = f"array with {len(era_names)} era profiles (expected {n_eras})"
                            if non_current:
                                desc += f", non-current names: {non_current}"
                            result.refs.append(EraRef(
                                file=path, line=array_start,
                                kind="js_era_array",
                                old_value=desc,
                                expected=f"{n_eras} entries with names: {', '.join(sorted(current_names))}",
                            ))
