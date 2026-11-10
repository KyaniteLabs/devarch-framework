# AG4TE Desktop: impact prediction (written before ship)

Written 2026-11-09 PT, before the plugin is installed on the home server's Hermes.
Compare against reality after ship. Do not edit the predictions below; add results under "Reality".

## Who the end user is
A developer (first: Simon) opening AG4TE in Hermes Desktop to understand a repo's history:
"what happened, when, by whom, and what should I fix?"

## Predictions (each is checkable)

| # | Prediction | How we check | Confidence |
|---|-----------|--------------|------------|
| P1 | First useful answer in under 2 minutes from opening the tab on an already-dug repo (read headline, spot eras, find one turning point). | Time Simon's first session; ask "what did you learn?" | 70% |
| P2 | A first dig of an ~800-commit repo finishes in under 5 minutes on the home server, and Stop/Resume works without a restart of Hermes. | Time a real dig; press Stop mid-run, then Resume. | 65% |
| P3 | Zero honesty complaints: no "the chart says X but that didn't happen" (no invented data in gaps, no fake decline in the last week, correct counts). | Simon's reactions over the first week. | 75% |
| P4 | The stone and strata get the "beautiful" reaction again; the most-used new features are the numbered turning points and the core-sample era filter. | Ask which parts he used; watch the session. | 55% |
| P5 | Practice health produces at least one action Simon actually takes (a card or a fix) in the first week. | Count cards/commits citing an AG4TE practice row. | 40% |
| P6 | The weakest spot users will hit is the DATA, not the UI: author aliases, conventional-commit-only kind classification, and signal thresholds will produce at least one "that's wrong" moment. | First-week feedback. Cross-check with the Fable data-model roast. | 70% |
| P7 | No Hermes breakage: the plugin adds no backend on the Mac mini, and the gateway needs no extra restarts beyond the one install reload. | Gateway restart log; Mac mini has no Hermes backend process. | 85% |
| P8 | Touch/keyboard users can reach every tooltip and filter (24px targets, arrow keys, Enter/Space on the core). | Keyboard-only pass and a tap pass in tastecheck. | 70% |

## What I expect will NOT change
- It will not tell you *why* something happened; it shows when and what kind.
- Repos without conventional commits will look mostly "Other".
- Multi-repo comparison does not exist yet.

## Reality (fill after ship)
- Ship date / revision:
- P1:
- P2:
- P3:
- P4:
- P5:
- P6:
- P7:
- P8:
- Surprises:

## Pre-ship evidence (not a result, just early signal)
- P6: the Fable data-model roast (docs/DATA-MODEL-ROAST.md, 2026-11-09) found the data issues before any user did: author aliases, mixed time zones, regex-only kinds, and duplicate signals.
