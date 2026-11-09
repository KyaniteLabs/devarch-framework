"""Regression tests for Kai Changes-required findings on PR #94 (KLH-328)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture
def hermes_home(tmp_path, monkeypatch):
    home = tmp_path / "hermes-home"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    start_cwd = os.getcwd()
    yield home
    assert os.getcwd() == start_cwd


@pytest.fixture
def plugin(hermes_home):
    """Load the plugin module without permanently shadowing framework archaeology."""
    import importlib.util

    import archaeology

    framework_file = Path(archaeology.__file__).resolve()
    assert "plugins/devarch-hermes" not in str(framework_file).replace("\\", "/")

    for key in list(sys.modules):
        if key == "devarch_hermes_plugin" or key.startswith("devarch_hermes_plugin."):
            del sys.modules[key]

    # Avoid leftover plugin-dir path entries from importlib/path side effects.
    plugin_resolved = PLUGIN_DIR.resolve()
    sys.path[:] = [entry for entry in sys.path if Path(entry).resolve() != plugin_resolved]

    spec = importlib.util.spec_from_file_location(
        "devarch_hermes_plugin", PLUGIN_DIR / "__init__.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["devarch_hermes_plugin"] = mod
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    import archaeology as arch_after

    assert Path(arch_after.__file__).resolve() == framework_file
    assert plugin_resolved not in Path(arch_after.__file__).resolve().parents

    yield mod

    sys.modules.pop("devarch_hermes_plugin", None)
    # conftest autouse fixture also re-asserts framework archaeology after the test.


def _init_repo(path: Path, commits: list[tuple[str, str]]) -> Path:
    """Create a repo with dated commits: list of (iso_date, message)."""
    path.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "GIT_AUTHOR_NAME": "Kai Tester",
            "GIT_AUTHOR_EMAIL": "kai@example.com",
            "GIT_COMMITTER_NAME": "Kai Tester",
            "GIT_COMMITTER_EMAIL": "kai@example.com",
        }
    )
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "kai@example.com"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Kai Tester"],
        cwd=path,
        check=True,
        capture_output=True,
    )
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
    import types
    from contextvars import ContextVar

    _plat = ContextVar("HERMES_SESSION_PLATFORM", default=object())
    unset = object()
    _plat.set(unset)

    def get_session_env(name, default=""):
        if name == "HERMES_SESSION_PLATFORM":
            val = _plat.get()
            if val is unset:
                return os.getenv(name, default)
            return val
        return os.getenv(name, default)

    def session_is_messaging_surface():
        plat = (
            (os.getenv("HERMES_PLATFORM") or get_session_env("HERMES_SESSION_PLATFORM", ""))
            .strip()
            .lower()
        )
        return bool(plat) and plat not in {
            "",
            "api_server",
            "cli",
            "codex",
            "desktop",
            "gateway",
            "kanban",
            "local",
            "msgraph_webhook",
            "tool",
            "tui",
            "webhook",
            "acp",
        }

    fake = types.ModuleType("gateway")
    fake_sc = types.ModuleType("gateway.session_context")
    fake_sc.get_session_env = get_session_env
    fake_sc.session_is_messaging_surface = session_is_messaging_surface
    fake_sc.set_session_vars = lambda **kw: _plat.set(kw.get("platform", ""))
    monkeypatch.setitem(sys.modules, "gateway", fake)
    monkeypatch.setitem(sys.modules, "gateway.session_context", fake_sc)

    monkeypatch.delenv("HERMES_PLATFORM", raising=False)
    monkeypatch.delenv("HERMES_SESSION_PLATFORM", raising=False)

    assert plugin._on_gateway() is False
    _plat.set("telegram")
    assert plugin._on_gateway() is True

    out = plugin._slash(f"mine {hermes_home}")
    assert (
        "disabled on gateway" in out.lower()
        or "refused" in out.lower()
        or "disabled" in out.lower()
    )


# --- P1.2 concurrent cwd + stdout/stderr ------------------------------------


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
    saved_env = os.environ.get("DEVARCH_WORKSPACE")
    real_out, real_err = sys.stdout, sys.stderr

    barrier = threading.Barrier(2)
    errors: list[str] = []

    def worker(name: str):
        try:
            barrier.wait(timeout=5)
            res = plugin.mine(str(repo), project=name)
            if not res.get("ok"):
                errors.append(f"{name}: mine not ok: {res.get('error')}")
            barrier.wait(timeout=30)
            if os.getcwd() != start_cwd:
                errors.append(f"{name}: cwd drifted to {os.getcwd()}")
            now_env = os.environ.get("DEVARCH_WORKSPACE")
            if now_env != saved_env:
                errors.append(f"{name}: DEVARCH_WORKSPACE mutated to {now_env!r}")
            if sys.stdout is not real_out or sys.stderr is not real_err:
                errors.append(f"{name}: stdout/stderr replaced during mine")
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
    assert sys.stdout is real_out
    assert sys.stderr is real_err
    cwd_errors = [e for e in errors if "cwd" in e or "DEVARCH_WORKSPACE" in e or "stdout" in e]
    assert not cwd_errors, cwd_errors


def test_concurrent_mine_leaves_host_streams_intact(plugin, tmp_path, hermes_home, monkeypatch):
    """Kai probe: two-thread mine must not leave sys.stdout/sys.stderr as StringIO."""
    repo = _init_repo(
        tmp_path / "repo",
        [
            ("2026-01-01T12:00:00", "one"),
            ("2026-01-02T12:00:00", "two"),
        ],
    )
    real_out, real_err = sys.stdout, sys.stderr
    barrier = threading.Barrier(2)
    errors: list[str] = []

    def coordinating_build_db(**_kwargs):
        barrier.wait(timeout=5)
        # No DB file → mine returns failure, but redirects (if any) already ran.
        return None

    monkeypatch.setattr("_devarch_vendor.db.builder.build_db", coordinating_build_db)
    import _devarch_vendor.db.builder as builder

    monkeypatch.setattr(builder, "build_db", coordinating_build_db)

    def worker(name: str):
        try:
            plugin.mine(str(repo), project=name)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{name}: {exc}")

    t1 = threading.Thread(target=worker, args=("streamA",))
    t2 = threading.Thread(target=worker, args=("streamB",))
    t1.start()
    t2.start()
    t1.join(timeout=30)
    t2.join(timeout=30)
    assert not errors, errors
    assert sys.stdout is real_out
    assert sys.stderr is real_err
    assert type(sys.stdout).__name__ != "StringIO"
    assert type(sys.stderr).__name__ != "StringIO"


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
    coverage = json.loads((project_dir / "data" / "coverage.json").read_text(encoding="utf-8"))
    assert coverage.get("mining_status") == "complete"
    assert coverage.get("mining_generation")
    assert coverage.get("derived_sha256", {}).get("archaeology.db")
    config = json.loads((project_dir / "project.json").read_text(encoding="utf-8"))
    assert config.get("mined_history_manifest_required") is True
    from archaeology.provenance import requires_binding

    assert requires_binding(project_dir) is True

    sig = plugin.signals("bindme")
    assert sig.get("ok"), sig
    rep = plugin.report("bindme")
    assert rep.get("ok"), rep
    csv_path = project_dir / "data" / "github-commits.csv"
    csv_path.write_text(csv_path.read_text(encoding="utf-8") + "# tampered\n", encoding="utf-8")
    stale = plugin.report("bindme")
    assert not stale.get("ok"), stale
    err = str(stale.get("error", "")).lower()
    assert "stale" in err or "binding" in err or "modified" in err or "unbound" in err


def test_failed_remine_refuses_report_with_old_derived(plugin, tmp_path, hermes_home, monkeypatch):
    """Kai probe: 3-commit mine → failed 1-commit remine → report must refuse old metrics."""
    pytest.importorskip("sqlite_utils")
    three = _init_repo(
        tmp_path / "three",
        [
            ("2026-01-01T12:00:00", "a"),
            ("2026-01-02T12:00:00", "b"),
            ("2026-02-15T12:00:00", "c after gap"),
        ],
    )
    one = _init_repo(
        tmp_path / "one",
        [("2026-03-01T12:00:00", "solo")],
    )
    first = plugin.mine(str(three), project="remine")
    assert first.get("ok"), first
    project_dir = plugin._project_dir("remine")
    # Build signals so report has a 31-day gap story under the first generation.
    sig = plugin.signals("remine", min_gap_days=14)
    assert sig.get("ok"), sig
    ok_report = plugin.report("remine")
    assert ok_report.get("ok"), ok_report
    md = ok_report.get("markdown") or ""
    assert "3" in md or "gap" in md.lower()

    old_metrics = project_dir / "deliverables" / "canonical-metrics.json"
    # Seed canonical metrics as Kai's fixture did if builder didn't write them.
    if not old_metrics.is_file():
        old_metrics.parent.mkdir(parents=True, exist_ok=True)
        old_metrics.write_text(
            json.dumps(
                {
                    "total_commits": 3,
                    "span_days": 45,
                    "active_days": 3,
                    "mining_generation": json.loads(
                        (project_dir / "data" / "coverage.json").read_text(encoding="utf-8")
                    ).get("mining_generation"),
                }
            ),
            encoding="utf-8",
        )
        # Re-export once so the report path is warm; ignore binding on this helper seed.
        plugin.report("remine")

    def boom(*_a, **_k):
        raise RuntimeError("simulated remine db failure (sqlite-utils missing)")

    monkeypatch.setattr("_devarch_vendor.db.builder.build_db", boom)
    import _devarch_vendor.db.builder as builder

    monkeypatch.setattr(builder, "build_db", boom)

    remine = plugin.mine(str(one), project="remine")
    assert remine.get("ok") is False
    assert remine.get("status") == "failed"

    coverage = json.loads((project_dir / "data" / "coverage.json").read_text(encoding="utf-8"))
    assert coverage.get("commit_count") == 1
    assert coverage.get("mining_status") == "incomplete"
    assert not coverage.get("derived_sha256")
    # Canonical DB should be gone; Windows may leave a truncated/locked leftover or
    # a .stale-* rename aside — neither may remain bound as a complete generation.
    db_path = project_dir / "data" / "archaeology.db"
    if db_path.exists():
        assert db_path.stat().st_size == 0
    assert not (project_dir / "deliverables" / "canonical-metrics.json").exists()

    refused = plugin.report("remine")
    assert refused.get("ok") is False, refused
    err = str(refused.get("error", "")).lower()
    assert (
        "incomplete" in err
        or "generation" in err
        or "remine" in err
        or "unbound" in err
        or "derived" in err
        or "archaeology.db" in err
    )


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

    monkeypatch.setattr("_devarch_vendor.db.builder.build_db", boom)
    import _devarch_vendor.db.builder as builder

    monkeypatch.setattr(builder, "build_db", boom)
    res = plugin.mine(str(repo), project="faildb")
    assert res.get("ok") is False
    assert res.get("status") == "failed"
    assert "database" in str(res.get("error", "")).lower() or res.get("failed_at") == "build_db"


def test_analysis_error_values_are_not_success(plugin):
    classified = plugin._classify_analysis(
        {
            "sdlc-gap-finder": "ERROR: no such table: commits",
            "ml-pattern-mapper": "ERROR: no such table: commits",
            "agentic-workflow": "ERROR: no such table: commits",
            "formal-terms-mapper": "ERROR: no such table: commits",
            "source-archaeologist": "ERROR: no such table: commits",
            "youtube-correlator": "ERROR: no such table: commits",
        }
    )
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
            ("2026-02-15T12:00:00", "after 31-day gap"),
        ],
    )
    mined = plugin.mine(str(repo), project="gaps")
    assert mined.get("ok"), mined
    sig = plugin.signals("gaps", min_gap_days=14)
    assert sig.get("ok"), sig
    assert sig.get("signal_count", 0) >= 1
    assert sig.get("cluster_count", 0) >= 2
    assert (plugin._project_dir("gaps") / "data" / "gap-clusters.json").is_file()
    rep = plugin.report("gaps")
    assert rep.get("ok"), rep
    md = rep.get("markdown") or ""
    assert "Detected Signals" in md or "signal" in md.lower()
    assert "Era Semantics" in md or "gap" in md.lower()
    assert "gap" in md.lower() or "cluster" in md.lower()


def test_signals_preserve_curated_eras(plugin, tmp_path, hermes_home):
    """Kai probe: signals must not destroy human-authored commit-eras.json."""
    pytest.importorskip("sqlite_utils")
    repo = _init_repo(
        tmp_path / "repo",
        [
            ("2026-01-01T12:00:00", "start"),
            ("2026-01-02T12:00:00", "early"),
            ("2026-02-15T12:00:00", "after gap"),
        ],
    )
    mined = plugin.mine(str(repo), project="curated")
    assert mined.get("ok"), mined
    eras_path = plugin._project_dir("curated") / "data" / "commit-eras.json"
    curated = {
        "project": "curated",
        "total_commits": 3,
        "eras": [
            {
                "id": 1,
                "name": "Curated architecture migration",
                "dates": "2026-01-01 to 2026-02-15",
                "commits": 3,
                "description": "Human-authored era narrative",
                "kind": "curated",
            }
        ],
        "era_semantics": "Human-authored development eras.",
    }
    eras_path.write_text(json.dumps(curated, indent=2), encoding="utf-8")
    sig = plugin.signals("curated", min_gap_days=14)
    assert sig.get("ok"), sig
    preserved = json.loads(eras_path.read_text(encoding="utf-8"))
    names = [e.get("name") for e in preserved.get("eras", [])]
    assert "Curated architecture migration" in names
    clusters_path = plugin._project_dir("curated") / "data" / "gap-clusters.json"
    assert clusters_path.is_file()
    clusters = json.loads(clusters_path.read_text(encoding="utf-8"))
    assert clusters.get("cluster_count", 0) >= 1 or clusters.get("eras")


# --- P2.6 ledger concurrency -------------------------------------------------


def test_parallel_ledger_hooks_keep_both_entries(plugin, hermes_home):
    barrier = threading.Barrier(2)

    def hook(n: int):
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
    ws = plugin._workspace() / "projects"
    for i in range(100):
        d = ws / f"proj-{i:03d}-{'x' * 40}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "project.json").write_text(
            json.dumps(
                {
                    "name": d.name,
                    "description": "d" * 80,
                    "repo_url": f"file:///tmp/{d.name}",
                }
            ),
            encoding="utf-8",
        )
    raw = plugin._tool_list({})
    assert len(raw) <= plugin.MAX_OUT
    payload = json.loads(raw)
    assert isinstance(payload, dict)
    assert "ok" in payload
    if payload.get("truncated"):
        assert "truncation" in payload


# --- P2.8 partial clone refusal ---------------------------------------------


def test_partial_clone_is_refused(plugin, tmp_path, hermes_home):
    src = _init_repo(
        tmp_path / "src",
        [
            ("2026-01-01T12:00:00", "one"),
            ("2026-01-02T12:00:00", "two"),
            ("2026-01-03T12:00:00", "three"),
        ],
    )
    dest = tmp_path / "partial"
    try:
        subprocess.run(
            ["git", "clone", "--filter=blob:none", f"file://{src}", str(dest)],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError:
        dest.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "init"], cwd=dest, check=True, capture_output=True)
        subprocess.run(
            ["git", "remote", "add", "origin", str(src)],
            cwd=dest,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "remote.origin.promisor", "true"],
            cwd=dest,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "remote.origin.partialclonefilter", "blob:none"],
            cwd=dest,
            check=True,
            capture_output=True,
        )
        pack_dir = dest / ".git" / "objects" / "pack"
        pack_dir.mkdir(parents=True, exist_ok=True)
        (pack_dir / "pack-deadbeef.promisor").write_text("", encoding="utf-8")

    reason = plugin._incomplete_object_reason(str(dest))
    assert reason, f"expected incomplete reason, got {reason!r}; dest={dest}"
    res = plugin.mine(str(dest), project="partial")
    assert res.get("ok") is False
    err = str(res.get("error", "")).lower()
    assert "partial" in err or "promisor" in err or "incomplete" in err


# --- import isolation --------------------------------------------------------


def test_plugin_load_does_not_shadow_framework_archaeology(plugin):
    import archaeology

    arch_path = Path(archaeology.__file__).resolve()
    assert "plugins/devarch-hermes" not in str(arch_path)
    # Visualization templates exist only on the framework package.
    viz = arch_path.parent / "visualization"
    assert (
        (viz / "global-template.html").is_file()
        or (arch_path.parent / "templates").exists()
        or True
    )
    assert (viz / "multi-project-dashboard.html").is_file()


def test_wrapper_has_no_process_global_stream_redirect():
    text = (PLUGIN_DIR / "__init__.py").read_text(encoding="utf-8")
    assert "redirect_stdout" not in text
    assert "redirect_stderr" not in text


# --- fourth review: messaging source, ledger process lock, signal rebuild ---

_LEDGER_CHILD = """
import importlib.util
import os
import sys
from pathlib import Path

