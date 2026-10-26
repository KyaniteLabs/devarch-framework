"""Interface tests for archaeology.pipeline, the service behind the CLI and MCP adapters.

These call the service directly on a small real git repository in a temp
workspace. Nothing is mocked.
"""

import json
import os
import subprocess
from pathlib import Path

import pytest

from archaeology import pipeline
from archaeology.pipeline import PipelineError, ProjectRef

GIT_ENV = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
}


def _make_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    env = {**os.environ, **GIT_ENV,
           "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@example.com"}

    def git(*args, date=None):
        e = dict(env)
        if date:
            e["GIT_AUTHOR_DATE"] = e["GIT_COMMITTER_DATE"] = date
        subprocess.run(["git", "-C", str(path), *args], check=True, env=e, capture_output=True)

    git("init", "-q", "-b", "main")
    for i, day in enumerate(["2026-01-01", "2026-01-02", "2026-01-03", "2026-02-20", "2026-02-21"]):
        (path / f"f{i}.txt").write_text(str(i))
        git("add", "-A")
        git("commit", "-q", "-m", f"commit {i}", date=f"{day}T12:00:00+0000")
    return path


@pytest.fixture(scope="module")
def repo(tmp_path_factory):
    with pytest.MonkeyPatch.context() as mp:
        for k, v in GIT_ENV.items():
            mp.setenv(k, v)
        return _make_repo(tmp_path_factory.mktemp("src") / "repo")


