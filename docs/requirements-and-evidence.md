# Requirements and evidence

> **Current page.** It replaces the worksheet of 11 November. Facts of earlier dates stay here as dated facts.

This page maps each request to the code and to what was observed.
It keeps three sources apart: the supervisor's requests, the student's own commitments, and the clauses of the original proposal.
It names the kind of evidence behind every statement.

## Kinds of evidence

| Kind | Meaning |
| --- | --- |
| Experiment | A study with a protocol that was fixed before the run. Its inputs, prompts, labels and results stay as they are. |
| Demonstration with real model output | A recorded run of the application in a real browser, on a small invented scenario, with replies from a real model. It shows that a control ran from request to Undo. It is not an accuracy result. |
| Authored replies | The same run with replies that a person wrote by hand. It shows the screens, Apply and Undo. It is not model behaviour. |
| Stand-in | A test of a model route against a small program or server that answers in the documented format. It is not a model and not a real provider. |
| Software test | An automatic check of program behaviour. |

Other words on this page:

- **Relay**: the application wrote each request to a file, and the reply came back as a file, unchanged.
- **AI operator**: an AI agent made the review decisions. A run with an AI operator has no human review.
- **13 November**: the date in Vancouver. The run receipts of that day give UTC times, which fall on 14 November.

## The supervisor's requests

The requests come from a meeting between the student and the supervisor. The student supplied an automatic transcript of it on 4 November 2026. The transcript is not in this repository, and the repository does not verify the meeting date or the audio. Times are positions in that transcript.
Each request below is a paraphrase of the supervisor's words, not a quotation. The exact words are kept in the private project records.

### 1. Manual category control, with measured performance

At 08:22 the supervisor said that, with categories that are set by hand, requests can be matched to them and the performance can be measured.

Code: `feedctrl/semantic_review.py` (the manual category path, `rank_groups`, Apply and Undo). Original benchmark: `feedctrl/controls.py`, `feedctrl/evaluation.py`.

| Kind | Evidence |
| --- | --- |
| Experiment (frozen Experiment 1) | For boost requests, TCP@10 (the share of the first ten items in the target category) was 11.615% with item feedback and 79.222% under the category policy. For mute requests, TCER@10 (the share of the first ten still in the muted category) was 6.112% and zero. Llama parsed 79 of 100 requests exactly and the rule parser 81 of 100; the 85% target was missed. Boost lowered NDCG@10 from 0.03012 to 0.01637. |
| Study of 4 November (used once, now exposed) | The intended profile (the model-written reference, applied without a model) against the language pipeline: the intended profile changed top-ten exposure by 5.3579 percentage points and the model-proposed profile by 2.9292 points. An AI author wrote the intended profiles, and another AI role reviewed them. The pipeline matched the complete intended profile on 48 of 100 supported requests ([protocol and results](../deliverables/2026-11-04-prospective-evaluation/PROTOCOL-AND-RESULTS.md)). These are signed descriptive averages, not a success rate. |
| Demonstration, 13 November, earlier revisions (`26a0b16` to `936d0f4`), AI operator, no model call | Excluding category `K1` left the preview unchanged, removed exactly its two items on Apply (8 to 6), and the two-step Undo restored the identical feed. The same was observed for category `Repair` in the second scenario. |
| Demonstration, 14 November, the package line before the merge | 14 November 2026 (UTC), revision `b7c5a91`, no model call. Scenario `tags`, category Cooking: 10 eligible items, 7 after Apply, 10 after Undo. Scenario `category`, category K1: 8, 6, 8. Scenario `hunger`, category Repair: 8, 6, 8. Each preview left the feed unchanged, and each Undo restored the identical order. An AI operator approved each step; no person reviewed. Records: `docs/evidence/2026-11-14/`. |
| Demonstration, integrated revision | 14 November 2026 (UTC), revision `e797ce1`, no model call. Scenario `tags`, category Cooking: 10 eligible items, 7 after Apply, 10 after Undo. Scenario `category`, category K1: 8, 6, 8. Scenario `hunger`, category Repair: 8, 6, 8. Each preview left the feed unchanged, and each Undo restored the identical order. An AI operator approved each step; no person reviewed. Records: `docs/evidence/2026-11-14-integrated/`. |

