"""Pipeline service: one place that runs the DevArch pipeline operations.

The click CLI (``archaeology/cli.py``) and the MCP tools
(``archaeology/mcp_server/tools.py``) are thin adapters over this module. It
owns project-directory resolution, input validation and each operation
(init, mine, build-db, signals, analyze, visualize, report, audit, the
mine-to-analyze run, and the CLI-only verbs serve, cascade and sync).
Adapters keep only presentation: click parsing, echo and exit codes on one
side, dict shaping on the other.

Caller-fixable failures raise ``PipelineError``. Its ``kind`` lets an adapter
choose its own wording where the two surfaces have always worded the same
failure differently. Unexpected failures (a git extraction error, a database
build crash) propagate unchanged.

The two surfaces still differ in behaviour in a few places. Each difference is
an explicit parameter or a separate function here, not a hidden branch:

* project resolution: ``ProjectRef.for_cli`` (cwd-relative ``projects/<name>``,
  the project must exist, name unchecked) versus ``ProjectRef.for_workspace``
  (``DEVARCH_WORKSPACE`` or cwd, resolved, name validated, may not exist yet);
* ``build_db(isolated=...)``: the CLI runs the builder in a subprocess, the MCP
  tool calls it in-process;
* ``mine(expand_repo_path=...)``: the MCP tool hands git the ``~``-expanded
  path, the CLI hands it the path as typed;
* ``render_visualization`` (CLI template hydration) and ``render_project_index``
  (MCP dashboard index) are different renderers;
* ``render_report`` (MCP) converts Markdown itself; the CLI calls
  ``report.export_report`` directly, which is already a single deep call.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterator

from .state_machine import require_transition

# Moved to visualization/hydrate.py (L6 renderer move); re-exported for compat.
from .visualization.hydrate import (  # noqa: F401
    DEFAULT_TEMPLATE,
    VisualizationResult,
    render_visualization,
)

# ── Errors ────────────────────────────────────────────────────────────────────


class PipelineError(Exception):
    """A failure the caller can fix (bad input, missing project, missing database).

    ``kind`` names the failure class so an adapter can word it its own way:
    ``project-missing``, ``repo-missing``, ``not-git``, ``no-database``,
    ``invalid-json``, ``template-missing``, ``not-discovered``, ``invalid-input``.
    ``path`` carries the location a message refers to, when there is one.
    """

    def __init__(self, message: str, kind: str = "invalid-input", path: str | None = None):
        super().__init__(message)
        self.message = message
        self.kind = kind
        self.path = path


# ── Workspace and project resolution ──────────────────────────────────────────


def get_workspace_root() -> Path:
    """Resolve the workspace root from DEVARCH_WORKSPACE env var or CWD."""
    env = os.environ.get("DEVARCH_WORKSPACE")
    if env:
        path = Path(env).resolve()
        # Validate workspace path
        if not path.exists():
            raise ValueError(f"DEVARCH_WORKSPACE path does not exist: {path}")
        if not path.is_dir():
            raise ValueError(f"DEVARCH_WORKSPACE path is not a directory: {path}")
        return path
    return Path.cwd().resolve()


def get_projects_dir() -> Path:
    """Return the projects/ directory path."""
    return get_workspace_root() / "projects"


def validate_project_name(name: str) -> None:
    """Validate project name for security.

    Raises:
        ValueError: If the project name is invalid
    """
    if not name:
        raise ValueError("Project name cannot be empty")

    if len(name) > 100:
        raise ValueError(f"Project name too long (max 100 chars): {len(name)}")

    # Only allow alphanumeric, dot, underscore, hyphen
    # fullmatch, not ^...$: "$" also matches before a trailing newline.
    if not re.fullmatch(r"[a-zA-Z0-9._-]+", name):
        raise ValueError(f"Project name contains invalid characters: {name!r}")

    # Reject path traversal attempts
    if ".." in name:
        raise ValueError(f"Project name cannot contain '..': {name!r}")

    if name.startswith("/"):
        raise ValueError(f"Project name cannot start with '/': {name!r}")

    # "." would resolve to projects/ itself; a leading "-" reads as a CLI flag.
    if name.startswith((".", "-")):
        raise ValueError(f"Project name cannot start with '.' or '-': {name!r}")


def get_project_dir(project_name: str) -> Path:
    """Return a specific project's directory path inside the workspace.

    Raises:
        ValueError: If project name is invalid or path traversal detected
    """
    validate_project_name(project_name)

    projects_dir = get_projects_dir()
    project_path = (projects_dir / project_name).resolve()

    # Verify the resolved path is within projects directory
    try:
        project_path.relative_to(projects_dir.resolve())
    except ValueError:
        raise ValueError(f"Project path escape detected: {project_name!r}")

    return project_path


@dataclass(frozen=True)
class ProjectRef:
    """A project named by an adapter, resolved to a directory on demand."""

    name: str
    workspace: bool = False
    must_exist: bool = False

    @classmethod
    def for_cli(cls, name: str, must_exist: bool = True) -> "ProjectRef":
        """``projects/<name>`` relative to the cwd; by default the project must exist.

        The name is validated like a workspace name, so ``../x`` and other
        unsafe names can never resolve outside ``projects/``.
        """
        try:
            validate_project_name(name)
        except ValueError as e:
            raise PipelineError(str(e), kind="invalid-name") from None
        return cls(name, workspace=False, must_exist=must_exist)

    @classmethod
    def for_workspace(cls, name: str) -> "ProjectRef":
        """``<workspace>/projects/<name>``, validated; the project may be new."""
        return cls(name, workspace=True, must_exist=False)

    def resolve(self) -> Path:
        """Return the project directory, raising ``PipelineError`` if required and missing."""
        if self.workspace:
            return get_project_dir(self.name)
        path = Path(os.path.join("projects", self.name))
        if self.must_exist and not os.path.isdir(path):
            raise PipelineError(
                f"Project '{self.name}' not found",
                kind="project-missing",
                path=str(path),
            )
        return path

    def root(self) -> Path:
        """The directory that cwd-relative engine functions expect to run from."""
        return get_workspace_root() if self.workspace else Path.cwd()


@contextmanager
def in_workspace(project: ProjectRef) -> Iterator[None]:
    """Run cwd-relative engine functions from the project's workspace root."""
    if not project.workspace:
        yield
        return
    saved = os.getcwd()
    os.chdir(str(get_workspace_root()))
    try:
        yield
    finally:
        os.chdir(saved)


