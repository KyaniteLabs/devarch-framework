"""CLI project names are validated so no command can write outside projects/."""

import pytest
from click.testing import CliRunner

from archaeology.cli import main

UNSAFE = ["../escape", "a/b", "..", ".", ".hidden", "with space", "x" * 101, "trailing\n"]
COMMANDS = [
    ["init"],
    ["audit"],
    ["signals"],
    ["build-db"],
    ["demo", "--project"],
    ["public-case-study", "--project"],
    ["mine", "/nonexistent-repo", "-p"],
]


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


def test_a_leading_dash_is_rejected(workspace):
    before_parent = _tree(workspace.parent)
    result = CliRunner().invoke(main, ["init", "--", "-rf"])
    assert result.exit_code == 1, result.output
    assert "cannot start with '.' or '-'" in result.output
    assert _tree(workspace.parent) == before_parent


def test_demo_project_creation_validates_the_name_itself(tmp_path):
    from archaeology.demo import create_demo_project

    with pytest.raises(ValueError):
        create_demo_project(tmp_path, project_name="../outside")
    assert not (tmp_path / "outside").exists()


def test_safe_names_still_work(workspace):
    result = CliRunner().invoke(main, ["init", "my-project_1.0"])
    assert result.exit_code == 0, result.output
    assert (workspace / "projects" / "my-project_1.0" / "project.json").exists()
