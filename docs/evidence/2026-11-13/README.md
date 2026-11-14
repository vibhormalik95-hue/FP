# Browser runs of the three controls, 13 November 2026

These records come from runs of the served application in a real browser (headless Chromium).
All times are UTC on 14 November 2026. In Vancouver that is the afternoon and evening of 13 November.
`SUMMARY.json` holds the same facts in machine-readable form. It is derived from the receipts and the model replies in this folder. Two groups of values are not in any receipt and were supplied by the operator: the source revision of each run, and the usage numbers that the session reported for each sub-agent.

## Read this first

- **The model.** Each model reply came from a sub-agent of the Claude Cowork session that did this work. The session asked for model family "fable" and effort "max". The session is configured for `claude-fable-5-2`. The transport cannot confirm which model served a reply, so the model name is a declaration. A sub-agent is not a bare model call. It starts with the system context of the session. A later sub-agent of the same session reported that its own start context holds the instructions of this project, which name the three controls and a hunger-to-food example. The model sub-agents were started in the same way, so they were probably not blind to the purpose of the scenarios. The task text told each one to decide from the request file alone, and the request files hold no hint. For the calls with a recorded total, the session reported 65,658 to 130,715 tokens per call for request texts of 2 to 5 KB.
- **The transport.** The app wrote each request to a file (the relay provider). The sub-agent read the request text from one file and wrote one answer file. The session reported two tool uses for each sub-agent. The session's lead agent delivered each answer file to the app unchanged; `cmp` reported identical bytes. This is an operator relay. It is not the automatic Claude Code CLI connection.
- **The reviewer.** The lead AI agent of that session made every review decision. The student did not, and no human reviewed these runs. The same agent also wrote the code changes of 13 November, so the review is not independent. The agent delivered each reply without a decision about its content: one command printed the reply and delivered it. The agent then read the reply and the review screen before each decision, with two exceptions that the notes name: the undo approvals of indirect run 1 and indirect run 3 were written without a separate reading of the undo screen. The decision times in the receipts measure only the time from the appearance of a screen to the decision: 0.5 s to 15.5 s, and 154 s for one gate. A human reviewer needs more time and has five minutes for each decision. The notes are in each `operator-review-notes.md`.
- **The data.** Eight invented item descriptions per scenario, and a labelled diagnostic scorer. No trained recommender ran.
- **The scope.** Each language control completed three times, on exposed development scenarios. These runs show each control running from end to end with real model output. They are not an accuracy result, and they say nothing about recommendation quality or user benefit.

## Runs with real model output

| Record | Source revision | Model calls | Outcome |
| --- | --- | --- | --- |
| `new-category/attempt-1-rejected` | `26a0b16` | 1 | **Rejected.** The model's definition was 1,062 characters. The app enforces a 1,000-character limit that the request did not state. The definition also numbered its conditions (1, 2, 3). Nothing was classified or applied. In the same browser session, the manual control completed first (category `K1`, 8 to 6 to 8). |
| `new-category/attempt-2-completed` | `010cfe2` | 3 | Completed (8 to 5 to 8). |
| `indirect-request/run-1` | `010ae75` | 2 | Completed (8 to 5 to 8). |
| `new-category/run-3` | `40315aa` | 3 | Completed (8 to 5 to 8), after the manual control in the same session (category `K1`, 8 to 6 to 8). |
| `indirect-request/run-2` | `40315aa` | 2 | Completed (8 to 5 to 8), after the manual control in the same session (category `Repair`, 8 to 6 to 8). |
| `new-category/run-4` | `936d0f4` | 3 | Completed (8 to 5 to 8), after the manual control in the same session (`K1`, 8 to 6 to 8). Recorded as video. |
| `indirect-request/run-3` | `936d0f4` | 2 | Completed (8 to 5 to 8), after the manual control in the same session (`Repair`, 8 to 6 to 8). Recorded as video. |

**Which code served which run.** A receipt from `40315aa` or later records a source fingerprint. Print the value of a checkout with `python scripts/run_demo.py --fingerprint`.

- Run 3 and indirect run 2: revision `40315aa`, fingerprint `f5df9878da22bf5a8d1b3b7aaf6ab4bcbf1a53528d73333d71163f38f75b52a6`.
- Then two code changes were made. `8e628cf`: the function that computes the fingerprint is now designed to give the same value on Windows, Linux and macOS (tested on Linux only). For the tree of `40315aa` the new function prints the value above. `e4711a4`: the student's Windows runtime work was merged: a higher output bound and timeout for the Claude Code CLI connection, and a correction of the literal-term scanner.
- Run 4 and indirect run 3: checkout `936d0f4`, which has the application code of `e4711a4`. Fingerprint `63cf01537d86f2afc54178c419f971ab726714ce900b1e3e6a16b8c958db33ac`. These are the runs on the final application code.
- For every completed definition (attempt 2, run 3 and run 4), the earlier scanner and the corrected scanner give the same result: no literal term. For the rejected definition of attempt 1, both give the terms 1, 2 and 3.

Receipts made before `40315aa` do not record the source. Their revisions are stated by the operator: each of those runs started after the commit of its revision and before the next change. For attempt 1 and attempt 2 the revision fixes the application code and the prompts, but not the built interface: those two commits did not yet include the built interface files, and the build that the browser loaded then is in no revision. The built interface is tracked from `010ae75`.

