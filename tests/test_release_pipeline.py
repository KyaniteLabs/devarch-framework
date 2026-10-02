"""Real Git and installed-style CLI regressions for evidence integrity."""
import csv
import json
import subprocess
from pathlib import Path
import pytest
from click.testing import CliRunner
from archaeology.cli import main
from archaeology.extractors.git import extract_git_log, repository_coverage
from archaeology.analysis_runner import AnalysisRunner
from archaeology.utils import _parse_date


def git(path, *args):
    return subprocess.check_output(['git', '-C', str(path), *args], text=True).strip()


@pytest.fixture
def repo(tmp_path):
    path = tmp_path / 'source'; path.mkdir()
    git(path, 'init'); git(path, 'config', 'user.name', 'Fixture')
    git(path, 'config', 'user.email', 'fixture@example.invalid')
    git(path, 'commit', '--allow-empty', '-m', 'init')
    git(path, 'checkout', '-b', 'side')
    git(path, 'commit', '--allow-empty', '-m', 'score\x1fpipe|tab\tλ')
    return path


def test_all_refs_bare_worktree_and_delimiter(repo, tmp_path):
    bare = tmp_path / 'bare.git'; git(repo, 'clone', '--bare', str(repo), str(bare))
    worktree = tmp_path / 'linked'; git(repo, 'worktree', 'add', '--detach', str(worktree))
    for source in (repo, bare, worktree):
        out = tmp_path / (source.name + '.csv')
        assert extract_git_log(str(source), str(out)) == 2
        with out.open(newline='', encoding='utf-8') as f: rows = list(csv.DictReader(f))
        assert len(rows) == 2
        assert any('score\x1fpipe|tab\tλ' == row['message'] for row in rows)
        assert all(row['author'] == 'Fixture' for row in rows)
        assert repository_coverage(str(source))['commit_count'] == 2


def test_shallow_rejected_before_output(repo, tmp_path, monkeypatch):
    shallow = tmp_path / 'shallow'
    git(repo, 'clone', '--depth=1', repo.as_uri(), str(shallow))
    monkeypatch.chdir(tmp_path)
    runner = CliRunner(); assert runner.invoke(main, ['init','trial']).exit_code == 0
    result = runner.invoke(main, ['mine', str(shallow), '-p', 'trial'])
    assert result.exit_code != 0
    assert 'Shallow history' in result.output
    assert not (tmp_path / 'projects/trial/data/github-commits.csv').exists()


def test_pipeline_outside_checkout(repo, tmp_path, monkeypatch):
    workspace = tmp_path / 'consumer'; workspace.mkdir(); monkeypatch.chdir(workspace)
    runner = CliRunner()
    for args in (['init','trial'], ['mine',str(repo),'-p','trial'], ['build-db','trial'],
                 ['signals','trial'], ['analyze','trial'], ['visualize','trial'],
                 ['export-report','trial'], ['audit','trial']):
        result = runner.invoke(main, args)
        assert result.exit_code == 0, (args, result.output, repr(result.exception))
    project = workspace / 'projects/trial'
    metrics = json.loads((project / 'deliverables/canonical-metrics.json').read_text())
    assert metrics['total_commits'] == 2
    html = (project / 'deliverables/visuals/archaeology.html').read_text()
    assert '2 commits' in html and '35,600' not in html
    agent = json.loads((project / 'deliverables/analysis/analysis-agentic-workflow.json').read_text())
    assert agent['session_depth_distribution'] is None
    assert agent['hook_effectiveness'] == []
    ml = json.loads((project / 'deliverables/analysis/analysis-ml-pattern-mapper.json').read_text())
    assert all(x['confidence'] == 'LOW' and x['estimated_token_waste'] is None for x in ml['mappings'])


def test_dates_normalize_offset():
    assert _parse_date('2026-01-01T23:30:00-08:00') == _parse_date('2026-01-02T07:30:00Z')


def test_analysis_missing_database_is_not_absence(tmp_path):
    runner = AnalysisRunner('missing', str(tmp_path))
    with pytest.raises(ValueError, match='database missing'):
        runner.run_sdlc_gap_finder()


def test_empty_history_replaces_stale_csv(tmp_path):
    git(tmp_path, 'init')
    out = tmp_path / 'out.csv'; out.write_text('stale')
    assert extract_git_log(str(tmp_path), str(out)) == 0
    assert out.read_text().strip() == 'hash,date,message,author'


def test_audit_detects_modified_mining_input(repo, tmp_path, monkeypatch):
    from archaeology.audit import check_mined_history
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    for args in (['init','audit-fixture'], ['mine',str(repo),'-p','audit-fixture'], ['build-db','audit-fixture']):
        result = runner.invoke(main, args)
        assert result.exit_code == 0, result.output
    assert not check_mined_history('audit-fixture', tmp_path)
    path = tmp_path / 'projects/audit-fixture/data/github-commits.csv'
    path.write_text(path.read_text().replace('init','changed'))
    assert any(f.code == 'MINING_ARTIFACT_DRIFT' for f in check_mined_history('audit-fixture', tmp_path))
