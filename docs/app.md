# Feed Control Lab: application reference

> **Current reference.** To run the application, see [install and run](install-and-run.md). To use the language controls, see the [guide](demo.md).

Feed Control Lab is a research application (React and FastAPI) for changing a recommendation feed through explicit controls.
It shows item metadata, not playable videos. It runs on one computer and binds to 127.0.0.1 only.

## The three views

| View | Content |
| --- | --- |
| Original study (A to E) | The five conditions of the original proposal, on one fixed scorer. |
| Compare A to E | The first ten items of each condition for the same user and the same inputs. It is a preview of the current inputs. It is not an experimental result. |
| Language controls | Reviewed controls: a model proposes, the application checks, a person approves. The view opens first when a bundled scenario is served. On the built-in fixture (scenario `conditions`) it is disabled, because the fixture has no item descriptions. |

The status line at the top names the data (fixture or processed dataset), the scorer (trained model or deterministic diagnostic scorer) and the provider of the language controls.

## The original study (A to E)

The original proposal names three interfaces: explanations, a free-text control, and an editable preference profile. The five conditions hold them as follows.

| Condition | Interface of the proposal | What the application does |
| --- | --- | --- |
| A, item feedback | The reference without language | Plus on an item card adds 0.25 to that item after score normalization. Minus removes only that item. |
| B, explanations | Explanations | The order of A, with one to three statements for each item. Each statement is a verified fact about the item, its categories and the history. A cached model selection is used where one exists for the exact fact set ("Cached LLM selection of template facts"). Other cards show "Template text · no LLM". On a bundled scenario or with the diagnostic scorer the cards show "Template text for the research dataset · not exact here", because the templates were written for opaque IDs and a trained model. B has exactly the rankings of A. |
| C, free text | Free-text control | A parser reads one category instruction, for example `Show me more category_1` or `Mute category_0`. A fixed policy applies it to the scores. In this protocol "less" means a hard mute. The latest instruction replaces the earlier one. |
| D, editable profile | Editable profile | The editor starts with a factual summary of the history. You write a profile of up to 200 words. A parser reads the category preferences. A save replaces the whole profile. You can remove one parsed preference. |
| E, all channels | All three | C and D with explanations. A command for a category replaces the profile weight of that category. It does not add to it. |

How the conditions relate to interpretation and to filtering:

- **Interpretation.** In C, D and E a parser turns text into a category command. The parser is a rule parser or a local Llama model through Ollama. The language model does not rank items.
- **Deterministic filtering.** A fixed policy applies the command to the scores of the frozen scorer. A boost adds a weight. A mute removes the items of the category. The list is not filled again after a mute.
- **Explanations.** They change the display only. They change no ranking.

These conditions keep the meaning of the frozen Experiment 1 ([protocol](evaluation-protocol.md)). Item feedback affects only A and B. Categories are opaque dataset identifiers; the application does not invent names for them.
The parser of C, D and E reads category IDs of the form `category_N` only. The bundled scenarios `tags`, `category` and `hunger` have named categories. On them the instruction and the profile are disabled, the page gives the reason, and C, D and E show the list of the scorer. The scenario `conditions` serves the built-in fixture (36 items, `category_0` to `category_5`, three users), where they work: `python scripts/quickstart.py rehearse --scenario conditions` or `python scripts/run_demo.py --scenario conditions`.
A model error leaves the controls unchanged. The application does not replace a failed model result by a rule result.

## Language controls

Every language control follows one workflow. The five methods differ in how the proposal is made.

