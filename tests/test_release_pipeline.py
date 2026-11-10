"""Real Git and installed-style CLI regressions for evidence integrity."""

import csv
import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from archaeology.analysis_runner import AnalysisRunner
from archaeology.cli import main
from archaeology.extractors.git import extract_git_log, repository_coverage
from archaeology.utils import _parse_date


def git(path, *args):
    return subprocess.check_output(["git", "-C", str(path), *args], text=True).strip()


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / "source"
    path.mkdir()
    git(path, "init")
    git(path, "config", "user.name", "Fixture")
    git(path, "config", "user.email", "fixture@example.invalid")
    git(path, "commit", "--allow-empty", "-m", "init")
    git(path, "checkout", "-b", "side")
    git(path, "commit", "--allow-empty", "-m", "score\x1fpipe|tab\tλ")
    return path


def test_all_refs_bare_worktree_and_delimiter(repo, tmp_path):
    bare = tmp_path / "bare.git"
    git(repo, "clone", "--bare", str(repo), str(bare))
    worktree = tmp_path / "linked"
    git(repo, "worktree", "add", "--detach", str(worktree))
    for source in (repo, bare, worktree):
        out = tmp_path / (source.name + ".csv")
        assert extract_git_log(str(source), str(out)) == 2
        with out.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2
        assert any("score\x1fpipe|tab\tλ" == row["message"] for row in rows)
        assert all(row["author"] == "Fixture" for row in rows)
        assert repository_coverage(str(source))["commit_count"] == 2


def test_shallow_rejected_before_output(repo, tmp_path, monkeypatch):
    shallow = tmp_path / "shallow"
    git(repo, "clone", "--depth=1", repo.as_uri(), str(shallow))
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(main, ["init", "trial"]).exit_code == 0
    result = runner.invoke(main, ["mine", str(shallow), "-p", "trial"])
    assert result.exit_code != 0
    assert "Shallow history" in result.output
    assert not (tmp_path / "projects/trial/data/github-commits.csv").exists()


def test_pipeline_outside_checkout(repo, tmp_path, monkeypatch):
    workspace = tmp_path / "consumer"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    runner = CliRunner()
    for args in (
        ["init", "trial"],
        ["mine", str(repo), "-p", "trial"],
        ["build-db", "trial"],
        ["signals", "trial"],
        ["analyze", "trial"],
        ["visualize", "trial"],
        ["export-report", "trial"],
        ["audit", "trial"],
    ):
        result = runner.invoke(main, args)
        assert result.exit_code == 0, (args, result.output, repr(result.exception))
    project = workspace / "projects/trial"
    metrics = json.loads((project / "deliverables/canonical-metrics.json").read_text())
    assert metrics["total_commits"] == 2
    html = (project / "deliverables/visuals/archaeology.html").read_text()
    assert "2 commits" in html and "35,600" not in html
    agent = json.loads(
        (project / "deliverables/analysis/analysis-agentic-workflow.json").read_text()
    )
    assert agent["session_depth_distribution"] is None
    assert agent["hook_effectiveness"] == []
    ml = json.loads((project / "deliverables/analysis/analysis-ml-pattern-mapper.json").read_text())
    assert all(
        x["confidence"] == "LOW" and x["estimated_token_waste"] is None for x in ml["mappings"]
    )


def test_dates_normalize_offset():
    assert _parse_date("2026-01-01T23:30:00-08:00") == _parse_date("2026-01-02T07:30:00Z")


def test_analysis_missing_database_is_not_absence(tmp_path):
    runner = AnalysisRunner("missing", str(tmp_path))
    with pytest.raises(ValueError, match="database missing"):
        runner.run_sdlc_gap_finder()


def test_empty_history_replaces_stale_csv(tmp_path):
    git(tmp_path, "init")
    out = tmp_path / "out.csv"
    out.write_text("stale")
    assert extract_git_log(str(tmp_path), str(out)) == 0
    assert out.read_text().strip() == "hash,date,message,author"


