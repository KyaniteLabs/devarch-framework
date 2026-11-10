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
