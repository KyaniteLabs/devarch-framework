"""Agent tools and dig progress notify Desktop without broadcasting private data."""

import importlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

PKG = Path(__file__).resolve().parents[1]
HERMES_SOURCE = Path(
    os.environ.get(
        "AG4TE_HERMES_SOURCE",
        "/nonexistent-hermes-source",
    )
)


def load_plugin():
    spec = importlib.util.spec_from_file_location("ag4te_events_test", PKG / "__init__.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def pane(monkeypatch, tmp_path):
    calls = []
    events = ModuleType("hermes_cli.plugin_events")
    events.broadcast_plugin_event = lambda *args: calls.append(args)
    monkeypatch.setitem(sys.modules, "hermes_cli", ModuleType("hermes_cli"))
    monkeypatch.setitem(sys.modules, "hermes_cli.plugin_events", events)
    monkeypatch.setitem(sys.modules, "tui_gateway.server", ModuleType("tui_gateway.server"))
    ag = load_plugin()
    ag._ctx = SimpleNamespace(
        get_config=lambda key, _: str(tmp_path) if key == "data_dir" else None
    )
    ag._write_json(tmp_path / "projects/demo" / ag.DIG_FILE, {"project": "demo", "empty": True})
    return ag, calls


def test_read_tools_select_and_refresh_the_pane(pane):
    ag, calls = pane
    summary = json.loads(ag._tool({"project": "demo"}))["summary"]
    assert (
        summary == f"{ag.UNTRUSTED_OPEN}\nNo commits found in that dig.\n{ag.UNTRUSTED_CLOSE}"
    )  # repo text stays marked
    assert calls == [("ag4te", "dig.selected", {"project": "demo"})]
    ag._tool({})
    assert calls[-1] == ("ag4te", "projects.updated", {"count": 1})
    calls.clear()
    ag._tool({"project": "missing"})
    ag._tool({"project": "../private"})
    assert calls == []


@pytest.mark.parametrize("terminal", ["done", "failed", "cancelled"])
def test_status_events_whitelist_fields_after_persistence(pane, tmp_path, terminal):
    ag, calls = pane
    pdir = tmp_path / "projects/demo"
    ag._set_status(pdir, fresh=True, state="running", repo="/home/private/repo", label="secret")
    ag._set_status(pdir, state=terminal, warnings=["token=private"], error="private text")
    assert calls == [
        ("ag4te", "dig.updated", {"project": "demo", "state": "running"}),
        ("ag4te", "dig.updated", {"project": "demo", "state": terminal}),
    ]
    assert ag._read_json(pdir / ag.STATUS_FILE)["state"] == terminal
    with pytest.raises(ag.DigError):
        ag._set_status(pdir, state=terminal)
    assert len(calls) == 2


def test_slash_show_selects_and_status_keeps_json_with_setup_hint(pane):
    ag, calls = pane
    ag._slash("show demo")
    assert calls == [("ag4te", "dig.selected", {"project": "demo"})]
    assert "Capabilities -> Plugins" in json.loads(ag._slash("status demo"))["desktop"]


@pytest.mark.parametrize(
    "view",
    [
        "overview",
        "story",
        "strata",
        "rhythm",
        "churn",
        "practices",
        "turning-points",
        "people",
        "change-size",
        "files",
        "releases",
        "commits",
    ],
)
def test_show_sections(pane, view):
    ag, calls = pane
    out = ag._show_tool({"view": view, "item_id": "abc123"})
    assert view in out and "open and enabled" in out
    assert calls == [("ag4te", "view.set", {"view": view, "item_id": "abc123"})]


@pytest.mark.parametrize(
    "args",
    [
        None,
        [],
        {},
        {"view": []},
        {"view": "unknown"},
        {"view": "x" * 1000},
        {"view": "story", "item_id": ""},
        {"view": "story", "item_id": "x" * 129},
        {"view": "story", "item_id": 1},
        {"view": "story", "item_id": "/home/private"},
        {"view": "story", "item_id": "x\n"},
        {"view": "story", "text": "private"},
    ],
)
def test_show_rejects_bad_input_without_events(pane, args):
    ag, calls = pane
    assert "error" in ag._show_tool(args).lower()
    assert calls == []


def test_show_without_item_and_without_hermes(pane, monkeypatch):
    ag, calls = pane
    assert "story" in ag._show_tool({"view": "story"})
    assert calls == [("ag4te", "view.set", {"view": "story"})]
    monkeypatch.setitem(sys.modules, "hermes_cli", None)
    monkeypatch.setitem(sys.modules, "hermes_cli.plugin_events", None)
    offline = load_plugin()
    assert "open and enabled" in offline._show_tool({"view": "story"})
    assert "Usage:" in offline._slash("")


@pytest.mark.parametrize(
    "event,payload",
    [
        ("unknown", {}),
        ("view.set", {"view": "unknown"}),
        ("dig.selected", {"project": "demo", "repo": "/home/private"}),
        ("dig.updated", {"project": "demo", "state": "private text"}),
        ("projects.updated", {"count": -1}),
        ("projects.updated", {"count": True}),
    ],
)
def test_event_boundary_rejects_invalid_payloads(pane, event, payload):
    ag, calls = pane
    with pytest.raises(ag.DigError):
        ag._pane_event(event, payload)
    assert calls == []


@pytest.mark.skipif(not HERMES_SOURCE.is_dir(), reason="Hermes v0.23.0 source is not available")
def test_status_event_failure_isolated_with_real_hermes_bridge(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(HERMES_SOURCE))
    monkeypatch.delitem(sys.modules, "hermes_cli.plugin_events", raising=False)
    monkeypatch.delitem(sys.modules, "hermes_cli", raising=False)
    bridge = importlib.import_module("hermes_cli.plugin_events")
    assert Path(bridge.__file__).resolve().is_relative_to(HERMES_SOURCE.resolve())
    calls = []
    gateway = ModuleType("tui_gateway")
    gateway.__path__ = []
    server = ModuleType("tui_gateway.server")

    def fail_delivery(name, payload):
        calls.append((name, payload))
        raise RuntimeError("synthetic delivery failure")

    server._broadcast_global_event = fail_delivery
    monkeypatch.setitem(sys.modules, "tui_gateway", gateway)
    monkeypatch.setitem(sys.modules, "tui_gateway.server", server)

    ag = load_plugin()
    valid = tmp_path / "projects" / "demo"
    ag._set_status(valid, fresh=True, state="running")
    assert calls == [("plugin.ag4te.dig.updated", {"project": "demo", "state": "running"})]
    invalid = tmp_path / "projects" / "invalid name"
    result = ag._set_status(invalid, fresh=True, state="running")

    assert result["state"] == "running"
    assert ag._read_json(invalid / ag.STATUS_FILE)["state"] == "running"


@pytest.mark.skipif(not HERMES_SOURCE.is_dir(), reason="Hermes v0.23.0 source is not available")
def test_broadcast_does_not_import_gateway_bridge_outside_tui_process(monkeypatch):
    monkeypatch.syspath_prepend(str(HERMES_SOURCE))
    for name in ("hermes_cli.plugin_events", "hermes_cli", "tui_gateway.server", "tui_gateway"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    ag = load_plugin()
    before = sys.stdout

    ag._pane_event("projects.updated", {"count": 1})

    assert "hermes_cli.plugin_events" not in sys.modules
    assert sys.stdout is before


def test_registration_exposes_show_and_skill(pane):
    ag, _ = pane
    tools, skills = {}, {}
    ctx = SimpleNamespace(
        register_command=lambda *a, **k: None,
        register_tool=lambda **k: tools.update({k["name"]: k}),
        register_skill=lambda name, path, **k: skills.update({name: path}),
    )
    ag.register(ctx)
    assert tools["ag4te_show"]["handler"]({"view": "story"}).startswith("Asked")
    assert tools["ag4te_show"]["schema"]["parameters"]["properties"]["view"]["enum"] == list(
        ag.PANE_VIEWS
    )
    assert skills["ag4te"].is_file()


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
def test_desktop_events():
    result = subprocess.run(
        ["node", str(PKG / "tests/pane-events.test.cjs")],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
