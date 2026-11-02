"""Regression tests for the QA failures found after PR #90 (card t_7f6ca03f).

D1: global-viz / multi-project-dashboard must resolve their templates
    against the installed package, not the CWD.
D2: sync must accept the README-documented "path" profile key and reject
    malformed entries with an actionable error instead of a KeyError traceback.
D3: serve must pass datasette's --setting as two arguments so the server boots.
"""

import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
from click.testing import CliRunner

from archaeology import cli
from archaeology.cli import main

REPO_PROFILE = os.path.abspath(str(Path(cli.__file__).parent.parent / "config" / "profile.json"))


def _hide_repo_profile(monkeypatch):
    """Force sync to fall back to ./config/profile.json in the test cwd."""
    real_exists = os.path.exists
    monkeypatch.setattr(
        os.path,
        "exists",
        lambda p: False if os.path.abspath(str(p)) == REPO_PROFILE else real_exists(p),
    )


def _write_profile(root: Path, profile: dict):
    config_dir = root / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "profile.json").write_text(json.dumps(profile), encoding="utf-8")


def _make_serve_project(root: Path, name: str = "serve-proj") -> Path:
    proj_dir = root / "projects" / name / "data"
    proj_dir.mkdir(parents=True)
    db_path = proj_dir / "archaeology.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE commits (sha TEXT, author TEXT, date TEXT)")
    conn.execute("INSERT INTO commits VALUES ('abc123', 'simon', '2026-01-01T00:00:00Z')")
    conn.commit()
    conn.close()
    return db_path


# ── D1: package-relative template resolution ──────────────────────────────────


@pytest.mark.parametrize(
    "template",
    ["global-template.html", "multi-project-dashboard.html"],
)
def test_viz_templates_resolve_inside_the_package(template):
    resolved = cli._viz_template_path(template)
    pkg_dir = Path(cli.__file__).parent
    assert resolved == pkg_dir / "visualization" / template
    assert resolved.is_file()


