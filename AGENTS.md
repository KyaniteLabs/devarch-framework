# KyaniteLabs Engineering Rules

**Repository**: devarch-framework
**Description**: Forensic repository archaeology framework for git history analysis, development signals, and engineering narrative reports.
**Tech Stack**: Python

This file provides operating instructions for all AI coding agents working in KyaniteLabs repositories. It is the AGENTS.md mirror of CLAUDE.md — both files contain identical rules.

See KyaniteLabs/.github for org-wide rules. Project-specific rules below:

## Project-Specific Context

This is the **devarch-framework** repository. It is Forensic repository archaeology framework for git history analysis, development signals, and engineering narrative reports..

# KyaniteLabs Engineering Rules

This file provides operating instructions for all AI coding agents working in KyaniteLabs repositories. It is the AGENTS.md mirror of CLAUDE.md — both files contain identical rules.

## Organization Principles

- **Local-first when it matters** — keep data, creative work, and knowledge close to the people who own it
- **Useful over flashy** — solve real workflow problems
- **Human-in-the-loop by design** — AI accelerates judgment, it doesn't erase it
- **Open where it helps** — public projects are documented for discovery and reuse
- **Craft matters** — README quality, tests, and maintenance are part of the product

## Issue-Driven Development

All contributions to KyaniteLabs repos flow through GitHub issues.

### Workflow

```
External contributor opens issue
  → Template applies: bug/enhancement + needs-triage label
  → Maintainer reviews, adds: approved label
  → Auto-triage promotes to: agent-ready label
  → Pipeline picks up → creates fix PR

Owner/member (Pastorsimon1798) opens issue
  → Auto-triage detects member author
  → Promotes directly to agent-ready (skips triage)
  → Pipeline picks up → creates fix PR
```

### Label System

| Label | Meaning | Who sets it |
|-------|---------|------------|
| `needs-triage` | New issue, awaiting review | Issue template (auto) |
| `approved` | Maintainer approved for work | Maintainer (manual) |
| `agent-ready` | Ready for pipeline to pick up | Auto-triage (auto) |
| `bug` | Bug report | Issue template (auto) |
| `enhancement` | Feature request | Issue template (auto) |
| `repo-pipeline` | Created by pipeline scanner | Pipeline (auto) |
| `ci-failure` | CI broke on main branch | Pipeline (auto) |
| `severity:low/medium/high/critical` | Impact level | Pipeline (auto) |

### Rules for Agents Creating Issues

- Never create issues without the `repo-pipeline` label
- Always include reproduction steps or evidence
- Set severity based on: does it break main? does it affect users? is it cosmetic?
- Link to the relevant CI run, commit, or file

## Pipeline Awareness

The GITHUB_pipeline runs a triage cycle every 30 minutes. When working in KyaniteLabs repos, be aware:

1. **Your PRs will be monitored** by `pr-maintainer.py` — it fixes CI failures, rebases, and addresses review comments
2. **Do not delete `fix/issue-*` branches** — the pipeline manages these
3. **Pipeline-created issues** have the `repo-pipeline` label — treat them as real issues
4. **Circuit breaker** — if the pipeline enters RED state, all automated work stops until manually reset
5. **Issue priority** — pipeline sorts by severity (critical > high > medium > low), then by age

## CI Standards

All KyaniteLabs repos must have these CI checks (via GitHub Actions on Blacksmith runners):

### Required Checks (must pass before merge)

| Check | Tool | Config |
|-------|------|--------|
| Lint | ruff | `ruff check . && ruff format --check .` |
| Test | pytest | `pytest --tb=short -q` |
| Build | pip install | `pip install -e .` (Python) or equivalent |

### Recommended Checks (add when applicable)

| Check | Tool | When |
|-------|------|------|
| Security scan | bandit + pip-audit | Python repos |
| Type check | mypy | repos with type annotations |
| Docker build | docker build | repos with Dockerfile |
| Package surface | custom script | published packages |
| Compatibility matrix | multi-Python/Node | public packages |

### CI Rules

