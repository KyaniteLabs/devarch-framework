"""Focused regressions from the eighth audit round."""

import importlib.util
import subprocess
import sys
import threading
import types
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("ag4te_round8_test", PKG / "__init__.py")
ag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ag)


@pytest.fixture(autouse=True)
def isolate_job_registry(monkeypatch):
    holder = types.ModuleType("_ag4te_jobs")
    holder.lock = threading.Lock()
    holder.jobs = {}
    holder.cancels = {}
    monkeypatch.setitem(sys.modules, "_ag4te_jobs", holder)
    monkeypatch.setattr(ag, "_reg", holder)
    monkeypatch.setattr(ag, "_jobs_lock", holder.lock)
    monkeypatch.setattr(ag, "_jobs", holder.jobs)
    monkeypatch.setattr(ag, "_cancels", holder.cancels)


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


def _reloaded_plugin():
    fresh_spec = importlib.util.spec_from_file_location(
        "ag4te_round8_reloaded", PKG / "__init__.py"
    )
    fresh = importlib.util.module_from_spec(fresh_spec)
    fresh_spec.loader.exec_module(fresh)
    return fresh


def test_reloaded_plugin_preserves_a_live_legacy_job(tmp_path):
    settings = {
        "repo_roots": str(tmp_path / "repos"),
        "data_dir": str(tmp_path / "workspace"),
    }
    repo = tmp_path / "repos" / "demo"
    _git_repo(repo)
    entered = threading.Event()
    release = threading.Event()

    def runner(_args, _settings):
        entered.set()
        release.wait(10)
        return {"ok": True}

    ag.start_dig(str(repo), "demo", settings, runner=runner)
    assert entered.wait(5)
    key = ag._job_key("demo", settings)
    with ag._jobs_lock:
        job = ag._jobs.pop(key)
        cancel = ag._cancels.pop(key)
        ag._jobs["demo"] = job
        ag._cancels["demo"] = cancel
    fresh = _reloaded_plugin()
    try:
        assert fresh._jobs is ag._jobs
        with pytest.raises(fresh.DigError, match="a dig is still running"):
            fresh.unlock_lease(settings)
        assert fresh.read_status("demo", settings)["state"] == "running"
        assert fresh.cancel_dig("demo", settings)["cancelling"]
    finally:
        release.set()
        job.join(10)
        with ag._jobs_lock:
            ag._jobs.pop(key, None)
            ag._jobs.pop("demo", None)
            ag._cancels.pop(key, None)
            ag._cancels.pop("demo", None)


def test_busy_message_names_legacy_registry_project(tmp_path):
    settings = {
        "repo_roots": str(tmp_path / "repos"),
        "data_dir": str(tmp_path / "workspace"),
    }
    repo = tmp_path / "repos" / "other"
    _git_repo(repo)
    release = threading.Event()
    job = threading.Thread(target=release.wait, name="ag4te-dig-demo", daemon=True)
    job.start()
    with ag._jobs_lock:
        ag._jobs["demo"] = job
        ag._cancels["demo"] = threading.Event()
    try:
        with pytest.raises(ag.DigBusyError, match=r"already running \(demo\)"):
            ag.start_dig(str(repo), "other", settings)
    finally:
        release.set()
        job.join(5)
        with ag._jobs_lock:
            ag._jobs.pop("demo", None)
            ag._cancels.pop("demo", None)
