import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("ag4te_under_test", PKG / "__init__.py")
ag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ag)

STATS = (
    "aaaa111\x1f2026-05-01 09:15:00 -0700\x1ffeat(ui): add strata ribbon\x1fAda\n\n"
    " 3 files changed, 120 insertions(+), 4 deletions(-)\n"
    "bbbb222\x1f2026-05-02 23:40:00 -0700\x1ffix: guard empty repo\x1fAda\n\n"
    " 1 file changed, 2 insertions(+)\n"
    "cccc333\x1f2026-05-20 10:00:00 +0200\x1fUpdate README\x1fLin\n\n"
    "dddd444\x1fnot a date\x1fbroken line\x1fX\n"
)


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
        (
            "2026-05-01T09:15:00-07:00",
            "feat(ui): add strata ribbon",
            "Ada",
            "ada@x.io",
            {"a.py": "1\n2\n3\n"},
        ),
        (
            "2026-05-02T23:40:00-07:00",
            "fix: guard empty repo",
            "Ada Lovelace",
            "ada@x.io",
            {"a.py": "1\n2\n"},
        ),
        ("2026-05-20T10:00:00+02:00", "Update README", "Lin", "lin@x.io", {"README.md": "hi\n"}),
    ]
    path.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True, env=env)
    for when, msg, name, email, files in commits:
        for f, text in files.items():
            (path / f).write_text(text)
        subprocess.run(["git", "-C", str(path), "add", "-A"], check=True, env=env)
        subprocess.run(
            [
                "git",
                "-C",
                str(path),
                "-c",
                f"user.name={name}",
                "-c",
                f"user.email={email}",
                "commit",
                "-q",
                "--allow-empty",
                "-m",
                msg,
            ],
            check=True,
            env={**env, "GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when},
        )
    return path


def test_kinds():
    assert ag.kind_of("feat(x)!: y") == "feat"
    assert ag.kind_of("chore: bump") == "ops"
    assert (
        ag.kind_of("Merge pull request #3") == "other"
    )  # merges are flagged by parents, not words
    assert ag.kind_of('Revert "feat: x"') == "fix"
    assert ag.kind_of("Fix the thing") == "fix"
    assert ag.kind_of("Update README") == "docs"
    assert ag.kind_of("wibble") == "other"
    assert ag.kind_of("") == "other"
    assert ag.kind_of("eval: fix mapeOf double scaling") == "fix"  # area prefix, not a type
    assert ag.kind_of("site: take GH_HEAD only from a fetch") == "other"


def test_summary_basic(tmp_path):
    d = ag.summarize(
        make_project(tmp_path), project="demo", settings={"time_zone": "America/Los_Angeles"}
    )
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


def test_default_devarch_config_hash_ignores_install_path(tmp_path, monkeypatch):
    pdir = make_project(tmp_path)
    first_constraints = tmp_path / "install-a" / "devarch-constraints.txt"
    second_constraints = tmp_path / "install-b" / "devarch-constraints.txt"
    first_constraints.parent.mkdir()
    second_constraints.parent.mkdir()
    first_constraints.write_text("package==1.2.3\n", encoding="utf-8")
    second_constraints.write_text("package==1.2.3\n", encoding="utf-8")
    settings = {"time_zone": "UTC"}

    monkeypatch.setattr(ag, "DEVARCH_CONSTRAINTS", first_constraints)
    monkeypatch.setitem(
        ag.DEFAULTS,
        "devarch_command",
        ag._default_devarch_command(str(first_constraints), windows=False),
    )
    first_hash = ag.summarize(pdir, settings=settings)["manifest"]["config_hash"]

    monkeypatch.setattr(ag, "DEVARCH_CONSTRAINTS", second_constraints)
    monkeypatch.setitem(
        ag.DEFAULTS,
        "devarch_command",
        ag._default_devarch_command(str(second_constraints), windows=False),
    )
    second_hash = ag.summarize(pdir, settings=settings)["manifest"]["config_hash"]

    assert first_hash == second_hash

    second_constraints.write_text("package==4.5.6\n", encoding="utf-8")
    changed_constraints_hash = ag.summarize(pdir, settings=settings)["manifest"]["config_hash"]
    assert changed_constraints_hash != first_hash


def test_custom_devarch_command_still_changes_config_hash(tmp_path):
    pdir = make_project(tmp_path)
    first = ag.summarize(pdir, settings={"time_zone": "UTC"})["manifest"]["config_hash"]
    second = ag.summarize(
        pdir, settings={"time_zone": "UTC", "devarch_command": "uvx --from custom devarch"}
    )["manifest"]["config_hash"]
    assert first != second


def test_summary_signals_and_bad_json(tmp_path):
    sig = {
        "signals": [
            {"date": "2026-05-02", "type": "velocity", "detail": "x" * 999, "strength": "strong"},
            {"date": "nope"},
            "junk",
        ],
        "cluster_summary": [
            {"start_date": "2026-05-01", "end_date": "2026-05-02", "commit_count": 2},
            {"start_date": "2026-05-09", "end_date": "2026-05-01"},
        ],
    }
    d = ag.summarize(make_project(tmp_path, signals=sig))
    assert len(d["signals"]) == 1 and len(d["signals"][0]["detail"]) == 240
    assert len(d["clusters"]) == 2  # eras come from the plugin's own gap rule, not cluster_summary
    (tmp_path / "projects" / "demo" / "data" / "detected-signals.json").write_text("{corrupt")
    assert ag.summarize(tmp_path / "projects" / "demo")["commit_count"] == 3


def test_empty(tmp_path):
    d = ag.summarize(make_project(tmp_path, stats=""))
    assert d["empty"] and d["days"] == []


@pytest.mark.parametrize("bad", ["", "A", "-x", "../x", "a/b", "a" * 64, None, 3, "é"])
def test_bad_project_names(bad):
    with pytest.raises(ag.DigError):
        ag.validate_project(bad)


def test_project_name_rejects_trailing_newline():
    with pytest.raises(ag.DigError):
        ag.validate_project("demo\n")


def test_resolve_repo(tmp_path):
    root = tmp_path / "ws"
    (root / "good" / ".git").mkdir(parents=True)
    (root / "plain").mkdir()
    outside = tmp_path / "outside"
    (outside / ".git").mkdir(parents=True)
    (root / "link").symlink_to(outside)
    s = {"repo_roots": str(root)}
    assert ag.resolve_repo(str(root / "good"), s) == (root / "good").resolve()
    for bad in [
        str(root / "plain"),
        str(outside),
        str(root / "link"),
        str(root / "good" / ".." / ".." / "outside"),
        str(root / "missing"),
        "",
        "a\x00b",
    ]:
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
        return {
            "ok": args[0] != "signals",
            "err": "Traceback\nboom" if args[0] == "signals" else "",
        }

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
    (root / "r" / ".git").mkdir(parents=True)  # looks like a repo, git can't read it
    s = {"repo_roots": str(root), "data_dir": str(tmp_path / "data")}
    calls = []
    st = ag.run_dig(
        ag.resolve_repo(str(root / "r"), s),
        "r",
        s,
        runner=lambda a, _: calls.append(a[0]) or {"ok": True},
    )
    assert st["state"] == "failed" and "Reading git history" in st["error"]
    assert calls == ["init"] and ag.load_dig("r", s) is None


def test_devarch_failure_is_optional(tmp_path):
    root = tmp_path / "ws"
    git_repo(root / "r")
    s = {"repo_roots": str(root), "data_dir": str(tmp_path / "data")}
    st = ag.run_dig(
        ag.resolve_repo(str(root / "r"), s),
        "r",
        s,
        runner=lambda a, _: {"ok": a[0] == "init", "err": "uvx: not found"},
    )
    assert st["state"] == "done" and len(st["warnings"]) == 3
    assert ag.load_dig("r", s)["commit_count"] == 3


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="plugin runs under the Hermes gateway on POSIX: shlex commands, process groups",
)
def test_run_devarch_scrubs_env(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret")
    s = {
        "devarch_command": f'{sys.executable} -c "import os,json;print(json.dumps(dict(os.environ)))"',
        "data_dir": str(tmp_path / "d"),
        "timeout_seconds": 30,
    }
    r = ag.run_devarch([], s)
    env = json.loads(r["out"])
    assert (
        r["ok"] and "OPENAI_API_KEY" not in env and env["DEVARCH_WORKSPACE"] == str(tmp_path / "d")
    )
    assert ag.run_devarch([], {**s, "devarch_command": "/no/such/bin"})["ok"] is False
    assert ag.run_devarch([], {**s, "devarch_command": "'unbalanced"})["ok"] is False


def test_slash_refuses_dig_on_gateway(monkeypatch):
    monkeypatch.setenv("HERMES_PLATFORM", "telegram")
    assert "off on chat platforms" in ag._slash("dig ~/x")
    assert ag._slash("") == ag.USAGE
    assert "names are" in ag._slash("show ../etc")


# A real DevArch project; defaults to the demo shipped in the repo so CI always runs it.
SAMPLE = os.environ.get("AG4TE_SAMPLE") or str(
    Path(__file__).resolve().parents[3] / "projects" / "demo-archaeology"
)


def test_real_sample():
    d = ag.summarize(Path(SAMPLE))
    assert d["commit_count"] > 0 and len(d["days"]) == d["span_days"]
    assert sum(x["n"] for x in d["days"]) <= d["commit_count"]
    json.dumps(d)


def test_author_aliases_merge_one_person():
    from collections import Counter

    a = ag.author_aliases(
        Counter(
            {
                "Robin": 5,
                "robin": 2,
                "Robin Alvarez De Luna": 3,
                "Ana": 1,
                "Ana Ruiz": 1,
                "Ana Lopez": 1,
                "dependabot[bot]": 4,
            }
        )
    )
    assert a["Robin"] == a["robin"] == a["Robin Alvarez De Luna"] == "Robin Alvarez De Luna"
    assert a["Ana"] == "Ana"  # two candidates: don't guess
    assert a["dependabot[bot]"] == "dependabot[bot]"


def test_dig_state_machine_transitions(tmp_path):
    pdir = tmp_path / "p"
    with pytest.raises(ag.DigError):
        ag._set_status(pdir, state="done")  # none -> done skips running
    ag._set_status(pdir, fresh=True, state="running", step=0, finished_at=123.0)
    ag._set_status(pdir, state="done", step=7)
    with pytest.raises(ag.DigError):
        ag._set_status(pdir, state="failed")  # a late writer cannot flip a terminal state
    st = ag._set_status(pdir, fresh=True, state="running", step=0)
    assert "finished_at" not in st and st["step"] == 0  # a re-dig starts a clean record
    ag._set_status(pdir, state="failed", error="x")
    ag._set_status(pdir, state="running")  # failed -> running (retry)


def test_redig_after_done_and_interrupted(tmp_path):
    root = tmp_path / "ws"
    git_repo(root / "r")
    s = {"repo_roots": str(root), "data_dir": str(tmp_path / "data")}
    repo = ag.resolve_repo(str(root / "r"), s)

    def runner(args, settings):
        return {"ok": True}

    assert ag.run_dig(repo, "r", s, runner=runner)["state"] == "done"
    assert ag.run_dig(repo, "r", s, runner=runner)["state"] == "done"  # done -> running -> done
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


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="plugin runs under the Hermes gateway on POSIX: shlex commands, process groups",
)
def test_cancel_kills_running_command_then_resume_skips_done_steps(tmp_path):
    import sys
    import time as _t

    root = tmp_path / "ws"
    git_repo(root / "r")
    s = {
        "repo_roots": str(root),
        "data_dir": str(tmp_path / "data"),
        "devarch_command": f"{sys.executable} -c 'import sys,time; time.sleep(0 if sys.argv[1]==\"init\" else 60)'",
    }
    t0 = _t.time()
    ag.start_dig(str(root / "r"), "r", s)
    for _ in range(200):  # wait until it is inside "Mining commits"
        if ag.read_status("r", s).get("label") == "Mining commits":
            break
        _t.sleep(0.05)
    with pytest.raises(ag.DigError):
        ag.start_dig(str(root / "r"), "r", s)  # one at a time
    assert ag.cancel_dig("r", s)["cancelling"]
    st = _wait("r", s)
    assert st["state"] == "cancelled" and st["completed"] == [
        "Opening the project",
        "Reading git history",
    ]
    assert _t.time() - t0 < 15  # the 60 s sleep was killed
    with pytest.raises(ag.DigError):
        ag.cancel_dig("r", s)  # nothing running now

    calls = []

    def runner(args, settings):
        calls.append(args[0])
        return {"ok": True}

    r = ag.start_dig(None, "r", s, resume=True, runner=runner)
    assert r["resumed"]
    st = _wait("r", s)
    assert st["state"] == "done" and calls == ["mine", "build-db", "signals"]
    with pytest.raises(ag.DigError):
        ag.start_dig(None, "r", s, resume=True)  # done: nothing to resume


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

    pairs = Counter(
        {
            ("Robin", "r@k.example"): 5,
            ("robin", "r@k.example"): 2,
            ("Robin Alvarez De Luna", "robin@pw.example"): 3,
            ("RobinA", "123+RobinA@users.noreply.github.com"): 1,
            ("Robin Alvarez De Luna", "r@k.example"): 1,
            ("dependabot[bot]", "49699333+dependabot[bot]@users.noreply.github.com"): 4,
            ("Claude Opus 4.7", "noreply@anthropic.com"): 2,
            ("Claude Fable 5", "noreply@anthropic.com"): 1,
            ("Kyanite Factory", "factory@k.example"): 2,
        }
    )
    idx, people = ag.build_identities(pairs, "Kyanite Factory")
    assert idx[("Robin", "r@k.example")] == idx[("Robin Alvarez De Luna", "robin@pw.example")]

    def who(k):
        return people[idx[k]]

    assert (
        who(("robin", "r@k.example"))["name"] == "Robin Alvarez De Luna"
        and who(("robin", "r@k.example"))["kind"] == "human"
    )
    assert (
        who(("dependabot[bot]", "49699333+dependabot[bot]@users.noreply.github.com"))["kind"]
        == "bot"
    )
    assert who(("Claude Opus 4.7", "noreply@anthropic.com"))["kind"] == "agent"
    assert who(("Claude Opus 4.7", "noreply@anthropic.com"))["name"] == "Claude"
    assert who(("Kyanite Factory", "factory@k.example"))["kind"] == "bot"  # the bots setting


