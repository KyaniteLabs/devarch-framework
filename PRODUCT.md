# DevArch Framework

DevArch helps engineers, researchers and agents investigate how a repository evolved. It turns locally available Git history into queryable data, heuristic investigation leads and inspectable reports. Its purpose is evidence-backed repository archaeology, not scoring a developer's productivity or inferring causes from commit counts.

## Core experience

Create a project workspace, mine a repository, build its SQLite database, detect signals, run analysis, then inspect generated history HTML and Markdown/HTML reports. Audit and evidence-binding checks help expose stale or inconsistent outputs. Mining is scoped to locally available refs; inaccessible/deleted/unfetched remote history is outside that evidence.

## Existing surfaces and features

- [Click CLI](archaeology/cli.py): project initialization, synthetic demo, mining, DB construction, signals, six analysis vectors, visualization, reports, audit and validation; additional sync, GitHub metadata, session/pipeline ingestion and multi-project commands.
- [Optional MCP server](archaeology/mcp_server/): project/query/pipeline functions for agent use, installed through the `mcp` extra. Do not assume CLI and MCP have identical safety/coverage checks.
- [SQLite builder](archaeology/db/builder.py) and optional Datasette inspection; packaged HTML templates and generated history reports.
- Six deterministic [analysis vectors](archaeology/analysis_runner.py): SDLC Gap Finder, ML Pattern Mapper, Agentic Workflow, Formal Terms Mapper, Source Archaeologist and YouTube Correlator. Automated results are low-confidence keyword/data summaries, not an LLM source-code review or proof a practice exists.
- Era/scanning modules, stage instructions, manual analysis prompts and integration scripts. Legacy CLI `cascade`, `opportunity`, `dashboard` and `publish-static` commands are explicitly disabled pending hardening; their source modules are not a promise of a supported operator path.

## Data already present

[projects/demo-archaeology](projects/demo-archaeology/) and [projects/demo-project](projects/demo-project/) contain demo history/session/era inputs, metrics and example deliverables governed by privacy manifests. [stages](stages/) also contains checked-in working outputs, including a database and reports; they are not fresh findings for the user's repository. Configuration/table registries and [analysis-vectors](analysis-vectors/) provide schemas, heuristics and prompts rather than a verified reference corpus.

Real mined history, session messages, watch-history supplements and pipeline logs are user data. They may contain sensitive identities and text; generating HTML or a public case study is not permission to publish raw inputs.

## Boundaries and proof

The CLI rejects shallow mining and records coverage/bindings for the hardened history path. It does not automatically fetch remote completeness. Local analysis needs no model service; GitHub metadata fetching and optional external integrations are separate network paths.

An isolated synthetic demo can exercise the real CLI and browser renderer without touching private history. That proves a bounded demo path only, not arbitrary repository coverage, all MCP paths, or correctness of inferred narratives. See [ARCHITECTURE.md](ARCHITECTURE.md) for failure boundaries.
