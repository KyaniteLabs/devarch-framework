#!/usr/bin/env python3
"""Capture the current playbook into the repo's PNG artifacts.

This intentionally uses the Playwright CLI through `npx playwright screenshot`
instead of a project-local Node dependency, so the capture path works in this
repo without adding package.json dependencies.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import socketserver
import subprocess
import sys
import threading
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DELIVERABLES = ROOT / "projects/liminal/deliverables"


def screenshot(url: str, output: Path, *, full_page: bool = False) -> None:
    cmd = [
        "npx",
        "--yes",
        "playwright",
        "screenshot",
        "--browser",
        "chromium",
        "--viewport-size",
        "1200,1479",
        "--wait-for-timeout",
        "1500",
    ]
    if full_page:
        cmd.append("--full-page")
    cmd.extend([url, str(output)])
    subprocess.run(cmd, check=True, timeout=120)


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture playbook screenshots.")
    parser.add_argument("--deliverables", type=Path, default=DELIVERABLES)
    parser.add_argument("--output-root", type=Path, default=ROOT)
    parser.add_argument("--port", type=int, default=4177)
    args = parser.parse_args()

    deliverables = args.deliverables.resolve()
    if not (deliverables / "playbook.html").exists():
        raise SystemExit(f"playbook.html not found under {deliverables}")

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(deliverables))
    with socketserver.TCPServer(("127.0.0.1", args.port), handler) as httpd:
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{args.port}/playbook.html"

        captures = [
            (base, "arch-top.png", False),
            (base, "archaeology-header.png", False),
            (base + "#ch-eras", "arch-eras.png", False),
            (base + "#ch-meta-patterns", "meta-patterns.png", False),
            (base, "archaeology-full-page.png", True),
        ]
        try:
            for url, filename, full_page in captures:
                output = args.output_root / filename
                screenshot(url, output, full_page=full_page)
                print(f"captured {output.relative_to(ROOT)}")
        finally:
            httpd.shutdown()
            thread.join(timeout=5)

    return 0


if __name__ == "__main__":
    sys.exit(main())
