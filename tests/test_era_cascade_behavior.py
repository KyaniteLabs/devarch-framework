"""Behaviour tests for archaeology.era_cascade.

Expectations derived by hand for a two-era canonical structure
(Dawn: 2026-01-01..10, Growth: 2026-01-11..20):

- project.json syncs era_count and trims era_colors to n entries, filling
  missing slots from the default palette (index 1 = #f87171);
- data.json era fields remap by date (era 9 on 2026-01-05 -> era 1) and
  data.js is regenerated as `const DATA = <json>;`;
- HTML gets CSS vars beyond the count comment-removed (--era-07),
  data-era-range upper bounds capped (1-9 -> 1-2), word counts rewritten
  (Fourteen Eras -> Two Eras) and embedded `"era": 9` remapped via the
  nearby date;
- markdown gets count words rewritten but old era NAMES are left in place
  (only the scanner reports them);
- the removal comment itself still contains "era-07", so the verification
  scan ends with exactly 2 stale refs: the comment and the old name.
"""

import json
from datetime import datetime
from pathlib import Path

from archaeology.era_cascade import cascade
from archaeology.era_mapper import EraDef

ERAS_JSON = {
    "first_commit_date": "2026-01-01",
    "eras": [
        {"id": 1, "name": "Dawn", "dates": "2026-01-01 to 2026-01-10", "commits": 10},
        {"id": 2, "name": "Growth", "dates": "2026-01-11 to 2026-01-20", "commits": 6},
    ],
}

REPORT_HTML = """<html><body>
--era-07: #abc;
<div data-era-range="1-9">Fourteen Eras</div>
<script>
const rows = [
  { "date": "2026-01-05", "era": 9 }
];
</script>
</body></html>
"""

NOTES_MD = "Sixteen Eras and The Crusade\n"


def build_project(tmp_path: Path, with_project_json: bool = True) -> Path:
    proj = tmp_path / "proj"
    (proj / "deliverables").mkdir(parents=True)
    (proj / "commit-eras.json").write_text(json.dumps(ERAS_JSON))
    if with_project_json:
        (proj / "project.json").write_text(json.dumps({
            "overrides": {"era_count": 99},
            "visualization": {"era_colors": {
                "era-01": "#111111", "era-99": "#222222",
            }},
        }))
    (proj / "deliverables" / "data.json").write_text(json.dumps({
        "events": [{"era": 9, "date": "2026-01-05", "label": "first"}],
    }))
    (proj / "deliverables" / "data.js").write_text("const DATA = {};\n")
    (proj / "deliverables" / "report.html").write_text(REPORT_HTML)
    (proj / "deliverables" / "notes.md").write_text(NOTES_MD)
    return proj


class TestCascadeFullRun:
    def test_every_counter_matches_the_hand_derivation(self, tmp_path):
        proj = build_project(tmp_path)
        result = cascade(proj, proj / "commit-eras.json")

        assert result.project_json_synced is True
        assert result.files_changed == 3          # project.json, report.html, notes.md
        assert result.era_fields_remapped == 2    # data.json + embedded html field
        assert result.css_vars_fixed == 1         # --era-07
        assert result.ranges_capped == 1          # 1-9 -> 1-2
        assert result.counts_fixed == 2           # Fourteen->Two (html), Sixteen->Two (md)
        assert result.stale_refs_remaining == 2   # removal comment + "The Crusade"
        assert result.files_scanned == 4          # data.json, data.js, report.html, notes.md

    def test_project_json_sync(self, tmp_path):
        proj = build_project(tmp_path)
        cascade(proj, proj / "commit-eras.json")
        pj = json.loads((proj / "project.json").read_text())
        assert pj["overrides"]["era_count"] == 2
        # Trimmed to the era count; the missing second slot is filled from the
        # default palette (index 1), the stale era-99 dropped.
        assert pj["visualization"]["era_colors"] == {
            "era-01": "#111111", "era-02": "#f87171",
        }

    def test_data_json_remapped_and_data_js_mirrored(self, tmp_path):
        proj = build_project(tmp_path)
        cascade(proj, proj / "commit-eras.json")
        data = json.loads((proj / "deliverables" / "data.json").read_text())
        # 2026-01-05 falls in era 1 (Dawn).
        assert data["events"][0]["era"] == 1
        expected_js = (
            "const DATA = " + json.dumps(data, indent=2) + ";\n"
        )
        assert (proj / "deliverables" / "data.js").read_text() == expected_js

    def test_html_fixes(self, tmp_path):
        proj = build_project(tmp_path)
        cascade(proj, proj / "commit-eras.json")
        html = (proj / "deliverables" / "report.html").read_text()
        assert "/* removed: era-07 */" in html
        assert '--era-07' not in html
        assert 'data-era-range="1-2"' in html
        assert "Two Eras" in html
        assert '"era": 1' in html

    def test_markdown_count_fixed_but_old_name_left(self, tmp_path):
        proj = build_project(tmp_path)
        cascade(proj, proj / "commit-eras.json")
        md = (proj / "deliverables" / "notes.md").read_text()
        assert "Two Eras" in md
        assert "The Crusade" in md


