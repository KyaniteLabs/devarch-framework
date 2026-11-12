"""A4: the embedded desktop fonts travel with their licence text and a NOTICE."""

import re
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
FONT_COPYRIGHT = (
    "Copyright 2018 The Chakra Petch Project Authors (https://github.com/m4rc1e/Chakra-Petch.git)"
)


def test_ofl_text_ships_with_the_fonts():
    text = (PKG / "desktop" / "fonts" / "OFL.txt").read_text(encoding="utf-8")
    assert FONT_COPYRIGHT in text
    assert "SIL OPEN FONT LICENSE Version 1.1" in text


def test_notice_names_the_family_and_its_copyright():
    notice = (PKG / "NOTICE").read_text(encoding="utf-8")
    assert "Chakra Petch" in notice
    assert FONT_COPYRIGHT in notice
    assert "OFL" in notice


def test_notice_covers_every_embedded_font_face():
    js = (PKG / "desktop" / "plugin.js").read_text(encoding="utf-8")
    assert re.search(r"@font-face\{font-family:.AG Chakra.", js)
    notice = (PKG / "NOTICE").read_text(encoding="utf-8")
    # The embedded subset is renamed "AG Chakra"; the notice must say which family it came from.
    assert "AG Chakra" in notice