Limits: the experiment measures exposure to an assigned category. The zero comes from the hard filter by construction. The browser runs show that the control is enforced and can be reversed. Neither shows that recommendations are better.

### 2. A new category from natural language that feeds the filter

At 08:38 he asked for language processing that makes new categories, which then go into the filter.

Code: `feedctrl/staged_routes.py`, `staged_induction.py`, `evidence_audit.py`, `source_constraints.py`; review screens in `web/src/ReviewBoard.jsx` and `ReviewTable.jsx`. Method in the page: "A new category from my description, in stages (model)".

| Kind | Evidence |
| --- | --- |
| Demonstration with real model output, 13 November, earlier revision, relay, AI operator | Three completed runs. From an objective that names no concept, the model proposed "Defective or damaged object repaired, same object kept or remaining in use" (run 4). All eight items were classified and separately assessed. Three items became members (41001, 41002, 41003). The preview changed nothing; Apply removed exactly the three members (8 to 5); Undo restored the identical feed. The other two completed runs gave the same members from differently worded definitions. In those two runs, two disagreements between the two calls were withheld as unknown; run 4 had none. |
| Kept negative results | The first attempt of 13 November was rejected: its definition was longer than a limit that the request did not state. On 11 November a call through the Claude Code CLI stopped at clarification, and nothing was classified ([summary](evidence/2026-11-11/HOSTED-TWO-SCENARIO-SUMMARY.md)). A frozen twelve-request study of 5 November with local models gave 0 of 4 supported new-category cases ([results and limits](../deliverables/2026-11-05-final-demo/RESULTS-AND-LIMITS.md)). |
| Demonstration with real model output, 14 November, the package line before the merge | 14 November 2026 (UTC), revision `b7c5a91`, scenario `category`, three model calls. Proposed label "Damaged object repaired and kept in use". The model also named two other meanings; the reviewer chose the unchanged primary meaning and then approved the definition. Classification: three members (41001, 41002, 41003), four not members, one unknown. The separate assessment disagreed on item 41007, and the application withheld it as unknown. 8 eligible items, 5 after Apply, 8 after Undo. Route and review: model output through the file relay (declared model: Claude Opus sub-agents of the AI session, not attested); an AI operator reviewed; no person reviewed. Records: `docs/evidence/2026-11-14/``real-model-relay/category/`. |
| Demonstration with real model output, integrated revision | 14 November 2026 (UTC), revision `e797ce1`, scenario `category`, three model calls, with the definition and membership prompts of the published work branch. Proposed label "Damaged object repaired and kept in use". The model also named two other meanings; the reviewer chose the unchanged primary meaning and then approved the definition. Classification: three members (41001, 41002, 41003), three not members, two unknown. The separate assessment agreed on every item, so no item was withheld for a disagreement. 8 eligible items, 5 after Apply, 8 after Undo. Route and review: model output through the file relay (declared model: Claude Opus sub-agents of the AI session, not attested); an AI operator reviewed; no person reviewed. Records: `docs/evidence/2026-11-14-integrated/real-model-relay/category/`. |
| Authored replies | The browser flow `category` completes on the scenario `category` (8 to 5 to 8). The browser flow `reject` rejects a definition under review; the server then refuses to classify with it. |

Limits: one invented eight-item scenario, repeated. Three runs of one exposed example are not a reliability figure. Two model calls can agree and both be wrong.

### 3. Requests that do not use the literal words, matched to what exists

At 07:49 he gave the case of a word that means cooking but is not literally that word.
At 08:38 he asked for language processing that matches what a person intends to the categories and tags that exist.

The application has two separate cases for this request.

**3a. Matched to existing categories and tags.** Method in the page: "My request, matched to existing categories and tags (model)". Code: `feedctrl/vocabulary_grounding.py`, `feedctrl/vocabulary_routes.py`; scenario `scenarios/categories-and-tags/`.
The model sees the request and the existing category and tag names. It does not see a description. The application checks each returned name and selects the items that carry it.

