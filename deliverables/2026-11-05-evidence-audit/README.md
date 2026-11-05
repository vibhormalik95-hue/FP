# Evidence assessment and conservative source constraints

Development revision after published `69c1ae545ee83ace8dcea3ec841f33ee59d4438f`. This document records engineering checks and exposed synthetic development results, including failures. It does not replace frozen E1/E2 or the November 4 study. New code and analysis are assistant-generated work, not a claim of later personal student authorship or hours.

## Why another guard

The earlier IP68 example showed that real source quotations can accompany an unsupported category or membership. The assistant reviewer rejected that example; quotation validation did not establish semantic truth. A second model pass can also be wrong. This revision preserves explicit definition and membership review and adds two narrower checks:

1. **Blinded evidence assessment.** After complete classification, a separate call receives only the approved definition and supplied source metadata, without primary membership decisions or reasons. It assesses every item as `supported`, `contradicted`, `not_stated` or `ambiguous`. A primary positive survives only with `supported`; disagreements become unknown. Primary unknowns/negatives never become positive. The same installed model may perform both passes: this is not independent ground truth.
2. **Declared literal witnesses.** Digit-bearing terms in the request and approved definition must have word-delimited, Unicode-normalized literal witnesses in an item's metadata before it may remain positive. The definition review displays these terms. Missing witnesses force unknown. This is a conservative text constraint, **not semantic entailment**: equivalent words, conversions or ranges can be withheld, and a present term may be negated, quoted or unrelated. Qualitative attributes without such terms remain dependent on fallible assessment and review.

Both original decisions and assessments, source/model digests, unknowns, withheld items and literal witnesses are retained. Apply, feed reads and undo restore revalidate the entire sealed record against current source and inventory. No new items or observations are invented. The original indirect-intent route is unchanged; this guard is installed in the staged category workflow only.

### Code map

| Component | File |
|---|---|
| Blinded assessment, strict quote/ID validation, conservative intersection and revalidation | [evidence_audit.py](../../feedctrl/evidence_audit.py) |
| Declared text requirements and source witnesses | [source_constraints.py](../../feedctrl/source_constraints.py) |
| Definition seals and bounded complete classification schema | [staged_induction.py](../../feedctrl/staged_induction.py) |
| Additional bounded call, race/state checks and separate receipts | [staged_routes.py](../../feedctrl/staged_routes.py) |
| Review disclosures and per-item assessment display | [SemanticPanel.jsx](../../web/src/SemanticPanel.jsx) |

The workflow has two review stages and at most **three** generation calls: definition; then classification and evidence assessment. Each call is limited to 90 seconds plus identity probes. Existing 2–12-item, evidence-byte and actual chat-byte limits remain. There is no retry or rule fallback after a failed stage.

## Fresh development assessment experiment

Two new authored predicates used eight explicitly synthetic records: affirmative current service terms, an explicit denial, a different term, missing information, a future hope, a quoted question, a second affirmative promise and an instruction-like caption. References were written in the same assistant context. They are not independent/human gold or a held-out bank.

The first predicate required a current 18-month service plan; intended positives were 1/7. The second required an independent laboratory abrasion score of exactly 90 points, absent from all source records. To test the guard, the primary proposal was an **intentionally wrong all-positive software double**. Only the separate assessment used an actual model, and it never received that double's decisions.

| Model / task | Exact per-item assessments | Retained positive IDs before the literal-witness revision | Outcome |
|---|---:|---|---|
| Qwen / current plan | 7/8 | 1, 7 | Intended positive set; explicit denial misclassified as not stated |
| Qwen / absent laboratory score | 8/8 | None | All positives withheld |
| Llama / current plan | 7/8 | 1, 7 | Intended positive set; same denial error |
| Llama / absent laboratory score | 6/8 | 7 | **Unsupported positive survived.** One other item was wrongly called contradicted |

These are **four actual assessment calls**, two requests per model, not 32 independent requests. Generation times were Qwen 16.79/10.67 s and Llama 21.62/18.64 s. Exact installed model digests and raw outputs were retained. The eight definition/membership functions constructing the adversarial proposals were simulated, not model calls.

After freezing those predictions and their exact source, the declared text-witness contract was added. Pure cached-response reprocessing changed Llama's absent-score result from positive 7 to **no positives / all unknown**, because no item contained the required literal `90`. Qwen's abstention and both supported sets stayed the same. This is **post-development deterministic reanalysis with zero new inference**, not a fresh model success; original assessment errors and outputs are unchanged. It neither demonstrates general semantic reliability nor makes numeral presence sufficient evidence.

## Served/browser execution, including the failed attempt

The prespecified full-app rehearsal used the same development catalogue and an assistant reviewer. It was not another independent accuracy case.

1. **First attempt failed safely.** Llama proposed a supported definition, but returned only 3/8 classification rows (IDs 1/7/8; 2–6 omitted). Validation returned `ready:false`, `applied:false`, with no apply token. The evidence-assessment call was unattempted. Saved groups/history and original A–E remained unchanged. Both actual generation receipts are retained.
2. **Structural repair.** The generation schema now binds `minItems=maxItems` to the declared pool size and restricts item IDs to the supplied inventory. This adds no expected answer and changes no semantic prompt. Independent validation still rejects omissions, duplicates, invented IDs and invalid quotations. The failed attempt was not overwritten.
3. **One bounded repair rehearsal succeeded mechanically.** Actual Llama definition, complete classification and separate assessment calls took 14.25/14.05/16.08 s. All eight rows were present. After explicit reviews in the rendered browser, only intended IDs **1/7** were excluded: eligibility **8 → 6**, resulting order **4/2/3/5/6/8**, identical to manual intended exclusion on the same score vector. All remaining numeric scores were unchanged. Clear restored eight items; reviewed undo restored the exact group/feed; reset cleared groups/history. Original A–E before/after JSON was identical.

