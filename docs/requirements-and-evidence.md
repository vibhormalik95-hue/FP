# Requirements and evidence

Status on 13 November 2026. This page maps each request from the supervisor's meeting to the code and to what was actually observed. The transcript of that meeting was supplied on 4 November; the repository does not verify the meeting date. It separates the supervisor's requests from the student's own additions. It replaces the 11 November worksheet as the current summary; the older page stays as a dated record.

Words used here:

- **observed in the browser**: the served application was driven in a real browser and its server state was compared before and after each step;
- **relay**: an operator carried each request to a model and returned the reply unchanged;
- **AI operator**: an AI agent made the review decisions. No human review of these runs exists yet.
- **13 November**: the date in Vancouver. The run receipts give UTC times, which fall on 14 November.

## The supervisor's requests

| Request | Code | Evidence observed | What this does not show |
| --- | --- | --- | --- |
| **1. Manual category filtering, with measured performance** | `feedctrl/semantic_review.py` (manual category path, `rank_groups`, Apply and Undo). Original benchmark: `feedctrl/controls.py`, `feedctrl/evaluation.py`. | *Measured, frozen Experiment 1:* for boost requests, TCP@10 (the share of the top ten in the target category) was 11.615% with item feedback and 79.222% under the category policy; for mute requests, TCER@10 (the share of the top ten still in the muted category) was 6.112% and zero. Llama parsed 79/100 requests exactly, the rule parser 81/100; the 85% target was missed. Boost lowered NDCG@10 from 0.03012 to 0.01637. *Measured, 4 November synthetic-language study, manual reference against the model pipeline:* the intended manual profile changed top-ten exposure by 5.3579 percentage points and the model-proposed profile by 2.9292 points; the pipeline matched the complete intended profile on 48 of 100 supported requests ([protocol and results](../deliverables/2026-11-04-prospective-evaluation/PROTOCOL-AND-RESULTS.md)). These are signed descriptive averages, not a success rate. *Observed in the browser, 13 November, AI operator:* excluding category `K1` left the preview unchanged, removed exactly its two items on Apply (8 to 6), and the two-step Undo restored the identical feed. The same was observed for category `Repair` in the second scenario. No model call. | That a manual control improves recommendations. The exposure numbers follow from the policy by construction. A complete replay of Experiment 1 is not established ([note](../deliverables/2026-11-04-completion-review/E1-REPLAY-DISCREPANCY.md)). |
| **2. A new category created from natural language that feeds the filter** | `feedctrl/staged_routes.py`, `staged_induction.py`, `evidence_audit.py`, `source_constraints.py`; review screens in `web/src/SemanticPanel.jsx` and `ReviewTable.jsx`. | *Observed in the browser, 13 November, relay, AI operator, three completed runs (the last on the final application code):* from an objective that names no concept, the model proposed "Defective or damaged object repaired, same object kept or remaining in use" (run 4). The AI operator read and approved the definition. All eight items were classified and separately assessed. Three items became members; two disagreements were withheld as unknown. Preview changed nothing; Apply removed exactly the three members (8 to 5); Undo restored the identical feed. The other two completed runs gave the same members from differently worded definitions. *Kept negative result:* the first attempt was rejected because its definition exceeded a length limit that the request did not state. | Accuracy on unseen requests or catalogues. One eight-item invented scenario was used. The reviewer was an AI operator. Through the automatic Claude Code CLI connection, attempts up to 13 November returned definitions that stopped at review; that connection has not yet completed this whole flow, and the records of those attempts are not in this repository. |
| **3. Requests that do not use the literal words, matched to what exists** | `feedctrl/semantic_review.py` (`interpret_action`), `feedctrl/indirect_grounding.py`. | *Observed in the browser, 13 November, relay, AI operator, three completed runs (the last on the final application code):* "I'm not hungry, remove all the stuff that makes me hungry." was read as an exclusion. The model selected the three items whose descriptions state that food is prepared to be eaten, with a quotation from each. Preview changed nothing; Apply removed exactly those three (8 to 5); Undo restored the identical feed. *Earlier:* a two-call run through the Claude Code CLI selected the same three items on 11 November (03:03 UTC), applied through direct Python calls. | That the reading is right for a given person. The result is a reviewed set of existing items, chosen from their descriptions, tags and category names. It is not a mapping to one existing category label. The supervisor's words were "match what people intend to existing categories and tags". This scenario has no category or tag that names food, so the match comes from the item descriptions, not from a category or tag name. Three runs of one exposed example are not a reliability figure. |
| **4. Report progress and what remains** | This page and [current progress](current-progress.md). | See "What remains" below. | |
| **5. Two or three conference options** | Not code. | Official pages were rechecked on 14 November 2026 at 00:29 UTC (13 November in Vancouver): ACM UMAP 2027 (abstract 22 January, paper 29 January 2027, AoE); ACM SIGIR 2027 full papers (abstract 14 January, paper 21 January 2027, AoE); ACM RecSys 2027 (no deadline published yet). | No venue has been chosen. No submission exists. |

