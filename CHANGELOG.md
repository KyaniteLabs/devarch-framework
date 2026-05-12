# Changelog

All notable changes to DevArch Framework will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[Unreleased]: https://github.com/KyaniteLabs/devarch-framework/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/KyaniteLabs/devarch-framework/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/KyaniteLabs/devarch-framework/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/KyaniteLabs/devarch-framework/releases/tag/v0.1.0
