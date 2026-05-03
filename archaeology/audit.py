"""Forensic audit gate for dev-archaeology projects.

The audit module intentionally checks the product's credibility surface rather
than only whether individual scripts run. It catches drift between canonical
metrics, project config, generated data, the SQLite database, and publishable
claims.
"""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .utils import _load_json


SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
PUBLISHABLE_SUFFIXES = {".md", ".html", ".json", ".j2"}
SENSITIVE_NAME_PATTERNS = [
    re.compile(r"raw-sessions", re.I),
    re.compile(r"human-messages", re.I),
    re.compile(r"gpt-conversations", re.I),
    re.compile(r"youtube-search-history", re.I),
    re.compile(r"developer-resume", re.I),
]
SECRET_PATTERNS = [
    re.compile(r"\bsk-(?:proj|live|test|ant|svcacct)-[A-Za-z0-9_-]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{40,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----"),
]


@dataclass(frozen=True)
class AuditFinding:
    severity: str
    code: str
    message: str
    path: str | None = None
    detail: str | None = None

    def format(self) -> str:
        location = f" [{self.path}]" if self.path else ""
        detail = f"\n    {self.detail}" if self.detail else ""
        return f"{self.severity}: {self.code}: {self.message}{location}{detail}"


def _project_dir(project_name: str, root: Path) -> Path:
    return root / "projects" / project_name


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _iter_publishable_files(paths: Iterable[Path]) -> Iterable[Path]:
    for path in paths:
        if path.is_file() and path.suffix.lower() in PUBLISHABLE_SUFFIXES:
            yield path
        elif path.is_dir():
            for child in path.rglob("*"):
                if child.is_file() and child.suffix.lower() in PUBLISHABLE_SUFFIXES:
                    yield child


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        cleaned = value.replace(",", "").strip()
        if cleaned.isdigit():
            return int(cleaned)
    return None


def _db_count(db_path: Path, table: str) -> int | None:
    if not db_path.exists():
        return None
    conn = sqlite3.connect(str(db_path), timeout=30)
    try:
        return int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
    except sqlite3.Error:
        return None
    finally:
        conn.close()


def _table_exists(db_path: Path, table: str) -> bool:
    if not db_path.exists():
        return False
    conn = sqlite3.connect(str(db_path), timeout=30)
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        return row is not None
    except sqlite3.Error:
        return False
    finally:
        conn.close()


def check_canonical_consistency(project_name: str, root: Path) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    project_root = _project_dir(project_name, root)
    project_json_path = project_root / "project.json"
    canonical_path = project_root / "deliverables" / "canonical-metrics.json"
    data_json_path = project_root / "deliverables" / "data.json"
    eras_path = project_root / "data" / "commit-eras.json"
    db_path = project_root / "data" / "archaeology.db"

    project = _load_json(project_json_path) or {}
    canonical = _load_json(canonical_path) or {}
    data = _load_json(data_json_path) or {}
    eras = _load_json(eras_path) or {}

    if not canonical:
        findings.append(AuditFinding("CRITICAL", "CANONICAL_MISSING", "canonical-metrics.json is missing or invalid", _rel(canonical_path, root)))
        return findings

    expected_commits = _as_int(canonical.get("total_commits"))
    expected_days = _as_int(canonical.get("span_days"))
    expected_active = _as_int(canonical.get("active_days"))

    project_overrides = project.get("overrides", {}) if isinstance(project, dict) else {}
    project_timeline = project.get("timeline", {}) if isinstance(project, dict) else {}
    checks = [
        ("total_commits", expected_commits, project_overrides.get("total_commits"), project_json_path),
        ("span_days", expected_days, project_timeline.get("total_days"), project_json_path),
        ("active_days", expected_active, project_overrides.get("active_days"), project_json_path),
    ]
    for metric, expected, observed, path in checks:
        observed_int = _as_int(observed)
        if expected is not None and observed_int is not None and expected != observed_int:
            findings.append(AuditFinding("HIGH", "PROJECT_DRIFT", f"project.json {metric} does not match canonical metrics", _rel(path, root), f"canonical={expected}, project={observed_int}"))

    tv_meta = data.get("telemetry_visualizations", {}).get("meta", {}) if isinstance(data, dict) else {}
    data_checks = [
        ("total_commits", expected_commits, tv_meta.get("total_commits")),
        ("span_days", expected_days, tv_meta.get("lifespan_days") or tv_meta.get("span_days")),
        ("active_days", expected_active, tv_meta.get("active_days")),
    ]
    for metric, expected, observed in data_checks:
        observed_int = _as_int(observed)
        if expected is not None and observed_int is not None and expected != observed_int:
            findings.append(AuditFinding("HIGH", "DATA_DRIFT", f"data.json {metric} does not match canonical metrics", _rel(data_json_path, root), f"canonical={expected}, data={observed_int}"))

    if isinstance(eras, dict):
        era_commits = _as_int(eras.get("total_commits"))
        if expected_commits is not None and era_commits is not None and era_commits != expected_commits:
            findings.append(AuditFinding("HIGH", "ERA_DRIFT", "commit-eras.json total_commits does not match canonical metrics", _rel(eras_path, root), f"canonical={expected_commits}, commit-eras={era_commits}"))
        canonical_eras = _as_int(project_overrides.get("era_count"))
        era_count = len(eras.get("eras", [])) if isinstance(eras.get("eras"), list) else None
        if canonical_eras is not None and era_count is not None and canonical_eras != era_count:
            findings.append(AuditFinding("HIGH", "ERA_COUNT_DRIFT", "commit-eras.json era count does not match project override", _rel(eras_path, root), f"project={canonical_eras}, commit-eras={era_count}"))

    db_commits = _db_count(db_path, "commits")
    if expected_commits is not None and db_commits is not None and db_commits != expected_commits:
        findings.append(AuditFinding("HIGH", "DB_COMMIT_DRIFT", "SQLite commits table does not match canonical metrics", _rel(db_path, root), f"canonical={expected_commits}, db={db_commits}"))
    db_eras = _db_count(db_path, "eras")
    canonical_eras = _as_int(project_overrides.get("era_count"))
    if canonical_eras is not None and db_eras is not None and db_eras != canonical_eras:
        findings.append(AuditFinding("HIGH", "DB_ERA_DRIFT", "SQLite eras table does not match project era count", _rel(db_path, root), f"project={canonical_eras}, db={db_eras}"))
    if db_path.exists() and not _table_exists(db_path, "pipeline_runs"):
        findings.append(AuditFinding("MEDIUM", "PIPELINE_TABLE_MISSING", "pipeline_runs table is absent; pipeline history queries cannot work", _rel(db_path, root)))

    return findings


