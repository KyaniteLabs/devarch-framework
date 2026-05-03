"""Tests for archaeology/utils.py _parse_date function used by era_detector."""

from archaeology.utils import _parse_date


def test_parse_date_empty_string():
    """Test _parse_date() returns None for empty string."""
    assert _parse_date("") is None


def test_parse_date_none():
    """Test _parse_date() returns None for None input."""
    assert _parse_date(None) is None


def test_parse_date_whitespace_only():
    """Test _parse_date() returns None for whitespace-only strings."""
    assert _parse_date("   ") is None
    assert _parse_date("\t\n") is None


def test_parse_date_unparseable_string():
    """Test _parse_date() returns None for unparseable date strings."""
    assert _parse_date("not-a-date") is None
    assert _parse_date("123456789") is None  # Just digits, no format match
    assert _parse_date("January 32, 2024") is None  # Invalid date


def test_parse_date_valid_iso_with_timezone():
    """Test _parse_date() returns correct datetime for ISO format with timezone."""
    result = _parse_date("2024-01-15 10:30:45 +0000")
    assert result is not None
    assert result.year == 2024
    assert result.month == 1
    assert result.day == 15
    assert result.hour == 10
    assert result.minute == 30
    assert result.second == 45


def test_parse_date_valid_iso_without_timezone():
    """Test _parse_date() returns correct datetime for ISO format without timezone."""
    result = _parse_date("2024-01-15 10:30:45")
    assert result is not None
    assert result.year == 2024
    assert result.month == 1
    assert result.day == 15
    assert result.hour == 10
    assert result.minute == 30


def test_parse_date_valid_iso_t_format():
    """Test _parse_date() returns correct datetime for ISO T format."""
    result = _parse_date("2024-01-15T10:30:45")
    assert result is not None
    assert result.year == 2024
    assert result.month == 1
    assert result.day == 15
    assert result.hour == 10
    assert result.minute == 30


def test_parse_date_valid_date_only():
    """Test _parse_date() returns correct datetime for date-only format."""
    result = _parse_date("2024-01-15")
    assert result is not None
    assert result.year == 2024
    assert result.month == 1
    assert result.day == 15
    assert result.hour == 0
    assert result.minute == 0


def test_parse_date_truncates_long_strings():
    """Test _parse_date() truncates long strings before parsing."""
    result = _parse_date("2024-01-15 10:30:45 +0000 extra text here")
    assert result is not None
    assert result.year == 2024
    assert result.month == 1
    assert result.day == 15


def test_parse_date_strips_whitespace():
    """Test _parse_date() strips leading/trailing whitespace."""
    result = _parse_date("  2024-01-15  ")
    assert result is not None
    assert result.year == 2024
    assert result.month == 1
