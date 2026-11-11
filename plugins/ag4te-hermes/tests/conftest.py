"""Keep gateway startup and its install side effects out of plugin tests."""

import sys
from types import ModuleType

import pytest


@pytest.fixture(autouse=True)
def desktop_bridge(monkeypatch):
    events = ModuleType("hermes_cli.plugin_events")
    events.broadcast_plugin_event = lambda *args: None
    monkeypatch.setitem(sys.modules, "hermes_cli.plugin_events", events)
