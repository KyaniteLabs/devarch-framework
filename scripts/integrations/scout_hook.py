#!/usr/bin/env python3
"""Integration hook for research-scout to trigger dev-archaeology analysis.

This script allows external tools (research-scout, CI/CD, etc.) to trigger
archaeological analysis on discovered repositories.

Usage:
    # CLI mode
    python3 scout_hook.py --repo-url https://github.com/user/repo --project-name my-project

    # Stdin mode
    echo '{"url": "https://github.com/user/repo", "name": "my-project"}' | python3 scout_hook.py --stdin

    # Local repo
    python3 scout_hook.py --repo-path /path/to/repo --project-name my-project

Output:
    JSON to stdout with status, metrics, and artifact paths
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from enum import Enum
from pathlib import Path
from typing import Any

# ── Run lifecycle ────────────────────────────────────────────────────────────
#
# The JSON this script prints has a run ``status`` and one ``status`` per step.
# Both are named here, and every write goes through the transition functions
# below. Legal moves of the run::
#
#     RUNNING --critical step failed--> FAILED
#     RUNNING --all steps recorded----> COMPLETE
#     (any exception / bad input) ----> ERROR   (built by ``error_result``)
#
# Steps are recorded once each, in STEP_ORDER, only while RUNNING. A critical
# step (init, mine, build_db) is SUCCESS or FAILED; a soft step (signals,
# analyze) is SUCCESS or PARTIAL and never stops the run.


class RunStatus(str, Enum):
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    ERROR = "error"


class StepStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


STEP_ORDER = ("init", "mine", "build_db", "signals", "analyze")
CRITICAL_STEPS = frozenset({"init", "mine", "build_db"})

RUN_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.RUNNING: frozenset({RunStatus.FAILED, RunStatus.COMPLETE}),
    RunStatus.COMPLETE: frozenset(),
    RunStatus.FAILED: frozenset(),
    RunStatus.ERROR: frozenset(),
}

# Exit code for each terminal run status (README: complete -> 0, else 1).
EXIT_CODES: dict[RunStatus, int] = {
    RunStatus.RUNNING: 1,
    RunStatus.COMPLETE: 0,
    RunStatus.FAILED: 1,
    RunStatus.ERROR: 1,
}


class IllegalTransition(RuntimeError):
    """A run or step move the lifecycle above does not allow."""


def read_run_status(value: object) -> RunStatus | None:
    """Read a stored run status; ``None`` for anything this script never writes."""
    try:
        return RunStatus(value)
    except ValueError:
        return None


def _move_run(result: dict[str, Any], target: RunStatus) -> None:
    current = RunStatus(result["status"])
    if target not in RUN_TRANSITIONS[current]:
        raise IllegalTransition(f"run: {current.value} -> {target.value}")
    result["status"] = target.value


def new_run(project_name: str, repo_path: str, repo_url: str | None) -> dict[str, Any]:
    """A RUNNING result with no steps recorded."""
    return {
        "project_name": project_name,
        "repo_path": repo_path,
        "repo_url": repo_url or "",
        "status": RunStatus.RUNNING.value,
        "steps": {},
        "metrics": {},
        "artifacts": {},
    }


def record_step(result: dict[str, Any], step: str, ok: bool, message: str) -> StepStatus:
    """Record the next step's outcome; a failed critical step fails the run.

    ``ok`` is the step's own success. A soft step that did not fully succeed
    is PARTIAL. Raises ``IllegalTransition`` for an out-of-order or repeated
    step, or when the run is no longer RUNNING.
    """
    if result["status"] != RunStatus.RUNNING.value:
        raise IllegalTransition(f"step {step}: run is {result['status']}")
    expected = STEP_ORDER[len(result["steps"])] if len(result["steps"]) < len(STEP_ORDER) else None
    if step != expected:
        raise IllegalTransition(f"step {step}: expected {expected}")
    if ok:
        status = StepStatus.SUCCESS
    elif step in CRITICAL_STEPS:
        status = StepStatus.FAILED
    else:
        status = StepStatus.PARTIAL
    result["steps"][step] = {"status": status.value, "message": message}
    if status is StepStatus.FAILED:
        _move_run(result, RunStatus.FAILED)
        result["error"] = message
    return status


def finish_run(result: dict[str, Any]) -> None:
    """RUNNING -> COMPLETE once every step is recorded."""
    if tuple(result["steps"]) != STEP_ORDER:
        raise IllegalTransition(f"finish: steps recorded {tuple(result['steps'])}")
    _move_run(result, RunStatus.COMPLETE)


def error_result(error: str, **fields: Any) -> dict[str, Any]:
    """A result that never ran or crashed: status ERROR."""
    return {"status": RunStatus.ERROR.value, **fields, "error": error}


def failed_result(error: str, **fields: Any) -> dict[str, Any]:
    """A result that failed before the pipeline started (clone, missing repo)."""
    return {"status": RunStatus.FAILED.value, **fields, "error": error}


def exit_code(result: dict[str, Any]) -> int:
    status = read_run_status(result.get("status"))
    return 0 if status is None else EXIT_CODES[status]


def log_error(msg: str) -> None:
    """Write error to stderr for non-JSON logging."""
    print(f"[ERROR] {msg}", file=sys.stderr)


def log_info(msg: str) -> None:
    """Write info to stderr for progress logging."""
    print(f"[INFO] {msg}", file=sys.stderr)


def run_command(
    cmd: list[str], check: bool = True, timeout: int = 300
) -> subprocess.CompletedProcess[str]:
    """Run a command and return the result."""
    log_info(f"Running: {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=check,
        timeout=timeout,
    )
    if result.stderr:
        log_info(f"stderr: {result.stderr.strip()}")
    return result


def clone_repo(url: str, clone_dir: str) -> tuple[bool, str]:
    """Clone a repository to a temporary directory.

    Returns:
        (success, path_or_error)
    """
    try:
        log_info(f"Cloning {url} to {clone_dir}")
        result = run_command(
            ["git", "clone", "--depth", "1", url, clone_dir],
            check=False,
            timeout=600,
        )
        if result.returncode != 0:
            return False, f"git clone failed: {result.stderr}"
        return True, clone_dir
    except subprocess.TimeoutExpired:
        return False, "git clone timed out"
    except Exception as e:
        return False, f"clone error: {e}"


def init_project(
    project_name: str, description: str, repo_url: str
) -> tuple[bool, str, dict[str, Any]]:
    """Initialize a new archaeology project.

    Returns:
        (success, message, result_dict)
    """
    try:
        log_info(f"Initializing project '{project_name}'")
        cmd = [
            sys.executable,
            "-m",
            "archaeology.cli",
            "init",
            project_name,
            "--description",
            description,
            "--repo-url",
            repo_url,
        ]
        result = run_command(cmd, check=False)
        if result.returncode != 0:
            return False, f"init failed: {result.stderr}", {}

        project_dir = os.path.join("projects", project_name)
        return True, project_dir, {"project_dir": project_dir}
    except Exception as e:
        return False, f"init error: {e}", {}


def mine_repo(repo_path: str, project_name: str) -> tuple[bool, str, dict[str, Any]]:
    """Extract git data from repository.

    Returns:
        (success, message, result_dict)
    """
    try:
        log_info(f"Mining git data from {repo_path}")
        cmd = [
            sys.executable,
            "-m",
            "archaeology.cli",
            "mine",
            repo_path,
            "--project",
            project_name,
        ]
        result = run_command(cmd, check=False, timeout=600)
        if result.returncode != 0:
            return False, f"mine failed: {result.stderr}", {}

        # Parse commit count from output
        commit_count = 0
        for line in result.stdout.split("\n"):
            if "Extracted" in line and "commits" in line:
                try:
                    commit_count = int(line.split()[1])
                except (ValueError, IndexError):
                    pass

        return True, result.stdout, {"commit_count": commit_count}
    except subprocess.TimeoutExpired:
        return False, "mine timed out", {}
    except Exception as e:
        return False, f"mine error: {e}", {}


def build_database(project_name: str) -> tuple[bool, str, dict[str, Any]]:
    """Build SQLite database from extracted data.

    Returns:
        (success, message, result_dict)
    """
    try:
        log_info(f"Building database for '{project_name}'")
        cmd = [
            sys.executable,
            "-m",
            "archaeology.cli",
            "build-db",
            project_name,
        ]
        result = run_command(cmd, check=False, timeout=600)
        if result.returncode != 0:
            return False, f"build-db failed: {result.stderr}", {}

        db_path = os.path.join("projects", project_name, "data", "archaeology.db")
        exists = os.path.exists(db_path)
        return True, result.stdout, {"db_path": db_path, "db_exists": exists}
    except subprocess.TimeoutExpired:
        return False, "build-db timed out", {}
    except Exception as e:
        return False, f"build-db error: {e}", {}


def detect_signals(project_name: str) -> tuple[bool, str, dict[str, Any]]:
    """Detect development signals.

    Returns:
        (success, message, result_dict)
    """
    try:
        log_info(f"Detecting signals for '{project_name}'")
        cmd = [
            sys.executable,
            "-m",
            "archaeology.cli",
            "signals",
            project_name,
        ]
        result = run_command(cmd, check=False, timeout=300)
        if result.returncode != 0:
            # Signals might fail if no patterns found - not critical
            log_info(f"Signals detection returned non-zero: {result.stderr}")

        # Try to parse signal count
        signal_count = 0
        for line in result.stdout.split("\n"):
            if "Detected" in line and "signals" in line:
                try:
                    signal_count = int(line.split()[1])
                except (ValueError, IndexError):
                    pass

        return True, result.stdout, {"signal_count": signal_count}
    except subprocess.TimeoutExpired:
        return False, "signals timed out", {}
    except Exception as e:
        return False, f"signals error: {e}", {}


_FAILED_VECTOR_LINE = re.compile(r"^\s*\[analysis\] (\S+) ERROR:", re.MULTILINE)


def count_failed_vectors(stdout: str) -> int:
    """Distinct vectors the runner reported as failed.

    The CLI prints each failure twice (runner line and summary line), so
    counting ``"ERROR:"`` doubled it; count runner lines by vector name.
    """
    return len(set(_FAILED_VECTOR_LINE.findall(stdout)))


def run_analysis(project_name: str) -> tuple[bool, str, dict[str, Any]]:
    """Run analysis vectors.

    Returns:
        (success, message, result_dict)
    """
    try:
        log_info(f"Running analysis vectors for '{project_name}'")
        cmd = [
            sys.executable,
            "-m",
            "archaeology.cli",
            "analyze",
            project_name,
        ]
        result = run_command(cmd, check=False, timeout=600)

        # Parse analysis outputs from files created (more reliable than parsing stdout).
        # The runner writes them to deliverables/analysis/, not deliverables/.
        analysis_dir = os.path.join("projects", project_name, "deliverables", "analysis")
        analysis_files = []
        if os.path.exists(analysis_dir):
            import time

            for f in sorted(os.listdir(analysis_dir)):
                if f.startswith("analysis-") and f.endswith(".json"):
                    file_path = os.path.join(analysis_dir, f)
                    # Only count files created recently
                    if time.time() - os.path.getmtime(file_path) < 120:
                        analysis_files.append(file_path)

        success_count = len(analysis_files)
        if success_count == 0:
            return False, f"analyze failed: {result.stderr}", {}

        failed = count_failed_vectors(result.stdout)
        data = {
            "analysis_count": success_count,
            "analysis_files": analysis_files,
            "failed_vectors": failed,
            "total_vectors": 6,  # Known vector count
        }
        # Some vectors failed: the step is PARTIAL, not SUCCESS.
        return failed == 0, result.stdout, data
    except subprocess.TimeoutExpired:
        return False, "analyze timed out", {}
    except Exception as e:
        return False, f"analyze error: {e}", {}


def run_full_pipeline(
    repo_path: str,
    project_name: str,
    repo_url: str | None = None,
    keep_clone: bool = False,
) -> dict[str, Any]:
    """Run the complete archaeological pipeline.

    Args:
        repo_path: Path to repository (local or cloned)
        project_name: Name for the archaeology project
        repo_url: Original repository URL (for metadata)
        keep_clone: If True, don't delete temporary clones

    Returns:
        Result dictionary with status and metrics
    """
    result = new_run(project_name, repo_path, repo_url)

    # Use repo_url for init if available, otherwise use placeholder
    init_url = repo_url or "https://github.com/example/example"

    # Step 1: Initialize project
    success, msg, data = init_project(project_name, f"Analysis of {project_name}", init_url)
    if record_step(result, "init", success, msg) is StepStatus.FAILED:
        return result
    result["artifacts"]["project_dir"] = data.get("project_dir")

    # Step 2: Mine repository
    success, msg, data = mine_repo(repo_path, project_name)
    if record_step(result, "mine", success, msg) is StepStatus.FAILED:
        return result
    result["metrics"]["commit_count"] = data.get("commit_count", 0)

    # Step 3: Build database
    success, msg, data = build_database(project_name)
    if record_step(result, "build_db", success, msg) is StepStatus.FAILED:
        return result
    result["artifacts"]["db_path"] = data.get("db_path")
    result["metrics"]["db_built"] = data.get("db_exists", False)

    # Step 4: Detect signals (non-critical)
    success, msg, data = detect_signals(project_name)
    record_step(result, "signals", success, msg)
    result["metrics"]["signal_count"] = data.get("signal_count", 0)

    # Step 5: Run analysis (non-critical)
    success, msg, data = run_analysis(project_name)
    record_step(result, "analyze", success, msg)
    result["metrics"]["analysis_count"] = data.get("analysis_count", 0)
    result["artifacts"]["analysis_files"] = data.get("analysis_files", [])

    finish_run(result)
    return result


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Integration hook for research-scout to trigger dev-archaeology analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # CLI mode with URL
  python3 scout_hook.py --repo-url https://github.com/user/repo --project-name my-project

  # CLI mode with local path
  python3 scout_hook.py --repo-path /path/to/repo --project-name my-project

  # Stdin mode
  echo '{"url": "https://github.com/user/repo", "name": "my-project"}' | python3 scout_hook.py --stdin

  # Keep cloned repository
  python3 scout_hook.py --repo-url https://github.com/user/repo --project-name my-project --keep
        """,
    )
    parser.add_argument(
        "--repo-url",
        help="Repository URL to clone and analyze",
    )
    parser.add_argument(
        "--repo-path",
        help="Local repository path to analyze (skips cloning)",
    )
    parser.add_argument(
        "--project-name",
        help="Name for the archaeology project",
    )
    parser.add_argument(
        "--clone-dir",
        help="Directory for cloned repos (default: temp dir)",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Keep cloned repository after analysis",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read input as JSON from stdin",
    )

    args = parser.parse_args()

    # Read from stdin if requested
    if args.stdin:
        try:
            input_data = json.loads(sys.stdin.read())
            repo_url = input_data.get("url")
            repo_path = input_data.get("path")
            project_name = input_data.get("name")
            keep_clone = input_data.get("keep", False)
            clone_dir = input_data.get("clone_dir")
        except json.JSONDecodeError as e:
            log_error(f"Invalid JSON input: {e}")
            result = error_result(f"Invalid JSON input: {e}")
            print(json.dumps(result, indent=2))
            return 1
    else:
        repo_url = args.repo_url
        repo_path = args.repo_path
        project_name = args.project_name
        keep_clone = args.keep
        clone_dir = args.clone_dir

    # Validate inputs
    if not project_name:
        log_error("--project-name is required")
        result = error_result("--project-name is required")
        print(json.dumps(result, indent=2))
        return 1

    if not repo_url and not repo_path:
        log_error("Either --repo-url or --repo-path must be provided")
        result = error_result("Either --repo-url or --repo-path must be provided")
        print(json.dumps(result, indent=2))
        return 1

    # Change to dev-archaeology root
    script_dir = Path(__file__).parent
    archaeology_root = script_dir.parent.parent
    os.chdir(archaeology_root)

    temp_clone_dir = None
    try:
        # Clone repository if URL provided
        if repo_url:
            if clone_dir:
                target_dir = os.path.join(clone_dir, project_name)
            else:
                temp_clone_dir = tempfile.mkdtemp(prefix="archaeology-scout-")
                target_dir = os.path.join(temp_clone_dir, project_name)

            success, msg_or_path = clone_repo(repo_url, target_dir)
            if not success:
                result = failed_result(msg_or_path, project_name=project_name, repo_url=repo_url)
                print(json.dumps(result, indent=2))
                return 1
            repo_path = msg_or_path
        else:
            repo_path = os.path.expanduser(repo_path)  # type: ignore

        # Validate repository exists
        if not os.path.isdir(repo_path):
            result = failed_result(
                f"Repository not found: {repo_path}", project_name=project_name, repo_path=repo_path
            )
            print(json.dumps(result, indent=2))
            return 1

        # Run full pipeline
        result = run_full_pipeline(
            repo_path=repo_path,
            project_name=project_name,
            repo_url=repo_url,
            keep_clone=keep_clone,
        )

        # Add cleanup info
        if temp_clone_dir and not keep_clone:
            result["cleanup"] = {"temp_dir": temp_clone_dir, "action": "will_delete"}

    except Exception as e:
        result = error_result(f"Pipeline error: {e}", project_name=project_name)

    finally:
        # Cleanup temporary clone
        if temp_clone_dir and not keep_clone and os.path.exists(temp_clone_dir):
            try:
                shutil.rmtree(temp_clone_dir)
            except Exception as e:
                log_error(f"Failed to cleanup temp dir: {e}")

    # Output result as JSON
    print(json.dumps(result, indent=2))

    return exit_code(result)


if __name__ == "__main__":
    sys.exit(main())
