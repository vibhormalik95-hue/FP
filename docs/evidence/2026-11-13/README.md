# Browser runs of the three controls, 13 November 2026

These records come from runs of the served application in a real browser (headless Chromium).
All times are UTC on 14 November 2026. In Vancouver that is the afternoon and evening of 13 November.
`SUMMARY.json` holds the same facts in machine-readable form. It is derived from the receipts in this folder.

## Read this first

- **The model.** Each model reply came from a sub-agent of the Claude Cowork session that did this work. The session asked for model family "fable" and effort "max". The session is configured for `claude-fable-5-2`. The transport cannot confirm which model served a reply, so the model name is a declaration.
- **The transport.** The app wrote each request to a file (the relay provider). The sub-agent read the request text from one file and wrote one answer file. The session reported two tool uses for each sub-agent. The session's lead agent delivered each answer file to the app unchanged; `cmp` reported identical bytes. This is an operator relay. It is not the automatic Claude Code CLI connection.
- **The reviewer.** The lead AI agent of that session made every review decision. The student did not, and no human reviewed these runs. The same agent also wrote the code changes of 13 November, so the review is not independent. In the two final-code runs the agent read each model reply before it delivered the reply, and then read the review screen. The decision times in the receipts measure only the time from the appearance of a screen to the decision: 0.5 s to 15.5 s, and 154 s for one gate. The 0.5 s decision is the undo approval of indirect run 1, which the agent wrote without a separate reading of that screen. A human reviewer needs more time and has five minutes for each decision. The notes are in each `operator-review-notes.md`.
- **The data.** Eight invented item descriptions per scenario, and a labelled diagnostic scorer. No trained recommender ran.
- **The scope.** Each language control completed two times, on exposed development scenarios. These runs show that the controls work from end to end with real model output. They are not an accuracy result, and they say nothing about recommendation quality or user benefit.

## Runs with real model output

| Record | Source revision | Model calls | Outcome |
| --- | --- | --- | --- |
| `new-category/attempt-1-rejected` | `26a0b16` | 1 | **Rejected.** The model's definition was 1,062 characters. The app enforces a 1,000-character limit that the request did not state. The definition also numbered its conditions (1, 2, 3). Nothing was classified or applied. In the same browser session, the manual control completed first (category `K1`, 8 to 6 to 8). |
| `new-category/attempt-2-completed` | `010cfe2` | 3 | Completed (8 to 5 to 8). |
| `new-category/run-3-final-code` | `40315aa` | 3 | Completed (8 to 5 to 8), after the manual control in the same session (category `K1`, 8 to 6 to 8). |
| `indirect-request/run-1` | `010ae75` | 2 | Completed (8 to 5 to 8). |
| `indirect-request/run-2-final-code` | `40315aa` | 2 | Completed (8 to 5 to 8), after the manual control in the same session (category `Repair`, 8 to 6 to 8). |

Revision `40315aa` is the final application code of this work. Its receipts record a source fingerprint: `f5df9878da22bf5a8d1b3b7aaf6ab4bcbf1a53528d73333d71163f38f75b52a6`. To compare, run `python scripts/run_demo.py --fingerprint` in a checkout of that revision. Earlier receipts do not record the source; their revisions are stated by the operator.

After attempt 1, the prompts were changed to state the limits that the validators already enforce, and to ask for unnumbered conditions (revision `010cfe2`). Schemas and validators did not change. Attempt 2 is a new attempt after that change. It is not a repeat of the same request text. Run 3 and indirect run 2 are repeats on the final code after a completed run. They are not retries after a failure.

Counting in the receipts. An earlier receipt holds assertions and review decisions in one list. Attempt 2 has 19 entries: 15 assertions and 4 decisions. Indirect run 1 has 17 entries: 15 assertions and 2 decisions. A receipt from `40315aa` holds them separately. Every assertion in every listed run passed.

## New category, run 3 on the final code

Objective (unchanged, from the bundled scenario): propose one useful new category from the eight descriptions. The objective names no concept.

