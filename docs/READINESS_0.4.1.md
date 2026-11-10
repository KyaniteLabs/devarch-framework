# 0.4.1 readiness candidate — not published

This follow-up closes broader package risks found after the 0.4.0 core-pipeline repair. It does not authorize another release, tag, deployment, publisher configuration change or KINOCUT run.

## Supported and disabled behavior

Use `init → mine → build-db → signals → analyze → visualize → validate → export-report → audit` from an analysis workspace. Each analysis file binds to exact local inputs and has an independently checked content digest. Reports bind to those analyses; visualization binds to its inputs. Changed history/configuration, edited analysis, stale reports and missing bindings fail closed. Rerun affected stages to recover. These local integrity checks do not authenticate remote provenance or prevent coordinated modification of both data and bindings. Legacy imported datasets without a mining manifest retain their separate compatibility path; they do not gain verified Git provenance.

`dashboard`, `publish-static`, `cascade` (including dry-run), and `opportunity` now return an actionable nonzero error before any mutation or listener. Direct opportunity inference is disabled too. This deliberately removes unsupported personal/medical-adjacent profiles and prevents broad serving/deletion of local artifacts. There is no unsafe override. The old Markdown query viewer is inert and the JSON API no longer adds wildcard CORS. Open reviewed local HTML directly. A future dashboard needs a constrained export inventory, loopback/authentication policy and tested safe rendering before re-enablement.

Validation now locates the CLI's `deliverables/visuals/archaeology.html` and uses packaged Python code. It checks evidence binding, required structure and absence of active content; it does not claim browser, accessibility or general HTML conformance acceptance.

The existing LICENSE remains Apache-2.0. Distribution and first-party documentation labels are corrected to match it; third-party MIT acknowledgments remain. No relicensing occurred.

## Verification and CI

Real-Git tests cover A→B stale outputs, edited analysis followed by reexport, deleted report bindings, modified HTML, direct opportunity rejection, disabled-command no-side-effect behavior and CORS. A pre-existing SWOT strength-count NameError has a failing-then-passing regression. A separate non-editable wheel runs eleven CLI commands outside the checkout and checks metadata/runtime identity and Apache license.

CI includes installed-wheel checks on Python 3.12 for Linux/macOS/Windows. All supported Python 3.10–3.12 combinations retain unit tests. Lint and formatting now fail rather than being swallowed, including Forgejo. Ruff is pinned at 0.16.10 with explicit E4/E7/E9/F/I rules; repository Python files were formatted, import hygiene repaired, and unused bindings renamed without discarding expression side effects. Repository-only content-generation scripts use Python 3.12 syntax, recorded through per-file target versions. Two standalone scripts intentionally import after path setup, with narrowly scoped E402 exceptions. Package code remains Python 3.10 compatible. The older broader Ruff diagnostic is retained outside the repository as investigation evidence, not a claim all optional Ruff rules are enabled.

## Release status

GitHub v0.4.0 exists at 2a37692cbb0e76954d1a48648f1125f1b26102d6; it does not contain these follow-up fixes. Its PyPI job failed with `invalid-publisher`, no matching publisher. Do not retry until an authorized PyPI project owner verifies the expected owner `KyaniteLabs`, repository `devarch-framework`, workflow `publish.yml`, and environment claim (the workflow currently declares none). No credential or publisher-access change was made. Binary attachment uploads were blocked in the execution environment, so that GitHub release exposes tagged source archives rather than the local wheel/sdist.

The current changes prepare 0.4.1 only. Publication requires explicit authorization and exact-head review/checks. KINOCUT's previous 0.4.0 results are retained as a preliminary extraction, not final accepted archaeology after this expanded readiness review.