def test_fold_signals_onset_peak_end():
    raw = [
        {"date": f"2026-05-0{i}", "type": "velocity", "detail": "upshift x", "strength": s}
        for i, s in [(1, "weak"), (2, "strong"), (4, "weak")]
    ]
    raw += [
        {"date": "2026-05-03", "type": "gap", "detail": "quiet"},
        {"date": "2026-06-20", "type": "velocity", "detail": "upshift y"},
    ]
    out = ag.fold_signals(raw, 7)
    assert [s["type"] for s in out] == ["velocity", "velocity"]
    assert out[0]["d"] == "2026-05-01" and out[0]["end"] == "2026-05-04" and out[0]["n"] == 3


def test_practices_word_bounded_and_roi_from_evidence():
    def mk(msg, paths=()):
        return {
            "msg": msg,
            "kind": ag.kind_of(msg),
            "paths": [(p, 1, 0) for p in paths],
            "sha": "a" * 40,
        }

    work = [mk("fix: specification parser")] * 10 + [mk("test: add cases", ["tests/t.py"])] * 2
    rows = {r["practice"]: r for r in ag.practices(work)}
    assert rows["Tests"]["n"] == 2 and rows["Tests"]["of"] == 12  # "specification" is not "ci"
    assert rows["CI/CD pipeline"]["n"] == 0
    assert len({r["roi"] for r in rows.values()}) > 1


