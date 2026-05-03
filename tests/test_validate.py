"""Tests for archaeology audit module — replaces old pipeline.core.validate tests."""

from pathlib import Path

from archaeology.audit import AuditFinding, check_project_config


def test_audit_finding_severity_order():
    """Test that AuditFinding severity levels are distinct."""
    info = AuditFinding(severity="INFO", code="TEST", message="test", path="x")
    high = AuditFinding(severity="HIGH", code="TEST", message="test", path="x")
    critical = AuditFinding(severity="CRITICAL", code="TEST", message="test", path="x")
    assert critical.severity != info.severity
    assert high.severity != info.severity


def test_audit_finding_fields():
    """Test AuditFinding dataclass has expected fields."""
    f = AuditFinding(severity="INFO", code="TEST_CODE", message="test msg", path="a/b")
    assert f.severity == "INFO"
    assert f.code == "TEST_CODE"
    assert f.message == "test msg"
    assert f.path == "a/b"


def test_check_project_config_missing_dir():
    """Test check_project_config handles missing project directory gracefully."""
    findings = check_project_config("nonexistent-project", root=Path("/tmp"))
    assert isinstance(findings, list)


def test_audit_finding_optional_detail():
    """Test AuditFinding optional detail field."""
    f = AuditFinding(severity="INFO", code="TEST", message="test", detail="extra info")
    assert f.detail == "extra info"


def test_audit_finding_defaults():
    """Test AuditFinding with minimal required fields."""
    f = AuditFinding(severity="INFO", code="TEST", message="test")
    assert f.path is None
    assert f.detail is None