| Step | What happens | Where |
| --- | --- | --- |
| 1. Request | The person writes a request or chooses a category. The evidence scope is the first 6 or the first 10 items of the starting list. No other item is used. | `web/src/SemanticPanel.jsx` |
| 2. Model output | The provider gets an instruction with input data and a JSON schema. It returns one JSON object. The structured reply and hashes can be recorded by the selected route. The reviewed personal transport does not retain the raw CLI stream. | `feedctrl/model_routes.py`, `feedctrl/demo_providers.py` |
| 3. Application checks | Structure and bounds of the reply; item identifiers exist; each quotation is an exact part of the text of its own item; each category or tag name exists with exactly the supplied value; the quoted part of the request is an exact part of the request; the selection is not too broad. A reply that fails gives an error, and nothing is proposed. | `feedctrl/indirect_grounding.py`, `feedctrl/vocabulary_grounding.py`, `feedctrl/staged_induction.py`, `feedctrl/evidence_audit.py` |
| 4. Review | The page shows what came back (the model output, an authored reply, or your own selection), the application checks and the decision in three blocks, a row for every item in the scope, and the first ten items now and after approval. The applied feed does not change. | `web/src/ReviewBoard.jsx`, `web/src/ReviewTable.jsx` |
| 5. Sealed group | Each control becomes one sealed record (see below). The server keeps the plan. | `feedctrl/semantic_review.py` |
| 6. Policy | On Apply, the server validates the plan again against the current source and applies exactly the approved set. | `rank_groups` in `feedctrl/semantic_review.py` |
| 7. Undo | The undo is previewed, then approved. The server keeps up to ten earlier states. | `feedctrl/semantic_review.py` |

### The five methods

| Method in the page | How the members are chosen | Model calls | Code |
| --- | --- | --- | --- |
| Existing category (manual, no model) | The exact existing category selects the members. | 0 | `feedctrl/semantic_review.py` |
| My request, matched to existing categories and tags (model) | The model sees the request and the existing category and tag names with their item counts. It returns up to four controls, each with a direction, an exact part of the request and a list of names. The application selects the items that carry the names. | 1 | `feedctrl/vocabulary_grounding.py`, `feedctrl/vocabulary_routes.py` |
| My request, matched to item descriptions (model) | Call 1 reads the direction, the strength and the subject part of the request. Call 2 sees the item data of the scope and returns item identifiers, each with an exact quotation. | 2 | `interpret_action` in `feedctrl/semantic_review.py`, `feedctrl/indirect_grounding.py` |
| My mixed request, matched to descriptions, categories and tags (model) | One call proposes up to four controls using the supplied captions, cover text and existing labels. The application checks the cited fields, scope and non-overlap before review. | 1 | `feedctrl/combined_grounding.py`, `feedctrl/combined_routes.py` |
| A new category from my description, in stages (model) | Call 1 proposes a definition, and the person reviews it or rejects it. Call 2 classifies every item. Call 3 assesses the evidence without seeing the classifications. A member needs agreement of both. An item on which they disagree gets no decision and is not selected. | 3 | `feedctrl/staged_routes.py`, `feedctrl/staged_induction.py`, `feedctrl/evidence_audit.py`, `feedctrl/source_constraints.py` |

The page also offers two earlier methods. "A new category in one call (earlier method)" makes a new category in one model call. "My request, matched to item descriptions (local model NAME)" uses a local Ollama model, where the server allows local models.
With the hand-written replies the method names end with "(authored replies, no model)". On a server with no provider, the model methods are listed as disabled, marked "(needs a model provider)".
The method with categories and tags names each control from its action and its names, for example `Remove: category "Cooking", tag "street food"` or `Show more: category "Music"`. A name longer than 80 characters is cut and ends with `... [hash6]`. A name that is in use gets ` (2)`.

### When the application proposes nothing

