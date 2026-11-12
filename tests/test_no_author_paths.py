"""No default points at the author's own folders: a path comes from a flag or an environment variable."""
import importlib.util
import os
from pathlib import Path

from click.testing import CliRunner

from archaeology.cli import main

ROOT = Path(__file__).resolve().parents[1]
AUTHOR_MARKERS = ("Desktop/OMC", "Desktop/GITHUB_pipeline", "workspaces/GITHUB_pipeline", "dev/GITHUB_pipeline",
                  "MyStuff", "-Users-user-")


def test_no_author_folder_is_named_in_the_cli_or_the_regeneration_script():
    for rel in ("archaeology/cli.py", "scripts/data/regenerate_all.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        hits = [m for m in AUTHOR_MARKERS if m in text]
        assert not hits, f"{rel} still names {hits}"


def _project(tmp_path, name):
    proj = tmp_path / "projects" / name
    (proj / "data").mkdir(parents=True)
    (proj / "project.json").write_text('{"name": "%s"}' % name)
    (proj / "data" / "archaeology.db").write_bytes(b"")
    return proj


def test_ingest_pipeline_does_not_guess_a_logs_folder_under_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / "Desktop" / "OMC" / ".omc" / "logs" / "repo-pipeline").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("ARCHAEOLOGY_PIPELINE_ROOT", raising=False)
    monkeypatch.chdir(tmp_path)
    _project(tmp_path, "np")
    result = CliRunner().invoke(main, ["ingest-pipeline", "np"])
    assert result.exit_code != 0
    assert "--logs-dir" in result.output and "ARCHAEOLOGY_PIPELINE_ROOT" in result.output


def test_ingest_pipeline_reads_the_logs_under_archaeology_pipeline_root(tmp_path, monkeypatch):
    root = tmp_path / "pipe"
    logs = root / ".omc" / "logs" / "repo-pipeline"
    logs.mkdir(parents=True)
    seen = {}

    def fake_ingest(db, directory, verbose=False):
        seen["dir"] = Path(directory)
        return {"ingested": 0, "skipped": 0, "errors": []}

    monkeypatch.setattr("archaeology.db.pipeline_ingest.ingest_directory", fake_ingest)
    monkeypatch.setenv("ARCHAEOLOGY_PIPELINE_ROOT", str(root))
    monkeypatch.chdir(tmp_path)
    _project(tmp_path, "np2")
    result = CliRunner().invoke(main, ["ingest-pipeline", "np2"])
    assert result.exit_code == 0, result.output
    assert seen["dir"] == logs


def _regen(monkeypatch):
    monkeypatch.setenv("ARCHAEOLOGY_SOURCE_REPO", str(ROOT))
    spec = importlib.util.spec_from_file_location("regen_under_test", ROOT / "scripts" / "data" / "regenerate_all.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_private_mining_runs_nothing_unless_asked_for_specific_inputs(monkeypatch):
    mod = _regen(monkeypatch)
    ran = []
    monkeypatch.setattr(mod, "run", lambda cmd, **kw: ran.append(cmd) or "")
    mod.mine_private_sessions(ROOT)
    assert ran == []


def test_private_mining_uses_the_dirs_and_export_given_on_the_command_line(monkeypatch, tmp_path):
    mod = _regen(monkeypatch)
    ran = []
    monkeypatch.setattr(mod, "run", lambda cmd, **kw: ran.append(cmd) or "")
    mod.mine_private_sessions(ROOT, claude_sessions=[(str(tmp_path / "s1"), "one")],
                              chatgpt_export=str(tmp_path / "c.json"))
    flat = [" ".join(map(str, c)) for c in ran]
    assert any("claude" in f and str(tmp_path / "s1") in f and "--prefix one" in f for f in flat)
    assert any("chatgpt" in f and str(tmp_path / "c.json") in f for f in flat)
    assert len(ran) == 2
