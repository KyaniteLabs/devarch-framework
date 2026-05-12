# Sync Rules

Reference material (L3). Load when syncing from DEV-ARCH or modifying framework internals.

## Parity with DEV-ARCH

- This repo must maintain 100% feature parity with DEV-ARCH
- DEV-ARCH is the LAB (working version with real data)
- This repo is the PRODUCT (sterilized, publishable version)
- Never contain real project data (no LIMINAL, no sessions, no YouTube data)
- Use only synthetic/demo data in projects/

## When DEV-ARCH changes

- New CLI commands → copy command function to this repo's cli.py
- New Python modules → copy to this repo's archaeology/ package
- New templates → copy to this repo's archaeology/visualization/
- New analysis vectors → copy analysis-vectors/*.md
- New config → copy config/ files
- After sync: run `python3 scripts/sync/check_parity.py --dev-arch /path/to/DEV-ARCH` to verify

## Verification

- Run `python3 -m archaeology.cli demo --force --build-db` after changes
- Run `python3 -m archaeology.cli audit demo-project` to verify quality gate
- The demo project must always work end-to-end

## Git Workspace Hygiene

Agents must leave the repository in the same clean state they found it. No exceptions.

- **Delete feature branches** after merge — whether you merged via PR or locally
- **Remove worktrees** when done. No orphaned worktrees
- **Clean up stale references** — `git remote prune origin`
- **No abandoned work left behind** — delete cancelled/superseded branches
- **Local branches stay current** — rebase against upstream regularly
- **Worktree state matches intent** — `git status` should show nothing when done

## Epoch Data Tracking

Every project must use Epoch (KyaniteLabs/Epoch) for time estimation and actively feed it data.

- **Before starting a task** — get a time estimate from Epoch (via MCP, REST API at `localhost:3099`, or CLI)
- **After completing a task** — record actual time using `record_actual` or `POST /v1/feedback/record-actual`
- **Include context** — task type, complexity, tools used
- **Batch submissions OK** — use `batch_record_actuals` for multiple estimates

Integration options:
- MCP: add `@puenteworks/epoch` to project's `.mcp.json`
- REST API: `epoch serve --port 3099`
- CLI: `npx @puenteworks/epoch pert-estimate ...`
