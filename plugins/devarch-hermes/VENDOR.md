# Vendored DevArch Framework package

`archaeology/` is copied from KyaniteLabs/devarch-framework @ `b44430e198e45bfaee1edb2f3473f7d50ce17bc2` (v0.4.1).

Omitted from the vendor copy (not used by this Hermes wrap):
- `mcp_server/` (optional `mcp` extra)
- `templates/` and large `visualization/*.html` dashboards (HTML comment scanner caution; wrap uses markdown report + `_markdown_to_html`)

Refresh from repo root:

```bash
rm -rf plugins/devarch-hermes/archaeology
mkdir -p plugins/devarch-hermes/archaeology
tar -C archaeology -cf - \
  --exclude='__pycache__' --exclude='*.pyc' --exclude='mcp_server' \
  --exclude='templates' \
  --exclude='visualization/template.html' \
  --exclude='visualization/global-template.html' \
  --exclude='visualization/multi-project-dashboard.html' \
  . | tar -C plugins/devarch-hermes/archaeology -xf -
```

## Plugin-local patches (KLH-328 Kai review)

Applied on top of the pinned vendor copy for the Hermes wrap (kept in sync with matching framework `archaeology/` fixes where noted):

- `extractors/git.py` — `GIT_NO_LAZY_FETCH=1` on all git invocations; `incomplete_object_reason()` refuses promisor/partial/missing-object repos (local-only contract).
- `report.py` — include measured `detected-signals.json` + `gap-clusters.json`; honest era/cluster semantics; curated `commit-eras.json` preserved; `verify_mining_inputs` + `verify_derived_stage`; `verify_analyses(require=…)` only when analysis artifacts exist.
- `provenance.py`, `metrics.py` — present derived metrics/signals/clusters require both the current generation and a content-hash sidecar (also synchronized to root framework). Optional absence does not exempt a present artifact.
- `extractors/git.py` — positive commit cap for both raw/stats extraction, disabled transports and optional Git locks; full ref coverage remains separately reported.
- `report.py`, `visualization/dashboard.py`, `visualization/agent_benchmark.py` — package-relative imports support the isolated `_devarch_vendor` namespace. The wrapper never prefers an arbitrary installed framework.
- Wrapper project transactions serialize full operations across threads/processes; complete pipelines retain the same lock across nested stages.

**Refresh warning:** the raw copy commands above do not preserve these patches. Reapply and rerun the full framework + plugin suite, native runtime/validator and deterministic concurrency/content-integrity probes after any refresh.
