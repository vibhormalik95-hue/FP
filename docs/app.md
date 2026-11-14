# Feed Control Lab: application reference

> **Current reference.** To run the application, see [install and run](install-and-run.md). To use the language controls, see the [guide](demo.md).

Feed Control Lab is a research application (React and FastAPI) for changing a recommendation feed through explicit controls.
It shows item metadata, not playable videos. It runs on one computer and binds to 127.0.0.1 only.

## The three views

| View | Content |
| --- | --- |
| Original study (A to E) | The five conditions of the original proposal, on one fixed scorer. |
| Compare A to E | The first ten items of each condition for the same user and the same inputs. It is a preview of the current inputs. It is not an experimental result. |
| Language controls | Reviewed controls: a model proposes, the application checks, a person approves. The view opens first when a bundled scenario is served. |

The status line at the top names the data (fixture or processed dataset), the scorer (trained model or deterministic diagnostic scorer) and the provider of the language controls.

## The original study (A to E)

The original proposal names three interfaces: explanations, a free-text control, and an editable preference profile. The five conditions hold them as follows.

| Condition | Interface of the proposal | What the application does |
| --- | --- | --- |
| A, item feedback | The reference without language | Plus on an item card adds 0.25 to that item after score normalization. Minus removes only that item. |
| B, explanations | Explanations | The order of A, with one to three statements for each item. Each statement is a verified fact about the item, its categories and the history. A cached model selection is used where one exists for the exact fact set. Other cards show "Verified template · no LLM". B has exactly the rankings of A. |
| C, free text | Free-text control | A parser reads one category instruction, for example `Show me more category_1` or `Mute category_0`. A fixed policy applies it to the scores. In this protocol "less" means a hard mute. The latest instruction replaces the earlier one. |
| D, editable profile | Editable profile | The editor starts with a factual summary of the history. You write a profile of up to 200 words. A parser reads the category preferences. A save replaces the whole profile. You can remove one parsed preference. |
| E, all channels | All three | C and D with explanations. A command for a category replaces the profile weight of that category. It does not add to it. |

How the conditions relate to interpretation and to filtering:

- **Interpretation.** In C, D and E a parser turns text into a category command. The parser is a rule parser or a local Llama model through Ollama. The language model does not rank items.
- **Deterministic filtering.** A fixed policy applies the command to the scores of the frozen scorer. A boost adds a weight. A mute removes the items of the category. The list is not filled again after a mute.
- **Explanations.** They change the display only. They change no ranking.

These conditions keep the meaning of the frozen Experiment 1 ([protocol](evaluation-protocol.md)). Item feedback affects only A and B. Categories are opaque dataset identifiers; the application does not invent names for them.
A model error leaves the controls unchanged. The application does not replace a failed model result by a rule result.

## Language controls

Every language control follows one workflow. The four methods differ only in how the proposal is made.

| Step | What happens | Where |
| --- | --- | --- |
| 1. Request | The person writes a request or chooses a category. The evidence scope is the first 6 or the first 10 items of the starting list. No other item is used. | `web/src/SemanticPanel.jsx` |
| 2. Model output | The provider gets an instruction with input data and a JSON schema. It returns one JSON object. The raw reply is kept with hashes of the request and of the schema. | `feedctrl/model_routes.py`, `feedctrl/demo_providers.py` |
| 3. Application checks | Structure and bounds of the reply; item identifiers exist; each quotation is an exact part of the text of its own item; each category or tag name exists with exactly the supplied value; the quoted part of the request is an exact part of the request; the selection is not too broad. A reply that fails gives an error, and nothing is proposed. | `feedctrl/indirect_grounding.py`, `feedctrl/vocabulary_grounding.py`, `feedctrl/staged_induction.py`, `feedctrl/evidence_audit.py` |
| 4. Review | The page shows the model output, the application checks and the decision in three blocks, a row for every item in the scope, and the first ten items now and after approval. The applied feed does not change. | `web/src/ReviewBoard.jsx`, `web/src/ReviewTable.jsx` |
| 5. Sealed group | Each control becomes one sealed record (see below). The server keeps the plan. | `feedctrl/semantic_review.py` |
| 6. Policy | On Apply, the server validates the plan again against the current source and applies exactly the approved set. | `rank_groups` in `feedctrl/semantic_review.py` |
| 7. Undo | The undo is previewed, then approved. The server keeps up to ten earlier states. | `feedctrl/semantic_review.py` |

### The four methods

| Method in the page | How the members are chosen | Model calls | Code |
| --- | --- | --- | --- |
| Existing category (manual, no model) | The exact existing category selects the members. | 0 | `feedctrl/semantic_review.py` |
| My request, matched to existing categories and tags (model) | The model sees the request and the existing category and tag names with their item counts. It returns up to four controls, each with a direction, an exact part of the request and a list of names. The application selects the items that carry the names. | 1 | `feedctrl/vocabulary_grounding.py`, `feedctrl/vocabulary_routes.py` |
| My request, matched to item descriptions (model) | Call 1 reads the direction, the strength and the subject part of the request. Call 2 sees the item data of the scope and returns item identifiers, each with an exact quotation. | 2 | `interpret_action` in `feedctrl/semantic_review.py`, `feedctrl/indirect_grounding.py` |
| A new category from my description (model, in stages) | Call 1 proposes a definition, and the person reviews it. Call 2 classifies every item. Call 3 assesses the evidence without seeing the classifications. A member needs agreement of both. A disagreement stays unknown. | 3 | `feedctrl/staged_routes.py`, `feedctrl/staged_induction.py`, `feedctrl/evidence_audit.py`, `feedctrl/source_constraints.py` |