| Status | When | Source |
| --- | --- | --- |
| `clarify` | The reply names competing meanings or leaves a negation open. Or a control would select more than half of the scope. Or two controls give opposite instructions to the same items. Or the request matches the negated-command pattern (a negated hide, exclude, remove, reduce or boost, or a negated "show ... more" or "show ... less"); this check runs before any model call, in both language routes. "Do not show ..." without "more" or "less" does not match the pattern: it goes to the model as a request to remove. | the reply, or an application check |
| `no_match` | The reply reports that no existing name, or no description, supports the request. A scope without a category or a tag gives `no_match` with no call. | the reply, or an application check |
| `unsupported` | The reply reports that the request needs an operation that these controls do not have: a quota, a time, a condition, an order or an exception. The method with categories and tags has this result. | the reply |
| `error` | A call failed, or the application rejected the reply. | the provider, or the application |
| `limit` | The request would make more than eight applied controls. The manual method and the method with item descriptions stop before any call. The method with categories and tags decides after the interpretation. | an application check |
| `label_collision` | An applied control has the same name (manual and description methods). Only the same manual control (same category and action) is replaced by its new version. It stops before any call. | an application check |
| `duplicate` | A proposed definition name already exists. | the reply |
| `discarded` | The person rejected a definition under review (`POST semantic/definition/discard`). | the person |

In each case the applied feed and the applied controls stay as they are. A request with a control character or a format character gets HTTP 422.

A result without a proposal carries these fields:

- `calls_attempted`: the number of calls that started, failed calls included. It is always present in the three model routes.
- `outcome_source`: `application_check` (always with `calls_attempted: 0`), `provider_failure` (with `calls_attempted: 0` the provider could not start), `reply_rejected` or `model_report`.
- `call_attempts` (`stage`, `status`, and for a failure `error_type`), `failed_stage` and `reply_reason` (the reason text of the reply, marked as reply text): in the vocabulary and description routes.
- `failed_stage` and `definition_consumed` in a staged classification that did not finish. An approved definition is used once.

A reply that is not valid JSON stays in `model_calls` as bounded text (`raw_text`) with `reply_rejected: true`. The page shows it as text.
An error text reaches the page only from an exception that the application marks as safe for the page (at most 600 characters, no control characters). Every other failure shows a fixed sentence: the call to the provider failed, no usable reply came back, and the terminal of the server has the details.
When the provider cannot start, or the first call of the description route fails, the answer is HTTP 502. Its body keeps `detail` and carries all the fields of a result without a proposal.

### Fields of a ready review

A ready review also carries:

- `plan_notes`: notes about the whole plan, each with `kind` (`conflict`, `overlap` or `broad_total`), `message`, `item_ids` and `controls`. A note is not a failed check and does not stop the request.
- `scope_effects`: for the manual control and each category and tag control, the items in the scope and the items with the same category or name outside the scope, which do not change.
- `review_window_seconds`: how long the server accepts the review (300).
- `scope_items`, with the categories and labels of each item, and for the description route a full `checks` list.

### The policy

- Each user has one normalized score vector.
- An approved "show more" or "show less" adds or subtracts 0.10, 0.25 or 0.40 for the approved members.
- An approved removal takes the members out of the feed. Removal wins over a rank change.
- The item identifier breaks ties.

The policy applies an approved set exactly. It does not judge whether the set is right.

### What a review stores

A sealed group holds:

- the name of the control and the original request;
- the action (operation, strength, and the part of the request that names the subject);
- the selected item identifiers and the evidence for each one (item, field, quotation or name);
- the identifiers of the evidence scope;
- SHA-256 hashes of the source data, the catalogue of the scope, the request and the action, and for a model method also of the prompt and the schema;
- the provider identity: the kind of route, the model name as requested, and a hash of the route settings;
- for a new category: the definition, every classification, the separate assessment and the raw model replies;
- one SHA-256 value over the whole record.

Apply needs the server-held plan of the current revision, at most 300 seconds old. A stale or replaced plan is refused. If the source data, the request or the action no longer match their hashes, the group is refused and a new review is necessary.
The provider identity is a declaration by the route. The application records it. It cannot attest model weights or an account.

### Fictional items and the earlier topic steering

- [Fictional item drafts](synthetic-item-drafts.md) are metadata that a model writes. They go to a separate list in which every item has the same score 0, so the page shows no score. They never enter the catalogue, the evidence scope of a language control or the conditions A to E.
- "Earlier topic tool (exact phrases)" is the reviewed topic workflow of 4 November. It matches literal topic phrases in the source text and needs a local Ollama model for language input; without one it accepts the phrases that you type. The 4 November study used it ([protocol and results](../deliverables/2026-11-04-prospective-evaluation/PROTOCOL-AND-RESULTS.md)).

