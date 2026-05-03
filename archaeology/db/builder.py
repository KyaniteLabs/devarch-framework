#!/usr/bin/env python3
"""Convert archaeology data files into a SQLite database for Datasette exploration.

Project-agnostic: point --project <name> or --project-root <path> at any project
directory with a data/ folder and this script auto-detects CSV and JSON files,
flattens nested structures into separate tables, creates indexes, and enables
FTS5 for full-text search.

Table registry is loaded from:
  1. <project-root>/project.json -> "db_tables" key
  2. config/defaults.json -> "db_tables" key (relative to script location)
  3. DEFAULT_TABLE_REGISTRY constant (hardcoded fallback)

Requires: sqlite-utils CLI on PATH.
"""

import argparse
import csv
import json
import re
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

from ..utils import _script_dir


# ---------------------------------------------------------------------------
# Default table registry (fallback when no project.json or defaults.json)
# ---------------------------------------------------------------------------

DEFAULT_TABLE_REGISTRY: dict[str, dict] = {
    "commits": {"file": "github-commits.csv", "format": "csv"},
    "sessions": {"file": "human-messages.json", "format": "json_array"},
    "youtube_searches": {"file": "youtube-search-history.json", "format": "json_array"},
    "eras": {"file": "commit-eras.json", "format": "json_special"},
    "derived_patterns": {"file": "derived-patterns.json", "format": "json_special"},
    "cross_repo_analysis": {"file": "cross-repo-analysis.json", "format": "json_nested"},
    "model_adoption": {"file": "model-adoption-analysis.json", "format": "json_nested"},
    "lunar_phases": {"file": "lunar-phases.json", "format": "json_nested"},
    "youtube_correlation": {"file": "youtube-ai-correlation.json", "format": "json_nested"},
    "youtube_creators": {"file": "youtube-creators.json", "format": "json_special_creators"},
    "telemetry_git": {"file": "telemetry-git.json", "format": "json_nested"},
    "telemetry_agents": {"file": "telemetry-agents.json", "format": "json_nested"},
    "telemetry_codebase": {"file": "telemetry-codebase.json", "format": "json_nested"},
    "telemetry_cross_repo": {"file": "telemetry-cross-repo.json", "format": "json_nested"},
    "telemetry_github_full": {"file": "telemetry-github-full.json", "format": "json_nested"},
    "telemetry_repo_depth": {"file": "telemetry-repo-depth.json", "format": "json_nested"},
    "telemetry_visualizations": {"file": "telemetry-visualizations.json", "format": "json_nested"},
    "youtube_topic_classification": {"file": "youtube-topic-classification.json", "format": "json_nested"},
    "youtube_engagement": {"file": "youtube-engagement-heuristics.json", "format": "json"},
    "youtube_transcript_analysis": {"file": "youtube-transcript-analysis.json", "format": "json"},
    "context_management": {"file": "context-management-analysis.json", "format": "json"},
}

# Nested key-to-table mappings for json_nested format files.
# Keys within each JSON file that should be extracted into separate tables.
NESTED_KEY_MAPPINGS: dict[str, dict[str, str]] = {
    "cross-repo-analysis.json": {
        "monthly_velocity": "monthly_velocity",
        "top_repos": "repos",
        "hourly_pattern": "hourly_activity",
        "day_of_week": "weekly_activity",
        "language_evolution": "languages",
    },
    "model-adoption-analysis.json": {
        "model_releases": "model_releases",
        "first_mentions": "model_mentions",
        "adoption_lag": "adoption_lag",
        "timeline": "model_timeline",
    },
    "lunar-phases.json": {"daily_phases": "lunar_phases", "key_events": "lunar_events"},
    "youtube-ai-correlation.json": {
        "monthly_summary": "yt_monthly",
        "key_correlations": "yt_correlations",
        "creator_influence_map": "yt_creator_influence",
    },
    "youtube-topic-classification.json": {
        "classified_videos": "yt_classified",
        "categories": "yt_categories",
    },
    "telemetry-git.json": {
        "commits_by_hour": "commits_by_hour",
        "commits_by_day_of_week": "commits_by_weekday",
        "author_breakdown": "authors",
        "co_authored_by": "co_authors",
    },
    "telemetry-agents.json": {
        "agent_comparison": "agent_comparison",
        "co_authorship_patterns": "co_authorship_patterns",
    },
    "telemetry-codebase.json": {
        "file_growth_timeline": "file_growth",
        "language_evolution": "codebase_languages",
        "module_emergence_timeline": "module_emergence",
    },
    "telemetry-cross-repo.json": {
        "timeline": "cross_repo_timeline",
        "concurrent_repos": "concurrent_repos",
    },
    "telemetry-github-full.json": {
        "repos": "github_repos",
        "activity_heatmap": "github_heatmap",
    },
    "telemetry-repo-depth.json": {
        "repos": "repo_depth",
        "domain_map": "domain_map",
        "feeder_repos": "feeder_repos",
    },
}

