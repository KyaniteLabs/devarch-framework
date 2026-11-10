"""Regressions for the 2026-11-09 data-model roast fixes."""
import sqlite3
import subprocess
from datetime import datetime

from archaeology.classifiers.era_detector import SignalDetector
from archaeology.classifiers.work_kind import is_merge, kind_of, word_pattern
from archaeology.utils import _parse_date


def test_parse_date_keeps_the_offset_as_utc():
    assert _parse_date("2026-11-09 17:46:00 -0800") == datetime(2026, 11, 10, 1, 46)
    assert _parse_date("2026-11-09T17:46:00-08:00") == datetime(2026, 11, 10, 1, 46)
    assert _parse_date("2026-11-09 17:46:00") == datetime(2026, 11, 9, 17, 46)
    assert _parse_date("2026-11-09") == datetime(2026, 11, 9)
    assert _parse_date("nonsense") is None


def test_kind_of_prefers_prefix_then_words():
    assert kind_of("feat(ui): add a chart") == "feat"
    assert kind_of('Revert "feat: x"') == "fix"
    assert kind_of("chore: bump deps") == "ops"
    assert kind_of("Fix the decision cache") == "fix"
    assert kind_of("latest numbers") == "other"  # "test" inside "latest" is not a test


def test_merge_and_word_bounds():
    assert is_merge("Merge pull request 'x' (#3) from a into main")
    assert not is_merge("merged cells in the table renderer")
    rx = word_pattern(["ci", "test"])
    assert rx.search("ci: run on push") and rx.search("add a test")
    assert not rx.search("decision about the latest release")


def _db(tmp_path, rows):
    db = tmp_path / "a.db"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE commits (hash TEXT, date TEXT, author TEXT, message TEXT, repo TEXT)")
    con.executemany("INSERT INTO commits VALUES (?,?,?,?,?)", rows)
    con.commit(); con.close()
    return db


def test_commits_load_in_instant_order_across_zones(tmp_path):
    # Lexically 10:00 +0000 sorts before 11:00 +0900, but the +0900 one happened first.
    db = _db(tmp_path, [
        ("a", "2026-01-01 10:00:00 +0000", "x", "m", ""),
        ("b", "2026-01-01 11:00:00 +0900", "x", "m", ""),
    ])
    commits = SignalDetector(db_path=db)._load_commits()
    assert [c["date"][11:13] for c in commits] == ["11", "10"]


def test_velocity_runs_fold_into_one_signal():
    sigs = [
        {"index": 0, "date": "2026-01-10", "type": "velocity", "detail": "4.0x upshift (1→4 commits/day avg)", "strength": "strong"},
        {"index": 1, "date": "2026-01-11", "type": "velocity", "detail": "6.0x upshift (1→6 commits/day avg)", "strength": "strong"},
        {"index": 2, "date": "2026-01-12", "type": "velocity", "detail": "3.0x downshift (6→2 commits/day avg)", "strength": "moderate"},
        {"index": 3, "date": "2026-03-01", "type": "velocity", "detail": "5.0x upshift (1→5 commits/day avg)", "strength": "strong"},
    ]
    out = SignalDetector._fold_velocity(sigs)
    assert [s["date"] for s in out] == ["2026-01-10", "2026-01-12", "2026-03-01"]
    assert out[0]["detail"].startswith("6.0x") and out[0]["end"] == "2026-01-11"


def test_extractor_writes_email_and_parents(tmp_path):
    repo = tmp_path / "r"; repo.mkdir()
    env = {"GIT_AUTHOR_NAME": "A", "GIT_AUTHOR_EMAIL": "a@x.io", "GIT_COMMITTER_NAME": "A",
           "GIT_COMMITTER_EMAIL": "a@x.io", "HOME": str(tmp_path), "PATH": "/usr/bin:/bin"}
    run = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True, env=env)
    run("init", "-q"); (repo / "f").write_text("1"); run("add", "f"); run("commit", "-qm", "feat: one")
    from archaeology.extractors.git import extract_git_log
    out = tmp_path / "c.csv"
    assert extract_git_log(str(repo), str(out)) == 1
    header, row = out.read_text().splitlines()
    assert header == "hash,date,message,author,email,parents"
    assert row.split(",")[4] == "a@x.io"
