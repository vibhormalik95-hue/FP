# Fictional item metadata drafts

> **Legacy guide (earlier demonstrator, 13–15 November).** This page describes the fixture scenarios and the SemanticPanel page started by `scripts/quickstart.py`, not the current application. The current application is the four-tab Lab (Choose a category, Say it your way, New category, New items; new-category scope 10–200 items of the current feed; editable definition; provider setup in the page), started by `run-app.cmd` (`scripts/run_app.py`, port 8765). Its guide is [docs/guide/PROFESSOR-GUIDE.md](guide/PROFESSOR-GUIDE.md). The evidence statements at the end keep their dates.

This optional feature lets a model write a title, a description and a category label for an item that does not exist.
It creates no real media, no observed event and no record of the dataset.

## Use it in the page

Open the view **Language controls**. Under **Fictional items (separate list)**, open **Open the fictional items**.

1. Under "Describe the fictional item", write a description, or press **Insert the example description** when a bundled scenario is served.
2. Tick "I want a fictional item, not a real video or an item of the catalogue."
3. Press **Write a fictional draft**. The application makes one model call for each click. It does not try again by itself.
4. Read the draft under "Review the fictional item before you add it": the wording, the model and the hashes. A preview adds nothing to a list.
5. If the draft is suitable, press **Approve and add to the list of fictional items**.

A server without a provider says that no draft can be written. To try the language controls with no key, use the current four-tab Lab (`run-app.cmd` or `python scripts/run_app.py`, port 8765, default **Mock** provider; see the [guide for the supervisor](guide/PROFESSOR-GUIDE.md)).

A valid reply and a recorded origin do not make the wording suitable. Review it before you admit it.

## What a record holds

Each record keeps:

- its origin `model_generated_synthetic`, a synthetic flag and no media asset;
- the raw output of the model, the model name and its digest;
- hashes of the brief, the prompt and the schema;
- a digest of the source version.

The API cannot change the origin label.

## The separate feed

- Admitted drafts appear in a separate list. The server gives every item there the same score 0, so the page shows no score. The list keeps the order in which you added the items.
- That feed never calls the trained scorer.
- A fictional item has a text identifier. It cannot enter a control over observed items, the evidence scope of a language control, or the item feedback of the conditions A to E.
- The catalogue, the categories, the applied language controls and the rankings of A to E stay as they are.

## Removal, restoration and reset

- Records exist only for the current session and user. At most eight items can be admitted.
- **Remove fictional item ID** removes one item. The application keeps the exact generated record, so that **Review the return of the last removed fictional item** can restore it without another model call. A restoration needs a new approval.
- **Remove every fictional item** and **Reset this user** remove drafts, admitted items and the restoration record.
- An admission or a removal makes pending reviews invalid. If the source data changes, the application blocks a stale admission and withholds earlier records from the separate feed.

## Providers

The draft uses the provider that the server was started with: a [model route](model-routes.md), the relay, or the reviewed Claude Code CLI connection. A draft counts toward the same call allowance as the other calls.
Only the drafting instruction, the brief and the reply schema go to the provider. The catalogue, the history and existing fictional records do not.
A server without a provider cannot draft.

A malformed reply, a duplicate field, an unsupported field, invalid text, a URL or an incomplete reply adds nothing. The page shows "No draft was written." and the reason. A draft answer carries `calls_attempted` and `outcome_source`, as the language controls do.

## Evidence, with dates

| Date | Kind | What was observed |
| --- | --- | --- |
| 5 November 2026 | Document statement (the evidence archive is private) | A local model drafted metadata; preview, approval, the separate feed, removal, reviewed restoration and reset were observed through the browser and the API ([record](../deliverables/2026-11-05-final-demo/CLAIM-MATRIX.md)). |
| 10 November 2026, 22:46 UTC | Demonstration with real model output | One call through the Claude Code CLI drafted metadata. Preview, admission, removal and restoration ran through the Python methods of the application, with no browser and no HTTP. Restoration replayed the removed record with no model call ([summary](evidence/2026-11-11/FABLE-LUNARIA-PUBLIC-SAFE-SUMMARY.json)). |
| [14 November, integrated revision `ff92666`](evidence/2026-11-14-integrated/authored-replies/tags-browser-receipt.json) | Authored replies | The browser flow `fictional` completes on the scenario `tags`: draft, review, admission to the separate list, removal. |
| 14 November, revision `b7c5a91` | Demonstration with real model output | 14 November 2026 (UTC): one draft through the file relay (declared model: a Claude Opus sub-agent, not attested), approved by an AI operator, added to the separate list and removed. No person reviewed. Records: `docs/evidence/2026-11-14/``real-model-relay/tags/`. |
| 14 November, integrated revision `ff92666` | Demonstration with real model output | One draft through the file relay, with the title "Patch and Fly: A Kite Repair in Forty Seconds" (declared model: a Claude Opus sub-agent, not attested), approved by an AI operator, added to the separate list and removed. No person reviewed. Records: `docs/evidence/2026-11-14-integrated/real-model-relay/tags/`. |

## Limits

- A fictional item is authored demonstration data. It is not a new playable item of the research dataset.
- The separate feed gives no evidence about the recommendation of new items.
- The feature does not change the frozen studies.

## Earlier local generation settings

This section is a dated record of the first implementation (5 November 2026). The local adapter used an installed model over the loopback address. Its settings were temperature 0, seed 42, context 8192, at most 1,000 output tokens and a time limit of 90 seconds, with identity checks. Each preview had one attempt, with no automatic retry and no rule fallback.
