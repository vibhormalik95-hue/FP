# Publication contribution and completion roadmap

**Updated:** 3 October 2026 UTC  
**Status:** Supervisor discussion document, not a claim of submission readiness or acceptance.

The defensible contribution today is a reproducible offline study separating language parsing, deterministic category enforcement and historical next-item quality. Its results are mixed and bounded: enforcement works, the canonical LLM path adds no observed advantage over rules, broader synthetic parsing misses the 85% target, and boosting reduces NDCG@10 on a weak backbone. Experiment 2 has a compound-intent protocol and recorded development work, but its central hypotheses are not assessed.

## Strengthening the contribution

The strongest plausible direction is an empirical study of when richer feedback changes a feed in the intended direction, and whether an LLM contributes beyond rules under the same enforcement policy. The publication claim must follow the results. "LLMs improve recommendation accuracy" is not supported by this evidence.

| Contribution candidate | Present evidence | Remaining requirement |
| --- | --- | --- |
| Separate parser ability from policy enforcement | E1 LLM and rule canonical rankings agree; broader parser errors; explanation equality | Reconstruct results and keep the narrow synthetic scope explicit |
| Compound intent satisfaction per interaction | E2 protocol, schema, bank commitments, dev runs and tests | Genuine student annotation, agreement, adjudication and one reserved evaluation |
| LLM value beyond rules | Matched text and enforcement are prespecified | Reserved H1 comparisons against both A and rules, per class and pooled |
| Quality cost of control | E1 boost NDCG paired CI and backbone diagnosis | E2 H3 paired changes with CIs, preserving the sparse-baseline warning |
| Reproducible artifact | Frozen records, scripts, manifests, caches and historical checks | Independent replay and honest environment-specific acceptance records |

## Completing the current study

1. **Confirm scope and authorship.** Obtain the supervisor's decision on the revised question, deliverables, AI disclosure and student responsibilities. A course email and unsigned proposal do not approve the revised individual design.
2. **Resolve the real annotation gate.** Record actual prior exposure, complete the required human pass, calculate pre-adjudication agreement and adjudicate blind to model predictions. Preserve original labels. If the protocol can no longer be fulfilled, record that limitation and agree a separately identified prospective replacement. Do not substitute AI labels for a student pass.
3. **Restore the specified runtime.** The 3 October check found no Ollama executable and a refused local endpoint. Confirm Llama 3.1 8B and provenance in an authorised environment. Cache replay cannot count as new inference.
4. **Freeze and evaluate once.** Preserve the parser commitment, verify all required receipts and hashes, then report reserved parser accuracy before ranking results. Retain failed parses and impossible assigned cases under the committed rules.
5. **Run the prespecified analysis.** Average seeds within user. Report H1 by class and pooled against both comparators, H2 movement against A and H3 paired quality changes. Use the fixed eleven-test BH family. Do not change weights, bands or exclusions after seeing outcomes.
6. **Integrate and reproduce.** Replace pending text only with recorded evidence. Keep failures, conduct independent numerical, claims and engineering reviews, preserve reports verbatim and check course page and talk lengths.

These steps make the study reviewable. They do not guarantee a positive hypothesis result, sufficient novelty for every venue or publication acceptance.

## Conclusions conditional on the evidence

| Outcome | Defensible interpretation |
| --- | --- |
| H1 and H2 both pass | The channel demonstrates an expressiveness advantage under this protocol's operational metrics and proxy comparators. Report class results, effect sizes, intervals, parser accuracy and quality costs. Naturalness is still unmeasured. |
| H1 fails against rules | Natural-language feedback did not demonstrate an expressiveness advantage under this protocol. A gain over A alone could support richer controls over this proxy, while added LLM value remains unsupported. |
| H1 fails against A or H2 fails | Natural-language feedback did not demonstrate an expressiveness advantage under this protocol. Identify the failed contrast and explain it using reported parsing, feasibility, movement and policy evidence. |
| Evaluation stays blocked | H1/H2 remain not assessed and H3 has not run. Development success cannot supply a reserved-test conclusion. |

## Extensions needing separate prospective evidence

Experiment 1 stays frozen. These extensions cannot replace its results or redefine Experiment 2 after outcome inspection.

- **Stronger recommendation baseline:** select hyperparameters through genuine pre-test validation, match temporal information use and retain recency popularity as a comparator. Reserve untouched outcomes for new claims. Hashing an exposed test again does not restore independence.
- **More representative language:** independently author or elicit requests, validate semantic category mappings and include unsupported inputs. Prespecify sampling, sample-size justification, annotation and error analysis. Human collection may require approval and cannot be replaced by synthetic text while keeping the same claim.
- **Broader comparators:** consider a justified item-feedback method that infers attributes, direct structured controls and an oracle parse for diagnosis. State which comparison identifies language understanding, granularity or interface effort. Equal interaction count alone does not match semantic content or effort.
- **Naturalness and usability:** use an approved human study with prespecified task success, effort, completion time and perceived ease outcomes. Counterbalance interfaces and distinguish interface preference from predictive accuracy. Offline exposure metrics cannot measure felt naturalness.
- **Sensitivity and external validity:** validate numerical bands independently and evaluate additional datasets or backbones. Analyses selected after current results are exploratory until independently confirmed.

Prioritise these with the supervisor. The 135-hour plan should first support understanding, completion and reproduction of the current study, rather than promise every possible extension.

## Submission readiness

- Every headline number is regenerable from immutable records.
- Development revisions and test accesses are documented.
- Test, development, live inference, replay and static inspection are distinguished.
- Novelty is compared with critiquing, editable profiles and language-preference research.
- Abstract, conclusion, tables and confidence intervals agree.
- The student can explain the code and recompute an example without scripted answers.
- Authorship, AI disclosure, data/model licences, venue scope and current formatting rules are checked before submission.

The next milestone is an approved completion decision and an honest Experiment 2 result, or a documented reason it remains unassessed. Credible negative evidence can strengthen the paper; overstating completion cannot.
