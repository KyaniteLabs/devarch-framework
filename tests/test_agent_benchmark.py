"""Regression coverage for benchmark commit-date parsing and empty databases."""

import sqlite3
from pathlib import Path

import pytest

from archaeology.visualization.agent_benchmark import analyze_agent_benchmarks


def _write_commits_db(path: Path, rows: list[tuple[str, str, str, str]]) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE commits (hash TEXT, date TEXT, message TEXT, author TEXT)")
        connection.executemany("INSERT INTO commits VALUES (?, ?, ?, ?)", rows)


def test_analyzer_counts_iso8601_utc_offset_and_legacy_dates_once(tmp_path):
    db_path = tmp_path / "archaeology.db"
    _write_commits_db(
        db_path,
        [
            ("utc", "2026-04-29T01:52:23+00:00", "UTC commit", "Claude 3.7"),
            ("offset", "2026-04-30T10:30:00-07:00", "Offset commit", "codex"),
            ("legacy", "2026-03-19 21:30:56 -0700", "Legacy commit", "simon"),
        ],
    )

    result = analyze_agent_benchmarks(str(db_path))

    assert result["meta"]["total_commits"] == 3
    assert sum(agent["total_commits"] for agent in result["agents"]) == 3
    assert result["meta"]["total_agents"] > 0
    assert result["meta"]["date_range"] == "2026-03-19 to 2026-04-30"
    assert {agent["name"] for agent in result["agents"]} == {"Claude", "Codex", "Human"}


def test_analyzer_rejects_malformed_commit_date_with_row_context(tmp_path):
    db_path = tmp_path / "archaeology.db"
    _write_commits_db(
        db_path,
        [
            ("valid", "2026-04-29T01:52:23Z", "Valid commit", "codex"),
            ("bad-hash", "not-a-date", "Malformed commit", "author"),
        ],
    )

    with pytest.raises(ValueError, match="bad-hash.*not-a-date"):
        analyze_agent_benchmarks(str(db_path))


def test_analyzer_returns_explicit_empty_metrics_for_empty_database(tmp_path):
    db_path = tmp_path / "archaeology.db"
    _write_commits_db(db_path, [])

    result = analyze_agent_benchmarks(str(db_path))

    assert result["agents"] == []
    assert result["meta"] == {
        "total_commits": 0,
        "total_agents": 0,
        "date_range": "Unknown",
    }
