"""The README may not say "fully local / no external services" while generated pages load a CDN."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_readme_does_not_overclaim_local_only():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert not re.search(r"fully local|no external services|no cloud api calls", text, re.I), (
        "the generated HTML pages load Chart.js, d3 and fonts from a CDN"
    )


def test_readme_says_where_the_network_is_used():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert re.search(r"CDN", text) and re.search(r"Chart\.js", text)
    assert re.search(r"mining and analysis (run|happen)s? (entirely )?(locally|on your machine)", text, re.I)
