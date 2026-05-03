#!/bin/bash
# auto-sync.sh — Run archaeology sync for all registered projects
# Designed to be called by launchd every 6 hours
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_FILE="$REPO_DIR/auto-sync.log"
VENV_DIR="$REPO_DIR/.venv"

timestamp() { date '+%Y-%m-%d %H:%M:%S'; }

{
  echo "=========================================="
  echo "$(timestamp) — Auto-sync starting"
  echo "=========================================="

  # Activate venv
  source "$VENV_DIR/bin/activate"

  # Change to repo dir (CLI expects to run from repo root)
  cd "$REPO_DIR"

  # Run sync
  python -m archaeology.cli sync --skip-mine 2>&1 || {
    echo "$(timestamp) — ERROR: sync failed, attempting fresh mine"
    python -m archaeology.cli sync 2>&1 || {
      echo "$(timestamp) — FATAL: full sync also failed"
      exit 1
    }
  }

  # Count new commits
  COMMIT_COUNT=$(wc -l < "$REPO_DIR/global/data/global-commits.csv")
  COMMIT_COUNT=$((COMMIT_COUNT - 1))  # subtract header

  echo "$(timestamp) — Auto-sync complete: $COMMIT_COUNT total commits across all projects"

} >> "$LOG_FILE" 2>&1
