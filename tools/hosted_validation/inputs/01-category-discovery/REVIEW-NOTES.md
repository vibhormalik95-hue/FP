# Scenario 1: discover the concept, then classify it

**Proposed only.** Eight newly invented records; no generated answer, gold label or executed result. The objective asks the model to choose the shared concept from the descriptions. It does not tell the model to find repair, reuse, offline use, account requirements or another target meaning.

The four existing labels K1–K4 are deliberately opaque. Their member sets are K1=[41001,41004], K2=[41002,41006], K3=[41003,41007], K4=[41005,41008]. All records are already categorized; uncovered items are not required for discovery.

## Frozen proposed input

- `app-data.json`: exactly eight item IDs and category assignments; synthetic user 1 has empty histories. This is a proposed new diagnostic fixture, not a replacement for research data.
- `metadata.json` and equivalent `metadata.csv`: the exact descriptions and opaque topic tags.
- `existing-inventory.json`: the four categories projected over this scope.
- `app-preview.json`: exact body for `/api/semantic/definition/preview`, with explicitly selected exclude/none and merge mode. Direction is manual; the model chooses the definition, not the action.
- `first-model-input.json`: exact logical payload/schema for the first hosted definition call after the existing category-payload adapter. Its system prompt/schema are extracted from the reviewed source, not rewritten.

JSON files are canonical UTF-8, sorted keys, compact separators, no trailing newline. CSV is UTF-8 with LF records. Checksums and byte counts are in the root manifest. These are logical application/model inputs, not a complete approved CLI invocation or HTTP wire representation.

## Stated facts and unknowns, by item

| ID | Facts explicitly stated | Not established |
| --- | --- | --- |
| 41001 | Bent bookmark is straightened using pliers; existing piece is kept and used again. | Repair duration/cost/durability, other equipment, creator skill. |
| 41002 | Torn canvas satchel is mended with needle/thread; same bag carries books again. | Cost, duration, certification, long-term durability. |
| 41003 | Leaking clay jug is sealed; same jug returns to watering plants. | Sealant/materials, cost, food safety, lasting leak resistance. |
| 41004 | Broken organizer goes to recycling; a newly purchased organizer replaces it. | Whether recycling succeeds, any later repair of the discarded item. |
| 41005 | Paper offcuts become a new tray; no glue or powered equipment is used. | Load capacity, durability, whether a damaged tray existed earlier. |
| 41006 | A raw wooden blank is shaped on an electric lathe into a new knob. | Whether the blank is reused material; the knob's later use; repair of another object. |
| 41007 | Knot diagrams appear on a page; no completed activity or finished object is described. | Whether any object is repaired or made; whether the depicted instructions are carried out. |
| 41008 | Blue background and 20-second duration are listed. | Subject, materials, actions and every substantive category property. |

Missing facts must remain unknown for definitions that require them. An opaque label supplies no hidden factual property.

## What can honestly be expected

There is enough information for more than one defensible new category. **The following are reviewer-only illustrations, not model input or preselected outputs:**

- A precise definition about restoring damaged existing objects to use while retaining the same object could be supported by 41001/41002/41003 across three old categories. Replacement/new-object creation in 41004/41005/41006 provides contrasting evidence; 41007/41008 do not establish the required action.
- A definition about transforming materials into a newly made object could instead cover 41005/41006 across two old categories. Its exact boundaries and all eight dispositions still need review.

Other definitions may be valid. Do not automatically score them against either illustrative set. “New” means a supported concept absent from this supplied inventory and not supplied by this objective, not a concept never previously conceived by a person or model. A new label, renamed category, arbitrary ID set or novel membership alone does not demonstrate discovery of a useful meaning.

The operator must judge whether the actual definition is useful, precise, meaningfully different from the old labels, and supported in full by its quoted evidence. Then review every membership against that exact definition. Quotes prove presence, not correctness. The app rejects an exact existing scoped member set even if the proposed wording differs; preserve that duplicate result rather than change the data after seeing it.

For an approved group with n supported members, the mechanical expectation is 8→8−n eligible items after Apply, then 8 after reviewed Undo. This does not predetermine n or the label. If no supported definition is returned, stop and retain that outcome; do not provide a repair answer or retry automatically.

## Source, tests, calls and limits

Existing app path: `staged_routes.propose` → `staged_induction.propose_definition` → definition review → `staged_routes.classify` → `classify_definition`/`classify_rows` → `evidence_audit.audit_membership_envelope` → exact-ID review/Apply → reviewed Undo. Inventory comes from `induction_integration.projected_inventory`.

Relevant authored tests include `test_two_distinct_approvals_apply_only_complete_reviewed_ids`, `test_unsupported_definition_abstains_without_membership_or_profile_write`, `test_all_unknown_memberships_preserve_abstention_after_definition_review`, `test_blind_assessment_intersection_revalidates_and_retains_primary`, and `test_two_model_calls_can_agree_wrongly_and_are_not_marked_truth`. They establish contracts, not the model's ability on these new records. They were inspected, not rerun for this preparation.

Minimum for a complete proposed/apply demonstration: **3 logical model calls** (definition, complete eight-item membership, evidence audit). Definition abstention stops after 1; a non-reviewable membership stops after 2. Reviews, Apply and Undo require no additional model call. The later membership/audit inputs depend on the real approved definition and cannot be honestly prefilled now. Preserve their actual exact bytes/hashes during a separately approved run.

A successful case would demonstrate one new source-grounded category feeding this bounded synthetic filter. It would not establish full-catalogue discovery, generalization, recommendation utility, scientific novelty, comparative accuracy, or model-independent reliability. The evidence audit is another model assessment, not independent truth.
