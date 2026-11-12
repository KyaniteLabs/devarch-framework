"""L-F3 / F32: the default DevArch command pins the dependency closure with a constraints file."""

import importlib.util
import re
import shlex
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("ag4te_lf3_under_test", PKG / "__init__.py")
ag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ag)

LOCK = PKG / "devarch-constraints.txt"


def test_default_command_line_uses_the_constraints_file():
    argv = shlex.split(ag.DEFAULTS["devarch_command"])
    assert argv[0] == "uvx"
    i = argv.index("--constraints")
    assert Path(argv[i + 1]) == LOCK and Path(argv[i + 1]).is_absolute()
    assert argv[argv.index("--from") + 1].endswith(f"@{ag.DEVARCH_PIN}")
    assert argv[-1] == "devarch"


def test_constraints_pin_every_package_exactly_for_this_devarch_commit():
    text = LOCK.read_text(encoding="utf-8")
    assert ag.DEVARCH_PIN in text.split("\n\n")[0] or ag.DEVARCH_PIN in text[:600]
    pins = [line for line in text.splitlines() if line and not line.startswith("#")]
    assert len(pins) >= 30
    for line in pins:
        assert re.match(r"^[A-Za-z0-9_.-]+==[0-9][^ ;]*( ; .+)?$", line), line
    names = {p.split("==")[0].lower() for p in pins}
    assert {"click", "sqlite-utils", "datasette"} <= names
    assert not any("@" in p or "git+" in p for p in pins)  # no unpinned URLs


def test_every_default_setting_still_parses():
    shlex.split(ag.DEFAULTS["devarch_command"])
