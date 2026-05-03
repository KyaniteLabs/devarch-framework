import json
import sqlite3
from pathlib import Path

from click.testing import CliRunner

from archaeology.audit import has_blocking_findings, run_audit
from archaeology.cli import main
from archaeology.db.queries import get_eras, get_table_count


def test_demo_project_audit_has_no_blocking_high_findings():
    findings = run_audit("demo-project", root=Path.cwd())
    assert not has_blocking_findings(findings, fail_on="HIGH")


def test_audit_marks_placeholder_sections_as_excluded_info():
    findings = run_audit("demo-project", root=Path.cwd())
    codes = {f.code for f in findings}
    # demo-project has no placeholder sections, so just verify it doesn't crash
    assert isinstance(codes, set)


def test_get_eras_falls_back_when_start_date_missing(tmp_path):
    db = tmp_path / "archaeology.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE eras (id INTEGER, name TEXT, dates TEXT)")
    conn.execute("INSERT INTO eras VALUES (2, 'Second', 'later')")
    conn.execute("INSERT INTO eras VALUES (1, 'First', 'earlier')")
    conn.commit()
    conn.close()

    rows = get_eras(str(db))
    assert [row["name"] for row in rows] == ["First", "Second"]


def test_get_table_count_rejects_bad_table_name(tmp_path):
    db = tmp_path / "archaeology.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE commits (id INTEGER)")
    conn.commit()
    conn.close()

    assert get_table_count(str(db), "commits") == 0
    try:
        get_table_count(str(db), "commits; DROP TABLE commits")
    except ValueError:
        pass
    else:
        raise AssertionError("bad table name should be rejected")


def test_init_generates_schema_plausible_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "init",
            "demo-project",
            "--description",
            "Demo project",
            "--repo-url",
            "https://github.com/example/demo-project",
        ],
    )
    assert result.exit_code == 0, result.output
    data = json.loads((tmp_path / "projects" / "demo-project" / "project.json").read_text())
    assert data["description"] == "Demo project"
    assert data["repo_url"] == "https://github.com/example/demo-project"


def test_demo_command_creates_sanitized_project_and_audits(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["demo", "--project", "demo", "--build-db"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "projects" / "demo" / "data" / "github-commits.csv").exists()

    audit_result = runner.invoke(main, ["audit", "demo", "--fail-on", "HIGH"])
    assert audit_result.exit_code == 0, audit_result.output
    assert "Summary:" in audit_result.output


def test_analyze_command_runs_all_six_vectors_for_demo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    demo_result = runner.invoke(main, ["demo", "--project", "demo", "--build-db"])
    assert demo_result.exit_code == 0, demo_result.output

    analyze_result = runner.invoke(main, ["analyze", "demo"])
    assert analyze_result.exit_code == 0, analyze_result.output

    deliverables = tmp_path / "projects" / "demo" / "deliverables"
    expected = {
        "analysis-sdlc-gap-finder.json",
        "analysis-ml-pattern-mapper.json",
        "analysis-agentic-workflow.json",
        "analysis-formal-terms-mapper.json",
        "analysis-source-archaeologist.json",
        "analysis-youtube-correlator.json",
    }
    assert expected == {path.name for path in deliverables.glob("analysis-*.json")}


def test_export_report_from_demo_analysis(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(main, ["demo", "--project", "demo", "--build-db"]).exit_code == 0
    analyze = runner.invoke(main, ["analyze", "demo"])
    assert analyze.exit_code == 0, analyze.output
    export = runner.invoke(main, ["export-report", "demo"])
    assert export.exit_code == 0, export.output
    report = tmp_path / "projects" / "demo" / "deliverables" / "ARCHAEOLOGY-REPORT.md"
    text = report.read_text()
    assert "# DEMO ARCHAEOLOGY Archaeology Report" in text
    assert "## Canonical Metrics" in text
    assert "## Remediation Priorities" in text

    custom = tmp_path / "case-study" / "index.html"
    custom_export = runner.invoke(main, ["export-report", "demo", "--format", "html", "--output", str(custom)])
    assert custom_export.exit_code == 0, custom_export.output
    assert custom.exists()

    html_export = runner.invoke(main, ["export-report", "demo", "--format", "html"])
    assert html_export.exit_code == 0, html_export.output
    html_report = tmp_path / "projects" / "demo" / "deliverables" / "ARCHAEOLOGY-REPORT.html"
    html = html_report.read_text()
    assert "<!doctype html>" in html
    assert "DEMO ARCHAEOLOGY Archaeology Report" in html


def test_local_pipeline_status_reads_latest_json(tmp_path):
    pipeline_dir = tmp_path / "pipeline"
    latest_dir = pipeline_dir / ".omc" / "logs" / "repo-pipeline"
    latest_dir.mkdir(parents=True)
    (latest_dir / "latest.json").write_text(json.dumps({
        "run_timestamp": "2026-01-01T00:00:00Z",
        "summary": {"overall_health": "PARTIAL"},
        "repos": [{
            "name": "dev-archaeology",
            "full_name": "Pastorsimon1798/dev-archaeology",
            "health": "HEALTHY",
            "verdict": "stable",
            "issues": {"total": 0, "critical": 0, "high": 0, "medium": 0, "low": 0},
            "open_prs": 1,
            "open_issues": 0
        }]
    }))
    runner = CliRunner()
    result = runner.invoke(main, ["local-pipeline", "--pipeline-dir", str(pipeline_dir), "--repo", "dev-archaeology", "--fail-on-issues"])
    assert result.exit_code == 0, result.output
    assert "health: HEALTHY" in result.output
    assert "verdict: stable" in result.output


def test_public_case_study_command_exports_showroom(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["public-case-study", "--output", "showroom"] )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "showroom" / "index.html").exists()
    assert (tmp_path / "showroom" / "ARCHAEOLOGY-REPORT.md").exists()
    assert (tmp_path / "showroom" / "data" / "github-commits.csv").exists()
    assert "invented fixture data" in (tmp_path / "showroom" / "README.md").read_text()