- All CI runs on `blacksmith-2vcpu-ubuntu-2404` runners
- CI must pass on all supported Python/Node versions
- Never skip CI (`--no-verify`) — if it fails, fix the root cause
- CI failures on main get auto-detected by the pipeline

## Branch Protection

All `main`/`master` branches in KyaniteLabs repos are protected:

- No direct pushes — everything through PRs
- Required status checks must pass
- Branches must be up-to-date before merge
- Force pushes blocked
- Linear history required (squash or rebase merge)

## Repository Standards

### Python Repos
- **Formatter**: ruff (not black)
- **Linter**: ruff
- **Config**: `pyproject.toml` (not setup.py/setup.cfg)
- **Python**: minimum 3.11, test on 3.11 and latest
- **Dependencies**: pin exact versions

### Node/TypeScript Repos
- **Package manager**: pnpm (not npm/yarn)
- **Formatter**: prettier
- **Linter**: eslint

### All Repos
- **README.md**: Must explain what it is, how to run it, how to test it
- **CHANGELOG.md**: Updated with every release
- **LICENSE**: MIT (org default)
- **CONTRIBUTING.md**: Points to org contributing guide

## Agent Coordination

When multiple agents work on the same repo:

1. **Claim your scope** — note in the issue which files/areas you're working on
2. **Don't edit files another agent is actively modifying** — check open PRs first
3. **Rebase frequently** — pull from main before pushing to avoid conflicts
4. **Test before pushing** — run the same CI checks locally first
5. **Communicate via issues** — leave comments on issues for context, not in code

## Code Quality Rules

### Dependency Discipline
- Never add a dependency for something 20 lines of stdlib can do
- Never add a dependency without checking it's actively maintained (commits in last 6 months)
- Pin exact versions in requirements, never ranges
- When you add one, write a one-line comment explaining why

### Error Handling
- Validate at system edges only (user input, API responses, file reads)
- Trust internal code — no try/except around your own functions unless the operation is genuinely fallible (network, disk)
- Never catch `Exception` broadly — catch the specific failure mode
- Errors must be actionable: tell the human *what* broke and *what to do*

### No Orphaned Code
- Every function must be called by something (tests count)
- Every file must be imported by something
- No dead config, no unused imports, no commented-out code blocks
- If you write it, wire it up or delete it

### Security Non-Negotiables
- Never use `shell=True` with user input
- Never hardcode secrets, tokens, or API keys
- Always validate file paths (no path traversal)
- Always use parameterized queries for database interaction
- Always use HTTPS for external calls
- Sanitize any string that becomes part of a command, HTML, or SQL

### Testing
- Test behavior, not implementation
- One assertion per concept
- Test the unhappy path — what happens when the API is down, the file is missing, the input is garbage
- Integration tests over unit tests for anything touching external systems
- No mocking what you don't own unless the real thing is destructive or slow

### Documentation
- README must answer: what is this, how do I run it, how do I test it
- Public functions get a docstring only if the name doesn't explain itself
- No docstrings on private functions — rename them instead
- CHANGELOG entries for every user-visible change

### Git and PR Hygiene
- Commits tell *why*, not *what* (the diff shows what)
- PRs under 400 lines of meaningful change
- Every PR describes how it was verified
- No merge commits on feature branches — rebase

### Git Workspace Hygiene
Agents must leave the repository in the same clean state they found it. No exceptions.

- **Delete feature branches** after merge — whether you merged via PR or locally. A merged branch that still exists is a failure.
- **Remove worktrees** when done. If you created a git worktree for isolated work, remove it when the work is complete or abandoned. No orphaned worktrees.
- **Clean up stale references** — prune remote-tracking branches that no longer exist upstream (`git remote prune origin`).
- **No abandoned work left behind** — if you started a branch, pushed it, and then the task was cancelled or superseded, delete the branch. Dead branches accumulate and confuse everyone.
- **Local branches stay current** — regularly rebase local tracking branches against their upstream. If a local branch has diverged and is no longer needed, delete it.
- **Worktree state matches intent** — if you're done with a task, the working directory should be clean (`git status` shows nothing). Staged changes, untracked files, and modified files from abandoned work are not acceptable.

