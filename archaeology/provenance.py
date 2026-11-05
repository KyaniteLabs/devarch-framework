"""Bind derived evidence to the exact local inputs, without claiming signed provenance."""

import hashlib
import json
from pathlib import Path

from .utils import atomic_write

INPUTS = (
    "project.json",
    "data/coverage.json",
    "data/github-commits.csv",
    "data/github-commits-with-stats.txt",
    "data/archaeology.db",
    "data/detected-signals.json",
    "data/commit-eras.json",
    "data/gap-clusters.json",
    "deliverables/canonical-metrics.json",
    "deliverables/data.json",
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def snapshot(project):
    project = Path(project)
    return {name: digest(project / name) for name in INPUTS}


def requires_binding(project):
    project = Path(project)
    config_path = project / "project.json"
    config = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    return bool(
        config.get("mined_history_manifest_required") or (project / "data/coverage.json").exists()
    )


def analysis_paths(project):
    deliverables = Path(project) / "deliverables"
    paths = set(deliverables.glob("analysis-*.json")) | set(
        (deliverables / "analysis").glob("analysis-*.json")
    )
    return sorted(p for p in paths if not p.name.endswith(".provenance.json"))


def verify_analyses(project, require=False):
    if not requires_binding(project):
        return
    paths = analysis_paths(project)
    if require and not paths:
        raise ValueError("Missing bound analysis; run analyze before exporting")
    current = snapshot(project)
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("evidence_binding") != current:
            raise ValueError(f"Stale or unbound analysis: {path.name}; rerun signals and analyze")
        verify_artifact(project, path)


def bind_artifact(project, artifact, include_analysis=False):
    project, artifact = Path(project), Path(artifact)
    if not requires_binding(project):
        return
    binding = {"snapshot": snapshot(project), "artifact": artifact.name, "sha256": digest(artifact)}
    if include_analysis:
        binding["analysis"] = {
            str(p.relative_to(project)): digest(p) for p in analysis_paths(project)
        }
    atomic_write(str(artifact) + ".provenance.json", json.dumps(binding, indent=2))


def verify_artifact(project, artifact):
    project, artifact = Path(project), Path(artifact)
    if not requires_binding(project):
        return
    sidecar = Path(str(artifact) + ".provenance.json")
    try:
        binding = json.loads(sidecar.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Missing or invalid evidence binding: {artifact.name}") from exc
    if (
        not isinstance(binding, dict)
        or binding.get("artifact") != artifact.name
        or binding.get("sha256") != digest(artifact)
        or binding.get("snapshot") != snapshot(project)
    ):
        raise ValueError(f"Stale or modified artifact: {artifact.name}; regenerate it")
    if "analysis" in binding:
        current = {str(p.relative_to(project)): digest(p) for p in analysis_paths(project)}
        if binding["analysis"] != current:
            raise ValueError(f"Stale analysis inputs for artifact: {artifact.name}; re-export")


def _load_coverage(project):
    coverage_path = Path(project) / "data" / "coverage.json"
    if not coverage_path.is_file():
        raise ValueError("Missing data/coverage.json for bound mining project")
    try:
        coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("Invalid data/coverage.json") from exc
    if not isinstance(coverage, dict):
        raise ValueError("Invalid data/coverage.json")
    return coverage


def verify_mining_inputs(project):
    """Fail when mined CSV/stats no longer match coverage.json artifact hashes."""
    project = Path(project)
    if not requires_binding(project):
        return
    coverage = _load_coverage(project)
    hashes = coverage.get("artifact_sha256")
    if not isinstance(hashes, dict) or not hashes:
        raise ValueError("Mining coverage missing artifact_sha256 bindings")
    for name, expected in hashes.items():
        path = project / "data" / name
        actual = digest(path)
        if actual != expected:
            raise ValueError(f"Stale or modified mining artifact: {name}; remine before export")


def verify_derived_stage(project):
    """Refuse export when DB/metrics/signals belong to a different or incomplete mining generation.

    A failed remine may refresh coverage.json + raw CSV hashes while leaving an older
    archaeology.db / metrics / signals tree in place. Export must not publish that mix.

    Legacy CLI coverage (no mining_status / mining_generation) only requires that the
    SQLite DB exist. Plugin mining always stamps generation + derived_sha256 and must
    pass the full binding checks.
    """
    project = Path(project)
    if not requires_binding(project):
        return
    coverage = _load_coverage(project)
    status = coverage.get("mining_status")
    generation = coverage.get("mining_generation")
    db_path = project / "data" / "archaeology.db"

    # Legacy manifests from the framework CLI mine path.
    if status is None and generation is None:
        if not db_path.is_file():
            raise ValueError("Missing archaeology.db; remine before export")
        return

    if status != "complete":
        raise ValueError(
            "Mining rebuild incomplete or unbound; remine successfully before export "
            f"(mining_status={status!r})"
        )
    if not generation:
        raise ValueError("Mining coverage missing mining_generation; remine before export")
    derived = coverage.get("derived_sha256")
    if not isinstance(derived, dict) or not derived:
        raise ValueError("Mining coverage missing derived_sha256 bindings; remine before export")
    expected_db = derived.get("archaeology.db")
    actual_db = digest(db_path)
    if not expected_db or actual_db != expected_db:
        raise ValueError(
            "Stale or unbound archaeology.db for current mining generation; remine before export"
        )
    # Optional derived JSON must declare the same generation when present.
    for rel in (
        "deliverables/canonical-metrics.json",
        "data/detected-signals.json",
        "data/gap-clusters.json",
    ):
        path = project / rel
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError(f"Invalid derived artifact: {rel}") from exc
        if isinstance(payload, dict):
            marked = payload.get("mining_generation")
            if marked is not None and marked != generation:
                raise ValueError(
                    f"Derived artifact {rel} belongs to a different mining generation; "
                    "rebuild signals/metrics before export"
                )
