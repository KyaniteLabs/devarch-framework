"""Common query helpers for archaeology SQLite databases."""

import re
import sqlite3
from pathlib import Path
from typing import Optional


# Allowed table names for FTS queries (whitelist validation)
_ALLOWED_FTS_TABLES = {"commits", "sessions", "eras"}


def _validate_table_name(table: str) -> str:
    """Validate table name to prevent SQL injection.

    Only allows alphanumeric characters and underscores.
    Raises ValueError if invalid.
    """
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table):
        raise ValueError(f"Invalid table name: {table}")
    return table


def _validate_order_by(col: str) -> str:
    """Validate ORDER BY column name to prevent SQL injection."""
    col = col.strip()
    parts = col.split()
    if len(parts) > 2:
        raise ValueError(f"Invalid order_by: {col!r}")
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', parts[0]):
        raise ValueError(f"Invalid column name in order_by: {parts[0]!r}")
    if len(parts) == 2 and parts[1].upper() not in ("ASC", "DESC"):
        raise ValueError(f"Invalid sort direction: {parts[1]!r}")
    return col


def get_connection(db_path: str | Path) -> sqlite3.Connection:
    """Get a connection to the archaeology database."""
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def get_commits(db_path: str, filters: Optional[dict] = None, limit: int = 1000) -> list[dict]:
    """Query commits with optional filters. Filters: repo, author, date_from, date_to."""
    conn = get_connection(db_path)
    try:
        query = "SELECT * FROM commits WHERE 1=1"
        params = []
        if filters:
            if "repo" in filters:
                query += " AND repo = ?"
                params.append(filters["repo"])
            if "author" in filters:
                query += " AND author = ?"
                params.append(filters["author"])
            if "date_from" in filters:
                query += " AND date >= ?"
                params.append(filters["date_from"])
            if "date_to" in filters:
                query += " AND date <= ?"
                params.append(filters["date_to"])
        query += " ORDER BY date LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_eras(db_path: str) -> list[dict]:
    """Get all era definitions.

    Older archaeology databases do not have a start_date column; they usually
    expose id and/or dates instead. Prefer start_date when available and fall
    back to stable available columns so query helpers do not break on
    databases with varying schema versions.
    """
    conn = get_connection(db_path)
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(eras)").fetchall()}
        if "start_date" in cols:
            order_by = "start_date"
        elif "id" in cols:
            order_by = "id"
        elif "dates" in cols:
            order_by = "dates"
        else:
            order_by = "rowid"
        order_by = _validate_order_by(order_by)
        rows = conn.execute(f"SELECT * FROM eras ORDER BY {order_by}").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_sessions(db_path: str, filters: Optional[dict] = None, limit: int = 500) -> list[dict]:
    """Query sessions with optional filters."""
    conn = get_connection(db_path)
    try:
        query = "SELECT * FROM sessions WHERE 1=1"
        params = []
        if filters:
            if "session_id" in filters:
                query += " AND session_id = ?"
                params.append(filters["session_id"])
        query += " ORDER BY timestamp LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_fts_results(db_path: str, table: str, query_text: str, limit: int = 50) -> list[dict]:
    """Full-text search on FTS-enabled tables.

    Args:
        db_path: Path to SQLite database
        table: Base table name (must be in allowed FTS tables whitelist)
        query_text: FTS search query
        limit: Maximum results to return

    Raises:
        ValueError: If table name is not in the allowed whitelist
    """
    # Validate table name against whitelist to prevent SQL injection
    if table not in _ALLOWED_FTS_TABLES:
        raise ValueError(f"Table '{table}' not allowed for FTS queries. Allowed: {sorted(_ALLOWED_FTS_TABLES)}")

    conn = get_connection(db_path)
    try:
        fts_table = f"{table}_fts"
        rows = conn.execute(
            f"SELECT * FROM {fts_table} WHERE {fts_table} MATCH ? LIMIT ?",
            [query_text, limit]
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_table_list(db_path: str) -> list[str]:
    """Get all table names in the database."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


def get_table_count(db_path: str, table: str) -> int:
    """Get row count for a table."""
    table = _validate_table_name(table)
    conn = get_connection(db_path)
    try:
        count = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        return count
    finally:
        conn.close()


def get_pipeline_runs(db_path: str, repo_name: str | None = None, limit: int = 50) -> list[dict]:
    """Query pipeline run history from the pipeline_runs table."""
    from .pipeline_ingest import get_pipeline_history
    return get_pipeline_history(Path(db_path), repo_name=repo_name, limit=limit)


def get_repo_quality_trend(db_path: str, repo_name: str, limit: int = 30) -> list[dict]:
    """Get quality trend for a repo across pipeline runs."""
    from .pipeline_ingest import get_repo_quality_trend as _trend
    return _trend(Path(db_path), repo_name=repo_name, limit=limit)