def load_config_file(path: str) -> dict:
    """Read a JSON config file; a malformed file is a ``PipelineError``."""
    try:
        with open(path) as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise PipelineError(f"Invalid JSON in {path}: {e}", kind="invalid-json")


# ── init ──────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class InitResult:
    created: bool
    project_dir: Path
    config_path: Path


def init(project: ProjectRef, description: str, repo_url: str) -> InitResult:
    """Create the project directories and ``project.json`` if absent."""
    project_dir = project.resolve()
    (project_dir / "data").mkdir(parents=True, exist_ok=True)
    (project_dir / "deliverables").mkdir(parents=True, exist_ok=True)

    config_path = project_dir / "project.json"
    if config_path.exists():
        return InitResult(False, project_dir, config_path)

    config = {
        "name": project.name,
        "description": description,
        "repo_url": repo_url,
        "developer": {},
        "timeline": {},
        "overrides": {},
        "visualization": {},
        "data_sources": {},
    }
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    return InitResult(True, project_dir, config_path)


# ── mine ──────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MineResult:
    commits: int
    csv_path: str
    stats_path: str


def require_git_repo(repo_path: str) -> str:
    """Return the ``~``-expanded repo path, or raise if it is not a git checkout."""
    expanded = os.path.expanduser(repo_path)
    if not os.path.isdir(expanded):
        raise PipelineError(f"Repository not found: {repo_path}", kind="repo-missing")
    if not os.path.exists(os.path.join(expanded, ".git")):  # a worktree has a .git file
        raise PipelineError(f"Not a git repository: {repo_path}", kind="not-git")
    return expanded


def mine(
    repo_path: str,
    project: ProjectRef,
    *,
    verbose: bool = False,
    expand_repo_path: bool = True,
    on_event: Callable[[str, Any], None] | None = None,
) -> MineResult:
    """Extract git history into the project's data directory.

    The repository is validated before the project is resolved. Extraction
    failures propagate unchanged. ``on_event`` receives ``("start", None)``,
    ``("csv-done", commit_count)`` and tells the caller which extraction
    stage a failure belongs to: before ``csv-done`` it is the commit log,
    after it the stats log.
    """
    import hashlib

    from archaeology.extractors.git import (
        extract_git_log,
        extract_git_log_with_stats,
        repository_coverage,
    )
    from archaeology.utils import atomic_write

    expanded = require_git_repo(repo_path)
    project_dir = project.resolve()
    data_dir = project_dir / "data"
    source = expanded if expand_repo_path else repo_path
    coverage = repository_coverage(source)  # git failures propagate unchanged
    if coverage["shallow"]:
        raise PipelineError(
            "Shallow history: fetch complete history before mining; no fetch performed",
            kind="shallow",
        )

    def emit(event: str, detail: Any = None) -> None:
        if on_event:
            on_event(event, detail)

    emit("start")
    data_dir.mkdir(parents=True, exist_ok=True)
    csv_path = str(data_dir / "github-commits.csv")
    count = extract_git_log(source, csv_path, verbose=verbose)
    emit("csv-done", count)

    stats_path = str(data_dir / "github-commits-with-stats.txt")
    extract_git_log_with_stats(source, stats_path, verbose=verbose)

    # Bind the mined bytes to the refs they came from, so audit can detect
    # later edits (0.4.1 evidence binding).
    if repository_coverage(source) != coverage:
        raise PipelineError(
            "Repository refs changed during mining; retry before analysis", kind="refs-changed"
        )
    coverage["artifact_sha256"] = {
        Path(path).name: hashlib.sha256(Path(path).read_bytes()).hexdigest()
        for path in (csv_path, stats_path)
    }
    atomic_write(data_dir / "coverage.json", json.dumps(coverage, indent=2))
    config_path = project_dir / "project.json"
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["repo_path"] = str(Path(expanded).resolve())
        config["mined_history_manifest_required"] = True
        atomic_write(config_path, json.dumps(config, indent=2))
    return MineResult(count, csv_path, stats_path)


