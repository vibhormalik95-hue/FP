# Fictional item metadata drafts

> **Current guide.** The evidence statements at the end keep their dates.

This optional feature lets a model write a title, a description and a category label for an item that does not exist.
It creates no real media, no observed event and no record of the dataset.

## Use it in the page

Open the view **Language controls**. Under **Fictional item drafts (separate feed)**, open "Fictional item drafts: metadata that a model writes, in a separate feed".

1. Write a brief, or press **Insert the example brief** when a bundled scenario is served.
2. Tick "I want fictional metadata, not a real video or observed item."
3. Press **Generate fictional metadata draft**. The application makes one model call for each click. It does not try again by itself.
4. Read the draft under "Review fictional metadata before admission": the wording, the model and the hashes. A preview adds nothing to a feed.
5. If the draft is suitable, press **Approve fictional draft and admit to synthetic feed**.

A valid reply and a recorded origin do not make the wording suitable. Review it before you admit it.

## What a record holds

Each record keeps:

- its origin `model_generated_synthetic`, a synthetic flag and no media asset;
- the raw output of the model, the model name and its digest;
- hashes of the brief, the prompt and the schema;
- a digest of the source version.

The API cannot change the origin label.

## The separate feed

- Admitted drafts appear in a separate feed. Every item there has score 0. The order of admission breaks ties.
- That feed never calls the trained scorer.
- A fictional item has a text identifier. It cannot enter a control over observed items, the evidence scope of a language control, or the item feedback of the conditions A to E.
- The catalogue, the categories, the applied language controls and the rankings of A to E stay as they are.

## Removal, restoration and reset

- Records exist only for the current session and user. At most eight items can be admitted.
- **Remove synthetic item** removes one item. The application keeps the exact generated record, so that **Review restoring last removed synthetic item** can restore it without another model call. A restoration needs a new approval.
- **Clear synthetic items** and **Reset this user** remove drafts, admitted items and the restoration record.
- An admission or a removal makes pending reviews invalid. If the source data changes, the application blocks a stale admission and withholds earlier records from the separate feed.

## Providers

The draft uses the provider that the server was started with: the hand-written replies of `rehearse`, a [model route](model-routes.md), the relay, or the reviewed Claude Code CLI connection. A draft counts toward the same call allowance as the other calls.
Only the drafting instruction, the brief and the reply schema go to the provider. The catalogue, the history and existing fictional records do not.
A server without a provider cannot draft.

A malformed reply, a duplicate field, an unsupported field, invalid text, a URL or an incomplete reply adds nothing. The page shows the reason.

## Evidence, with dates

| Date | Kind | What was observed |
| --- | --- | --- |
| 5 November 2026 | Document statement (the evidence archive is private) | A local model drafted metadata; preview, approval, the separate feed, removal, reviewed restoration and reset were observed through the browser and the API ([record](../deliverables/2026-11-05-final-demo/CLAIM-MATRIX.md)). |
| 10 November 2026, 22:46 UTC | Demonstration with real model output | One call through the Claude Code CLI drafted metadata. Preview, admission, removal and restoration ran through the Python methods of the application, with no browser and no HTTP. Restoration replayed the removed record with no model call ([summary](evidence/2026-11-11/FABLE-LUNARIA-PUBLIC-SAFE-SUMMARY.json)). |
| This revision | Authored replies | The browser flow `fictional` completes on the scenario `tags`: draft, review, admission to the separate feed, removal. |
| Final build | Demonstration with real model output | Not yet recorded for the integrated final revision. |

## Limits

- A fictional item is authored demonstration data. It is not a new playable item of the research dataset.
- The separate feed gives no evidence about the recommendation of new items.
- The feature does not change the frozen studies.

## Earlier local generation settings

This section is a dated record of the first implementation (5 November 2026). The local adapter used an installed model over the loopback address. Its settings were temperature 0, seed 42, context 8192, at most 1,000 output tokens and a time limit of 90 seconds, with identity checks. Each preview had one attempt, with no automatic retry and no rule fallback.
