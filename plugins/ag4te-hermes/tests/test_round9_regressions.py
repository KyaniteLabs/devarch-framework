"""Focused regressions from the ninth audit round."""

import importlib.util
import subprocess
import sys
import threading
import types
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("ag4te_round9_test", PKG / "__init__.py")
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


def test_legacy_job_migrates_only_for_its_lease_owner(tmp_path):
    repo_root = tmp_path / "repos"
    settings_a = {"repo_roots": str(repo_root), "data_dir": str(tmp_path / "workspace-a")}
    settings_b = {"repo_roots": str(repo_root), "data_dir": str(tmp_path / "workspace-b")}
    repo = repo_root / "demo"
    _git_repo(repo)
    entered = threading.Event()
    release = threading.Event()

    def runner(_args, _settings):
        entered.set()
        release.wait(10)
        return {"ok": True}

    ag.start_dig(str(repo), "demo", settings_a, runner=runner)
    assert entered.wait(5)
    ag._set_status(ag.project_dir("demo", settings_b), fresh=True, state="running")
    key_a = ag._job_key("demo", settings_a)
    with ag._jobs_lock:
        job = ag._jobs.pop(key_a)
        cancel = ag._cancels.pop(key_a)
        ag._jobs["demo"] = job
        ag._cancels["demo"] = cancel

    try:
        status_b = ag.read_status("demo", settings_b)
        assert status_b["state"] == "failed" and status_b["interrupted"]
        with pytest.raises(ag.DigError, match="no dig of demo is running"):
            ag.cancel_dig("demo", settings_b)
        assert ag.unlock_lease(settings_b) is False
        assert not cancel.is_set()
        assert ag._jobs.get("demo") is job
        assert ag._cancels.get("demo") is cancel
        assert ag.read_status("demo", settings_a)["state"] == "running"
        assert ag._jobs.get(key_a) is job
        assert ag._cancels.get(key_a) is cancel
        assert "demo" not in ag._jobs
        assert ag.cancel_dig("demo", settings_a)["cancelling"]
        assert cancel.is_set()
        with pytest.raises(ag.DigError, match="a dig is still running"):
            ag.unlock_lease(settings_a)
    finally:
        release.set()
        job.join(10)
        with ag._jobs_lock:
            ag._jobs.pop(key_a, None)
            ag._jobs.pop("demo", None)
            ag._cancels.pop(key_a, None)
            ag._cancels.pop("demo", None)