# ── build-db ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class BuildResult:
    db_path: Path
    built: bool
    returncode: int = 0
    error: str | None = None


def build_db(project: ProjectRef, *, verbose: bool = False, isolated: bool = False) -> BuildResult:
    """Build the project's SQLite database.

    ``isolated=True`` runs the builder in a subprocess (a failing build raises
    ``subprocess.CalledProcessError``); otherwise it runs in-process and a
    build exception is reported in ``BuildResult.error``.
    """
    project_dir = project.resolve()
    db_path = project_dir / "data" / "archaeology.db"

    if isolated:
        cmd = [sys.executable, "-m", "archaeology.db.builder", "--project-root", str(project_dir)]
        if verbose:
            cmd.append("--verbose")
        env = os.environ.copy()
        pkg_root = str(Path(__file__).parent.parent)
        env["PYTHONPATH"] = pkg_root + (
            (os.pathsep + env["PYTHONPATH"]) if env.get("PYTHONPATH") else ""
        )
        result = subprocess.run(cmd, check=True, timeout=300, env=env)
        return BuildResult(db_path, db_path.exists(), result.returncode)

    from archaeology.db.builder import build_db as run_builder

    try:
        run_builder(project_root=project_dir, verbose=verbose)
    except Exception as e:
        return BuildResult(db_path, False, 0, str(e))
    if db_path.exists():
        return BuildResult(db_path, True)
    return BuildResult(db_path, False, 0, "Database file not created after build")


# ── signals ───────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SignalsResult:
    signals: list
    clusters: list
    output_path: Path


def signals(
    project: ProjectRef,
    *,
    config: dict | None = None,
    min_gap_days: int | None = None,
) -> SignalsResult:
    """Detect development signals; the database must already exist."""
    from archaeology.classifiers.era_detector import detect_signals

    project_dir = project.resolve()
    if not (project_dir / "data" / "archaeology.db").exists():
        raise PipelineError("Database not found. Run build-db first.", kind="no-database")

    config = dict(config) if config else {}
    if min_gap_days is not None:
        config["min_gap_days"] = min_gap_days

    with in_workspace(project):
        result = detect_signals(project.name, config=config or None)

    if isinstance(result, dict):
        found, clusters = result.get("signals", []), result.get("cluster_summary", [])
    else:
        found, clusters = result, []
    return SignalsResult(found, clusters, project_dir / "data" / "detected-signals.json")


# ── analyze ───────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AnalysisResult:
    results: dict
    failed: dict = field(default_factory=dict)


def validate_vectors(vectors) -> list[str]:
    """Return the vectors to run (all when none given) or raise on unknown names."""
    from archaeology.analysis_runner import AnalysisRunner

    available = AnalysisRunner.VECTORS
    unknown = set(vectors) - set(available) if vectors else set()
    if unknown:
        raise PipelineError("\n".join(f"Unknown vector: {v}" for v in sorted(unknown)))
    return list(vectors) if vectors else list(available)


def analysis_dir(project: ProjectRef) -> Path:
    """Return (creating it) the project's analysis output directory."""
    path = project.resolve() / "deliverables" / "analysis"
    path.mkdir(parents=True, exist_ok=True)
    return path


def analyze(
    project: ProjectRef, vectors: list[str] | None = None, *, verbose: bool = False
) -> AnalysisResult:
    """Run analysis vectors. The engine itself rejects a missing project or unknown vector."""
    from archaeology.analysis_runner import failed_vectors, run_analysis_vectors

    with in_workspace(project):
        results = run_analysis_vectors(project.name, verbose=verbose, vectors=vectors)
    return AnalysisResult(results, failed_vectors(results))


def render_project_index(project: ProjectRef) -> Path:
    """Write the dashboard project index page (the MCP renderer)."""
    project_dir = project.resolve()
    if not project_dir.exists():
        raise PipelineError(f"Project '{project.name}' not found", kind="project-missing")

    from archaeology.visualization.dashboard import discover_projects, generate_project_index

    projects_dir = get_projects_dir()
    projects = discover_projects(projects_dir) if projects_dir.exists() else []
    project_data = next((p for p in projects if p["name"] == project.name), None)
    if not project_data:
        raise PipelineError(
            f"Project '{project.name}' not found in discovered projects",
            kind="not-discovered",
        )

    html = generate_project_index(project_data)
    output_dir = project_dir / "deliverables" / "visuals"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "index.html"
    output_path.write_text(html, encoding="utf-8")
    return output_path


