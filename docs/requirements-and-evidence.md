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

### 1. Manual category control, with measured performance

> 08:22: "If you manually have categories, you can match and you can measure the performance [...]"

Code: `feedctrl/semantic_review.py` (the manual category path, `rank_groups`, Apply and Undo). Original benchmark: `feedctrl/controls.py`, `feedctrl/evaluation.py`.

| Kind | Evidence |
| --- | --- |
| Experiment (frozen Experiment 1) | For boost requests, TCP@10 (the share of the first ten items in the target category) was 11.615% with item feedback and 79.222% under the category policy. For mute requests, TCER@10 (the share of the first ten still in the muted category) was 6.112% and zero. Llama parsed 79 of 100 requests exactly and the rule parser 81 of 100; the 85% target was missed. Boost lowered NDCG@10 from 0.03012 to 0.01637. |
| Study of 4 November (used once, now exposed) | Manual reference against the language pipeline: the intended manual profile changed top-ten exposure by 5.3579 percentage points and the model-proposed profile by 2.9292 points. The pipeline matched the complete intended profile on 48 of 100 supported requests ([protocol and results](../deliverables/2026-11-04-prospective-evaluation/PROTOCOL-AND-RESULTS.md)). These are signed descriptive averages, not a success rate. |
| Demonstration, 13 November, earlier revision `b9220b4`, AI operator, no model call | Excluding category `K1` left the preview unchanged, removed exactly its two items on Apply (8 to 6), and the two-step Undo restored the identical feed. The same was observed for category `Repair` in the second scenario. |
| Demonstration, final build | Not yet recorded for the integrated final revision. |

Limits: the experiment measures exposure to an assigned category. The zero comes from the hard filter by construction. The browser runs show that the control is enforced and can be reversed. Neither shows that recommendations are better.

### 2. A new category from natural language that feeds the filter

> 08:38: "[...] use NLP to create new categories that then feed the filter [...]"

Code: `feedctrl/staged_routes.py`, `staged_induction.py`, `evidence_audit.py`, `source_constraints.py`; review screens in `web/src/ReviewBoard.jsx` and `ReviewTable.jsx`. Method in the page: "A new category from my description (model, in stages)".

| Kind | Evidence |
| --- | --- |
| Demonstration with real model output, 13 November, earlier revision, relay, AI operator | Three completed runs. From an objective that names no concept, the model proposed "Defective or damaged object repaired, same object kept or remaining in use" (run 4). All eight items were classified and separately assessed. Three items became members (41001, 41002, 41003). The preview changed nothing; Apply removed exactly the three members (8 to 5); Undo restored the identical feed. The other two completed runs gave the same members from differently worded definitions. In those two runs, two disagreements between the two calls were withheld as unknown; run 4 had none. |
| Kept negative results | The first attempt of 13 November was rejected: its definition was longer than a limit that the request did not state. On 11 November a call through the Claude Code CLI stopped at clarification, and nothing was classified ([summary](evidence/2026-11-11/HOSTED-TWO-SCENARIO-SUMMARY.md)). A frozen twelve-request study of 5 November with local models gave 0 of 4 supported new-category cases ([results and limits](../deliverables/2026-11-05-final-demo/RESULTS-AND-LIMITS.md)). |
| Demonstration with real model output, final build | Not yet recorded for the integrated final revision. |
| Authored replies | The browser flow `category` completes on the scenario `category` (8 to 5 to 8). |

Limits: one invented eight-item scenario, repeated. Three runs of one exposed example are not a reliability figure. Two model calls can agree and both be wrong.

### 3. Requests that do not use the literal words, matched to what exists

> 07:49: "[...] some other word that basically cooking, but it doesn't literally match cooking."
> 08:38: "[...] use NLP to match what people intend to existing categories and tags."

The application has two separate cases for this request.

