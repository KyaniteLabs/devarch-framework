# DevArch for Hermes

**Disclosure first:** this Apache-2.0 plugin vendors DevArch v0.4.1 from
`b44430e198e45bfaee1edb2f3473f7d50ce17bc2` plus the patches in VENDOR.md.
Installation downloads the exact `click`, `sqlite-utils`, and `datasette` versions
in plugin.yaml from PyPI. Invocation uses the DevArch Python API directly, not
`devarch` or its MCP server. Framework internals launch local Git and
`python -m sqlite_utils` subprocesses. No account, API key, model call or paid
service is needed. Child processes inherit the host environment; this is **not**
a credential sandbox. Mining disables Git transports and lazy fetches, refuses
shallow/promisor/missing-object repositories, and never fetches remotes.

Reads target Git history; writes SQLite, extracted data, reports, lock files and
a summary ledger only under `<HERMES_HOME>/plugin-data/devarch/`. No telemetry.
Optional HTML reports reference shared design-system web fonts when opened in a
browser; use the Markdown report for an entirely offline viewing path.

## Why native, rather than an MCP wrapper?

The `pre_llm_call` hook recognizes history/evolution questions and injects an
archaeology brief before Hermes guesses at an answer. Tools measure history;
`post_tool_call` records a profile-local summary ledger. `/devarch` and a bundled
skill complete the same workflow without starting an MCP server.

| Surface | Behavior |
|---|---|
| `devarch_mine` | Extract local commits into SQLite; capped at 500 by default |
| `devarch_signals` | Measured gaps, velocity/author shifts and gap clusters |
| `devarch_report` | Markdown in the session, optional HTML path |
| `devarch_pipeline` | Mine → signals → six best-effort analysis vectors → report |
| `devarch_list`, `devarch_version` | Project inventory and vendor source pin |
| `/devarch` | mine, signals, report, pipeline, list, version, status, help |
| Hooks | archaeology brief and mine/report summary ledger |

## Install and run

Requires Git, Python >=3.10 and Hermes >=0.21.6. Catalog installation must pin the
**accepted merge SHA**, not a moving branch. Before catalog submission, use the
exact reviewed checkout locally:

```sh
hermes plugins validate /path/to/devarch-framework/plugins/devarch-hermes --install-deps --json
hermes plugins install KyaniteLabs/devarch-framework --subdir plugins/devarch-hermes
hermes plugins enable devarch
```

The unpinned repository install above is for local development only. Follow
`submission/CLICK-PACKET.md` for pinned catalog preparation.

```text
/devarch pipeline /path/to/full/local/checkout demo
/devarch report demo
/devarch status
```

Ask: “How did this codebase evolve?” The hook supplies the evidence-first brief;
Hermes still needs a local repository path before mining.

## Integrity and concurrency

- Reports disclose full local ref coverage **and the extracted sample count**.
  Capped results are not a complete-history claim. Deleted, inaccessible and
  unfetched refs remain outside coverage; shallow history is rejected, not
  relabeled as sampling.
- A per-project reentrant transaction covers mine, signals, export and the whole
  pipeline, with thread and OS file locks. Separate projects remain independent.
- Raw files, DB and present metrics/signals/clusters are checked against their
  mining generation and hashes. Failed remining cannot export stale evidence.
  This is consistency checking, not signed/tamper-proof forensic custody.
- The patched vendor has an isolated namespace. An installed `archaeology` package
  neither replaces it nor gets replaced by it.
- Gap clusters are **not curated eras**. Human `commit-eras.json` survives mining
  and signal detection. Vectors are keyword investigation leads, never causal
  conclusions or productivity scores.
- Gateway slash mine/pipeline/report are disabled by default. Agent tools retain
  local filesystem authority; the slash restriction is not tool authorization.

## Settings (`plugins.entries.devarch.settings`)

| Key | Default | Meaning |
|---|---|---|
| `inject_on_archaeology` | true | Hook brief |
| `allow_repo_slash_on_gateway` | false | Explicit slash opt-in |
| `max_commits` | 500 | Positive hard extraction cap across local refs |
| `max_commits_warn` | 5000 | Warn about full local history size |
| `default_project` | session | Project used when omitted |

## Verification

From the framework root, with plugin dependencies and pytest/ruff installed:

```sh
PYTHONPATH="$PWD" python -m pytest -q --tb=short
ruff check . && ruff format --check .
hermes plugins validate plugins/devarch-hermes --json
```

Fresh-process plugin-only tests run with and without an incompatible installed
framework. Deterministic schedules cover mine/mine, signals/mine and report/mine;
content/generation/binding mutations are rejected. See the card's evidence packet
for native PluginManager/tool-registry/hooks/slash execution, network tracing,
hermes-agent demo timing, and the installed-wheel P16/U7 replay in
`submission/P16-U7-RECEIPT.md`. Run `python plugins/devarch-hermes/submission/demo_under_90s.py`
for the native hook path (it exits non-zero at 90 seconds). A native API harness
is not a live deployed chat session or a post-merge Product acceptance.

## Rollback

Disable with `hermes plugins disable devarch`. Target repositories need no
rollback because they are read-only. Preserve plugin-data if you need its
reports; deleting that directory is a separate deliberate data-loss decision.

Demo/capture and Simon-only catalog steps: `submission/`.