# ── report ────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ReportResult:
    fmt: str
    output_path: Path


def render_report(project: ProjectRef, fmt: str = "html") -> ReportResult:
    """Write the Markdown report and, for ``html``, a rendered copy (the MCP report)."""
    fmt = fmt.lower().strip()
    if fmt not in ("html", "markdown"):
        raise PipelineError(f"Invalid format '{fmt}'. Use 'html' or 'markdown'.")

    project_dir = project.resolve()
    if not project_dir.exists():
        raise PipelineError(f"Project '{project.name}' not found", kind="project-missing")

    from archaeology.report import export_html_report, export_markdown_report

    if fmt == "markdown":
        return ReportResult("markdown", export_markdown_report(project.name, str(project_dir)))
    # Writes the Markdown report and report.html, each with its evidence binding.
    return ReportResult("html", export_html_report(project.name, project_dir))


# ── audit ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AuditResult:
    findings: list
    summary: dict
    # None when no fail_on level was given: the caller only wants findings.
    blocking: bool | None


def audit(project: ProjectRef, fail_on: str | None = "HIGH") -> AuditResult:
    """Run the forensic audit from the project's root.

    ``fail_on`` sets the severity that makes the result blocking; pass None to
    skip that verdict entirely (the MCP tool reports findings only).
    """
    from archaeology.audit import has_blocking_findings, run_audit, summarize

    findings = run_audit(project.name, project.root())
    blocking = None if fail_on is None else has_blocking_findings(findings, fail_on=fail_on)
    return AuditResult(findings, summarize(findings), blocking)


# ── run-pipeline ──────────────────────────────────────────────────────────────


class RunStage(str, Enum):
    """Where a ``run_pipeline`` run is. The only legal moves::

        INITIALIZED --mined--------> MINED --built--------> BUILT --finished--> COMPLETE
             |                         |
             +--mine_failed--> MINE_FAILED   +--build_failed--> BUILD_FAILED

    ``COMPLETE``, ``MINE_FAILED`` and ``BUILD_FAILED`` are terminal.
    """

    INITIALIZED = "initialized"
    MINED = "mined"
    BUILT = "built"
    COMPLETE = "complete"
    MINE_FAILED = "mine_failed"
    BUILD_FAILED = "build_failed"


RUN_TRANSITIONS: dict[RunStage, frozenset[RunStage]] = {
    RunStage.INITIALIZED: frozenset({RunStage.MINED, RunStage.MINE_FAILED}),
    RunStage.MINED: frozenset({RunStage.BUILT, RunStage.BUILD_FAILED}),
    RunStage.BUILT: frozenset({RunStage.COMPLETE}),
    RunStage.COMPLETE: frozenset(),
    RunStage.MINE_FAILED: frozenset(),
    RunStage.BUILD_FAILED: frozenset(),
}

# The step name each failed stage reports as ``failed_at`` (MCP output values).
FAILED_AT: dict[RunStage, str] = {
    RunStage.MINE_FAILED: "mine",
    RunStage.BUILD_FAILED: "build_db",
}


@dataclass
class PipelineRun:
    """Outcome of init, mine, build-db, signals, analyze run in order.

    Fields are written only by the transition methods below, which refuse any
    move ``RUN_TRANSITIONS`` does not list.
    """

    init_created: bool
    stage: RunStage = RunStage.INITIALIZED
    mine: MineResult | None = None
    mine_error: str | None = None
    build: BuildResult | None = None
    signal_count: int = 0
    analysis: list | str = field(default_factory=list)

    @property
    def failed_at(self) -> str | None:
        """``"mine"`` or ``"build_db"`` for a failed run, else ``None``."""
        return FAILED_AT.get(self.stage)

    def _move(self, target: RunStage) -> None:
        self.stage = require_transition("PipelineRun", RUN_TRANSITIONS, self.stage, target)

    def mined(self, result: MineResult) -> None:
        self._move(RunStage.MINED)
        self.mine = result

    def mine_failed(self, message: str) -> None:
        self._move(RunStage.MINE_FAILED)
        self.mine_error = message

    def built(self, result: BuildResult) -> None:
        """Record the build; a build carrying an error fails the run."""
        self._move(RunStage.BUILT if result.error is None else RunStage.BUILD_FAILED)
        self.build = result

    def finished(self, signal_count: int, analysis: list | str) -> None:
        self._move(RunStage.COMPLETE)
        self.signal_count = signal_count
        self.analysis = analysis


def run_pipeline(repo_path: str, project: ProjectRef) -> PipelineRun:
    """Run the full pipeline, stopping at the first failed mine or build step.

    A missing database for signals counts zero signals, and an analysis
    exception is recorded rather than raised, as the MCP tool always has.
    """
    run = PipelineRun(init_created=init(project, "", "").created)

    try:
        run.mined(mine(repo_path, project))
    except PipelineError as e:
        run.mine_failed(e.message)
        return run

    run.built(build_db(project))
    if run.stage is RunStage.BUILD_FAILED:
        return run

    try:
        signal_count = len(signals(project).signals)
    except PipelineError:
        signal_count = 0

    analysis: list | str
    try:
        analysis = list(analyze(project).results.keys())
    except Exception as e:
        analysis = f"skipped: {e}"
    run.finished(signal_count, analysis)
    return run


