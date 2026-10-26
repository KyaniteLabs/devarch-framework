"""CLI project names are validated so no command can write outside projects/."""

import pytest
from click.testing import CliRunner

from archaeology.cli import main

UNSAFE = ["../escape", "a/b", "..", "with space", "x" * 101]
COMMANDS = [["init"], ["audit"], ["signals"], ["build-db"], ["demo", "--project"]]


def _tree(root):
    return sorted(str(p.relative_to(root)) for p in root.rglob("*"))


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    root = tmp_path / "ws"
    (root / "projects").mkdir(parents=True)
    monkeypatch.chdir(root)
    return root


@pytest.mark.parametrize("name", UNSAFE)
@pytest.mark.parametrize("argv", COMMANDS)
def test_unsafe_names_are_rejected_before_any_write(workspace, argv, name):
    before_parent = _tree(workspace.parent)
    result = CliRunner().invoke(main, [*argv, name])
    assert result.exit_code == 1, result.output
    assert "Error: Project name" in result.output
    # Nothing was created anywhere: not in the workspace, not beside it.
    assert _tree(workspace.parent) == before_parent


def test_safe_names_still_work(workspace):
    result = CliRunner().invoke(main, ["init", "my-project_1.0"])
    assert result.exit_code == 0, result.output
    assert (workspace / "projects" / "my-project_1.0" / "project.json").exists()
