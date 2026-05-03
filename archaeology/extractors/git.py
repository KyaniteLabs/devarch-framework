"""Git log extraction for archaeology pipeline."""

import csv
import subprocess
from pathlib import Path


def extract_git_log(repo_path: str, output_path: str, verbose: bool = False) -> int:
    """Extract git log to CSV. Returns number of commits extracted."""
    # Use %x1f (unit separator) as delimiter — can't appear in commit subjects
    cmd = [
        "git", "-C", repo_path,
        "log", "--format=%H%x1f%ai%x1f%s%x1f%an", "--all"
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except FileNotFoundError:
        raise RuntimeError("git binary not found. Install git and ensure it's on PATH.")
    except subprocess.TimeoutExpired:
        raise RuntimeError("git log timed out after 300s. Repository may be too large.")

    if result.returncode != 0:
        raise RuntimeError(f"git log failed: {result.stderr}")

    lines = result.stdout.strip().split("\n")
    if not lines or lines[0] == "":
        return 0

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["hash", "date", "message", "author"])
        skipped = 0
        for line in lines:
            parts = line.split("\x1f")
            if len(parts) >= 4:
                writer.writerow(parts[:4])
            else:
                skipped += 1

    count = len(lines) - skipped
    if verbose:
        print(f"Extracted {count} commits from {repo_path}")
        if skipped:
            print(f"  Skipped {skipped} malformed lines (expected 4 fields, got fewer)")
    return count


def extract_git_log_with_stats(repo_path: str, output_path: str, verbose: bool = False) -> int:
    """Extract git log with file change stats."""
    cmd = [
        "git", "-C", repo_path,
        "log", "--format=%H%x1f%ai%x1f%s%x1f%an", "--shortstat", "--all"
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except FileNotFoundError:
        raise RuntimeError("git binary not found. Install git and ensure it's on PATH.")
    except subprocess.TimeoutExpired:
        raise RuntimeError("git log timed out after 300s. Repository may be too large.")

    if result.returncode != 0:
        raise RuntimeError(f"git log failed: {result.stderr}")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(result.stdout)

    if verbose:
        print(f"Extracted git log with stats from {repo_path}")
    return result.stdout.count("\n\n")


def get_repo_list(repo_path: str) -> list[str]:
    """Get list of all repos accessible from the given path (for multi-repo extraction)."""
    # If it's a GitHub user/org, use gh API
    try:
        result = subprocess.run(
            ["gh", "repo", "list", "--limit", "100", "--json", "name,url"],
            capture_output=True, text=True, cwd=repo_path, timeout=60
        )
    except FileNotFoundError:
        raise RuntimeError("gh CLI not found. Install GitHub CLI and ensure it's on PATH.")
    except subprocess.TimeoutExpired:
        raise RuntimeError("gh repo list timed out after 60s.")

    if result.returncode == 0:
        import json
        repos = json.loads(result.stdout)
        return [r["name"] for r in repos]
    return []
