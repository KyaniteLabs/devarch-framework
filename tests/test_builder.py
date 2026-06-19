"""Tests for archaeology/db/builder.py table name validation."""

import sqlite3

import pytest

from archaeology.db.builder import (
    SqliteUtilsError,
    _assert_commits_ingested,
    _validate_table_name,
    run_su,
)


def test_validate_table_name_valid_simple_names():
    """Test _validate_table_name() with valid simple table names."""
    assert _validate_table_name("users") == "users"
    assert _validate_table_name("commits") == "commits"
    assert _validate_table_name("sessions") == "sessions"
    assert _validate_table_name("data") == "data"


def test_validate_table_name_valid_with_underscore():
    """Test _validate_table_name() with valid underscore-prefixed names."""
    assert _validate_table_name("_private") == "_private"
    assert _validate_table_name("_meta") == "_meta"


def test_validate_table_name_valid_with_numbers():
    """Test _validate_table_name() with valid alphanumeric table names."""
    assert _validate_table_name("table_123") == "table_123"
    assert _validate_table_name("commits_2024") == "commits_2024"
    assert _validate_table_name("t123") == "t123"


def test_validate_table_name_valid_mixed_case():
    """Test _validate_table_name() with valid mixed-case table names."""
    assert _validate_table_name("Users") == "Users"
    assert _validate_table_name("CommitsData") == "CommitsData"


def test_validate_table_name_rejects_sql_injection_drop_table():
    """Test _validate_table_name() rejects SQL injection attempts with DROP TABLE."""
    with pytest.raises(ValueError, match="Invalid table name"):
        _validate_table_name("'; DROP TABLE users--")


def test_validate_table_name_rejects_path_traversal():
    """Test _validate_table_name() rejects path traversal attempts."""
    with pytest.raises(ValueError, match="Invalid table name"):
        _validate_table_name("../../../etc/passwd")
    with pytest.raises(ValueError, match="Invalid table name"):
        _validate_table_name("..\\..\\..\\windows\\system32")


def test_validate_table_name_rejects_semicolon_injection():
    """Test _validate_table_name() rejects semicolon injection attempts."""
    with pytest.raises(ValueError, match="Invalid table name"):
        _validate_table_name("table; DROP TABLE commits")
    with pytest.raises(ValueError, match="Invalid table name"):
        _validate_table_name("users; DELETE FROM users")


def test_validate_table_name_rejects_special_characters():
    """Test _validate_table_name() rejects names with special characters."""
    with pytest.raises(ValueError, match="Invalid table name"):
        _validate_table_name("table-with-dashes")
    with pytest.raises(ValueError, match="Invalid table name"):
        _validate_table_name("table with spaces")
    with pytest.raises(ValueError, match="Invalid table name"):
        _validate_table_name("table.with.dots")
    with pytest.raises(ValueError, match="Invalid table name"):
        _validate_table_name("table@symbol")


def test_validate_table_name_rejects_empty_string():
    """Test _validate_table_name() rejects empty string."""
    with pytest.raises(ValueError, match="Invalid table name"):
        _validate_table_name("")


def test_validate_table_name_rejects_starting_with_number():
    """Test _validate_table_name() rejects names starting with a number."""
    with pytest.raises(ValueError, match="Invalid table name"):
        _validate_table_name("123table")
    with pytest.raises(ValueError, match="Invalid table name"):
        _validate_table_name("9tables")


# --- Fail-loud build guarantees (regression: silent sqlite-utils failure
# produced an empty DB and a confidently-wrong all-zero report) ---

def test_run_su_raises_on_failure():
    """run_su must raise, not warn-and-continue, when sqlite-utils fails."""
    with pytest.raises(SqliteUtilsError):
        run_su(["this-is-not-a-sqlite-utils-command"])


def test_assert_commits_ingested_aborts_when_table_empty(tmp_path):
    """Populated commits CSV + empty commits table must abort the build."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "github-commits.csv").write_text(
        "hash,date,message,author\nabc,2026-01-01,hi,me\n", encoding="utf-8"
    )
    db = tmp_path / "archaeology.db"
    sqlite3.connect(db).close()  # empty db, no commits table
    with pytest.raises(SystemExit):
        _assert_commits_ingested(db, data_dir)


def test_assert_commits_ingested_passes_when_populated(tmp_path):
    """A populated commits table satisfies the guard."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "github-commits.csv").write_text(
        "hash,date,message,author\nabc,2026-01-01,hi,me\n", encoding="utf-8"
    )
    db = tmp_path / "archaeology.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE commits (hash, date, message, author)")
    conn.execute("INSERT INTO commits VALUES ('a', 'b', 'c', 'd')")
    conn.commit()
    conn.close()
    _assert_commits_ingested(db, data_dir)  # must not raise


def test_assert_commits_ingested_noop_without_csv(tmp_path):
    """No commits CSV means nothing to assert (e.g. session-only projects)."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    db = tmp_path / "archaeology.db"
    sqlite3.connect(db).close()
    _assert_commits_ingested(db, data_dir)  # must not raise