class TestCascadeDryRun:
    def test_no_files_change_on_disk(self, tmp_path):
        proj = build_project(tmp_path)
        before = {
            p: p.read_text()
            for p in [
                proj / "project.json",
                proj / "deliverables" / "data.json",
                proj / "deliverables" / "data.js",
                proj / "deliverables" / "report.html",
                proj / "deliverables" / "notes.md",
            ]
        }
        result = cascade(proj, proj / "commit-eras.json", dry_run=True)
        after = {p: p.read_text() for p in before}
        assert before == after
        # Counters still report the would-be work; only disk writes are skipped.
        assert result.era_fields_remapped == 2
        assert result.css_vars_fixed == 1
        assert result.ranges_capped == 1
        assert result.counts_fixed == 2
        assert result.files_changed == 0
        assert result.project_json_synced is False


class TestCascadeEdges:
    def test_empty_eras_file_returns_all_zero_result(self, tmp_path):
        proj = build_project(tmp_path)
        (proj / "commit-eras.json").write_text(json.dumps({"eras": []}))
        result = cascade(proj, proj / "commit-eras.json")
        assert result.files_changed == 0
        assert result.era_fields_remapped == 0
        assert result.stale_refs_remaining == 0

    def test_missing_project_json_still_cascades_deliverables(self, tmp_path):
        proj = build_project(tmp_path, with_project_json=False)
        result = cascade(proj, proj / "commit-eras.json")
        assert result.project_json_synced is False
        assert result.era_fields_remapped == 2
        data = json.loads((proj / "deliverables" / "data.json").read_text())
        assert data["events"][0]["era"] == 1

    def test_default_palette_cycles(self, tmp_path):
        # 12 eras force palette wrap-around; era-12 (index 11) reuses index 1.
        eras = {
            "first_commit_date": "2026-01-01",
            "eras": [
                {"id": i + 1, "name": f"E{i}",
                 "dates": f"2026-{(i // 20) + 1:02d}-{(i % 20) + 1:02d}",
                 "commits": 1}
                for i in range(12)
            ],
        }
        proj = tmp_path / "proj"
        (proj / "deliverables").mkdir(parents=True)
        (proj / "commit-eras.json").write_text(json.dumps(eras))
        (proj / "project.json").write_text("{}")
        cascade(proj, proj / "commit-eras.json")
        pj = json.loads((proj / "project.json").read_text())
        colors = pj["visualization"]["era_colors"]
        assert len(colors) == 12
        assert colors["era-01"] == "#4ade80"
        assert colors["era-12"] == "#f87171"  # palette[11 % 10] == palette[1]


# ---------------------------------------------------------------------------
# round 2 — literal tables and remaining fixer branches
# ---------------------------------------------------------------------------

from archaeology.era_cascade import (
    CascadeResult,
    _default_color,
    _fix_era_count_text,
    _fix_era_range,
)


