"""Ingest GITHUB_pipeline run logs into an archaeology SQLite database.

Reads pipeline JSON files (from .omc/logs/repo-pipeline/) and inserts them
into pipeline_runs and pipeline_repo_results tables for historical tracking
and cross-referencing with commit/session data.

Pipeline JSON format (expected keys):
  {
    "timestamp": "2026-04-09T22:17:10Z",
    "status": "pass|fail|partial",
    "duration_seconds": 120,
    "repos": [
      {
        "name": "repo-name",
        "tier": 1,
        "issues": [...],
        "fixes_applied": 2,
        "status": "clean"
      }
    ],
    "agents_used": ["hygiene-agent", "secret-scanner"],
    "summary": { ... }
  }
"""

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


SCHEMA = """
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_timestamp TEXT NOT NULL,
    status TEXT,
    duration_seconds INTEGER,
    agents_used TEXT,
    summary_json TEXT,
    source_file TEXT,
    ingested_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS pipeline_repo_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    repo_name TEXT NOT NULL,
    tier INTEGER,
    status TEXT,
    issues_count INTEGER DEFAULT 0,
    fixes_applied INTEGER DEFAULT 0,
    issues_json TEXT,
    FOREIGN KEY (run_id) REFERENCES pipeline_runs(id)
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_timestamp ON pipeline_runs(run_timestamp);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs(status);
CREATE INDEX IF NOT EXISTS idx_pipeline_repo_results_repo ON pipeline_repo_results(repo_name);
CREATE INDEX IF NOT EXISTS idx_pipeline_repo_results_run ON pipeline_repo_results(run_id);
"""


def ensure_tables(db_path: Path) -> None:
    """Create pipeline tables if they don't exist."""
    conn = sqlite3.connect(str(db_path), timeout=30)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def ingest_run(db_path: Path, run_json: dict, source_file: str = "") -> int:
    """Ingest a single pipeline run JSON. Returns the run_id."""
    ensure_tables(db_path)
    conn = sqlite3.connect(str(db_path), timeout=30)
    try:
        ts = run_json.get("timestamp", datetime.utcnow().isoformat())
        status = run_json.get("status", "unknown")
        duration = run_json.get("duration_seconds")
        agents = json.dumps(run_json.get("agents_used", []))
        summary = json.dumps(run_json.get("summary", {}))

        cursor = conn.execute(
            "INSERT INTO pipeline_runs (run_timestamp, status, duration_seconds, agents_used, summary_json, source_file) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (ts, status, duration, agents, summary, source_file),
        )
        run_id = cursor.lastrowid

        for repo in run_json.get("repos", []):
            issues = repo.get("issues", [])
            issues_count = len(issues) if isinstance(issues, list) else sum(issues.values()) if isinstance(issues, dict) else 0
            issues_json = json.dumps(issues) if isinstance(issues, (list, dict)) else "[]"
            fixes_raw = repo.get("fixes_applied", 0)
            fixes_count = len(fixes_raw) if isinstance(fixes_raw, list) else fixes_raw if isinstance(fixes_raw, int) else 0
            conn.execute(
                "INSERT INTO pipeline_repo_results (run_id, repo_name, tier, status, issues_count, fixes_applied, issues_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    repo.get("name", "unknown"),
                    repo.get("tier"),
                    repo.get("status", "unknown"),
                    issues_count,
                    fixes_count,
                    issues_json,
                ),
            )

        conn.commit()
    finally:
        conn.close()
    return run_id


def ingest_directory(db_path: Path, logs_dir: Path, verbose: bool = False) -> dict:
    """Ingest all pipeline run JSONs from a directory.

    Returns stats: {"ingested": int, "skipped": int, "errors": list[str]}
    """
    ensure_tables(db_path)

    # Get already-ingested source files to avoid duplicates
    conn = sqlite3.connect(str(db_path), timeout=30)
    try:
        existing = {
            row[0]
            for row in conn.execute("SELECT source_file FROM pipeline_runs WHERE source_file != ''").fetchall()
        }
    finally:
        conn.close()

    stats = {"ingested": 0, "skipped": 0, "errors": []}

    for json_file in sorted(logs_dir.glob("*.json")):
        if json_file.name == "latest.json" or json_file.name in existing:
            if verbose:
                print(f"  SKIP {json_file.name} (already ingested or symlink)")
            stats["skipped"] += 1
            continue

        try:
            with open(json_file, encoding="utf-8") as f:
                data = json.load(f)

            # Validate it looks like a pipeline run
            if "repos" not in data and "timestamp" not in data:
                if verbose:
                    print(f"  SKIP {json_file.name} (not a pipeline run)")
                stats["skipped"] += 1
                continue

            run_id = ingest_run(db_path, data, source_file=json_file.name)
            if verbose:
                print(f"  INGESTED {json_file.name} -> run_id={run_id}")
            stats["ingested"] += 1

        except (json.JSONDecodeError, OSError) as exc:
            stats["errors"].append(f"{json_file.name}: {exc}")

    return stats


def get_pipeline_history(db_path: Path, repo_name: Optional[str] = None, limit: int = 50) -> list[dict]:
    """Query pipeline run history, optionally filtered by repo."""
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        if repo_name:
            rows = conn.execute(
                """
                SELECT r.*, pr.repo_name, pr.tier, pr.status as repo_status,
                       pr.issues_count, pr.fixes_applied
                FROM pipeline_runs r
                JOIN pipeline_repo_results pr ON r.id = pr.run_id
                WHERE pr.repo_name = ?
                ORDER BY r.run_timestamp DESC LIMIT ?
                """,
                (repo_name, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM pipeline_runs ORDER BY run_timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()

        results = [dict(r) for r in rows]
    finally:
        conn.close()
    return results


def get_repo_quality_trend(db_path: Path, repo_name: str, limit: int = 30) -> list[dict]:
    """Get quality trend for a repo across pipeline runs (issues/fixes over time)."""
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT r.run_timestamp, pr.status, pr.issues_count, pr.fixes_applied, pr.tier
            FROM pipeline_runs r
            JOIN pipeline_repo_results pr ON r.id = pr.run_id
            WHERE pr.repo_name = ?
            ORDER BY r.run_timestamp DESC LIMIT ?
            """,
            (repo_name, limit),
        ).fetchall()
        results = [dict(r) for r in rows]
    finally:
        conn.close()
    return results
