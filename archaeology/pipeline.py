"""Pipeline service: one place that runs the DevArch pipeline operations.

The click CLI (``archaeology/cli.py``) and the MCP tools
(``archaeology/mcp_server/tools.py``) are thin adapters over this module. It
owns project-directory resolution, input validation and each operation
(init, mine, build-db, signals, analyze, visualize, report, audit and the
mine-to-analyze run). Adapters keep only presentation: click parsing, echo and
exit codes on one side, dict shaping on the other.

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
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator

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
    if not re.fullmatch(r'[a-zA-Z0-9._-]+', name):
        raise ValueError(f"Project name contains invalid characters: {name!r}")

    # Reject path traversal attempts
    if '..' in name:
        raise ValueError(f"Project name cannot contain '..': {name!r}")

    if name.startswith('/'):
        raise ValueError(f"Project name cannot start with '/': {name!r}")

    # "." would resolve to projects/ itself; a leading "-" reads as a CLI flag.
    if name.startswith(('.', '-')):
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
                f"Project '{self.name}' not found", kind="project-missing", path=str(path),
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
    if not os.path.isdir(os.path.join(expanded, ".git")):
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
    from archaeology.extractors.git import extract_git_log, extract_git_log_with_stats

    expanded = require_git_repo(repo_path)
    project_dir = project.resolve()
    data_dir = project_dir / "data"
    source = expanded if expand_repo_path else repo_path

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
        cmd = [sys.executable, "-m", "archaeology.db.builder",
               "--project-root", str(project_dir)]
        if verbose:
            cmd.append("--verbose")
        env = os.environ.copy()
        pkg_root = str(Path(__file__).parent.parent)
        env["PYTHONPATH"] = pkg_root + ((os.pathsep + env["PYTHONPATH"]) if env.get("PYTHONPATH") else "")
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
    project: ProjectRef, *, config: dict | None = None, min_gap_days: int | None = None,
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


def analyze(project: ProjectRef, vectors: list[str] | None = None, *, verbose: bool = False) -> AnalysisResult:
    """Run analysis vectors. The engine itself rejects a missing project or unknown vector."""
    from archaeology.analysis_runner import run_analysis_vectors

    with in_workspace(project):
        results = run_analysis_vectors(project.name, verbose=verbose, vectors=vectors)
    failed = {name: path for name, path in results.items() if str(path).startswith("ERROR")}
    return AnalysisResult(results, failed)


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
            f"Project '{project.name}' not found in discovered projects", kind="not-discovered",
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

    from archaeology.report import _markdown_to_html, export_markdown_report

    md_path = export_markdown_report(project.name, str(project_dir))
    if fmt == "markdown":
        return ReportResult("markdown", md_path)

    title = project.name
    config_path = project_dir / "project.json"
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if config:
            title = config.get("visualization", {}).get("title", project.name)

    html_content = _markdown_to_html(md_path.read_text(encoding="utf-8"), title)
    output_dir = project_dir / "deliverables" / "visuals"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "report.html"
    output_path.write_text(html_content, encoding="utf-8")
    return ReportResult("html", output_path)


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


@dataclass
class PipelineRun:
    """Outcome of init, mine, build-db, signals, analyze run in order."""

    init_created: bool
    mine: MineResult | None = None
    mine_error: str | None = None
    build: BuildResult | None = None
    signal_count: int = 0
    analysis: list | str = field(default_factory=list)
    failed_at: str | None = None


def run_pipeline(repo_path: str, project: ProjectRef) -> PipelineRun:
    """Run the full pipeline, stopping at the first failed mine or build step.

    A missing database for signals counts zero signals, and an analysis
    exception is recorded rather than raised, as the MCP tool always has.
    """
    run = PipelineRun(init_created=init(project, "", "").created)

    try:
        run.mine = mine(repo_path, project)
    except PipelineError as e:
        run.mine_error = e.message
        run.failed_at = "mine"
        return run

    run.build = build_db(project)
    if run.build.error is not None:
        run.failed_at = "build_db"
        return run

    try:
        run.signal_count = len(signals(project).signals)
    except PipelineError:
        run.signal_count = 0

    try:
        run.analysis = list(analyze(project).results.keys())
    except Exception as e:
        run.analysis = f"skipped: {e}"
    return run
