"""Focused regressions from the round-three review."""

import importlib
import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

PKG = Path(__file__).resolve().parents[1]
HERMES_SOURCE = Path(os.environ.get("AG4TE_HERMES_SOURCE") or "/nonexistent-hermes-source")


def load_plugin(name="ag4te_round3_test"):
    spec = importlib.util.spec_from_file_location(name, PKG / "__init__.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def load_api():
    spec = importlib.util.spec_from_file_location(
        "ag4te_round3_api_test", PKG / "dashboard" / "plugin_api.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def clear_plugin_modules(monkeypatch):
    target = (PKG / "__init__.py").resolve()
    for name, mod in tuple(sys.modules.items()):
        filename = getattr(mod, "__file__", None)
        if filename:
            try:
                if Path(filename).resolve() == target:
                    monkeypatch.delitem(sys.modules, name, raising=False)
            except OSError:
                pass


def test_same_host_lease_age_backstop_and_unlock(tmp_path):
    ag = load_plugin()
    ag._boot_id = lambda: "current-boot"
    ag._ctx = SimpleNamespace(
        get_config=lambda key, default=None: str(tmp_path) if key == "data_dir" else default
    )
    settings = {"data_dir": str(tmp_path)}
    lease = ag._lease_path(settings)
    lease.parent.mkdir(parents=True, exist_ok=True)
    lease.write_text(
        json.dumps(
            {
                "project": "stale",
                "pid": -1,
                "host": ag._host(),
                "since": time.time() - ag.MAX_LEASE_AGE_SECONDS - 1,
            }
        ),
        encoding="utf-8",
    )

    assert ag.read_lease(settings) is None
    lease.write_text(
        json.dumps(
            {
                "project": "old-boot",
                "pid": 1,
                "host": ag._host(),
                "boot_id": "previous-boot",
                "since": time.time(),
            }
        ),
        encoding="utf-8",
    )
    assert ag.read_lease(settings) is None
    lease.write_text(
        json.dumps(
            {
                "project": "stale",
                "pid": -1,
                "host": ag._host(),
                "boot_id": "current-boot",
                "since": time.time() - ag.MAX_LEASE_AGE_SECONDS - 1,
            }
        ),
        encoding="utf-8",
    )
    assert ag.read_lease(settings) is None
    assert "unlock" in ag.USAGE
    assert "stale" in ag._slash("unlock")
    assert not lease.exists()


def test_dashboard_reuses_profile_scoped_registered_core(monkeypatch):
    clear_plugin_modules(monkeypatch)
    core = load_plugin("hermes_plugins.ag4te__home_0123456789ab")
    core._ctx = SimpleNamespace(
        get_config=lambda key, default=None: "/synthetic/repos" if key == "repo_roots" else default
    )
    monkeypatch.setitem(sys.modules, "hermes_plugins.ag4te__home_0123456789ab", core)
    api = load_api()

    assert api._plugin() is core
    assert api._plugin()._cfg("repo_roots") == "/synthetic/repos"


def test_dashboard_prefers_registered_profile_after_private_fallback(monkeypatch):
    clear_plugin_modules(monkeypatch)
    api = load_api()
    private = api._load_private()
    sys.modules.pop("_ag4te_private", None)
    monkeypatch.setitem(sys.modules, "_ag4te_private", private)
    probes = []

    class UnrelatedModule(ModuleType):
        def __getattr__(self, name):
            if name == "start_dig":
                probes.append(name)
            raise AttributeError(name)

    unrelated = UnrelatedModule("unrelated_profile_probe")
    unrelated.__file__ = str(PKG / "__init__.py")
    monkeypatch.setitem(sys.modules, unrelated.__name__, unrelated)
    registered = load_plugin("hermes_plugins.ag4te__home_0123456789ab")
    registered._ctx = SimpleNamespace(get_config=lambda key, default=None: default)
    monkeypatch.setitem(sys.modules, registered.__name__, registered)

    assert api._plugin() is registered
    assert api._plugin() is registered
    assert probes == ["start_dig"]


@pytest.mark.parametrize("since", [float("nan"), float("inf"), float("-inf"), time.time() + 3600])
def test_invalid_or_future_foreign_lease_since_is_expired(tmp_path, since):
    ag = load_plugin()
    settings = {"data_dir": str(tmp_path)}
    lease = ag._lease_path(settings)
    lease.parent.mkdir(parents=True, exist_ok=True)
    lease.write_text(
        json.dumps({"project": "foreign", "pid": 1, "host": "other-host", "since": since}),
        encoding="utf-8",
    )

    assert ag.read_lease(settings) is None
    assert ag.unlock_lease(settings) is True


def test_old_same_host_live_process_without_proc_start_keeps_lease(tmp_path, monkeypatch):
    import subprocess

    ag = load_plugin("ag4te_lease_no_proc")
    settings = {"data_dir": str(tmp_path)}
    process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        monkeypatch.setattr(ag, "_proc_start", lambda pid: None)
        monkeypatch.setattr(ag, "_boot_id", lambda: None)
        lease = ag._lease_path(settings)
        lease.parent.mkdir(parents=True, exist_ok=True)
        lease.write_text(
            json.dumps(
                {
                    "project": "live",
                    "pid": process.pid,
                    "host": ag._host(),
                    "since": time.time() - ag.MAX_LEASE_AGE_SECONDS - 1,
                }
            ),
            encoding="utf-8",
        )

        assert ag.read_lease(settings) is not None
        with pytest.raises(ag.DigError, match="still running"):
            ag.unlock_lease(settings)
    finally:
        process.kill()
        process.wait()


def test_unlock_holds_jobs_lock_while_reading_lease(tmp_path, monkeypatch):
    ag = load_plugin("ag4te_unlock_lock")
    settings = {"data_dir": str(tmp_path)}
    lease = ag._lease_path(settings)
    lease.parent.mkdir(parents=True, exist_ok=True)
    lease.write_text("{}", encoding="utf-8")

    class LockProbe:
        held = False

        def __enter__(self):
            self.held = True

        def __exit__(self, *_):
            self.held = False

    lock = LockProbe()
    monkeypatch.setattr(ag, "_jobs_lock", lock)
    original = ag.read_lease
    observed = []

    def check_lock(settings=None, *, _locked=False):
        observed.append(_locked and lock.held)
        return original(settings, _locked=_locked)

    monkeypatch.setattr(ag, "read_lease", check_lock)
    assert ag.unlock_lease(settings) is True
    assert observed == [True]


@pytest.mark.skipif(
    not HERMES_SOURCE.is_dir() or importlib.util.find_spec("ruamel") is None,
    reason="Hermes v0.23.0 source or its YAML dependency is not available",
)
def test_private_dashboard_fallback_reads_real_hermes_plugin_settings(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(HERMES_SOURCE))
    hermes_home = tmp_path / ".hermes"
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.setenv("HERMES_CONTAINER", "1")
    config = hermes_home / "config.yaml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        "plugins:\n  entries:\n    ag4te:\n      settings:\n        repo_roots: /synthetic/configured-roots\n",
        encoding="utf-8",
    )
    clear_plugin_modules(monkeypatch)
    api = load_api()

    assert api._plugin()._cfg("repo_roots") == "/synthetic/configured-roots"


def test_gateway_tool_and_slash_show_hide_project_names(monkeypatch):
    ag = load_plugin()
    marker = "private-project-marker"
    ag._ctx = SimpleNamespace(session_surface=lambda: "telegram")
    ag.list_projects = lambda: [
        {"project": marker, "state": "done", "repo": "/synthetic/private", "has_dig": True}
    ]
    ag.load_dig = lambda project: {
        "project": project,
        "commit_count": 1,
        "first": "2026-01-01",
        "last": "2026-01-01",
        "active_days": 1,
        "span_days": 1,
        "merge_count": 0,
        "kinds": ["feat"],
        "kind_totals": [1],
        "longest_streak": 1,
        "longest_gap": 0,
        "busiest_day": {"d": "2026-01-01", "n": 1},
        "clusters": [],
        "signals": [],
        "people": {},
    }

    assert json.loads(ag._tool({})) == {"count": 1, "states": {"done": 1}, "notice": ag.UNTRUSTED_NOTICE}
    assert marker not in ag._slash(f"show {marker}")


def test_shipped_strata_images_have_no_caption_text():
    import struct
    import zlib

    def rows(path):
        data = path.read_bytes()
        offset, compressed, width, height = 8, bytearray(), 0, 0
        while offset < len(data):
            length = struct.unpack(">I", data[offset : offset + 4])[0]
            kind = data[offset + 4 : offset + 8]
            chunk = data[offset + 8 : offset + 8 + length]
            offset += length + 12
            if kind == b"IHDR":
                width, height, depth, color, _, _, interlace = struct.unpack(">IIBBBBB", chunk)
                assert (depth, color, interlace) == (8, 2, 0)
            elif kind == b"IDAT":
                compressed.extend(chunk)
        raw = zlib.decompress(compressed)
        stride, prior, result = width * 3, bytearray(width * 3), []
        offset = 0
        for _ in range(height):
            filt = raw[offset]
            scan = bytearray(raw[offset + 1 : offset + 1 + stride])
            offset += stride + 1
            for i, value in enumerate(scan):
                left = scan[i - 3] if i >= 3 else 0
                up = prior[i]
                upper_left = prior[i - 3] if i >= 3 else 0
                if filt == 1:
                    value += left
                elif filt == 2:
                    value += up
                elif filt == 3:
                    value += (left + up) // 2
                elif filt == 4:
                    p = left + up - upper_left
                    distances = (abs(p - left), abs(p - up), abs(p - upper_left))
                    value += (left, up, upper_left)[distances.index(min(distances))]
                scan[i] = value & 255
            assert filt in range(5)
            result.append(scan)
            prior = scan
        return width, height, result

    for filename, color in (
        ("strata-dark.png", (15, 18, 24)),
        ("strata-light.png", (244, 246, 250)),
    ):
        width, height, image_rows = rows(PKG / "docs" / filename)
        assert (width, height) == (1600, 1231)
        expected = bytes(color)
        for y in range(265, 300):
            scan = image_rows[y]
            assert all(scan[x * 3 : x * 3 + 3] == expected for x in range(25, 1000))


def test_lease_survives_its_age_while_the_same_process_still_holds_it(tmp_path):
    """A long dig keeps its lease past the age backstop; a reused PID does not."""
    import subprocess

    ag = load_plugin("ag4te_round3_pid_start")
    settings = {"data_dir": str(tmp_path)}
    ag._ctx = SimpleNamespace(
        get_config=lambda key, default=None: str(tmp_path) if key == "data_dir" else default
    )
    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        start = ag._proc_start(other.pid)
        if start is None:
            pytest.skip("this host exposes no process start time")
        lease = ag._lease_path(settings)
        lease.parent.mkdir(parents=True, exist_ok=True)
        body = {
            "project": "long",
            "pid": other.pid,
            "host": ag._host(),
            "boot_id": ag._boot_id(),
            "pid_start": start,
            "since": time.time() - ag.MAX_LEASE_AGE_SECONDS - 60,
        }
        lease.write_text(json.dumps(body), encoding="utf-8")
        assert ag.read_lease(settings) is not None  # still running: not stale
        lease.write_text(
            json.dumps({**body, "pid_start": str(int(start) + 1), "since": time.time()}),
            encoding="utf-8",
        )
        assert ag.read_lease(settings) is None  # same PID, different process
    finally:
        other.kill()
        other.wait()
