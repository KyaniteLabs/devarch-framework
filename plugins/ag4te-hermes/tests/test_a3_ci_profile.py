"""A3: the Forgejo CI profile lints and tests the plugin, not just the repo root."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PLUGIN = "plugins/ag4te-hermes"


def _steps():
    profile = json.loads((ROOT / ".ci" / "profile.json").read_text(encoding="utf-8"))
    return {s["phase"] + ":" + s["name"]: s["argv"] for s in profile["steps"]}, profile


def test_profile_lints_the_plugin():
    steps, _ = _steps()
    ruff = [a for a in steps.values() if a[0].endswith("ruff")]
    # Same commands as GitHub CI: a full-repo check (covers the plugin) and a format check.
    assert [".venv/bin/ruff", "check", "."] in ruff
    assert [".venv/bin/ruff", "format", "--check", "."] in ruff


def test_profile_runs_the_plugin_tests():
    steps, profile = _steps()
    pytest_argv = next(a for a in steps.values() if "pytest" in a)
    assert f"{PLUGIN}/tests" in pytest_argv
    assert f"{PLUGIN}/tests/test_*.py" in profile["test_globs"]
    assert (ROOT / PLUGIN / "tests").is_dir()
