"""F11: cancelling a dig stops the whole process group, not only the direct child."""

import importlib.util
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("ag4te_f11_under_test", PKG / "__init__.py")
ag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ag)

import pytest  # noqa: E402

posix_only = pytest.mark.skipif(os.name == "nt", reason="process groups are POSIX")


@posix_only
def test_cancel_returns_fast_and_leaves_no_process_in_the_group(tmp_path, monkeypatch):
    seen = []
    real_popen = subprocess.Popen

    def recording_popen(*a, **kw):
        p = real_popen(*a, **kw)
        seen.append(p)
        return p

    monkeypatch.setattr(ag.subprocess, "Popen", recording_popen)
    settings = {"devarch_command": "sh", "data_dir": str(tmp_path), "timeout_seconds": 600}
    cancel = threading.Event()
    threading.Timer(0.5, cancel.set).start()
    t0 = time.monotonic()
    res = ag.run_devarch(["-c", "sleep 9; true"], settings, cancel)
    took = time.monotonic() - t0

    assert res["cancelled"] is True
    assert took <= 1.0, f"cancel took {took:.2f}s"
    pgid = seen[0].pid  # the child leads its own group (start_new_session)
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline and _group_alive(pgid):
        time.sleep(0.05)
    assert not _group_alive(pgid), "a process of the dig's group survived the cancel"


def _group_alive(pgid):
    """True while a group member still runs. Zombies do not count: in a CI container
    the orphaned grandchild is reparented to a PID 1 that may never reap it."""
    proc = Path("/proc")
    if proc.is_dir():
        for stat in proc.glob("[0-9]*/stat"):
            try:
                fields = stat.read_text().rsplit(")", 1)[1].split()
            except OSError:
                continue
            if int(fields[2]) == pgid and fields[0] != "Z":
                return True
        return False
    try:
        os.killpg(pgid, 0)
        return True
    except ProcessLookupError:
        return False


@posix_only
def test_term_ignoring_grandchild_is_killed_and_wait_is_bounded(tmp_path):
    settings = {"devarch_command": "sh", "data_dir": str(tmp_path), "timeout_seconds": 600}
    cancel = threading.Event()
    threading.Timer(0.3, cancel.set).start()
    t0 = time.monotonic()
    res = ag.run_devarch(["-c", "trap '' TERM; sleep 30; true"], settings, cancel)
    took = time.monotonic() - t0
    assert res["cancelled"] is True
    assert took <= 8.0, f"escalation to KILL took {took:.2f}s"
