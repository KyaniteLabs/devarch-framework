"""Validate the installed CLI's self-contained measured-history output."""

from html.parser import HTMLParser
from pathlib import Path

from ..provenance import verify_artifact


class HistoryParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = set()
        self.unsafe = False

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag)
        if tag in {"script", "iframe", "object", "embed", "form"}:
            self.unsafe = True
        if any(
            k.lower().startswith("on") or (v and v.strip().lower().startswith("javascript:"))
            for k, v in attrs
        ):
            self.unsafe = True


def validate_history(project):
    path = Path(project) / "deliverables/visuals/archaeology.html"
    if not path.is_file():
        raise ValueError("Generated history HTML missing; run visualize first")
    verify_artifact(project, path)
    parser = HistoryParser()
    parser.feed(path.read_text(encoding="utf-8"))
    parser.close()
    if parser.unsafe or not {"html", "title", "h1", "table", "caption"}.issubset(parser.tags):
        raise ValueError("Generated history HTML is incomplete or contains active content")
