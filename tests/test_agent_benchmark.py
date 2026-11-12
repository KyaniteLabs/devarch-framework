"""Regression coverage for benchmark commit-date parsing and empty databases."""

import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest

from archaeology.visualization.agent_benchmark import analyze_agent_benchmarks

P16_U7_ROWS = 89
P16_U7_START = date(2026, 4, 29)
P16_U7_END = date(2026, 11, 3)


def _p16_u7_rows() -> list[tuple[str, str, str, str]]:
    """89 mixed ISO-8601 / legacy dates spanning the published P16/U7 range."""
    span = (P16_U7_END - P16_U7_START).days
    days = [
        P16_U7_START + timedelta(days=round(i * span / (P16_U7_ROWS - 1)))
        for i in range(P16_U7_ROWS)
    ]
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


def test_p16_u7_replay_counts_every_mixed_date_row(tmp_path):
    """Published P16/U7 contract: 89 rows, one agent, 2026-04-29 to 2026-11-03."""
    db_path = tmp_path / "archaeology.db"
    rows = _p16_u7_rows()
    _write_commits_db(db_path, rows)

    result = analyze_agent_benchmarks(str(db_path))

    assert len(rows) == P16_U7_ROWS
    assert result["meta"]["total_commits"] == P16_U7_ROWS
    assert sum(agent["total_commits"] for agent in result["agents"]) == P16_U7_ROWS
    assert result["meta"]["total_agents"] == 1
    assert result["agents"][0]["name"] == "Claude"
    assert result["meta"]["date_range"] == "2026-04-29 to 2026-11-03"


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
