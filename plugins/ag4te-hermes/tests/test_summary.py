import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("ag4te_under_test", PKG / "__init__.py")
ag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ag)

STATS = ("aaaa111\x1f2026-05-01 09:15:00 -0700\x1ffeat(ui): add strata ribbon\x1fAda\n\n"
         " 3 files changed, 120 insertions(+), 4 deletions(-)\n"
         "bbbb222\x1f2026-05-02 23:40:00 -0700\x1ffix: guard empty repo\x1fAda\n\n"
         " 1 file changed, 2 insertions(+)\n"
         "cccc333\x1f2026-05-20 10:00:00 +0200\x1fUpdate README\x1fLin\n\n"
         "dddd444\x1fnot a date\x1fbroken line\x1fX\n")


def make_project(tmp_path, stats=STATS, signals=None):
    pdir = tmp_path / "projects" / "demo"
    (pdir / "data").mkdir(parents=True)
    (pdir / "data" / "github-commits-with-stats.txt").write_text(stats, encoding="utf-8")
    if signals is not None:
        (pdir / "data" / "detected-signals.json").write_text(json.dumps(signals), encoding="utf-8")
    return pdir


def git_repo(path, commits=None):
    """A real git repo; commits are (iso date, subject, author name, author email, {file: text})."""
    commits = commits or [
        ("2026-05-01T09:15:00-07:00", "feat(ui): add strata ribbon", "Ada", "ada@x.io", {"a.py": "1\n2\n3\n"}),
        ("2026-05-02T23:40:00-07:00", "fix: guard empty repo", "Ada Lovelace", "ada@x.io", {"a.py": "1\n2\n"}),
        ("2026-05-20T10:00:00+02:00", "Update README", "Lin", "lin@x.io", {"README.md": "hi\n"}),
    ]
    path.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True, env=env)
    for when, msg, name, email, files in commits:
        for f, text in files.items():
            (path / f).write_text(text)
        subprocess.run(["git", "-C", str(path), "add", "-A"], check=True, env=env)
        subprocess.run(["git", "-C", str(path), "-c", f"user.name={name}", "-c", f"user.email={email}",
                        "commit", "-q", "--allow-empty", "-m", msg], check=True,
                       env={**env, "GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when})
    return path


def test_kinds():
    assert ag.kind_of("feat(x)!: y") == "feat"
    assert ag.kind_of("chore: bump") == "ops"
    assert ag.kind_of("Merge pull request #3") == "other"   # merges are flagged by parents, not words
    assert ag.kind_of('Revert "feat: x"') == "fix"
    assert ag.kind_of("Fix the thing") == "fix"
    assert ag.kind_of("Update README") == "docs"
    assert ag.kind_of("wibble") == "other"
    assert ag.kind_of("") == "other"
    assert ag.kind_of("eval: fix mapeOf double scaling") == "fix"     # area prefix, not a type
    assert ag.kind_of("site: take GH_HEAD only from a fetch") == "other"


def test_summary_basic(tmp_path):
    d = ag.summarize(make_project(tmp_path), project="demo", settings={"time_zone": "America/Los_Angeles"})
    assert d["commit_count"] == 3
    assert d["first"] == "2026-05-01" and d["last"] == "2026-05-20"
    assert len(d["days"]) == d["span_days"] == 20
    assert d["insertions"] == 122 and d["deletions"] == 4
    assert d["gaps"] == [{"start": "2026-05-03", "end": "2026-05-19", "days": 17}]
    assert d["longest_streak"] == 2
    # one clock: the project zone, 23:40 Saturday in Los Angeles
    assert d["rhythm"][5][23] == 1 and d["manifest"]["time_zone"] == "America/Los_Angeles"
    assert d["commits"][0]["sha"].startswith("cccc")  # newest first
    assert len(d["clusters"]) == 2  # computed eras split by the quiet gap
    assert sum(d["kind_totals"]) == 3


def test_summary_signals_and_bad_json(tmp_path):
    sig = {"signals": [{"date": "2026-05-02", "type": "velocity", "detail": "x" * 999, "strength": "strong"},
                       {"date": "nope"}, "junk"],
           "cluster_summary": [{"start_date": "2026-05-01", "end_date": "2026-05-02", "commit_count": 2},
                               {"start_date": "2026-05-09", "end_date": "2026-05-01"}]}
    d = ag.summarize(make_project(tmp_path, signals=sig))
    assert len(d["signals"]) == 1 and len(d["signals"][0]["detail"]) == 240
    assert len(d["clusters"]) == 2   # eras come from the plugin's own gap rule, not cluster_summary
    (tmp_path / "projects" / "demo" / "data" / "detected-signals.json").write_text("{corrupt")
    assert ag.summarize(tmp_path / "projects" / "demo")["commit_count"] == 3


def test_empty(tmp_path):
    d = ag.summarize(make_project(tmp_path, stats=""))
    assert d["empty"] and d["days"] == []


@pytest.mark.parametrize("bad", ["", "A", "-x", "../x", "a/b", "a" * 64, None, 3, "é"])
def test_bad_project_names(bad):
    with pytest.raises(ag.DigError):
        ag.validate_project(bad)


def test_resolve_repo(tmp_path):
    root = tmp_path / "ws"
    (root / "good" / ".git").mkdir(parents=True)
    (root / "plain").mkdir()
    outside = tmp_path / "outside"
    (outside / ".git").mkdir(parents=True)
    (root / "link").symlink_to(outside)
    s = {"repo_roots": str(root)}
    assert ag.resolve_repo(str(root / "good"), s) == (root / "good").resolve()
    for bad in [str(root / "plain"), str(outside), str(root / "link"), str(root / "good" / ".." / ".." / "outside"),
                str(root / "missing"), "", "a\x00b"]:
        with pytest.raises(ag.DigError):
            ag.resolve_repo(bad, s)
    names = [r["name"] for r in ag.candidate_repos(s)]
    assert names == ["good"]


def test_run_dig_with_fake_runner(tmp_path):
    root = tmp_path / "ws"
    git_repo(root / "Repo One")
    s = {"repo_roots": str(root), "data_dir": str(tmp_path / "data"), "time_zone": "UTC"}
    calls = []

    def runner(args, settings):
        calls.append(args[0])
        return {"ok": args[0] != "signals", "err": "Traceback\nboom" if args[0] == "signals" else ""}

    repo = ag.resolve_repo(str(root / "Repo One"), s)
    st = ag.run_dig(repo, ag.project_from_repo(repo), s, runner=runner)
    assert calls == ["init", "mine", "build-db", "signals"]
    assert st["state"] == "done" and st["warnings"] == ["Finding signals: boom"]
    d = ag.load_dig("repo-one", s)
    assert d["commit_count"] == 3 and d["manifest"]["source"] == "git"
    assert [a["name"] for a in d["authors"]][:1] == ["Ada Lovelace"] and d["author_count"] == 2
    assert [p["project"] for p in ag.list_projects(s)] == ["repo-one"]


def test_required_step_failure_stops(tmp_path):
    root = tmp_path / "ws"
    (root / "r" / ".git").mkdir(parents=True)          # looks like a repo, git can't read it
    s = {"repo_roots": str(root), "data_dir": str(tmp_path / "data")}
    calls = []
    st = ag.run_dig(ag.resolve_repo(str(root / "r"), s), "r", s,
                    runner=lambda a, _: calls.append(a[0]) or {"ok": True})
    assert st["state"] == "failed" and "Reading git history" in st["error"]
    assert calls == ["init"] and ag.load_dig("r", s) is None


def test_devarch_failure_is_optional(tmp_path):
    root = tmp_path / "ws"
    git_repo(root / "r")
    s = {"repo_roots": str(root), "data_dir": str(tmp_path / "data")}
    st = ag.run_dig(ag.resolve_repo(str(root / "r"), s), "r", s,
                    runner=lambda a, _: {"ok": a[0] == "init", "err": "uvx: not found"})
    assert st["state"] == "done" and len(st["warnings"]) == 3
    assert ag.load_dig("r", s)["commit_count"] == 3


def test_run_devarch_scrubs_env(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")
    s = {"devarch_command": f"{sys.executable} -c \"import os,json;print(json.dumps(dict(os.environ)))\"",
         "data_dir": str(tmp_path / "d"), "timeout_seconds": 30}
    r = ag.run_devarch([], s)
    env = json.loads(r["out"])
    assert r["ok"] and "OPENAI_API_KEY" not in env and env["DEVARCH_WORKSPACE"] == str(tmp_path / "d")
    assert ag.run_devarch([], {**s, "devarch_command": "/no/such/bin"})["ok"] is False
    assert ag.run_devarch([], {**s, "devarch_command": "'unbalanced"})["ok"] is False


def test_slash_refuses_dig_on_gateway(monkeypatch):
    monkeypatch.setenv("HERMES_PLATFORM", "telegram")
    assert "off on chat platforms" in ag._slash("dig ~/x")
    assert ag._slash("") == ag.USAGE
    assert "names are" in ag._slash("show ../etc")


SAMPLE = os.environ.get("AG4TE_SAMPLE")


@pytest.mark.skipif(not SAMPLE, reason="set AG4TE_SAMPLE to a real DevArch project dir")
def test_real_sample():
    d = ag.summarize(Path(SAMPLE))
    assert d["commit_count"] > 0 and len(d["days"]) == d["span_days"]
    assert sum(x["n"] for x in d["days"]) <= d["commit_count"]
    json.dumps(d)


def test_author_aliases_merge_one_person():
    from collections import Counter
    a = ag.author_aliases(Counter({"Simon": 5, "simon": 2, "Simon Gonzalez De Cruz": 3, "Ana": 1, "Ana Ruiz": 1, "Ana Lopez": 1, "dependabot[bot]": 4}))
    assert a["Simon"] == a["simon"] == a["Simon Gonzalez De Cruz"] == "Simon Gonzalez De Cruz"
    assert a["Ana"] == "Ana"  # two candidates: don't guess
    assert a["dependabot[bot]"] == "dependabot[bot]"


def test_dig_state_machine_transitions(tmp_path):
    pdir = tmp_path / "p"
    with pytest.raises(ag.DigError):
        ag._set_status(pdir, state="done")            # none -> done skips running
    ag._set_status(pdir, fresh=True, state="running", step=0, finished_at=123.0)
    ag._set_status(pdir, state="done", step=7)
    with pytest.raises(ag.DigError):
        ag._set_status(pdir, state="failed")          # a late writer cannot flip a terminal state
    st = ag._set_status(pdir, fresh=True, state="running", step=0)
    assert "finished_at" not in st and st["step"] == 0  # a re-dig starts a clean record
    ag._set_status(pdir, state="failed", error="x")
    ag._set_status(pdir, state="running")             # failed -> running (retry)


def test_redig_after_done_and_interrupted(tmp_path):
    root = tmp_path / "ws"
    git_repo(root / "r")
    s = {"repo_roots": str(root), "data_dir": str(tmp_path / "data")}
    repo = ag.resolve_repo(str(root / "r"), s)

    def runner(args, settings):
        return {"ok": True}

    assert ag.run_dig(repo, "r", s, runner=runner)["state"] == "done"
    assert ag.run_dig(repo, "r", s, runner=runner)["state"] == "done"   # done -> running -> done
    # A status left "running" with no live thread reads as interrupted.
    ag._set_status(ag.project_dir("r", s), fresh=True, state="running", step=2)
    st = ag.read_status("r", s)
    assert st["state"] == "failed" and st["interrupted"] and "dig again" in st["error"]


def _wait(project, s, timeout=20):
    import time as _t
    end = _t.time() + timeout
    while _t.time() < end:
        t = ag._jobs.get(project)
        if t is None or not t.is_alive():
            return ag.read_status(project, s)
        _t.sleep(0.05)
    raise AssertionError("dig did not finish")


def test_cancel_kills_running_command_then_resume_skips_done_steps(tmp_path):
    import sys
    import time as _t
    root = tmp_path / "ws"
    git_repo(root / "r")
    s = {"repo_roots": str(root), "data_dir": str(tmp_path / "data"),
         "devarch_command": f"{sys.executable} -c 'import sys,time; time.sleep(0 if sys.argv[1]==\"init\" else 60)'"}
    t0 = _t.time()
    ag.start_dig(str(root / "r"), "r", s)
    for _ in range(200):   # wait until it is inside "Mining commits"
        if ag.read_status("r", s).get("label") == "Mining commits":
            break
        _t.sleep(0.05)
    with pytest.raises(ag.DigError):
        ag.start_dig(str(root / "r"), "r", s)          # one at a time
    assert ag.cancel_dig("r", s)["cancelling"]
    st = _wait("r", s)
    assert st["state"] == "cancelled" and st["completed"] == ["Opening the project", "Reading git history"]
    assert _t.time() - t0 < 15                          # the 60 s sleep was killed
    with pytest.raises(ag.DigError):
        ag.cancel_dig("r", s)                           # nothing running now

    calls = []

    def runner(args, settings):
        calls.append(args[0])
        return {"ok": True}

    r = ag.start_dig(None, "r", s, resume=True, runner=runner)
    assert r["resumed"]
    st = _wait("r", s)
    assert st["state"] == "done" and calls == ["mine", "build-db", "signals"]
    with pytest.raises(ag.DigError):
        ag.start_dig(None, "r", s, resume=True)         # done: nothing to resume


def test_cancelled_state_transitions(tmp_path):
    pdir = tmp_path / "p"
    ag._set_status(pdir, fresh=True, state="running")
    ag._set_status(pdir, state="cancelled")
    with pytest.raises(ag.DigError):
        ag._set_status(pdir, state="done")
    ag._set_status(pdir, state="running")


# --------------------------------------------------------------- FIX ALL (data model)


def test_parse_git_reads_identity_parents_trailers_and_paths(tmp_path):
    repo = git_repo(tmp_path / "r")
    pdir = tmp_path / "p"
    (pdir / "data").mkdir(parents=True)
    ag.mine_git(repo, pdir, {"history": "head"}, None)
    cs = ag.parse_git((pdir / "data" / ag.GIT_FILE).read_text())
    assert len(cs) == 3 and all(c["email"] for c in cs)
    first = min(cs, key=lambda c: c["dt"])
    assert first["parents"] == [] and first["dt"].utcoffset().total_seconds() == -7 * 3600
    assert [p[0] for p in first["paths"]] == ["a.py"] and first["ins"] == 3
    meta = json.loads((pdir / "data" / ag.REPO_FILE).read_text())
    assert len(meta["head_sha"]) == 40 and meta["ref"] == "main"


def test_identities_one_person_many_spellings_and_kinds():
    from collections import Counter
    pairs = Counter({("Simon", "s@k.tech"): 5, ("simon", "s@k.tech"): 2, ("Simon Gonzalez De Cruz", "simon@pw.com"): 3,
                     ("SimonG", "123+SimonG@users.noreply.github.com"): 1, ("Simon Gonzalez De Cruz", "s@k.tech"): 1,
                     ("dependabot[bot]", "49699333+dependabot[bot]@users.noreply.github.com"): 4,
                     ("Claude Opus 4.7", "noreply@anthropic.com"): 2, ("Claude Fable 5", "noreply@anthropic.com"): 1,
                     ("Kyanite Factory", "factory@k.tech"): 2})
    idx, people = ag.build_identities(pairs, "Kyanite Factory")
    assert idx[("Simon", "s@k.tech")] == idx[("Simon Gonzalez De Cruz", "simon@pw.com")]
    who = lambda k: people[idx[k]]
    assert who(("simon", "s@k.tech"))["name"] == "Simon Gonzalez De Cruz" and who(("simon", "s@k.tech"))["kind"] == "human"
    assert who(("dependabot[bot]", "49699333+dependabot[bot]@users.noreply.github.com"))["kind"] == "bot"
    assert who(("Claude Opus 4.7", "noreply@anthropic.com"))["kind"] == "agent"
    assert who(("Claude Opus 4.7", "noreply@anthropic.com"))["name"] == "Claude"
    assert who(("Kyanite Factory", "factory@k.tech"))["kind"] == "bot"     # the bots setting


def test_fold_signals_onset_peak_end():
    raw = [{"date": f"2026-05-0{i}", "type": "velocity", "detail": "upshift x", "strength": s}
           for i, s in [(1, "weak"), (2, "strong"), (4, "weak")]]
    raw += [{"date": "2026-05-03", "type": "gap", "detail": "quiet"}, {"date": "2026-06-20", "type": "velocity",
            "detail": "upshift y"}]
    out = ag.fold_signals(raw, 7)
    assert [s["type"] for s in out] == ["velocity", "velocity"]
    assert out[0]["d"] == "2026-05-01" and out[0]["end"] == "2026-05-04" and out[0]["n"] == 3


def test_practices_word_bounded_and_roi_from_evidence():
    mk = lambda msg, paths=(): {"msg": msg, "kind": ag.kind_of(msg), "paths": [(p, 1, 0) for p in paths], "sha": "a" * 40}
    work = [mk("fix: specification parser")] * 10 + [mk("test: add cases", ["tests/t.py"])] * 2
    rows = {r["practice"]: r for r in ag.practices(work)}
    assert rows["Tests"]["n"] == 2 and rows["Tests"]["of"] == 12   # "specification" is not "ci"
    assert rows["CI/CD pipeline"]["n"] == 0
    assert len({r["roi"] for r in rows.values()}) > 1


def test_real_git_dig_is_deterministic_and_merges_are_not_work(tmp_path):
    repo = git_repo(tmp_path / "r")
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_AUTHOR_DATE": "2026-05-21T10:00:00+00:00", "GIT_COMMITTER_DATE": "2026-05-21T10:00:00+00:00"}
    g = lambda *a: subprocess.run(["git", "-C", str(repo), "-c", "user.name=Lin", "-c", "user.email=lin@x.io", *a],
                                  check=True, env=env, capture_output=True)
    g("checkout", "-q", "-b", "side"); (repo / "b.txt").write_text("b\n"); g("add", "-A"); g("commit", "-q", "-m", "feat: b")
    g("checkout", "-q", "main"); g("merge", "-q", "--no-ff", "-m", "Merge pull request #7 from x/side", "side")
    g("tag", "v1.0")
    s = {"history": "head", "time_zone": "UTC"}
    pdir = tmp_path / "p"
    (pdir / "data").mkdir(parents=True)
    ag.mine_git(repo, pdir, s, None)
    a = ag.summarize(pdir, project="r", settings=s)
    b = ag.summarize(pdir, project="r", settings=s)
    a.pop("generated_at"); b.pop("generated_at")
    assert a == b
    assert a["commit_count"] == 4 and a["merge_count"] == 1 and a["pr_count"] == 1
    assert sum(a["kind_totals"]) == a["commit_count"]
    assert [r["name"] for r in a["releases"]] == ["v1.0"]
    assert a["manifest"]["schema_version"] == ag.SCHEMA_VERSION and a["manifest"]["config_hash"]
    days = [c["day"] for c in a["commits"]]
    assert days == sorted(days, reverse=True)                     # one clock: no inversions
