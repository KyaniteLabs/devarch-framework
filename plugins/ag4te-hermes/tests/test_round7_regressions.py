"""Focused regressions from the seventh audit round."""

import importlib.util
import json
import os
import subprocess
import threading
import time
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("ag4te_round7_test", PKG / "__init__.py")
ag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ag)


def _git_repo(path):
    path.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", "-b", "test", str(path)], check=True)
    (path / "README.md").write_text("repo\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(path), "add", "README.md"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(path),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-q",
            "-m",
            "initial",
        ],
        check=True,
    )


def _start_blocked_dig(tmp_path, settings):
    repo = tmp_path / "repos" / "demo"
    _git_repo(repo)
    entered = threading.Event()
    release = threading.Event()

    def runner(args, _settings):
        entered.set()
        release.wait(10)
        return {"ok": True}

    ag.start_dig(str(repo), "demo", settings, runner=runner)
    assert entered.wait(5)
    thread = next(t for t in ag._jobs.values() if t.name == "ag4te-dig-demo")
    return thread, release


def test_same_named_dig_is_owned_by_its_workspace(tmp_path):
    first = {"repo_roots": str(tmp_path / "repos"), "data_dir": str(tmp_path / "workspace-a")}
    second = {"repo_roots": str(tmp_path / "repos"), "data_dir": str(tmp_path / "workspace-b")}
    first_alias = {
        **first,
        "data_dir": str(tmp_path / "workspace-a" / ".." / "workspace-a"),
    }
    thread, release = _start_blocked_dig(tmp_path, first)
    try:
        ag._set_status(ag.project_dir("demo", second), fresh=True, state="running")

        status = ag.read_status("demo", second)
        assert status["state"] == "failed" and status["interrupted"]
        with pytest.raises(ag.DigError, match="no dig of demo is running"):
            ag.cancel_dig("demo", second)
        assert (
            ag._read_json(ag.project_dir("demo", second) / ag.STATUS_FILE).get("cancelling") is None
        )

        assert ag.read_status("demo", first_alias)["state"] == "running"
        assert ag.cancel_dig("demo", first_alias)["cancelling"]
    finally:
        release.set()
        thread.join(10)


def test_unverified_live_local_dig_keeps_lease_after_clock_step(tmp_path, monkeypatch):
    settings = {
        "repo_roots": str(tmp_path / "repos"),
        "data_dir": str(tmp_path / "workspace"),
    }
    thread, release = _start_blocked_dig(tmp_path, settings)
    lease = ag._lease_path(settings)
    try:
        body = ag._read_json(lease)
        body.update(
            since=time.time() - ag.MAX_LEASE_AGE_SECONDS - 10,
            boot_id=None,
            pid_start=None,
        )
        lease.write_text(json.dumps(body), encoding="utf-8")
        monkeypatch.setattr(ag, "_boot_id", lambda: None)
        monkeypatch.setattr(ag, "_proc_start", lambda _pid: None)

        assert ag.read_lease(settings) == body
        with pytest.raises(ag.DigError, match="a dig is still running"):
            ag.unlock_lease(settings)
        assert lease.exists()
    finally:
        release.set()
        thread.join(10)


def test_foreign_host_lease_tolerates_small_future_clock_skew(tmp_path):
    settings = {"data_dir": str(tmp_path)}
    lease = ag._lease_path(settings)
    lease.parent.mkdir(parents=True, exist_ok=True)
    body = {"project": "foreign", "host": "other-host", "since": time.time() + 5}
    lease.write_text(json.dumps(body), encoding="utf-8")

    assert ag.read_lease(settings) == body


def test_integer_process_start_matches_proc_text(tmp_path, monkeypatch):
    settings = {"data_dir": str(tmp_path)}
    lease = ag._lease_path(settings)
    lease.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "project": "other",
        "pid": os.getpid() + 100_000,
        "host": ag._host(),
        "boot_id": "current-boot",
        "pid_start": 4312,
        "since": time.time(),
    }
    lease.write_text(json.dumps(body), encoding="utf-8")
    monkeypatch.setattr(ag, "_boot_id", lambda: "current-boot")
    monkeypatch.setattr(ag, "_proc_start", lambda _pid: "4312")
    monkeypatch.setattr(ag, "_pid_alive", lambda _pid: True)

    assert ag.read_lease(settings) == body
