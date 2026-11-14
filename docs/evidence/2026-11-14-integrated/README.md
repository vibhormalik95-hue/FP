# Run records of the integrated revision, 14 November 2026

These records belong to revision `ff92666` (source fingerprint `22ba794e2091685fa879dcc43b68233dae1963fa4231c38dd73a36f13639068a`).
That revision is the merge of two lines of work of 14 November, the published work branch (`c84e2cd`) and the package line (`6dd3486`), with the corrections that followed the merge.
The folder [`../2026-11-14/`](../2026-11-14/README.md) holds the records of the package line before the merge (revision `b7c5a91`, another fingerprint, other prompts for the new category).
The times in the records are UTC. `SUMMARY.json` is generated from the receipts. `SHA256SUMS.txt` lists every other file.

## Earlier runs on the merged source

The same runs were made two times before on 14 November 2026. Each time a correction then replaced the build, so the runs were made again.

| Pass | Revision | Source fingerprint | Runs with real model output (UTC) | Result | Records |
| --- | --- | --- | --- | --- | --- |
| 1 | `e797ce1`, the merge commit | `24d0a8246edc...` | 19:04 to 19:12 | 321 of 321 checks, 13 model calls, 19 approvals | In revision `7678016` of this repository, in this folder |
| 2 | `615dd55` | `516be14ae8ac...` | 19:49 to 19:57 | 321 of 321 checks, 13 model calls, 19 approvals | Not in the repository |
| 3 | `ff92666` | `22ba794e2091...` | 20:05 to 20:13 | The records of this folder | This folder |

The application code is the same in the three builds. After pass 1, two style rules of the published branch were added to the page; the script file of the page has the same bytes in the three builds. After pass 2, two sentences were corrected in the guide of the scenario `tags`, a file that the source fingerprint counts.

In the three passes the selected items, the item counts and the class of each outcome were the same. The words of the model differed: the name of the new category was "Damaged object repaired and kept in use" in passes 1 and 3 and "Repaired and kept in use" in pass 2; the ambiguous request got four, five and five alternatives; the fictional item got another title each time.
Three equal passes on scenarios that were written for these requests are not an accuracy result.

## What these records are

| Folder | What ran | What answered | Who reviewed |
| --- | --- | --- | --- |
| `real-model-relay/` | The served application in a headless Chromium browser, three scenarios | Real model output through the file relay. One sub-agent of the AI session answered each request and wrote one answer file. The model name is declared as "claude-opus (sub-agent alias opus of the Cowork session; version not attested)". It is not attested. | An AI operator (a separate sub-agent). No person reviewed these runs. |
| `authored-replies/` | The same browser check on four scenarios | Hand-written replies for the bundled requests. Not a model. Scenario `conditions` has no provider. | The script ticked the review boxes. |
| `route-checks/` | The connection check and the route trial for three model routes | Stand-in servers and one stand-in program that return the hand-written replies. Not a model. | Nobody. A trial stops before the first review. |

## Limits

- The items are invented: ten in scenario `tags`, eight in `category` and in `hunger`. The scorer is a diagnostic formula, not the trained recommender.
- The runs show that each step executes: a preview changes nothing, Apply changes exactly the approved items, and Undo restores the earlier feed. They are not accuracy results.
- The reviewer was an AI agent. The model agents and the operator agent belong to the same AI session, and they start with the project instructions, so they were probably not blind to the purpose of the scenarios. Each model agent read two files, its instruction file and the text of its own request. It ran only the commands of its instructions: it waited for its request, wrote the request text, wrote its answer file, checked that the file parses as JSON, and renamed it. The session transcripts of the agents show no other tool call.
- No real provider API, no local model server and no command-line program of a provider was called. The HTTP and command-line routes ran against stand-ins only. These runs were made on Linux. None was made on Windows or macOS.
- Each request ran one time in this pass.

## Real model output through the relay: what each flow did

Model calls: 13. Checks of the script: 321 of 321 passed. Review decisions by the AI operator: 19, all APPROVE.