# Default indexes to create (table -> list of columns).
DEFAULT_INDEXES: list[tuple[str, list[str]]] = [
    ("commits", ["date", "author", "repo"]),
    ("eras", ["name", "frustration_category", "dominant_intent"]),
    ("sessions", ["timestamp", "session_id"]),
    ("yt_classified", ["category"]),
    ("lunar_phases", ["date"]),
]

# Default FTS configurations (table -> columns to index).
DEFAULT_FTS: list[tuple[str, list[str]]] = [
    ("commits", ["message"]),
    ("sessions", ["messages"]),
    ("eras", ["description", "narrative_arc"]),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def log(msg: str, verbose: bool = False) -> None:
    if verbose:
        print(f"  {msg}")


def run_su(args: list[str], verbose: bool = False) -> subprocess.CompletedProcess:
    """Call sqlite-utils CLI and return the result."""
    cmd = [sys.executable, "-m", "sqlite_utils"] + args
    if verbose:
        print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  WARNING: sqlite-utils error: {result.stderr.strip()}", file=sys.stderr)
    return result


def load_json(path: Path, verbose: bool = False) -> dict | list | None:
    if not path.exists():
        log(f"SKIP {path.name} (not found)", verbose)
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        log(f"LOADED {path.name}", verbose)
        return data
    except (json.JSONDecodeError, OSError) as exc:
        print(f"  WARNING: Failed to read {path}: {exc}", file=sys.stderr)
        return None


def import_csv(db: Path, table: str, csv_path: Path, verbose: bool = False) -> int:
    if not csv_path.exists():
        log(f"SKIP {csv_path.name} (not found)", verbose)
        return 0
    # Count rows during initial read to avoid re-reading the file
    with open(csv_path, encoding="utf-8") as f:
        count = sum(1 for _ in csv.reader(f)) - 1
    run_su(["insert", str(db), table, str(csv_path), "--csv", "--alter"], verbose)
    log(f"IMPORTED {csv_path.name} -> {table} ({count} rows)", verbose)
    return max(count, 0)


def write_temp(records: list[dict]) -> Path:
    tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8")
    json.dump(records, tmp, default=str)
    tmp.close()
    return Path(tmp.name)


def import_list(db: Path, table: str, records: list[dict], verbose: bool = False) -> int:
    if not records:
        log(f"SKIP {table} (empty)", verbose)
        return 0
    tmp = write_temp(records)
    try:
        run_su(["insert", str(db), table, str(tmp), "--alter"], verbose)
        log(f"IMPORTED {table} ({len(records)} rows)", verbose)
    finally:
        tmp.unlink(missing_ok=True)
    return len(records)


def extract_nested(data: dict, key: str) -> list[dict] | None:
    value = data.get(key)
    if value is None:
        return None
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return [{"_key": k, **(v if isinstance(v, dict) else {"value": v})} for k, v in value.items()]
    return None


def flatten_dict(data: dict, prefix: str = "") -> dict:
    flat: dict = {}
    for k, v in data.items():
        key = f"{prefix}_{k}" if prefix else k
        flat[key] = json.dumps(v, default=str) if isinstance(v, (dict, list)) else v
    return flat


def _flat(records: list) -> list[dict]:
    return [flatten_dict(r) if isinstance(r, dict) else {"value": r} for r in records]


def _import_mapping(db: Path, data: dict, mapping: dict[str, str], verbose: bool = False) -> int:
    total = 0
    for key, table in mapping.items():
        records = extract_nested(data, key)
        if records:
            total += import_list(db, table, _flat(records), verbose)
    return total


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def load_table_registry(project_root: Path, verbose: bool = False) -> dict[str, dict]:
    """Load table registry from project.json, then defaults.json, then fallback.

    Priority:
      1. <project-root>/project.json -> "db_tables"
      2. <script_dir>/../../config/defaults.json -> "db_tables"
      3. DEFAULT_TABLE_REGISTRY constant
    """
    # Try project.json first
    project_json = project_root / "project.json"
    if project_json.exists():
        try:
            with open(project_json, encoding="utf-8") as f:
                data = json.load(f)
            tables = data.get("db_tables")
            if tables:
                log(f"Loaded table registry from project.json ({len(tables)} tables)", verbose)
                return tables
        except (json.JSONDecodeError, OSError) as exc:
            print(f"  WARNING: Failed to read {project_json}: {exc}", file=sys.stderr)

    # Try defaults.json
    defaults_json = _script_dir().parent.parent / "config" / "defaults.json"
    if defaults_json.exists():
        try:
            with open(defaults_json, encoding="utf-8") as f:
                data = json.load(f)
            tables = data.get("db_tables")
            if tables:
                log(f"Loaded table registry from defaults.json ({len(tables)} tables)", verbose)
                return tables
        except (json.JSONDecodeError, OSError) as exc:
            print(f"  WARNING: Failed to read {defaults_json}: {exc}", file=sys.stderr)

    # Fallback to hardcoded defaults
    log(f"Using DEFAULT_TABLE_REGISTRY ({len(DEFAULT_TABLE_REGISTRY)} tables)", verbose)
    return DEFAULT_TABLE_REGISTRY.copy()


def load_nested_key_mappings(project_root: Path, verbose: bool = False) -> dict[str, dict[str, str]]:
    """Load nested key-to-table mappings from project config.

    Priority:
      1. <project-root>/project.json -> "nested_key_mappings"
      2. NESTED_KEY_MAPPINGS constant
    """
    project_json = project_root / "project.json"
    if project_json.exists():
        try:
            with open(project_json, encoding="utf-8") as f:
                data = json.load(f)
            mappings = data.get("nested_key_mappings")
            if mappings:
                log(f"Loaded nested mappings from project.json ({len(mappings)} files)", verbose)
                return mappings
        except (json.JSONDecodeError, OSError):
            pass
    return NESTED_KEY_MAPPINGS.copy()


def resolve_project_root(args: argparse.Namespace) -> Path:
    """Resolve the project root directory from CLI arguments.

    Accepts either --project <name> (resolves to projects/<name>/) or
    --project-root <path> (direct path).
    """
    repo_root = _script_dir().parent.parent

    if args.project:
        project_path = repo_root / "projects" / args.project
        if not project_path.exists():
            print(f"ERROR: Project directory not found: {project_path}", file=sys.stderr)
            sys.exit(1)
        return project_path.resolve()

    return Path(args.project_root).resolve()


# ---------------------------------------------------------------------------
# Specialized importers
# ---------------------------------------------------------------------------

def import_commit_eras(db: Path, data_dir: Path, era_file: str = "commit-eras.json", verbose: bool = False) -> int:
    data = load_json(data_dir / era_file, verbose)
    if data is None:
        return 0
    total = import_list(db, "eras", _flat(data.get("eras", [])), verbose)
    meta_keys = [k for k in data if k != "eras"]
    if meta_keys:
        meta = [{"key": k, "value": json.dumps(data[k], default=str)} for k in meta_keys]
        total += import_list(db, "project_meta", meta, verbose)
    return total


def import_derived_patterns(db: Path, data_dir: Path, patterns_file: str = "derived-patterns.json", verbose: bool = False) -> int:
    data = load_json(data_dir / patterns_file, verbose)
    if data is None:
        return 0
    total = 0
    named = {"frustration_to_automation_latency": "frustration_patterns", "co_authorship_gap_analysis": "co_authorship_gaps"}
    for key, table in named.items():
        section = data.get(key)
        if section is None:
            continue
        if isinstance(section, dict):
            for sub_val in section.values():
                if isinstance(sub_val, list) and sub_val:
                    total += import_list(db, table, _flat(sub_val), verbose)
                    break
        elif isinstance(section, list):
            total += import_list(db, table, section, verbose)
    for key, val in data.items():
        if key not in named and isinstance(val, list) and val:
            total += import_list(db, key.replace("-", "_")[:60], val, verbose)
    return total


def import_telemetry_sessions(db: Path, data_dir: Path, sessions_file: str = "telemetry-sessions.json", verbose: bool = False) -> int:
    data = load_json(data_dir / sessions_file, verbose)
    if data is None:
        return 0
    total = import_list(db, "sessions_per_era", data.get("sessions_per_era", []), verbose)
    for key in ("frustration_analysis", "intent_analysis"):
        section = data.get(key)
        if isinstance(section, dict):
            rows = [flatten_dict({k: v}) for k, v in section.items()]
            total += import_list(db, key, rows, verbose)
        elif isinstance(section, list):
            total += import_list(db, key, section, verbose)
    return total


def import_audit_files(db: Path, data_dir: Path, verbose: bool = False) -> int:
    total = 0
    for path in sorted(data_dir.glob("audit-*.json")):
        table = path.stem.replace("-", "_")
        data = load_json(path, verbose)
        if data is None:
            continue
        if isinstance(data, list):
            total += import_list(db, table, data, verbose)
        elif isinstance(data, dict):
            rows = []
            for k, v in data.items():
                if isinstance(v, list) and v:
                    rows.extend(_flat(v))
                else:
                    rows.append({"key": k, "value": json.dumps(v, default=str)})
            total += import_list(db, table, rows, verbose)
    return total


# ---------------------------------------------------------------------------
# Registry-driven import (generalized)
# ---------------------------------------------------------------------------

def import_from_registry(db: Path, data_dir: Path, registry: dict[str, dict],
                         nested_mappings: dict[str, dict[str, str]],
                         verbose: bool = False) -> int:
    """Import all tables defined in the registry.

    Format handling:
      - csv: import via CSV
      - json_array: top-level JSON array -> single table
      - json_special: specialized importer (eras, derived_patterns, etc.)
      - json_special_creators: youtube-creators specific handling
      - json_nested: use nested_key_mappings to extract sub-tables
      - json: generic dict -> flatten and import
    """
    total = 0
    for table_name, entry in registry.items():
        filename = entry["file"]
        fmt = entry.get("format", "json")
        filepath = data_dir / filename

        if fmt == "csv":
            total += import_csv(db, table_name, filepath, verbose)

        elif fmt == "json_array":
            data = load_json(filepath, verbose)
            if isinstance(data, list):
                total += import_list(db, table_name, data, verbose)

        elif fmt == "json_special":
            # Delegate to specialized importers
            if filename == "commit-eras.json":
                total += import_commit_eras(db, data_dir, filename, verbose)
            elif filename == "derived-patterns.json":
                total += import_derived_patterns(db, data_dir, filename, verbose)

        elif fmt == "json_nested":
            data = load_json(filepath, verbose)
            if isinstance(data, dict):
                mapping = nested_mappings.get(filename, {})
                if mapping:
                    total += _import_mapping(db, data, mapping, verbose)
                else:
                    # Generic: flatten top-level keys as separate tables
                    for k, v in data.items():
                        if isinstance(v, list) and v:
                            total += import_list(db, f"{table_name}_{k}"[:60], _flat(v), verbose)

        elif fmt == "json":
            data = load_json(filepath, verbose)
            if isinstance(data, list):
                total += import_list(db, table_name, _flat(data), verbose)
            elif isinstance(data, dict):
                rows = []
                for k, v in data.items():
                    if isinstance(v, (dict, list)):
                        rows.append({"key": k, "value": json.dumps(v, default=str)})
                    else:
                        rows.append(flatten_dict({k: v}))
                total += import_list(db, table_name, rows, verbose)

    return total


# ---------------------------------------------------------------------------
# Indexes & FTS
# ---------------------------------------------------------------------------

def _validate_table_name(table: str) -> str:
    """Reject table names that could enable SQL injection."""
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table):
        raise ValueError(f"Invalid table name: {table!r}")
    return table


