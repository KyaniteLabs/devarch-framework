"""Behaviour tests for archaeology.era_mapper.

Every expected value is derived by hand from the rules in the module:
dates parse as ISO (%Y-%m-%d, %Y-%m) or "%b %d" against the inferred year;
ranges split on " - ", " – " or " to "; a single date spans one day; an end
before its start wraps to year+1; commits strings yield their first integer;
era_from_date is inclusive on both bounds; remap walks dicts/lists and only
rewrites an "era" when a date field maps it to a different valid era.
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

from archaeology.era_mapper import (
    EraDef,
    era_count,
    era_from_date,
    get_current_era_names,
    load_eras,
    remap_json_era_fields,
)


def write_eras(tmp_path: Path, payload: dict) -> Path:
    p = tmp_path / "commit-eras.json"
    p.write_text(json.dumps(payload))
    return p


# ---------------------------------------------------------------------------
# load_eras — parsing rules
# ---------------------------------------------------------------------------

class TestLoadEras:
    def test_iso_to_range(self, tmp_path):
        p = write_eras(tmp_path, {
            "first_commit_date": "2026-01-01",
            "eras": [
                {"id": 1, "name": "Dawn", "dates": "2026-01-01 to 2026-01-10", "commits": 40},
            ],
        })
        eras = load_eras(p)
        assert eras == [
            EraDef(id=1, name="Dawn", start=datetime(2026, 1, 1),
                   end=datetime(2026, 1, 10), commits=40)
        ]

    def test_single_date_spans_one_day(self, tmp_path):
        p = write_eras(tmp_path, {
            "first_commit_date": "2026-02-01",
            "eras": [
                {"id": 2, "name": "Solo", "dates": "2026-02-05", "commits": 1},
            ],
        })
        eras = load_eras(p)
        assert eras[0].start == datetime(2026, 2, 5)
        assert eras[0].end == datetime(2026, 2, 5)

    def test_dash_and_endash_separators(self, tmp_path):
        for dates, expected_end in (
            ("2026-03-01 - 2026-03-08", datetime(2026, 3, 8)),
            ("2026-03-01 – 2026-03-08", datetime(2026, 3, 8)),
        ):
            p = write_eras(tmp_path, {
                "first_commit_date": "2026-03-01",
                "eras": [{"id": 1, "name": "X", "dates": dates, "commits": 3}],
            })
            assert load_eras(p)[0].end == expected_end

    def test_month_day_format_uses_inferred_year(self, tmp_path):
        p = write_eras(tmp_path, {
            "first_commit_date": "2026-06-01",
            "eras": [
                {"id": 1, "name": "M", "dates": "Jun 1 - Jun 9", "commits": 7},
            ],
        })
        eras = load_eras(p)
        assert eras[0].start == datetime(2026, 6, 1)
        assert eras[0].end == datetime(2026, 6, 9)

    def test_year_falls_back_to_earliest_daily_key(self, tmp_path):
        p = write_eras(tmp_path, {
            "eras": [
                {
                    "id": 1, "name": "D", "dates": "Mar 4 - Mar 9", "commits": 2,
                    "daily": {"2026-03-04": 1, "2026-03-05": 1},
                },
            ],
        })
        eras = load_eras(p)
        assert eras[0].start == datetime(2026, 3, 4)

    def test_end_before_start_wraps_to_next_year(self, tmp_path):
        p = write_eras(tmp_path, {
            "first_commit_date": "2026-05-01",
            "eras": [
                {"id": 1, "name": "W", "dates": "Dec 28 - Jan 3", "commits": 5},
            ],
        })
        eras = load_eras(p)
        assert eras[0].start == datetime(2026, 12, 28)
        assert eras[0].end == datetime(2027, 1, 3)

    def test_commits_string_yields_first_integer(self, tmp_path):
        p = write_eras(tmp_path, {
            "first_commit_date": "2026-01-01",
            "eras": [
                {"id": 1, "name": "C", "dates": "2026-01-01 to 2026-01-02",
                 "commits": "12 commits"},
            ],
        })
        assert load_eras(p)[0].commits == 12

    def test_commits_string_without_digits_is_zero(self, tmp_path):
        p = write_eras(tmp_path, {
            "first_commit_date": "2026-01-01",
            "eras": [
                {"id": 1, "name": "C", "dates": "2026-01-01 to 2026-01-02",
                 "commits": "unknown"},
            ],
        })
        assert load_eras(p)[0].commits == 0

    def test_unparseable_dates_skip_the_era(self, tmp_path):
        p = write_eras(tmp_path, {
            "first_commit_date": "2026-01-01",
            "eras": [
                {"id": 1, "name": "Bad", "dates": "not a date at all", "commits": 1},
                {"id": 2, "name": "Good", "dates": "2026-01-01", "commits": 2},
            ],
        })
        eras = load_eras(p)
        assert [e.id for e in eras] == [2]

    def test_missing_file_is_empty(self, tmp_path):
        assert load_eras(tmp_path / "nope.json") == []


# ---------------------------------------------------------------------------
# era_from_date — inclusive bounds
# ---------------------------------------------------------------------------

THREE_ERAS = [
    EraDef(id=1, name="Foundation", start=datetime(2026, 1, 1),
           end=datetime(2026, 1, 10), commits=40),
    EraDef(id=2, name="Expansion", start=datetime(2026, 1, 11),
           end=datetime(2026, 1, 20), commits=35),
    EraDef(id=3, name="Consolidation", start=datetime(2026, 1, 21),
           end=datetime(2026, 1, 31), commits=27),
]


class TestEraFromDate:
    def test_interior_dates_map_to_their_era(self):
        assert era_from_date(THREE_ERAS, "2026-01-05") == 1
        assert era_from_date(THREE_ERAS, "2026-01-15") == 2
        assert era_from_date(THREE_ERAS, "2026-01-25") == 3

    def test_bounds_are_inclusive(self):
        assert era_from_date(THREE_ERAS, "2026-01-01") == 1
        assert era_from_date(THREE_ERAS, "2026-01-10") == 1
        assert era_from_date(THREE_ERAS, "2026-01-11") == 2
        assert era_from_date(THREE_ERAS, "2026-01-31") == 3

    def test_gaps_and_outside_return_none(self):
        assert era_from_date(THREE_ERAS, "2025-12-31") is None
        assert era_from_date(THREE_ERAS, "2026-02-01") is None

    def test_invalid_input_returns_none(self):
        assert era_from_date(THREE_ERAS, "") is None
        assert era_from_date(THREE_ERAS, "not-a-date") is None
        assert era_from_date(THREE_ERAS, None) is None

    def test_datetime_suffix_is_truncated_to_ten_chars(self):
        # "2026-01-05 14:33:12 +0000" parses via the first 10 chars.
        assert era_from_date(THREE_ERAS, "2026-01-05 14:33:12 +0000") == 1


# ---------------------------------------------------------------------------
# counts and names
# ---------------------------------------------------------------------------

class TestCountsAndNames:
    def test_era_count_is_len(self):
        assert era_count(THREE_ERAS) == 3
        assert era_count([]) == 0

    def test_current_era_names_is_the_name_set(self):
        assert get_current_era_names(THREE_ERAS) == {
            "Foundation", "Expansion", "Consolidation",
        }


# ---------------------------------------------------------------------------
# remap_json_era_fields — date is the only remap source
# ---------------------------------------------------------------------------

class TestRemapJsonEraFields:
    def test_wrong_era_is_remapped_from_its_date(self):
        data = {"events": [{"era": 3, "date": "2026-01-05", "label": "e1"}]}
        changed = remap_json_era_fields(data, THREE_ERAS)
        # 2026-01-05 lies in era 1; the reported tuple is (old, new, date).
        assert changed == [(3, 1, "2026-01-05")]
        assert data["events"][0]["era"] == 1

    def test_correct_era_is_left_alone(self):
        data = {"events": [{"era": 2, "date": "2026-01-15"}]}
        assert remap_json_era_fields(data, THREE_ERAS) == []
        assert data["events"][0]["era"] == 2

    def test_date_outside_every_era_is_left_alone(self):
        data = {"events": [{"era": 2, "date": "2027-06-01"}]}
        assert remap_json_era_fields(data, THREE_ERAS) == []
        assert data["events"][0]["era"] == 2

    def test_missing_date_leaves_the_era_field(self):
        data = {"events": [{"era": 9, "label": "no date"}]}
        assert remap_json_era_fields(data, THREE_ERAS) == []
        assert data["events"][0]["era"] == 9

    def test_date_field_priority_date_then_first_expression(self):
        data = {"row": {"era": 1, "date": "2026-01-15", "first_expression": "2026-01-05"}}
        changed = remap_json_era_fields(data, THREE_ERAS)
        # "date" wins: 2026-01-15 is era 2.
        assert changed == [(1, 2, "2026-01-15")]
        assert data["row"]["era"] == 2

    def test_first_expression_used_when_date_absent(self):
        data = {"row": {"era": 3, "first_expression": "2026-01-05"}}
        assert remap_json_era_fields(data, THREE_ERAS) == [(3, 1, "2026-01-05")]

    def test_estimated_hook_commit_used_as_last_resort(self):
        data = {"row": {"era": 1, "estimated_hook_commit": "2026-01-25"}}
        assert remap_json_era_fields(data, THREE_ERAS) == [(1, 3, "2026-01-25")]

    def test_nested_lists_are_walked(self):
        data = {"pages": [[{"era": 1, "date": "2026-01-15"}, {"era": 2, "date": "2026-01-25"}]]}
        changed = remap_json_era_fields(data, THREE_ERAS)
        assert changed == [(1, 2, "2026-01-15"), (2, 3, "2026-01-25")]
        assert data["pages"][0][0]["era"] == 2
        assert data["pages"][0][1]["era"] == 3

    def test_plain_dict_without_era_is_untouched(self):
        data = {"config": {"date": "2026-01-05", "name": "x"}}
        assert remap_json_era_fields(data, THREE_ERAS) == []
        assert data == {"config": {"date": "2026-01-05", "name": "x"}}


# ---------------------------------------------------------------------------
# round 2 — year inference and month-only dates
# ---------------------------------------------------------------------------

from archaeology.era_mapper import _infer_year


class TestInferYear:
    def test_first_commit_date_prefix_wins(self):
        assert _infer_year({"first_commit_date": "2024-06-15"}) == 2024

    def test_short_first_commit_date_ignored_for_daily_fallback(self):
        raw = {
            "first_commit_date": "ab",
            "eras": [{"daily": {"2023-02-02": 1}}],
        }
        assert _infer_year(raw) == 2023

    def test_daily_keys_use_the_earliest_sorted(self):
        raw = {"eras": [{"daily": {"2025-05-05": 1, "2022-01-01": 1, "2023-03-03": 1}}]}
        assert _infer_year(raw) == 2022

    def test_non_numeric_daily_keys_are_skipped(self):
        raw = {"eras": [{"daily": {"bad": 1, "2021-04-04": 1}}]}
        assert _infer_year(raw) == 2021

    def test_unparseable_everything_falls_back_to_current_year(self):
        from datetime import datetime
        assert _infer_year({}) == datetime.now().year


class TestMonthOnlyDates:
    def test_month_only_range(self, tmp_path):
        p = write_eras(tmp_path, {
            "first_commit_date": "2026-01-01",
            "eras": [
                {"id": 1, "name": "MO", "dates": "2026-03 to 2026-04", "commits": 4},
            ],
        })
        eras = load_eras(p)
        assert eras[0].start == datetime(2026, 3, 1)
        assert eras[0].end == datetime(2026, 4, 1)
