"""A6, A7 and the F14 follow-up: typed busy error, schema descriptions, 503 on a broken host."""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parent.parent


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, PKG / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _client(api):
    fastapi = pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    app = fastapi.FastAPI()
    app.include_router(api.router)
    return TestClient(app)


def _stub_plugin(raises):
    class DigError(ValueError):
        pass

    class DigBusyError(DigError):
        pass

    def start_dig(*a, **k):
        raise raises(DigError, DigBusyError)

    return types.SimpleNamespace(DigError=DigError, DigBusyError=DigBusyError, start_dig=start_dig)


def test_status_comes_from_the_exception_type_not_its_words(monkeypatch):
    api = _load("ag4te_api_a6", "dashboard/plugin_api.py")
    c = _client(api)
    monkeypatch.setattr(api, "_plugin", lambda: _stub_plugin(lambda E, B: B("worded differently")))
    assert c.post("/dig", json={"repo": "x"}).status_code == 409
    monkeypatch.setattr(
        api, "_plugin", lambda: _stub_plugin(lambda E, B: E("a dig is already running"))
    )
    assert c.post("/dig", json={"repo": "x"}).status_code == 400


def test_the_plugin_raises_the_typed_busy_error():
    mod = _load("hermes_plugins.ag4te_a6", "__init__.py")
    assert issubclass(mod.DigBusyError, mod.DigError)


def test_every_tool_schema_property_has_a_description():
    mod = _load("hermes_plugins.ag4te_a7", "__init__.py")
    props = mod.TOOL_SCHEMA["parameters"]["properties"]
    assert props
    missing = [k for k, v in props.items() if not str(v.get("description") or "").strip()]
    assert not missing, f"properties without a description: {missing}"


def _fake_hermes_cli(monkeypatch, with_loader):
    pkg = types.ModuleType("hermes_cli")
    cfg = types.ModuleType("hermes_cli.config")
    if with_loader:
        cfg.load_config_readonly = lambda: {}
    pkg.config = cfg
    monkeypatch.setitem(sys.modules, "hermes_cli", pkg)
    monkeypatch.setitem(sys.modules, "hermes_cli.config", cfg)


def test_missing_loader_in_a_present_hermes_is_503_not_defaults(monkeypatch):
    from fastapi import HTTPException

    api = _load("ag4te_api_503a", "dashboard/plugin_api.py")
    _fake_hermes_cli(monkeypatch, with_loader=False)
    with pytest.raises(HTTPException) as exc:
        api._read_host_settings()
    assert exc.value.status_code == 503


def test_absent_hermes_still_means_defaults(monkeypatch):
    api = _load("ag4te_api_503b", "dashboard/plugin_api.py")
    monkeypatch.setitem(sys.modules, "hermes_cli", None)
    monkeypatch.delitem(sys.modules, "hermes_cli.config", raising=False)
    assert api._read_host_settings() == {}