def table_exists(db: Path, table: str) -> bool:
    table = _validate_table_name(table)
    result = run_su(["query", str(db), f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'"])
    if result.returncode == 0 and result.stdout.strip():
        try:
            rows = json.loads(result.stdout)
            return len(rows) > 0
        except json.JSONDecodeError:
            pass
    return False


def table_columns(db: Path, table: str) -> set[str]:
    table = _validate_table_name(table)
    result = run_su(["query", str(db), f"PRAGMA table_info([{table}])"])
    if result.returncode != 0 or not result.stdout.strip():
        return set()
    try:
        rows = json.loads(result.stdout)
    except json.JSONDecodeError:
        return set()
    return {row.get("name") for row in rows if row.get("name")}


def create_indexes(db: Path, indexes: list[tuple[str, list[str]]] | None = None,
                   verbose: bool = False) -> None:
    if indexes is None:
        indexes = DEFAULT_INDEXES
    for table, columns in indexes:
        if not table_exists(db, table):
            log(f"SKIP indexes on {table} (table not found)", verbose)
            continue
        available = table_columns(db, table)
        for col in columns:
            if col not in available:
                log(f"SKIP index {table}.{col} (column not found)", verbose)
                continue
            run_su(["create-index", str(db), table, col, "--name", f"idx_{table}_{col}", "--if-not-exists"], verbose)


def create_fts(db: Path, fts_config: list[tuple[str, list[str]]] | None = None,
               verbose: bool = False) -> None:
    if fts_config is None:
        fts_config = DEFAULT_FTS
    for table, columns in fts_config:
        if not table_exists(db, table):
            log(f"SKIP FTS on {table} (table not found)", verbose)
            continue
        fts_table = f"{table}_fts"
        if table_exists(db, fts_table):
            log(f"SKIP FTS on {table} (already exists)", verbose)
            continue
        run_su(["enable-fts", str(db), table] + columns + ["--fts4", "--create-triggers"], verbose)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def print_summary(db: Path, verbose: bool = False) -> None:
    result = run_su(["tables", str(db), "--counts"], verbose)
    if result.returncode == 0 and result.stdout.strip():
        print("\nTables (with row counts):")
        for line in result.stdout.strip().splitlines():
            print(f"  {line}")
    idx = run_su(["indexes", str(db)], verbose)
    if idx.returncode == 0 and idx.stdout.strip():
        print("\nIndexes:")
        for line in idx.stdout.strip().splitlines():
            print(f"  {line}")
    fts = run_su(["query", str(db), "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%_fts%'"], verbose)
    if fts.returncode == 0 and fts.stdout.strip():
        try:
            tables = json.loads(fts.stdout)
            if tables:
                print("\nFTS tables:")
                for t in tables:
                    print(f"  {t.get('name', t)}")
        except json.JSONDecodeError:
            pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_db(project_root: Path, output: Path | None = None, verbose: bool = False) -> None:
    """Build archaeology SQLite database from data files.

    Args:
        project_root: Path to the project root directory.
        output: Optional output DB path (default: <project-root>/data/archaeology.db).
        verbose: If True, print detailed progress.
    """
    data_dir = project_root / "data"

    if output:
        db_path = Path(output)
        if not db_path.is_absolute():
            db_path = project_root / output
    else:
        db_path = data_dir / "archaeology.db"

    if not data_dir.exists():
        print(f"ERROR: Data directory not found: {data_dir}", file=sys.stderr)
        sys.exit(1)

    # Load configuration
    registry = load_table_registry(project_root, verbose)
    nested_mappings = load_nested_key_mappings(project_root, verbose)

    # Load project-specific index/fts config if available
    project_json = project_root / "project.json"
    indexes = DEFAULT_INDEXES
    fts_config = DEFAULT_FTS
    if project_json.exists():
        try:
            with open(project_json, encoding="utf-8") as f:
                pdata = json.load(f)
            if "indexes" in pdata:
                indexes = [(item["table"], item["columns"]) for item in pdata["indexes"]]
            if "fts" in pdata:
                fts_config = [(item["table"], item["columns"]) for item in pdata["fts"]]
        except (json.JSONDecodeError, OSError):
            pass

    db_path.unlink(missing_ok=True)
    log(f"Rebuilding DB: {db_path}", verbose)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.touch()

    print(f"Building archaeology DB: {db_path}")
    print(f"Project root: {project_root}")
    print(f"Data directory: {data_dir}")

    # Registry-driven import (handles all formats)
    print("\n--- Importing tables ---")
    import_from_registry(db_path, data_dir, registry, nested_mappings, verbose)

    # Audit files (auto-discovered from glob)
    print("\n--- Audit files ---")
    import_audit_files(db_path, data_dir, verbose)

    # Pipeline history tables are part of the stable query surface even when
    # no pipeline logs have been ingested yet. Create them empty so audit and
    # query helpers can distinguish "no runs" from "schema missing".
    try:
        from .pipeline_ingest import ensure_tables
        ensure_tables(db_path)
    except (OSError, sqlite3.Error) as exc:  # pragma: no cover - defensive CLI guard
        print(f"  WARNING: Failed to ensure pipeline tables: {exc}", file=sys.stderr)

    # Indexes & FTS
    print("\n--- Indexes ---")
    create_indexes(db_path, indexes, verbose)
    print("\n--- Full-text search ---")
    create_fts(db_path, fts_config, verbose)

    print_summary(db_path, verbose)
    print(f"\nDone. Database: {db_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build archaeology SQLite database from data files")
    parser.add_argument("--project", help="Project name (resolves to projects/<name>/)")
    parser.add_argument("--project-root", default=".", help="Direct path to project root (default: .)")
    parser.add_argument("--output", default=None, help="Output DB path (default: <project-root>/data/archaeology.db)")
    parser.add_argument("--verbose", action="store_true", help="Print detailed progress")
    args = parser.parse_args()

    project_root = resolve_project_root(args)
    build_db(project_root, args.output, args.verbose)


if __name__ == "__main__":
    main()
