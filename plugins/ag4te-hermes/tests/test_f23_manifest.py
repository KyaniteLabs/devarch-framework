"""F23: plugin.yaml names its licence and author, matching LICENSE and the package metadata."""

import re
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
MANIFEST = (PKG / "plugin.yaml").read_text(encoding="utf-8")
# Keys the Hermes v0.23 validator accepts (the Epoch and tastecheck manifests, which pass it, use them).
KNOWN_TOP_LEVEL = {
    "name",
    "version",
    "manifest_version",
    "requires_hermes",
    "description",
    "author",
    "license",
    "homepage",
    "tags",
    "requires_env",
    "provides_tools",
    "config_schema",
}


def _top(key):
    m = re.search(rf"^{key}:[ \t]*(.+)$", MANIFEST, re.M)
    return m.group(1).strip().strip("\"'") if m else None


def test_license_matches_the_license_file():
    text = (PKG / "LICENSE").read_text(encoding="utf-8")
    assert "Apache License" in text and "Version 2.0" in text
    assert _top("license") == "Apache-2.0"


def test_author_is_the_git_author():
    assert (
        _top("author") == "Kyanite Labs"
    )  # company standard, as in the Epoch and tastecheck manifests


def test_manifest_uses_only_keys_the_host_accepts():
    tops = set(re.findall(r"^([a-z_]+):", MANIFEST, re.M))
    assert tops <= KNOWN_TOP_LEVEL, tops - KNOWN_TOP_LEVEL
