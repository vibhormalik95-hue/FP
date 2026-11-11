# Scenario 2: prospective continuation of the original hunger example

**Proposed only.** This is a new demonstration proposal deliberately reusing the exact exposed historical utterance and eight invented metadata rows. It is not a newly held-out case, a rewrite of the historical run, or an executed Fable result.

Exact request: **“I'm not hungry, remove all the stuff that makes me hungry.”**

The student supplied this example at 07:55 in the retained professor transcript. The professor's preceding example was cooking without saying “cooking”. The original local-model run used this exact request and metadata. Its action call returned exclude/none, but its grounding call returned no_match, unresolved negation and competing interpretations; the app stopped at clarify after two calls and no Apply. That remains an unsuccessful historical exclusion demonstration. `historical-source.json` records the original file/hash and returned content without altering it.

## Frozen proposed input

- `app-data.json`: eight historical synthetic IDs/category assignments, with a new clearly marked proposed fixture and empty invented history.
- `metadata.json` and equivalent `metadata.csv`: exact eight `catalogue` rows recovered from the historical second-call payload. No caption, category, tag or ID was rewritten.
- `app-preview.json`: exact `/api/semantic/preview` body, with configured_model and action_source=model. The label is neutral and does not reveal a food interpretation. No manual action or confirmed target is silently supplied.
- `first-model-input.json`: exact initial action-parser logical payload/schema using the current source prompt. The grounding call must use the actual returned action and the supplied metadata, not the old response as a forced answer.

JSON files are canonical UTF-8 with no trailing newline; CSV uses UTF-8/LF. They are logical inputs, not approved CLI transport configuration. The request repeats none of the existing labels Evening/Afternoon/Repair and does not say food, cooking, bread, pasta or salad.

## Stated facts and unknowns, by item

| ID | Explicit metadata facts | What remains unknown |
| --- | --- | --- |
| 81001 | A cook prepares an edible tomato-and-pasta dinner; ingredients and finished plate are shown. | Whether this particular viewer would feel hungry; any unstated dietary property. |
| 81002 | Mechanic cleans/lubricates a bicycle chain; no food or meal is shown. | Any personal appetite association unrelated to the described subject. |
| 81003 | Baker shapes edible dough, bakes a loaf and slices it for eating. | The viewer's appetite response and unstated dietary facts. |
| 81004 | Electrician replaces a lamp switch; no food or cooking is shown. | Any idiosyncratic personal appetite response. “Cooking” occurs in a negated description, not positive evidence. |
| 81005 | Duration/colour palette are listed; subject is undescribed. | Whether it depicts food, eating or any appetite-related subject. |
| 81006 | Cook chops edible vegetables and mixes a salad intended for eating. | The viewer's appetite response and unstated dietary facts. |
| 81007 | Train crosses a bridge; no food or cooking is shown. | Any idiosyncratic personal appetite response. |
| 81008 | Title/thumbnail unavailable; no content description. | Subject and whether any food/eating relation exists. |

## Honest outcomes and operator judgment

“Not hungry” describes a personal state, while “remove” supplies an exclusion direction. A model may interpret the remaining phrase as appetite-stimulating food preparation, with a reason grounded in 81001/81003/81006. **Only under that interpretation**, those three descriptions are the supported food-related targets, 81002/81004/81007 explicitly depict unrelated activity with no food, and 81005/81008 remain unknown. Do not treat missing descriptions or a shared Evening/Afternoon tag as positive or negative food evidence.

Metadata cannot prove the user's subjective hunger response. If the model considers this unresolved or sees competing meanings, clarification with no Apply is valid conservative behavior in the prospective case. It is not a successful inferred-exclusion demonstration. A no_match result must also be preserved as returned, not relabeled as matching success. Do not supply a clarification answer automatically, switch to confirmed-target mode, or rewrite the request to obtain a pass. Any later user clarification would be a separately identified continuation, outside these two prepared scenarios.

If the model does return a supported proposal, the operator must review its actual operation, retained intent span, reason, negation handling, exact quotations and completeness against all eight records. Missing 81003 or 81006 under the food interpretation remains incomplete even if Apply/Undo works. Selecting a sparse or explicitly no-food row requires support that these descriptions do not supply.

If and only if that exact three-item exclusion is returned and approved, the mechanical expectation is 8→5→8 after Apply/Undo. A different valid interpretation is judged on its own evidence, not forced into that set. Current indirect output lists selected items and quotes; it does not return the category flow's complete tri-state membership table. Distinguish reviewer-marked unknowns from model-returned dispositions.

This path maps indirect meaning to existing described items and their existing metadata. It does not rename Evening/Afternoon/Repair to Food or prove a separate category-label classifier. That boundary should be said plainly.

## Source, tests, calls and limits

Existing app path: `semantic_review.interpret_action` → `indirect_grounding.propose_indirect` → source/ID/quote checks → actual review/Apply → reviewed Undo. `semantic_review.confirmed_target_context` is a different explicitly confirmed mode and must not be used to disguise an automatic interpretation failure.

Relevant authored checks in `tests/test_indirect_grounding.py` and `tests/test_semantic_review.py` cover indirect evidence, ambiguity, negation, action types and no-match state preservation. `test_explicit_manual_action_ablation_never_calls_the_action_parser` distinguishes manual direction from model interpretation. `test_cleanup_uncertainty_latches_across_factories` protects shared transport stopping. No new tests or inference were executed for this scenario.

Minimum complete inference path: **2 logical calls** (action interpretation, then grounded selection). An action-stage clarification stops after 1. Review, Apply and Undo add zero calls. Later exact grounding bytes depend on the actual action and must be retained during a separately approved run; the old Llama action is not a permitted substitute.

A supported result would demonstrate one exposed nonliteral request on these invented descriptions with actual Fable output and reviewed filtering. It would not establish subjective appetite prediction, general semantic accuracy, a stronger-model comparison, real-user utility, held-out performance or repair of the frozen failed study. A clarification would demonstrate safe abstention only.