def test_real_git_dig_is_deterministic_and_merges_are_not_work(tmp_path):
    repo = git_repo(tmp_path / "r")
    env = {
        **os.environ,
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_DATE": "2026-05-21T10:00:00+00:00",
        "GIT_COMMITTER_DATE": "2026-05-21T10:00:00+00:00",
    }

    def g(*a):
        return subprocess.run(
            ["git", "-C", str(repo), "-c", "user.name=Lin", "-c", "user.email=lin@x.io", *a],
            check=True,
            env=env,
            capture_output=True,
        )

    g("checkout", "-q", "-b", "side")
    (repo / "b.txt").write_text("b\n")
    g("add", "-A")
    g("commit", "-q", "-m", "feat: b")
    g("checkout", "-q", "main")
    g("merge", "-q", "--no-ff", "-m", "Merge pull request #7 from x/side", "side")
    g("tag", "v1.0")
    s = {"history": "head", "time_zone": "UTC"}
    pdir = tmp_path / "p"
    (pdir / "data").mkdir(parents=True)
    ag.mine_git(repo, pdir, s, None)
    a = ag.summarize(pdir, project="r", settings=s)
    b = ag.summarize(pdir, project="r", settings=s)
    a.pop("generated_at")
    b.pop("generated_at")
    assert a == b
    assert a["commit_count"] == 4 and a["merge_count"] == 1 and a["pr_count"] == 1
    assert sum(a["kind_totals"]) == a["commit_count"]
    assert [r["name"] for r in a["releases"]] == ["v1.0"]
    assert a["manifest"]["schema_version"] == ag.SCHEMA_VERSION and a["manifest"]["config_hash"]
    days = [c["day"] for c in a["commits"]]
    assert days == sorted(days, reverse=True)  # one clock: no inversions


