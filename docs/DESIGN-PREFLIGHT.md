# Design preflight: AG4TE stone (in-app agate cross-section)

TLDR: the stone in the AG4TE pane must read as the iris agate in the logo, with fine concentric colour banding around a dark core, even when a repo has one era or mostly unclassified commits.

## 1. Purpose
AG4TE turns a repo's git history into strata. The stone is the signature view: eras as bands, oldest at the rim. User outcome: one glance tells you how the repo's work was layered over time.

## 2. Title ↔ stone ↔ purpose
| Item | Value | Evidence class |
|---|---|---|
| Title | AG4TE (agate) | Simon's pick, 2026-11-09 (memory devarch-ag4te-name) |
| Stone | Iris agate: fine concentric rainbow bands of cyan, violet, magenta and green on a dark core | Locked logo #5, `branding/ag4te-1024.png` |
| Purpose fit | Agates fill from the rim inward in layers, like a history | Mineral fact: agate is banded chalcedony deposited in successive layers (Wikipedia, "Agate") |

## 3. Rejected metaphors
- Flat grey rings for unclassified or short eras. They read as a "weird grey donut" (Simon, 2026-11-10).
- Thick monolithic slices per kind. Real agate shows fine lines, not wedges of paint.

## 4. Material reference
- Habit: concentric, wavy, fine bands. Milky translucent chalcedony layers sit between the coloured layers.
- Family renders: `branding/ag4te-1024.png` (logo) and the banner stone in `plugins/ag4te-hermes/docs/banner.png` (the mockup Simon likes).

## 5. Family icon law and form
The stone is a data view, not the icon, so it does not replace the mark. How to read it: the rim is the oldest work and the core the newest. Each era's thickness follows the square root of its commit count. Inside an era, commits are laid in time order, rim to core, and each kind's band thickness equals its share of the era's commits. Resolution follows pixels: one striation per commit when a commit is at least 1.5px thick, otherwise time-ordered chunks of at least 3px. White lines mark era boundaries; dark seams mark quiet gaps of 7+ days. Checked by `plugins/ag4te-hermes/tests/test_stone_layout.py`; decision trail in `.audit/ag4te-stone.tsv`.

## 6. Typography
Unchanged. The caption uses the UI's secondary text.

## 7. Platform conventions
| Surface | Convention | Status |
|---|---|---|
| Hermes Desktop plugin pane | Uses the pane's theme tokens; the stone is SVG | kept |

## 8. UI colour
- Kind colours stay the validated `PALETTE`.
- In the stone only, "other" and unclassified commits render as milky chalcedony (pale lavender, translucent) instead of flat grey. **Assumption:** this reads as natural agate, not as missing data. The tooltip still names the kind "Other".
- Short eras (unnumbered) keep their real kind colours at lower opacity instead of turning grey.
- No brown or orange.
