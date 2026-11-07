"""Exact third-review schedules, using the real dependency-backed pipeline."""

import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from test_kai_regressions import PLUGIN_DIR, _init_repo  # noqa: E402

pytest_plugins = ["test_kai_regressions"]


@pytest.fixture
def repositories(tmp_path):
    old = _init_repo(
        tmp_path / "old",
        [
            ("2024-01-01T12:00:00+00:00", "initial"),
            ("2024-02-01T12:00:00+00:00", "migration"),
            ("2024-02-02T12:00:00+00:00", "fix"),
        ],
    )
    new = _init_repo(tmp_path / "new", [("2024-03-01T12:00:00+00:00", "new")])
    return old, new


def test_metrics_closes_sqlite_handle_before_remine(plugin, repositories, monkeypatch):
    import sqlite3

    from _devarch_vendor.metrics import write_metrics

    assert plugin.mine(str(repositories[0]), "handles")["ok"]
    project = plugin._project_dir("handles")
    original = sqlite3.connect
    connections = []

    class TrackedConnection(sqlite3.Connection):
        closed = False

        def close(self):
            self.closed = True
            super().close()

    def connect(*args, **kwargs):
        connection = original(*args, factory=TrackedConnection, **kwargs)
        connections.append(connection)
        return connection

    monkeypatch.setattr(sqlite3, "connect", connect)
    write_metrics(project, project / "data/archaeology.db")
    assert connections and all(connection.closed for connection in connections)


def test_capped_history_is_explicit(plugin, repositories, monkeypatch):
    monkeypatch.setitem(plugin.DEFAULTS, "max_commits", 2)
    mined = plugin.mine(str(repositories[0]), "cap")
    assert mined["ok"], mined
    assert mined["commits_extracted"] == 2
    assert mined["coverage"]["commit_count"] == 3
    assert mined["coverage"]["sampled"] is True
    assert plugin.signals("cap")["ok"]
    report = plugin.report("cap")
    assert report["ok"], report
    assert "Sampled history: True; extracted 2 of 3" in report["markdown"]


@pytest.mark.parametrize("first", ["mine", "signals", "report"])
def test_same_project_transactions(plugin, repositories, monkeypatch, first):
    import _devarch_vendor.db.builder as builder
    import _devarch_vendor.report as exporter
    from _devarch_vendor.classifiers.era_detector import SignalDetector

    old, new = repositories
    assert plugin.mine(str(old), "shared")["ok"]
    assert plugin.signals("shared")["ok"]
    entered, release, second_entered = threading.Event(), threading.Event(), threading.Event()
    original_build = builder.build_db

    def paused(call):
        def run(*args, **kwargs):
            value = call(*args, **kwargs) if first != "mine" else None
            entered.set()
            assert release.wait(60), "test failed to release first operation"
            return call(*args, **kwargs) if first == "mine" else value

        return run

    if first == "mine":
        monkeypatch.setattr(builder, "build_db", paused(original_build))

        def operation():
            return plugin.mine(str(old), "shared")
    elif first == "signals":
        monkeypatch.setattr(SignalDetector, "detect", paused(SignalDetector.detect))

        def operation():
            return plugin.signals("shared")
    else:
        monkeypatch.setattr(
            exporter, "export_markdown_report", paused(exporter.export_markdown_report)
        )

        def operation():
            return plugin.report("shared")

    with ThreadPoolExecutor(2) as pool:
        one = pool.submit(operation)
        assert entered.wait(60), (
            one.result(timeout=1) if one.done() else "operation did not reach pause"
        )

        def second_build(*args, **kwargs):
            second_entered.set()
            return original_build(*args, **kwargs)

        # First call has already resolved its callable; observe the second one's entry.
        monkeypatch.setattr(builder, "build_db", second_build)
        two = pool.submit(plugin.mine, str(new), "shared")
        try:
            assert not second_entered.wait(0.3), "remine entered a live project transaction"
        finally:
            release.set()
        first_result = one.result(timeout=60)
        second_result = two.result(timeout=60)
        assert first_result["ok"], first_result
        assert second_result["ok"], second_result
    assert plugin.signals("shared")["ok"]
    report = plugin.report("shared")
    assert report["ok"], report
    project = plugin._project_dir("shared")
    coverage = json.loads((project / "data/coverage.json").read_text())
    metrics = json.loads((project / "deliverables/canonical-metrics.json").read_text())
    assert coverage["commit_count"] == metrics["total_commits"] == 1
    assert plugin.signals("shared")["signal_count"] == 0


@pytest.mark.parametrize(
    "artifact",
    ["deliverables/canonical-metrics.json", "data/detected-signals.json", "data/gap-clusters.json"],
)
@pytest.mark.parametrize("mutation", ["content", "generation", "binding"])
def test_present_derived_artifact_requires_generation_and_content(
    plugin, repositories, artifact, mutation
):
    assert plugin.mine(str(repositories[0]), "bound")["ok"]
    assert plugin.signals("bound")["ok"]
    assert plugin.report("bound")["ok"]
    path = plugin._project_dir("bound") / artifact
    value = json.loads(path.read_text())
    if mutation == "binding":
        path.with_name(path.name + ".generation.json").unlink()
    else:
        if mutation == "generation":
            value.pop("mining_generation")
        else:
            value["total_commits"] = 999
        path.write_text(json.dumps(value))
    refused = plugin.report("bound")
    assert not refused["ok"], refused


@pytest.mark.parametrize("preinstalled", [False, True])
def test_plugin_only_fresh_process_ignores_installed_framework(
    tmp_path, repositories, preinstalled
):
    script = """
import importlib.util, json, os, sys, types
from pathlib import Path
if sys.argv[3] == "True":
    fake = types.ModuleType("archaeology")
    fake.__version__ = "0.4.1-unpatched"
    fake.__file__ = "/unpatched/site-packages/archaeology/__init__.py"
    sys.modules["archaeology"] = fake
spec = importlib.util.spec_from_file_location("plugin", Path(sys.argv[1]) / "__init__.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
assert "archaeology" not in sys.modules or sys.modules["archaeology"].__version__ == "0.4.1-unpatched"
r = m.pipeline(sys.argv[2], "isolated")
assert r["ok"], r
assert "Detected Signals" in r["report"]["markdown"], r
assert r["signals"]["signal_count"] > 0, r
print(json.dumps({"ok": r["ok"], "status": r["status"]}))
"""
    env = {**os.environ, "HERMES_HOME": str(tmp_path / "home")}
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            script,
            str(PLUGIN_DIR),
            str(repositories[0]),
            str(preinstalled),
        ],
        env=env,
        text=True,
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
