"""Characterization of the CLI and MCP pipeline adapters.

Both adapters drive the same pipeline operations (init, mine, build-db,
signals, analyze, visualize, report, audit, run-pipeline). This test runs each
operation through each adapter, in an isolated temp workspace, on a small real
git repository and on error inputs. It records the observable outcome (CLI:
exit code and output; MCP: the returned dict or the raised exception) and
compares it exactly with ``tests/golden/pipeline_contract.json``.

Temp paths are masked. The golden file pins today's behaviour, including the
places where the two adapters disagree. Regenerate it only on purpose:
``UPDATE_GOLDEN=1 python -m pytest tests/test_pipeline_contract.py``.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

import archaeology
from archaeology.cli import main as cli_main


def _import_mcp_tools():
    """Import the MCP tool functions even where the optional `mcp` SDK is absent.

    ``archaeology.mcp_server`` imports the SDK in its package ``__init__``; the
    tool functions themselves do not need it. Where the SDK is missing, a
    throwaway stub stands in for it just long enough to import the package.
    """
    import importlib
    import importlib.util
    import sys
    import types

    if importlib.util.find_spec("mcp") is not None:
        return importlib.import_module("archaeology.mcp_server.tools")

    class _StubFastMCP:
        def __init__(self, *args, **kwargs):
            pass

        def tool(self, *args, **kwargs):
            return lambda fn: fn

        def __getattr__(self, name):
            return lambda *a, **k: (lambda fn: fn)

    names = ("mcp", "mcp.server", "mcp.server.fastmcp")
    stubs = {n: types.ModuleType(n) for n in names}
    stubs["mcp.server.fastmcp"].FastMCP = _StubFastMCP
    sys.modules.update(stubs)
    try:
        return importlib.import_module("archaeology.mcp_server.tools")
    finally:
        for n in names:
            sys.modules.pop(n, None)


mcp = _import_mcp_tools()

GOLDEN = Path(__file__).parent / "golden" / "pipeline_contract.json"
PKG_ROOT = Path(archaeology.__file__).resolve().parent
TEMPLATE = PKG_ROOT / "visualization" / "template.html"

GIT_ENV = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
}


# ── Fixtures and helpers ──────────────────────────────────────────────────────

def _git(repo: Path, *args, date="2026-01-01T12:00:00+0000"):
    env = {
        **os.environ, **GIT_ENV,
        "GIT_AUTHOR_NAME": "Tester", "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "Tester", "GIT_COMMITTER_EMAIL": "t@example.com",
        "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date,
    }
    subprocess.run(["git", "-C", str(repo), *args], check=True, env=env,
                   capture_output=True)


def _make_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    _git(path, "init", "-q", "-b", "main")
    days = ["2026-01-01", "2026-01-02", "2026-01-03", "2026-02-20", "2026-02-21"]
    for i, day in enumerate(days):
        (path / f"f{i}.txt").write_text(f"change {i}\n")
        _git(path, "add", "-A")
        _git(path, "commit", "-q", "-m", f"commit {i}", date=f"{day}T12:00:00+0000")
    return path


class Env:
    """An isolated workspace plus the masking rules for its paths."""

    def __init__(self, root: Path, monkeypatch, template_repo: Path):
        self.root = root
        self.ws = root / "ws"
        self.ws.mkdir()
        self.repo = root / "repo"
        shutil.copytree(template_repo, self.repo)
        self.not_repo = root / "plain"
        self.not_repo.mkdir()
        self.missing_repo = root / "does-not-exist"
        self.fake_git = root / "fakegit"
        (self.fake_git / ".git").mkdir(parents=True)
        # the CLI visualize command reads a cwd-relative template path
        tpl_dir = self.ws / "archaeology" / "visualization"
        tpl_dir.mkdir(parents=True)
        shutil.copy(TEMPLATE, tpl_dir / "template.html")
        monkeypatch.chdir(self.ws)
        monkeypatch.delenv("DEVARCH_WORKSPACE", raising=False)
        for k, v in GIT_ENV.items():
            monkeypatch.setenv(k, v)
        self.monkeypatch = monkeypatch

    def mask(self, text):
        text = str(text)
        for needle, tag in (
            (str(self.root.resolve()), "<TMP>"), (str(self.root), "<TMP>"),
            (str(PKG_ROOT), "<PKG>"),
            (str(tempfile.gettempdir()), "<TMPDIR>"),
        ):
            text = text.replace(needle, tag)
        # serve generates a random temp metadata filename per run
        text = re.sub(r"arch-metadata-\w+\.yaml", "arch-metadata-<RAND>.yaml", text)
        # The cascade verb pins the db-builder subprocess's failure payload,
        # whose traceback text varies by interpreter and install location:
        # the venv's site-packages path, runpy's stdlib line numbers, and
        # traceback caret alignment all differ across Python versions.
        text = re.sub(r"\S*/site-packages", "<VENV>", text)
        text = re.sub(r'(File "<frozen runpy>", line )\d+', r"\1<N>", text)
        # dependency-internal frames (click, sqlite_utils) move on upgrades
        text = re.sub(r'(File "<VENV>[^"]+", line )\d+', r"\1<N>", text)
        # caret lines differ in PRESENCE across Python versions (3.12 anchors
        # fewer frames than 3.15), so drop them rather than normalize them
        text = re.sub(r"^[ \t]*[~^]{3,}[ \t]*\n", "", text, flags=re.M)
        return text

    def mask_obj(self, obj):
        return json.loads(self.mask(json.dumps(obj)))

    def files(self, project):
        base = self.ws / "projects" / project
        if not base.exists():
            return None
        return sorted(
            str(p.relative_to(base)) for p in base.rglob("*")
            if p.is_file() and not p.name.endswith("-journal")
        )


def _cli_args(op, a):
    return {
        "init": lambda: ["init", a["project"], *_opt("--description", a.get("description")),
                         *_opt("--repo-url", a.get("repo_url"))],
        "mine": lambda: ["mine", a["repo"], "--project", a["project"]],
        "build_db": lambda: ["build-db", a["project"]],
        "signals": lambda: ["signals", a["project"], *_opt("--min-gap-days", a.get("min_gap_days"))],
        "analyze": lambda: ["analyze", a["project"], *sum((["--vector", v] for v in a.get("vectors", [])), [])],
        "visualize": lambda: ["visualize", a["project"]],
        "report": lambda: ["export-report", a["project"], "--format", a["fmt"]],
        "audit": lambda: ["audit", a["project"]],
    }[op]()


def _opt(flag, value):
    return [] if value is None else [flag, str(value)]


def _mcp_call(op, a):
    return {
        "init": lambda: mcp.devarch_init(a["project"], a.get("description", ""), a.get("repo_url", "")),
        "mine": lambda: mcp.devarch_mine(a["repo"], a["project"]),
        "build_db": lambda: mcp.devarch_build_db(a["project"]),
        "signals": lambda: mcp.devarch_signals(a["project"], a.get("min_gap_days")),
        "analyze": lambda: mcp.devarch_analyze(a["project"], a.get("vectors") or None),
        "visualize": lambda: mcp.devarch_visualize(a["project"]),
        "report": lambda: mcp.devarch_report(a["project"], a["fmt"]),
        "audit": lambda: mcp.devarch_audit(a["project"]),
        "run_pipeline": lambda: mcp.devarch_run_pipeline(a["repo"], a["project"]),
    }[op]()


def _step(env: Env, capfd, adapter, op, **a):
    """Run one operation through one adapter and return its masked outcome."""
    if "repo" in a:
        a["repo"] = str(getattr(env, a["repo"]))
    capfd.readouterr()
    rec = {"op": op, "args": env.mask_obj({k: v for k, v in a.items()})}
    if adapter == "cli":
        result = CliRunner().invoke(cli_main, _cli_args(op, a))
        rec["exit_code"] = result.exit_code
        rec["output"] = env.mask(result.output)
        if result.exception and not isinstance(result.exception, SystemExit):
            rec["exception"] = [type(result.exception).__name__, env.mask(result.exception)]
    else:
        try:
            rec["returned"] = env.mask_obj(_mcp_call(op, a))
        except BaseException as exc:  # noqa: BLE001 - the exception is the outcome
            rec["raised"] = [type(exc).__name__, env.mask(exc)]
    captured = capfd.readouterr()
    rec["stdout"] = env.mask(captured.out)
    rec["stderr"] = env.mask(captured.err)
    return rec


def _happy(env, capfd, adapter):
    steps = [
        ("init", dict(project="alpha", description="Alpha", repo_url="https://example.com/a")),
        ("init", dict(project="alpha")),
        ("mine", dict(repo="repo", project="alpha")),
        ("build_db", dict(project="alpha")),
        ("signals", dict(project="alpha")),
        ("signals", dict(project="alpha", min_gap_days=5)),
        ("analyze", dict(project="alpha", vectors=["sdlc-gap-finder"])),
        ("analyze", dict(project="alpha")),
        ("visualize", dict(project="alpha")),
        ("report", dict(project="alpha", fmt="markdown")),
        ("report", dict(project="alpha", fmt="html")),
        ("audit", dict(project="alpha")),
    ]
    if adapter == "mcp":
        steps.append(("run_pipeline", dict(repo="repo", project="beta")))
    out = []
    for op, a in steps:
        rec = _step(env, capfd, adapter, op, **a)
        rec["files_after"] = env.files(a["project"])
        out.append(rec)
    return out


def _errors(env, capfd, adapter):
    # a project that exists but has no database, and a project with no data
    init = [("init", dict(project="bare"))]
    steps = init + [
        ("mine", dict(repo="missing_repo", project="bare")),
        ("mine", dict(repo="not_repo", project="bare")),
        ("mine", dict(repo="fake_git", project="bare")),
        ("mine", dict(repo="repo", project="ghost1")),
        ("mine", dict(repo="not_repo", project="ghost2")),
        ("build_db", dict(project="ghost3")),
        ("build_db", dict(project="bare")),
        ("signals", dict(project="ghost4")),
        ("signals", dict(project="bare")),
        ("analyze", dict(project="ghost5")),
        ("analyze", dict(project="bare", vectors=["no-such-vector"])),
        ("visualize", dict(project="ghost6")),
        ("report", dict(project="ghost7", fmt="markdown")),
        ("audit", dict(project="ghost8")),
        ("init", dict(project="../escape")),
        ("init", dict(project="bad name")),
    ]
    if adapter == "mcp":
        steps += [
            ("report", dict(project="bare", fmt="pdf")),
            ("run_pipeline", dict(repo="not_repo", project="gamma")),
            ("run_pipeline", dict(repo="fake_git", project="delta")),
        ]
    else:
        steps += [("report", dict(project="bare", fmt="pdf"))]
    out = []
    for op, a in steps:
        rec = _step(env, capfd, adapter, op, **a)
        out.append(rec)
    return out


def _run_all(tmp_path_factory, monkeypatch, capfd):
    outcome = {}
    template_repo = _make_repo(tmp_path_factory.mktemp("template") / "repo")
    for scenario, fn in (("happy", _happy), ("errors", _errors)):
        for adapter in ("cli", "mcp"):
            root = tmp_path_factory.mktemp(f"{scenario}-{adapter}")
            with monkeypatch.context() as mp:
                env = Env(root, mp, template_repo)
                outcome[f"{scenario}/{adapter}"] = fn(env, capfd, adapter)
    root = tmp_path_factory.mktemp("verbs-cli")
    with monkeypatch.context() as mp:
        env = Env(root, mp, template_repo)
        outcome["verbs/cli"] = _verbs(env, capfd)
    return outcome


# ── cascade / serve / sync (CLI-only verbs) ───────────────────────────────────
#
# These three verbs have no MCP surface, so they are characterized through the
# CLI alone. ``serve`` never launches Datasette here: ``subprocess.run`` in the
# CLI module is replaced with a capturer that records the built command and the
# generated metadata file. ``sync`` runs only its hermetic error path, because
# the command resolves its profile from the package's ``config/`` first, which
# names the developer's real projects; the full flow is covered by the service
# interface tests.

ERAS_JSON = {
    "first_commit_date": "2026-01-01",
    "eras": [
        {"id": 1, "name": "Dawn", "dates": "2026-01-01 to 2026-01-31", "commits": 3},
        {"id": 2, "name": "Growth", "dates": "2026-02-01 to 2026-02-28", "commits": 2},
    ],
}


def _capture_serve(monkeypatch):
    """Replace the CLI's Datasette launch with a command/metadata capturer."""
    captured = {}

    def fake_run(cmd, *args, **kwargs):
        captured["cmd"] = list(cmd)
        meta = None
        for i, part in enumerate(cmd):
            if part == "--metadata" and i + 1 < len(cmd):
                p = Path(cmd[i + 1])
                if p.exists():
                    meta = p.read_text()
        captured["metadata"] = meta
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr("archaeology.cli.subprocess.run", fake_run)
    return captured


