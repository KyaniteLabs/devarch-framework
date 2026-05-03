"""Tests for archaeology/db/builder.py table name validation."""

import pytest

from archaeology.db.builder import _validate_table_name


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