def test_api_loads_the_plugin_once(monkeypatch):
    """Each API call must reach the same plugin module, or the running-dig registry is lost."""
    pytest.importorskip("fastapi")
    for name in ("ag4te", "hermes_plugins.ag4te", "plugins.ag4te", "_ag4te_private"):
        monkeypatch.delitem(sys.modules, name, raising=False)
    api_spec = importlib.util.spec_from_file_location(
        "ag4te_api_under_test", PKG / "dashboard" / "plugin_api.py"
    )
    api = importlib.util.module_from_spec(api_spec)
    api_spec.loader.exec_module(api)
    first = api._plugin()
    first._jobs["probe"] = "kept"
    try:
        assert api._plugin() is first
        assert first._jobs.get("probe") == "kept"
    finally:
        first._jobs.pop("probe", None)
        sys.modules.pop("_ag4te_private", None)


def test_reloaded_plugin_keeps_running_digs(tmp_path):
    """A plugin reload (fresh import) must still see a dig the old copy started."""
    import threading

    fresh_spec = importlib.util.spec_from_file_location("ag4te_reloaded", PKG / "__init__.py")
    fresh = importlib.util.module_from_spec(fresh_spec)
    fresh_spec.loader.exec_module(fresh)
    assert fresh._jobs is ag._jobs and fresh._jobs_lock is ag._jobs_lock
    gate = threading.Event()
    t = threading.Thread(target=gate.wait, name="ag4te-dig-probe", daemon=True)
    repo = tmp_path / "repos" / "r"
    git_repo(repo)  # a catalog install has no .git of its own
    settings = {
        **ag.snapshot_settings(),
        "data_dir": str(tmp_path / "data"),
        "repo_roots": str(tmp_path / "repos"),
    }
    ag._set_status(ag.project_dir("probe", settings), fresh=True, state="running", step=1)
    with ag._jobs_lock:
        ag._jobs["probe"], ag._cancels["probe"] = t, threading.Event()
    t.start()
    try:
        assert fresh.read_status("probe", settings)["state"] == "running"
        with pytest.raises(fresh.DigBusyError, match="already running"):
            fresh.start_dig(str(repo), "other", settings)
        assert fresh.cancel_dig("probe", settings)["cancelling"] is True
    finally:
        gate.set()
        t.join(2)
        with ag._jobs_lock:
            ag._jobs.pop("probe", None)
            ag._cancels.pop("probe", None)


