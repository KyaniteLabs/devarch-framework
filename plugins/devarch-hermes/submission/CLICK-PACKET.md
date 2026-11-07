# Simon's Nov 11 click packet — do not execute before acceptance

**Hold:** implementation PR94 remains DRAFT. Engineering must not merge it or
open the catalog PR. Independent Kai/Security review, exact-head CI and Simon's
merge click precede final catalog preparation. A candidate head SHA is not the
accepted merge SHA. The prepared candidate entry proves schema shape only.

## 1. After review/CI acceptance, Simon merges PR94

Read the review and CI, confirm all holds resolved, then use GitHub's merge UI.
Read back the resulting merge SHA; do not infer it from the pre-merge head.

```sh
META=$(gh pr view 94 --repo KyaniteLabs/devarch-framework --json state,mergeCommit)
MERGED_SHA=$(printf '%s' "$META" | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["state"]=="MERGED", "PR94 is not merged"; print(d["mergeCommit"]["oid"])')
git -C /path/to/devarch-framework fetch origin main
git -C /path/to/devarch-framework cat-file -e "$MERGED_SHA^{commit}"
python3 /path/to/devarch-framework/plugins/devarch-hermes/submission/prepare_catalog.py --sha "$MERGED_SHA" --out /path/to/click-packet
```

The generator rejects malformed/non-full SHA strings; it does not check remote
acceptance, push or publish. Above readback is the acceptance precondition.
Validate the merged plugin checkout again, including actual dependency install
in a disposable supported Hermes runtime. Never mutate the production gateway
venv merely to prepare this submission. Refresh screenshots/banner/video if the
accepted code differs from the captured code.

## 2. Personal-fork catalog PR (Simon only, Nov 11)

Use Simon's **personal** authenticated account; verify it with `gh auth status`.
The target is `NousResearch/hermes-agent`, not a separate hermes-plugins repo.
Do these in a fresh writable checkout, never on the nucbox runtime source.

```sh
gh repo fork NousResearch/hermes-agent --clone --remote
cd hermes-agent
git remote -v
# Ensure origin is Simon's personal fork and upstream is NousResearch/hermes-agent.
git fetch upstream main
git switch -c hackathon/devarch upstream/main
cp /path/to/click-packet/devarch.yaml plugin-catalog/devarch.yaml
python3 scripts/validate_plugin_catalog.py --json plugin-catalog/devarch.yaml
hermes plugins validate /path/to/merged/devarch-framework/plugins/devarch-hermes --install-deps --json
```

Inspect the single-file diff; `sha` and `docs_url` must contain `MERGED_SHA`.
Add the real 2:1 banner and capture URLs only after those assets exist at that
pin; omit optional image fields rather than inventing URLs. Reconcile current
catalog rules/duplicate listings on the day. Use `PR-BODY.md`, add exact final CI,
review, validation and media URLs, and append Simon's current required signature.

```sh
git add plugin-catalog/devarch.yaml
git commit -m 'feat(catalog): add native DevArch archaeology plugin'
git push -u origin hackathon/devarch
gh pr create --repo NousResearch/hermes-agent --base main --head 'SIMON_PERSONAL_LOGIN:hackathon/devarch' --title 'Add DevArch: native evidence-before-edits archaeology' --body-file /path/to/final-PR-BODY.md
```

Replace `SIMON_PERSONAL_LOGIN` with the verified personal fork owner. Simon opens
this PR; this packet does not. Read back its head/file/diff and checks before
sharing the link. Simon posts the <90s demo tagging @NousResearch and submits
catalog PR + demo links to https://form.typeform.com/to/FwJLvOln.

## Review/rollback

Exposure: no server, account, credentials or invocation-time network; local Git
and SQLite child processes remain host-authority code. Optional HTML viewing
requests web fonts. Data stays profile-local. Revert/disable the plugin; retain
plugin-data for evidence. No target repo change requires rollback. Catalog
publication is a separate Simon approval/click, not implied by validation.
