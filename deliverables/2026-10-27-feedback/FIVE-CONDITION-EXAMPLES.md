# Five matched condition examples

These are **in-process demonstration outputs** reproduced on 27 October from the saved processed KuaiRec data, frozen seed-42 checkpoint and current rule parser. They are not new test-set results, a browser acceptance test or Llama inference. Run `python deliverables/2026-10-27-feedback/reproduce_demo_examples.py DATA_JSON MODEL_DIR` from the FP checkout; `demo-example-receipt.json` records the output. The example uses user 14 and the same scored catalog throughout. The input intent is set explicitly before parsing. Category IDs are opaque.

The untouched history-only top ten is `8958, 7383, 1116, 2894, 4367, 6001, 2687, 4506, 10217, 6090`. This neutral ranking is a reference, **not** Condition A after feedback. The matched intervention chooses a like on item 1116 for A/B and an explicit category_1 boost for C/D/E. Those interventions differ in scope, so their downstream difference cannot alone isolate a language-model effect.

| Condition | Input and expected mechanism | Actual top three; target category_1 count in top ten | Evidence and limit |
| --- | --- | --- | --- |
| A item feedback | Like item 1116; +0.25 affects only that item. | `1116, 8958, 7383`; 0/10 | Receipt condition A. This simulates feedback; it is not observed thumbs data. |
| B explanations | Same item like, plus explanation display. Ordering must match A. | `1116, 8958, 7383`; 0/10 | Receipt B top ten equals A and `explanations_enabled=true`. This tests ranking invariance, not human understanding. Per-card provenance can be cached LLM or template and must be read on screen. |
| C free text | Rule parser reads `Show me more category_1`; shared policy boosts all matching items by 0.25. | `10138, 2666, 937`; 9/10 | Receipt C. It proves deterministic control in this example, not an LLM advantage. |
| D editable profile | Rule profile parser saves `Show me more category_1.` and applies the same category weight. | `10138, 2666, 937`; 9/10 | Receipt D. The profile also displays factual history text, which is not itself an explicit preference. |
| E combined | Matching C command and D profile, with explanations. The explicit command takes precedence and is not summed twice. | `10138, 2666, 937`; 9/10 | Receipt E equals C/D in this case, with explanations enabled. Equality is an expected finding, not a missing effect. |

All five lists contain ten items. The receipt's `feedback_count=1` remains displayed in C/D/E because the user session stores the like, but `api.py:150-157` applies it only to A/B. Likewise, C does not silently inherit the editable profile and D does not silently inherit the latest free-text instruction. A separate clean-session UI run should reset user 14 before a professor-facing replay; do not treat these in-process results as proof that the browser was clicked in this check.

## Mute and conflict examples

- With the command `Mute category_28` in C, the resulting top three are `7383, 2894, 2687`, the list remains 10/10, and target category_28 appears 0/10. The original neutral top ten contains six category_28 items. Current `controls.rerank` removes muted-category items; it does not merely lower their scores. The meeting's spoken description of mute as a graded decrease was inaccurate for this code.
- In E, a saved profile boost for category_1 and a **latest explicit mute** for category_1 yield zero category_1 items in the ten displayed. `controls.apply_to_profile` replaces the same-category weight, rather than adding conflicting signals. This is a local policy example, not a separate E2 compound/conditional language test.
- The rule parser maps `less/fewer category_N` to the same hard mute. A soft reduction is not implemented in this app. The revised E2 research parser has a different structured command vocabulary; do not infer its capabilities from these live controls.

## Evaluation coverage, separate from this demonstration

| Question | Existing evidence | Gap or constraint |
| --- | --- | --- |
| Can A-E run on matched fixed scores? | E1 protocol and the current `api.py:140-187`; this receipt shows A-E on one user. | A-E are configurations, not an experiment that isolates all independent channel effects. |
| Do explanations change ranking? | E1 B is rank-identical to A; the receipt repeats it. | No measured user response to explanations. |
| Does canonical category steering change exposure? | Frozen E1 covers A/B versus C/D/E with TCP/TCER and quality metrics. | Equal rule/LLM canonical rankings mean this does not show LLM-specific added value. |
| Can Llama interpret broader requests? | E1 broader synthetic parser check and fresh AI-reference E2; 20 October student-label exploratory parser check is separate. | Synthetic/model-authored references and validation failures limit human-language claims; the exploratory check has no ranking measure. |
| Does an actual user benefit? | No participant study. Historical next-item HR/NDCG and offline exposure are proxies. | No claim of satisfaction, trust or utility. A new prospective human-intent design would require a separate scope decision. |
