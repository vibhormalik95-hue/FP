# Browser runs of the three controls, 13 November 2026

These records come from runs of the served application in a real browser (headless Chromium).
The times are UTC on 14 November 2026, which is the evening of 13 November in Vancouver.
`SUMMARY.json` holds the same facts in machine-readable form.

## Read this first

- **The model.** Each model reply came from a sub-agent of the Claude Cowork session that did this work. The sub-agent was requested with model family "fable" and effort "max". The session is configured for `claude-fable-5-2`. The transport cannot confirm which model served a reply, so the name is a declaration.
- **The transport.** The app wrote each request to a file (the relay provider). The sub-agent read the request text from one file and wrote one answer file. The session reported two tool uses for each sub-agent. The answer file went to the app unchanged; `cmp` confirmed that the bytes are identical. This is an operator relay. It is not the automatic Claude Code CLI connection.
- **The reviewer.** Every review decision was made by the lead AI agent of that session. It was not made by the student and it is not a human review. The notes are in `operator-review-notes.md`.
- **The data.** Eight invented item descriptions per scenario, and a labelled diagnostic scorer. No trained recommender ran.
- **The scope.** One run of each control on exposed development scenarios. These runs show that the controls work from end to end with real model output. They are not an accuracy result, and they say nothing about recommendation quality or user benefit.

## Runs

| Run | Source revision | Model calls | Outcome |
| --- | --- | --- | --- |
| Manual category `K1`, exclude | `26a0b16` | 0 | Preview left the feed unchanged. Apply removed exactly 41001 and 41004 (8 to 6). The two-step Undo restored the identical feed. |
| New category, attempt 1 | `26a0b16` | 1 | **Rejected.** The model's definition was 1,062 characters. The app enforces a 1,000-character limit that the request did not state. Nothing was classified or applied. The record is kept in `new-category/attempt-1-rejected/`. |
| New category, attempt 2 | `010cfe2` | 3 | Completed. See below. |
| Indirect request | `010ae75` | 2 | Completed. See below. |
| Both scenarios with the scripted provider | `010ae75` | 0 (authored replies) | 29 of 29 and 27 of 27 browser checks passed. These check the screens only. |

After attempt 1, the prompts were changed to state the limits that the validators already enforce, and to ask for unnumbered conditions (revision `010cfe2`). Schemas and validators did not change. Attempt 2 is a new attempt after that change, not a repeat of the same request.

The files that hold the new-category prompts and validators are byte-identical in `010cfe2` and `010ae75`. The route file differs in one comment.

## New category, attempt 2

Objective (unchanged, from the bundled scenario): propose one useful new category from the eight descriptions.

1. **Definition.** The model proposed "Damaged object repaired and the same object kept or remaining in use" (665 characters) with three quotations and two competing meanings. The page showed the competing meanings. The operator chose the unchanged primary meaning, then reviewed and approved the definition.
2. **Classification of every item.** match: 41001, 41002, 41003. not_match: 41004, 41005, 41006. unknown: 41007, 41008.
3. **Separate evidence assessment**, made without the classification. supported: 41001, 41002, 41003. contradicted: 41004. not_stated: 41005 to 41008.
4. **Result.** Members: 41001, 41002, 41003. The two calls disagreed on 41005 and 41006, so the app withheld both as unknown. Nothing is applied to an unknown item.
5. **Preview.** The applied feed, the revision and the page stayed unchanged (8 eligible items).
6. **Apply.** Exactly 41001, 41002 and 41003 were removed (8 to 5).
7. **Undo.** The undo review changed nothing. After its approval the feed was identical to the starting feed (8).

All 19 browser checks passed. Relay receipts show 650 s, 1,022 s and 145 s per call. Those times include waiting for the operator to deliver the answer. The sub-agents took 325 s, 478 s and 100 s.

Before revision `26a0b16` this run could not have completed: the five-minute review limit also covered the model calls that follow an approval.

## Indirect request

Request (unchanged): "I'm not hungry, remove all the stuff that makes me hungry." It names no existing category.

1. **Action.** The model returned exclude, with the verbatim subject "stuff that makes me hungry".
2. **Items.** The model selected 81001 (a pasta dinner is prepared), 81003 (bread is baked and sliced for eating) and 81006 (a salad is mixed to be eaten), each with a quotation from the item's own description. It did not select the three items that state that no food is shown, or the two items with no description.
3. **Preview, Apply, Undo.** The preview changed nothing. Apply removed exactly those three items (8 to 5). Undo restored the identical feed.

All 17 browser checks passed. The link from "food being prepared" to "makes me hungry" is the model's reading of the request. It was reviewed. It is not evidence about any person's appetite.

## Files

- `request-000N.json`: the exact request that the app wrote (instruction, input and schema).
- `model-reply-000N.json`: the model's answer, byte for byte.
- `relay-receipt-000N.json`: hashes, times and outcome for that call.
- `browser-receipt.json`: every check that the browser script made, with times.
- `review-table.txt`, `definition-review.txt`, `competing-meanings.txt`: the text that the page showed for review.
- `operator-review-notes.md`: what the reviewer checked and decided.
- `*.png`: parts of the page at the named step.
