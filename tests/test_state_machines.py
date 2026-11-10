"""Tests for the explicit state machines.

Each machine gets: its state table checked exhaustively over its enum, every
legal transition, every illegal transition refused, legacy values still read,
and (where it has transitions) a Hypothesis stateful test.
"""

from __future__ import annotations

import importlib.util
import itertools
import os
import subprocess
import time
from pathlib import Path

import pytest
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule

from archaeology import pipeline
from archaeology.analysis_runner import (
    VectorOutcome,
    classify_vector_outcome,
    failed_vectors,
    vector_error,
)
from archaeology.db.pipeline_ingest import (
    RUN_STATUS_TO_HEALTH,
    RunHealth,
    normalize_run_status,
)
from archaeology.mcp_server import tools as mcp_tools
from archaeology.pipeline import (
    FAILED_AT,
    RUN_TRANSITIONS,
    BuildResult,
    MineResult,
    PipelineRun,
    RunStage,
)
from archaeology.state_machine import IllegalTransition, require_transition

ROOT = Path(__file__).resolve().parent.parent


def _load_scout_hook():
    path = ROOT / "scripts" / "integrations" / "scout_hook.py"
    spec = importlib.util.spec_from_file_location("scout_hook_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scout = _load_scout_hook()

MINED = MineResult(3, "c.csv", "s.txt")
BUILT_OK = BuildResult(Path("a.db"), True)
BUILT_ERR = BuildResult(Path("a.db"), False, 0, "boom")

# ── shared helper ────────────────────────────────────────────────────────────


def test_require_transition_returns_target_or_raises():
    assert require_transition("t", RUN_TRANSITIONS, RunStage.INITIALIZED, RunStage.MINED) is (
        RunStage.MINED
    )
    with pytest.raises(IllegalTransition, match="complete -> mined"):
        require_transition("t", RUN_TRANSITIONS, RunStage.COMPLETE, RunStage.MINED)


# ── PipelineRun (archaeology.pipeline) ───────────────────────────────────────

TERMINAL_STAGES = {RunStage.COMPLETE, RunStage.MINE_FAILED, RunStage.BUILD_FAILED}


def test_run_transition_table_covers_every_stage():
    assert set(RUN_TRANSITIONS) == set(RunStage)
    for targets in RUN_TRANSITIONS.values():
        assert targets <= set(RunStage)
    assert {s for s, t in RUN_TRANSITIONS.items() if not t} == TERMINAL_STAGES


def test_failed_at_is_derived_for_every_stage():
    expected = {
        RunStage.INITIALIZED: None,
        RunStage.MINED: None,
        RunStage.BUILT: None,
        RunStage.COMPLETE: None,
        RunStage.MINE_FAILED: "mine",
        RunStage.BUILD_FAILED: "build_db",
    }
    assert set(expected) == set(RunStage)
    for stage, failed_at in expected.items():
        assert PipelineRun(True, stage=stage).failed_at == failed_at
    assert set(FAILED_AT) == {s for s, v in expected.items() if v}


# One call per transition method, and the stage it moves to.
RUN_MOVES = {
    "mined": (lambda r: r.mined(MINED), RunStage.MINED),
    "mine_failed": (lambda r: r.mine_failed("nope"), RunStage.MINE_FAILED),
    "built": (lambda r: r.built(BUILT_OK), RunStage.BUILT),
    "build_failed": (lambda r: r.built(BUILT_ERR), RunStage.BUILD_FAILED),
    "finished": (lambda r: r.finished(2, ["v"]), RunStage.COMPLETE),
}


@pytest.mark.parametrize(
    "start,move", list(itertools.product(list(RunStage), sorted(RUN_MOVES))), ids=str
)
def test_every_run_move_from_every_stage(start, move):
    call, target = RUN_MOVES[move]
    run = PipelineRun(True, stage=start)
    if target in RUN_TRANSITIONS[start]:
        call(run)
        assert run.stage is target
    else:
        with pytest.raises(IllegalTransition):
            call(run)
        assert run.stage is start


def test_every_legal_run_edge_has_a_move():
    edges = {(s, t) for s, ts in RUN_TRANSITIONS.items() for t in ts}
    reachable = set()
    for start in RunStage:
        for call, target in RUN_MOVES.values():
            if target in RUN_TRANSITIONS[start]:
                reachable.add((start, target))
    assert reachable == edges


def test_run_moves_write_their_fields():
    run = PipelineRun(True)
    run.mined(MINED)
    run.built(BUILT_OK)
    run.finished(4, ["sdlc-gap-finder"])
    assert (run.mine, run.build, run.signal_count, run.analysis) == (
        MINED,
        BUILT_OK,
        4,
        ["sdlc-gap-finder"],
    )
    failed = PipelineRun(False)
    failed.mine_failed("Not a git repository: x")
    assert failed.mine_error == "Not a git repository: x" and failed.mine is None


class PipelineRunMachine(RuleBasedStateMachine):
    """Random move sequences: illegal ones are refused and nothing changes."""

    def __init__(self):
        super().__init__()
        self.run = PipelineRun(True)
        self.model = RunStage.INITIALIZED

    @rule(move=st.sampled_from(sorted(RUN_MOVES)))
    def apply(self, move):
        call, target = RUN_MOVES[move]
        if target in RUN_TRANSITIONS[self.model]:
            call(self.run)
            self.model = target
        else:
            with pytest.raises(IllegalTransition):
                call(self.run)

    @invariant()
    def stage_matches_model(self):
        assert self.run.stage is self.model

    @invariant()
    def fields_match_stage(self):
        r = self.run
        assert (r.mine is not None) == (
            r.stage in {RunStage.MINED, RunStage.BUILT, RunStage.BUILD_FAILED, RunStage.COMPLETE}
        )
        assert (r.mine_error is not None) == (r.stage is RunStage.MINE_FAILED)
        assert (r.build is not None) == (
            r.stage in {RunStage.BUILT, RunStage.BUILD_FAILED, RunStage.COMPLETE}
        )
        if r.build is not None:
            assert (r.build.error is not None) == (r.stage is RunStage.BUILD_FAILED)
        assert r.failed_at == FAILED_AT.get(r.stage)


TestPipelineRunMachine = PipelineRunMachine.TestCase
TestPipelineRunMachine.settings = settings(max_examples=60, stateful_step_count=12, deadline=None)


@pytest.mark.parametrize(
    "stage", [RunStage.COMPLETE, RunStage.MINE_FAILED, RunStage.BUILD_FAILED], ids=str
)
def test_mcp_run_pipeline_shape_per_terminal_stage(monkeypatch, stage):
    run = PipelineRun(True)
    if stage is RunStage.MINE_FAILED:
        run.mine_failed("Not a git repository: r")
    else:
        run.mined(MINED)
        run.built(BUILT_ERR if stage is RunStage.BUILD_FAILED else BUILT_OK)
        if stage is RunStage.COMPLETE:
            run.finished(5, ["sdlc-gap-finder"])
    monkeypatch.setattr(pipeline, "run_pipeline", lambda repo, ref: run)
    monkeypatch.setattr(mcp_tools, "_ref", lambda name: None)
    out = mcp_tools.devarch_run_pipeline("r", "p")
    if stage is RunStage.MINE_FAILED:
        assert out == {
            "init": "created",
            "mine": {"error": "Not a git repository: r"},
            "status": "failed",
            "failed_at": "mine",
        }
    elif stage is RunStage.BUILD_FAILED:
        assert list(out) == ["init", "mine", "commits_extracted", "build_db", "status", "failed_at"]
        assert (out["build_db"], out["status"], out["failed_at"]) == (
            "failed",
            "failed",
            "build_db",
        )
    else:
        assert list(out) == [
            "init",
            "mine",
            "commits_extracted",
            "build_db",
            "signals",
            "analysis",
            "status",
            "project",
        ]
        assert (out["build_db"], out["status"], out["signals"]) == ("complete", "complete", 5)


# ── Analysis vector outcome (archaeology.analysis_runner) ────────────────────


def test_vector_outcome_reads_every_state():
    samples = {
        VectorOutcome.WRITTEN: "projects/p/deliverables/analysis/analysis-x.json",
        VectorOutcome.FAILED: vector_error(ValueError("bad")),
    }
    assert set(samples) == set(VectorOutcome)
    for outcome, value in samples.items():
        assert classify_vector_outcome(value) is outcome


def test_vector_error_keeps_legacy_value_format():
    assert vector_error("disk full") == "ERROR: disk full"
    # Values already produced by older runs are still read as failures.
    assert classify_vector_outcome("ERROR: Analysis inputs changed") is VectorOutcome.FAILED
    assert classify_vector_outcome(Path("out/analysis-a.json")) is VectorOutcome.WRITTEN


def test_failed_vectors_selects_only_failures():
    results = {"a": "out/analysis-a.json", "b": "ERROR: x", "c": "ERROR: y"}
    assert failed_vectors(results) == {"b": "ERROR: x", "c": "ERROR: y"}
    assert failed_vectors({}) == {}


# ── Pipeline run health (archaeology.db.pipeline_ingest) ─────────────────────


def test_every_run_health_is_produced():
    produced = set(RUN_STATUS_TO_HEALTH.values()) | {RunHealth(normalize_run_status(None))}
    assert produced == set(RunHealth)


@pytest.mark.parametrize(
    "raw,stored",
    [
        ("COMPLETE", "pass"),
        ("success", "pass"),
        ("NEEDS_ATTENTION", "partial"),
        ("Running", "partial"),
        ("FAILED", "fail"),
        ("error", "fail"),
        (None, "unknown"),
        ("", "unknown"),
        (7, "unknown"),
        # Legacy and unrecognised values pass through lower-cased.
        ("pass", "pass"),
        ("partial", "partial"),
        ("Cancelled", "cancelled"),
    ],
)
def test_normalize_run_status_table(raw, stored):
    assert normalize_run_status(raw) == stored


# ── Scout hook run (scripts/integrations/scout_hook.py) ──────────────────────


def _ran(result, *steps_ok):
    for step, ok in zip(scout.STEP_ORDER, steps_ok):
        scout.record_step(result, step, ok, f"{step} msg")
    return result


def test_scout_run_table_covers_every_status():
    assert set(scout.RUN_TRANSITIONS) == set(scout.RunStatus)
    assert set(scout.EXIT_CODES) == set(scout.RunStatus)
    assert scout.EXIT_CODES[scout.RunStatus.COMPLETE] == 0
    assert all(c == 1 for s, c in scout.EXIT_CODES.items() if s is not scout.RunStatus.COMPLETE)


def test_scout_step_statuses_are_all_reachable():
    seen = set()
    for step in scout.STEP_ORDER:
        for ok in (True, False):
            result = _ran(scout.new_run("p", "r", None), *[True] * scout.STEP_ORDER.index(step))
            seen.add(scout.record_step(result, step, ok, "m"))
    assert seen == set(scout.StepStatus)


def test_scout_critical_failure_fails_run_with_error():
    result = _ran(scout.new_run("p", "r", None), True, False)
    assert result["status"] == "failed" and result["error"] == "mine msg"
    assert result["steps"]["mine"] == {"status": "failed", "message": "mine msg"}
    with pytest.raises(scout.IllegalTransition):
        scout.record_step(result, "build_db", True, "m")
    with pytest.raises(scout.IllegalTransition):
        scout.finish_run(result)


def test_scout_soft_failure_is_partial_and_run_completes():
    result = _ran(scout.new_run("p", "r", None), True, True, True, False, False)
    scout.finish_run(result)
    assert result["status"] == "complete"
    assert [result["steps"][s]["status"] for s in scout.STEP_ORDER] == [
        "success",
        "success",
        "success",
        "partial",
        "partial",
    ]
    assert scout.exit_code(result) == 0


def test_scout_refuses_out_of_order_repeat_and_early_finish():
    result = scout.new_run("p", "r", None)
    with pytest.raises(scout.IllegalTransition):
        scout.record_step(result, "mine", True, "m")
    scout.record_step(result, "init", True, "m")
    with pytest.raises(scout.IllegalTransition):
        scout.record_step(result, "init", True, "m")
    with pytest.raises(scout.IllegalTransition):
        scout.finish_run(result)
    done = _ran(scout.new_run("p", "r", None), *[True] * 5)
    scout.finish_run(done)
    with pytest.raises(scout.IllegalTransition):
        scout.record_step(done, "analyze", True, "m")
    with pytest.raises(scout.IllegalTransition):
        scout.finish_run(done)


def test_scout_terminal_results_keep_their_json_shape():
    assert scout.error_result("bad") == {"status": "error", "error": "bad"}
    assert list(scout.error_result("e", project_name="p")) == ["status", "project_name", "error"]
    assert list(scout.failed_result("e", project_name="p", repo_url="u")) == [
        "status",
        "project_name",
        "repo_url",
        "error",
    ]


@pytest.mark.parametrize(
    "status,code",
    [("complete", 0), ("failed", 1), ("error", 1), ("running", 1), ("legacy-other", 0), (None, 0)],
)
def test_scout_exit_code_reads_any_status(status, code):
    assert scout.exit_code({"status": status}) == code


class ScoutRunMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.result = scout.new_run("p", "r", None)

    @rule(step=st.sampled_from(scout.STEP_ORDER), ok=st.booleans())
    def record(self, step, ok):
        r = self.result
        n = len(r["steps"])
        legal = (
            r["status"] == "running" and n < len(scout.STEP_ORDER) and step == scout.STEP_ORDER[n]
        )
        before = {k: dict(v) for k, v in r["steps"].items()}, r["status"]
        if legal:
            scout.record_step(r, step, ok, "m")
        else:
            with pytest.raises(scout.IllegalTransition):
                scout.record_step(r, step, ok, "m")
            assert ({k: dict(v) for k, v in r["steps"].items()}, r["status"]) == before

    @precondition(lambda self: self.result["status"] == "running")
    @rule()
    def finish(self):
        r = self.result
        if tuple(r["steps"]) == scout.STEP_ORDER:
            scout.finish_run(r)
        else:
            with pytest.raises(scout.IllegalTransition):
                scout.finish_run(r)

    @invariant()
    def consistent(self):
        r = self.result
        steps = tuple(r["steps"])
        assert steps == scout.STEP_ORDER[: len(steps)]
        statuses = {s: v["status"] for s, v in r["steps"].items()}
        failed = [s for s, v in statuses.items() if v == "failed"]
        assert all(s in scout.CRITICAL_STEPS for s in failed)
        assert all(statuses[s] != "partial" for s in statuses if s in scout.CRITICAL_STEPS)
        if failed:
            assert r["status"] == "failed" and failed == [steps[-1]]
        elif r["status"] == "complete":
            assert steps == scout.STEP_ORDER
        else:
            assert r["status"] == "running"
        assert ("error" in r) == (r["status"] == "failed")


TestScoutRunMachine = ScoutRunMachine.TestCase
TestScoutRunMachine.settings = settings(max_examples=60, stateful_step_count=15, deadline=None)


# Bugs in run_analysis, proven against its real file layout.

RUNNER_STDOUT_ONE_FAILURE = (
    "  [analysis] sdlc-gap-finder: projects/p/deliverables/analysis/analysis-sdlc-gap-finder.json\n"
    "  [analysis] youtube-correlator ERROR: no data\n"
    "Running automated analysis vectors for 'p'\n"
    "  sdlc-gap-finder: projects/p/deliverables/analysis/analysis-sdlc-gap-finder.json\n"
    "  youtube-correlator: ERROR: no data\n"
)


def test_count_failed_vectors_counts_each_vector_once():
    # Old code counted "ERROR:" occurrences: 2 for one failed vector.
    assert scout.count_failed_vectors(RUNNER_STDOUT_ONE_FAILURE) == 1
    assert scout.count_failed_vectors("  [analysis] a: out.json\n") == 0


def _fake_analyze(monkeypatch, tmp_path, stdout):
    monkeypatch.chdir(tmp_path)
    analysis = tmp_path / "projects" / "p" / "deliverables" / "analysis"
    analysis.mkdir(parents=True)
    (analysis / "analysis-sdlc-gap-finder.json").write_text("{}", encoding="utf-8")
    now = time.time()
    os.utime(analysis / "analysis-sdlc-gap-finder.json", (now, now))
    monkeypatch.setattr(
        scout,
        "run_command",
        lambda cmd, check=True, timeout=300: subprocess.CompletedProcess(cmd, 0, stdout, ""),
    )


def test_run_analysis_finds_files_in_the_analysis_dir(monkeypatch, tmp_path):
    """The runner writes deliverables/analysis/; the hook looked in deliverables/
    and so always reported zero analyses and a 'partial' step."""
    _fake_analyze(monkeypatch, tmp_path, "  [analysis] sdlc-gap-finder: out.json\n")
    ok, _msg, data = scout.run_analysis("p")
    assert ok is True
    assert data["analysis_count"] == 1 and data["failed_vectors"] == 0


def test_run_analysis_with_failed_vectors_is_partial(monkeypatch, tmp_path):
    """The computed success/partial status was dead: failed vectors still read 'success'."""
    _fake_analyze(monkeypatch, tmp_path, RUNNER_STDOUT_ONE_FAILURE)
    ok, _msg, data = scout.run_analysis("p")
    assert ok is False and data["failed_vectors"] == 1 and data["analysis_count"] == 1
    result = _ran(scout.new_run("p", "r", None), True, True, True, True)
    assert scout.record_step(result, "analyze", ok, _msg) is scout.StepStatus.PARTIAL


def test_full_pipeline_records_every_step(monkeypatch):
    for name in ("init_project", "mine_repo", "build_database", "detect_signals"):
        monkeypatch.setattr(scout, name, lambda *a, **k: (True, "ok", {}))
    monkeypatch.setattr(scout, "run_analysis", lambda p: (False, "1 failed", {"analysis_count": 5}))
    result = scout.run_full_pipeline("r", "p")
    assert result["status"] == "complete"
    assert result["steps"]["analyze"]["status"] == "partial"
    monkeypatch.setattr(scout, "mine_repo", lambda *a: (False, "mine failed: x", {}))
    result = scout.run_full_pipeline("r", "p")
    assert result["status"] == "failed" and list(result["steps"]) == ["init", "mine"]


def test_scout_hook_has_no_free_text_status_writes():
    source = (ROOT / "scripts" / "integrations" / "scout_hook.py").read_text(encoding="utf-8")
    for literal in ('"status": "', '"status"] = \'', '["status"] = "'):
        assert literal not in source, literal


# ── Follow-up fixes ──────────────────────────────────────────────────────────


def test_scout_clone_keeps_full_history(tmp_path):
    """The hook cloned with --depth 1, and mine refuses shallow history, so
    every --repo-url run failed at the mine step."""
    src = tmp_path / "src"
    src.mkdir()
    env = {
        **os.environ,
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "T",
        "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "T",
        "GIT_COMMITTER_EMAIL": "t@example.com",
    }

    def git(*args, cwd=src):
        return subprocess.run(
            ["git", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True
        ).stdout.strip()

    git("init", "-q", "-b", "main")
    for i in range(3):
        (src / f"f{i}.txt").write_text(str(i), encoding="utf-8")
        git("add", "-A")
        git("commit", "-q", "-m", f"c{i}")

    dest = tmp_path / "clone"
    ok, path = scout.clone_repo(src.as_uri(), str(dest))
    assert ok, path
    assert git("rev-parse", "--is-shallow-repository", cwd=dest) == "false"
    assert git("rev-list", "--count", "HEAD", cwd=dest) == "3"


@pytest.mark.parametrize(
    "results,status,failed",
    [
        ({"a": "out/analysis-a.json"}, "complete", None),
        ({"a": "out/analysis-a.json", "b": "ERROR: no data"}, "partial", ["b"]),
    ],
)
def test_mcp_analyze_reports_failed_vectors(monkeypatch, results, status, failed):
    """devarch_analyze said "complete" even when vectors failed."""
    monkeypatch.setattr(
        pipeline,
        "analyze",
        lambda ref, vectors: pipeline.AnalysisResult(results, failed_vectors(results)),
    )
    monkeypatch.setattr(mcp_tools, "_ref", lambda name: None)
    out = mcp_tools.devarch_analyze("p")
    assert out["status"] == status
    assert out.get("failed_vectors") == failed
    assert list(out)[:4] == ["status", "project", "vectors_run", "results"]
