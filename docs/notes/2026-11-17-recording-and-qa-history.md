# Recording and QA history, 17 November 2026

> **History note.** This page holds the details that were moved out of the professor-facing files (the weekly progress report, its worksheet, the guide and `docs/requirements-and-evidence.md`) in release `comp9500-final-2026-11-r6`, so that those files carry only the main points. Nothing here is a new measurement. The frozen receipts stay where they are: [take 14](../evidence/2026-11-17-video-take14/README.md), [take 13 diagnosis](../evidence/2026-11-17-take13-diagnosis/README.md), [take 13](../evidence/2026-11-17-video-take13/).

## Take 13 (earlier take, kept unchanged as history)

Take 13 (10:12) shows the same four tabs on the English-only app with gpt-5 at minimal reasoning effort. In it, the new-category step selected 0 members, so the feed did not change (2,100 eligible before and after Apply), and the new hike item matched with a quotation but was not selected. The reason, found afterwards, was the separate evidence check, which the review screen did not yet show. Takes 12 and 11 are also kept as history.

## Why take 13 showed no new-category member, and the fixes

The app selects an item for a new category only if the classifier says "match", its quotation is found in the item's text, and a separate evidence check (which sees the definition, the item and the quotation, not the verdict) supports it. Take 13 was reproduced with every model request and response saved. The rule worked as designed; both rejections came from the evidence check, which was valid for that definition: the definition demanded that "the main visual subject" be nature, which text can rarely show, and the hike description stressed "a view over the city". At the measured effort (low) instead of the take's minimal effort, item 2894 was accepted. Three real defects were fixed, each with a regression test:

- the scope was the top N of the *original* ranking, so 5 of the 10 classified videos were ones the user had already hidden; it is now the top N of the current feed;
- the new-item review did not show the evidence check, so "match … not selected" looked contradictory; it now shows the check and its reason, and counts it among the checks;
- the definition step now asks for conditions the item text can establish.

## Take 14 recording history and checks

- Live attempts: 4 (14a aborted at the key check; 14b stopped by a low-memory reaper; 14c failed the silence check and selected 1 member; 14d passed). Source: the frozen [take 14 receipt](../evidence/2026-11-17-video-take14/README.md).
- Checks of the published take (`check.json` of that folder): no silence of 5 s or more at -45 dB; transcript 103/103 script sentences (similarity 0.899); one frame every 30 s (22 frames, contact sheet); live CJK check, 69 checks, none visible. The transcript figure is a word-presence check of the script sentences, not an ordered sentence, timestamp or screen-synchronisation check.

## Earlier test runs (historical, superseded)

These runs are kept as history only; the current results of `run-all-tests.cmd` for release r6 are stated in the README and in `docs/requirements-and-evidence.md`.

- Mock, 2026-11-17T01:14Z (before commit `9c9d393`): pytest 1,745 passed, 76 skipped, 1 failed (frozen by design: `test_guarded_current_contract`); page 126/126; browser 29/29; workflows 13/13.
- Mock, 2026-11-17T06:59Z (code after commit `d824e13`; receipts in the private `FINAL2/receipts/final-tests/`): pytest 1,752 passed, 75 skipped, 1 failed (same frozen test); page 126/126; browser 29/29; workflows 14/14. It was called "final" at the time; it is not the final run of release r6.
- Mock, r4 English-only code (receipts in the private `FINAL2/receipts/r4-tests/`): pytest 1,763 passed, 75 skipped, 1 failed (same frozen test); page 126/126; browser 29/29; English-only check 53 screens; workflows 14/14.
- After the take 13 fixes (r5): Python 1,766 passed (3 new regression tests), same single failure; page 126/126; browser 29/29; English-only check 57 screens; workflows 17/17.