| Kind | Evidence |
| --- | --- |
| Demonstration with real model output, 14 November, the package line before the merge | 14 November 2026 (UTC), revision `b7c5a91`, scenario `tags`, one model call. Request: "I'm not hungry, remove all the stuff that makes me hungry." The model chose the categories Cooking, Baking and Home recipes and the tags baking, bread, dinner, recipe, salad and street food. All 16 application checks passed. Selected items: 61001, 61002 and 61009 through their category and tags, and 61003 through the tag street food. Item 61004 stayed: only its description names food. 10 eligible items, 6 after Apply, 10 after Undo. Route and review: model output through the file relay (declared model: Claude Opus sub-agents of the AI session, not attested); an AI operator reviewed; no person reviewed. Records: `docs/evidence/2026-11-14/``real-model-relay/tags/`. |
| Demonstration with real model output, integrated revision | 14 November 2026 (UTC), revision `e797ce1`, scenario `tags`, one model call, the same request. The model chose the categories Cooking, Baking and Home recipes and the tags baking, bread, dinner, recipe, salad and street food. Selected items: 61001, 61002 and 61009 through their category and tags, and 61003 through the tag street food. Item 61004 stayed: only its description names food. 10 eligible items, 6 after Apply, 10 after Undo. Route and review: model output through the file relay (declared model: Claude Opus sub-agents of the AI session, not attested); an AI operator reviewed; no person reviewed. Records: `docs/evidence/2026-11-14-integrated/real-model-relay/tags/`. |
| Authored replies | The browser flow `vocabulary` completes on the scenario `tags`: "I'm not hungry, remove all the stuff that makes me hungry." becomes an exclusion through the category `Cooking` and the tag `street food` (10 to 6 to 10). |
| Experiment | None. Experiments 1 and 2 used requests that name a category identifier. The study of 4 November used literal topic phrases. No frozen study measures a nonliteral match to categories and tags. |

**3b. Matched to item descriptions.** Method in the page: "My request, matched to item descriptions (model)". Code: `interpret_action` in `feedctrl/semantic_review.py`, `feedctrl/indirect_grounding.py`.

| Kind | Evidence |
| --- | --- |
| Demonstration with real model output, 13 November, earlier revision, relay, AI operator | Three completed runs. "I'm not hungry, remove all the stuff that makes me hungry." was read as an exclusion. The model selected the three items whose descriptions state that food is prepared to be eaten, with a quotation from each. The preview changed nothing; Apply removed exactly those three (8 to 5); Undo restored the identical feed. |
| Earlier demonstration | On 11 November a two-call run through the Claude Code CLI selected the same three items. Apply and Undo were direct Python calls, not a browser ([summary](evidence/2026-11-11/HOSTED-TWO-SCENARIO-SUMMARY.md)). |
| Kept negative results | In the frozen twelve-request study of 5 November, the indirect request had 0 of 4 supported cases; an invalid exclusion strength stopped those paths before item selection ([results and limits](../deliverables/2026-11-05-final-demo/RESULTS-AND-LIMITS.md)). Across 14 retained development calls of local models on indirect requests, none produced a set that could be approved ([record of 5 November](../deliverables/2026-11-05-semantic-review/README.md)). |
| Demonstration with real model output, 14 November, the package line before the merge | 14 November 2026 (UTC), revision `b7c5a91`, two model calls each. Scenario `hunger`, request "I'm not hungry, remove all the stuff that makes me hungry.": items 81001, 81003 and 81006, each with a quotation from its description; 8 eligible items, 5 after Apply, 8 after Undo. Scenario `tags`, request "Remove the videos where someone is eating.": item 61004 with the quotation "between bites of a sandwich"; 10, 9, 10. Route and review: model output through the file relay (declared model: Claude Opus sub-agents of the AI session, not attested); an AI operator reviewed; no person reviewed. Records: `docs/evidence/2026-11-14/``real-model-relay/`. |
| Demonstration with real model output, integrated revision | 14 November 2026 (UTC), revision `e797ce1`, two model calls each. Scenario `hunger`, the same request: items 81001, 81003 and 81006, each with a quotation from its description; 8 eligible items, 5 after Apply, 8 after Undo. Scenario `tags`, request "Remove the videos where someone is eating.": item 61004 with the quotation "between bites of a sandwich"; 10, 9, 10. Route and review: model output through the file relay (declared model: Claude Opus sub-agents of the AI session, not attested); an AI operator reviewed; no person reviewed. Records: `docs/evidence/2026-11-14-integrated/real-model-relay/`. |
| Authored replies | The browser flows `indirect` (scenario `hunger`, 8 to 5 to 8) and `description` (scenario `tags`, item 61004) complete. |