def _verbs(env, capfd):
    from archaeology import pipeline as svc

    # alpha: a project with mined data and a built database (state prep only).
    ref = svc.ProjectRef.for_cli("alpha", must_exist=False)
    svc.init(ref, "Alpha", "https://example.com/a")
    svc.mine(str(env.repo), ref, expand_repo_path=False)
    svc.build_db(ref)
    # bare: a project with no data at all.
    svc.init(svc.ProjectRef.for_cli("bare", must_exist=False), "Bare", "")

    out = []

    def run(op, args, **extra):
        capfd.readouterr()
        rec = {"op": op, "args": env.mask_obj({"args": args, **extra})}
        result = CliRunner().invoke(cli_main, [op, *args])
        rec["exit_code"] = result.exit_code
        rec["output"] = env.mask(result.output)
        if result.exception and not isinstance(result.exception, SystemExit):
            rec["exception"] = [type(result.exception).__name__, env.mask(result.exception)]
        captured = capfd.readouterr()
        rec["stdout"] = env.mask(captured.out)
        rec["stderr"] = env.mask(captured.err)
        out.append(rec)
        return rec

    # serve: missing project, project without a database, project with one.
    run("serve", ["ghost9", "--port", "8021"])
    run("serve", ["bare", "--port", "8022"])
    env.ws.joinpath("config").mkdir(exist_ok=True)
    env.ws.joinpath("config", "datasette-metadata.yaml").write_text(
        'title: "Archaeology Database"\ndescription: test\n', encoding="utf-8")
    with env.monkeypatch.context() as mp:
        cap = _capture_serve(mp)
        rec = run("serve", ["alpha", "--port", "8023", "--unsafe-cors"])
        rec["serve_cmd"] = env.mask_obj(cap.get("cmd"))
        rec["serve_metadata"] = env.mask(cap.get("metadata"))
    env.ws.joinpath("config", "datasette-metadata.yaml").unlink()

    # cascade: missing project, no eras file, full run, dry run.
    run("cascade", ["ghost10"])
    run("cascade", ["alpha"])
    pj_path = env.ws / "projects" / "alpha" / "project.json"
    pj = json.loads(pj_path.read_text())
    pj["repo_path"] = str(env.repo)
    pj_path.write_text(json.dumps(pj, indent=2))
    run("cascade", ["alpha"])
    (env.ws / "projects" / "alpha" / "data" / "commit-eras.json").write_text(
        json.dumps(ERAS_JSON))
    rec = run("cascade", ["alpha"])
    rec["files_after"] = env.files("alpha")
    run("cascade", ["alpha", "--dry-run"])
    run("cascade", ["alpha", "--skip-mine", "--dry-run"])

    # sync: hermetic error path only (one unknown name; set order is unstable).
    run("sync", ["--project", "ghostproj"])
    return out


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_adapter_outcomes_match_golden(tmp_path_factory, monkeypatch, capfd):
    actual = json.dumps(_run_all(tmp_path_factory, monkeypatch, capfd), indent=2) + "\n"
    if os.environ.get("UPDATE_GOLDEN"):
        GOLDEN.write_text(actual, encoding="utf-8")
    assert GOLDEN.exists(), "golden missing; run with UPDATE_GOLDEN=1"
    assert actual == GOLDEN.read_text(encoding="utf-8")


def test_mcp_audit_never_evaluates_fail_on(tmp_path, monkeypatch):
    """The MCP audit tool reports findings only; fail_on is accepted but unused.

    Review of the pipeline refactor caught a regression: the shared service
    evaluated fail_on for every caller, so an unknown level raised KeyError
    over MCP where it used to return the normal result.
    """
    monkeypatch.setenv("DEVARCH_WORKSPACE", str(tmp_path))
    (tmp_path / "projects").mkdir()
    monkeypatch.chdir(tmp_path)
    mcp.devarch_init("audited", "d", "u")
    baseline = mcp.devarch_audit("audited", "HIGH")
    assert baseline["status"] == "complete"
    assert mcp.devarch_audit("audited", "BOGUS") == baseline
