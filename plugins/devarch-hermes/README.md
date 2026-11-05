# DevArch for Hermes (native plugin)

**Git repository archaeology** — mine a local checkout's full commit history, detect development signals (gaps, velocity shifts, author changes), and export an evidence-backed eras/signals report before the agent touches the code. Wraps DevArch Framework `v0.4.1` pinned to commit `b44430e198e45bfaee1edb2f3473f7d50ce17bc2`.

| Surface | What it does |
|---|---|
| `pre_llm_call` | When a message asks about repo history / evolution / eras, injects an archaeology brief |
| `post_tool_call` | Appends mine/report summaries (project, commits, signal count, paths — **no commit bodies**) to a ledger |
| `/devarch mine\|signals\|report\|pipeline\|list\|version\|status\|help` | Gateway-safe by default: `mine`/`pipeline`/`report` refused on gateway unless `allow_repo_slash_on_gateway: true` |
| `devarch_mine` | Mine full local history into plugin-data (rejects shallow clones) |
| `devarch_signals` | Heuristic signal detection (investigation leads) |
| `devarch_report` | Markdown/HTML report with truncated body for the session |
| `devarch_pipeline` | One-shot mine → signals → (best-effort) vectors → report |
| `devarch_list` / `devarch_version` | Projects under plugin-data / framework version |
| Skill `devarch:devarch` | Ask → pipeline → lead-with-eras/signals workflow |

## Install

```bash
hermes plugins install KyaniteLabs/devarch-framework --subdir plugins/devarch-hermes
hermes plugins enable devarch
```

Requires **Python ≥ 3.10**, `git` on PATH, and the `pip_dependencies` install of `devarch-framework` (runs on `plugins install` / `validate --install-deps`).

## Disclosure

- **Vendored code:** this plugin ships the DevArch `archaeology` package pinned to commit `b44430e198e45bfaee1edb2f3473f7d50ce17bc2` (see `VENDOR.md`). PyPI deps `click`, `sqlite-utils`, `datasette` install into the Hermes venv on `plugins install` / `validate --install-deps`.
- **Network:** mining is **local-only** — it runs `git` against the checkout you name and never fetches remotes. No telemetry.
- **Filesystem:** project DBs, signals, reports and the ledger live under `<HERMES_HOME>/plugin-data/devarch/` (per profile). The target repo is read-only.
- **Integrity:** shallow clones are refused; coverage (refs, commit count, head) is recorded beside the extraction. Analysis vectors are **keyword investigation leads**, not verified conclusions or productivity measurements.
- **Secrets:** no child process, no env scrubbing needed for a subprocess; no API keys required. Only public `ctx.*` APIs.
- **Gateway:** `/devarch mine|pipeline|report` refused on gateway platforms unless `allow_repo_slash_on_gateway: true`. Agent tools still work.
- **No background jobs;** nothing runs unless a hook matches or you call a tool/slash.

## Settings (`plugins.entries.devarch.settings`)

| Key | Default | Notes |
|---|---|---|
| `inject_on_archaeology` | `true` | pre_llm_call brief |
| `allow_repo_slash_on_gateway` | `false` | gateway safety |
| `max_commits_warn` | `5000` | soft warning only |
| `default_project` | `session` | default project name |

## Known issues

- First `validate --install-deps` / install pulls datasette + sqlite-utils from PyPI.
- Very large histories (>max_commits_warn) still mine but take wall-clock; prefer a dedicated project name.
- No Desktop pane, 2:1 banner, or screenshots yet.
- PyPI `devarch-framework` is not published at 0.4.1 yet; the plugin vendors the package instead. Datasette/sqlite-utils still need the usual ≥3-day age before catalog merge.

## Demo (< 90s)

```text
/devarch version
/devarch pipeline /path/to/some/repo demo
/devarch status
```

Or ask the agent: "How did this codebase evolve?"

License: Apache-2.0 (same as DevArch Framework).