Limits for 3a and 3b: the reading is the model's. It is not evidence about a person. The scenarios are small, invented and exposed. The 13 November runs show case 3b only: that scenario has no category or tag that names food.

### 4. Progress and what remains

At 09:18 he asked the student to share the work and to say what remains.

This page, the [front page](../README.md) and the section "What remains" below.

### 5. Two or three conference options

From 11:48 to 12:05 he asked for two or three conference options. He said that their deadline for papers is possibly in January.

Official pages were read on 14 November 2026 (UTC):

| Venue | Deadline on the official page | Page |
| --- | --- | --- |
| ACM UMAP 2027, full and short papers | Abstract 22 January 2027, paper 29 January 2027, 11:59 pm AoE | <https://um.org/umap2027/call-for-full-and-short-paper/> |
| ACM SIGIR 2027, full papers | Abstract 14 January 2027, paper 21 January 2027, AoE | <https://sigir2027.org/pages/submit-full.html> |
| ACM RecSys 2027 | No deadline published on that date | <https://recsys.acm.org/recsys27/> |

No venue has been chosen. No submission exists.

## Further behaviour of the language controls

These points are part of one workflow. They are not separate requests of the supervisor.

| Behaviour | Code | Evidence |
| --- | --- | --- |
| A mixed request: several preferences in one request, one review, one Apply | `feedctrl/vocabulary_grounding.py` | Authored replies: browser flow `mixed` on the scenario `tags` (two controls from one reply). Real model output, 14 November 2026 (UTC), revision `b7c5a91`, one model call: "Show me more music videos, and remove anything about food." gave two controls in one review. Show more (standard) for items 61007 and 61008 through the category Music and its subcategories and tags; they moved from positions 4 and 5 to 2 and 4. Remove for items 61001, 61002, 61003 and 61009. 10 eligible items, 6 after one Apply, 10 after Undo. Model output through the file relay (declared model: Claude Opus sub-agents of the AI session, not attested); an AI operator reviewed; no person reviewed. Records: `docs/evidence/2026-11-14/``real-model-relay/tags/`. Integrated revision `e797ce1`, 14 November 2026 (UTC), one model call: the same request again gave two controls in one review, Show more (standard) for items 61007 and 61008 and Remove for items 61001, 61002, 61003 and 61009; 10 eligible items, 6 after one Apply, 10 after Undo; an AI operator reviewed. Records: `docs/evidence/2026-11-14-integrated/real-model-relay/tags/`. |
| Requests that change nothing: ambiguous, negated command, unsupported, no match | `feedctrl/vocabulary_grounding.py`, `feedctrl/indirect_grounding.py` | Authored replies: browser flow `outcomes`; the feed and the applied controls stay unchanged in each case. A request that matches the negated-command pattern (a negated hide, exclude, remove, reduce or boost, or a negated "show ... more" or "show ... less") is stopped before any model call, in both language routes. "Do not show ..." without "more" or "less" is not stopped: it goes to the model as a request to remove. Real model output, 14 November 2026 (UTC), revision `b7c5a91`, nothing applied in any case: the ambiguous request gave a clarification with five alternatives from the model; the daily limit was reported by the model as unsupported; the negated command was stopped by the application before any model call; the subject without a match was reported by the model as no match. Records: `docs/evidence/2026-11-14/``real-model-relay/tags/`. Integrated revision `e797ce1`, 14 November 2026 (UTC), nothing applied in any case: a clarification with four alternatives; the daily limit reported as unsupported; the negated command stopped by the application before any model call; no match for the subject without a term. Records: `docs/evidence/2026-11-14-integrated/real-model-relay/tags/`. |
| Review in three blocks, with evidence for selected and not selected items | `web/src/ReviewBoard.jsx`, `web/src/ReviewTable.jsx` | Software tests of the interface (`web/tests/`) and the browser check. |
| A proposal changes nothing; Apply uses exactly the approved set; a two-step Undo restores the earlier feed | `feedctrl/semantic_review.py` | Asserted by the browser check in every flow, against the state of the server. The flow `history` also checks Undo after two controls and the removal of every control. |
| A failed call, an expired review and a rejected definition apply nothing | `feedctrl/semantic_review.py`, `feedctrl/staged_routes.py`, `web/src/SemanticPanel.jsx` | Authored replies: browser flows `failure`, `expired` and `reject`. The page names a failed call as a failed call. It never says that no call was made. |
| The original conditions A to E on category IDs | `feedctrl/controls.py`, `web/src/main.jsx` | Browser flow `original`: on the scenario `conditions` the instruction changes C and E, the profile changes D, and A and B stay as they were; on the scenarios with named categories both are disabled, and the page says why. |

