"""Behaviour tests for archaeology.era_scanner.

Every expected EraRef is derived by hand from the detection rules: era
numbers and CSS variables flag only when ABOVE the era count; the plain
"N eras" total flags only the known stale totals {10, 14, 15, 16}; the
word form flags any count word that disagrees with the era count; JSON
"era": N flags above the count or zero; old era names flag unless the
line is a mapping (arrow); day counts flag only span_days ± 1; per-era
commit claims flag when they disagree with the canonical EraDef; JS/HTML
era arrays flag oversized or non-current arrays at the array's start
line. project.json supplies the canonical metrics.
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

from archaeology.era_mapper import EraDef
from archaeology.era_scanner import scan_deliverables

ERAS = [
    EraDef(id=1, name="Foundation", start=datetime(2026, 1, 1),
           end=datetime(2026, 1, 10), commits=40),
    EraDef(id=2, name="Expansion", start=datetime(2026, 1, 11),
           end=datetime(2026, 1, 20), commits=35),
    EraDef(id=3, name="Consolidation", start=datetime(2026, 1, 21),
           end=datetime(2026, 1, 31), commits=27),
]
N = 3
CURRENT = "Consolidation, Expansion, Foundation"  # ", ".join(sorted(names))


def make_project(tmp_path: Path, files: dict, span_days: int | None = 30) -> Path:
    proj = tmp_path / "proj"
    (proj / "deliverables").mkdir(parents=True, exist_ok=True)
    for name, content in files.items():
        target = proj / "deliverables" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    if span_days is not None:
        (proj / "project.json").write_text(json.dumps({
            "total_commits": 102, "span_days": span_days,
            "active_days": 22, "era_count": N,
        }))
    return proj


def refs(result):
    return [(r.kind, r.old_value, r.expected, r.line) for r in result.refs]


# ---------------------------------------------------------------------------
# structural checks
# ---------------------------------------------------------------------------

class TestEraNumbers:
    def test_number_above_count_flags_with_remap_hint(self, tmp_path):
        proj = make_project(tmp_path, {"story.md": "We reached Era 5.\n"})
        r = scan_deliverables(proj, ERAS)
        assert refs(r) == [
            ("era_number", "Era 5", "Era 1-3 (remap by date)", 1),
        ]

    def test_number_at_or_below_count_is_clean(self, tmp_path):
        proj = make_project(tmp_path, {"story.md": "Era 3 then Era 1.\n"})
        assert scan_deliverables(proj, ERAS).refs == []

    def test_css_var_above_count_flags(self, tmp_path):
        proj = make_project(tmp_path, {"style.html": "--era-07: #fff;\n"})
        r = scan_deliverables(proj, ERAS)
        assert refs(r) == [
            ("era_css_var", "era-07", "era-01 through era-03", 1),
        ]

    def test_css_var_within_count_is_clean(self, tmp_path):
        proj = make_project(tmp_path, {"style.html": "--era-02: #fff;\n"})
        assert scan_deliverables(proj, ERAS).refs == []


class TestEraCounts:
    def test_known_stale_numeric_total_flags(self, tmp_path):
        proj = make_project(tmp_path, {"report.md": "The project spans 15 eras.\n"})
        r = scan_deliverables(proj, ERAS)
        assert refs(r) == [("era_count", "15 eras", "3 eras", 1)]

    def test_non_stale_numeric_total_passes_even_if_wrong(self, tmp_path):
        # Only {10, 14, 15, 16} are known stale totals; 7 is not flagged.
        proj = make_project(tmp_path, {"report.md": "spans 7 eras\n"})
        assert scan_deliverables(proj, ERAS).refs == []

    def test_word_total_disagreeing_flags_with_word_form(self, tmp_path):
        proj = make_project(tmp_path, {"report.md": "# Fourteen Eras\n"})
        r = scan_deliverables(proj, ERAS)
        assert refs(r) == [("era_count", "Fourteen Eras", "Three Eras", 1)]

    def test_word_total_matching_is_clean(self, tmp_path):
        proj = make_project(tmp_path, {"report.md": "# Three Eras\n"})
        assert scan_deliverables(proj, ERAS).refs == []

    def test_chapter_count_disagreeing_flags(self, tmp_path):
        proj = make_project(tmp_path, {"report.md": "5 chapters of work.\n"})
        r = scan_deliverables(proj, ERAS)
        assert refs(r) == [("era_count", "5 chapters", "3 (matches era count)", 1)]

    def test_across_count_disagreeing_flags(self, tmp_path):
        proj = make_project(tmp_path, {"report.md": "across 12 eras of work.\n"})
        r = scan_deliverables(proj, ERAS)
        assert refs(r) == [("era_count", "across 12 eras", "across 3 eras", 1)]

    def test_across_count_matching_is_clean(self, tmp_path):
        proj = make_project(tmp_path, {"report.md": "across 3 development eras.\n"})
        assert scan_deliverables(proj, ERAS).refs == []


class TestJsonEraFields:
    def test_era_above_count_flags(self, tmp_path):
        proj = make_project(tmp_path, {"data.json": '{"row": {"era": 7}}\n'})
        r = scan_deliverables(proj, ERAS)
        assert refs(r) == [
            ("era_json_field", '"era": 7', '"era": 1-3 (remap by date)', 1),
        ]

    def test_era_zero_flags(self, tmp_path):
        proj = make_project(tmp_path, {"data.json": '{"row": {"era": 0}}\n'})
        r = scan_deliverables(proj, ERAS)
        assert refs(r) == [
            ("era_json_field", '"era": 0', '"era": 1-3 (remap by date)', 1),
        ]

    def test_era_in_range_is_clean(self, tmp_path):
        proj = make_project(tmp_path, {"data.json": '{"row": {"era": 2}}\n'})
        assert scan_deliverables(proj, ERAS).refs == []


class TestOldEraNames:
    def test_known_old_name_flags_with_sorted_current_names(self, tmp_path):
        proj = make_project(tmp_path, {"blog.md": "Back in The Crusade.\n"})
        r = scan_deliverables(proj, ERAS)
        assert refs(r) == [
            ("era_name", "The Crusade", CURRENT, 1),
        ]

    def test_current_name_in_prose_is_clean(self, tmp_path):
        proj = make_project(tmp_path, {"blog.md": "The Expansion era.\n"})
        assert scan_deliverables(proj, ERAS).refs == []

    def test_mapping_lines_with_arrows_are_skipped(self, tmp_path):
        proj = make_project(tmp_path, {"map.md": "The Crusade -> Foundation\n"})
        assert scan_deliverables(proj, ERAS).refs == []


class TestHistoricalSkipLines:
    @pytest.mark.parametrize("line", [
        "Original Claim: The Crusade",
        "originally reported Era 9",
        "was 15 eras",
        "Corrected To Era 2",
    ])
    def test_annotation_lines_are_skipped(self, tmp_path, line):
        proj = make_project(tmp_path, {"history.md": line + "\n"})
        assert scan_deliverables(proj, ERAS).refs == []


# ---------------------------------------------------------------------------
# semantic drift checks
# ---------------------------------------------------------------------------

class TestSemanticDrift:
    def test_day_count_off_by_one_flags(self, tmp_path):
        proj = make_project(tmp_path, {"report.md": "a 31 day sprint.\n"}, span_days=30)
        r = scan_deliverables(proj, ERAS)
        assert refs(r) == [
            ("semantic_drift", "31 day", "30 days (from project.json)", 1),
        ]

    def test_day_count_off_by_one_below_flags(self, tmp_path):
        proj = make_project(tmp_path, {"report.md": "a 29-day sprint.\n"}, span_days=30)
        r = scan_deliverables(proj, ERAS)
        assert refs(r) == [
            ("semantic_drift", "29 day", "30 days (from project.json)", 1),
        ]

    def test_exact_day_count_is_clean(self, tmp_path):
        proj = make_project(tmp_path, {"report.md": "a 30-day sprint.\n"}, span_days=30)
        assert scan_deliverables(proj, ERAS).refs == []

    def test_day_count_far_off_is_not_flagged(self, tmp_path):
        # Only span_days ± 1 count as drift; 45 is out of scope.
        proj = make_project(tmp_path, {"report.md": "a 45-day sprint.\n"}, span_days=30)
        assert scan_deliverables(proj, ERAS).refs == []

    def test_no_project_json_disables_span_check(self, tmp_path):
        proj = make_project(tmp_path, {"report.md": "a 31 day sprint.\n"}, span_days=None)
        assert scan_deliverables(proj, ERAS).refs == []

    def test_old_cluster_commit_total_flags(self, tmp_path):
        proj = make_project(tmp_path, {"report.md": "about 1,050 commits total.\n"})
        r = scan_deliverables(proj, ERAS)
        assert refs(r) == [
            ("semantic_drift", "1,050 commits",
             "972 commits (Eras 3-7) or era-specific count", 1),
        ]

    def test_per_era_commit_mismatch_flags_with_canonical(self, tmp_path):
        proj = make_project(tmp_path, {"report.md": "Era 2: 99 commits.\n"})
        r = scan_deliverables(proj, ERAS)
        assert refs(r) == [
            ("semantic_drift", "Era 2: 99 commits", "Era 2: 35 commits", 1),
        ]

    def test_per_era_commit_match_is_clean(self, tmp_path):
        proj = make_project(tmp_path, {"report.md": "Era 2: 35 commits.\n"})
        assert scan_deliverables(proj, ERAS).refs == []

    def test_unknown_era_commit_claim_flags_only_the_era_number(self, tmp_path):
        # Era 9 is not in the canonical map, so the commit-count check passes,
        # but the structural "Era N" check still flags the out-of-range number.
        proj = make_project(tmp_path, {"report.md": "Era 9: 12 commits.\n"})
        r = scan_deliverables(proj, ERAS)
        assert refs(r) == [
            ("era_number", "Era 9", "Era 1-3 (remap by date)", 1),
        ]


# ---------------------------------------------------------------------------
# JS / HTML era arrays
# ---------------------------------------------------------------------------

class TestJsEraArrays:
    def test_oversized_number_array_flags_at_array_start(self, tmp_path):
        js = (
            "const modelTimeline = [\n"
            "  {era: 1, label: 'a'},\n"
            "  {era: 9, label: 'b'},\n"
            "];\n"
        )
        proj = make_project(tmp_path, {"timeline.js": js})
        r = scan_deliverables(proj, ERAS)
        assert refs(r) == [
            ("js_era_array",
             "array with era entries [1, 9] (2 entries, max=9)",
             "max 3 entries (stale: [9])", 1),
        ]

    def test_in_range_number_array_is_clean(self, tmp_path):
        js = (
            "const modelTimeline = [\n"
            "  {era: 1},\n"
            "  {era: 2},\n"
            "];\n"
        )
        proj = make_project(tmp_path, {"timeline.js": js})
        assert scan_deliverables(proj, ERAS).refs == []

    def test_non_current_name_array_flags(self, tmp_path):
        js = (
            "const eraProfiles = [\n"
            "  {era: 'Seed'},\n"
            "  {era: 'Sprout'},\n"
            "  {era: 'Bloom'},\n"
            "  {era: 'Wither'},\n"
            "];\n"
        )
        proj = make_project(tmp_path, {"profiles.html": js})
        r = scan_deliverables(proj, ERAS)
        assert refs(r) == [
            ("js_era_array",
             "array with 4 era profiles (expected 3), "
             "non-current names: ['Seed', 'Sprout', 'Bloom', 'Wither']",
             "3 entries with names: " + CURRENT, 1),
        ]


# ---------------------------------------------------------------------------
# scan-level behaviour
# ---------------------------------------------------------------------------

class TestScanResult:
    def test_counts_files_and_lines(self, tmp_path):
        proj = make_project(tmp_path, {
            "a.md": "one\ntwo\n",
            "b.html": "three\n",
            "notes.txt": "ignored suffix\n",
        })
        r = scan_deliverables(proj, ERAS)
        assert r.files_scanned == 2
        assert r.lines_scanned == 3
        assert r.has_findings is False

    def test_has_findings_true_when_refs(self, tmp_path):
        proj = make_project(tmp_path, {"a.md": "Era 5\n"})
        r = scan_deliverables(proj, ERAS)
        assert r.has_findings is True

    def test_missing_deliverables_dir_is_empty(self, tmp_path):
        proj = tmp_path / "empty"
        proj.mkdir()
        r = scan_deliverables(proj, ERAS)
        assert r.files_scanned == 0
        assert r.refs == []

    def test_historical_file_name_is_skipped(self, tmp_path):
        proj = make_project(tmp_path, {"ERA_UPDATE_SUMMARY.md": "Era 5 everywhere\n"})
        assert scan_deliverables(proj, ERAS).refs == []


# ---------------------------------------------------------------------------
# round 2 — literal tables and remaining branches
# ---------------------------------------------------------------------------

from archaeology.era_scanner import _number_word


class TestNumberWord:
    def test_every_supported_count(self):
        expected = {
            1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five",
            6: "Six", 7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten",
            11: "Eleven", 12: "Twelve", 13: "Thirteen", 14: "Fourteen",
            15: "Fifteen", 16: "Sixteen",
        }
        for n, word in expected.items():
            assert _number_word(n) == word

    def test_out_of_range_falls_back_to_str(self):
        assert _number_word(17) == "17"
        assert _number_word(0) == "0"


class TestKnownStaleTotals:
    def test_each_stale_total_flags(self, tmp_path):
        for stale in (10, 14, 15, 16):
            proj = make_project(tmp_path, {"r.md": f"spanned {stale} eras.\n"})
            refs(scan_deliverables(proj, ERAS))  # helper import guard
            r = scan_deliverables(proj, ERAS)
            assert [(x.kind, x.old_value) for x in r.refs] == [
                ("era_count", f"{stale} eras")
            ], stale

    def test_non_stale_numbers_are_clean(self, tmp_path):
        for fine in (11, 12, 13):
            proj = make_project(tmp_path, {"r.md": f"spanned {fine} eras.\n"})
            assert scan_deliverables(proj, ERAS).refs == [], fine


class TestWordTotals:
    def test_each_word_total_disagreeing_flags(self, tmp_path):
        for word in ("Ten", "Eleven", "Twelve", "Thirteen", "Fourteen",
                     "Fifteen", "Sixteen"):
            proj = make_project(tmp_path, {"r.md": f"# {word} Eras\n"})
            r = scan_deliverables(proj, ERAS)
            assert [(x.kind, x.old_value, x.expected) for x in r.refs] == [
                ("era_count", f"{word} Eras", "Three Eras")
            ], word

    def test_word_totals_below_ten_are_not_word_checked(self, tmp_path):
        # The word regex only alternates Ten..Sixteen; "Seven Eras" with a
        # 3-era structure is wrong but outside this check's vocabulary.
        proj = make_project(tmp_path, {"r.md": "# Seven Eras\n"})
        assert scan_deliverables(proj, ERAS).refs == []


class TestScannerEdges:
    def test_unparseable_project_json_disables_span_check(self, tmp_path):
        proj = tmp_path / "proj"
        (proj / "deliverables").mkdir(parents=True, exist_ok=True)
        (proj / "deliverables" / "r.md").write_text("a 31 day sprint.\n")
        (proj / "project.json").write_text("{not json")
        assert scan_deliverables(proj, ERAS).refs == []

    def test_css_files_are_not_scanned(self, tmp_path):
        proj = make_project(tmp_path, {"style.css": "Era 9 everywhere\n"})
        r = scan_deliverables(proj, ERAS)
        assert r.files_scanned == 0

    def test_two_arrays_only_the_oversized_one_flags(self, tmp_path):
        js = (
            "const ok = [\n  {era: 1},\n  {era: 2},\n];\n"
            "const stale = [\n  {era: 1},\n  {era: 8},\n];\n"
        )
        proj = make_project(tmp_path, {"t.js": js})
        r = scan_deliverables(proj, ERAS)
        assert refs(r) == [
            ("js_era_array",
             "array with era entries [1, 8] (2 entries, max=8)",
             "max 3 entries (stale: [8])", 5),
        ]

    def test_name_array_with_right_length_and_current_names_is_clean(self, tmp_path):
        js = (
            "const eraProfiles = [\n"
            "  {era: 'Foundation'},\n"
            "  {era: 'Expansion'},\n"
            "  {era: 'Consolidation'},\n"
            "];\n"
        )
        proj = make_project(tmp_path, {"p.html": js})
        assert scan_deliverables(proj, ERAS).refs == []
