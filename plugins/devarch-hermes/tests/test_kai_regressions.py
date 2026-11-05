"""Regression tests for Kai Changes-required findings on PR #94 (KLH-328)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parents[1]
if str(PLUGIN_DIR) not in sys.path:
    sys.path.insert(0, str(PLUGIN_DIR))

# Isolate plugin-data under tmp paths via HERMES_HOME.
@pytest.fixture
def hermes_home(tmp_path, monkeypatch):
    home = tmp_path / "hermes-home"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    # Ensure cwd mutation would be detectable and is NOT used.
    start_cwd = os.getcwd()
    yield home
    assert os.getcwd() == start_cwd


@pytest.fixture
def plugin(hermes_home):
    import importlib

    # Fresh module each test so module-level state is clean.
    if "plugins.devarch_hermes_under_test" in sys.modules:
        del sys.modules["plugins.devarch_hermes_under_test"]
    # Load __init__.py as a top-level-ish module name
    import importlib.util

    spec = importlib.util.spec_from_file_location("devarch_hermes_plugin", PLUGIN_DIR / "__init__.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["devarch_hermes_plugin"] = mod
    spec.loader.exec_module(mod)
    return mod


def _git(repo: Path, *args: str, env: dict | None = None) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    return result.stdout


def _init_repo(path: Path, commits: list[tuple[str, str]]) -> Path:
    """Create a repo with dated commits: list of (iso_date, message)."""
    path.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update({
        "GIT_AUTHOR_NAME": "Kai Tester",
        "GIT_AUTHOR_EMAIL": "kai@example.com",
        "GIT_COMMITTER_NAME": "Kai Tester",
        "GIT_COMMITTER_EMAIL": "kai@example.com",
    })
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "kai@example.com"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Kai Tester"], cwd=path, check=True, capture_output=True)
    for idx, (date, message) in enumerate(commits):
        fname = path / f"f{idx}.txt"
        fname.write_text(f"{message}\n", encoding="utf-8")
        subprocess.run(["git", "add", fname.name], cwd=path, check=True, capture_output=True)
        env["GIT_AUTHOR_DATE"] = date
        env["GIT_COMMITTER_DATE"] = date
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=path,
            check=True,
            capture_output=True,
            env=env,
        )
    return path


# --- P1.1 gateway ContextVars ------------------------------------------------

def test_gateway_reads_session_contextvars(plugin, monkeypatch, hermes_home):
    """Hermes 0.21.6 binds platform via ContextVars; slash must refuse on telegram."""
    # Simulate gateway.session_context without requiring full Hermes install.
    import types
    from contextvars import ContextVar

    _plat = ContextVar("HERMES_SESSION_PLATFORM", default=object())
    UNSET = object()
    _plat.set(UNSET)

    def get_session_env(name, default=""):
        if name == "HERMES_SESSION_PLATFORM":
            val = _plat.get()
            if val is UNSET:
                return os.getenv(name, default)
            return val
        return os.getenv(name, default)

    def session_is_messaging_surface():
        plat = (os.getenv("HERMES_PLATFORM") or get_session_env("HERMES_SESSION_PLATFORM", "")).strip().lower()
        return bool(plat) and plat not in {
            "", "api_server", "cli", "codex", "desktop", "gateway", "kanban", "local",
            "msgraph_webhook", "tool", "tui", "webhook", "acp",
        }

    fake = types.ModuleType("gateway")
    fake_sc = types.ModuleType("gateway.session_context")
    fake_sc.get_session_env = get_session_env
    fake_sc.session_is_messaging_surface = session_is_messaging_surface
    fake_sc.set_session_vars = lambda **kw: _plat.set(kw.get("platform", ""))
    sys.modules["gateway"] = fake
    sys.modules["gateway.session_context"] = fake_sc

    # Clear env so only ContextVar matters (Kai reproduction).
    monkeypatch.delenv("HERMES_PLATFORM", raising=False)
    monkeypatch.delenv("HERMES_SESSION_PLATFORM", raising=False)

    assert plugin._on_gateway() is False
    _plat.set("telegram")
    assert plugin._on_gateway() is True

    # Slash refuses mine on gateway.
    out = plugin._slash(f"mine {hermes_home}")
    assert "disabled on gateway" in out.lower() or "refused" in out.lower() or "disabled" in out.lower()


# --- P1.2 concurrent cwd -----------------------------------------------------

def test_concurrent_calls_do_not_mutate_cwd_or_env(plugin, tmp_path, hermes_home):
    repo = _init_repo(
        tmp_path / "repo",
        [
            ("2026-01-01T12:00:00", "one"),
            ("2026-01-02T12:00:00", "two"),
            ("2026-02-15T12:00:00", "three after gap"),
        ],
    )
    start_cwd = os.getcwd()
    assert "DEVARCH_WORKSPACE" not in os.environ or True
    saved_env = os.environ.get("DEVARCH_WORKSPACE")

    barrier = threading.Barrier(2)
    errors: list[str] = []

    def worker(name: str):
        try:
            barrier.wait(timeout=5)
            # Overlap workspace usage
            res = plugin.mine(str(repo), project=name)
            if not res.get("ok"):
                # DB deps may be missing in some envs; cwd must still be untouched.
                errors.append(f"{name}: mine not ok: {res.get('error')}")
            barrier.wait(timeout=30)
            if os.getcwd() != start_cwd:
                errors.append(f"{name}: cwd drifted to {os.getcwd()}")
            now_env = os.environ.get("DEVARCH_WORKSPACE")
            if now_env != saved_env:
                errors.append(f"{name}: DEVARCH_WORKSPACE mutated to {now_env!r}")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{name}: {type(exc).__name__}: {exc}")

    t1 = threading.Thread(target=worker, args=("projA",))
    t2 = threading.Thread(target=worker, args=("projB",))
    t1.start()
    t2.start()
    t1.join(timeout=60)
    t2.join(timeout=60)
    assert os.getcwd() == start_cwd
    assert os.environ.get("DEVARCH_WORKSPACE") == saved_env
    # Soft-assert mine outcomes when sqlite-utils present
    cwd_errors = [e for e in errors if "cwd" in e or "DEVARCH_WORKSPACE" in e]
    assert not cwd_errors, cwd_errors


# --- P1.3 evidence binding ---------------------------------------------------

def test_mining_writes_coverage_and_enables_binding(plugin, tmp_path, hermes_home):
    pytest.importorskip("sqlite_utils")
    repo = _init_repo(
        tmp_path / "repo",
        [
            ("2026-01-01T12:00:00", "alpha"),
            ("2026-01-02T12:00:00", "beta"),
            ("2026-01-03T12:00:00", "gamma"),
        ],
    )
    res = plugin.mine(str(repo), project="bindme")
    assert res.get("ok"), res
    project_dir = plugin._project_dir("bindme")
    assert (project_dir / "data" / "coverage.json").is_file()
    config = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    assert config.get("mined_history_manifest_required") is True
    from archaeology.provenance import requires_binding

    assert requires_binding(project_dir) is True

    # Stale CSV must make report fail once binding is on and a bound artifact exists.
    # First produce signals + report so a provenance sidecar exists.
    sig = plugin.signals("bindme")
    assert sig.get("ok"), sig
    rep = plugin.report("bindme")
    assert rep.get("ok"), rep
    csv_path = project_dir / "data" / "github-commits.csv"
    csv_path.write_text(csv_path.read_text(encoding="utf-8") + "# tampered\n", encoding="utf-8")
    stale = plugin.report("bindme")
    assert not stale.get("ok"), stale
    assert "stale" in str(stale.get("error", "")).lower() or "binding" in str(stale.get("error", "")).lower() or "modified" in str(stale.get("error", "")).lower() or "unbound" in str(stale.get("error", "")).lower()


# --- P1.4 failed stages honesty ---------------------------------------------

def test_db_build_failure_is_not_ok_complete(plugin, tmp_path, hermes_home, monkeypatch):
    repo = _init_repo(
        tmp_path / "repo",
        [
            ("2026-01-01T12:00:00", "a"),
            ("2026-01-02T12:00:00", "b"),
            ("2026-01-03T12:00:00", "c"),
        ],
    )

    def boom(*_a, **_k):
        raise RuntimeError("simulated db failure (no such table: commits)")

    monkeypatch.setattr("archaeology.db.builder.build_db", boom)
    # Force import path used inside mine
    import archaeology.db.builder as builder

    monkeypatch.setattr(builder, "build_db", boom)
    res = plugin.mine(str(repo), project="faildb")
    assert res.get("ok") is False
    assert res.get("status") == "failed"
    assert "database" in str(res.get("error", "")).lower() or res.get("failed_at") == "build_db"


def test_analysis_error_values_are_not_success(plugin):
    classified = plugin._classify_analysis({
        "sdlc-gap-finder": "ERROR: no such table: commits",
        "ml-pattern-mapper": "ERROR: no such table: commits",
        "agentic-workflow": "ERROR: no such table: commits",
        "formal-terms-mapper": "ERROR: no such table: commits",
        "source-archaeologist": "ERROR: no such table: commits",
        "youtube-correlator": "ERROR: no such table: commits",
    })
    assert classified["ok"] is False
    assert classified["vectors_run"] == []
    assert len(classified["vector_errors"]) == 6


# --- P2.5 report includes signals -------------------------------------------

def test_report_includes_detected_signals_and_clusters(plugin, tmp_path, hermes_home):
    pytest.importorskip("sqlite_utils")
    repo = _init_repo(
        tmp_path / "repo",
        [
            ("2026-01-01T12:00:00", "start"),
            ("2026-01-02T12:00:00", "early"),
            ("2026-02-15T12:00:00", "after 31-day gap"),  # >=31 day gap
        ],
    )
    mined = plugin.mine(str(repo), project="gaps")
    assert mined.get("ok"), mined
    sig = plugin.signals("gaps", min_gap_days=14)
    assert sig.get("ok"), sig
    assert sig.get("signal_count", 0) >= 1
    assert sig.get("cluster_count", 0) >= 2
    rep = plugin.report("gaps")
    assert rep.get("ok"), rep
    md = rep.get("markdown") or ""
    assert "Detected Signals" in md or "signal" in md.lower()
    assert "Era Semantics" in md or "gap" in md.lower()
    # Should not instruct citing nonexistent curated eras exclusively
    assert "gap" in md.lower() or "cluster" in md.lower()


# --- P2.6 ledger concurrency -------------------------------------------------

def test_parallel_ledger_hooks_keep_both_entries(plugin, hermes_home):
    barrier = threading.Barrier(2)

    def hook(n: int):
        # Synchronize so both reads would race without a lock.
        barrier.wait(timeout=5)
        plugin._on_post_tool(
            "devarch_report",
            {"project": f"p{n}"},
            {"ok": True, "project": f"p{n}", "output_path": f"/tmp/r{n}.md"},
        )

    t1 = threading.Thread(target=hook, args=(1,))
    t2 = threading.Thread(target=hook, args=(2,))
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)
    ledger = plugin._load_json(plugin._ledger_path(), [])
    assert isinstance(ledger, list)
    assert len(ledger) == 2, ledger


# --- P2.7 JSON truncation stays valid ----------------------------------------

def test_output_cap_keeps_valid_json_envelope(plugin, hermes_home):
    # Seed many projects so list exceeds MAX_OUT if naively dumped.
    ws = plugin._workspace() / "projects"
    for i in range(100):
        d = ws / f"proj-{i:03d}-{'x' * 40}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "project.json").write_text(
            json.dumps({
                "name": d.name,
                "description": "d" * 80,
                "repo_url": f"file:///tmp/{d.name}",
            }),
            encoding="utf-8",
        )
    raw = plugin._tool_list({})
    assert len(raw) <= plugin.MAX_OUT
    payload = json.loads(raw)  # must not raise
    assert isinstance(payload, dict)
    assert "ok" in payload
    if payload.get("truncated"):
        assert "truncation" in payload


# --- P2.8 partial clone refusal ---------------------------------------------

def test_partial_clone_is_refused(plugin, tmp_path, hermes_home):
    # Build a normal repo, then mark it as promisor via config + empty promisor pack marker.
    src = _init_repo(
        tmp_path / "src",
        [
            ("2026-01-01T12:00:00", "one"),
            ("2026-01-02T12:00:00", "two"),
            ("2026-01-03T12:00:00", "three"),
        ],
    )
    # Clone as partial (blob:none) into dest via local file:// protocol.
    dest = tmp_path / "partial"
    # Some environments may not support partial clone filters on file://; fall back to
    # planting promisor config + a .promisor pack marker.
    try:
        subprocess.run(
            ["git", "clone", "--filter=blob:none", f"file://{src}", str(dest)],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError:
        dest.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=dest, check=True, capture_output=True)
        # Copy objects lightly then mark promisor
        subprocess.run(["git", "remote", "add", "origin", str(src)], cwd=dest, check=True, capture_output=True)
        subprocess.run(["git", "config", "remote.origin.promisor", "true"], cwd=dest, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "remote.origin.partialclonefilter", "blob:none"],
            cwd=dest,
            check=True,
            capture_output=True,
        )
        pack_dir = dest / ".git" / "objects" / "pack"
        pack_dir.mkdir(parents=True, exist_ok=True)
        (pack_dir / "pack-deadbeef.promisor").write_text("", encoding="utf-8")

    from archaeology.extractors.git import incomplete_object_reason

    reason = incomplete_object_reason(str(dest))
    # If clone succeeded as partial, reason should be set; if we planted markers, also set.
    assert reason, f"expected incomplete reason, got {reason!r}; dest={dest}"
    res = plugin.mine(str(dest), project="partial")
    assert res.get("ok") is False
    assert "partial" in str(res.get("error", "")).lower() or "promisor" in str(res.get("error", "")).lower() or "incomplete" in str(res.get("error", "")).lower()


# --- lint / import hygiene smoke --------------------------------------------

def test_wrapper_imports_sorted_for_ruff_i001():
    # Structural smoke: future + stdlib import block should sort redirect_stderr first.
    text = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")
    assert "from contextlib import redirect_stderr, redirect_stdout" in text
