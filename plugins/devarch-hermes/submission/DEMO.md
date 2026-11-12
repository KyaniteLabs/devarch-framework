# DevArch demo: hook first, under 90 seconds

Executable check (temporary profile, five local commits, no Hermes install):

```sh
python plugins/devarch-hermes/submission/demo_under_90s.py
```

The process exits 0 only when native `plugin.yaml` hooks are registered, the
archaeology brief fires, pipeline and `/devarch report` finish, the report
ledger contains that report, and the elapsed time is under 90 seconds.

## Spoken/screen sequence (target 70–80s)

- **0–12s:** Ask Hermes “How did this codebase evolve?” Show the native
  `pre_llm_call` archaeology brief: measure before guessing. Say: “This is a
  native context hook, not an MCP server wrapped in a tool.”
- **12–40s:** Run `/devarch pipeline /path/to/hermes-agent demo` on a complete
  local checkout, `max_commits=500`. Keep the elapsed clock visible. Show the
  sampled-history disclosure: full local ref count versus 500 extracted commits;
  never describe the sample as all Hermes history.
- **40–63s:** Show the Markdown report: detected signals and gap-separated
  clusters. Say: “These are measured leads, not causal conclusions. Clusters are
  not curated development eras.” Open the optional human-era section only when
  it contains real curated data; do not fabricate eras for a better video.
- **63–78s:** `/devarch status`: the native `post_tool_call` summary ledger.
  Finish on the read-only/local-only disclosure and report path.

## Reproduced component demo

The Engineering receipt mined **500 / 74,442** locally reachable commits from
hermes-agent at `90d6b98fd86d20981ee06ddd5b7d93e4320f26a4`, generated **26 signals,
3 clusters**, and completed all six vectors. Initial native API replay took
18.746s; the final attached receipt records the measured rerun. This is real
PluginManager discovery, registered tool execution, both hooks, slash report and
status, and the actual gateway ContextVar refusal — no model or gateway chat
session was launched. Timing excludes installation/network dependency downloads.
Data remains a sample; ref coverage describes the local checkout, not upstream's
complete or deleted history.

## Capture needs (not claimed recorded)

1. A real Hermes chat with DevArch enabled, approved dependency installation
   complete, and a full local hermes-agent checkout available.
2. Capture brief injection/tool call, elapsed clock, coverage, signal/cluster
   report and ledger. Hide personal paths, tokens, unrelated chats and names
   where appropriate. Use a fresh profile/project for the final recording.
3. 2:1 banner; screenshot of report coverage + signals and screenshot of ledger.
   Native proof logs/report and P16/U7 screenshot are evidence, not promo footage.
4. Export <90s MP4; verify actual media duration before Simon publishes it.
5. Simon alone posts the video/catalog PR and submits the two links on Nov 11.

If a live run exceeds the budget, lower the positive `max_commits` setting,
retain the sample disclosure, and rerun. Never present cached output as live.
