# Data-model roast (Fable, 2026-11-09 PT)

Verdict: "a competent visualisation of a commit-subject spreadsheet pretending to be a forensic model; fix identity, time and provenance before adding one more heuristic."

Top 7 fixes, ranked by user impact against effort, with their acceptance tests:
1. Real identity (email + .mailmap + is_bot). Accept: Epoch shows 1 human + bots; 0 author signals; no bot is primary_author.
2. One clock (UTC instant + offset, one project zone). Accept: 0 sort inversions; era filter and table day agree 804/804.
3. Dig manifest (head_sha, refs, pin, config hash, schema_version). Accept: two digs of same HEAD differ only in generated_at.
4. One kind, computed once; is_merge/is_revert/is_bot flags. Accept: kind_totals == work_type_distribution; merges not ops.
5. Dedupe + declare signals; drop gap signals (they repeat the era cuts). Accept: Epoch <= 15 signals, no shared cause.
6. Honest practices (word-boundary, no merges, ROI from evidence). Accept: CI/CD ~57 not 78; roi not constant.
7. Paths and tags (--numstat files table, releases). Accept: top-10 churn paths + release markers in dig.

Wrong: lexical date sort (29 inversions), offset-stripping _parse_date, mixed-zone day buckets (18% of commits), merges double-counted with zero stats, LIKE '%ci%' substring practices, dead critical_gaps branch, commit_count vs truncated commits[], index on missing repo column, empty repo provenance.
Thin: email/committer/parents/body/refs, identity table, files/paths, tags, PRs (196 "(#N)" unparsed), reverts, Co-authored-by trailers, dig manifest, incremental mine, typed/keyed schema.
Weak: two competing kind classifiers, cognitive load = len(message), magic SDLC thresholds + constant ROI, uncalibrated signals (one burst = 3 turning points), clusters promoted to eras, UI-side ERA_MIN / alias merge / hiatus guess.

## Fix status (plugin 0.2.0, 2026-11-09 PT)

Acceptance run: Epoch at a5c7eac, zone America/Los_Angeles, `bots` setting with wildcards.

| # | Fix | Result |
|---|-----|--------|
| 1 | Identity | Pass. 1 person (11 spellings), 1 agent (Claude, 5 spellings), 15 bots; 0 author signals; per-person counts exclude merges (419 + 60 bot = 479). |
| 2 | One clock | Pass. 0 sort inversions; every work commit sits in exactly one era; table day and era filter use the same server-side day. |
| 3 | Manifest | Pass. Two digs of the same HEAD differ only in `generated_at` (config hash 84a9164b8215a113). |
| 4 | One kind + flags | Pass. One shared classifier (`archaeology/classifiers/work_kind.py`, mirrored in the plugin). On Epoch's 479 work commits the framework and plugin agree on every commit; the 105 merges are flagged separately and kept out of `work_type_distribution`. |
| 5 | Signals | Pass. 73 → 10: gap and author signals dropped, same-type runs within 7 days folded, pace changes that only restate a quiet gap dropped. |
| 6 | Practices | Pass. Word-bounded, merges and bots out, ROI from evidence (not constant), each row carries n / of / target. |
| 7 | Paths and tags | Pass. Top hotspot files (generated files out) and 17 releases in the dig and on screen. |

Wrong/Thin/Weak in the plugin: lexical sort, offset stripping, mixed-zone buckets, merge double-counting, substring practices, commit_count vs truncated list, PR numbers, reverts, co-author trailers, UI-side era minimum and alias merge: all fixed. Change size replaces "cognitive load". Eras come from the plugin's gap-based cut, with the minimum in the dig's thresholds.

Framework side (`archaeology/`, commit c512180 on branch `ag4te-plugin`): all fixed.
- Git extractor records email and parents. A root commit's empty parents field is no longer stripped.
- `_parse_date` keeps the offset and returns the UTC instant.
- The era detector sorts commits by instant, buckets days by parsed date, and folds same-direction velocity runs within 7 days.
- `db/builder.py` keys commits on (repo, hash) and replaces on re-import. The docs now say FTS4, which is what the code uses.
- The SDLC gap finder is word-bounded and excludes merges. Each practice has a target share; ROI comes from the evidence; the dead `critical_gaps` branch is gone.
- Cognitive load is labelled honestly as a subject-length proxy. It excludes merges and uses the shared kind classifier.
- Tests: 346 passed, 1 skipped. That includes 6 new data-model tests. The pipeline-contract golden test was already failing; it now passes, because its masks now cover dependency and package line numbers.

The plugin pins DevArch from the public GitHub repo, KyaniteLabs/ag4te, so these fixes reach it and anyone can install it without credentials. The pin was 0f87d05 (the reconciled 0.4.1 main); it is now 6dd2299, which adds the plain-imperative verbs that cut "other" commits from 63% to 27% on UNBL0CK.
