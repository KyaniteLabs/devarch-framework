# Changelog

All notable changes to DevArch Framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.1] - Unreleased readiness candidate

- Harden the AG4TE Hermes plugin after review: chat platforms (and any platform not known as local) can no longer stop a dig, and get summaries without paths, error text or author names; one dig at a time now holds across Hermes processes through a workspace lease; two repositories with the same folder name no longer share a project; a small era beside a large one keeps a 3px band in the stone; the layout regression runs on a sanitized fixture instead of host data; tests no longer name real people; the plugin pins DevArch to the catalog-reviewed commit (`d884f9a`).
- Rename the repository to AG4TE (`KyaniteLabs/ag4te`). The `devarch` command and the `devarch-framework` package keep their names.
- Draw the AG4TE plugin's stone as an iris agate: one band per era, oldest at the rim, laid out in time order with each kind of work sized by its share of the era's commits. Classify plain imperative commit subjects ("Add…", "Fix…") as kinds of work, and pin the plugin to that DevArch commit (`6dd2299`).
- Add the AG4TE Hermes plugin (`plugins/ag4te-hermes`) and fix the commit data model: the Git extractor records email and parents, dates keep their UTC offset, era signals sort by instant, and SDLC practices are word-bounded with merges left out.

- Fix QA regressions from #90: `global-viz` and `multi-project-dashboard` now resolve their templates against the installed package (they failed outside the repo source root); `sync` accepts the README-documented `path` profile key as an alias for `repo_path`, validates `name` and the repository location as nonempty strings before any filesystem writes, and reports malformed project entries with actionable errors instead of `KeyError`/`TypeError` tracebacks; `serve` passes datasette's `--setting` as two arguments so the server actually starts.
- Parse ISO-8601 and legacy Git-log commit timestamps in agent benchmarks, and report malformed dates with commit context instead of silently dropping rows.

- Name the installed `devarch` binary in every CLI error/hint (was the retired `archaeology` name); replace PyPI badges and links — the package is not published — with GitHub release equivalents; point the docs page canonical at the live GitHub repo; keep the public source line GitHub-only.

