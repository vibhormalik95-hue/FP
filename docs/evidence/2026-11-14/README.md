# Run records of the final build, 14 November 2026

These records belong to revision `b7c5a91` (source fingerprint `ab1a9d846b33bf0e7e3840b91b69f65747386daec2cf5d38fc621d455c8fcefd`).
The times in the records are UTC. `SUMMARY.json` is generated from the receipts. `SHA256SUMS.txt` lists every other file.

## What these records are

| Folder | What ran | What answered | Who reviewed |
| --- | --- | --- | --- |
| `real-model-relay/` | The served application in a headless Chromium browser, three scenarios | Real model output through the file relay. One sub-agent of the AI session answered each request and wrote one answer file. The model name is declared as "claude-opus (sub-agent alias opus of the Cowork session; version not attested)". It is not attested. | An AI operator (a separate sub-agent). No person reviewed these runs. |
| `authored-replies/` | The same browser check on four scenarios | Hand-written replies for the bundled requests. Not a model. Scenario `conditions` has no provider. | The script ticked the review boxes. |
| `route-checks/` | The connection check and the route trial for three model routes | Stand-in servers and one stand-in program that return the hand-written replies. Not a model. | Nobody. A trial stops before the first review. |

## Limits

- The items are invented: ten in scenario `tags`, eight in `category` and in `hunger`. The scorer is a diagnostic formula, not the trained recommender.
- The runs show that each step executes: a preview changes nothing, Apply changes exactly the approved items, and Undo restores the earlier feed. They are not accuracy results.
- The reviewer was an AI agent. The model agents and the operator agent belong to the same AI session, and they start with the project instructions, so they were probably not blind to the purpose of the scenarios. Some model agents ran one extra command that checked that their answer file was valid JSON before they saved it; they did not change the answer after that.
- No real provider API, no local model server and no command-line program of a provider was called. The HTTP and command-line routes ran against stand-ins only. Nothing ran on Windows or macOS.
- Each request ran one time.

## Real model output through the relay: what each flow did

Model calls: 13. Checks of the script: 308 of 308 passed. Review decisions by the AI operator: 19, all APPROVE.

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
| `tags` | all flows completed | 209 of 209 |
| `category` | all flows completed | 104 of 104 |
| `hunger` | all flows completed | 96 of 96 |
| `conditions` | all flows completed | 12 of 12 |

## Route checks with stand-ins

- `doctor-openai-compatible.txt`, `doctor-anthropic.txt`, `doctor-cli-claude-code.txt`: the output of `python scripts/model_route.py check` against a stand-in.
- `trial-authored/`, `trial-openai-compatible-standin/`, `trial-anthropic-standin/`, `trial-cli-standin/`: `python scripts/route_trial.py run --scenario tags`. Each trial ran nine cases, and no case ended in an error.
- `compare-authored-vs-cli-standin.md`: the output of `python scripts/route_trial.py compare`.
A stand-in shows that the application sends a request in the documented form and reads a reply in the documented form. It does not show how a real provider, a real local model or a real command-line program behaves.
