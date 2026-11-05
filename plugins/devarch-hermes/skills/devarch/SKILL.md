---
name: devarch
description: >-
  Use when the user asks how a local git repository evolved, wants eras/signals
  from commit history, or needs an evidence-backed archaeology report before
  changing code. Mine locally, label vectors as leads, refuse shallow clones.
---

# DevArch archaeology (Hermes)

Three laws:
1. **Local history only.** Mine the checkout on disk; do not invent eras from a handful of recent commits you happened to see.
2. **Leads, not conclusions.** Automated vectors and signals are keyword investigation leads — never present them as verified causal explanations or productivity scores.
3. **Integrity first.** Shallow clones are a hard refuse. Report coverage (commit count, head, shallow=false) beside any claim.

## Workflow
1. Confirm a local git path (worktree with `.git`, or bare repo).
2. Prefer `devarch_pipeline` with `repo_path` (and an optional `project` name). Fall back to `devarch_mine` → `devarch_signals` → `devarch_report`.
3. Lead the answer with eras + top signals from the report markdown; cite the `output_path` under plugin-data.
4. If mine fails for shallow history, tell the user to `git fetch --unshallow` (or reclone full) and stop.
5. Do not modify the target repository.

`devarch_list` shows projects already mined under `<HERMES_HOME>/plugin-data/devarch/`.
