"""Development Archaeology CLI."""

import json
import os

import subprocess
import sys
import tempfile
from pathlib import Path

import click

from .analysis_runner import run_analysis_vectors
from .classifiers.era_detector import detect_signals
from .extractors.git import extract_git_log, extract_git_log_with_stats


def _project_dir(project_name):
    """Resolve project directory path."""
    d = os.path.join("projects", project_name)
    if not os.path.isdir(d):
        click.echo(f"Project '{project_name}' not found at {d}/", err=True)
        click.echo("Run 'archaeology init {project_name}' first.", err=True)
        sys.exit(1)
    return d


@click.group()
def main():
    """Development Archaeology - forensic mining of software development history."""
    pass


@main.command()
@click.argument("project_name")
@click.option("--description", default="Draft archaeology project", help="Human-readable project description")
@click.option("--repo-url", default="https://github.com/example/example", help="GitHub repository URL")
def init(project_name, description, repo_url):
    """Create a new project directory with default config."""
    project_dir = os.path.join("projects", project_name)
    os.makedirs(os.path.join(project_dir, "data"), exist_ok=True)
    os.makedirs(os.path.join(project_dir, "deliverables"), exist_ok=True)

    config_path = os.path.join(project_dir, "project.json")
    if os.path.exists(config_path):
        click.echo(f"Project '{project_name}' already exists at {config_path}")
        return

    config = {
        "name": project_name,
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

    click.echo(f"Created project '{project_name}' at {project_dir}/")


@main.command()
@click.option("--project", "project_name", default="demo-archaeology", help="Demo project name to create")
@click.option("--force", is_flag=True, help="Overwrite an existing demo project")
@click.option("--build-db", is_flag=True, help="Build the demo SQLite database after creating files")
def demo(project_name, force, build_db):
    """Create a sanitized demo archaeology project."""
    from .demo import create_demo_project

    try:
        project_root = create_demo_project(Path.cwd(), project_name=project_name, force=force)
    except FileExistsError as exc:
        click.echo(str(exc), err=True)
        raise click.exceptions.Exit(1)
    click.echo(f"Created sanitized demo project at {project_root}")
    click.echo(f"Try: archaeology build-db {project_name}")
    click.echo(f"Then: archaeology audit {project_name} --fail-on HIGH")
    if build_db:
        cmd = [sys.executable, "-m", "archaeology.db.builder", "--project-root", str(project_root)]
        result = subprocess.run(cmd, check=True, timeout=300)
        if result.returncode != 0:
            raise click.exceptions.Exit(result.returncode)


@main.command()
@click.argument("repo_path")
@click.option("--project", "-p", required=True, help="Project name to extract into")
@click.option("--verbose", "-v", is_flag=True)
def mine(repo_path, project, verbose):
    """Phase 1: Extract data from a git repository."""
    from .extractors.git import extract_git_log, extract_git_log_with_stats

    project_dir = _project_dir(project)
    data_dir = os.path.join(project_dir, "data")

    if not os.path.isdir(os.path.expanduser(repo_path)):
        click.echo(f"Repository not found: {repo_path}", err=True)
        sys.exit(1)

    click.echo(f"Extracting git log from {repo_path}...")

    csv_path = os.path.join(data_dir, "github-commits.csv")
    count = extract_git_log(repo_path, csv_path, verbose=verbose)
    click.echo(f"  Extracted {count} commits to {csv_path}")

    stats_path = os.path.join(data_dir, "github-commits-with-stats.txt")
    extract_git_log_with_stats(repo_path, stats_path, verbose=verbose)

    click.echo(f"Phase 1 complete for '{project}'.")


@main.command()
@click.argument("project_name")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def build_db(project_name, verbose):
    """Phase 1.5: Build SQLite database from extracted data."""
    project_dir = _project_dir(project_name)
    db_path = os.path.join(project_dir, "data", "archaeology.db")

    cmd = [sys.executable, "-m", "archaeology.db.builder",
           "--project-root", project_dir]
    if verbose:
        cmd.append("--verbose")

    result = subprocess.run(cmd, check=True, timeout=300)
    if result.returncode == 0 and os.path.exists(db_path):
        click.echo(f"Database built at {db_path}")
    else:
        click.echo(f"Build failed with exit code {result.returncode}", err=True)
        sys.exit(result.returncode)


@main.command()
@click.argument("project_name")
@click.option("--port", default=8001, help="Port for Datasette server")
@click.option("--unsafe-cors", is_flag=True, help="Enable Datasette CORS headers. Off by default for local data safety.")
def serve(project_name, port, unsafe_cors):
    """Launch Datasette for a project."""
    project_dir = _project_dir(project_name)
    db_path = os.path.join(project_dir, "data", "archaeology.db")

    if not os.path.exists(db_path):
        click.echo(f"Database not found at {db_path}. Run 'archaeology build-db {project_name}' first.")
        sys.exit(1)

    # Load project config for display name
    project_config = {}
    config_path = os.path.join(project_dir, "project.json")
    if os.path.exists(config_path):
        with open(config_path, encoding="utf-8") as f:
            project_config = json.load(f)

    display_name = project_config.get("visualization", {}).get(
        "title", project_name.upper()
    )

    # Use project-specific metadata if it exists, otherwise default
    project_metadata = os.path.join(project_dir, "datasette-metadata.yaml")
    default_metadata = os.path.join("config", "datasette-metadata.yaml")

    metadata_src = None
    if os.path.exists(project_metadata):
        metadata_src = project_metadata
    elif os.path.exists(default_metadata):
        # Create a temp metadata with project name injected
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

    cmd = ["datasette", db_path, "--port", str(port),
           "--setting", "sql_time_limit_ms,5000"]
    if unsafe_cors:
        cmd.append("--cors")
    if metadata_src:
        cmd.extend(["--metadata", metadata_src])

    click.echo(f"Launching Datasette at http://localhost:{port}")
    try:
        subprocess.run(cmd, timeout=300)
    finally:
        if metadata_src and metadata_src.startswith(tempfile.gettempdir()):
            os.unlink(metadata_src)


@main.command()
@click.argument("project_name")
@click.option("--config", "config_path", help="Path to custom config JSON")
@click.option("--min-gap-days", type=int, help="Override min gap days for signal detection")
@click.option("--verbose", "-v", is_flag=True)
def signals(project_name, config_path, min_gap_days, verbose):
    """Phase 2: Detect development signals (gaps, velocity shifts, etc).

    Signals are patterns in the data, NOT era definitions. Eras are
    hand-curated narrative judgments based on these signals.
    """
    from .classifiers.era_detector import detect_signals

    config = {}
    if config_path:
        with open(config_path) as f:
            config = json.load(f)
    if min_gap_days is not None:
        config["min_gap_days"] = min_gap_days

    result = detect_signals(project_name, config=config or None)
    if result.get("signals"):
        click.echo(f"Detected {len(result['signals'])} signals "
                   f"across {len(result['cluster_summary'])} clusters.")
    else:
        click.echo("No signals detected. Build the database first.")


@main.command()
@click.argument("project_name")
@click.option("--sessions-dir", help="Directory containing .jsonl session files")
@click.option("--verbose", "-v", is_flag=True)
def extract_sessions(project_name, sessions_dir, verbose):
    """Extract Claude Code session data."""
    project_dir = _project_dir(project_name)
    output_path = os.path.join(project_dir, "data", "raw-sessions.md")

    cmd = [sys.executable, "-m", "archaeology.extractors.sessions",
           "--output", output_path]
    if sessions_dir:
        cmd.extend(["--sessions-dir", sessions_dir])
    cmd.extend(["--project", project_name])

    result = subprocess.run(cmd, check=True, timeout=300)
    if result.returncode == 0:
        click.echo(f"Sessions extracted to {output_path}")
    else:
        click.echo(f"Session extraction failed", err=True)
        sys.exit(result.returncode)


@main.command()
@click.argument("project_name")
@click.option("--vector", "-v", "vectors", multiple=True,
              help="Run specific analysis vector(s). Repeat for multiple.")
@click.option("--prompts", is_flag=True, help="Show legacy prompt-template instructions instead of running automation")
@click.option("--verbose", is_flag=True, help="Print vector execution detail")
def analyze(project_name, vectors, prompts, verbose):
    """Phase 3: Run automated analysis vectors against project data."""
    from .analysis_runner import AnalysisRunner, run_analysis_vectors

    available = AnalysisRunner.VECTORS
    unknown = set(vectors) - set(available) if vectors else set()
    if unknown:
        for vector in sorted(unknown):
            click.echo(f"Unknown vector: {vector}", err=True)
        raise click.exceptions.Exit(1)

    target = list(vectors) if vectors else list(available)
    project_dir = _project_dir(project_name)
    deliverables_dir = os.path.join(project_dir, "deliverables")
    analysis_dir = os.path.join(deliverables_dir, "analysis")
    os.makedirs(analysis_dir, exist_ok=True)

    if prompts:
        vectors_dir = os.path.join(os.path.dirname(__file__), "..", "analysis-vectors")
        click.echo(f"Analysis prompt templates for '{project_name}'")
        for vec_name in target:
            prompt_path = os.path.join(vectors_dir, f"{vec_name}.md")
            output_path = os.path.join(analysis_dir, f"analysis-{vec_name}.md")
            click.echo(f"  [{vec_name}] prompt={prompt_path} output={output_path}")
        return

    click.echo(f"Running automated analysis vectors for '{project_name}'")
    click.echo(f"Vectors: {', '.join(target)}")
    results = run_analysis_vectors(project_name, verbose=verbose, vectors=target)
    failed = {name: path for name, path in results.items() if str(path).startswith("ERROR")}
    for name, path in results.items():
        click.echo(f"  {name}: {path}")
    if failed:
        raise click.exceptions.Exit(1)


@main.command("public-case-study")
@click.option("--output", "output_dir", default="public-case-study", help="Output directory for the sanitized public case study")
@click.option("--project", "project_name", default="demo-archaeology", help="Temporary/generated sanitized demo project name")
@click.option("--force", is_flag=True, default=True, help="Overwrite existing generated demo project")
def public_case_study(output_dir, project_name, force):
    """Generate a sanitized public case-study showroom."""
    from .report import export_public_case_study

    path = export_public_case_study(Path.cwd(), output_dir=output_dir, project_name=project_name, force=force)
    click.echo(f"Public case study exported to {path}")


@main.command("local-pipeline")
@click.option("--repo", "repo_name", default="dev-archaeology", help="Repository name or owner/name to inspect")
@click.option("--pipeline-dir", default=None, help="Path to the local GITHUB_pipeline workspace (defaults to ARCHAEOLOGY_PIPELINE_ROOT)")
@click.option("--repos-dir", default=None, help="Directory containing local repositories (defaults to ARCHAEOLOGY_REPOS_DIR)")
@click.option("--top-repos", default=20, type=int, help="Number of active repos to review when --run is used")
@click.option("--review-days", default=30, type=int, help="Commit lookback window when --run is used")
@click.option("--run", "run_first", is_flag=True, help="Run the local pipeline before reading latest.json")
@click.option("--fail-on-issues", is_flag=True, help="Exit nonzero if the repo has any local-pipeline findings")
def local_pipeline(repo_name, pipeline_dir, repos_dir, top_repos, review_days, run_first, fail_on_issues):
    """Read or run the local GITHUB_pipeline verification status."""
    from .local_pipeline import read_local_pipeline_status, run_local_pipeline, status_lines

    # Resolve pipeline_dir if not provided
    if pipeline_dir is None:
        pipeline_dir = os.environ.get("ARCHAEOLOGY_PIPELINE_ROOT", "")
        if not pipeline_dir:
            raise click.UsageError(
                "ARCHAEOLOGY_PIPELINE_ROOT environment variable not set. "
                "Please set it to your local GITHUB_pipeline workspace path, "
                "or use --pipeline-dir option."
            )

    if run_first:
        # repos_dir only needed for running the pipeline
        if repos_dir is None:
            repos_dir = os.environ.get("ARCHAEOLOGY_REPOS_DIR", "")
            if not repos_dir:
                raise click.UsageError(
                    "ARCHAEOLOGY_REPOS_DIR environment variable not set. "
                    "Please set it to the directory containing your local repositories, "
                    "or use --repos-dir option."
                )
        run_local_pipeline(pipeline_dir=pipeline_dir, repos_dir=repos_dir, top_repos=top_repos, review_days=review_days)
    status = read_local_pipeline_status(pipeline_dir, repo_name)
    for line in status_lines(status):
        click.echo(line)
    if fail_on_issues and status.issue_total > 0:
        raise click.exceptions.Exit(1)


@main.command("export-report")
@click.argument("project_name")
@click.option("--format", "fmt", type=click.Choice(["markdown", "md", "html"]), default="markdown", help="Report format to export")
@click.option("--output", "output_path", help="Output path. Defaults to project deliverables/ARCHAEOLOGY-REPORT.<ext>")
def export_report_cmd(project_name, fmt, output_path):
    """Export an archaeology report from analysis outputs."""
    from .report import export_report

    project_dir = _project_dir(project_name)
    path = export_report(project_name, project_dir, output_path=output_path, fmt=fmt)
    click.echo(f"Report exported to {path}")


@main.command()
@click.argument("project_name")
def visualize(project_name):
    """Phase 4: Generate visualization HTML from template."""
    project_dir = _project_dir(project_name)
    template = os.path.join("archaeology", "visualization", "template.html")
    data_json = os.path.join(project_dir, "deliverables", "data.json")
    output_html = os.path.join(project_dir, "deliverables", "visuals", "archaeology.html")

    if not os.path.exists(template):
        click.echo(f"Template not found at {template}", err=True)
        sys.exit(1)

    # Load project config for hydration
    config_path = os.path.join(project_dir, "project.json")
    project_config = {}
    if os.path.exists(config_path):
        with open(config_path, encoding="utf-8") as f:
            project_config = json.load(f)

    vis = project_config.get("visualization", {})
    overrides = project_config.get("overrides", {})

    # Read template and inject project-specific values
    with open(template, encoding="utf-8") as f:
        html = f.read()

    # Compute stats from commit-eras.json for template hydration
    total_commits = 0
    total_lines = 0
    first_date = ""
    last_date = ""
    agent_count = 0
    eras_json = os.path.join(project_dir, "data", "commit-eras.json")
    if os.path.exists(eras_json):
        with open(eras_json, encoding="utf-8") as f:
            eras_data = json.load(f)
        total_commits = eras_data.get("total_commits", 0)
        lifespan = eras_data.get("lifespan", "")
        # Parse "43 days (Feb 28 - Apr 11, 2026)" format
        if "(" in lifespan and ")" in lifespan:
            date_part = lifespan.split("(")[1].split(")")[0]
            parts = date_part.split(" - ")
            first_date = parts[0].strip() if parts else ""
            last_date = parts[-1].strip() if len(parts) > 1 else ""
        # Count unique agents from agent_evidence
        agent_evidence = eras_data.get("agent_evidence", {})
        agent_count = len(agent_evidence)
        if not agent_count:
            agent_count = 6  # Claude, Kai, Cursor, Kimi, Codex, dogfood
        # Get file count from codebase_growth last entry
        growth = eras_data.get("codebase_growth", [])
        if growth:
            total_lines = growth[-1].get("files", 0)
    elif os.path.exists(data_json):
        with open(data_json, encoding="utf-8") as f:
            pdata = json.load(f)
        total_commits = pdata.get("total_commits", 0)

    # Hydrate template variables
    title = vis.get("title", project_name.upper())
    duration = vis.get("duration", f"{first_date} — {last_date}" if first_date else "")
    html = html.replace("{{PROJECT_NAME}}", title)
    html = html.replace("{{PROJECT_DURATION}}", duration)
    html = html.replace("{{TOTAL_COMMITS}}", str(total_commits or 803))
    html = html.replace("{{TOTAL_LINES}}", str(total_lines or "35,600"))
    html = html.replace("{{AGENT_COUNT}}", str(agent_count or 6))

    # Also update <title> tag if it still has the old format
    html = html.replace(
        "<title>Development Archaeology</title>",
        f"<title>{title} — Development Archaeology</title>",
    )

    # Generate era color CSS variables from config
    era_colors = vis.get("era_colors", {})
    if era_colors:
        era_css = "\n".join(
            f"  --{era_key}: {color};"
            for era_key, color in era_colors.items()
        )
        # Insert era colors after :root block opens
        html = html.replace(
            "/* ERA COLORS */",
            f"/* ERA COLORS — from project.json */\n{era_css}",
        )

    # Generate agent color CSS variables
    agent_colors = vis.get("agent_colors", {})
    if agent_colors:
        agent_css = "\n".join(
            f"  --{name.lower()}: {color};"
            for name, color in agent_colors.items()
        )
        html = html.replace(
            "/* AGENT COLORS */",
            f"/* AGENT COLORS — from project.json */\n{agent_css}",
        )

    # Inline data.json so the HTML works from file:// (no CORS issues)
    if os.path.exists(data_json):
        with open(data_json, encoding="utf-8") as f:
            data_content = f.read()
        safe_data_content = data_content.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
        inline_script = f'<script>window.PROJECT_DATA = {safe_data_content}; window.dispatchEvent(new Event("data-loaded"));</script>'
        html = html.replace(
            '<script>\n  // Load project data from external JSON file\n  // The data.json file contains all visualization data (telemetry, sessions, eras, etc.)\n  // Original inline data was ~6870 lines (272KB)\n  fetch("data.json")\n    .then(function(r) { return r.json(); })\n    .then(function(d) {\n      window.PROJECT_DATA = d;\n      window.dispatchEvent(new Event("data-loaded"));\n    })\n    .catch(function(e) { console.error("Failed to load data.json:", e); });\n</script>',
            inline_script,
        )

    # Write hydrated HTML
    os.makedirs(os.path.dirname(output_html), exist_ok=True)
    with open(output_html, "w", encoding="utf-8") as f:
        f.write(html)

    click.echo(f"Visualization generated at {output_html}")

    if not os.path.exists(data_json):
        click.echo(f"Warning: {data_json} not found. Visualization will be empty.")


@main.command()
@click.argument("project_name")
@click.option("--logs-dir", help="Path to pipeline logs directory (default: auto-detect)")
@click.option("--verbose", "-v", is_flag=True)
def ingest_pipeline(project_name, logs_dir, verbose):
    """Ingest GITHUB_pipeline run logs into archaeology database.

    Imports pipeline JSON logs from .omc/logs/repo-pipeline/ into
    pipeline_runs and pipeline_repo_results tables for historical tracking.
    """
    from .db.pipeline_ingest import ingest_directory

    project_dir = _project_dir(project_name)
    db_path = os.path.join(project_dir, "data", "archaeology.db")

    if not os.path.exists(db_path):
        click.echo(f"Database not found. Run 'archaeology build-db {project_name}' first.", err=True)
        sys.exit(1)

    # Auto-detect pipeline logs dir
    if not logs_dir:
        candidates = [
            os.path.expanduser("~/Desktop/OMC/.omc/logs/repo-pipeline"),
            os.path.expanduser("~/.claude/data/review"),
            os.path.expanduser("~/dev/GITHUB_pipeline/.omc/logs/repo-pipeline"),
            os.path.expanduser("~/Desktop/GITHUB_pipeline/.omc/logs/repo-pipeline"),
        ]
        for c in candidates:
            if os.path.isdir(c):
                logs_dir = c
                break

    if not logs_dir or not os.path.isdir(logs_dir):
        click.echo("Pipeline logs directory not found. Use --logs-dir to specify path.", err=True)
        sys.exit(1)

    click.echo(f"Ingesting pipeline logs from {logs_dir}...")
    stats = ingest_directory(Path(db_path), Path(logs_dir), verbose=verbose)
    click.echo(f"  Ingested: {stats['ingested']}, Skipped: {stats['skipped']}, Errors: {len(stats['errors'])}")
    for err in stats["errors"]:
        click.echo(f"  ERROR: {err}", err=True)


@main.command()
@click.argument("project_name")
@click.option("--dry-run", is_flag=True, help="Show what would change without writing")
@click.option("--skip-mine", is_flag=True, help="Skip git mining (use existing data)")
def cascade(project_name, dry_run, skip_mine):
    """Full pipeline: mine → build-db → signals → era cascade → sync → audit."""
    from .era_cascade import cascade as run_cascade
    from .extractors.git import extract_git_log, extract_git_log_with_stats
    from .classifiers.era_detector import detect_signals

    project_dir = Path(_project_dir(project_name))
    project_json_path = project_dir / "project.json"
    eras_path = project_dir / "data" / "commit-eras.json"
    data_dir = project_dir / "data"

    # Load project config for repo path
    repo_path = None
    if project_json_path.exists():
        pj = json.loads(project_json_path.read_text())
        repo_path = pj.get("repo_path")
        if repo_path:
            repo_path = os.path.expanduser(repo_path)

    # ── Step 1: Mine fresh git data ──
    if not skip_mine:
        if not repo_path or not os.path.isdir(repo_path):
            click.echo(f"  SKIP: repo_path not found ({repo_path}). Use --skip-mine to skip mining.")
        else:
            click.echo(f"\n[1/6] Mining git data from {repo_path}...")
            csv_path = data_dir / "github-commits.csv"
            count = extract_git_log(repo_path, str(csv_path))
            click.echo(f"  Extracted {count} commits")
            stats_path = data_dir / "github-commits-with-stats.txt"
            extract_git_log_with_stats(repo_path, str(stats_path))
    else:
        click.echo(f"\n[1/6] Mining — SKIPPED (--skip-mine)")

    # ── Step 2: Build database ──
    click.echo(f"\n[2/6] Building database...")
    db_path = data_dir / "archaeology.db"
    cmd = [sys.executable, "-m", "archaeology.db.builder",
           "--project-root", str(project_dir)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode == 0:
        click.echo(f"  Database built ({db_path})")
    else:
        click.echo(f"  Build failed: {result.stderr}", err=True)

    # ── Step 3: Detect signals ──
    click.echo(f"\n[3/6] Detecting signals...")
    sig_result = detect_signals(project_name)
    n_signals = len(sig_result.get("signals", []))
    n_clusters = len(sig_result.get("cluster_summary", []))
    click.echo(f"  {n_signals} signals across {n_clusters} clusters")

    # ── Step 4: Era cascade ──
    click.echo(f"\n[4/6] Running era cascade...")
    if not eras_path.exists():
        click.echo(f"  ERROR: No commit-eras.json found at {eras_path}", err=True)
        sys.exit(1)

    if dry_run:
        click.echo("  (dry run — no files will be written)")

    cascade_result = run_cascade(project_dir, eras_path, dry_run=dry_run)
    click.echo(f"  Files scanned: {cascade_result.files_scanned}")
    click.echo(f"  Files changed: {cascade_result.files_changed}")
    click.echo(f"  Era fields remapped: {cascade_result.era_fields_remapped}")
    click.echo(f"  Stale refs remaining: {cascade_result.stale_refs_remaining}")

    # ── Step 5: Sync derived deliverables ──
    click.echo(f"\n[5/6] Syncing derived deliverables...")
    sync_script = Path(__file__).parent.parent / "scripts" / "sync" / "sync_derived_deliverables.py"
    if sync_script.exists():
        sync_cmd = [sys.executable, str(sync_script)]
        if dry_run:
            sync_cmd.append("--check")
        sync_result = subprocess.run(sync_cmd, capture_output=True, text=True, timeout=120)
        click.echo(f"  {sync_result.stdout.strip()}")
    else:
        click.echo("  SKIP: sync script not found")

    # ── Step 6: Audit ──
    click.echo(f"\n[6/6] Running audit...")
    from .audit import has_blocking_findings, run_audit, summarize
    findings = run_audit(project_name, root=Path.cwd())
    summary = summarize(findings)
    blocking = [f for f in findings if f.severity in ("CRITICAL", "HIGH")]

    if blocking:
        click.echo(f"  FAIL: {len(blocking)} HIGH/CRITICAL findings")
        for f in blocking:
            click.echo(f"    {f.format()}")
    else:
        info_count = sum(1 for f in findings if f.severity == "INFO")
        click.echo(f"  PASS: {info_count} info-only findings")

    if cascade_result.stale_refs_remaining > 0:
        click.echo(f"\n  WARNING: {cascade_result.stale_refs_remaining} stale era references remain")
        if not dry_run:
            raise click.exceptions.Exit(1)
    elif blocking:
        if not dry_run:
            raise click.exceptions.Exit(1)
    else:
        click.echo(f"\n  ✓ Pipeline complete. All {cascade_result.files_scanned} deliverables consistent.")


@main.command()
@click.argument("project_name")
@click.option("--fail-on", type=click.Choice(["CRITICAL", "HIGH", "MEDIUM", "LOW"]), default="HIGH", help="Lowest severity that causes nonzero exit")
def audit(project_name, fail_on):
    """Run forensic audit quality gate."""
    from .audit import has_blocking_findings, run_audit, summarize

    findings = run_audit(project_name, root=Path.cwd())
    summary = summarize(findings)
    click.echo(f"Forensic audit for '{project_name}'")
    click.echo("Summary: " + ", ".join(f"{k}={v}" for k, v in summary.items() if v))
    if not findings:
        click.echo("PASS: no findings")
        return
    for finding in findings:
        click.echo(finding.format())
    if has_blocking_findings(findings, fail_on=fail_on):
        raise click.exceptions.Exit(1)


@main.command()
@click.argument("project_name")
def validate(project_name):
    """Run HTML validation checks."""
    project_dir = _project_dir(project_name)
    html_path = os.path.join(project_dir, "deliverables", "archaeology.html")
    validator = os.path.join("archaeology", "validators", "validate_html.cjs")

    if not os.path.exists(html_path):
        click.echo(f"No archaeology.html found at {html_path}")
        sys.exit(1)

    subprocess.run(["node", validator, html_path, "--project-dir", project_dir], check=True, timeout=120)


def _aggregate_global(targets, profile, verbose=False):
    """Merge per-project data into global/ for cross-project narrative."""
    import csv
    import sqlite3
    from datetime import datetime

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
            with open(signals_path, encoding="utf-8") as f:
                proj_signals = json.load(f)
            proj_signals["_project"] = proj_name
            all_eras.append(proj_signals)

        # Build per-project summary from DB
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path, timeout=30)
            conn.row_factory = sqlite3.Row
            try:
                row = conn.execute(
                    "SELECT COUNT(*) as cnt, MIN(date) as first, MAX(date) as last "
                    "FROM commits"
                ).fetchone()
                project_summaries.append({
                    "name": proj_name,
                    "total_commits": row["cnt"],
                    "first_commit": row["first"],
                    "last_commit": row["last"],
                })
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
        click.echo(f"  {len(all_commits)} commits across {len(targets)} projects → global-commits.csv")

    # Write global signals JSON
    if all_eras:
        signals_path = os.path.join(global_dir, "global-signals.json")
        with open(signals_path, "w", encoding="utf-8") as f:
            json.dump(all_eras, f, indent=2)
        click.echo(f"  {len(all_eras)} signal reports across {len(targets)} projects → global-signals.json")

    # Write project summaries
    summaries_path = os.path.join(global_dir, "project-summaries.json")
    with open(summaries_path, "w", encoding="utf-8") as f:
        json.dump(project_summaries, f, indent=2)
    click.echo(f"  {len(project_summaries)} project summaries → project-summaries.json")

    # Build global DB
    global_db = os.path.join(global_dir, "global.db")
    Path(global_db).unlink(missing_ok=True)

    if all_commits:
        # Use sqlite-utils CLI if available, otherwise sqlite3
        tmp_csv = os.path.join(global_dir, "global-commits.csv")
        try:
            subprocess.run(
                ["sqlite-utils", "insert", global_db, "commits", tmp_csv, "--csv"],
                capture_output=True, check=True, timeout=300,
            )
        except (FileNotFoundError, subprocess.CalledProcessError):
            conn = sqlite3.connect(global_db, timeout=30)
            try:
                with open(tmp_csv, newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    cols = reader.fieldnames
                    conn.execute(
                        f"CREATE TABLE commits ({', '.join(c + ' TEXT' for c in cols)})"
                    )
                    for row in reader:
                        placeholders = ", ".join("?" for _ in cols)
                        conn.execute(
                            f"INSERT INTO commits VALUES ({placeholders})",
                            [row[c] for c in cols],
                        )
                conn.commit()
            finally:
                conn.close()

        click.echo(f"  Global DB → global.db")


@main.command()
@click.option("--project", "-p", "projects", multiple=True,
              help="Sync specific project(s) only. Defaults to all in profile.json.")
@click.option("--skip-mine", is_flag=True, help="Skip git extraction (use cached data)")
@click.option("--skip-signals", is_flag=True, help="Skip signal detection")
@click.option("--verbose", "-v", is_flag=True)
def sync(projects, skip_mine, skip_signals, verbose):
    """Sync registered projects and aggregate into global narrative."""
    profile_path = os.path.join(os.path.dirname(__file__), "..", "config", "profile.json")
    if not os.path.exists(profile_path):
        profile_path = "config/profile.json"
    if not os.path.exists(profile_path):
        click.echo("No profile.json found. Create one at config/profile.json with your project list.", err=True)
        sys.exit(1)

    with open(profile_path, encoding="utf-8") as f:
        profile = json.load(f)

    registered = profile.get("projects", [])
    sync_cfg = profile.get("sync", {})

    if not registered:
        click.echo("No projects registered in profile.json.")
        sys.exit(0)

    # Filter to requested projects
    if projects:
        names = set(projects)
        targets = [p for p in registered if p["name"] in names]
        unknown = names - {p["name"] for p in registered}
        for u in unknown:
            click.echo(f"Unknown project: {u} (not in profile.json)", err=True)
    else:
        targets = registered

    if not targets:
        click.echo("No matching projects to sync.")
        sys.exit(1)

    click.echo(f"Syncing {len(targets)} project(s)...\n")

    # Ensure all project dirs exist
    for proj in targets:
        proj_dir = os.path.join("projects", proj["name"])
        if not os.path.isdir(proj_dir):
            click.echo(f"  Initializing {proj['name']}...")
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
                click.echo(f"  SKIP {proj['name']}: repo not found at {repo_path}", err=True)
                continue
            if not os.path.isdir(os.path.join(repo_path, ".git")):
                click.echo(f"  SKIP {proj['name']}: not a git repo", err=True)
                continue

            click.echo(f"  Mining {proj['name']}...")

            data_dir = os.path.join("projects", proj["name"], "data")
            csv_path = os.path.join(data_dir, "github-commits.csv")
            count = extract_git_log(repo_path, csv_path, verbose=verbose)
            click.echo(f"    {count} commits extracted")

            stats_path = os.path.join(data_dir, "github-commits-with-stats.txt")
            extract_git_log_with_stats(repo_path, stats_path, verbose=verbose)

    # Phase 1.5: Build DBs
    for proj in targets:
        proj_name = proj["name"]
        db_path = os.path.join("projects", proj_name, "data", "archaeology.db")
        click.echo(f"  Building DB for {proj_name}...")

        cmd = [sys.executable, "-m", "archaeology.db.builder",
               "--project-root", os.path.join("projects", proj_name)]
        if verbose:
            cmd.append("--verbose")

        result = subprocess.run(cmd, capture_output=not verbose, check=True, timeout=300)
        if result.returncode == 0 and os.path.exists(db_path):
            click.echo(f"    DB built")
        else:
            click.echo(f"    DB build failed (exit {result.returncode})", err=True)

    # Phase 2: Detect signals
    should_detect_signals = sync_cfg.get("run_signals", True) and not skip_signals
    if should_detect_signals:
        min_gap = sync_cfg.get("default_min_gap_days", 3)
        for proj in targets:
            click.echo(f"  Detecting signals for {proj['name']}...")
            result = detect_signals(proj["name"], config={"min_gap_days": min_gap})
            sig_count = len(result.get("signals", []))
            cluster_count = len(result.get("cluster_summary", []))
            click.echo(f"    {sig_count} signals, {cluster_count} clusters")

    # Phase 3: Run automated analysis vectors
    run_auto_analysis = sync_cfg.get("run_analysis", True)
    if run_auto_analysis:
        click.echo("\nRunning automated analysis vectors...")
        for proj in targets:
            click.echo(f"  Analyzing {proj['name']}...")
            try:
                results = run_analysis_vectors(proj["name"], verbose=verbose)
                for vector, path in results.items():
                    if not path.startswith("ERROR"):
                        click.echo(f"    ✓ {vector}")
                    else:
                        click.echo(f"    ✗ {vector}: {path}")
            except Exception as e:
                click.echo(f"    Analysis failed: {e}", err=True)

    # Phase 4: Aggregate into global/
    click.echo("\nAggregating global data...")
    _aggregate_global(targets, profile, verbose)
    click.echo("Sync complete.")


@main.command("global-viz")
@click.option("--output", "output_dir", default="global/deliverables", help="Output directory for the global visualization")
@click.option("--top", "top_n", type=int, help="Limit to top N repos by commit count")
@click.option("--year", type=int, help="Only include repos updated in this year")
@click.option("--verbose", "-v", is_flag=True)
def global_viz(output_dir, top_n, year, verbose):
    """Generate cross-repo visualization from synced global data."""
    from .visualization.global_data_builder import prepare_global_visualization_data

    global_dir = "global"
    data_dir = os.path.join(global_dir, "data")
    github_json = os.path.join(data_dir, "github-repos.json")
    commits_csv = os.path.join(data_dir, "global-commits.csv")

    if not os.path.exists(commits_csv) and not os.path.exists(github_json):
        click.echo("No global data found. Run 'archaeology fetch-github' or 'archaeology sync' first.", err=True)
        sys.exit(1)

    # Build visualization data
    click.echo("Building global visualization data...")
    viz_data = prepare_global_visualization_data(global_dir, top_n=top_n, year=year)

    # Write viz data JSON
    viz_json_path = os.path.join(data_dir, "global-viz-data.json")
    with open(viz_json_path, "w") as f:
        json.dump(viz_data, f, indent=2)
    click.echo(f"  Data written to {viz_json_path}")

    # Hydrate template
    template_path = os.path.join("archaeology", "visualization", "global-template.html")
    if not os.path.exists(template_path):
        click.echo(f"Template not found at {template_path}", err=True)
        sys.exit(1)

    with open(template_path, encoding="utf-8") as f:
        html = f.read()

    # Inline the data JSON
    safe_data = json.dumps(viz_data).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")

    # Replace the placeholder lines inside the script block
    # Template has: "// GLOBAL_DATA_PLACEHOLDER\nwindow.GLOBAL_DATA = {};"
    old_placeholder = "// GLOBAL_DATA_PLACEHOLDER\nwindow.GLOBAL_DATA = {};"
    new_inline = f"window.GLOBAL_DATA = {safe_data};\n  window.dispatchEvent(new Event('global-data-loaded'));"
    if old_placeholder in html:
        html = html.replace(old_placeholder, new_inline)
    elif "window.GLOBAL_DATA = {};" in html:
        html = html.replace("window.GLOBAL_DATA = {};", f"window.GLOBAL_DATA = {safe_data};")
    else:
        click.echo("Warning: could not find GLOBAL_DATA placeholder in template", err=True)

    # Write output
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "global.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    click.echo(f"Global visualization generated at {output_path}")
    meta = viz_data.get("meta", {})
    click.echo(f"  {meta.get('total_commits', '?')} commits across {meta.get('total_repos', '?')} repos")


@main.command("fetch-github")
@click.option("--owner", default="Pastorsimon1798", help="GitHub username/org")
@click.option("--output", "output_path", default="global/data/github-repos.json", help="Output JSON path")
def fetch_github(owner, output_path):
    """Fetch repo metadata from GitHub API for all repos (no cloning)."""
    from .visualization.github_fetcher import save_github_data

    click.echo(f"Fetching repos for {owner} from GitHub...")
    data = save_github_data(output_path, owner=owner)
    click.echo(f"  {data['total_repos']} repos, {data['total_commits']} total commits")


@main.command()
@click.argument("project_name")
def benchmark(project_name):
    """Generate agent performance benchmark visualization."""
    from .visualization.agent_benchmark import run_benchmark_analysis

    project_dir = _project_dir(project_name)

    click.echo(f"Analyzing agent performance for '{project_name}'...")

    try:
        output_path = run_benchmark_analysis(project_dir)
        click.echo(f"Benchmark visualization generated at {output_path}")
    except FileNotFoundError as e:
        click.echo(str(e), err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error generating benchmark: {e}", err=True)
        sys.exit(1)


@main.command("multi-project-dashboard")
@click.option("--output", "output_dir", default="global/deliverables", help="Output directory for the dashboard")
@click.option("--top", "top_n", type=int, help="Limit to top N repos by commit count")
@click.option("--year", type=int, help="Only include repos updated in this year")
@click.option("--verbose", "-v", is_flag=True)
def multi_project_dashboard(output_dir, top_n, year, verbose):
    """Generate comprehensive multi-project dashboard visualization."""
    from .visualization.global_data_builder import prepare_dashboard_data

    global_dir = "global"
    data_dir = os.path.join(global_dir, "data")
    github_json = os.path.join(data_dir, "github-repos.json")

    if not os.path.exists(github_json):
        click.echo("No GitHub data found. Run 'archaeology fetch-github' first.", err=True)
        sys.exit(1)

    click.echo("Building dashboard data...")
    dashboard_data = prepare_dashboard_data(global_dir, top_n=top_n, year=year)

    dashboard_json_path = os.path.join(data_dir, "dashboard-data.json")
    with open(dashboard_json_path, "w") as f:
        json.dump(dashboard_data, f, indent=2)
    if verbose:
        click.echo(f"  Data written to {dashboard_json_path}")

    template_path = os.path.join("archaeology", "visualization", "multi-project-dashboard.html")
    if not os.path.exists(template_path):
        click.echo(f"Template not found at {template_path}", err=True)
        sys.exit(1)

    with open(template_path, encoding="utf-8") as f:
        html = f.read()

    safe_data = json.dumps(dashboard_data).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")

    old_placeholder = "// DATA_PLACEHOLDER\nwindow.DASHBOARD_DATA = {};"
    new_inline = f"window.DASHBOARD_DATA = {safe_data};\n  window.dispatchEvent(new Event('dashboard-data-loaded'));"
    if old_placeholder in html:
        html = html.replace(old_placeholder, new_inline)
    elif "window.DASHBOARD_DATA = {};" in html:
        html = html.replace("window.DASHBOARD_DATA = {};", f"window.DASHBOARD_DATA = {safe_data};")
    else:
        click.echo("Warning: could not find DASHBOARD_DATA placeholder in template", err=True)

    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "dashboard.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    click.echo(f"Multi-project dashboard generated at {output_path}")
    meta = dashboard_data.get("meta", {})
    click.echo(f"  {meta.get('total_commits', '?')} commits across {meta.get('total_repos', '?')} repos")


@main.command()
@click.option("--port", default=8080, help="Port to serve on")
@click.option("--no-open", is_flag=True, help="Don't open browser automatically")
def serve(port, no_open):
    """Start local dashboard server for all project deliverables.

    Generates the master dashboard and serves all projects over HTTP.
    Accessible from any device on your Tailscale network.
    """
    import functools
    import http.server
    import threading
    import webbrowser

    from .visualization.dashboard import (
        discover_projects,
        generate_global_section,
        generate_master_dashboard,
        generate_project_index,
        load_api_repos,
    )

    root = Path.cwd()
    projects_dir = root / "projects"

    # Generate master dashboard
    projects = discover_projects(projects_dir)
    if not projects:
        click.echo("No projects found. Run 'archaeology mine <repo>' first.", err=True)
        sys.exit(1)

    # Load API repos and deduplicate against mined projects
    global_data_dir = root / "global" / "data"
    api_repos = load_api_repos(global_data_dir) if global_data_dir.exists() else []
    mined_names = {p["name"].lower().replace("-", "").replace("_", "") for p in projects}
    api_repos = [r for r in api_repos if r["name"].lower().replace("-", "").replace("_", "") not in mined_names]
    print(f"  After dedup: {len(api_repos)} API-only repos")

    api_section_html = generate_global_section(api_repos)
    dashboard_html = generate_master_dashboard(projects, api_section_html=api_section_html, api_repos=api_repos)

    # Write master dashboard to a temp location that the server will serve
    site_dir = root / ".serve"
    site_dir.mkdir(exist_ok=True)
    (site_dir / "index.html").write_text(dashboard_html, encoding="utf-8")

    # Symlink global deliverables (multi-project dashboard, network graph)
    global_deliverables = root / "global" / "deliverables"
    if global_deliverables.exists():
        for html_file in global_deliverables.glob("*.html"):
            link_path = site_dir / html_file.name
            if link_path.is_symlink() or link_path.exists():
                link_path.unlink()
            link_path.symlink_to(html_file.resolve())

    # Generate per-project index pages and symlink/copy HTML files
    for proj in projects:
        proj_site_dir = site_dir / proj["name"]
        proj_site_dir.mkdir(exist_ok=True)

        # Generate project index page
        proj_index_html = generate_project_index(proj)
        (proj_site_dir / "index.html").write_text(proj_index_html, encoding="utf-8")

        # Symlink HTML files from deliverables
        deliverables_dir = projects_dir / proj["name"] / "deliverables"
        visuals_dir = deliverables_dir / "visuals"
        source_dir = visuals_dir if visuals_dir.exists() else deliverables_dir

        for html_file in source_dir.glob("*.html"):
            link_path = proj_site_dir / html_file.name
            # Remove old symlink if exists
            if link_path.is_symlink():
                link_path.unlink()
            elif link_path.exists():
                link_path.unlink()
            link_path.symlink_to(html_file.resolve())

        # Symlink data.json if it exists (needed by HTML visualizations)
        data_json = deliverables_dir / "data.json"
        if data_json.exists():
            link_path = proj_site_dir / "data.json"
            if link_path.is_symlink():
                link_path.unlink()
            elif link_path.exists():
                link_path.unlink()
            link_path.symlink_to(data_json.resolve())

    click.echo(f"  Master dashboard: {len(projects)} projects")
    total_html = sum(len(p["visuals"]) for p in projects)
    click.echo(f"  Total visualizations: {total_html}")

    # Custom handler to serve from site_dir
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(site_dir))

    server = http.server.HTTPServer(("0.0.0.0", port), handler)
    url = f"http://localhost:{port}"

    click.echo(f"\n  Serving at {url}")
    click.echo(f"  Tailscale: http://100.115.175.18:{port}")
    click.echo(f"  Press Ctrl+C to stop\n")

    if not no_open:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        click.echo("\n  Server stopped.")
        server.server_close()


@main.command("publish-static")
@click.option("--output", "output_dir", default="site", help="Output directory for the static site")
def publish_static(output_dir):
    """Generate a static site for deployment (GitHub Pages, nginx, etc.)."""
    import shutil

    from .visualization.dashboard import (
        discover_projects,
        generate_global_section,
        generate_master_dashboard,
        generate_project_index,
        load_api_repos,
    )

    root = Path.cwd()
    projects_dir = root / "projects"
    site = root / output_dir

    # Clean output directory
    if site.exists():
        shutil.rmtree(site)
    site.mkdir(parents=True)

    # Generate master dashboard
    projects = discover_projects(projects_dir)
    if not projects:
        click.echo("No projects found.", err=True)
        sys.exit(1)

    # Load API repos and deduplicate
    global_data_dir = root / "global" / "data"
    api_repos = load_api_repos(global_data_dir) if global_data_dir.exists() else []
    mined_names = {p["name"].lower().replace("-", "").replace("_", "") for p in projects}
    api_repos = [r for r in api_repos if r["name"].lower().replace("-", "").replace("_", "") not in mined_names]

    api_section_html = generate_global_section(api_repos)
    dashboard_html = generate_master_dashboard(projects, api_section_html=api_section_html, api_repos=api_repos)
    (site / "index.html").write_text(dashboard_html, encoding="utf-8")

    click.echo(f"  Master dashboard: {len(projects)} projects")

    # Copy global deliverables
    global_deliverables = root / "global" / "deliverables"
    if global_deliverables.exists():
        for html_file in global_deliverables.glob("*.html"):
            shutil.copy2(html_file, site / html_file.name)

    # Generate per-project pages
    for proj in projects:
        proj_site_dir = site / proj["name"]
        proj_site_dir.mkdir()

        # Project index
        proj_index_html = generate_project_index(proj)
        (proj_site_dir / "index.html").write_text(proj_index_html, encoding="utf-8")

        # Copy HTML files from deliverables
        deliverables_dir = projects_dir / proj["name"] / "deliverables"
        visuals_dir = deliverables_dir / "visuals"
        source_dir = visuals_dir if visuals_dir.exists() else deliverables_dir

        for html_file in source_dir.glob("*.html"):
            shutil.copy2(html_file, proj_site_dir / html_file.name)

        # Copy data.json
        data_json = deliverables_dir / "data.json"
        if data_json.exists():
            shutil.copy2(data_json, proj_site_dir / "data.json")

        click.echo(f"  {proj['name']}: {len(proj['visuals'])} pages")

    total = sum(len(p["visuals"]) for p in projects) + len(projects) + 1
    click.echo(f"\n  Static site generated at {site}/ ({total} pages)")
    click.echo(f"  Deploy with: rsync -avz {site}/ user@host:/var/www/archaeology/")


if __name__ == "__main__":
    main()