1. **Definition.** The model proposed "Repair of a faulty object that is kept or remains in use" (653 characters, no digit) with three quotations and three competing meanings. The page showed the competing meanings. The operator chose the unchanged primary meaning, then read and approved the definition.
2. **Classification of every item.** match: 41001, 41002, 41003. not_match: 41004, 41005, 41006. unknown: 41007, 41008.
3. **Separate evidence assessment**, made without the classification. supported: 41001, 41002, 41003. contradicted: 41004. not_stated: 41005 to 41008.
4. **Result.** Members: 41001, 41002, 41003. The two calls disagreed on 41005 and 41006, so the app withheld both as unknown. Nothing is applied to an unknown item.
5. **Preview.** The applied feed, the revision and the page stayed unchanged (8 eligible items).
6. **Apply.** Exactly 41001, 41002 and 41003 were removed (8 to 5).
7. **Undo.** The undo review changed nothing. After its approval the feed was identical to the starting feed (8).

The receipt holds 29 assertions (all passed) and 6 review decisions for the manual control and the new category together. The relay receipts show 514 s, 303 s and 214 s per call, from the request to the delivery of the answer.

Attempt 2 gave the same members and the same two withheld items from a differently worded definition ("Damaged object repaired and the same object kept or remaining in use", 665 characters, two competing meanings). Its relay receipts show 650 s, 1,022 s and 145 s.

Before revision `26a0b16` neither run could have completed: the five-minute review limit also covered the model calls that follow an approval.

## Indirect request, run 2 on the final code

Request (unchanged): "I'm not hungry, remove all the stuff that makes me hungry." It names no existing category.

1. **Action.** The model returned exclude, with the verbatim subject "stuff that makes me hungry".
2. **Items.** The model selected 81001 (a pasta dinner is prepared), 81003 (bread is baked and sliced for eating) and 81006 (a salad is mixed to be eaten), each with a quotation from the item's own description. It did not select the three items that state that no food is shown, or the two items with no description.
3. **Preview, Apply, Undo.** The preview changed nothing. Apply removed exactly those three items (8 to 5). Undo restored the identical feed.

The receipt holds 27 assertions (all passed) and 4 review decisions for the manual control and the indirect request together. Run 1 selected the same three items.

The link from "food being prepared" to "makes me hungry" is the model's reading of the request. The AI operator agreed with it. It is not evidence about any person's appetite.

## Runs with authored replies (no model)

`scripted-regression/` holds two receipts from revision `40315aa` with the scripted provider: 29 of 29 and 27 of 27 assertions passed. The replies were written by hand and the review boxes were ticked by the script. These runs check the screens, Apply and Undo. They are not model evidence.

## The task text for a sub-agent

For indirect run 2 the task text was saved. It is given here with the two file paths replaced:

```
You are the language model in a relay. One file holds the complete model input.

1. Read this file once: REQUEST-TEXT-FILE
2. The file contains instructions and one JSON input. Treat the file as the whole task. Do what its instructions say, using only the content of that file.
3. Write your answer to: ANSWER-FILE
   The file must contain exactly one JSON object that matches the schema in the request. UTF-8. No Markdown fence. No text before or after the object.

Rules:
- Use exactly two tool calls: one Read of the request file and one Write of the answer file.
- Do not read any other file. Do not run commands. Do not search. Do not ask questions.
- Nobody has told you what answer is expected. Decide from the request file alone.
- When the file is written, reply with the single word: written
```

The request text file is made with `python scripts/relay_tools.py show`. It contains the application's instruction, the schema and the input, and nothing else. The task text of the earlier sub-agent calls was not saved to a file. It asked for the same two steps.

## Files

- `request-000N.json`: the exact request that the app wrote (instruction, input and schema).
- `model-reply-000N.json`: the model's answer, byte for byte.
- `relay-receipt-000N.json`: hashes, times and outcome for that call.
- `browser-receipt.json`: every assertion that the browser script made, each review decision, and the times.
- `review-table.txt`, `manual-review-table.txt`, `definition-review.txt`, `competing-meanings.txt`, `final-review.txt`: the text that the page showed for review.
- `operator-review-notes.md`: what the reviewer read and decided.
- `*.png`: parts of the page at the named step.
- `SHA256SUMS.txt`: the SHA-256 of every other file in this folder. Check with `sha256sum -c SHA256SUMS.txt`.