def test_host_zone_is_named_not_a_fixed_offset(monkeypatch):
    """With no time_zone and no TZ, summer commits must use summer time."""
    monkeypatch.delenv("TZ", raising=False)
    monkeypatch.setattr(ag, "_host_zone_name", lambda: "America/Los_Angeles")
    zone, name = ag.project_zone({**ag.snapshot_settings(), "time_zone": ""})
    assert name == "America/Los_Angeles"
    from datetime import datetime, timezone

    summer = datetime(2026, 7, 1, 7, 30, tzinfo=timezone.utc).astimezone(zone)
    assert (summer.day, summer.hour) == (1, 0)


def test_cancel_with_bad_name_is_400(monkeypatch):
    fastapi = pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    api_spec = importlib.util.spec_from_file_location(
        "ag4te_api_cancel", PKG / "dashboard" / "plugin_api.py"
    )
    api = importlib.util.module_from_spec(api_spec)
    api_spec.loader.exec_module(api)
    app = fastapi.FastAPI()
    app.include_router(api.router)
    c = TestClient(app)
    assert c.post("/cancel", json={"project": "../etc"}).status_code == 400
    assert c.post("/cancel", json={"project": "nothing-running"}).status_code == 409
    sys.modules.pop("_ag4te_private", None)


def test_name_particles_fold_into_one_person():
    from collections import Counter

    ident, people = ag.build_identities(
        Counter(
            {
                ("Robin Alvarez De Luna", "a@x.dev"): 20,
                ("Robin Alvarez de la Luna", "b@y.dev"): 21,
                ("Ana de la Rosa", "c@z.dev"): 3,
            }
        )
    )
    humans = [p for p in people if p.get("kind", "human") == "human"]
    assert len(humans) == 2
    assert (
        ident[("Robin Alvarez De Luna", "a@x.dev")]
        == ident[("Robin Alvarez de la Luna", "b@y.dev")]
    )


