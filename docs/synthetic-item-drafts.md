# Fictional item metadata drafts

This optional feature creates a model-written title, description and synthetic category label. It creates no real media, observed event or factual dataset record. A separate local-model development example is recorded in the [5 November demonstration](../deliverables/2026-11-05-final-demo/CLAIM-MATRIX.md).

**Current status (11 November):** one real Claude Code Lunaria call completed preview, admission, removal and restoration through the application’s Python methods using an explicit runner. Restoration replayed the removed record with no extra model call. This is operator-reviewed headless synthetic evidence, not browser acceptance, real media creation or trained cold-start relevance. The default launch remains disabled. If no permitted adapter is configured, generation remains unavailable. See the [safe result](evidence/2026-11-11/FABLE-LUNARIA-PUBLIC-SAFE-SUMMARY.json).

## Review before adding a draft

In an authorized configuration with a working provider, open **Reviewed topic feed → Experimental synthetic item drafts**, opt in, enter a fictional brief and generate once. Previewing adds nothing to the feed. Read the wording and generation details, then explicitly approve the draft if it is suitable.

Each record keeps its `model_generated_synthetic` origin, a synthetic flag, no media asset, raw output, model/digest, brief/prompt/schema hashes and the original source-version digest. The API cannot change the origin label.

Approved drafts appear in a separate feed. Every item has score zero; admission order breaks ties. This feed never calls the trained scorer. Synthetic string IDs cannot enter groups over observed items or the original item-feedback controls. The original catalogue, categories, saved source-based groups and A–E rankings are preserved.

## Removal, restoration and reset

Records exist only for the current session/user, with up to eight admitted items. Removing an item keeps its exact generated record for a separately reviewed restoration without another model call. Restoration needs fresh approval and retains the original generation details.

Clear/global reset removes drafts, admitted items and restoration history. Admission or removal invalidates pending reviews, including source-based previews already in progress, while retaining saved source-based preferences. If the source changes, the app blocks stale admission/restoration and withholds earlier records from the synthetic feed.

## Hosted configuration

Trusted setup can pass `synthetic_infer_factory` to `create_app`. Both hosted app factories supply their existing provider callable and call allowance, so a drafting attempt draws from the same run budget as the other model-assisted actions. It does not create a fresh allowance or enable the disabled personal Claude launcher.

Only the drafting instruction, fictional brief and response schema go to the provider. The observed catalogue and existing synthetic records are not included. The app preserves the returned model/configuration identity and raw response before validation. The usual preview, review, admission, removal, restoration and reset rules still apply, and configured failures do not trigger a local fallback.

Independent review passed 92 guarded Python checks, including 3 ASGI checks covering both hosted constructors and request/session/isolation behavior, the item lifecycle, and malformed-response, provider-error and source-change handling. All 7 frontend index checks passed after the build pins were corrected. This evidence uses authored provider replies; the frontend builds also matched. It does not establish real model output, browser behavior or paid-provider execution.

## Earlier local generation settings

The local adapter uses an explicitly configured installed model over loopback, with temperature 0, seed 42, context 8192, at most 1000 output tokens and 90 seconds plus identity probes. Each preview gets one attempt, with no automatic retry or rule fallback.

Malformed or duplicate-key JSON, unsupported fields/IDs, invalid text, URLs, an incomplete response or a changed model digest adds nothing. The caller can inspect the raw records. A valid response and recorded origin do not guarantee suitable wording, so human review remains necessary.

Offline tests use model substitutes and check application behavior only. Live development examples are separately preserved fixtures, not reliability estimates. The feature does not admit source-backed real media, establish trained cold-start relevance or change the frozen studies.
