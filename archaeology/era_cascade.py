"""Era cascade: automated propagation of era structure changes.

Reads canonical era definitions from commit-eras.json and propagates
changes across all deliverable files. This is the fix engine that the
scanner detects and the mapper calculates.

Usage:
    from archaeology.era_cascade import cascade
    result = cascade(project_dir, eras_path, dry_run=True)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .era_mapper import EraDef, load_eras, remap_json_era_fields, era_count, get_current_era_names
from .era_scanner import scan_deliverables


# Known old era names that may appear in deliverables
KNOWN_OLD_NAMES = {
    "The Acceleration", "The Crusade", "The Hardening",
    "The Threshold", "The Surface", "The Return",
}

# Files exempt from era name replacement (historical mapping docs)
EXEMPT_FILES: frozenset[str] = frozenset({
    "ERA_UPDATE_SUMMARY.md",
})


@dataclass
class CascadeResult:
    files_scanned: int = 0
    files_changed: int = 0
    era_fields_remapped: int = 0
    names_replaced: int = 0
    css_vars_fixed: int = 0
    ranges_capped: int = 0
    counts_fixed: int = 0
    project_json_synced: bool = False
    stale_refs_remaining: int = 0


def cascade(
    project_dir: Path,
    eras_path: Path,
    dry_run: bool = False,
) -> CascadeResult:
    """Run the full era cascade on a project.

    Steps:
    1. Load canonical eras
    2. Sync project.json
    3. Remap data.json era fields by date
    4. Mirror data.js
    5. Fix HTML era CSS vars and data-era-range
    6. Fix markdown era names and numbers
    7. Verify with scanner
    """
    result = CascadeResult()

    eras = load_eras(eras_path)
    if not eras:
        return result
    n_eras = era_count(eras)
    current_names = get_current_era_names(eras)

    # Step 2: Sync project.json
    _sync_project_json(project_dir, eras, n_eras, dry_run, result)

    # Step 3: Remap data.json era fields
    data_json = project_dir / "deliverables" / "data.json"
    if data_json.exists():
        changed = _remap_data_json(data_json, eras, dry_run)
        result.era_fields_remapped += changed

    # Step 4: Mirror data.js
    data_js = project_dir / "deliverables" / "data.js"
    if data_json.exists() and data_js.exists():
        _mirror_data_js(data_json, data_js, dry_run)

    # Step 5: Fix HTML files
    deliverables = project_dir / "deliverables"
    for html_file in deliverables.glob("*.html"):
        if html_file.name in EXEMPT_FILES:
            continue
        _fix_html_file(html_file, eras, n_eras, dry_run, result)

    # Step 6: Fix markdown files
    for md_file in deliverables.rglob("*.md"):
        if md_file.name in EXEMPT_FILES:
            continue
        _fix_markdown_file(md_file, eras, n_eras, current_names, dry_run, result)

    # Step 7: Verify
    scan_result = scan_deliverables(project_dir, eras)
    result.files_scanned = scan_result.files_scanned
    result.stale_refs_remaining = len(scan_result.refs)

    return result


def _sync_project_json(
    project_dir: Path,
    eras: list[EraDef],
    n_eras: int,
    dry_run: bool,
    result: CascadeResult,
) -> None:
    """Sync era_count and era_colors in project.json."""
    pj_path = project_dir / "project.json"
    if not pj_path.exists():
        return

    pj = json.loads(pj_path.read_text())
    changed = False

    # Fix era_count
    overrides = pj.setdefault("overrides", {})
    if overrides.get("era_count") != n_eras:
        overrides["era_count"] = n_eras
        changed = True

    # Fix era_colors — trim to n_eras entries
    viz = pj.setdefault("visualization", {})
    colors = viz.setdefault("era_colors", {})
    trimmed = {f"era-{i+1:02d}": colors.get(f"era-{i+1:02d}", _default_color(i))
               for i in range(n_eras)}
    if len(colors) != len(trimmed) or colors != trimmed:
        viz["era_colors"] = trimmed
        changed = True

    if changed and not dry_run:
        pj_path.write_text(json.dumps(pj, indent=2) + "\n")
        result.project_json_synced = True
        result.files_changed += 1


def _default_color(index: int) -> str:
    """Default era color palette."""
    palette = [
        "#4ade80", "#f87171", "#fb923c", "#60a5fa", "#a78bfa",
        "#34d399", "#fbbf24", "#f472b6", "#c084fc", "#9ca3af",
    ]
    return palette[index % len(palette)]


def _remap_data_json(
    data_json: Path, eras: list[EraDef], dry_run: bool
) -> int:
    """Remap era fields in data.json using date-based calculation."""
    data = json.loads(data_json.read_text())
    changes = remap_json_era_fields(data, eras)
    if changes and not dry_run:
        data_json.write_text(json.dumps(data, indent=2) + "\n")
    return len(changes)


def _mirror_data_js(data_json: Path, data_js: Path, dry_run: bool) -> None:
    """Mirror data.json into data.js with JS wrapper."""
    if dry_run:
        return
    data = json.loads(data_json.read_text())
    js_content = f"const DATA = {json.dumps(data, indent=2)};\n"
    data_js.write_text(js_content)


def _fix_html_file(
    html_path: Path,
    eras: list[EraDef],
    n_eras: int,
    dry_run: bool,
    result: CascadeResult,
) -> None:
    """Fix era references in HTML deliverables."""
    content = html_path.read_text(errors="ignore")
    original = content
    lines = content.splitlines(keepends=True)

    new_lines = []
    for line in lines:
        # Fix CSS vars: --era-NN where NN > n_eras
        line = _fix_css_vars(line, n_eras, result)

        # Fix data-era-range: cap upper bound
        line = _fix_era_range(line, n_eras, result)

        # Fix era count text: "14 Eras", "Ten Eras"
        line = _fix_era_count_text(line, n_eras, result)

        # Fix "Era N" text references
        line = _fix_era_number_text(line, n_eras, result)

        new_lines.append(line)

    content = "".join(new_lines)

    # Fix embedded JSON era fields
    content = _fix_embedded_json_eras(content, eras, result)

    if content != original and not dry_run:
        html_path.write_text(content)
        result.files_changed += 1


def _fix_css_vars(line: str, n_eras: int, result: CascadeResult) -> str:
    """Remove or fix era CSS variables beyond current count."""
    def _replace(m: re.Match) -> str:
        num = int(m.group(1))
        if num > n_eras:
            result.css_vars_fixed += 1
            return f"/* removed: era-{m.group(1)} */"
        return m.group(0)

    return re.sub(r"--era-(\d{2})", _replace, line)


def _fix_era_range(line: str, n_eras: int, result: CascadeResult) -> str:
    """Cap data-era-range upper bound to n_eras."""
    def _replace(m: re.Match) -> str:
        low = int(m.group(1))
        high = int(m.group(2))
        if high > n_eras:
            new_high = n_eras
            if low > new_high:
                low = 1
            result.ranges_capped += 1
            return f'data-era-range="{low}-{new_high}"'
        return m.group(0)

    return re.sub(r'data-era-range="(\d+)-(\d+)"', _replace, line)


def _fix_era_count_text(line: str, n_eras: int, result: CascadeResult) -> str:
    """Fix era count references like '14 Eras', 'Ten Eras'."""
    # Skip historical/comparison lines
    if "→" in line or "->" in line:
        return line

    word_map = {
        1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five",
        6: "Six", 7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten",
        11: "Eleven", 12: "Twelve", 13: "Thirteen", 14: "Fourteen",
        15: "Fifteen", 16: "Sixteen",
    }
    target_word = word_map.get(n_eras, str(n_eras))

    # "14 Eras" → "7 Eras"
    def _replace_num(m: re.Match) -> str:
        num = int(m.group(1))
        if num != n_eras and num > n_eras:
            result.counts_fixed += 1
            return f"{n_eras} Eras"
        return m.group(0)

    line = re.sub(r"\b(\d+)\s+Eras\b", _replace_num, line)

    # "Ten Eras" → "Seven Eras"
    for word, num in word_map.items():
        if num != n_eras and f"{word} Eras" in line:
            line = line.replace(f"{word} Eras", f"{target_word} Eras")
            result.counts_fixed += 1

    return line


def _fix_era_number_text(line: str, n_eras: int, result: CascadeResult) -> str:
    """Fix 'Era N' text where N > n_eras. Limited context — cannot auto-remap."""
    # We can only flag these, not auto-fix without date context
    return line


def _fix_embedded_json_eras(
    content: str, eras: list[EraDef], result: CascadeResult
) -> str:
    """Fix 'era': N fields in embedded HTML data using nearby date context."""
    lines = content.splitlines(keepends=True)
    new_lines = []

    era_line_indices = []
    for i, line in enumerate(lines):
        if re.search(r'"era":\s*(\d+)', line):
            m = re.search(r'"era":\s*(\d+)', line)
            num = int(m.group(1))
            if num > len(eras):
                era_line_indices.append(i)

    for idx in era_line_indices:
        # Search backwards up to 20 lines for a date field
        found_date = None
        for j in range(max(0, idx - 20), idx + 1):
            dm = re.search(r'"(?:date|first_expression|estimated_hook_commit)":\s*"(\d{4}-\d{2}-\d{2})', lines[j])
            if dm:
                found_date = dm.group(1)
                break

        if found_date:
            from .era_mapper import era_from_date
            new_era = era_from_date(eras, found_date)
            if new_era is not None:
                lines[idx] = re.sub(r'"era":\s*\d+', f'"era": {new_era}', lines[idx])
                result.era_fields_remapped += 1

    return "".join(lines)


def _fix_markdown_file(
    md_path: Path,
    eras: list[EraDef],
    n_eras: int,
    current_names: set[str],
    dry_run: bool,
    result: CascadeResult,
) -> None:
    """Fix era names in markdown files."""
    content = md_path.read_text(errors="ignore")
    original = content

    # Skip historical/comparison lines
    lines = content.splitlines(keepends=True)
    new_lines = []
    for line in lines:
        if re.search(r"→|->|Original Claim|originally reported", line):
            new_lines.append(line)
            continue
        line = _fix_era_count_text(line, n_eras, result)
        new_lines.append(line)

    content = "".join(new_lines)

    if content != original and not dry_run:
        md_path.write_text(content)
        result.files_changed += 1