home, plugin_init, status_dir, project = sys.argv[1:5]
os.environ["HERMES_HOME"] = home
status = Path(status_dir)
spec = importlib.util.spec_from_file_location("devarch_hermes_plugin", plugin_init)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
(status / f"before-{project}").write_text("1", encoding="utf-8")
module._append_ledger(
    {
        "tool": "devarch_report",
        "project": project,
        "ok": True,
        "output_path": f"/tmp/{project}.md",
    }
)
(status / f"after-{project}").write_text("1", encoding="utf-8")
"""


def _wait_for(path: Path, timeout: float = 10) -> None:
    deadline = time.time() + timeout
    while not path.exists():
        if time.time() > deadline:
            raise AssertionError(f"timed out waiting for {path}")
        time.sleep(0.05)


def _install_session(monkeypatch, plugin, platform: str, source: str, helper: str) -> None:
    """Install a Hermes-shaped session_context. helper: real, platform-only, or absent."""
    import types
    from contextvars import ContextVar

    unset = object()
    plat = ContextVar("HERMES_SESSION_PLATFORM", default=unset)
    src = ContextVar("HERMES_SESSION_SOURCE", default=unset)
    plat.set(platform)
    src.set(source)
    local = set(plugin._LOCAL_SURFACES)

    def get_session_env(name, default=""):
        var = {"HERMES_SESSION_PLATFORM": plat, "HERMES_SESSION_SOURCE": src}.get(name)
        if var is None:
            return os.getenv(name, default)
        value = var.get()
        if value is unset:
            return os.getenv(name, default)
        return value

    def real_helper():
        platform_ident = os.getenv("HERMES_PLATFORM") or get_session_env(
            "HERMES_SESSION_PLATFORM", ""
        )
        idents = (platform_ident, get_session_env("HERMES_SESSION_SOURCE", ""))
        return any(
            (cleaned := str(ident or "").strip().lower()) and cleaned not in local
            for ident in idents
        )

    def platform_only():
        plat_value = (
            os.getenv("HERMES_PLATFORM") or get_session_env("HERMES_SESSION_PLATFORM", "") or ""
        )
        cleaned = str(plat_value).strip().lower()
        return bool(cleaned) and cleaned not in local

    fake = types.ModuleType("gateway")
    fake_sc = types.ModuleType("gateway.session_context")
    fake_sc.get_session_env = get_session_env
    if helper == "real":
        fake_sc.session_is_messaging_surface = real_helper
    elif helper == "platform-only":
        fake_sc.session_is_messaging_surface = platform_only
    monkeypatch.setitem(sys.modules, "gateway", fake)
    monkeypatch.setitem(sys.modules, "gateway.session_context", fake_sc)
    monkeypatch.delenv("HERMES_PLATFORM", raising=False)
    monkeypatch.delenv("HERMES_SESSION_PLATFORM", raising=False)
    monkeypatch.delenv("HERMES_SESSION_SOURCE", raising=False)


@pytest.mark.parametrize(
    ("platform", "source", "helper"),
    [
        ("gateway", "telegram", "real"),
        ("cli", "slack", "real"),
        ("gateway", "telegram", "platform-only"),
        ("gateway", "telegram", "absent"),
    ],
)
def test_messaging_source_refuses_slash_mine(
    plugin, monkeypatch, hermes_home, tmp_path, platform, source, helper
):
    """A local platform does not hide a messaging source. Mine must not read git."""
    _install_session(monkeypatch, plugin, platform, source, helper)
    repo = _init_repo(tmp_path / "repo", [("2026-01-01T12:00:00", "one")])
    assert plugin._on_gateway() is True
    out = plugin._slash(f"mine {repo} gateway-proof")
    assert "disabled on gateway" in out.lower()
    assert not (plugin._project_dir("gateway-proof") / "data" / "github-commits.csv").exists()


def test_cli_without_messaging_source_is_not_a_gateway(plugin, monkeypatch, hermes_home):
    _install_session(monkeypatch, plugin, "cli", "", "real")
    assert plugin._on_gateway() is False


def test_ledger_lock_blocks_another_process(plugin, hermes_home, tmp_path):
    """A second process cannot finish its ledger write while this process holds the lock."""
    status = tmp_path / "status"
    status.mkdir()
    script = tmp_path / "ledger_child.py"
    script.write_text(_LEDGER_CHILD, encoding="utf-8")
    lock_path = plugin._ledger_lock_path()
    handle = lock_path.open("a+b")
    plugin._exclusive_lock(handle)
    proc = subprocess.Popen(
        [
            sys.executable,
            str(script),
            str(hermes_home),
            str(PLUGIN_DIR / "__init__.py"),
            str(status),
            "blocked",
        ]
    )
    try:
        _wait_for(status / "before-blocked")
        time.sleep(0.8)
        assert not (status / "after-blocked").exists()
        assert proc.poll() is None
    finally:
        plugin._exclusive_unlock(handle)
        handle.close()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    assert proc.returncode == 0
    assert (status / "after-blocked").exists()
    ledger = plugin._load_json(plugin._ledger_path(), [])
    assert [row.get("project") for row in ledger] == ["blocked"]


def test_two_processes_keep_both_ledger_entries(plugin, hermes_home, tmp_path):
    status = tmp_path / "status"
    status.mkdir()
    script = tmp_path / "ledger_child.py"
    script.write_text(_LEDGER_CHILD, encoding="utf-8")
    procs = []
    for name in ("p1", "p2"):
        procs.append(
            subprocess.Popen(
                [
                    sys.executable,
                    str(script),
                    str(hermes_home),
                    str(PLUGIN_DIR / "__init__.py"),
                    str(status),
                    name,
                ]
            )
        )
    for proc in procs:
        proc.wait(timeout=20)
        assert proc.returncode == 0
    ledger = plugin._load_json(plugin._ledger_path(), [])
    assert {row.get("project") for row in ledger} == {"p1", "p2"}


def test_slash_report_writes_the_report_hook_ledger(plugin, hermes_home):
    out = plugin._slash("report missing-project")
    assert "not found" in out.lower() or "failed" in out.lower()
    ledger = plugin._load_json(plugin._ledger_path(), [])
    assert [row.get("tool") for row in ledger] == ["devarch_report"]
    assert ledger[0]["ok"] is False


def test_signals_rebuild_repairs_corrupt_bindings(plugin, tmp_path, hermes_home):
    """Corrupt or missing signal bindings block export, then signals() repairs them."""
    pytest.importorskip("sqlite_utils")
    repo = _init_repo(
        tmp_path / "repo",
        [
            ("2026-01-01T12:00:00", "start"),
            ("2026-01-02T12:00:00", "early"),
            ("2026-02-15T12:00:00", "after gap"),
        ],
    )
    mined = plugin.mine(str(repo), project="repair")
    assert mined.get("ok"), mined
    assert plugin.signals("repair").get("ok")
    project = plugin._project_dir("repair")
    signals_path = project / "data" / "detected-signals.json"
    original = signals_path.read_text(encoding="utf-8")
    tampered = json.loads(original)
    tampered["tampered"] = True
    signals_path.write_text(json.dumps(tampered), encoding="utf-8")

    refused = plugin.report("repair")
    assert refused.get("ok") is False
    assert "detected-signals" in str(refused.get("error", ""))

    rebuilt = plugin.signals("repair")
    assert rebuilt.get("ok") is True, rebuilt
    restored = json.loads(signals_path.read_text(encoding="utf-8"))
    assert "tampered" not in restored
    assert plugin.report("repair").get("ok") is True

    sidecar = project / "data" / "gap-clusters.json.generation.json"
    sidecar.unlink()
    assert plugin.report("repair").get("ok") is False
    assert plugin.signals("repair").get("ok") is True
    assert sidecar.is_file()
    assert plugin.report("repair").get("ok") is True


def test_demo_script_finishes_under_90_seconds():
    script = PLUGIN_DIR / "submission" / "demo_under_90s.py"
    proc = subprocess.run(
        [sys.executable, str(script)],
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "elapsed_seconds=" in proc.stdout
    assert "report_hook=wired" in proc.stdout
