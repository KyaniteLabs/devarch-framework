"""L-F2: which environment variables reach the DevArch child, and that the docs say so."""

import importlib.util
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("ag4te_lf2_under_test", PKG / "__init__.py")
ag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ag)

SENTINEL = "SENTINEL-do-not-leak"
# Code-injection and secret-bearing variables: none of these may reach the child.
BLOCKED = (
    "PYTHONSTARTUP", "PYTHONPATH", "PYTHONHOME", "PYTHONUSERBASE", "PYTHONINSPECT",
    "NODE_OPTIONS", "NODE_PATH", "NPM_CONFIG_USERCONFIG", "NPM_CONFIG_REGISTRY",
    "LD_PRELOAD", "LD_LIBRARY_PATH", "DYLD_INSERT_LIBRARIES", "DYLD_LIBRARY_PATH",
    "BASH_ENV", "ENV", "GIT_ASKPASS", "GIT_SSH_COMMAND", "GIT_CONFIG_GLOBAL",
    "GITHUB_TOKEN", "GH_TOKEN", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
    "UV_PUBLISH_TOKEN", "UV_INDEX_PRIVATE_PASSWORD", "UV_INDEX", "UV_DEFAULT_INDEX",
    "UV_CONSTRAINT", "UV_OVERRIDE", "UV_NO_CONFIG", "UV_PYTHON_INSTALL_MIRROR",
    "PIP_EXTRA_INDEX_URL", "PIP_CONFIG_FILE", "PIP_REQUIRE_VIRTUALENV",
)


def test_code_injection_and_secret_variables_never_reach_the_child(tmp_path, monkeypatch):
    for name in BLOCKED:
        monkeypatch.setenv(name, SENTINEL)
    env = ag._scrubbed_env({"data_dir": str(tmp_path)})
    leaked = sorted(k for k in BLOCKED if k in env)
    assert not leaked, leaked
    assert SENTINEL not in "".join(env.values())


def test_only_the_documented_fetch_variables_carry_package_manager_settings(tmp_path, monkeypatch):
    for name in ag.FETCH_ENV:
        monkeypatch.setenv(name, SENTINEL)
    env = ag._scrubbed_env({"data_dir": str(tmp_path)})
    assert {k for k, v in env.items() if v == SENTINEL} == set(ag.FETCH_ENV)
    assert not set(ag.FETCH_ENV) & set(BLOCKED)


def test_readme_and_manifest_name_every_package_manager_variable():
    readme = (PKG / "README.md").read_text(encoding="utf-8")
    manifest = (PKG / "plugin.yaml").read_text(encoding="utf-8")
    for name in ag.FETCH_ENV:
        assert name in readme, f"README.md does not mention {name}"
        assert name in manifest, f"plugin.yaml does not mention {name}"
    assert "PYTHONSTARTUP" in readme and "PYTHONPATH" in readme and "NODE_OPTIONS" in readme