## The student's own commitments

The student offered these in the same meeting. They are not among the supervisor's requests.

| Commitment | Code | Evidence | Limits |
| --- | --- | --- | --- |
| A fictional item with a generated description | `feedctrl/synthetic_drafts.py`, `web/src/SyntheticDraftPanel.jsx` | Demonstration, 10 November (22:46 UTC): one call through the Claude Code CLI drafted fictional metadata; it was admitted to a separate feed, removed and restored, through direct Python calls ([summary](evidence/2026-11-11/FABLE-LUNARIA-PUBLIC-SAFE-SUMMARY.json)). Authored replies: browser flow `fictional` on the scenario `tags` (draft, review, admit, remove). Real model output, 14 November 2026 (UTC), revision `b7c5a91`, one model call through the file relay: the model wrote a draft that names itself fictional; an AI operator approved it; the item went to the separate list and the feed stayed at 10 items; the item was then removed. No person reviewed. Records: `docs/evidence/2026-11-14/``real-model-relay/tags/`. Integrated revision `e797ce1`, 14 November 2026 (UTC), one model call: a draft with the title "Mending the Red Kite (Fictional Clip)" that names itself fictional; an AI operator approved it; it went to the separate list and was removed; the feed stayed at 10 items. Records: `docs/evidence/2026-11-14-integrated/real-model-relay/tags/`. | A fictional item is authored demonstration data. It is not a new playable item of the research dataset. The separate feed gives every item score 0. It gives no evidence about recommendation of new items. |
| A comparison of a stronger model with the earlier local models | The model routes (`feedctrl/model_routes.py`) let the same requests run through different models. | Document statement, 5 November: in a standalone six-case batch, Claude matched 6 of 6 tasks and 36 of 36 item decisions; the local Llama and Qwen runs failed strict JSON validation ([packet](../deliverables/2026-11-05-final-demo/IMMEDIATE-PROFESSOR-PACKET.md)). 14 November, revision `b7c5a91`: four route trials of scenario `tags` without a model (authored replies in process, and the same replies through a stand-in server for the OpenAI-compatible route, a stand-in server for the Anthropic route and a stand-in program for the command-line route); nine cases each, no error. No trial with a real model was recorded, so no model comparison exists. Records: `docs/evidence/2026-11-14/``route-checks/`. Integrated revision `e797ce1`: the same four trials again, nine cases each, no error, no model. Records: `docs/evidence/2026-11-14-integrated/route-checks/`. | Different transports and settings. Six invented cases. A format failure is not a measured accuracy of zero. This is not a ranking of models. A like-for-like comparison has not been run; it would be a new experiment with its own protocol. |

## Model routes

The application reaches a model through a route that the person selects ([model routes](model-routes.md)). This is a requirement of use, not a research claim.

| Route | Evidence |
| --- | --- |
| File relay | Demonstration with real model output: the runs of 13 November; 14 November 2026 (UTC), revision `b7c5a91`: three relay runs (13 model calls; started with `--provider relay`), records in `docs/evidence/2026-11-14/real-model-relay/`; and the integrated revision `e797ce1`: three relay runs again (13 model calls), records in `docs/evidence/2026-11-14-integrated/real-model-relay/`. |
| Command-line program (`cli`) | Stand-in program only. |
| OpenAI-compatible endpoint, local or hosted | Stand-in server only. |
| Anthropic API | Stand-in server only. |

A first real call through the last three routes on Windows or macOS is still to do. No real provider, no real local model server and no real CLI was called for this revision.
The route identity is stored in every review. The frozen experiments keep their own model configuration; a change of route does not change them.

