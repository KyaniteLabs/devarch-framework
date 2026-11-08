# DevArch architecture

## Parts and data flow

```text
CLI project config + local Git refs
 -> extractors/git.py -> CSV + stats + CLI coverage manifest
 -> db/builder.py -> SQLite tables/indexes/FTS
 -> classifiers + analysis_runner -> signals + six vector JSON outputs
 -> visualization/history + report -> HTML/Markdown + evidence sidecars
 -> audit / validate -> consistency and integrity findings
Optional: MCP tool wrappers, Datasette, session/pipeline ingest, multi-project sync
```

- [archaeology/cli.py](archaeology/cli.py) orchestrates project-relative operations. [setup.py](setup.py) exposes `devarch` and `devarch-mcp`, declares dependencies, and packages templates. Actual packaging currently uses setuptools and Python >=3.10; repository aspirational stack rules do not change the executable metadata.
- [extractors/git.py](archaeology/extractors/git.py) reads Git using argv arrays and bounded subprocess calls. Primary CSV extraction uses NUL-delimited fields, normalizes dates to UTC and checks extracted count against reachable commits. CLI mining rejects shallow history, compares coverage before/after and hashes outputs into `coverage.json`.
- [db/builder.py](archaeology/db/builder.py) maps project/default table registries to CSV/JSON ingestion, flattening, indexes and full-text search. It depends on the `sqlite-utils` command as well as Python dependencies; missing ingestion tooling must fail rather than silently produce zero findings.
- [analysis_runner.py](archaeology/analysis_runner.py) queries local SQLite/JSON and writes six deterministic vector summaries. Commit-keyword matches are investigation leads. Optional supplementary data feeds correlations only when supplied.
- [provenance.py](archaeology/provenance.py) snapshots hashes of known inputs and binds analyses/artifacts to them. Verification can reject stale/modified results for projects requiring binding. This is local integrity checking, not signed provenance or proof that input assertions are true.
- [mcp_server/tools.py](archaeology/mcp_server/tools.py) calls Python functions directly, with workspace helpers, rather than invoking the CLI. [local_pipeline.py](archaeology/local_pipeline.py) separately reads external pipeline status or explicitly runs its producer.

## Risky paths and visible failures

| Path | Failure and interpretation |
| --- | --- |
| Mining/coverage | Shallow history, changing refs or extraction mismatch should fail. Unfetched/deleted remote refs remain gaps even after a clean run. Commit dates/subjects and counts are not productivity or causal evidence. |
| CLI vs MCP | MCP mining has different wrapper checks and does not reproduce the CLI coverage-manifest sequence; its `.git` directory check also excludes ordinary linked worktrees. Do not extend hardened-CLI acceptance to all surfaces. |
| DB/analysis | Missing DB, tables or ingestion tooling can fail commands. Missing supplementary data is not evidence of no activity; keyword matches cannot verify testing, security or implementation quality. |
| Derived outputs | An old report may look polished while inputs changed. Check required evidence sidecars and audit output, not file existence alone; older/demo projects may not require bindings. |
| Workspace/global state | CLI uses relative project paths; some MCP helpers temporarily change process CWD. Concurrent jobs and untrusted project/path values need separate containment review, not a claim that local-first implies sandboxed. |
| Privacy/exposure | Author names, commit messages, session/watch data and logs flow into databases/reports. Datasette/public exports/HTML are exposure boundaries. Review privacy manifests and sanitization before serving or sharing. |
| Legacy commands | Disabled CLI paths are intentional refusal, not install failures. Do not enable cascade/publication or invoke legacy modules just because a file exists. |

## Verification and change scope

An isolated synthetic demo exercised `demo --build-db`, `signals`, all six `analyze` vectors, `visualize`, Markdown `export-report`, and `audit --fail-on HIGH`. The demo DB held six commits, two sessions and three eras; the browser showed six commits across four active UTC days. Audit reported one INFO notice for governed sensitive artifacts, not an all-findings-empty result. These are synthetic demo outputs, not fabricated live-repository findings.

The screenshot of the actual generated renderer is bounded evidence of that demo path; it does not validate every command, MCP compatibility or private-history handling. Documentation changes do not modify runtime, source repositories, existing project data or services. Rollback is reverting the docs commit; preserve historical project records.
