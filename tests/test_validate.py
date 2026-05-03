"""Tests for pipeline/core/validate.py validation logic."""

from pipeline.core.validate import MetricValidator


def test_compare_int_valid_values():
    """Test _compare() with valid int values returns True when equal."""
    validator = MetricValidator({}, {}, "", {})
    assert validator._compare(100, 100, "int")
    assert validator._compare(0, 0, "int")
    assert validator._compare(-5, -5, "int")


def test_compare_int_different_values():
    """Test _compare() with different int values returns False."""
    validator = MetricValidator({}, {}, "", {})
    assert not validator._compare(100, 99, "int")
    assert not validator._compare(0, 1, "int")


def test_compare_float_valid_values():
    """Test _compare() with valid float values returns True when close."""
    validator = MetricValidator({}, {}, "", {})
    assert validator._compare(100.0, 100.05, "float")
    assert validator._compare(0.0, 0.09, "float")
    assert validator._compare(50.5, 50.55, "float")


def test_compare_float_different_values():
    """Test _compare() with different float values returns False."""
    validator = MetricValidator({}, {}, "", {})
    assert not validator._compare(100.0, 100.2, "float")
    assert not validator._compare(0.0, 0.15, "float")


def test_compare_non_numeric_strings():
    """Test _compare() with non-numeric strings returns False, not crash."""
    validator = MetricValidator({}, {}, "", {})
    assert not validator._compare("n/a", 100, "int")
    assert not validator._compare("n/a", 100.0, "float")
    assert not validator._compare("unknown", "100", "int")
    assert not validator._compare("", 0, "int")


def test_compare_none_values():
    """Test _compare() with None values returns False gracefully."""
    validator = MetricValidator({}, {}, "", {})
    assert not validator._compare(None, 100, "int")
    assert not validator._compare(100, None, "int")
    assert not validator._compare(None, None, "int")


def test_find_author_in_verified_decimal_strings():
    """Test _find_author_in_verified() with decimal strings (commas)."""
    validator = MetricValidator(
        metrics={},
        data_json={},
        verified_stats="| Simon | 1,234 |\n| Liminal | 567 |",
        commit_eras={}
    )
    assert validator._find_author_in_verified("Simon") == 1234
    assert validator._find_author_in_verified("Liminal") == 567


def test_find_author_in_verified_not_found():
    """Test _find_author_in_verified() returns None when author not found."""
    validator = MetricValidator(
        metrics={},
        data_json={},
        verified_stats="| Simon | 100 |",
        commit_eras={}
    )
    assert validator._find_author_in_verified("UnknownAuthor") is None


def test_find_author_in_verified_malformed_decimal():
    """Test _find_author_in_verified() with malformed decimal strings."""
    validator = MetricValidator(
        metrics={},
        data_json={},
        verified_stats="| Simon | not-a-number |",
        commit_eras={}
    )
    assert validator._find_author_in_verified("Simon") is None


def test_metric_validator_handles_missing_metrics():
    """Test MetricValidator handles missing metrics gracefully without crashing."""
    validator = MetricValidator(
        metrics={"total_commits": {"value": 3951, "type": "int", "source": "meta"}},
        data_json={"telemetry_visualizations": {"meta": {"total_commits": 3951}}},
        verified_stats="",
        commit_eras={}
    )
    results = validator.validate(verbose=False)
    # Should have one ok result for total_commits
    assert any(r["status"] == "ok" for r in results if r["metric"] == "total_commits")


def test_metric_validator_skips_non_checkable_types():
    """Test MetricValidator skips dict/string/ratio types."""
    validator = MetricValidator(
        metrics={
            "dict_metric": {"value": {}, "type": "dict"},
            "string_metric": {"value": "text", "type": "string"},
            "ratio_metric": {"value": "1:2", "type": "ratio"},
        },
        data_json={},
        verified_stats="",
        commit_eras={}
    )
    results = validator.validate(verbose=False)
    assert all(r["status"] == "skip" for r in results)