# ── serve ──────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ServeLaunch:
    """A Datasette invocation built for one project's database.

    ``temp_metadata`` marks that ``metadata_src`` is a temp file the caller
    must unlink after the launch returns.
    """

    cmd: list[str]
    db_path: str
    metadata_src: str | None
    temp_metadata: bool


def prepare_serve(project: ProjectRef, port: int, unsafe_cors: bool) -> ServeLaunch:
    """Build the Datasette launch for a project's database.

    The database must already exist. A project-specific
    ``datasette-metadata.yaml`` wins; otherwise the workspace default at
    ``config/datasette-metadata.yaml`` is copied to a temp file with the
    project's display title injected.
    """
    project_dir = project.resolve()
    db_path = os.path.join(project_dir, "data", "archaeology.db")

    if not os.path.exists(db_path):
        raise PipelineError(
            f"Database not found at {db_path}. Run 'devarch build-db {project.name}' first.",
            kind="no-database",
        )

    project_config = {}
    config_path = os.path.join(project_dir, "project.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, encoding="utf-8") as f:
                project_config = json.load(f)
        except json.JSONDecodeError as e:
            raise PipelineError(f"Invalid JSON in {config_path}: {e}", kind="invalid-json")

    display_name = project_config.get("visualization", {}).get("title", project.name.upper())

    project_metadata = os.path.join(project_dir, "datasette-metadata.yaml")
    default_metadata = os.path.join("config", "datasette-metadata.yaml")

    metadata_src = None
    temp_metadata = False
    if os.path.exists(project_metadata):
        metadata_src = project_metadata
    elif os.path.exists(default_metadata):
        with open(default_metadata, encoding="utf-8") as f:
            content = f.read()
        content = content.replace(
            'title: "Archaeology Database"',
            f'title: "{display_name} Archaeology Database"',
        )
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, prefix="arch-metadata-"
        )
        tmp.write(content)
        tmp.close()
        metadata_src = tmp.name
        temp_metadata = True

    cmd = ["datasette", db_path, "--port", str(port), "--setting", "sql_time_limit_ms,5000"]
    if unsafe_cors:
        cmd.append("--cors")
    if metadata_src:
        cmd.extend(["--metadata", metadata_src])
    return ServeLaunch(cmd, db_path, metadata_src, temp_metadata)


# ── cascade ────────────────────────────────────────────────────────────────────


@dataclass
class CascadeOutcome:
    """Exit verdict of a cascade run; the transcript went to ``on_line``."""

    exit_code: int = 0
    files_scanned: int = 0
    stale_refs_remaining: int = 0