| Scenario | Flow | Model calls | Controls and selected items | Eligible items: before, after Apply, after Undo | Outcome |
| --- | --- | --- | --- | --- | --- |
| `tags` | manual | 0 | Manual: Cooking (exclude): 61001, 61002, 61009 | 10 to 7 to 10 | completed: preview unchanged, apply exact, undo restored |
| `tags` | vocabulary | 1 | Remove: category "Cooking", category "Baking", category "Home recipe... [25c4f8] (exclude): 61001, 61002, 61003, 61009 | 10 to 6 to 10 | completed: preview unchanged, apply exact, undo restored |
| `tags` | mixed | 1 | Show more: category "Music", category "Guitar", category "Live sessi... [5705b2] (boost standard): 61007, 61008; Remove: category "Cooking", category "Baking", category "Home recipe... [25c4f8] (exclude): 61001, 61002, 61003, 61009 | 10 to 6 to 10 | completed: preview unchanged, apply exact, undo restored |
| `tags` | description | 2 | Reviewed description request (exclude): 61004 | 10 to 9 to 10 | completed: preview unchanged, apply exact, undo restored |
| `tags` | fictional | 1 | completed: draft reviewed, admitted to the separate feed, removed; observed feed unchanged | 10 | completed: draft reviewed, admitted to the separate feed, removed; observed feed unchanged |
| `category` | manual | 0 | Manual: K1 (exclude): 41001, 41004 | 8 to 6 to 8 | completed: preview unchanged, apply exact, undo restored |
| `category` | category | 3 | Damaged object repaired and kept in use (exclude): 41001, 41002, 41003 | 8 to 5 to 8 | completed: preview unchanged, apply exact, undo restored |
| `hunger` | manual | 0 | Manual: Repair (exclude): 81002, 81004 | 8 to 6 to 8 | completed: preview unchanged, apply exact, undo restored |
| `hunger` | indirect | 2 | Reviewed indirect request (exclude): 81001, 81003, 81006 | 8 to 5 to 8 | completed: preview unchanged, apply exact, undo restored |

Requests that must change nothing (scenario `tags`, flow `outcomes`). The script records the observed class beside the class of the hand-written reply. Nothing was applied in any of them.

| Case | Request | Class of the hand-written reply | Observed class | Model calls begun | Source of the outcome |
| --- | --- | --- | --- | --- | --- |
| ambiguous | I have had enough of the heavy stuff. | clarify | clarify | 1 | model_report |
| unsupported | Show me at most two cooking videos per day. | unsupported | unsupported | 1 | model_report |
| negated | Do not hide the cooking videos. | clarify | clarify | 0 | application_check |
| no_match | Show me fewer videos about astronomy. | no_match | no_match | 1 | model_report |

For each run the folder holds: the receipt of the browser check, every review gate with the text that the page showed and the decision file, the review texts, the exact relay requests and the model replies, the receipts of the relay, the reviewer's notes, and selected screenshots.

## Authored replies

| Scenario | Outcome | Checks passed |
| --- | --- | --- |
| `tags` | all flows completed | 222 of 222 |
| `category` | all flows completed | 106 of 106 |
| `hunger` | all flows completed | 98 of 98 |
| `conditions` | all flows completed | 12 of 12 |

## Route checks with stand-ins

- `doctor-openai-compatible.txt`, `doctor-anthropic.txt`, `doctor-cli-claude-code.txt`: the output of `python scripts/model_route.py check` against a stand-in.
- `trial-authored/`, `trial-openai-compatible-standin/`, `trial-anthropic-standin/`, `trial-cli-standin/`: `python scripts/route_trial.py run --scenario tags`. Each trial ran nine cases, and no case ended in an error.
- `compare-authored-vs-cli-standin.md`: the output of `python scripts/route_trial.py compare`.
A stand-in shows that the application sends a request in the documented form and reads a reply in the documented form. It does not show how a real provider, a real local model or a real command-line program behaves.