def check_placeholder_data(project_name: str, root: Path) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    data_json_path = _project_dir(project_name, root) / "deliverables" / "data.json"
    data = _load_json(data_json_path)
    if not isinstance(data, dict):
        return findings

    def walk(obj: Any, path: str = "", excluded: bool = False) -> Iterable[tuple[str, Any, bool]]:
        current_excluded = excluded
        if isinstance(obj, dict):
            provenance = obj.get("provenance")
            if isinstance(provenance, dict):
                status = str(provenance.get("status", "")).lower()
                if status in {"placeholder_excluded", "excluded", "historical_raw"} or provenance.get("publishable") is False:
                    current_excluded = True
        yield path, obj, current_excluded
        if isinstance(obj, dict):
            for key, value in obj.items():
                yield from walk(value, f"{path}.{key}" if path else str(key), current_excluded)
        elif isinstance(obj, list):
            for idx, value in enumerate(obj):
                yield from walk(value, f"{path}[{idx}]", current_excluded)

    zero_total_paths: list[str] = []
    excluded_zero_total_paths: list[str] = []
    mpc_paths: list[str] = []
    excluded_mpc_paths: list[str] = []
    for path, value, excluded in walk(data):
        if isinstance(value, dict):
            if value.get("co_authored") == 0 and value.get("total") == 0:
                (excluded_zero_total_paths if excluded else zero_total_paths).append(path)
            if value.get("messages_per_commit") == 1.0:
                (excluded_mpc_paths if excluded else mpc_paths).append(path)

    if len(zero_total_paths) >= 3:
        findings.append(AuditFinding("HIGH", "PLACEHOLDER_COAUTHORSHIP", "Repeated all-zero co-authorship rows look placeholder-derived", _rel(data_json_path, root), f"examples={zero_total_paths[:5]}"))
    elif excluded_zero_total_paths:
        findings.append(AuditFinding("INFO", "PLACEHOLDER_COAUTHORSHIP_EXCLUDED", "Co-authorship placeholder rows are explicitly marked non-publishable", _rel(data_json_path, root), f"count={len(excluded_zero_total_paths)}"))
    if len(mpc_paths) >= 3:
        findings.append(AuditFinding("MEDIUM", "PLACEHOLDER_SESSION_DEPTH", "Repeated messages_per_commit=1.0 rows look placeholder-derived", _rel(data_json_path, root), f"examples={mpc_paths[:5]}"))
    elif excluded_mpc_paths:
        findings.append(AuditFinding("INFO", "PLACEHOLDER_SESSION_DEPTH_EXCLUDED", "Session-depth placeholder rows are explicitly marked non-publishable", _rel(data_json_path, root), f"count={len(excluded_mpc_paths)}"))
    return findings


