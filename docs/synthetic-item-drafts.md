# Experimental synthetic item drafts

This opt-in feature creates fictional metadata: a model-written title, description and synthetic category label. It creates no real media, observed event or factual dataset record. All drafts retain `model_generated_synthetic` origin, an explicit synthetic flag, no media asset, raw output, model/digest, brief/prompt/schema hashes and the original source-version digest. The origin cannot be edited through the API.

## Review and isolation

Open **Reviewed topic feed → Experimental synthetic item drafts**, opt in, enter a fictional brief and generate once. A preview admits nothing. Review the wording and provenance, then explicitly approve admission. The separate synthetic feed uses score zero for every item, with admission order breaking ties. It never calls the trained scorer. Synthetic string IDs cannot enter observed-source semantic scopes or original item-feedback controls. Original catalogue/categories, saved observed-source groups and A–E ranks are preserved.

Records live only in the current session/user. Up to eight can be admitted. Removal retains one exact removed generated record for separately reviewed restoration, without inference. Restoration preserves the original generation provenance and requires fresh approval. Clear/global reset removes items, restoration history and pending drafts. Admission/removal invalidates pending reviews, including already in-flight observed-source previews, while preserving saved observed-source preferences. Source drift blocks stale admission/restoration and withholds earlier records from the synthetic feed.

## Bounded local inference

The adapter uses an explicitly configured installed local model, fixed loopback transport, temperature 0, seed 42, context 8192, at most 1000 output tokens and 90 seconds plus identity probes. It makes one attempt per preview, with no internal retry or rule fallback. Malformed/duplicate-key JSON, unsupported fields/IDs, invalid text, URLs, incomplete response or changed model digest admit nothing; raw receipts remain available to the caller. A valid schema and exact provenance cannot guarantee that the creative wording is appropriate. Review remains necessary.

Offline tests use inference doubles and validate mechanics only. Any live development result is a separately frozen, bounded fixture and must be labelled as such; do not infer model reliability from mocked tests or fictional records. This feature does not implement source-backed admission of real media or trained cold-start relevance, and does not change frozen studies.