**3a. Matched to existing categories and tags.** Method in the page: "My request, matched to existing categories and tags (model)". Code: `feedctrl/vocabulary_grounding.py`, `feedctrl/vocabulary_routes.py`; scenario `scenarios/categories-and-tags/`.
The model sees the request and the existing category and tag names. It does not see a description. The application checks each returned name and selects the items that carry it.

| Kind | Evidence |
| --- | --- |
| Demonstration with real model output, final build | Not yet recorded for the integrated final revision. |
| Authored replies | The browser flow `vocabulary` completes on the scenario `tags`: "I'm not hungry, remove all the stuff that makes me hungry." becomes an exclusion through the category `Cooking` and the tag `street food` (10 to 6 to 10). |
| Experiment | None. Experiments 1 and 2 used requests that name a category identifier. The study of 4 November used literal topic phrases. No frozen study measures a nonliteral match to categories and tags. |

**3b. Matched to item descriptions.** Method in the page: "My request, matched to item descriptions (model)". Code: `interpret_action` in `feedctrl/semantic_review.py`, `feedctrl/indirect_grounding.py`.

| Kind | Evidence |
| --- | --- |
| Demonstration with real model output, 13 November, earlier revision, relay, AI operator | Three completed runs. "I'm not hungry, remove all the stuff that makes me hungry." was read as an exclusion. The model selected the three items whose descriptions state that food is prepared to be eaten, with a quotation from each. The preview changed nothing; Apply removed exactly those three (8 to 5); Undo restored the identical feed. |
| Earlier demonstration | On 11 November a two-call run through the Claude Code CLI selected the same three items. Apply and Undo were direct Python calls, not a browser ([summary](evidence/2026-11-11/HOSTED-TWO-SCENARIO-SUMMARY.md)). |
| Kept negative results | In the frozen twelve-request study of 5 November, the indirect request had 0 of 4 supported cases; an invalid exclusion strength stopped those paths before item selection ([results and limits](../deliverables/2026-11-05-final-demo/RESULTS-AND-LIMITS.md)). Across 14 retained development calls of local models on indirect requests, none produced a set that could be approved ([record of 5 November](../deliverables/2026-11-05-semantic-review/README.md)). |
| Demonstration with real model output, final build | Not yet recorded for the integrated final revision. |
| Authored replies | The browser flows `indirect` (scenario `hunger`, 8 to 5 to 8) and `description` (scenario `tags`, item 61004) complete. |

Limits for 3a and 3b: the reading is the model's. It is not evidence about a person. The scenarios are small, invented and exposed. The 13 November runs show case 3b only: that scenario has no category or tag that names food.

### 4. Progress and what remains

> 09:18: "[...] share it [...] what remains [...]"

This page, the [front page](../README.md) and the section "What remains" below.

### 5. Two or three conference options

> 11:48 to 12:05: "[...] send me a 2 or 3 options of conferences [...] Maybe their deadline for papers is in January."

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
| A mixed request: several preferences in one request, one review, one Apply | `feedctrl/vocabulary_grounding.py` | Authored replies: browser flow `mixed` on the scenario `tags` (two controls from one reply). Final build with real model output: Not yet recorded for the integrated final revision. |
| Requests that change nothing: ambiguous, negated command, unsupported, no match | `feedctrl/vocabulary_grounding.py`, `feedctrl/indirect_grounding.py` | Authored replies: browser flow `outcomes`; the feed and the applied controls stay unchanged in each case. The negated command is stopped before any model call. Final build with real model output: Not yet recorded for the integrated final revision. |
| Review in three blocks, with evidence for selected and not selected items | `web/src/ReviewBoard.jsx`, `web/src/ReviewTable.jsx` | Software tests of the interface (`web/tests/`) and the browser check. |
| A proposal changes nothing; Apply uses exactly the approved set; a two-step Undo restores the earlier feed | `feedctrl/semantic_review.py` | Asserted by the browser check in every flow, against the state of the server. |

## The student's own commitments

The student offered these in the same meeting. They are not among the supervisor's requests.