def check_sensitive_artifacts(project_name: str, root: Path) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    project_root = _project_dir(project_name, root)
    sensitive_paths = []
    for path in project_root.rglob("*"):
        if not path.is_file():
            continue
        rel = _rel(path, root)
        if any(pattern.search(path.name) for pattern in SENSITIVE_NAME_PATTERNS):
            sensitive_paths.append(rel)
    if sensitive_paths:
        manifest = project_root / "PRIVACY-MANIFEST.md"
        severity = "INFO" if manifest.exists() else "MEDIUM"
        message = "Private/raw data artifacts are present and governed by the project privacy manifest" if manifest.exists() else "Private/raw data artifacts are present in the project tree"
        findings.append(AuditFinding(severity, "SENSITIVE_ARTIFACTS", message, _rel(project_root, root), "examples=" + ", ".join(sensitive_paths[:8])))

    for path in _iter_publishable_files([project_root / "data", project_root / "deliverables"]):
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                findings.append(AuditFinding("CRITICAL", "SECRET_PATTERN", "Potential secret/private key pattern found", _rel(path, root)))
                break
    return findings


def check_project_config(project_name: str, root: Path) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    project_json_path = _project_dir(project_name, root) / "project.json"
    project = _load_json(project_json_path)
    if not isinstance(project, dict):
        findings.append(AuditFinding("CRITICAL", "PROJECT_JSON_INVALID", "project.json is missing or invalid", _rel(project_json_path, root)))
        return findings
    for key in ("name", "description", "repo_url"):
        if not str(project.get(key, "")).strip():
            findings.append(AuditFinding("MEDIUM", "PROJECT_FIELD_EMPTY", f"project.json field '{key}' is empty", _rel(project_json_path, root)))
    if project.get("repo_url") and not str(project["repo_url"]).startswith("https://github.com/"):
        findings.append(AuditFinding("MEDIUM", "PROJECT_REPO_URL", "repo_url should be a GitHub HTTPS URL", _rel(project_json_path, root)))
    return findings


def check_era_references(project_name: str, root: Path) -> list[AuditFinding]:
    """Scan deliverables for stale era references."""
    from .era_mapper import load_eras
    from .era_scanner import scan_deliverables

    findings: list[AuditFinding] = []
    project_root = _project_dir(project_name, root)
    eras_path = project_root / "data" / "commit-eras.json"

    if not eras_path.exists():
        return findings

    eras = load_eras(eras_path)
    if not eras:
        return findings

    result = scan_deliverables(project_root, eras)

    for ref in result.refs:
        severity = "MEDIUM"
        code = "ERA_STALE_REF"
        if ref.kind == "era_json_field":
            severity = "HIGH"
            code = "ERA_STALE_NUMBER"
        elif ref.kind == "era_name":
            severity = "HIGH"
            code = "ERA_STALE_NAME"
        elif ref.kind == "era_css_var":
            severity = "HIGH"
            code = "ERA_STALE_CSS"
        elif ref.kind == "era_count":
            severity = "MEDIUM"
            code = "ERA_STALE_COUNT"

        findings.append(AuditFinding(
            severity, code,
            f"Stale era reference: {ref.old_value} (expected: {ref.expected})",
            path=_rel(ref.file, root),
            detail=f"line {ref.line}, kind={ref.kind}",
        ))

    return findings


def run_audit(project_name: str, root: str | Path = ".") -> list[AuditFinding]:
    root_path = Path(root).resolve()
    project_root = _project_dir(project_name, root_path)
    findings: list[AuditFinding] = []
    if not project_root.exists():
        return [AuditFinding("CRITICAL", "PROJECT_MISSING", f"Project '{project_name}' does not exist", _rel(project_root, root_path))]

    for check in (
        check_project_config,
        check_canonical_consistency,
        check_placeholder_data,
        check_sensitive_artifacts,
        check_era_references,
    ):
        findings.extend(check(project_name, root_path))

    return sorted(findings, key=lambda f: (SEVERITY_ORDER.get(f.severity, 99), f.code, f.path or ""))


def has_blocking_findings(findings: Iterable[AuditFinding], fail_on: str = "HIGH") -> bool:
    threshold = SEVERITY_ORDER[fail_on]
    return any(SEVERITY_ORDER.get(f.severity, 99) <= threshold for f in findings)


def summarize(findings: Iterable[AuditFinding]) -> dict[str, int]:
    summary = {severity: 0 for severity in SEVERITY_ORDER}
    for finding in findings:
        summary[finding.severity] = summary.get(finding.severity, 0) + 1
    return summary