def cascade(
    project: ProjectRef,
    *,
    dry_run: bool = False,
    skip_mine: bool = False,
    on_line: Callable[..., None] | None = None,
) -> CascadeOutcome:
    """Full pipeline: mine → build-db → signals → era cascade → sync → audit.

    Every line this verb has always printed is emitted through ``on_line``
    (called as ``on_line(text, err=False)``), in the same order; the return
    value carries only the exit verdict. Failures that used to stop the run
    return early with their lines already emitted.
    """

    def say(text: str, err: bool = False) -> None:
        if on_line:
            on_line(text, err)

    from .classifiers.era_detector import detect_signals
    from .era_cascade import cascade as run_cascade
    from .extractors.git import extract_git_log, extract_git_log_with_stats

    project_dir = Path(project.resolve())
    project_json_path = project_dir / "project.json"
    eras_path = project_dir / "data" / "commit-eras.json"
    data_dir = project_dir / "data"

    # Load project config for repo path
    repo_path = None
    if project_json_path.exists():
        try:
            pj = json.loads(project_json_path.read_text())
            repo_path = pj.get("repo_path")
            if repo_path:
                repo_path = os.path.expanduser(repo_path)
        except json.JSONDecodeError as e:
            say(f"Error: Invalid JSON in {project_json_path}: {e}", err=True)
            return CascadeOutcome(1)

    # ── Step 1: Mine fresh git data ──
    if not skip_mine:
        if not repo_path or not os.path.isdir(repo_path):
            say(f"  SKIP: repo_path not found ({repo_path}). Use --skip-mine to skip mining.")
        else:
            say(f"\n[1/7] Mining git data from {repo_path}...")
            csv_path = data_dir / "github-commits.csv"
            try:
                count = extract_git_log(repo_path, str(csv_path))
                say(f"  Extracted {count} commits")
            except (RuntimeError, Exception) as e:
                say(f"  Error: Git extraction failed: {e}", err=True)
                return CascadeOutcome(1)
            stats_path = data_dir / "github-commits-with-stats.txt"
            try:
                extract_git_log_with_stats(repo_path, str(stats_path))
            except (RuntimeError, Exception) as e:
                say(f"  Error: Git stats extraction failed: {e}", err=True)
                return CascadeOutcome(1)
    else:
        say("\n[1/7] Mining — SKIPPED (--skip-mine)")

    # ── Step 2: Build database ──
    say("\n[2/7] Building database...")
    db_path = data_dir / "archaeology.db"
    cmd = [sys.executable, "-m", "archaeology.db.builder", "--project-root", str(project_dir)]
    _env = os.environ.copy()
    _pkg_root = str(Path(__file__).parent.parent)
    _env["PYTHONPATH"] = _pkg_root + (
        (os.pathsep + _env["PYTHONPATH"]) if _env.get("PYTHONPATH") else ""
    )
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=_env)
    if result.returncode == 0:
        say(f"  Database built ({db_path})")
    else:
        say(f"  Build failed: {result.stderr}")

    # ── Step 3: Detect signals ──
    say("\n[3/7] Detecting signals...")
    sig_result = detect_signals(project.name)
    n_signals = len(sig_result.get("signals", []))
    n_clusters = len(sig_result.get("cluster_summary", []))
    say(f"  {n_signals} signals across {n_clusters} clusters")

    # ── Step 4: Era cascade ──
    say("\n[4/7] Running era cascade...")
    if not eras_path.exists():
        say(f"  ERROR: No commit-eras.json found at {eras_path}", err=True)
        return CascadeOutcome(1)

    if dry_run:
        say("  (dry run — no files will be written)")

    cascade_result = run_cascade(project_dir, eras_path, dry_run=dry_run)
    say(f"  Files scanned: {cascade_result.files_scanned}")
    say(f"  Files changed: {cascade_result.files_changed}")
    say(f"  Era fields remapped: {cascade_result.era_fields_remapped}")
    say(f"  Stale refs remaining: {cascade_result.stale_refs_remaining}")

    # ── Step 5: Sync derived deliverables ──
    say("\n[5/7] Syncing derived deliverables...")
    sync_script = Path(__file__).parent.parent / "scripts" / "sync" / "sync_derived_deliverables.py"
    if sync_script.exists():
        sync_cmd = [sys.executable, str(sync_script)]
        if dry_run:
            sync_cmd.append("--check")
        sync_result = subprocess.run(sync_cmd, capture_output=True, text=True, timeout=120)
        say(f"  {sync_result.stdout.strip()}")
    else:
        say("  SKIP: sync script not found")

    # ── Step 6: Audit ──
    say("\n[6/7] Running audit...")
    from .audit import run_audit, summarize

    findings = run_audit(project.name, root=Path.cwd())
    summarize(findings)
    blocking = [f for f in findings if f.severity in ("CRITICAL", "HIGH")]

    # ── Step 7: Opportunity analyzers ──
    say("\n[7/7] Running opportunity analyzers...")
    # OpportunityAnalyzer is disabled and raises on construction; calling it
    # here crashed every cascade before its verdict.
    say("  SKIP: opportunity analyzers are disabled")

    if blocking:
        say(f"  FAIL: {len(blocking)} HIGH/CRITICAL findings")
        for f in blocking:
            say(f"    {f.format()}")
    else:
        info_count = sum(1 for f in findings if f.severity == "INFO")
        say(f"  PASS: {info_count} info-only findings")

    if cascade_result.stale_refs_remaining > 0:
        say(f"\n  WARNING: {cascade_result.stale_refs_remaining} stale era references remain")
        if not dry_run:
            return CascadeOutcome(
                1, cascade_result.files_scanned, cascade_result.stale_refs_remaining
            )
    elif blocking:
        if not dry_run:
            return CascadeOutcome(
                1, cascade_result.files_scanned, cascade_result.stale_refs_remaining
            )
    else:
        say(f"\n  ✓ Pipeline complete. All {cascade_result.files_scanned} deliverables consistent.")
    return CascadeOutcome(0, cascade_result.files_scanned, cascade_result.stale_refs_remaining)


# ── sync ───────────────────────────────────────────────────────────────────────


@dataclass
class SyncOutcome:
    """Exit verdict of a sync run; the transcript went to ``on_line``."""

    exit_code: int = 0


def _resolve_profile_path() -> str:
    """The profile path the sync verb uses: package config first, then cwd."""
    profile_path = os.path.join(os.path.dirname(__file__), "..", "config", "profile.json")
    if not os.path.exists(profile_path):
        profile_path = "config/profile.json"
    return profile_path