| Commitment | Code | Evidence | Limits |
| --- | --- | --- | --- |
| A fictional item with a generated description | `feedctrl/synthetic_drafts.py`, `web/src/SyntheticDraftPanel.jsx` | Demonstration, 10 November (22:46 UTC): one call through the Claude Code CLI drafted fictional metadata; it was admitted to a separate feed, removed and restored, through direct Python calls ([summary](evidence/2026-11-11/FABLE-LUNARIA-PUBLIC-SAFE-SUMMARY.json)). Authored replies: browser flow `fictional` on the scenario `tags` (draft, review, admit, remove). Final build with real model output: Not yet recorded for the integrated final revision. | A fictional item is authored demonstration data. It is not a new playable item of the research dataset. The separate feed gives every item score 0. It gives no evidence about recommendation of new items. |
| A comparison of a stronger model with the earlier local models | The model routes (`feedctrl/model_routes.py`) let the same requests run through different models. | Document statement, 5 November: in a standalone six-case batch, Claude matched 6 of 6 tasks and 36 of 36 item decisions; the local Llama and Qwen runs failed strict JSON validation ([packet](../deliverables/2026-11-05-final-demo/IMMEDIATE-PROFESSOR-PACKET.md)). No final-build route trials are established by the supplied evidence. | Different transports and settings. Six invented cases. A format failure is not a measured accuracy of zero. This is not a ranking of models. A like-for-like comparison has not been run; it would be a new experiment with its own protocol. |

## Model routes

The application reaches a model through a route that the person selects ([model routes](model-routes.md)). This is a requirement of use, not a research claim.

| Route | Evidence |
| --- | --- |
| File relay | Demonstration with real model output: the runs of 13 November, and Not yet recorded for the integrated final revision.. |
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

**Final revision.**

| Check | Command | Result |
| --- | --- | --- |
| Python tests | `python -m pytest -q -p no:cacheprovider` | Not yet run on the integrated final revision |
| Guarded checks | `python tools/hosted_validation_current/run_guarded.py .` | Not yet run on the integrated final revision |
| Interface logic | `node --test "web/tests/*.mjs"` | Not yet run on the integrated final revision |
| Browser, authored replies, scenarios `tags`, `category`, `hunger` | `node tests/browser/demo_flows.cjs --scenario NAME` | Not yet run on the integrated final revision |
| Source fingerprint | `python scripts/run_demo.py --fingerprint` | Not yet recorded for the integrated final revision. |

The dated 13 November checks used Linux, Python 3.13, Node 22 and headless Chromium. No final integrated-build environment or results are established here.

## Defects that real runs found, corrected on 13 November

1. **The review limit also covered model time.** A definition approval is valid for five minutes. The same limit was applied again after each of the two model calls that follow an approval, so a correct run with a slow model failed. The limit now applies to the reviewer's decision only.
2. **Length limits were enforced but not stated.** A real reply was rejected for a definition of 1,062 characters. The prompts now state the limits that the checks enforce.
3. **Numbered conditions were read as required facts.** A digit in a definition becomes a literal term that the text of an item must contain. The definition prompt now asks for unnumbered conditions. See [literal source requirements](numbered-source-constraints.md).
4. **The published branch did not serve a complete interface.** The built interface is now part of the repository and is pinned.
5. **The limits of the reviewed Claude Code CLI connection were too low for the replies.** The bound is now 16,384 output tokens and the time limit is 300 seconds.
6. **A run record did not name its source.** A browser receipt now records a source fingerprint and lists review decisions apart from assertions.

## What remains

- **Real-machine checks.** A first real call through the routes `cli`, `openai-compatible` and `anthropic` on Windows or macOS. A run of the application and its checks on Windows and on macOS.
- **Human review.** A review by a person of a run with real model output. No final-build human review is established by the supplied evidence.
- **A fresh evaluation.** Scenarios that were not used during development, with references fixed before any prediction. The scenarios of this repository are exposed development material.
- **A like-for-like model comparison**, with its own protocol before the first run.
- **Not measured by this work:** recommendation quality with the language controls, and benefit to users.