def test_audit_detects_modified_mining_input(repo, tmp_path, monkeypatch):
    from archaeology.audit import check_mined_history

    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    for args in (
        ["init", "audit-fixture"],
        ["mine", str(repo), "-p", "audit-fixture"],
        ["build-db", "audit-fixture"],
    ):
        result = runner.invoke(main, args)
        assert result.exit_code == 0, result.output
    assert not check_mined_history("audit-fixture", tmp_path)
    path = tmp_path / "projects/audit-fixture/data/github-commits.csv"
    path.write_text(path.read_text().replace("init", "changed"))
    assert any(
        f.code == "MINING_ARTIFACT_DRIFT" for f in check_mined_history("audit-fixture", tmp_path)
    )


def test_git_z_timestamp_is_portable(tmp_path, monkeypatch):
    import archaeology.extractors.git as extractor

    def read_git(repo_path, *args):
        return "a\x002026-01-02T07:30:00Z\x00subject\x00author\x00" if args[0] == "log" else "1\n"

    monkeypatch.setattr(extractor, "_git", read_git)
    out = tmp_path / "utc.csv"
    assert extract_git_log(str(tmp_path), str(out)) == 1
    with out.open(newline="") as f:
        row = next(csv.DictReader(f))
    assert row["date"] == "2026-01-02T07:30:00+00:00"


def test_csv_export_under_windows_newline_translation(repo, tmp_path, monkeypatch):
    import archaeology.utils as utils

    def windows_write(path, content, encoding="utf-8"):
        Path(path).write_bytes(content.replace("\n", "\r\n").encode(encoding))

    monkeypatch.setattr(utils, "atomic_write", windows_write)
    out = tmp_path / "windows.csv"
    assert extract_git_log(str(repo), str(out)) == 2
    with out.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    assert len(rows) == 3 and all(len(row) == 4 for row in rows)


@pytest.mark.parametrize("corruption", ["manifest", "database", "metrics", "visual"])
def test_audit_rejects_semantic_corruption(repo, tmp_path, monkeypatch, corruption):
    import sqlite3

    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    for args in (
        ["init", "corrupt"],
        ["mine", str(repo), "-p", "corrupt"],
        ["build-db", "corrupt"],
    ):
        result = runner.invoke(main, args)
        assert result.exit_code == 0, result.output
    project = tmp_path / "projects/corrupt"
    if corruption == "manifest":
        (project / "data/coverage.json").write_text("{not-json")
    elif corruption == "database":
        with sqlite3.connect(project / "data/archaeology.db") as conn:
            # Deliberately corrupt base records, bypassing FTS maintenance in this fixture.
            triggers = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='commits'"
            ).fetchall()
            for (name,) in triggers:
                conn.execute('DROP TRIGGER "' + name.replace('"', '""') + '"')
            conn.execute("UPDATE commits SET date='1900-01-01', message='changed'")
    elif corruption == "visual":
        visual = project / "deliverables/data.json"
        data = json.loads(visual.read_text())
        data["daily_commits"] = {"1900-01-01": 2}
        visual.write_text(json.dumps(data))
    else:
        canonical = project / "deliverables/canonical-metrics.json"
        data = json.loads(canonical.read_text())
        data["active_days"] = 9999
        data["span_days"] = 9999
        canonical.write_text(json.dumps(data))
        visual = project / "deliverables/data.json"
        data2 = json.loads(visual.read_text())
        data2["telemetry_visualizations"]["meta"] = data
        visual.write_text(json.dumps(data2))
    result = runner.invoke(main, ["audit", "corrupt"])
    assert result.exit_code != 0, result.output
    assert "HIGH" in result.output or "CRITICAL" in result.output


def test_coverage_records_detached_head(repo):
    git(repo, "checkout", "--detach")
    git(repo, "commit", "--allow-empty", "-m", "detached")
    assert repository_coverage(str(repo))["head"] == git(repo, "rev-parse", "HEAD")


