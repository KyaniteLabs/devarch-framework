# DevArch 0.4.0 evidence-integrity release

This release repairs the standard init → mine → build-db → signals → analyze → visualize → export-report → audit path before using it for release archaeology.

## Root causes and fixes

- Git validation assumed a `.git` directory, rejecting linked worktrees and bare repositories. Git now establishes repository validity; shallow histories fail explicitly. Mining includes all local refs, writes an exact ref/root/count inventory and binds the CSV/raw-stat files by SHA256. It does not fetch remotes or claim deleted history coverage.
- Unit-separator parsing could silently shift fields in unusual subjects. NUL-delimited extraction retains separators, tabs and Unicode. Empty histories replace stale CSV data with a header.
- The ordinary pipeline never produced the canonical metrics needed by audit/reporting. Database build now reconciles complete commit identities and produces measured UTC counts/dates and daily activity.
- Visualization depended on the caller's current directory and substituted 803 commits, 35,600 lines and six agents. It now produces a self-contained measured daily-activity table/chart from any working directory; missing data fails explicitly. The prior narrative dashboard template remains available as a legacy template but is no longer the default CLI output.
- Agent vectors fabricated session-depth buckets and hook effectiveness; ML vectors fabricated similarity and token waste. These become unmeasured/null or explicitly low-confidence investigation candidates. Keyword evidence is not source verification. SDLC and source summaries no longer establish absence or improving quality from keywords alone. Summary keyword counts are no longer capped at 500.
- Timestamp parsing discarded offsets. Dates now normalize to UTC before aggregation.
- Audit now catches modified mining inputs, missing databases and commit identity drift. The example archaeology workflow no longer swallows audit failures.
- Runtime and distribution versions agree, and `devarch --version` identifies the installed distribution.

## Compatibility and boundaries

Python >=3.10 and existing CLI command names remain. JSON session measurements and unsupported similarity/waste claims are now null rather than fabricated numbers; consumers must handle unknown values. Generated charts intentionally do not infer agents, personal sessions or causal eras. CSV dates are ISO8601 UTC, potentially shifting author-local calendar days. Git author aliases remain unresolved. Merge/cherry-pick duplication across refs is genuine history, not necessarily repeated defects.

This is deterministic commit-message analysis plus an auditable extraction path, not automated line-level source/PR reasoning. Manual source evidence is required for architecture decisions, abandoned-feature disposition and release recommendations. No personal session or YouTube data is needed. The mining implementation still buffers Git output; large-repository streaming remains a documented follow-up. Raw history may contain private material and must be reviewed before sharing.

## Acceptance

Use the real-Git fixtures in `tests/test_release_pipeline.py`, the full test suite, and a clean wheel installation outside the source checkout. The fixtures cover bare repositories, worktrees, delimiter-bearing subjects, shallow rejection, timezone normalization, full pipeline execution and tampered-input audit rejection. Release only from reviewed canonical history; never bypass protections. Registry availability is separate from a GitHub release.

Local acceptance on Python 3.12: baseline 97 tests; repaired suite 104 tests passed. Wheel and source archive passed Twine metadata validation. A separate non-editable wheel environment outside the checkout passed ten CLI invocations, including bare-repository mining, database build, all six analysis vectors, visualization, both report formats and audit. Git/CSV/SQLite totals reconciled to two fixture commits. These fixtures do not establish remote registry publication or native Windows/macOS acceptance.
