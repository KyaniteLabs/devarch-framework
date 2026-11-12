"""CI installs its own tooling (pip, build, twine) at exact versions, so a new release cannot change a build unseen."""
import re
from pathlib import Path

WORKFLOWS = Path(__file__).resolve().parents[1] / ".github" / "workflows"
TOOLS = {"pip", "build", "twine", "uv"}


def _install_lines():
    for wf in sorted(WORKFLOWS.glob("*.yml")):
        for n, line in enumerate(wf.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"\bpip install\b", line):
                yield wf.name, n, line.strip()


def test_ci_tooling_is_pinned_to_exact_versions():
    unpinned = []
    for name, n, line in _install_lines():
        for token in line.split("pip install", 1)[1].split():
            if token.startswith("-"):
                if token == "--upgrade":
                    unpinned.append(f"{name}:{n} uses --upgrade: {line}")
                continue
            if token in TOOLS:
                unpinned.append(f"{name}:{n} {token} has no ==version: {line}")
    assert not unpinned, "\n".join(unpinned)


def test_the_pinned_tooling_is_actually_installed_somewhere():
    text = "\n".join(wf.read_text(encoding="utf-8") for wf in WORKFLOWS.glob("*.yml"))
    for pin in ("pip==", "build==", "twine=="):
        assert pin in text, pin