The repair's final dispositions were **7/8** against the declared development references: item 2's explicit denial became conservative unknown after the audit called it not stated. Correct positive membership does not erase that error. Literal-witness constraints and the same-model/can-be-wrong warning were visibly rendered before approval. This is exposed-development repair evidence, not confirmatory generalization.

This revision's executed work totals **nine actual generation calls**: four assessment diagnostics, two in the failed rehearsal, three in the repair rehearsal. There were eight simulated fixture functions and four cached deterministic reanalyses, not additional inference. No paid calls, downloads, external provider transmission or held-out access occurred.

### Clarification of the preserved repair protocol

The executed `repair-protocol.json` is preserved byte-for-byte at SHA-256 `5dcfef338831da3f0260d6459425b448ad97d0653e9cf290a803752fca2bddc0`. It inherited descriptive fields from earlier phases. Its `followup` wording about unchanged frozen source/prompts describes the earlier rehearsal plan, not source equivalence between all phases. Its `post_development_change` statement that no model prompt/schema changed describes the literal-witness addition; it does not describe the later membership-schema repair. The inherited four scheduled audit calls were already completed, not four more calls in the repair phase.

| Phase | Actual execution and change |
|---|---|
| Initial assessment diagnostics | Four real assessment calls against intentionally wrong software-double primary proposals; outputs then frozen |
| Literal-witness revision and first full-app rehearsal | Four cached reanalyses, then two real calls; incomplete 3-of-8 membership failed safely before assessment |
| Explicit structural repair | One exposed-development rehearsal with three real calls, using the recorded `source-cardinality-v3` snapshot and complete-count/supplied-ID generation schema |

For the final phase, `phase`, `structural_change`, `maximum_generation_calls_this_phase: 3`, the source hashes and `previous_workflow_protocol_sha256` describe the actual repair. Source/schema changed as disclosed; semantic prompts, tasks and reference answers were unchanged. This clarification neither retroactively amends the executed protocol nor makes the exposed repair an independent test. No further model calls were made to address the review comments.

The UI now distinguishes assessment disagreement from missing literal witnesses. The latter can withhold a primary positive even when both model passes agreed; it must not be labelled model disagreement.

## Software verification

- Full suite at reviewed revision `6a7b290`: **529 passed, 1 skipped** (private parser banks absent).
- Affected audit/staged/literal contracts: **68 passed**. These include explicit tests showing two passes can agree wrongly, unchanged-state failures, complete IDs/quotes, current-source/seal checks, stale undo, races, immutable snapshots, literal false-positive boundaries and canonical unknowns.
- UI build: passed, 30 modules. Browser/API evidence above is separate from mocked software tests.
- Independent review of the exact `6a7b290` packet verified all 118 manifest hashes and the base-to-candidate patch, ran 117 unmodified test-function invocations (including the 68 affected checks) and nine additional probes, and found no blocking source/mechanics defect. Report SHA-256: `fe7c67a661b84e30ebf81375cea5413be7081cbf043417ad085d70f9999cfed0`. This does not independently establish browser execution or semantic reliability. The subsequent label/phase wording corrections are separate from that reviewed source revision.
- Earlier frozen outcomes and the failed original IP68 examples remain unchanged. No scientific improvement or human benefit is claimed from these development checks.

## Remaining requirements and boundary

| Professor track / deliverable | Current evidence | Remaining gap |
|---|---|---|
| Manual category control baseline | Existing fixed-score implementation, mechanical tests and manual comparator receipts | Preserve negative empirical results; this is not proof of better human relevance |
| NLP-created categories feeding the filter | Published reviewed definition/membership path; local assessment/constraint revision and actual repair rehearsal; bounded independent source/mechanics review passed for `6a7b290` | Publication of the local revision; fresh independently held semantic references across attributes, ambiguity, negation and no-match |
| Indirect intent matching existing categories/tags | Separate opt-in existing workflow; no changes to it in this revision | Broad indirect-intent quality and bilingual equivalence are not established by this direct attribute fixture |
| Code walkthrough, attribution and results | Source map above, explicit assistant attribution, failed and successful receipts | Integrate reviewed new evidence into the professor packet; do not say all semantic claims are proven |
| New-item pledge / frontier comparison | Outside this local safety revision | Clarify what new items means; real observations cannot be fabricated. Provider access, data destinations and spend need their separately approved scope |

The supplied stage-ledger adapter could not be installed through the supported Library helper on Windows (`os.setxattr` unavailable before atomic installation). Its bytes/hash were not independently verified here, so its 70 synthetic checks were not rerun and application receipts are **not yet integrated** into that adapter. Original receipts remain available for a supported handoff; no alternate download or access bypass was used.

This is a local review candidate following the verified public baseline. Publication is a separate action. No professor email or main merge was performed.