## The original proposal

The proposal file is not in this repository. Its 33 clauses and their status are in the [completion audit of 4 November](../deliverables/2026-11-04-completion-review/PROJECT-COMPLETION-AUDIT.md). The status words below are those of the audit. This page does not judge them again.

| Status in the audit | Clauses | Subject |
| --- | --- | --- |
| Implemented or executed | R01, R03, R04, R06, R07, R08, R09, R11, R13, R14, R18, R20, R21, R25, R27 | Offline study and title; one testbed; React and FastAPI; KuaiRec training; local Llama; no paid inference in the tested paths; explanation channel; plain-language controls; all channels combined; history as input; five conditions; TCP and TCER; the 100-case parser test; the statistical tests; the model only parses during evaluation. |
| Implemented with a stated difference | R05, R10, R12, R22 | An independently written SASRec-style variant; explanation cache for the declared worked cases, not for every context; the profile interface exists, and the offline condition D tested one explicit preference; the parser bank was authored under a rubric, not sampled from a taxonomy. |
| Departure from the proposed method | R15, R16, R17 | Requests come from earlier history, not from held-out behaviour; the item-feedback baseline is a simulated proxy, not observed thumbs data. |
| Target missed or conclusion not established | R19, R23, R24, R28, R33 | The contribution of each channel is not isolated; the 85% parser target was missed (79 of 100); useful non-inferiority of HR@1 is not established; a complete bit-identical replay of Experiment 1 is not established; the like-for-like and real-intent readings of the comparison are not fully delivered. |
| Supported with a limit | R26 | The directional hypothesis holds numerically for the assigned-control comparison. A benefit that is unique to the language model does not follow. |
| Prepared; the final event is not recorded here | R02, R29, R30, R31, R32 | Related work; the paper; the presentation; public source; the schedule. |

