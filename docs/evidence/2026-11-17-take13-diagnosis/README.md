# Why take 13 selected no member (diagnosis, 17 November 2026)

Take 13 (English-only app, gpt-5 at minimal reasoning effort, scope 10) showed two puzzling results:
(a) the new item "Weekend hike up the mountain" got "match" with a quotation and "1 of 1 checks passed", yet
"not selected"; (b) item 2894 ("Laojun Peak reappears sea of clouds") was a match but was rejected by the
independent evidence check, so the new category had 0 members and the feed did not change (2100 -> 2100).

**Selection rule** (`feedctrl/lab_workflows.py`, `classify_members` and `add_items_preview`): an item is selected
only if the classifier's verdict is "match" AND its quotation is found in the named field of the item AND the
independent check (a separate call that sees the definition, the item and the quotation, not the verdict)
returns `supports: true`. The rule is correct and unchanged.

Reproduction through the normal workflow functions (`tools/diagnose_new_category.py`, every request and
response saved; files with item text kept outside git in `FINAL2/receipts/r5-diagnosis/`), with the take 13
definition, the five news categories hidden and scope 10:

| Run | 2894 | Hike item | Recipe item (negative control) | 4367 (negative control) |
| --- | --- | --- | --- | --- |
| gpt-5, effort minimal (take 13 setting) | match, quote found, check: does not support -> not selected | match, quote found, check: does not support -> not selected | not_match | not_match |
| gpt-5, effort low (measured setting) | match, quote found, check: supports -> selected; top ten changes (2894 to rank 1) | match, quote found, check: does not support -> not selected | not_match | not_match |

So both rejections came from the independent check, and they are valid under that definition: the model-proposed
definition required that "the main visual subject must be the natural environment rather than ... urban-only
views", which item text can rarely establish, and the hike description stresses "a view over the city".

Defects found and fixed (regression tests in `tests/test_lab.py`):
1. **Scope ignored the applied controls.** The scope was the top N of the *base* ranking, so 5 of the 10 items
   classified in take 13 (8958, 1116, 6001, 10217, 6090) were items the user had already hidden. The scope is now
   the top N of the user's current feed after the applied controls (`KuaiRecLab.scope`).
2. **The new-item review hid the reason.** The independent check's verdict of a new-category match was not shown,
   and "1 of 1 checks passed" counted only label existence. Each match now adds a check line ("verdict match,
   quotation found, independent check does not support -> not selected") and the review shows the check and its reason.
3. **Definitions asked for what text cannot show.** The definition prompt (not a measured prompt) now asks for
   conditions that the item text (title, description, tags) can establish.

Dry run for take 14 (scope 50, low effort, model-proposed definition from "Videos about dogs: a pet dog, a puppy
or a named dog is part of the story."), gpt-5 and gpt-5-mini both: members 2882, 8902, 7564; after Apply the top
ten changes (8902 and 7564 enter, 10184 and 8777 leave); the new item "Our puppy's first walk in the park" joins
the category; the recipe item and item 4367 do not. The new item starts at the user's median score and does not
enter the top ten by itself, as the setup predicts.