The rule is simple: finish your work, merge or discard it, clean up every artifact you created. The main branch is the only permanent artifact. Everything else is temporary and must be treated as such.

### Epoch Data Tracking

Every project must use Epoch (KyaniteLabs/Epoch) for time estimation and actively feed it data. Epoch only becomes useful when it has real estimate-vs-actual data from real projects.

### What This Means
- **Before starting a task**, get a time estimate from Epoch (via MCP, REST API at `localhost:3099`, or CLI)
- **After completing a task**, record the actual time spent using `record_actual` or `POST /v1/feedback/record-actual`
- **Include context** — task type, complexity, tools used, anything that helps the model learn
- **Batch submissions are fine** — use `batch_record_actuals` for multiple estimates at once

### Integration
- MCP: add `@puenteworks/epoch` to your project's `.mcp.json`
- REST API: `epoch serve --port 3099`
- CLI: `npx @puenteworks/epoch pert-estimate ...`

### Why This Is Non-Negotiable
Epoch's accuracy improves with data. Without estimate-vs-actual feedback from real projects, it's just a calculator with uncalibrated assumptions. Every project that uses Epoch and reports back makes every other project's estimates better. This is a collective intelligence system — it only works if everyone contributes.

The data stored in `~/.epoch/` (estimates.jsonl + feedback.jsonl) is the project's most valuable asset. Protect it, back it up, and keep feeding it.

### Performance
- No N+1 queries
- No loading full datasets into memory — paginate or stream
- No regex in hot loops
- If you add a cache, also add a cache invalidation strategy

### Configuration
- Magic numbers become named constants
- Tunable behavior becomes config/env vars, not code changes
- Default config works for development without modification

## KyaniteLabs Tech Stack Standard

Every project in KyaniteLabs follows these stack decisions. No exceptions without explicit approval.

### TypeScript Projects
- **Zero `.js`/`.jsx` files.** Everything is `.ts`/`.tsx`. If a file is JS, convert it.
- **`tsconfig.json`: `strict: true`, `target: ES2022`, `module: NodeNext`.** No `any` without a justifying comment.
- **Package manager: pnpm.** Never npm, never yarn. If a repo uses npm, migrate it.
- **Formatter: prettier.** Linter: eslint with typescript-eslint. Both configured from day one.
- **Test: vitest.** Not jest.
- **Build: tsup** for libraries, **tsc** for applications.
- **Import style: ESM only.** `"type": "module"` in package.json. No CommonJS (`require`, `module.exports`).

### Python Projects
- **Python 3.11 minimum.** Test on 3.11 and latest.
- **Config: `pyproject.toml` only.** No setup.py, no setup.cfg, no requirements.txt. Dependencies go in `[project.dependencies]`.
- **Build backend: hatch.** Not setuptools.
- **Formatter: ruff format.** Linter: ruff. Not black, not flake8, not isort.
- **Test: pytest** with `--tb=short`.
- **Entry points: `[project.scripts]`** in pyproject.toml, not `if __name__ == "__main__"`.

### Dart/Flutter Projects
- **Dart only.** No embedded JS unless Flutter requires it.
- **Package manager: pub.**
- **Test: flutter_test.** Lint: `flutter analyze`.

### Cross-Cutting Rules
- **One language per project.** No Python+JS repos, no TS+JS mixing.
- **One package manager per project.**
- **Dependencies pinned to exact versions.**
- **Editorconfig** in every repo root for consistent indentation.

## Project Scaffolding

When Kyan (operations agent) receives a project idea via Telegram:

### Phase 1: Research
1. Find latest official documentation for the relevant framework/library
2. Check latest stable versions — pin all dependencies exactly
3. Check GitHub Advisories for security issues in chosen dependencies
4. Check community best practices (recent posts, discussions)
5. Check if an existing KyaniteLabs repo solves a similar problem

### Phase 2: Classify
Determine project type and apply matching tech stack from the rules above.

### Phase 3: Scaffold
Create a private repo in Pastorsimon1798's personal account with:

**Every project gets:**
- `.gitignore`, `.editorconfig`, `LICENSE` (MIT)
- `README.md` (what, why, run, test), `CHANGELOG.md`
- `CLAUDE.md` + `AGENTS.md` (from org templates + project-specific)
- `.cursorrules` + `.windsurfrules` (from org templates)
- `.github/copilot-instructions.md`, `dependabot.yml`, `CODEOWNERS`
- `.github/workflows/ci.yml` (lint + test + build, Blacksmith runner, concurrency, caching)
- `.github/ISSUE_TEMPLATE/` (bug_report.yml, feature_request.yml, config.yml)

**Python additionally:** pyproject.toml (hatch), src/project_name/__init__.py, tests/test_smoke.py
**TypeScript additionally:** package.json (type:module), tsconfig.json (strict), eslint.config.js, .prettierrc, vitest.config.ts, src/index.ts

### Phase 4: Verify
- Initial commit + push
- Branch protection on main
- CI runs green
- Parity check (CLAUDE.md = AGENTS.md)
- Report to user: repo URL, stack, CI status

## Local-First Inference (LM Studio)

All KyaniteLabs projects that require an LLM must use local inference first. Server runs on Tailscale at `100.66.225.85:1234`.

### Server Specs
- **CPU**: AMD Ryzen AI Max 395 (Strix Halo) — 16 cores, 32 threads
- **Memory**: 96GB unified RAM, 48GB VRAM (shared pool)

### API Quick Reference
| Action | Method | Endpoint | Body |
|--------|--------|----------|------|
| List loaded models | GET | `/v1/models` | — |
| Load a model | POST | `/api/v1/models/load` | `{"model": "<key>"}` |
| Unload a model | POST | `/api/v1/models/unload` | `{"instance_id": "<key>"}` |
| Chat completion | POST | `/v1/chat/completions` | OpenAI-compatible |

### Loading Rules
1. **Check before loading** — call `GET /v1/models` first, reuse if already loaded
2. **Do not touch models you did not load** — other agents or processes depend on them
3. **Unload when done** — call unload endpoint after task completes
4. **No downloading** — only use models already on the server
5. **Always enable**: flash attention, KV cache quantization at Q8, full GPU offload
6. **CPU thread pool: 10 threads** (formula: 16 cores × 0.625)
7. **Memory budget**: keep 16GB free, max ~80GB for LLM usage

### Inference Sampling Profiles
| Profile | Temp | top_p | top_k | repeat_penalty | min_p |
|---------|------|-------|-------|----------------|-------|
| Coding | 0.0-0.1 | 0.95 | 40 | 1.0 | 0.05 |
| Reasoning | 0.6-0.7 | 0.9 | 40 | 1.1 | 0.05 |
| Creative | 0.8 | 0.92 | 45 | 1.05 | 0.04 |
| Deterministic | 0.0 | 1.0 | 1 | 1.0 | 0.0 |

<!-- EMPOWER_ORCHESTRATOR:START -->
## Empower the Orchestrator

This repository is governed by the Empower Orchestrator law. Every top-level/orchestrator agent session is an audition to improve the system, not only finish the current task.

When you notice a repeatable task done 3+ times or a recurring agent failure mode, consider shipping the smallest durable artifact that prevents the repetition: a tool, skill, slash command, hook, guardrail, memory entry, test, verifier, or doctrine doc.

This applies to top-level/orchestrator sessions. Background workers execute their assigned slice and do not independently widen scope.

Before dispatching automation or creating a durable system change, state the four-question blast-radius check in chat:

1. Scale: one file/workspace/all sessions?
2. Severity: minor friction/broken workflow/data loss or leaked content?
3. Reversibility: single revert/manual cleanup/surgery?
4. Predictability: bounded failure mode/guessing/unknown?

All green permits auto mode. Any yellow requires inline human approval. Any red means do not dispatch; do the work inline or escalate.

Worker discipline: isolated worktree/sandbox, one artifact equals one commit/change unit, verify before commit, register through the target tool's native discovery surface, and never write outside the assigned scope.

Success line: “I noticed X, found a better way. The system just got an upgrade.”

Full recipe: `docs/agent-law/empower-orchestrator.md`.
<!-- EMPOWER_ORCHESTRATOR:END -->
