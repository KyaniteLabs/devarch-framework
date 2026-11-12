"""F14: the dashboard API honours the user's settings instead of falling back to DEFAULTS."""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parent.parent


def _load_api(name):
    spec = importlib.util.spec_from_file_location(name, PKG / "dashboard" / "plugin_api.py")
    api = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(api)
    return api


@pytest.fixture
def clean_modules(monkeypatch):
    target = (PKG / "__init__.py").resolve()
    for name, mod in list(sys.modules.items()):  # other test files import their own copies
        f = getattr(mod, "__file__", None)
        if name in ("ag4te", "hermes_plugins.ag4te", "plugins.ag4te", "_ag4te_private") or (
            f and Path(f).resolve() == target
        ):
            monkeypatch.delitem(sys.modules, name, raising=False)
    yield
    sys.modules.pop("_ag4te_private", None)


def _fake_host_config(monkeypatch, loader):
    pkg = types.ModuleType("hermes_cli")
    cfg = types.ModuleType("hermes_cli.config")
    cfg.load_config_readonly = loader
    pkg.config = cfg
    monkeypatch.setitem(sys.modules, "hermes_cli", pkg)
    monkeypatch.setitem(sys.modules, "hermes_cli.config", cfg)


def test_private_copy_reads_the_users_settings_from_the_host_config(
    tmp_path, monkeypatch, clean_modules
):
    _fake_host_config(
        monkeypatch,
        lambda: {
            "plugins": {
                "entries": {
                    "ag4te": {
                        "settings": {"repo_roots": str(tmp_path / "mine"), "timeout_seconds": 77}
                    }
                }
            }
        },
    )
    api = _load_api("ag4te_api_f14_a")
    p = api._plugin()
    assert [str(r) for r in p.repo_roots()] == [str((tmp_path / "mine").resolve())]
    assert p.snapshot_settings()["timeout_seconds"] == 77
    assert p.snapshot_settings()["repo_roots"] == str(tmp_path / "mine")


def test_unreadable_host_config_fails_loudly_not_silently_to_defaults(monkeypatch, clean_modules):
    from fastapi import HTTPException

    def boom():
        raise RuntimeError("config unreadable")

    _fake_host_config(monkeypatch, boom)
    api = _load_api("ag4te_api_f14_b")
    with pytest.raises(HTTPException) as exc:
        api._plugin()
    assert exc.value.status_code == 503


def test_registered_plugin_module_is_preferred_over_a_private_copy(monkeypatch, clean_modules):
    spec = importlib.util.spec_from_file_location("hermes_plugins.ag4te", PKG / "__init__.py")
    live = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(live)

    class Ctx:
        def get_config(self, key, default=None):
            return 41 if key == "timeout_seconds" else default

    live._ctx = Ctx()
    monkeypatch.setitem(sys.modules, "hermes_plugins.ag4te", live)
    api = _load_api("ag4te_api_f14_c")
    assert api._plugin() is live
    assert live.snapshot_settings()["timeout_seconds"] == 41