@pytest.mark.parametrize(
    "args",
    [
        ["dashboard", "--no-open"],
        ["cascade", "trial", "--dry-run"],
        ["opportunity", "trial"],
        ["publish-static"],
    ],
)
def test_unsafe_legacy_commands_fail_before_mutation(args, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import http.server

    def forbidden(*a, **kw):
        raise AssertionError("must not bind a server")

    monkeypatch.setattr(http.server, "HTTPServer", forbidden)
    sentinel = tmp_path / "public"
    sentinel.mkdir()
    (sentinel / "owned.txt").write_text("preserve")
    before = {
        str(p.relative_to(tmp_path)): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()
    }
    result = CliRunner().invoke(main, args)
    assert result.exit_code != 0 and "disabled" in result.output.lower(), result.output
    assert before == {
        str(p.relative_to(tmp_path)): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()
    }


def test_opportunity_api_cannot_invent_profiles(tmp_path):
    from archaeology.opportunity_analyzers import OpportunityAnalyzer

    with pytest.raises(RuntimeError, match="disabled"):
        OpportunityAnalyzer("trial", str(tmp_path))


def test_stale_analysis_report_and_validation(repo, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    def run(*args):
        result = runner.invoke(main, list(args))
        assert result.exit_code == 0, (args, result.output, result.exception)

    for args in [
        ("init", "trial"),
        ("mine", str(repo), "-p", "trial"),
        ("build-db", "trial"),
        ("signals", "trial"),
        ("analyze", "trial"),
        ("visualize", "trial"),
        ("export-report", "trial"),
    ]:
        run(*args)
    git(repo, "commit", "--allow-empty", "-m", "new snapshot")
    run("mine", str(repo), "-p", "trial")
    run("build-db", "trial")
    exported = runner.invoke(main, ["export-report", "trial"])
    assert exported.exit_code != 0 and "stale" in exported.output.lower()
    assert runner.invoke(main, ["audit", "trial"]).exit_code != 0
    run("signals", "trial")
    run("analyze", "trial")
    run("visualize", "trial")
    run("export-report", "trial")
    run("validate", "trial")
    run("audit", "trial")
    html = tmp_path / "projects/trial/deliverables/visuals/archaeology.html"
    html.write_text("<script>alert(1)</script>")
    assert runner.invoke(main, ["validate", "trial"]).exit_code != 0
    assert runner.invoke(main, ["audit", "trial"]).exit_code != 0


def test_api_has_no_wildcard_cors():
    import io

    from archaeology.api import _json_response

    class Handler:
        def __init__(self):
            self.headers = {}
            self.wfile = io.BytesIO()

        def send_response(self, status):
            pass

        def send_header(self, key, value):
            self.headers[key] = value

        def end_headers(self):
            pass

    handler = Handler()
    _json_response(handler, {"ok": True})
    assert "Access-Control-Allow-Origin" not in handler.headers


def test_history_validator_rejects_active_content(tmp_path):
    from archaeology.validators.history import validate_history

    path = tmp_path / "deliverables/visuals/archaeology.html"
    path.parent.mkdir(parents=True)
    path.write_text(
        "<html><title>x</title><h1>x</h1><table><caption>x</caption></table><script>alert(1)</script></html>"
    )
    with pytest.raises(ValueError, match="active content"):
        validate_history(tmp_path)


def test_analysis_edit_cannot_be_laundered_by_report(repo, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    for args in [
        ["init", "trial"],
        ["mine", str(repo), "-p", "trial"],
        ["build-db", "trial"],
        ["analyze", "trial"],
        ["export-report", "trial"],
    ]:
        result = runner.invoke(main, args)
        assert result.exit_code == 0, result.output
    path = tmp_path / "projects/trial/deliverables/analysis/analysis-source-archaeologist.json"
    data = json.loads(path.read_text())
    data["quality_trajectory"]["assessment"] = "invented"
    path.write_text(json.dumps(data))
    assert runner.invoke(main, ["export-report", "trial"]).exit_code != 0
    assert runner.invoke(main, ["audit", "trial"]).exit_code != 0


def test_swot_strength_count(tmp_path):
    from archaeology.api import _parse_swot

    path = tmp_path / "deliverables/strategy/SWOT-ANALYSIS.md"
    path.parent.mkdir(parents=True)
    path.write_text("strengths 2 found\n## Strengths\n- one\n- two\n")
    assert _parse_swot(tmp_path)["strengths_count"] == 2