Records for the 13 November runs: [docs/evidence/2026-11-13](evidence/2026-11-13/README.md).

## The student's own additions

These were offered by the student in the same meeting. They are not among the supervisor's three requests.

| Addition | Code | Evidence | Limit |
| --- | --- | --- | --- |
| A fictional item with a generated description | `feedctrl/synthetic_drafts.py`, `web/src/SyntheticDraftPanel.jsx` | One run through the Claude Code CLI on 10 November (22:46 UTC) created fictional metadata, admitted it to a separate feed, removed it and restored it, through direct Python calls ([summary](evidence/2026-11-11/FABLE-LUNARIA-PUBLIC-SAFE-SUMMARY.json)). | Not run in a browser. No real video. The separate feed gives every item a neutral score. Not repeated on 13 November. |
| A comparison with a stronger model | Provider seam in `feedctrl/api.py` and the adapters | A six-case standalone comparison from 5 November: Claude matched 6 of 6 tasks and 36 of 36 item decisions; the local models failed strict JSON validation, which is not a measured accuracy of zero. | Different transports and settings. Six invented cases. Not a ranking of models. Not repeated on 13 November. |

## Checks run on revision `0561594`

The served application was last changed in revision `e4711a4`. Its source fingerprint is `63cf01537d86f2afc54178c419f971ab726714ce900b1e3e6a16b8c958db33ac`. Later revisions add a video option to the browser check, the quick start, the relay helpers, tests, documents and run records. They change no file of the fingerprint.

The last runs with real model output (new-category run 4 and indirect run 3) were made on that application code, and their receipts record that fingerprint. Two code changes came after the earlier model runs of `40315aa`:

- `8e628cf` changes only the function that computes the source fingerprint, and its test.
- `e4711a4` merges the student's Windows runtime work: a higher output bound and timeout for the Claude Code CLI connection (16,384 tokens, 300 s), and a correction of the literal-term scanner ([details](numbered-source-constraints.md)). For every model definition that completed, the earlier scanner and the corrected scanner give the same result: no literal term.

| Check | Command | Result |
| --- | --- | --- |
| Python tests | `python -m pytest -p no:cacheprovider -q` | 1101 passed, 1 skipped (the private parser bank is not in this repository) |
| Validation-profile checks with network and process access blocked | `python tools/hosted_validation_current/run_guarded.py .` | 176 passed; no intercepted event |
| Interface logic | `node --test web/tests/*.mjs` (after `npm ci` in `web/`) | 59 passed |
| Browser, scripted provider, category scenario | `node tests/browser/demo_flows.cjs --scenario category --flows manual,category` | 29 of 29 assertions |
| Browser, scripted provider, hunger scenario | `node tests/browser/demo_flows.cjs --scenario hunger --flows manual,indirect` | 27 of 27 assertions |

Environment: Linux, Python 3.13.18 with PyTorch 2.5.1, Node 22, headless Chromium. Without PyTorch, four recommender tests cannot run. These are software checks with authored replies. They are not model evidence.

## Defects found and corrected on 13 November

1. **The review limit also covered model time.** A definition approval is valid for five minutes. The same limit was applied again after each of the two model calls that follow an approval. With a model that needs minutes per call, a correct run failed after its calls were spent. The limit now applies to the reviewer's decision only. Every other check on a stale or replaced approval is unchanged (`tests/test_staged_provider_latency.py`).
2. **Length limits were enforced but not stated.** A real reply was rejected for a 1,062-character definition. The prompts now state the limits that the validators already enforce.
3. **Numbered conditions were read as required facts.** A digit in a definition becomes a literal term that an item's text must contain. A definition with numbered conditions could therefore match nothing. The definition prompt now asks for unnumbered conditions and says how digits are treated.
4. **The published branch did not serve a complete interface.** A stale built file was tracked and the build folder was ignored. The built interface is now tracked and pinned.
5. **Limits of the Claude Code CLI connection were too low for the model's replies.** A reply of about 11,000 output tokens exceeded the bound of 4,096. The bound is now 16,384 tokens and the timeout is 300 s (merged from the student's Windows work).
6. **Quoted examples and label references were read as required facts.** See [literal source requirements](numbered-source-constraints.md) (merged from the student's Windows work; its review is recorded as pending there).
7. **A run record did not name its source.** A browser receipt now records a source fingerprint and lists review decisions apart from assertions. The fingerprint is designed to give the same value on Windows, Linux and macOS for the same files. It was tested on Linux only.

## What remains

- A human review of a run with real model output. So far an AI agent made every review decision.
- A run of the automatic operator (`scripts/relay_claude_cli.py`) with the real Claude Code CLI. It was tested with a stand-in program only.
- Run the complete new-category flow through the automatic Claude Code CLI connection on Windows, with a human reviewer.
- Record the demonstration with the student reviewing each step.
- A fresh evaluation on scenarios that were not used during development, with references fixed before any prediction. The scenarios used here are exposed development material.
- Decide whether request 3 should also name an existing category when one fits.
- Recommendation quality and user benefit are not measured by this work.
