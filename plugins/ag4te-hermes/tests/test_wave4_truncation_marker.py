"""A cut tool reply says how much was cut and how to get the rest (wave 4)."""
import json
import re

import pytest

from test_summary import ag


def _dig(monkeypatch, name, summary="ok"):
    monkeypatch.setattr(ag, "validate_project", lambda p: p)
    monkeypatch.setattr(ag, "load_dig", lambda p: {"authors": [{"name": name}], "kinds": []})
    monkeypatch.setattr(ag, "brief", lambda d: summary)
    monkeypatch.setattr(ag, "_on_gateway", lambda: False)


def test_a_path_of_a_few_hundred_characters_is_not_cut(monkeypatch):
    path = "src/" + "a/" * 120 + "file.py"  # 250 characters: a real deep path
    _dig(monkeypatch, path)
    out = json.loads(ag._tool({"project": "demo", "detail": "full"}))
    assert out["authors"][0]["name"] == path


def test_brief_cut_names_the_count_and_how_to_get_more(monkeypatch):
    long = "A" * 3000
    _dig(monkeypatch, "x", summary=long)
    out = json.loads(ag._tool({"project": "demo"}))
    body = out["summary"]
    m = re.search(r"…\((\d+) more chars; ask with detail: full\)", body)
    assert m, body
    kept = body.split(ag.UNTRUSTED_OPEN + "\n")[1].split("…(")[0]
    assert len(kept) + int(m.group(1)) == 3000
    assert len(body) < ag.TOOL_SUMMARY_CAP + 100


def test_full_cut_does_not_point_at_detail_full(monkeypatch):
    _dig(monkeypatch, "B" * 5000)
    name = json.loads(ag._tool({"project": "demo", "detail": "full"}))["authors"][0]["name"]
    m = re.search(r"…\((\d+) more chars cut\)$", name)
    assert m and "detail" not in name
    assert len(name) <= ag.TOOL_TEXT_CAP_FULL
    assert len(name) - len(m.group(0)) + int(m.group(1)) == 5000


@pytest.mark.parametrize("cap", [60, 500])
def test_marker_stays_inside_the_cap(cap):
    for n in (cap + 1, cap + 9, cap + 99, cap + 5000):
        s = ag._untrusted("z" * n, cap)
        assert len(s) <= cap and "more chars" in s
    assert ag._untrusted("z" * cap, cap) == "z" * cap


def test_two_long_keys_with_the_same_start_keep_both_values():
    a, b = "k" * 600 + "A", "k" * 600 + "B"
    out = ag._cap_strings({a: 1, b: 2})
    assert sorted(out.values()) == [1, 2]
    assert len(out) == 2 and all(len(k) <= ag.TOOL_TEXT_CAP for k in out)
    assert any(k.endswith("#2") for k in out)


def test_short_keys_are_untouched_and_a_third_collision_gets_its_own_number():
    assert ag._cap_strings({"kinds": 1, "paths": 2}) == {"kinds": 1, "paths": 2}
    keys = ["k" * 600 + c for c in "ABC"]
    out = ag._cap_strings({k: i for i, k in enumerate(keys)})
    assert sorted(out.values()) == [0, 1, 2] and len(set(out)) == 3


def test_cap_strings_collision_suffixing_is_linear_and_within_cap():
    import time
    cap = 40
    keys = ["k" * 100 + str(i) for i in range(3000)]
    t0 = time.perf_counter()
    out = ag._cap_strings({k: i for i, k in enumerate(keys)}, cap)
    elapsed = time.perf_counter() - t0
    assert len(out) == len(keys)  # no value dropped
    assert max(len(k) for k in out) <= cap
    assert elapsed < 2.0, elapsed  # quadratic suffix probing took far longer


def test_cap_strings_tiny_cap_never_exceeds_cap():
    out = ag._cap_strings({"a" * 50: 1, "a" * 51: 2, "a" * 52: 3}, 2)
    assert all(len(k) <= 2 for k in out)