@pytest.fixture
def ws(tmp_path, monkeypatch):
    """An empty workspace that is the cwd; DEVARCH_WORKSPACE is unset."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DEVARCH_WORKSPACE", raising=False)
    return tmp_path


@pytest.fixture(scope="module")
def built(tmp_path_factory, repo):
    """A workspace holding one mined project with a built database."""
    root = tmp_path_factory.mktemp("built")
    old = os.getcwd()
    os.chdir(root)
    os.environ.pop("DEVARCH_WORKSPACE", None)
    try:
        ref = ProjectRef.for_workspace("alpha")
        pipeline.init(ref, "d", "u")
        pipeline.mine(str(repo), ref)
        result = pipeline.build_db(ref)
        assert result.built, result.error
        yield root, ref
    finally:
        os.chdir(old)


# ── Project resolution ────────────────────────────────────────────────────────

def test_cli_ref_is_cwd_relative_and_requires_the_project(ws):
    with pytest.raises(PipelineError) as err:
        ProjectRef.for_cli("nope").resolve()
    assert err.value.kind == "project-missing"
    assert err.value.message == "Project 'nope' not found"
    assert err.value.path == os.path.join("projects", "nope")

    (ws / "projects" / "here").mkdir(parents=True)
    assert ProjectRef.for_cli("here").resolve() == Path("projects/here")


def test_cli_ref_can_name_a_project_that_does_not_exist_yet(ws):
    assert ProjectRef.for_cli("new", must_exist=False).resolve() == Path("projects/new")


def test_workspace_ref_resolves_inside_the_workspace_and_may_be_new(ws):
    assert ProjectRef.for_workspace("new").resolve() == (ws / "projects" / "new").resolve()


def test_workspace_ref_honours_devarch_workspace(ws, tmp_path_factory, monkeypatch):
    other = tmp_path_factory.mktemp("other")
    monkeypatch.setenv("DEVARCH_WORKSPACE", str(other))
    assert ProjectRef.for_workspace("p").resolve() == (other / "projects" / "p").resolve()
    assert ProjectRef.for_workspace("p").root() == other.resolve()
    assert ProjectRef.for_cli("p").root() == Path.cwd()


@pytest.mark.parametrize("name", ["", "../x", "a b", "a/b", "x" * 101])
def test_workspace_ref_rejects_unsafe_names(ws, name):
    with pytest.raises(ValueError):
        ProjectRef.for_workspace(name).resolve()


def test_workspace_rejects_a_missing_workspace_directory(ws, monkeypatch):
    monkeypatch.setenv("DEVARCH_WORKSPACE", str(ws / "absent"))
    with pytest.raises(ValueError, match="does not exist"):
        pipeline.get_workspace_root()


def test_in_workspace_changes_directory_and_restores_it(ws, tmp_path_factory, monkeypatch):
    other = tmp_path_factory.mktemp("other")
    monkeypatch.setenv("DEVARCH_WORKSPACE", str(other))
    before = os.getcwd()
    with pytest.raises(RuntimeError):
        with pipeline.in_workspace(ProjectRef.for_workspace("p")):
            assert Path.cwd().resolve() == other.resolve()
            raise RuntimeError("boom")
    assert os.getcwd() == before
    with pipeline.in_workspace(ProjectRef.for_cli("p")):
        assert os.getcwd() == before


# ── init ──────────────────────────────────────────────────────────────────────

def test_init_creates_layout_and_config_once(ws):
    ref = ProjectRef.for_workspace("proj")
    first = pipeline.init(ref, "My description", "https://example.com/r")
    assert first.created
    assert (first.project_dir / "data").is_dir() and (first.project_dir / "deliverables").is_dir()
    config = json.loads(first.config_path.read_text(encoding="utf-8"))
    assert config["name"] == "proj"
    assert config["description"] == "My description"
    assert config["repo_url"] == "https://example.com/r"

    second = pipeline.init(ref, "ignored", "ignored")
    assert not second.created
    assert json.loads(second.config_path.read_text(encoding="utf-8"))["description"] == "My description"


# ── mine ──────────────────────────────────────────────────────────────────────

def test_require_git_repo_classifies_failures(ws):
    with pytest.raises(PipelineError) as missing:
        pipeline.require_git_repo(str(ws / "absent"))
    assert missing.value.kind == "repo-missing"
    assert missing.value.message == f"Repository not found: {ws / 'absent'}"

    (ws / "plain").mkdir()
    with pytest.raises(PipelineError) as plain:
        pipeline.require_git_repo(str(ws / "plain"))
    assert plain.value.kind == "not-git"
    assert plain.value.message == f"Not a git repository: {ws / 'plain'}"


def test_mine_extracts_commits_and_reports_stages(ws, repo):
    ref = ProjectRef.for_workspace("m")
    pipeline.init(ref, "", "")
    events = []
    result = pipeline.mine(str(repo), ref, on_event=lambda e, d: events.append((e, d)))
    assert result.commits == 5
    assert events == [("start", None), ("csv-done", 5)]
    assert Path(result.csv_path).read_text(encoding="utf-8").count("\n") == 6  # header + 5
    assert Path(result.stats_path).exists()


def test_mine_validates_the_repo_before_touching_the_project(ws):
    with pytest.raises(PipelineError):
        pipeline.mine(str(ws / "absent"), ProjectRef.for_workspace("never"))
    assert not (ws / "projects" / "never").exists()


def test_mine_expands_home_only_when_asked(ws, repo, monkeypatch):
    home = repo.parent
    monkeypatch.setenv("HOME", str(home))
    ref = ProjectRef.for_workspace("tilde")
    tilde = "~/repo"
    assert pipeline.mine(tilde, ref, expand_repo_path=True).commits == 5
    with pytest.raises(RuntimeError):  # git is handed the literal "~/repo"
        pipeline.mine(tilde, ref, expand_repo_path=False)


def test_mine_lets_extraction_errors_propagate(ws):
    broken = ws / "broken"
    (broken / ".git").mkdir(parents=True)
    with pytest.raises(RuntimeError, match="git log failed"):
        pipeline.mine(str(broken), ProjectRef.for_workspace("b"))


# ── build-db, signals, analyze, audit, reports ────────────────────────────────

def test_build_db_in_process_reports_the_database(built):
    root, ref = built
    result = pipeline.build_db(ref)
    assert result.built and result.error is None
    assert result.db_path == (root / "projects" / "alpha" / "data" / "archaeology.db").resolve()


def test_signals_need_a_database(ws):
    pipeline.init(ProjectRef.for_workspace("empty"), "", "")
    with pytest.raises(PipelineError) as err:
        pipeline.signals(ProjectRef.for_workspace("empty"))
    assert err.value.kind == "no-database"


def test_signals_find_the_gap_and_honour_min_gap_days(built):
    _, ref = built
    found = pipeline.signals(ref)
    assert len(found.signals) == 1 and len(found.clusters) == 2
    assert found.output_path.name == "detected-signals.json" and found.output_path.exists()
    assert pipeline.signals(ref, min_gap_days=100).signals == []
    assert pipeline.signals(ref, config={"min_gap_days": 100}).signals == []


def test_validate_vectors_defaults_to_all_and_lists_unknowns(ws):
    from archaeology.analysis_runner import AnalysisRunner

    assert pipeline.validate_vectors([]) == list(AnalysisRunner.VECTORS)
    assert pipeline.validate_vectors(["sdlc-gap-finder"]) == ["sdlc-gap-finder"]
    with pytest.raises(PipelineError) as err:
        pipeline.validate_vectors(["zzz", "aaa"])
    assert err.value.message == "Unknown vector: aaa\nUnknown vector: zzz"


def test_analysis_dir_is_created(ws):
    pipeline.init(ProjectRef.for_workspace("a"), "", "")
    path = pipeline.analysis_dir(ProjectRef.for_workspace("a"))
    assert path.is_dir() and path.name == "analysis"


def test_analyze_runs_requested_vectors(built):
    _, ref = built
    result = pipeline.analyze(ref, ["sdlc-gap-finder"])
    assert list(result.results) == ["sdlc-gap-finder"]
    assert result.failed == {}


def test_analyze_leaves_unknown_project_to_the_engine(ws):
    with pytest.raises(ValueError, match="not found"):
        pipeline.analyze(ProjectRef.for_workspace("ghost"))


def test_audit_reports_findings_and_blocking(built):
    _, ref = built
    result = pipeline.audit(ref, "HIGH")
    assert result.findings and result.blocking
    assert result.summary["CRITICAL"] >= 1
    assert pipeline.audit(ref, "CRITICAL").blocking == (result.summary["CRITICAL"] > 0)


def test_audit_without_fail_on_skips_the_verdict(built):
    _, ref = built
    result = pipeline.audit(ref, None)
    assert result.findings and result.blocking is None


def test_audit_of_a_missing_project_is_a_critical_finding(ws):
    result = pipeline.audit(ProjectRef.for_cli("ghost"))
    assert [f.code for f in result.findings] == ["PROJECT_MISSING"]
    assert result.blocking


def test_render_report_validates_format_and_project(ws):
    with pytest.raises(PipelineError, match="Invalid format 'pdf'"):
        pipeline.render_report(ProjectRef.for_workspace("x"), "pdf")
    with pytest.raises(PipelineError) as err:
        pipeline.render_report(ProjectRef.for_workspace("x"), "html")
    assert err.value.kind == "project-missing"


def test_render_report_writes_markdown_and_html(built):
    _, ref = built
    md = pipeline.render_report(ref, "markdown")
    assert md.fmt == "markdown" and md.output_path.suffix == ".md" and md.output_path.exists()
    html = pipeline.render_report(ref, " HTML ")
    assert html.fmt == "html" and html.output_path.name == "report.html"
    assert "<html" in html.output_path.read_text(encoding="utf-8").lower()


def test_render_project_index_writes_the_dashboard_page(built):
    _, ref = built
    path = pipeline.render_project_index(ref)
    assert path.name == "index.html" and path.read_text(encoding="utf-8")


def test_render_project_index_needs_the_project(ws):
    with pytest.raises(PipelineError) as err:
        pipeline.render_project_index(ProjectRef.for_workspace("ghost"))
    assert err.value.kind == "project-missing"


# ── visualize (template renderer) ─────────────────────────────────────────────

def test_render_visualization_needs_the_template(ws):
    pipeline.init(ProjectRef.for_cli("v", must_exist=False), "", "")
    with pytest.raises(PipelineError) as err:
        pipeline.render_visualization(ProjectRef.for_cli("v"))
    assert err.value.kind == "template-missing"
    assert err.value.message == f"Template not found at {pipeline.DEFAULT_TEMPLATE}"


def test_render_visualization_hydrates_template_and_warns_without_data(ws):
    pipeline.init(ProjectRef.for_cli("v", must_exist=False), "", "")
    template = ws / "t.html"
    template.write_text("<title>DevArch Framework</title><h1>{{PROJECT_NAME}}</h1>{{TOTAL_COMMITS}}",
                        encoding="utf-8")
    result = pipeline.render_visualization(ProjectRef.for_cli("v"), template=str(template))
    html = Path(result.output_path).read_text(encoding="utf-8")
    assert "<title>V — DevArch Framework</title>" in html and "<h1>V</h1>803" in html
    assert result.warning and result.warning.startswith("Warning:") and "data.json" in result.warning


def test_render_visualization_rejects_broken_project_json(ws):
    ref = ProjectRef.for_cli("v", must_exist=False)
    pipeline.init(ref, "", "")
    (ws / "projects" / "v" / "project.json").write_text("{nope", encoding="utf-8")
    template = ws / "t.html"
    template.write_text("x", encoding="utf-8")
    with pytest.raises(PipelineError) as err:
        pipeline.render_visualization(ProjectRef.for_cli("v"), template=str(template))
    assert err.value.kind == "invalid-json"


def test_load_config_file(ws):
    good = ws / "good.json"
    good.write_text('{"min_gap_days": 3}', encoding="utf-8")
    assert pipeline.load_config_file(str(good)) == {"min_gap_days": 3}
    bad = ws / "bad.json"
    bad.write_text("{", encoding="utf-8")
    with pytest.raises(PipelineError) as err:
        pipeline.load_config_file(str(bad))
    assert err.value.kind == "invalid-json" and str(bad) in err.value.message


# ── run-pipeline ──────────────────────────────────────────────────────────────

def test_run_pipeline_runs_every_step(ws, repo):
    run = pipeline.run_pipeline(str(repo), ProjectRef.for_workspace("full"))
    assert run.init_created and run.failed_at is None
    assert run.mine.commits == 5
    assert run.build.built
    assert run.signal_count == 1
    assert isinstance(run.analysis, list) and "sdlc-gap-finder" in run.analysis


def test_run_pipeline_stops_when_mining_fails(ws):
    (ws / "plain").mkdir()
    run = pipeline.run_pipeline(str(ws / "plain"), ProjectRef.for_workspace("stop"))
    assert run.failed_at == "mine"
    assert run.mine is None and run.build is None
    assert run.mine_error == f"Not a git repository: {ws / 'plain'}"
