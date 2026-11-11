---
name: ag4te
description: Read a repository's finished AG4TE dig, explain its history, or guide the AG4TE Desktop page.
---

# Read a dig and show its history

Call `ag4te_dig` without a project to list digs, then with a project id to read and select that dig on the open Desktop page; the tool reads finished digs, while `/ag4te dig`, `resume` and `stop` run or control digs locally.

Check that AG4TE is on in Desktop Capabilities -> Plugins; enabling it there is the one step a person does, then open the AG4TE page.

Call `ag4te_show` with a section, for example `{"view":"story","item_id":"origin"}` or `{"view":"commits","item_id":"<full commit SHA>"}` after selecting the project with `ag4te_dig`.

The views are `overview`, `story`, `strata`, `rhythm`, `churn`, `practices`, `turning-points`, `people`, `change-size`, `files`, `releases` and `commits`; they scroll to the page's existing cards. Optional item ids are story chapter ids, full commit or release SHAs, change-size levels, zero-based era or signal indices, or zero-based visible row indices for people and files. Item ids are 1–128 letters, digits, or `_.:-`; an absent item focuses its section. Commit focus clears filters and reveals the row when it is in the saved dig.

The tool asks the page to show a section; its reply does not confirm delivery or enable Desktop. Events are local and contain only ids, counts and states; without an open, enabled page or on older Hermes builds without the event bridge, the tools still return text. `/ag4te status <project>` prints dig status and the setup hint.

Kinds, eras, signals and practice health are rules applied to history, not a reading of the code or a measure of productivity; explain them as leads to investigate.
