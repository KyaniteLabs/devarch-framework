"""F27: ag4te_dig answers briefly by default; the full JSON is opt-in."""

import importlib.util
import json
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("ag4te_f27_under_test", PKG / "__init__.py")
ag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ag)


def big_dig():
    return {
        "project": "demo",
        "commit_count": 900,
        "first": "2025-01-01",
        "last": "2026-01-01",
        "span_days": 365,
        "active_days": 200,
        "longest_streak": 9,
        "longest_gap": 30,
        "busiest_day": {"d": "2025-06-01", "n": 14},
        "kinds": ["feat", "fix"],
        "kind_totals": [500, 400],
        "clusters": [{"n": i, "label": "era " * 20} for i in range(20)],
        "signals": [{"type": "velocity", "detail": "upshift " * 30, "d": "2025-06-01"}] * 30,
        "authors": [{"name": f"Person {i}", "commits": i} for i in range(200)],
        "gaps": [{"from": "2025-02-01", "to": "2025-03-01"}] * 50,
    }


def setup(monkeypatch):
    monkeypatch.setattr(ag, "load_dig", lambda project, settings=None: big_dig())
    monkeypatch.setattr(ag, "validate_project", lambda p: p)
    monkeypatch.setattr(ag, "_on_gateway", lambda: False)


def test_default_reply_is_the_brief_and_small(monkeypatch):
    setup(monkeypatch)
    out = ag._tool({"project": "demo"})
    d = json.loads(out)
    assert set(d) - {"notice"} == {"summary"} and "900 commits" in d["summary"]
    assert len(out) < 1500
    assert out == ag._tool({"project": "demo", "detail": "brief"})


def test_full_detail_is_opt_in_and_unchanged(monkeypatch):
    setup(monkeypatch)
    full = json.loads(ag._tool({"project": "demo", "detail": "full"}))
    assert {"summary", "authors", "eras", "signals", "gaps", "commit_count"} <= set(full)
    assert len(ag._tool({"project": "demo", "detail": "full"})) > 10 * len(
        ag._tool({"project": "demo"})
    )


def test_unknown_detail_is_an_error(monkeypatch):
    setup(monkeypatch)
    assert "detail" in json.loads(ag._tool({"project": "demo", "detail": "everything"}))["error"]


def test_gateway_stays_summary_only_even_for_full(monkeypatch):
    setup(monkeypatch)
    monkeypatch.setattr(ag, "_on_gateway", lambda: True)
    assert set(json.loads(ag._tool({"project": "demo", "detail": "full"}))) - {"notice"} == {"summary"}


def test_schema_declares_detail():
    props = ag.TOOL_SCHEMA["parameters"]["properties"]
    assert props["detail"]["enum"] == ["brief", "full"]