class TestDefaultColorPalette:
    PALETTE = [
        "#4ade80", "#f87171", "#fb923c", "#60a5fa", "#a78bfa",
        "#34d399", "#fbbf24", "#f472b6", "#c084fc", "#9ca3af",
    ]

    def test_every_slot(self):
        for i, color in enumerate(self.PALETTE):
            assert _default_color(i) == color

    def test_wraps_after_ten(self):
        assert _default_color(10) == self.PALETTE[0]
        assert _default_color(11) == self.PALETTE[1]


class TestFixEraCountTextTable:
    def test_every_word_count_rewrites_to_target(self):
        words = {
            "One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5,
            "Six": 6, "Seven": 7, "Eight": 8, "Nine": 9, "Ten": 10,
            "Eleven": 11, "Twelve": 12, "Thirteen": 13, "Fourteen": 14,
            "Fifteen": 15, "Sixteen": 16,
        }
        for word, num in words.items():
            if num == 2:
                continue  # the target itself stays
            r = CascadeResult()
            out = _fix_era_count_text(f"seen {word} Eras here", 2, r)
            assert out == "seen Two Eras here", word
            assert r.counts_fixed == 1

    def test_numeric_count_above_target_rewrites_to_number(self):
        r = CascadeResult()
        out = _fix_era_count_text("span 10 Eras", 2, r)
        assert out == "span 2 Eras"
        assert r.counts_fixed == 1

    def test_numeric_count_below_target_is_left(self):
        r = CascadeResult()
        out = _fix_era_count_text("span 1 Eras", 2, r)
        assert out == "span 1 Eras"
        assert r.counts_fixed == 0

    def test_matching_word_is_left(self):
        r = CascadeResult()
        assert _fix_era_count_text("Two Eras", 2, r) == "Two Eras"
        assert r.counts_fixed == 0

    def test_arrow_lines_are_skipped(self):
        r = CascadeResult()
        out = _fix_era_count_text("Fourteen Eras -> Two Eras", 2, r)
        assert out == "Fourteen Eras -> Two Eras"
        assert r.counts_fixed == 0


class TestFixEraRange:
    def test_low_above_cap_resets_to_one(self):
        r = CascadeResult()
        out = _fix_era_range('data-era-range="5-9"', 2, r)
        assert out == 'data-era-range="1-2"'
        assert r.ranges_capped == 1

    def test_in_range_is_untouched(self):
        r = CascadeResult()
        out = _fix_era_range('data-era-range="1-2"', 2, r)
        assert out == 'data-era-range="1-2"'
        assert r.ranges_capped == 0

    def test_non_matching_attribute_is_untouched(self):
        r = CascadeResult()
        assert _fix_era_range('data-era-range="all"', 2, r) == 'data-era-range="all"'


class TestMarkdownSkipLines:
    def test_arrow_lines_are_not_rewritten(self, tmp_path):
        proj = build_project(tmp_path)
        (proj / "deliverables" / "skip.md").write_text(
            "Sixteen Eras -> Two Eras\nOriginal Claim: Sixteen Eras\n")
        cascade(proj, proj / "commit-eras.json")
        content = (proj / "deliverables" / "skip.md").read_text()
        assert content == "Sixteen Eras -> Two Eras\nOriginal Claim: Sixteen Eras\n"


class TestEmbeddedJsonWindow:
    def test_era_above_count_without_nearby_date_is_left(self, tmp_path):
        proj = build_project(tmp_path)
        html = (
            "<html><script>\n"
            "const rows = [\n"
            '  { "era": 7 }\n'
            "];\n"
            "</script></html>\n"
        )
        (proj / "deliverables" / "nodate.html").write_text(html)
        cascade(proj, proj / "commit-eras.json")
        out = (proj / "deliverables" / "nodate.html").read_text()
        assert '"era": 7' in out

    def test_era_in_range_is_untouched_even_next_to_a_date(self, tmp_path):
        proj = build_project(tmp_path)
        html = (
            "<html><script>\n"
            "const rows = [\n"
            '  { "date": "2026-01-05", "era": 2 }\n'
            "];\n"
            "</script></html>\n"
        )
        (proj / "deliverables" / "fine.html").write_text(html)
        cascade(proj, proj / "commit-eras.json")
        out = (proj / "deliverables" / "fine.html").read_text()
        assert '"era": 2' in out