def test_parse_git_accepts_utc_z_suffix():
    # git >= 2.5x prints UTC author dates as "...Z"; Python 3.10's fromisoformat rejects it
    rec = "\x1f".join(
        [
            "a" * 40,
            "",
            "2026-05-21T10:00:00Z",
            "2026-05-21T10:00:00Z",
            "Lin",
            "lin@x.io",
            "Lin",
            "lin@x.io",
            "feat: b",
            "",
        ]
    )
    assert len(ag.parse_git(rec + "\n\x1e")) == 1


def test_story_tells_the_dig_in_order_and_links_eras(tmp_path):
    repo = git_repo(tmp_path / "r")
    s = {"history": "head", "time_zone": "UTC"}
    pdir = tmp_path / "p"
    (pdir / "data").mkdir(parents=True)
    ag.mine_git(repo, pdir, s, None)
    d = ag.summarize(pdir, project="r", settings=s)
    ids = [c["id"] for c in d["story"]]
    assert ids[0] == "origin" and ids[-1] == "now"
    assert "shape" in ids and "people" in ids and "work" in ids
    assert "feat(ui): add strata ribbon" in d["story"][0]["text"]  # the real first commit
    for c in d["story"]:
        assert c["title"] and c["text"]
        assert c["era"] is None or 0 <= c["era"] < len(d["clusters"])
    assert ag.story(d) == d["story"]  # pure: same dig, same words


def test_story_empty_truncated_and_backfilled(tmp_path, monkeypatch):
    assert ag.story({}) == [] and ag.story({"empty": True}) == []
    d = {
        "commit_count": 3,
        "first": "2026-05-01",
        "last": "2026-05-20",
        "span_days": 20,
        "active_days": 3,
        "kinds": list(ag.KINDS),
        "kind_totals": [1, 1, 0, 1, 0, 0, 0],
        "commits_truncated": True,
        "commits": [{"kind": "docs", "msg": "late", "author": "Lin"}],
        "clusters": [],
        "generated_at": "not a date",
    }
    origin = ag.story(d)[0]
    assert origin["text"] == "The history read here starts on 2026-05-01."  # no false first commit
    assert not any(c["id"] == "now" for c in ag.story(d))  # no eras, no "now" chapter
    # a dig saved before the lens gets its story on load
    monkeypatch.setattr(ag, "project_dir", lambda project, settings=None: tmp_path)
    (tmp_path / ag.DIG_FILE).write_text(json.dumps(d), encoding="utf-8")
    assert ag.load_dig("demo")["story"] == ag.story(d)


