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
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


def log_error(msg: str) -> None:
    """Write error to stderr for non-JSON logging."""
    print(f"[ERROR] {msg}", file=sys.stderr)


def log_info(msg: str) -> None:
    """Write info to stderr for progress logging."""
    print(f"[INFO] {msg}", file=sys.stderr)


def run_command(cmd: list[str], check: bool = True, timeout: int = 300) -> subprocess.CompletedProcess[str]:
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


def init_project(project_name: str, description: str, repo_url: str) -> tuple[bool, str, dict[str, Any]]:
    """Initialize a new archaeology project.

    Returns:
        (success, message, result_dict)
    """
    try:
        log_info(f"Initializing project '{project_name}'")
        cmd = [
            sys.executable, "-m", "archaeology.cli",
            "init", project_name,
            "--description", description,
            "--repo-url", repo_url,
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
            sys.executable, "-m", "archaeology.cli",
            "mine", repo_path,
            "--project", project_name,
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
            sys.executable, "-m", "archaeology.cli",
            "build-db", project_name,
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
            sys.executable, "-m", "archaeology.cli",
            "signals", project_name,
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


def run_analysis(project_name: str) -> tuple[bool, str, dict[str, Any]]:
    """Run analysis vectors.

    Returns:
        (success, message, result_dict)
    """
    try:
        log_info(f"Running analysis vectors for '{project_name}'")
        cmd = [
            sys.executable, "-m", "archaeology.cli",
            "analyze", project_name,
        ]
        result = run_command(cmd, check=False, timeout=600)

        # Parse analysis outputs from files created (more reliable than parsing stdout)
        deliverables_dir = os.path.join("projects", project_name, "deliverables")
        analysis_files = []
        if os.path.exists(deliverables_dir):
            for f in os.listdir(deliverables_dir):
                if f.startswith("analysis-") and f.endswith(".json"):
                    file_path = os.path.join(deliverables_dir, f)
                    # Only count files created recently (within last minute)
                    if os.path.exists(file_path):
                        import time
                        mtime = os.path.getmtime(file_path)
                        if time.time() - mtime < 120:  # Created within last 2 minutes
                            analysis_files.append(file_path)

        # Determine success: at least one analysis file created = partial success
        success_count = len(analysis_files)
        if success_count == 0:
            return False, f"analyze failed: {result.stderr}", {}

        # Check if any vectors failed from stdout
        failed_count = result.stdout.count("ERROR:")
        total_vectors = 6  # Known vector count
        status = "success" if failed_count == 0 else "partial"

        return True, result.stdout, {
            "analysis_count": success_count,
            "analysis_files": analysis_files,
            "failed_vectors": failed_count,
            "total_vectors": total_vectors,
        }
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
    result: dict[str, Any] = {
        "project_name": project_name,
        "repo_path": repo_path,
        "repo_url": repo_url or "",
        "status": "running",
        "steps": {},
        "metrics": {},
        "artifacts": {},
    }

    # Use repo_url for init if available, otherwise use placeholder
    init_url = repo_url or "https://github.com/example/example"

    # Step 1: Initialize project
    success, msg, data = init_project(project_name, f"Analysis of {project_name}", init_url)
    result["steps"]["init"] = {"status": "success" if success else "failed", "message": msg}
    if not success:
        result["status"] = "failed"
        result["error"] = msg
        return result
    result["artifacts"]["project_dir"] = data.get("project_dir")

    # Step 2: Mine repository
    success, msg, data = mine_repo(repo_path, project_name)
    result["steps"]["mine"] = {"status": "success" if success else "failed", "message": msg}
    if not success:
        result["status"] = "failed"
        result["error"] = msg
        return result
    result["metrics"]["commit_count"] = data.get("commit_count", 0)

    # Step 3: Build database
    success, msg, data = build_database(project_name)
    result["steps"]["build_db"] = {"status": "success" if success else "failed", "message": msg}
    if not success:
        result["status"] = "failed"
        result["error"] = msg
        return result
    result["artifacts"]["db_path"] = data.get("db_path")
    result["metrics"]["db_built"] = data.get("db_exists", False)

    # Step 4: Detect signals (non-critical)
    success, msg, data = detect_signals(project_name)
    result["steps"]["signals"] = {"status": "success" if success else "partial", "message": msg}
    result["metrics"]["signal_count"] = data.get("signal_count", 0)

    # Step 5: Run analysis (non-critical)
    success, msg, data = run_analysis(project_name)
    result["steps"]["analyze"] = {"status": "success" if success else "partial", "message": msg}
    result["metrics"]["analysis_count"] = data.get("analysis_count", 0)
    result["artifacts"]["analysis_files"] = data.get("analysis_files", [])

    # Check for critical failures
    if result["steps"]["build_db"]["status"] == "failed":
        result["status"] = "failed"
    elif result["steps"]["mine"]["status"] == "failed":
        result["status"] = "failed"
    else:
        result["status"] = "complete"

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
            result = {
                "status": "error",
                "error": f"Invalid JSON input: {e}",
            }
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
        result = {
            "status": "error",
            "error": "--project-name is required",
        }
        print(json.dumps(result, indent=2))
        return 1

    if not repo_url and not repo_path:
        log_error("Either --repo-url or --repo-path must be provided")
        result = {
            "status": "error",
            "error": "Either --repo-url or --repo-path must be provided",
        }
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
                result = {
                    "status": "failed",
                    "project_name": project_name,
                    "repo_url": repo_url,
                    "error": msg_or_path,
                }
                print(json.dumps(result, indent=2))
                return 1
            repo_path = msg_or_path
        else:
            repo_path = os.path.expanduser(repo_path)  # type: ignore

        # Validate repository exists
        if not os.path.isdir(repo_path):
            result = {
                "status": "failed",
                "project_name": project_name,
                "repo_path": repo_path,
                "error": f"Repository not found: {repo_path}",
            }
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
        result = {
            "status": "error",
            "project_name": project_name,
            "error": f"Pipeline error: {e}",
        }

    finally:
        # Cleanup temporary clone
        if temp_clone_dir and not keep_clone and os.path.exists(temp_clone_dir):
            try:
                shutil.rmtree(temp_clone_dir)
            except Exception as e:
                log_error(f"Failed to cleanup temp dir: {e}")

    # Output result as JSON
    print(json.dumps(result, indent=2))

    # Return exit code based on status
    if result.get("status") == "complete":
        return 0
    elif result.get("status") in ("failed", "error"):
        return 1
    else:
        return 0


if __name__ == "__main__":
    sys.exit(main())
