"""Interface tests for the serve/cascade/sync pipeline verbs.

The adapter characterization (``test_pipeline_contract.py``) pins the CLI
transcript byte-for-byte, including for these verbs, but ``sync``'s full flow
can only run there as an error path: the verb resolves its profile from the
package's ``config/profile.json`` first, which names the developer's real
projects. These tests drive the service directly with a hermetic profile.
Nothing is mocked except the Datasette launch.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

from archaeology import pipeline
from archaeology.pipeline import PipelineError, ProjectRef

GIT_ENV = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
}


def _make_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    env = {
        **os.environ,
        **GIT_ENV,
        "GIT_AUTHOR_NAME": "T",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "T",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    }

    def git(*args, date=None):
        full = {"GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date} if date else {}
        subprocess.run(
            ["git", "-C", str(path), *args], check=True, env={**env, **full}, capture_output=True
        )

    git("init", "-q", "-b", "main")
    for i, day in enumerate(("2026-01-01", "2026-01-02", "2026-02-20")):
        (path / f"f{i}.txt").write_text(f"change {i}\n")
        git("add", "-A")
        git("commit", "-q", "-m", f"commit {i}", date=f"{day}T12:00:00+0000")
    return path


class Lines:
    """on_line collector: (text, err) pairs."""

    def __init__(self):
        self.items = []

    def __call__(self, text, err=False):
        self.items.append((text, err))

    def text(self):
        return "\n".join(t for t, _ in self.items)


# ── sync ───────────────────────────────────────────────────────────────────────


def _profile(root: Path, repo: Path) -> Path:
    profile = root / "profile.json"
    profile.write_text(
        json.dumps(
            {
                "developer": {"name": "T"},
                "sync": {"run_signals": True, "run_analysis": False, "default_min_gap_days": 3},
                "projects": [{"name": "demo", "repo_path": str(repo)}],
            }
        ),
        encoding="utf-8",
    )
    return profile


def test_sync_full_flow_hermetic_profile(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path / "repo")
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.chdir(ws)
    monkeypatch.delenv("DEVARCH_WORKSPACE", raising=False)

    lines = Lines()
    outcome = pipeline.sync(["demo"], profile_path=str(_profile(tmp_path, repo)), on_line=lines)
    assert outcome.exit_code == 0
    text = lines.text()
    assert "Syncing 1 project(s)..." in text
    assert "  Mining demo..." in text
    assert "    3 commits extracted" in text
    assert "  Building DB for demo..." in text
    assert "    DB built" in text
    assert "  Detecting signals for demo..." in text
    assert "Sync complete." in text

    # the project was initialized from the profile and fully populated
    proj = ws / "projects" / "demo"
    assert (proj / "project.json").exists()
    assert (proj / "data" / "github-commits.csv").exists()
    assert (proj / "data" / "archaeology.db").exists()
    assert (proj / "data" / "detected-signals.json").exists()

    # global aggregation ran
    gdata = ws / "global" / "data"
    assert (gdata / "global-commits.csv").exists()
    assert (gdata / "project-summaries.json").exists()
    assert (gdata / "global.db").exists()
    summaries = json.loads((gdata / "project-summaries.json").read_text())
    assert summaries[0]["name"] == "demo"
    assert summaries[0]["total_commits"] == 3


def test_sync_missing_profile_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    lines = Lines()
    outcome = pipeline.sync(["demo"], profile_path=str(tmp_path / "nope.json"), on_line=lines)
    assert outcome.exit_code == 1
    assert lines.items == [
        (
            "No profile.json found. Create one at config/profile.json with your project list.",
            True,
        )
    ]


def test_sync_skip_mine_skips_extraction_but_builds(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path / "repo")
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.chdir(ws)
    # pre-mined data, so the build can run without mining
    pipeline.init(ProjectRef.for_cli("demo", must_exist=False), "d", "")
    pipeline.mine(str(repo), ProjectRef.for_cli("demo"), expand_repo_path=False)

    lines = Lines()
    outcome = pipeline.sync(
        ["demo"], skip_mine=True, profile_path=str(_profile(tmp_path, repo)), on_line=lines
    )
    assert outcome.exit_code == 0
    text = lines.text()
    assert "Mining demo..." not in text
    assert "Building DB for demo..." in text


# ── serve ──────────────────────────────────────────────────────────────────────


def test_prepare_serve_requires_database(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DEVARCH_WORKSPACE", raising=False)
    ref = ProjectRef.for_cli("empty", must_exist=False)
    pipeline.init(ref, "d", "")
    with pytest.raises(PipelineError) as exc:
        pipeline.prepare_serve(ref, 8001, False)
    assert exc.value.kind == "no-database"
    assert str(exc.value) == (
        f"Database not found at {os.path.join('projects', 'empty', 'data', 'archaeology.db')}. "
        "Run 'devarch build-db empty' first."
    )


def test_prepare_serve_builds_command_and_metadata(tmp_path, monkeypatch):
    repo = _make_repo(tmp_path / "repo")
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.chdir(ws)
    monkeypatch.delenv("DEVARCH_WORKSPACE", raising=False)
    ref = ProjectRef.for_cli("alpha", must_exist=False)
    pipeline.init(ref, "Alpha", "https://example.com/a")
    pipeline.mine(str(repo), ref, expand_repo_path=False)
    pipeline.build_db(ref)
    (ws / "config").mkdir()
    (ws / "config" / "datasette-metadata.yaml").write_text(
        'title: "Archaeology Database"\ndescription: test\n', encoding="utf-8"
    )

    launch = pipeline.prepare_serve(ref, 8123, True)
    assert launch.cmd[0] == "datasette"
    assert launch.db_path == os.path.join("projects", "alpha", "data", "archaeology.db")
    assert launch.cmd[1] == launch.db_path
    assert "--port" in launch.cmd and "8123" in launch.cmd
    assert "--cors" in launch.cmd
    assert launch.temp_metadata is True
    content = Path(launch.metadata_src).read_text(encoding="utf-8")
    assert 'title: "ALPHA Archaeology Database"' in content
    Path(launch.metadata_src).unlink()

    plain = pipeline.prepare_serve(ref, 8124, False)
    assert "--cors" not in plain.cmd

    # a project-specific metadata file wins over the workspace default and
    # is used in place (no temp copy, nothing to clean up)
    proj_meta = ws / "projects" / "alpha" / "datasette-metadata.yaml"
    proj_meta.write_text('title: "Alpha custom"\n', encoding="utf-8")
    own = pipeline.prepare_serve(ref, 8125, False)
    i = own.cmd.index("--metadata") + 1
    assert own.cmd[i] == os.path.join("projects", "alpha", "datasette-metadata.yaml")
    assert own.temp_metadata is False


# ── cascade ────────────────────────────────────────────────────────────────────


def test_cascade_returns_exit_verdict_without_raising(tmp_path, monkeypatch):
    """Missing eras emits the transcript and reports exit 1 instead of raising."""
    repo = _make_repo(tmp_path / "repo")
    ws = tmp_path / "ws"
    ws.mkdir()
    monkeypatch.chdir(ws)
    monkeypatch.delenv("DEVARCH_WORKSPACE", raising=False)
    ref = ProjectRef.for_cli("alpha", must_exist=False)
    pipeline.init(ref, "Alpha", "")
    pipeline.mine(str(repo), ref, expand_repo_path=False)

    lines = Lines()
    outcome = pipeline.cascade(ref, on_line=lines)
    assert outcome.exit_code == 1
    assert "ERROR: No commit-eras.json found at" in lines.text()