After attempt 1, the prompts were changed to state the limits that the validators already enforce, and to ask for unnumbered conditions (revision `010cfe2`). Schemas and validators did not change. Attempt 2 is a new attempt after that change. It is not a repeat of the same request text. The later runs are repeats on later code after a completed run. They are not retries after a failure.

Counting in the receipts. An earlier receipt holds assertions and review decisions in one list. Attempt 1 has 17 entries: 15 assertions and 2 decisions. Attempt 2 has 19 entries: 15 assertions and 4 decisions. Indirect run 1 has 17 entries: 15 assertions and 2 decisions. A receipt from `40315aa` holds them separately. Every assertion in every listed run passed. The receipt of attempt 2 lists four call records for three model calls: the step that resolves competing meanings returned the record of the definition call a second time, with the same hashes.

Run 4 and indirect run 3 ran at the same time. The two indirect replies were ready after 22 s and 140 s. The operator delivered them after the new-category replies, so their relay receipts show 649 s and 397 s.

## New category, run 4

Objective (unchanged, from the bundled scenario): propose one useful new category from the eight descriptions. The objective names no concept.

1. **Definition.** The model proposed "Defective or damaged object repaired, same object kept or remaining in use" (582 characters, no digit) with three quotations and three competing meanings. The page showed the competing meanings. The operator chose the unchanged primary meaning, then read and approved the definition.
2. **Classification of every item.** match: 41001, 41002, 41003. not_match: 41004. unknown: 41005 to 41008.
3. **Separate evidence assessment**, made without the classification. supported: 41001, 41002, 41003. contradicted: 41004. not_stated: 41005 to 41008.
4. **Result.** Members: 41001, 41002, 41003. The two calls agreed on every item. Nothing is applied to an unknown item.
5. **Preview.** The applied feed, the revision and the page stayed unchanged (8 eligible items).
6. **Apply.** Exactly 41001, 41002 and 41003 were removed (8 to 5).
7. **Undo.** The undo review changed nothing. After its approval the feed was identical to the starting feed (8).

The receipt holds 29 assertions (all passed) and 6 review decisions for the manual control and the new category together. The relay receipts show 649 s, 353 s and 243 s per call, from the request to the delivery of the answer.

The three completed runs gave the same three members from three differently worded definitions:

| Run | Label | Characters | Competing meanings | 41005 and 41006 |
| --- | --- | --- | --- | --- |
| Attempt 2 | Damaged object repaired and the same object kept or remaining in use | 665 | 2 | The two calls disagreed; withheld as unknown |
| Run 3 | Repair of a faulty object that is kept or remains in use | 653 | 3 | The two calls disagreed; withheld as unknown |
| Run 4 | Defective or damaged object repaired, same object kept or remaining in use | 582 | 3 | Both calls: unknown |

Before revision `26a0b16` none of these runs could have completed: the five-minute review limit also covered the model calls that follow an approval, and those calls took longer than five minutes in each run.

## Indirect request, run 3

Request (unchanged): "I'm not hungry, remove all the stuff that makes me hungry." It names no existing category.

1. **Action.** The model returned exclude, with the verbatim subject "stuff that makes me hungry".
2. **Items.** The model selected 81001 (a pasta dinner is prepared), 81003 (bread is baked and sliced for eating) and 81006 (a salad is mixed to be eaten), each with a quotation from the item's own description. It did not select the three items that state that no food is shown, or the two items with no description.
3. **Preview, Apply, Undo.** The preview changed nothing. Apply removed exactly those three items (8 to 5). Undo restored the identical feed.

The receipt holds 27 assertions (all passed) and 4 review decisions for the manual control and the indirect request together. Run 1 and run 2 selected the same three items.

The link from "food being prepared" to "makes me hungry" is the model's reading of the request. The AI operator agreed with it. It is not evidence about any person's appetite. The match comes from the items' descriptions. This scenario has no category or tag that names food, so these runs do not show a match to an existing category or tag by its name.

## Runs with authored replies (no model)

`scripted-regression/` holds two receipts from revision `e4711a4` with the scripted provider: 29 of 29 and 27 of 27 assertions passed. Their fingerprint is the `63cf0153…` value above. The replies were written by hand and the review boxes were ticked by the script. These runs check the screens, Apply and Undo. They are not model evidence.

## The task text for a sub-agent

From indirect run 2 on, the task text was saved. It is given here with the two file paths replaced:

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

The request text file is made with `python scripts/relay_tools.py show`. It contains the application's instruction, the schema and the input, and fixed frame lines. The task text of the earlier sub-agent calls was not saved to a file. It asked for the same two steps.

## Files

- `request-000N.json`: the exact request that the app wrote (instruction, input and schema).
- `model-reply-000N.json`: the model's answer, byte for byte.
- `relay-receipt-000N.json`: hashes, times and outcome for that call.
- `browser-receipt.json`: every assertion that the browser script made, each review decision, and the times. For a recorded run it also lists the time of each step in the recording.
- `review-table.txt`, `manual-review-table.txt`, `definition-review.txt`, `competing-meanings.txt`, `final-review.txt`: the text that the page showed for review.
- `operator-review-notes.md`: what the reviewer read and decided.
- `*.png`: parts of the page at the named step.
- `SHA256SUMS.txt`: the SHA-256 of every other file in this folder. Check with `sha256sum -c SHA256SUMS.txt`.

The recordings of run 4 and indirect run 3 are not in this repository because of their size.