## Providers

The server gets its provider at start. A request from the page cannot supply a provider address, a credential or a provider choice.

| Provider | Meaning |
| --- | --- |
| none (`manual`) | Only the manual method works. The page lists the model methods as disabled, with the commands that start a provider. The scenario `conditions` accepts this provider only. |
| `scripted` | Replies that a person wrote for the bundled requests. Not a model. |
| a [model route](model-routes.md) | A command-line program, a hosted API, a model server on this computer, or the file relay. |
| `personal-cli` | The historical Windows driver uses a frozen profile. A separate [explicit personal binding](../diagnostic/README.md) supports the current combined route through an operator-supplied caller. |

## Endpoints

All endpoints are under `/api/`. `POST /api/session` returns a token. The page sends it in the header `X-Session-ID`.

| Group | Endpoints |
| --- | --- |
| Session and data | `POST session`, `GET status`, `GET users`, `GET categories` |
| Original study | `GET feed`, `GET compare`, `POST control`, `PUT profile`, `POST profile/text`, `POST feedback`, `POST reset`, `POST topic/preview` |
| Language controls: state | `GET semantic/groups`, `POST semantic/apply`, `POST semantic/history/preview` |
| Language controls: proposals | `POST semantic/preview` (existing category; request matched to descriptions), `POST semantic/combined/preview`, `POST semantic/vocabulary/terms`, `POST semantic/vocabulary/preview`, `POST semantic/definition/preview`, `POST semantic/definition/resolve`, `POST semantic/definition/classify`, `POST semantic/definition/discard`, `POST semantic/induction/preview` |
| Fictional items | `GET synthetic/items`, `POST synthetic/preview`, `POST synthetic/admit`, `POST synthetic/remove`, `POST synthetic/restore/preview`, `POST synthetic/clear` |
| Earlier topic steering | `GET steering`, `POST steering/preview`, `POST steering/apply`, `POST steering/remove`, `POST steering/history/preview` |

FastAPI serves an interactive reference of these endpoints at `/docs` on the running server.
`GET status` names the scenario (`scenario`), the data, the scorer and the provider. `scenario_requests` holds the bundled requests; it is `{}` for a scenario without them, for example `conditions`.

## Sessions and data

- State is separate for each session token and each user. It ends after 12 idle hours. A reload of the page starts a new session. A restart of the server clears all sessions. Nothing is stored on disk.
- The server holds at most 1,024 sessions.
- The API checks identifiers, text lengths, profile words and weights. It returns only training and request-history information. Held-out items and labels are not returned and are not used for rankings.
- Text from the catalogue and from a model is data. The page shows it as text and does not run it.

## Data and scorer

- A bundled scenario (`tags`, `category`, `hunger`) has invented items, one user with an empty history and the deterministic diagnostic scorer. The page marks it as fixture data with invented items.
- The scenario `conditions` is the built-in fixture: 36 items, categories `category_0` to `category_5`, three users, the diagnostic scorer and no item descriptions. It has no language controls and no provider.
- With the processed KuaiRec subset and a trained checkpoint, the page shows "PROCESSED DATASET" and "trained model". Those two inputs are in a separate research archive. They are not in this repository.
- A model folder that exists and fails to load gives an error. The application does not change the scorer silently.

The setup of the original experiments with local data, a checkpoint and a local Llama model is recorded in two dated pages: [Windows and Colab setup](windows-and-colab.md) and [local Llama runtime](LLM_RUNTIME.md).

## Limits

- The application is a single-process research tool for one computer. It has no accounts and no persistence.
- A language control covers the items of the evidence scope only. It does not reach an unseen catalogue.
- The checks confirm structure, identifiers, exact quotations and exact names. They do not confirm meaning. The review by a person stays necessary.
- The bundled scenarios show that the controls work as described. They are not an accuracy result and not a measure of recommendation quality.