def test_gateway_gate_fails_closed(monkeypatch):
    for var in ("HERMES_PLATFORM", "HERMES_SESSION_PLATFORM", "HERMES_GATEWAY_SESSION"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(ag, "_ctx", None)
    assert ag._on_gateway() is False  # older Hermes classic CLI: nothing set
    monkeypatch.setenv("HERMES_GATEWAY_SESSION", "1")
    assert ag._on_gateway() is True  # blank platform inside a gateway process
    monkeypatch.delenv("HERMES_GATEWAY_SESSION")

    class Ctx:
        surface = ""

        def session_surface(self):
            return self.surface

        def get_config(self, key, default=None):
            return default

    ctx = Ctx()
    monkeypatch.setattr(ag, "_ctx", ctx)
    assert ag._on_gateway() is True  # newer Hermes: blank means no local session
    for plat, chat in (("cli", False), ("desktop", False), ("discord", True), ("weird", True)):
        ctx.surface = plat
        assert ag._on_gateway() is chat, plat


def test_gateway_gets_summaries_and_cannot_stop(tmp_path, monkeypatch):
    s = {"data_dir": str(tmp_path / "data")}
    pdir = ag.project_dir("demo", s)
    ag._set_status(pdir, fresh=True, state="running", step=1, steps=6, repo="/home/someone/demo")
    ag._set_status(pdir, state="failed", error="Mining commits: /home/someone/demo: boom")
    monkeypatch.setattr(ag, "snapshot_settings", lambda: s)
    monkeypatch.setattr(ag, "_cfg", lambda k, settings=None: s.get(k, ag.DEFAULTS[k]))
    monkeypatch.setenv("HERMES_PLATFORM", "telegram")
    assert "off on chat platforms" in ag._slash("stop demo")
    status = ag._slash("status demo")
    assert "someone" not in status and json.loads(status)["state"] == "failed"
    assert ag._slash("list") == "1 dig: 1 failed"
    assert "someone" not in ag._tool({})
    monkeypatch.setenv("HERMES_PLATFORM", "cli")
    assert "boom" in ag._slash("status demo")
    assert ag._slash("list").startswith("demo: failed")


def test_same_folder_name_in_two_roots_gets_two_projects(tmp_path):
    a, b = tmp_path / "alpha" / "same", tmp_path / "beta" / "same"
    git_repo(a)
    git_repo(b)
    s = {"repo_roots": str(tmp_path), "data_dir": str(tmp_path / "data")}
    first = ag.start_dig(str(a), None, s, runner=lambda *a, **k: {"ok": True})
    ag._jobs[first["project"]].join(10)
    second = ag.start_dig(str(b), None, s, runner=lambda *a, **k: {"ok": True})
    ag._jobs[second["project"]].join(10)
    assert first["project"] == "same"
    assert second["project"].startswith("same-") and second["project"] != "same"
    assert ag.project_repo("same", s) == str(a.resolve())
    with pytest.raises(ag.DigError, match="another repository"):
        ag.start_dig(str(b), "same", s, runner=lambda *a, **k: {"ok": True})


def test_lease_blocks_a_dig_from_another_process(tmp_path):
    root = tmp_path / "repos"
    git_repo(root / "r")
    s = {"repo_roots": str(root), "data_dir": str(tmp_path / "data")}
    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        lease = ag._lease_path(s)
        lease.parent.mkdir(parents=True, exist_ok=True)
        lease.write_text(
            json.dumps(
                {
                    "project": "elsewhere",
                    "pid": other.pid,
                    "host": ag._host(),
                    "boot_id": ag._boot_id(),
                    "since": time.time(),
                }
            )
        )
        ag._set_status(ag.project_dir("elsewhere", s), fresh=True, state="running")
        with pytest.raises(ag.DigError, match="another Hermes process"):
            ag.start_dig(str(root / "r"), None, s, runner=lambda *a, **k: {"ok": True})
        assert ag.read_status("elsewhere", s)["state"] == "running"  # not "interrupted"
        with pytest.raises(ag.DigError, match="another Hermes process"):
            ag.cancel_dig("elsewhere", s)
    finally:
        other.kill()
        other.wait()
    # its owner died: the stale lease no longer blocks, and the dig drops it when done
    r = ag.start_dig(str(root / "r"), None, s, runner=lambda *a, **k: {"ok": True})
    ag._jobs[r["project"]].join(10)
    assert not ag._lease_path(s).exists()
    assert ag.read_status("elsewhere", s)["interrupted"] is True


def test_foreign_host_lease_expires_after_max_age(tmp_path):
    settings = {"repo_roots": str(tmp_path), "data_dir": str(tmp_path / "data")}
    lease = ag._lease_path(settings)
    lease.parent.mkdir(parents=True)
    lease.write_text(
        json.dumps(
            {
                "project": "orphaned",
                "pid": 12345,
                "host": "previous-host",
                "since": 0,
            }
        ),
        encoding="utf-8",
    )

    assert ag.read_lease(settings) is None
    ag._take_lease("new-dig", settings)
    assert json.loads(lease.read_text(encoding="utf-8"))["project"] == "new-dig"

    lease.write_text(
        json.dumps(
            {
                "project": "active-remote",
                "pid": 12345,
                "host": "previous-host",
                "since": time.time(),
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ag.DigError, match="another Hermes process"):
        ag._take_lease("competing-dig", settings)


def test_stale_lease_reclaim_does_not_remove_a_replacement(tmp_path):
    settings = {"repo_roots": str(tmp_path), "data_dir": str(tmp_path / "data")}
    lease = ag._lease_path(settings)
    lease.parent.mkdir(parents=True)
    lease.write_text(
        json.dumps({"project": "stale", "host": ag._host(), "pid": -1}), encoding="utf-8"
    )

    b_observed = tmp_path / "b-observed"
    a_installed = tmp_path / "a-installed"
    b_result = tmp_path / "b-result"
    a_result = tmp_path / "a-result"
    common = [str(PKG), str(tmp_path), str(tmp_path / "data")]
    b_script = """
import importlib.util, sys, time
from pathlib import Path
pkg, root, data, observed, installed, result, other = sys.argv[1:]
spec = importlib.util.spec_from_file_location('ag4te_child', Path(pkg) / '__init__.py')
ag = importlib.util.module_from_spec(spec); spec.loader.exec_module(ag)
original = ag.read_lease
def read_lease(settings=None, *, _locked=False):
    held = original(settings, _locked=_locked)
    if held is None:
        Path(observed).touch()
        deadline = time.monotonic() + 2
        while not Path(installed).exists() and time.monotonic() < deadline:
            time.sleep(0.005)
    return held
ag.read_lease = read_lease
try:
    ag._take_lease('process-b', {'repo_roots': root, 'data_dir': data})
    outcome = 'claimed'
except ag.DigError:
    outcome = 'rejected'
Path(result).write_text(outcome)
# Stay alive until A has decided: a lease whose owner has exited is stale, and Windows
# (unlike an unreaped zombie on POSIX) reports the exited owner as gone at once.
deadline = time.monotonic() + 10
while not Path(other).exists() and time.monotonic() < deadline:
    time.sleep(0.005)
"""
    a_script = """
import importlib.util, sys
from pathlib import Path
pkg, root, data, installed, result = sys.argv[1:]
spec = importlib.util.spec_from_file_location('ag4te_child', Path(pkg) / '__init__.py')
ag = importlib.util.module_from_spec(spec); spec.loader.exec_module(ag)
original = ag.os.link
def link(source, target, *args, **kwargs):
    original(source, target, *args, **kwargs)
    Path(installed).touch()
ag.os.link = link
try:
    ag._take_lease('process-a', {'repo_roots': root, 'data_dir': data})
    outcome = 'claimed'
except ag.DigError:
    outcome = 'rejected'
Path(result).write_text(outcome)
"""
    b = subprocess.Popen(
        [
            sys.executable,
            "-c",
            b_script,
            *common,
            str(b_observed),
            str(a_installed),
            str(b_result),
            str(a_result),
        ]
    )
    deadline = time.monotonic() + 2
    while not b_observed.exists() and time.monotonic() < deadline:
        time.sleep(0.005)
    assert b_observed.exists()
    a = subprocess.Popen([sys.executable, "-c", a_script, *common, str(a_installed), str(a_result)])
    assert b.wait(timeout=5) == 0
    assert a.wait(timeout=5) == 0

    assert sorted((a_result.read_text(), b_result.read_text())) == ["claimed", "rejected"]


def test_pid_probe_never_signals_on_windows(monkeypatch):
    """os.kill(pid, 0) sends CTRL_C_EVENT to the console group on Windows."""

    def boom(*a):
        raise AssertionError("os.kill must not be called on Windows")

    monkeypatch.setattr(ag.os, "name", "nt")
    monkeypatch.setattr(ag.os, "kill", boom)
    monkeypatch.setattr(ag, "_win_pid_alive", lambda pid: pid == 4242)
    assert ag._pid_alive(4242) is True
    assert ag._pid_alive("4243") is False
    assert ag._pid_alive(None) is False and ag._pid_alive(0) is False


def test_pid_probe_on_posix():
    if os.name == "nt":
        pytest.skip("posix branch")
    assert ag._pid_alive(os.getpid()) is True
    done = subprocess.Popen([sys.executable, "-c", "pass"])
    done.wait()
    assert ag._pid_alive(done.pid) is False