The page also offers two earlier methods. One makes a new category in one model call. The other matches a request to descriptions through a local Ollama model, where the server allows local models.

### When the application proposes nothing

- **Clarification.** The reply names competing meanings or leaves a negation open. Or a control would select more than half of the scope. Or one name is in two controls with different directions. Or the request negates a command: that check is a conservative English wording pattern, and it runs before any model call.
- **No match.** No existing name, or no description, supports the request.
- **Unsupported.** The request asks for something that these controls cannot express: a quota, a time, a condition, an order or an exception. The method with categories and tags has this result.
- **Error.** The call failed, or the reply was rejected. The message says what to change.

In each case the applied feed and the applied controls stay as they are.

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

- [Fictional item drafts](synthetic-item-drafts.md) are metadata that a model writes. They go to a separate feed with score 0. They never enter the catalogue, the evidence scope of a language control or the conditions A to E.
- "Earlier literal topic steering (local model only)" is the reviewed topic workflow of 4 November. It matches literal topic phrases in the source text and needs a local Ollama model for language input. The 4 November study used it ([protocol and results](../deliverables/2026-11-04-prospective-evaluation/PROTOCOL-AND-RESULTS.md)).

## Providers

The server gets its provider at start. A request from the page cannot supply a provider address, a credential or a provider choice.

| Provider | Meaning |
| --- | --- |
| none (`manual`) | Only the manual method is offered. |
| `scripted` | Replies that a person wrote for the bundled requests. Not a model. |
| a [model route](model-routes.md) | A command-line program, a hosted API, a model server on this computer, or the file relay. |
| `personal-cli` | The reviewed Claude Code CLI connection on Windows. See the [guide](demo.md#the-signed-in-claude-code-cli). |

## Endpoints

All endpoints are under `/api/`. `POST /api/session` returns a token. The page sends it in the header `X-Session-ID`.

| Group | Endpoints |
| --- | --- |
| Session and data | `POST session`, `GET status`, `GET users`, `GET categories` |
| Original study | `GET feed`, `GET compare`, `POST control`, `PUT profile`, `POST profile/text`, `POST feedback`, `POST reset`, `POST topic/preview` |
| Language controls: state | `GET semantic/groups`, `POST semantic/apply`, `POST semantic/history/preview` |
| Language controls: proposals | `POST semantic/preview` (existing category; request matched to descriptions), `POST semantic/vocabulary/terms`, `POST semantic/vocabulary/preview`, `POST semantic/definition/preview`, `POST semantic/definition/resolve`, `POST semantic/definition/classify`, `POST semantic/induction/preview` |
| Fictional items | `GET synthetic/items`, `POST synthetic/preview`, `POST synthetic/admit`, `POST synthetic/remove`, `POST synthetic/restore/preview`, `POST synthetic/clear` |
| Earlier topic steering | `GET steering`, `POST steering/preview`, `POST steering/apply`, `POST steering/remove`, `POST steering/history/preview` |

FastAPI serves an interactive reference of these endpoints at `/docs` on the running server.

## Sessions and data

- State is separate for each session token and each user. It ends after 12 idle hours. A reload of the page starts a new session. A restart of the server clears all sessions. Nothing is stored on disk.
- The server holds at most 1,024 sessions.
- The API checks identifiers, text lengths, profile words and weights. It returns only training and request-history information. Held-out items and labels are not returned and are not used for rankings.
- Text from the catalogue and from a model is data. The page shows it as text and does not run it.

## Data and scorer

- A bundled scenario (`tags`, `category`, `hunger`) has invented items, one user with an empty history and the deterministic diagnostic scorer. The page marks it as fixture data.
- With the processed KuaiRec subset and a trained checkpoint, the page shows "PROCESSED DATASET" and "trained model". Those two inputs are in a separate research archive. They are not in this repository.
- A model folder that exists and fails to load gives an error. The application does not change the scorer silently.

The setup of the original experiments with local data, a checkpoint and a local Llama model is recorded in two dated pages: [Windows and Colab setup](windows-and-colab.md) and [local Llama runtime](LLM_RUNTIME.md).

## Limits

- The application is a single-process research tool for one computer. It has no accounts and no persistence.
- A language control covers the items of the evidence scope only. It does not reach an unseen catalogue.
- The checks confirm structure, identifiers, exact quotations and exact names. They do not confirm meaning. The review by a person stays necessary.
- The bundled scenarios show that the controls work as described. They are not an accuracy result and not a measure of recommendation quality.