def sync(
    target_names: list[str] | tuple[str, ...] | None,
    *,
    skip_mine: bool = False,
    skip_signals: bool = False,
    verbose: bool = False,
    on_line: Callable[..., None] | None = None,
    profile_path: str | None = None,
) -> SyncOutcome:
    """Sync registered projects and aggregate into the global narrative.

    ``on_line`` receives the transcript exactly as the CLI has always
    printed it. ``profile_path`` overrides the default resolution (package
    ``config/profile.json`` first, then ``config/profile.json`` in the
    cwd), which keeps hermetic callers off the developer's real profile.
    """

    def say(text: str, err: bool = False) -> None:
        if on_line:
            on_line(text, err)

    from .analysis_runner import VectorOutcome, classify_vector_outcome, run_analysis_vectors
    from .classifiers.era_detector import detect_signals
    from .extractors.git import extract_git_log, extract_git_log_with_stats

    if profile_path is None:
        profile_path = _resolve_profile_path()
    if not os.path.exists(profile_path):
        say(
            "No profile.json found. Create one at config/profile.json with your project list.",
            err=True,
        )
        return SyncOutcome(1)

    try:
        with open(profile_path, encoding="utf-8") as f:
            profile = json.load(f)
    except json.JSONDecodeError as e:
        say(f"Error: Invalid JSON in {profile_path}: {e}", err=True)
        return SyncOutcome(1)

    registered = profile.get("projects", [])
    sync_cfg = profile.get("sync", {})

    if not registered:
        say("No projects registered in profile.json.")
        return SyncOutcome(0)

    # Filter to requested projects
    if target_names:
        names = set(target_names)
        targets = [p for p in registered if p["name"] in names]
        unknown = names - {p["name"] for p in registered}
        for u in unknown:
            say(f"Unknown project: {u} (not in profile.json)", err=True)
    else:
        targets = registered

    if not targets:
        say("No matching projects to sync.")
        return SyncOutcome(1)

    say(f"Syncing {len(targets)} project(s)...\n")

    # Ensure all project dirs exist
    for proj in targets:
        proj_dir = os.path.join("projects", proj["name"])
        if not os.path.isdir(proj_dir):
            say(f"  Initializing {proj['name']}...")
            os.makedirs(os.path.join(proj_dir, "data"), exist_ok=True)
            os.makedirs(os.path.join(proj_dir, "deliverables"), exist_ok=True)
            config = {
                "name": proj["name"],
                "repo_path": os.path.expanduser(proj["repo_path"]),
                "repo_url": proj.get("repo_url", ""),
                "developer": profile.get("developer", {}),
            }
            with open(os.path.join(proj_dir, "project.json"), "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)

    # Phase 1: Mine each project
    if not skip_mine:
        for proj in targets:
            repo_path = os.path.expanduser(proj["repo_path"])
            if not os.path.isdir(repo_path):
                say(f"  SKIP {proj['name']}: repo not found at {repo_path}", err=True)
                continue
            if not os.path.isdir(os.path.join(repo_path, ".git")):
                say(f"  SKIP {proj['name']}: not a git repo", err=True)
                continue

            say(f"  Mining {proj['name']}...")

            data_dir = os.path.join("projects", proj["name"], "data")
            csv_path = os.path.join(data_dir, "github-commits.csv")
            try:
                count = extract_git_log(repo_path, csv_path, verbose=verbose)
                say(f"    {count} commits extracted")
            except (RuntimeError, Exception) as e:
                say(f"    Error: Git extraction failed: {e}", err=True)
                continue

            stats_path = os.path.join(data_dir, "github-commits-with-stats.txt")
            try:
                extract_git_log_with_stats(repo_path, stats_path, verbose=verbose)
            except (RuntimeError, Exception) as e:
                say(f"    Error: Git stats extraction failed: {e}", err=True)
                continue

    # Phase 1.5: Build DBs
    for proj in targets:
        proj_name = proj["name"]
        db_path = os.path.join("projects", proj_name, "data", "archaeology.db")
        say(f"  Building DB for {proj_name}...")

        cmd = [
            sys.executable,
            "-m",
            "archaeology.db.builder",
            "--project-root",
            os.path.join("projects", proj_name),
        ]
        if verbose:
            cmd.append("--verbose")

        _env = os.environ.copy()
        _pkg_root = str(Path(__file__).parent.parent)
        _env["PYTHONPATH"] = _pkg_root + (
            (os.pathsep + _env["PYTHONPATH"]) if _env.get("PYTHONPATH") else ""
        )
        result = subprocess.run(cmd, capture_output=not verbose, check=True, timeout=300, env=_env)
        if result.returncode == 0 and os.path.exists(db_path):
            say("    DB built")
        else:
            say(f"    DB build failed (exit {result.returncode})", err=True)

    # Phase 2: Detect signals
    should_detect_signals = sync_cfg.get("run_signals", True) and not skip_signals
    if should_detect_signals:
        min_gap = sync_cfg.get("default_min_gap_days", 3)
        for proj in targets:
            say(f"  Detecting signals for {proj['name']}...")
            result = detect_signals(proj["name"], config={"min_gap_days": min_gap})
            sig_count = len(result.get("signals", []))
            cluster_count = len(result.get("cluster_summary", []))
            say(f"    {sig_count} signals, {cluster_count} clusters")

    # Phase 3: Run automated analysis vectors
    run_auto_analysis = sync_cfg.get("run_analysis", True)
    if run_auto_analysis:
        say("\nRunning automated analysis vectors...")
        for proj in targets:
            say(f"  Analyzing {proj['name']}...")
            try:
                results = run_analysis_vectors(proj["name"], verbose=verbose)
                for vector, path in results.items():
                    if classify_vector_outcome(path) is VectorOutcome.WRITTEN:
                        say(f"    ✓ {vector}")
                    else:
                        say(f"    ✗ {vector}: {path}")
            except Exception as e:
                say(f"    Analysis failed: {e}", err=True)

    # Phase 4: Aggregate into global/
    say("\nAggregating global data...")
    _aggregate_global(targets, profile, verbose=verbose, on_line=on_line)
    say("Sync complete.")
    return SyncOutcome(0)


def _aggregate_global(targets, profile, verbose=False, on_line=None):
    """Merge per-project data into global/ for cross-project narrative."""
    import csv
    import sqlite3

    def say(text, err=False):
        if on_line:
            on_line(text, err)

    global_dir = os.path.join("global", "data")
    os.makedirs(global_dir, exist_ok=True)

    all_commits = []
    all_eras = []
    project_summaries = []

    for proj in targets:
        proj_name = proj["name"]
        proj_dir = os.path.join("projects", proj_name)
        db_path = os.path.join(proj_dir, "data", "archaeology.db")

        # Collect commits from CSV (faster than DB)
        csv_path = os.path.join(proj_dir, "data", "github-commits.csv")
        if os.path.exists(csv_path):
            with open(csv_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Normalize: drop None keys from malformed rows
                    clean = {k: v for k, v in row.items() if k is not None}
                    clean["_project"] = proj_name
                    all_commits.append(clean)

        # Collect signals from detected-signals.json
        signals_path = os.path.join(proj_dir, "data", "detected-signals.json")
        if os.path.exists(signals_path):
            try:
                with open(signals_path, encoding="utf-8") as f:
                    proj_signals = json.load(f)
                proj_signals["_project"] = proj_name
                all_eras.append(proj_signals)
            except json.JSONDecodeError as e:
                say(f"Warning: Invalid JSON in {signals_path}: {e}", err=True)
                continue

        # Build per-project summary from DB
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path, timeout=30)
            conn.row_factory = sqlite3.Row
            try:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt, MIN(date) as first, MAX(date) as last FROM commits"
                ).fetchone()
                project_summaries.append(
                    {
                        "name": proj_name,
                        "total_commits": row["cnt"],
                        "first_commit": row["first"],
                        "last_commit": row["last"],
                    }
                )
            except sqlite3.OperationalError:
                project_summaries.append({"name": proj_name, "total_commits": 0})
            finally:
                conn.close()

    # Write global commits CSV
    if all_commits:
        # Collect union of all field names for consistent schema
        all_fields = set()
        for row in all_commits:
            all_fields.update(row.keys())
        fields = sorted(all_fields)
        commit_path = os.path.join(global_dir, "global-commits.csv")
        with open(commit_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(all_commits)
        say(f"  {len(all_commits)} commits across {len(targets)} projects → global-commits.csv")

    # Write global signals JSON
    if all_eras:
        signals_path = os.path.join(global_dir, "global-signals.json")
        with open(signals_path, "w", encoding="utf-8") as f:
            json.dump(all_eras, f, indent=2)
        say(
            f"  {len(all_eras)} signal reports across {len(targets)} projects → global-signals.json"
        )

    # Write project summaries
    summaries_path = os.path.join(global_dir, "project-summaries.json")
    with open(summaries_path, "w", encoding="utf-8") as f:
        json.dump(project_summaries, f, indent=2)
        say(f"  {len(project_summaries)} project summaries → project-summaries.json")

    # Build global DB
    global_db = os.path.join(global_dir, "global.db")
    Path(global_db).unlink(missing_ok=True)

    if all_commits:
        # Use sqlite-utils CLI if available, otherwise sqlite3
        tmp_csv = os.path.join(global_dir, "global-commits.csv")
        try:
            subprocess.run(
                ["sqlite-utils", "insert", global_db, "commits", tmp_csv, "--csv"],
                capture_output=True,
                check=True,
                timeout=300,
            )
        except (FileNotFoundError, subprocess.CalledProcessError):
            conn = sqlite3.connect(global_db, timeout=30)
            try:
                with open(tmp_csv, newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    cols = reader.fieldnames
                    conn.execute(f"CREATE TABLE commits ({', '.join(c + ' TEXT' for c in cols)})")
                    for row in reader:
                        placeholders = ", ".join("?" for _ in cols)
                        conn.execute(
                            f"INSERT INTO commits VALUES ({placeholders})",
                            [row[c] for c in cols],
                        )
                conn.commit()
            finally:
                conn.close()

        say("  Global DB → global.db")