The three interfaces of the proposal are explanations (R09, R10), the free-text control (R11) and the editable profile (R12). In the application they are the conditions B, C and D of the view "Original study (A to E)", and E combines them (R13). The [application reference](app.md#the-original-study-a-to-e) describes how each one relates to interpretation and to deterministic filtering.
The language controls of November add reviewed controls over named subjects. They do not change the status of a clause in the audit.

## Checks

Software checks with authored replies and stand-ins. They are not model evidence.

**Dated: revision `0561594` (13 November).**

| Check | Command | Result |
| --- | --- | --- |
| Python tests | `python -m pytest -p no:cacheprovider -q` | 1101 passed, 1 skipped (the private parser bank is not in this repository) |
| Guarded checks of the reviewed CLI profile, with network and process access blocked | `python tools/hosted_validation_current/run_guarded.py .` | 176 passed; no intercepted event |
| Interface logic | `node --test web/tests/*.mjs` (after `npm ci` in `web/`) | 59 passed |
| Browser, authored replies, scenario `category` | `node tests/browser/demo_flows.cjs --scenario category --flows manual,category` | 29 of 29 assertions |
| Browser, authored replies, scenario `hunger` | `node tests/browser/demo_flows.cjs --scenario hunger --flows manual,indirect` | 27 of 27 assertions |

**This revision: the integrated revision, checked 14 November 2026 (UTC) on Linux.**

It is the merge of the published work branch (`c84e2cd`) and the package line (`6dd3486`). These checks ran on Linux (Python 3.13, Node 22, headless Chromium). They do not establish Windows, macOS or real-provider acceptance.

| Check | Command | Result |
| --- | --- | --- |
| Python tests | `python -m pytest -q -p no:cacheprovider` | 1786 passed, 1 skipped (with PyTorch); 1782 passed and 2 skipped without PyTorch |
| Guarded checks of the frozen profile of 11 November | `python tools/hosted_validation_current/run_guarded.py .` | 180 checks: 16 of them have a failure (22 failed results with their sub-cases: 19 failures, 3 errors); no intercepted event. The checks that start a scenario cannot pass: the prompts changed after 11 November, so the frozen first model input no longer equals the request that the application builds. The published branch `c84e2cd` gives the same result. No reviewed successor profile exists. |
| The same guarded checks with the current-contract test inputs, on a temporary copy | `python scripts/run_guarded_current_contract.py` | 180 checks: 1 has a failure. That check compares the frozen templates with the driver file and cannot pass on a copy. The frozen profile stays unchanged. |
| Interface logic | `node --test "web/tests/*.mjs"` | 128 passed |
| Built interface | `npm run build` in `web/`, then `python scripts/check_personal_ui_index.py` | The build reproduces the tracked files; the pin check prints PASS |
| Source list | `python scripts/refresh_source_manifest.py --check` | PASS: `CURRENT-SOURCE-SHA256.txt` lists every tracked file of the revision |
| Browser, authored replies, scenarios `tags`, `category`, `hunger` | `node tests/browser/demo_flows.cjs --scenario NAME` | authored replies: `tags` 222, `category` 106, `hunger` 98 checks, all passed. Real model output through the relay: `tags` 184, `category` 69, `hunger` 68 checks, all passed |
| Browser, the original conditions, scenario `conditions` | `node tests/browser/demo_flows.cjs --scenario conditions` | 12 checks, all passed |
| Source fingerprint | `python scripts/run_demo.py --fingerprint` | `24d0a8246edc2f0bc261e163795da55ee24ce2b364a566b8fa2edc603c146cd3` |

These are software checks. They are not model evidence.

**Earlier states of 14 November, as they were recorded.**

- The integration candidate of the published work branch, revision `0efeee1faf0474048715582103c04e26510acd89`, on an isolated Linux system: 1,601 Python tests passed, 530 subtests passed, 2 skipped (Torch unavailable; private parser banks absent), 1 warning; 102 interface checks passed. The candidate also passed its production frontend build, its UI pin check and 497 source-manifest hashes. An independent review reproduced 204 focused Python checks and 102 interface checks. The browser launch failed at a host socket-permission restriction, so no browser run was claimed for it. The record said of these checks: "They do not establish Windows, browser or real-provider acceptance", and "The full run is software validation, not model evidence."
- The package line, revision `6dd3486` (source fingerprint `ab1a9d846b33bf0e7e3840b91b69f65747386daec2cf5d38fc621d455c8fcefd`): 1659 Python tests passed, 1 skipped (with PyTorch), and 1655 passed, 2 skipped without PyTorch; 114 interface checks; browser with authored replies: `tags` 209, `category` 104, `hunger` 96, `conditions` 12 checks. On that line the inputs and pins of `tools/hosted_validation_current/` had been written again for the changed source, and the guarded checks passed (178). The merge takes the frozen files of the published branch in their place.

## Defects that real runs found, corrected on 13 November

1. **The review limit also covered model time.** A definition approval is valid for five minutes. The same limit was applied again after each of the two model calls that follow an approval, so a correct run with a slow model failed. The limit now applies to the reviewer's decision only.
2. **Length limits were enforced but not stated.** A real reply was rejected for a definition of 1,062 characters. The prompts now state the limits that the checks enforce.
3. **Numbered conditions were read as required facts.** A digit in a definition becomes a literal term that the text of an item must contain. The definition prompt now asks for unnumbered conditions. See [literal source requirements](numbered-source-constraints.md).
4. **The published branch did not serve a complete interface.** The built interface is now part of the repository and is pinned.
5. **The limits of the reviewed Claude Code CLI connection were too low for the replies.** The correction set the bound to 16,384 output tokens and the time limit to 300 seconds. A later revision of the published branch (`d0a7bf7`) accepts a time limit of up to 600 seconds.
6. **A run record did not name its source.** A browser receipt now records a source fingerprint and lists review decisions apart from assertions.

## What remains

- **Real-machine checks.** A first real call through the routes `cli`, `openai-compatible` and `anthropic` on Windows or macOS. A run of the application and its checks on Windows and on macOS.
- **Human review.** A review by a person of a run with real model output. No person has reviewed a run of 14 November. An AI operator made all 19 review decisions of the three real-model runs on revision `b7c5a91`, and all 19 on the integrated revision.
- **A fresh evaluation.** Scenarios that were not used during development, with references fixed before any prediction. The scenarios of this repository are exposed development material.
- **A like-for-like model comparison**, with its own protocol before the first run.
- **Not measured by this work:** recommendation quality with the language controls, and benefit to users.
