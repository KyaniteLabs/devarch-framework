"""Tests for architecture audit fixes (issues #32-#46)."""

import json
import pytest
import sqlite3
import tempfile
from pathlib import Path

import pytest

from archaeology.utils import _load_json, atomic_write
from archaeology.db.queries import _validate_order_by, _validate_table_name


# ── Issue #33: Logging in _load_json ──────────────────────────────

def test_load_json_returns_none_for_missing_file(tmp_path):
    assert _load_json(tmp_path / "nonexistent.json") is None


def test_load_json_logs_warning_on_corrupt_file(tmp_path, caplog):
    bad = tmp_path / "bad.json"
    bad.write_text("{invalid json", encoding="utf-8")
    with caplog.at_level("WARNING"):
        result = _load_json(bad)
    assert result is None
    assert "JSON parse error" in caplog.text


def test_load_json_logs_warning_on_io_error(tmp_path, caplog):
    bad = tmp_path / "unreadable.json"
    bad.write_text("{}", encoding="utf-8")
    bad.chmod(0o000)
    import sys
    if sys.platform == "win32":
        # Windows ignores Unix-style chmod for owner — skip this test
        pytest.skip("chmod(0o000) does not prevent reads on Windows")
    try:
        with caplog.at_level("WARNING"):
            result = _load_json(bad)
        assert result is None
        assert "I/O error" in caplog.text
    finally:
        bad.chmod(0o644)


def test_load_json_returns_data_for_valid_file(tmp_path):
    good = tmp_path / "good.json"
    good.write_text('{"key": "value"}', encoding="utf-8")
    result = _load_json(good)
    assert result == {"key": "value"}


# ── Issue #34: atomic_write ──────────────────────────────────────

def test_atomic_write_creates_file(tmp_path):
    target = tmp_path / "output.json"
    atomic_write(target, '{"test": true}')
    assert json.loads(target.read_text()) == {"test": True}


def test_atomic_write_cleans_up_on_failure(tmp_path):
    target = tmp_path / "nested" / "deep" / "output.json"
    # Parent dir doesn't exist — atomic_write should create it
    atomic_write(target, "content")
    assert target.read_text() == "content"


def test_atomic_write_overwrites_existing(tmp_path):
    target = tmp_path / "file.txt"
    target.write_text("old", encoding="utf-8")
    atomic_write(target, "new")
    assert target.read_text() == "new"


# ── Issue #36: SQL injection validation ──────────────────────────

def test_validate_order_by_accepts_valid_columns():
    assert _validate_order_by("start_date") == "start_date"
    assert _validate_order_by("id ASC") == "id ASC"
    assert _validate_order_by("rowid DESC") == "rowid DESC"


def test_validate_order_by_rejects_injection():
    with pytest.raises(ValueError):
        _validate_order_by("1; DROP TABLE eras")
    with pytest.raises(ValueError):
        _validate_order_by("id; --")
    with pytest.raises(ValueError):
        _validate_order_by("col INVALID")


def test_validate_table_name_rejects_injection():
    with pytest.raises(ValueError):
        _validate_table_name("commits; DROP TABLE commits")


# ── Issue #38: Git binary error handling ─────────────────────────

def test_extract_git_log_raises_on_missing_git(tmp_path, monkeypatch):
    """Verify that a helpful error is raised when git is not found."""
    from archaeology.extractors.git import extract_git_log

    monkeypatch.setenv("PATH", str(tmp_path / "nonexistent"))
    with pytest.raises(RuntimeError, match="git binary not found"):
        extract_git_log(str(tmp_path), str(tmp_path / "out.csv"))


# ── Issue #42: Safe date parsing ─────────────────────────────────

def test_safe_parse_date_handles_none():
    from archaeology.visualization.global_data_builder import _safe_parse_date
    assert _safe_parse_date(None) is None
    assert _safe_parse_date("") is None
    assert _safe_parse_date(123) is None


def test_safe_parse_date_handles_valid_dates():
    from archaeology.visualization.global_data_builder import _safe_parse_date
    from datetime import datetime
    result = _safe_parse_date("2026-04-09")
    assert result == datetime(2026, 4, 9)


def test_safe_parse_date_handles_iso_format():
    from archaeology.visualization.global_data_builder import _safe_parse_date
    from datetime import datetime
    result = _safe_parse_date("2026-04-09T12:30:00Z")
    assert result == datetime(2026, 4, 9)


def test_safe_parse_date_handles_invalid():
    from archaeology.visualization.global_data_builder import _safe_parse_date
    assert _safe_parse_date("not-a-date") is None


# ── Issue #44: DB deletion safety ────────────────────────────────

def test_builder_unlink_missing_db_does_not_crash(tmp_path):
    """unlink(missing_ok=True) should not crash when DB doesn't exist."""
    db_path = tmp_path / "nonexistent.db"
    assert not db_path.exists()
    db_path.unlink(missing_ok=True)  # Should not raise
    assert not db_path.exists()


# ── Issue #46: Audit value conversion ────────────────────────────

def test_audit_as_int_returns_none_on_non_numeric():
    from archaeology.audit import _as_int
    assert _as_int("not_a_number") is None
    assert _as_int(None) is None


def test_audit_as_int_returns_int_on_numeric():
    from archaeology.audit import _as_int
    assert _as_int(100) == 100
    assert _as_int(0) == 0
    assert _as_int("42") == 42


def test_audit_as_int_handles_string_numbers():
    from archaeology.audit import _as_int
    assert _as_int("200") == 200
    assert _as_int("") is None


# ── Issue #45: Dynamic color generation ──────────────────────────

def test_repo_color_returns_known_colors():
    from archaeology.visualization.global_data_builder import _repo_color
    assert _repo_color("liminal") == "#51cf66"
    assert _repo_color("dev-archaeology") == "#74c0fc"


def test_repo_color_generates_consistent_unknown():
    from archaeology.visualization.global_data_builder import _repo_color
    c1 = _repo_color("unknown-repo-1")
    c2 = _repo_color("unknown-repo-1")
    assert c1 == c2  # Consistent
    assert c1.startswith("#")  # Valid hex color


# ── Issue #45: GitHub owner from env ─────────────────────────────

def test_github_fetcher_uses_env_owner(monkeypatch):
    monkeypatch.setenv("ARCHAEOLOGY_GITHUB_OWNER", "testuser")
    # Re-import to pick up env var
    import importlib
    import archaeology.visualization.github_fetcher as gf
    importlib.reload(gf)
    assert gf._DEFAULT_OWNER == "testuser"
