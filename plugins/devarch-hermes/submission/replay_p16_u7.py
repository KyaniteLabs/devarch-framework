"""Installed-wheel replay of the published P16/U7 benchmark contract.

PR #93 counted 89 commit rows, one normalized agent, and the date range
2026-04-29 to 2026-11-03. The retained Product QA database is not in this
repository, so this script rebuilds that contract with the date forms the
fix had to accept (ISO-8601 Z, numeric offset, and legacy Git-log dates),
installs a fresh wheel, and runs `devarch benchmark demo-archaeology`.

It does not publish, open a pull request, or contact a Hermes host.
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path

ROWS = 89
START = date(2026, 4, 29)
END = date(2026, 11, 3)
REPO_ROOT = Path(__file__).resolve().parents[3]
RECEIPT = Path(__file__).resolve().parent / "P16-U7-RECEIPT.md"


def _rows() -> list[tuple[str, str, str, str]]:
    span = (END - START).days
    days = [START + timedelta(days=round(index * span / (ROWS - 1))) for index in range(ROWS)]
    formats = (
        lambda day: f"{day.isoformat()}T01:52:23+00:00",
        lambda day: f"{day.isoformat()}T01:52:23Z",
        lambda day: f"{day.isoformat()}T10:30:00-07:00",
        lambda day: f"{day.isoformat()} 21:30:56 -0700",
    )
    return [
        (f"c{index:03d}", formats[index % len(formats)](day), "qa commit", "Claude 3.7")
        for index, day in enumerate(days)
    ]


def _clean_env() -> dict[str, str]:
    """Drop checkout injection so the wheel is what the fresh venv imports."""
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env.pop("PYTHONHOME", None)
    return env


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        cmd,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        env=_clean_env(),
    )
    if result.returncode != 0:
        raise RuntimeError(f"{cmd} exited {result.returncode}\n{result.stdout}\n{result.stderr}")
    return result


def _write_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE commits (hash TEXT, date TEXT, message TEXT, author TEXT)")
        connection.executemany("INSERT INTO commits VALUES (?, ?, ?, ?)", _rows())


def _receipt(text: str, destination: Path) -> None:
    destination.write_text(text, encoding="utf-8")
    print(destination)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    args = parser.parse_args()
    started = time.perf_counter()
    head = _run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT).stdout.strip()
    with tempfile.TemporaryDirectory(prefix="devarch-p16-") as temporary:
        root = Path(temporary)
        wheels = root / "wheels"
        _run(
            [sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(wheels), str(REPO_ROOT)],
            cwd=REPO_ROOT,
        )
        wheel = next(wheels.glob("devarch_framework-*.whl"))
        venv = root / "venv"
        _run([sys.executable, "-m", "venv", str(venv)])
        bindir = "Scripts" if sys.platform == "win32" else "bin"
        py = venv / bindir / "python"
        _run([str(py), "-m", "pip", "install", str(wheel)])
        identity = json.loads(
            _run(
                [
                    str(py),
                    "-c",
                    "import archaeology, json, importlib.metadata as meta; "
                    "print(json.dumps({'path': archaeology.__file__, "
                    "'version': meta.version('devarch-framework')}))",
                ],
                cwd=root,
            ).stdout
        )
        installed = Path(identity["path"]).resolve()
        if REPO_ROOT in installed.parents:
            raise RuntimeError(f"wheel import still points at the checkout: {installed}")
        workspace = root / "work"
        db_path = workspace / "projects" / "demo-archaeology" / "data" / "archaeology.db"
        _write_db(db_path)
        benchmark = _run(
            [str(venv / bindir / "devarch"), "benchmark", "demo-archaeology"],
            cwd=workspace,
        )
        html_path = (
            workspace
            / "projects"
            / "demo-archaeology"
            / "deliverables"
            / "visuals"
            / "agent-benchmark.html"
        )
        html = html_path.read_text(encoding="utf-8")
        analyzed = json.loads(
            _run(
                [
                    str(py),
                    "-c",
                    "import json, sys; "
                    "from archaeology.visualization.agent_benchmark import analyze_agent_benchmarks; "
                    "result = analyze_agent_benchmarks(sys.argv[1]); "
                    "print(json.dumps({'meta': result['meta'], "
                    "'agent_commits': [a['total_commits'] for a in result['agents']], "
                    "'agents': [a['name'] for a in result['agents']]}))",
                    str(db_path),
                ],
                cwd=workspace,
            ).stdout
        )
        versions = _run(
            [str(py), "-m", "pip", "show", "devarch-framework", "click", "sqlite-utils"]
        ).stdout
        elapsed = time.perf_counter() - started
        meta = analyzed["meta"]
        agent_sum = sum(analyzed["agent_commits"])
        ok = (
            meta["total_commits"] == ROWS
            and agent_sum == ROWS
            and meta["total_agents"] == 1
            and analyzed["agents"] == ["Claude"]
            and meta["date_range"] == "2026-04-29 to 2026-11-03"
            and '<div class="stat-value">89</div>' in html
            and "2026-04-29" in html
            and "2026-11-03" in html
        )
        receipt = "\n".join(
            [
                "# P16/U7 installed-wheel replay",
                "",
                "Status: **pass**" if ok else "Status: **fail**",
                "",
                "This is the published P16/U7 contract from PR #93, replayed on an installed wheel.",
                "The retained Product QA database is not in this repository. The fixture is 89",
                "rows for `demo-archaeology`, one author (`Claude 3.7` → Claude), and mixed",
                "ISO-8601 `Z` / offset dates plus legacy Git-log dates from 2026-04-29 to 2026-11-03.",
                "",
                f"- git HEAD at runtime: `{head}`",
                "- That SHA is the tree that was wheeled. A later commit that only adds this receipt does not change the analyzer.",
                f"- wheel: `{wheel.name}`",
                f"- installed archaeology: `{installed}`",
                f"- analyzer total_commits: {meta['total_commits']}",
                f"- sum of agent commits: {agent_sum}",
                f"- agents: {analyzed['agents']}",
                f"- date_range: {meta['date_range']}",
                f"- benchmark stdout: {benchmark.stdout.strip()}",
                f"- elapsed_seconds: {elapsed:.3f}",
                "",
                "## Installed versions",
                "",
                "```",
                versions.strip(),
                "```",
                "",
                "Catalog publication is still Simon's step. This receipt does not submit anything.",
                "",
            ]
        )
        _receipt(receipt, args.receipt)
        if not ok:
            print(json.dumps(analyzed, indent=2), file=sys.stderr)
            return 1
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
