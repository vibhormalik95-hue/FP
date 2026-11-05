# Two reviewed stages for derived category control

This is an optional development workflow over a declared pool of existing item metadata. It does not change the source taxonomy, create videos, or modify frozen E1, E2 or the November 4 prospective study. New implementation and development analysis in this packet were prepared with assistant-generated code; no claim is made that the student personally wrote or reviewed these later changes.

## Workflow and code

1. **Definition proposal.** Select `Reviewed topic feed` → `Experimental semantic groups` → `Local LLM: review definition, then classify all supplied items`. The first local call proposes one label, operational definition and exact supporting source quotations. No membership or ranking is approved.
2. **Definition review.** Inspect whether the whole definition is supported. Reject unstated properties, credentials or ratings even when the quotation exists. Check the explicit evidence-review box, then select `Approve definition and classify supplied items`.
3. **Complete classification.** A second call, pinned to the same installed model and digest, supplies one `match`, `not_match` or `unknown` decision for every declared item. Missing information must remain unknown. Review the entire list, source quotations, overlaps, model identity and proposed feed.
4. **Exact-set application.** Only `Approve this exact item set and apply` changes the separate semantic profile. Direction and strength are manually selected in this workflow; this is not a test of model action parsing. Clear and undo also require review. Global reset clears pending definitions, groups and history.

| Block | Source |
|---|---|
| Definition / complete membership contracts and seals | [staged_induction.py](../../feedctrl/staged_induction.py) |
| Session-bound stage tokens, approval and race checks | [staged_routes.py](../../feedctrl/staged_routes.py) |
| Installed-model adapter and current-source revalidation | [induction_integration.py](../../feedctrl/induction_integration.py) |
| Existing exact-ID ranker, apply, clear and undo | [semantic_review.py](../../feedctrl/semantic_review.py) |
| Review interface | [SemanticPanel.jsx](../../web/src/SemanticPanel.jsx) |
| Regression contracts | [test_staged_induction.py](../../tests/test_staged_induction.py) |

Each stage permits one generation attempt, at most 90 seconds plus installed-identity probes. The pool is 2–12 existing items; evidence and actual chat-byte budgets refuse oversized requests without silent truncation. Definition approval expires after five minutes and binds the request, action, scope, source, inventory, session, user and revision. Concurrent replay cannot start another classification. Source/inventory drift, reset or a newer review invalidates stale work. Application and history restoration revalidate the sealed definition and complete dispositions against current source data.

## Actual local development results

All examples below are newly authored, explicitly synthetic development fixtures with references from the same assistant context. They are not human ground truth, an independent held-out benchmark, observed dataset videos, or evidence of recommendation benefit. Temperature 0 / seed 42; installed Qwen `qwen2.5-coder:7b-instruct` and Llama `llama3.1:8b`, Ollama 0.34.0. Raw outputs and pre-execution commitments were retained privately. No paid calls, model downloads or frozen-study changes occurred.

### First frozen development run: seven generation calls

Seven fixture items crossed three original category pairs plus one item with an unstated power source. Supported intended members were 1/3/5; IP68 waterproof ratings were unsupported throughout the pool.

| Task | Qwen | Llama |
|---|---|---|
| Supported definition | Valid source quotations and intended definition, but unresolved alternatives caused `clarify`; no classification | Definition reached explicit review; second call emitted all seven declared intended verdicts, but an uncited unknown field caused strict validation failure |
| Unsupported IP68 definition | Raw `no_match`, but nonempty alternatives caused `clarify`; no application | Proposed an unsupported definition using quotations that contain no IP68 evidence. The assistant development reviewer rejected it; no classification/application followed |
| Separately supplied IP68 definition: diagnostic only | All seven raw verdicts were `unknown`, but invalid empty-quote field formatting failed validation | Wrongly selected 1/3/5 despite the supplied IP68 definition; formatting also failed. This is a semantic failure, not successful grounding |

The two supported primary cases had **0/2 applied successes** in that run. All five served stage requests left original A–E responses unchanged; no primary group was applied. The two fixed-definition diagnostics were not category discovery or served application tests. The paper-crane caption in the supported fixture describes creation rather than operation of a finished product; this ambiguity limits its semantic reference quality and was retained in review notes.

### Explicit post-development engineering correction

After freezing the complete first run and its exact source, uncited `unknown` rows with a valid field name were given a canonical empty field. Their verdict and quotation are never changed. The normalization is visible in the review, the original raw response/hash remains recorded, and nonexistent fields, invented quotes and uncited positive/negative decisions remain rejected. No prompt or schema was tuned, no old case was reinferred, and no first-run failure was relabelled as a pass.

### Fresh rendered-browser check after that correction

A separate new seven-item fixture described manual versus mains-powered coffee, gardening and cycling equipment, plus an item with an unstated power source. The exact objective was:

> Define a cross-category group of equipment that the metadata explicitly describes as running on mains electricity. Classify unstated power sources as unknown.

Using actual Llama calls through the browser, the model generated `mains_electric_equipment`, with definition “Equipment that is explicitly described as running on mains electricity.” After separate assistant development reviews, all **7/7 declared verdicts** matched this example: positives **2/4/6**, negatives **1/3/5**, unknown **7**. The second call supplied a real quotation for the unknown row; **no normalization was needed in this fresh case**.

The two calls took **14.28 s** and **13.22 s**. Exact-ID exclusion changed eligibility **7 → 4**, with full resulting order **1/3/5/7**, matching the manual intended exclusion on the identical seven-value score vector; remaining scores were unchanged. Browser clear restored seven items, undo restored the exact group and feed, and reset cleared groups/history. Original A–E before/after JSON was identical. The 20 captured HTTP responses were 19×200 and one expected session-creation 201.

This is **one successful synthetic mechanism check**, not a repeat of the failed two-model experiment, a real-catalogue semantic evaluation, or proof of autonomous novelty/understanding. Qwen was not rerun on the new case. Across both development phases there were nine actual generation calls, all raw outputs retained. Models loaded by these checks were unloaded afterward; unrelated workloads and original demo sessions were preserved.

## Verification and remaining limits

- Final full regression suite: **496 passed, 1 skipped** (private parser banks absent from this checkout). These are software checks, not model-accuracy observations.
- Staged contract/regression checks: **35 passed**, covering both approvals, session/user isolation, expiry, reset, stale source/inventory/eligibility, action/model drift, concurrent replay, in-flight invalidation, quote/ID completeness, immutable snapshots, canonical unknowns and stale undo restoration.
- Final Vite build: passed, 30 modules. Actual rendered controls and the fresh live-model review/apply/clear/undo/reset path were checked separately from unit tests.
- Source quotation validity is **not semantic entailment**. The retained Llama IP68 failure demonstrates that mandatory review cannot be removed. This workflow cannot automatically guarantee abstention on every unsupported property.
- Coverage is bounded by the declared supplied items. There is no full-catalogue semantic retrieval, independently validated ontology, synthetic video creation, frontier-provider comparison, human study or universal language/control claim here. Semantic accuracy on fresh independently held references remains unmeasured for this new workflow.
- New source is prepared locally for independent review. No additional public publication is implied by these results.
