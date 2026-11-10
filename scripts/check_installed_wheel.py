"""Exercise installed package from a fresh CWD; run after installing the wheel."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

source = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="devarch-installed-") as directory:
    root = Path(directory)

    def run(*args):
        result = subprocess.run(
            [str(a) for a in args],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
        )
        if result.returncode:
            raise RuntimeError(
                f"{args}: exit {result.returncode}\n{result.stdout}\n{result.stderr}"
            )
        return result.stdout

    identity = json.loads(
        run(
            sys.executable,
            "-c",
            'import archaeology,json,importlib.metadata as m; print(json.dumps({"path":archaeology.__file__,"version":m.version("devarch-framework"),"runtime":archaeology.__version__,"license":m.metadata("devarch-framework")["License"]}))',
        )
    )
    assert not Path(identity["path"]).is_relative_to(source), identity
    assert identity["version"] == identity["runtime"] == "0.4.1", identity
    assert identity["license"] == "Apache-2.0", identity
    repo = root / "source"
    run("git", "init", repo)
    run("git", "-C", repo, "config", "user.name", "Fixture")
    run("git", "-C", repo, "config", "user.email", "fixture@example.invalid")
    run("git", "-C", repo, "commit", "--allow-empty", "-m", "initial <script>")
    run("git", "-C", repo, "checkout", "-b", "side")
    run("git", "-C", repo, "commit", "--allow-empty", "-m", "feature λ")
    commands = [
        ["--version"],
        ["init", "trial"],
        ["mine", repo, "-p", "trial"],
        ["build-db", "trial"],
        ["signals", "trial"],
        ["analyze", "trial"],
        ["visualize", "trial"],
        ["validate", "trial"],
        ["export-report", "trial"],
        ["export-report", "trial", "--format", "html"],
        ["audit", "trial"],
    ]
    for args in commands:
        run(sys.executable, "-m", "archaeology.cli", *args)
    metrics = json.loads((root / "projects/trial/deliverables/canonical-metrics.json").read_text())
    assert metrics["total_commits"] == 2, metrics
    print(
        json.dumps(
            {
                "status": "PASS",
                "installed_identity": identity,
                "cli_commands": len(commands),
                "commits": 2,
            }
        )
    )