def _write_global_data(root: Path):
    data_dir = root / "global" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "github-repos.json").write_text(
        json.dumps(
            {
                "repos": [
                    {
                        "name": "demo",
                        "total_commits": 3,
                        "created": "2026-01-01T00:00:00Z",
                        "updated": "2026-01-02T00:00:00Z",
                        "authors": {"simon": 3},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def test_global_viz_works_from_non_repo_cwd(tmp_path, monkeypatch):
    """CWD has no archaeology/ dir, so a CWD-relative lookup cannot succeed."""
    monkeypatch.chdir(tmp_path)
    _write_global_data(tmp_path)

    result = CliRunner().invoke(main, ["global-viz", "--output", "out-global"])

    assert result.exit_code == 0, result.output
    assert "Global visualization generated at" in result.output
    html = (tmp_path / "out-global" / "global.html").read_text(encoding="utf-8")
    assert "window.GLOBAL_DATA = {" in html


def test_multi_project_dashboard_works_from_non_repo_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_global_data(tmp_path)

    result = CliRunner().invoke(main, ["multi-project-dashboard", "--output", "dash-out"])

    assert result.exit_code == 0, result.output
    assert "Multi-project dashboard generated at" in result.output
    html = (tmp_path / "dash-out" / "dashboard.html").read_text(encoding="utf-8")
    assert "window.DASHBOARD_DATA = {" in html


# ── D2: profile schema handling in sync ───────────────────────────────────────


def _make_git_repo(path: Path):
    path.mkdir(parents=True)
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "qa",
        "GIT_AUTHOR_EMAIL": "qa@example.com",
        "GIT_COMMITTER_NAME": "qa",
        "GIT_COMMITTER_EMAIL": "qa@example.com",
    }
    subprocess.run(["git", "init", "-q"], cwd=str(path), check=True, env=env)
    (path / "file.txt").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "file.txt"], cwd=str(path), check=True, env=env)
    subprocess.run(
        ["git", "commit", "-q", "-m", "first", "--date", "2026-01-01T00:00:00Z"],
        cwd=str(path),
        check=True,
        env=env,
    )
    return path


def test_sync_accepts_readme_documented_path_key(tmp_path, monkeypatch):
    """The exact README example ({"name": ..., "path": ...}) must sync, exit 0."""
    monkeypatch.chdir(tmp_path)
    _hide_repo_profile(monkeypatch)
    repo = _make_git_repo(tmp_path / "source" / "qa-proj")
    _write_profile(
        tmp_path,
        {
            "projects": [{"name": "qa-proj", "path": str(repo)}],
            "sync": {"run_signals": False, "run_analysis": False},
        },
    )

    result = CliRunner().invoke(main, ["sync", "--project", "qa-proj"])

    assert result.exit_code == 0, result.output
    assert "Sync complete." in result.output
    project_config = json.loads(
        (tmp_path / "projects" / "qa-proj" / "project.json").read_text(encoding="utf-8")
    )
    assert project_config["repo_path"] == str(repo)


def test_sync_rejects_missing_repo_key_with_actionable_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _hide_repo_profile(monkeypatch)
    _write_profile(tmp_path, {"projects": [{"name": "qa-proj"}]})

    result = CliRunner().invoke(main, ["sync", "--project", "qa-proj"])

    assert result.exit_code == 1
    assert "Traceback" not in result.output
    assert "qa-proj" in result.output
    assert "repo_path" in result.output


def test_sync_rejects_missing_name_with_actionable_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _hide_repo_profile(monkeypatch)
    _write_profile(tmp_path, {"projects": [{"repo_path": "/tmp/x"}]})

    result = CliRunner().invoke(main, ["sync"])

    assert result.exit_code == 1
    assert "Traceback" not in result.output
    assert "'name'" in result.output


def test_sync_rejects_non_object_entry_with_actionable_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _hide_repo_profile(monkeypatch)
    _write_profile(tmp_path, {"projects": ["just-a-string"]})

    result = CliRunner().invoke(main, ["sync"])

    assert result.exit_code == 1
    assert "Traceback" not in result.output
    assert "projects[0]" in result.output


# ── D3: datasette --setting argument form ─────────────────────────────────────


def test_serve_builds_two_argument_setting_flag(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_serve_project(tmp_path)
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = list(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    result = CliRunner().invoke(main, ["serve", "serve-proj", "--port", "8123"])

    assert result.exit_code == 0, result.output
    assert "Launching Datasette at http://localhost:8123" in result.output
    cmd = captured["cmd"]
    setting_at = cmd.index("--setting")
    assert cmd[setting_at + 1] == "sql_time_limit_ms"
    assert cmd[setting_at + 2] == "5000"
    assert "," not in cmd[setting_at + 1]


@pytest.mark.skipif(os.name == "nt", reason="POSIX process control; unit test covers Windows")
def test_serve_smoke_boots_datasette_and_serves_http_200(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_serve_project(tmp_path)

    sock = socket.socket()
    sock.bind(("localhost", 0))
    port = sock.getsockname()[1]
    sock.close()

    # `serve` shells out to the `datasette` console script, so make sure the
    # bin dir of the running interpreter (where it was installed) is on PATH.
    child_env = {
        **os.environ,
        "PATH": os.pathsep.join([os.path.dirname(sys.executable), os.environ.get("PATH", "")]),
    }

    proc = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "from archaeology.cli import main; main()",
            "serve",
            "serve-proj",
            "--port",
            str(port),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=child_env,
    )
    try:
        deadline = time.monotonic() + 60
        last_error = None
        served = False
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                output = proc.stdout.read() if proc.stdout else ""
                pytest.fail(f"serve exited early with {proc.returncode}:\n{output}")
            try:
                with urllib.request.urlopen(f"http://localhost:{port}/", timeout=2) as resp:
                    if resp.status == 200:
                        served = True
                        break
            except Exception as exc:  # server not up yet
                last_error = exc
                time.sleep(0.5)
        assert served, f"datasette never answered on port {port}: {last_error}"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