- Bind analysis, reports and visualizations to exact inputs; reject stale A-to-B runs.
- Disable unsafe legacy dashboard/static publishing, cascade and opportunity profiling before side effects; remove the active Markdown viewer and wildcard API CORS.
- Validate installed history HTML without a source-relative Node dependency.
- Correct package/documentation metadata to Apache-2.0. Released under Apache-2.0 since 2026-06-02 (PR #54); the initial MIT grant from 2026-04-29 remains in effect for copies obtained before that date.
- Add installed-wheel checks to native Python3.12 CI and remove suppressed CI failures.

## [0.4.0] - 2026-10-01 — Evidence integrity

Fix full-history mining for bare repositories/worktrees, reject shallow coverage, bind extraction artifacts, reconcile CSV/SQLite metrics, and generate portable measured visualizations. Replace unsupported agent/ML/quality assertions with explicit uncertainty. See [release notes](docs/RELEASE_0.4.0.md) for output compatibility and validation.

## [0.3.1] - 2026-05-12

### Changed
- **Pipeline service owns every verb**: `cascade`, `sync` and `serve` moved from inline CLI orchestration onto `archaeology/pipeline.py` (`prepare_serve`, `cascade`, `sync`), joining init/mine/build-db/signals/analyze/visualize/report/audit. CLI output is byte-identical — pinned by the adapter characterization golden, extended to the three verbs — and the sync flow gained hermetic service-level tests (its profile resolution reads the package's own `config/profile.json` first, so the golden pins only its error path).

### Security
- **CLI project-name validation**: the CLI now validates project names the way the MCP server does. `devarch init ../escape` used to create `projects/../escape`, outside `projects/`, and `demo --project ../x --force` could write files there. Every CLI command that takes a project name (`init`, `demo`, `public-case-study`, `audit`, `mine -p`, and the commands that open an existing project) rejects unsafe names before any write, with `Error: Project name …` and exit 1. `create_demo_project` also validates the name itself, which covers `public-case-study` and any other caller. Allowed names are 1–100 characters from `A–Z a–z 0–9 . _ -`, with no `..` and no leading `.` or `-`; `.` used to scaffold into `projects/` itself. Behaviour change: names with spaces or other characters are now refused by the CLI too, and a leading `.` or `-` is now refused by both the CLI and MCP.
- **Path traversal protection**: Added `validate_project_name()` to MCP server — blocks `..`, `/`, and non-alphanumeric characters in project names
- **Workspace validation**: `DEVARCH_WORKSPACE` env var now verified to exist and be a directory
- **Vector name validation**: MCP `query_analysis` tool validates vector names against known list, preventing injection
- **Format parameter validation**: MCP `report` tool validates `fmt` parameter against `html`/`markdown`
- **Git repo validation**: MCP `mine` tool and CLI `mine` command verify `.git` directory exists before extraction
- **Silent failure logging**: `read_json()` in MCP server now logs warnings for JSON decode and file read errors

### SEO/GEO
- **robots meta tag**: `seo_meta()` now includes `<meta name="robots" content="index, follow">` by default
- **Social sharing images**: Added `image` parameter to `seo_meta()` and `seo_software_application()` for `og:image`/`twitter:image`
- **Stage 06 visualization rewrite**: `generate_visualization.py` now uses design system with full SEO tags, accessibility, and theme support (was 17% SEO score, now ~95%)

### Error Handling
- **Git extraction**: Added try-except around `extract_git_log` and `extract_git_log_with_stats` in CLI (8 locations)
- **JSON parsing**: Added `json.JSONDecodeError` handling in CLI for config/data file reads (8 locations)
- **Database errors**: Added `sqlite3.Error` logging in `analysis_runner._query_db()` when verbose mode is active

### Changed
- **One pipeline service behind the CLI and MCP adapters.** `archaeology/pipeline.py` now owns project-directory resolution, input validation and the init, mine, build-db, signals, analyze, visualize, report, audit and run-pipeline operations, and raises `PipelineError` for caller-fixable failures. `cli.py` and `mcp_server/tools.py` keep only click parsing and echo, and dict shaping. Observable behaviour of both surfaces is unchanged and pinned by `tests/golden/pipeline_contract.json`; the differences between them (in-process vs subprocess build, unexpanded vs expanded repo path, separate visualize and report renderers) are kept as explicit parameters. `mcp_server/project_utils.py` re-exports the workspace helpers from the service.
- **Removed the standalone stage scripts and committed stage outputs.** `stages/0{4..8}-*/*.py` (5 scripts, 2,042 lines) were independent copies of the pipeline. They imported nothing from `archaeology`, nothing in the repo or docs ran them, and the `devarch` CLI is the supported implementation. The 20 committed working artifacts under `stages/*/output/` (sample CSVs, a SQLite database, generated HTML and Markdown) are removed, and `.gitignore` now keeps stage outputs local. The stage `CONTEXT.md` contracts and each `output/.gitkeep` stay.
- **Single version source**: `/api/health` and the global insights payload reported a hard-coded `1.0.0` from `archaeology/api.py`. They now report `archaeology.__version__` (0.3.1). The unused `__version__ = "1.0.0"` in `scripts/content/__init__.py` is removed.
- **CLI command name**: hints and errors named a nonexistent `archaeology` command. The installed command is `devarch` (`setup.py` console_scripts). Fixed in `cli.py`, `demo.py`, `report.py` and the demo fixture READMEs. The "Run 'devarch init …' first" error now formats the project name: it was a plain string that printed `{project_name}` literally.
- **Executable README**: a `bash readme-test` block (offline demo plus signals) runs in CI on every change through the shared profile's Layer 3 step. It pins the corrected hint text.
- **Consistent branding**: Standardized to "DevArch Framework" across all 36 references (was mixed with "Development Archaeology")
- **Author attribution**: Standardized to "Simon Gonzalez De Cruz" across setup.py, LICENSE, and generated HTML
- **Version in footers**: HTML templates show "DevArch Framework v0.3.1" (bumped with this version train; no artifacts have been tagged)
- **Third-party acknowledgments**: Added dependency attribution section to README.md

## [0.3.0] - 2026-05-11

### Changed
- **ICM refactoring**: CLAUDE.md reduced from 192 to 92 lines (pure L0 map)
- **Workspace siloing**: CONTEXT.md now routes to 5 workspaces (extraction, analysis, reporting, multi-project, setup)
- **Token management**: Explicit "When doing X, skip Y" guidance in routing tables
- **L3/L4 separation**: All 9 stage contracts now distinguish reference material from working artifacts
- **Handoff documentation**: Added `docs/decisions.md` with 7 architecture decision records
- **Reference extraction**: Moved Core Concepts to `shared/concepts.md`, Sync Rules to `shared/sync-rules.md`

### Added
- `docs/decisions.md` — Architecture decision records (7 ADRs)
- `shared/concepts.md` — L3 reference for core framework concepts
- `shared/sync-rules.md` — L3 reference for sync parity and git hygiene
- `stages/09-strategy/references/strategy-sections.md` — Strategy report section definitions
- `.gitkeep` files in all 9 stage output/ directories
- ICM layer declaration table in CLAUDE.md

### Removed
- Core Concepts section from CLAUDE.md (moved to shared/concepts.md)
- Sync Rules section from CLAUDE.md (moved to shared/sync-rules.md)
- Epoch Data Tracking section from CLAUDE.md (moved to shared/sync-rules.md)
- ICM Compliance meta-section from CLAUDE.md (replaced by ICM layer table)

## [0.2.0] - 2026-05-03

### Added
- **Complete CLI** with 19 commands for full archaeology workflow
- **6 Analysis Vectors**: SDLC Gap Finder, ML Pattern Mapper, Agentic Workflow Analyzer, Formal Terms Mapper, Source Archaeologist, YouTube Correlator
- **Era System**: Detect and track distinct phases in repository evolution
  - Era scanner with semantic pattern matching
  - Era cascade for propagating labels across files
  - Era mapper for visualizing era boundaries
- **Signal Detection**: 5 heuristics for identifying noteworthy patterns
  - Temporal gaps in commit activity
  - Velocity shifts in development pace
  - Author changes and collaboration patterns
  - Scope changes in file modifications
  - External data correlations
- **Audit System**: Severity-based validation (CRITICAL, HIGH, MEDIUM, LOW)
- **Multi-Project Sync**: Aggregate findings across multiple repositories
- **Visualization**: Template-based HTML report generation
- **Demo Generation**: Create synthetic projects for testing
- **Database Inspection**: Datasette integration for interactive exploration
- **Supplementary Data**: Correlate external data (fitness, YouTube, calendar)
- **Local Pipeline**: Inspect GitHub Actions pipelines locally
- **Public Case Study**: Export sanitized versions for sharing

### Changed
- Improved error handling throughout the CLI
- Enhanced database schema for better query performance
- Updated analysis vector templates for consistency

### Fixed
- Era detection false positives in semantic scanning
- Signal detection edge cases for sparse repositories
- Database migration issues between versions

## [0.1.0] - 2026-04-XX

### Added
- Initial release
- Basic git history mining
- SQLite database storage
- Signal detection framework
- Analysis vector system
- CLI scaffolding

[Unreleased]: https://github.com/KyaniteLabs/ag4te/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/KyaniteLabs/ag4te/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/KyaniteLabs/ag4te/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/KyaniteLabs/ag4te/releases/tag/v0.1.0
