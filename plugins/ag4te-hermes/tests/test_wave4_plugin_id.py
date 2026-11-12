"""The plugin id comes from plugin.yaml, not from a literal, so a renamed install keeps its own settings and data."""

import importlib.util
import shutil
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _renamed_copy(tmp_path, new_name):
    dst = tmp_path / "plug"
    shutil.copytree(PKG, dst, ignore=shutil.ignore_patterns("tests", "__pycache__", "desktop", "docs"))
    manifest = dst / "plugin.yaml"
    manifest.write_text(manifest.read_text().replace("name: ag4te\n", f"name: {new_name}\n", 1))
    return dst


def test_shipped_manifest_still_gives_ag4te():
    assert _load("ag4te_w4_id_a", PKG / "__init__.py").PLUGIN_NAME == "ag4te"
    assert _load("ag4te_w4_id_b", PKG / "dashboard" / "plugin_api.py").PLUGIN_ID == "ag4te"


def test_id_follows_the_manifest_name(tmp_path):
    dst = _renamed_copy(tmp_path, "ag4te-alias")
    mod = _load("ag4te_w4_id_c", dst / "__init__.py")
    api = _load("ag4te_w4_id_d", dst / "dashboard" / "plugin_api.py")
    assert mod.PLUGIN_NAME == "ag4te-alias"
    assert api.PLUGIN_ID == "ag4te-alias"
    assert mod.workspace({}).name == "ag4te-alias"


def test_missing_manifest_falls_back_to_ag4te(tmp_path):
    dst = _renamed_copy(tmp_path, "x")
    (dst / "plugin.yaml").unlink()
    assert _load("ag4te_w4_id_e", dst / "__init__.py").PLUGIN_NAME == "ag4te"
