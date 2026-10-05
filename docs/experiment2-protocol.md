# Experiment 2: expressiveness of one natural-language interaction

Protocol authored: 2026-09-29 UTC. Status: prospective development protocol, not an executed test report. The final freeze receipt supplies the exact timestamp and hashes. A change after that freeze requires a new experiment identifier, not replacement of this study's test results.

Revision note, 29 September 2026 UTC: the active bank is `language-v2/`. Independent cold review of development wording identified a feed-level versus same-item ambiguity. Conditional wording was clarified in a separate version before any reserved inference; v1 corpus bytes and gold were retained. The parser must clarify explicit feed-level conditions rather than reinterpret them as same-item conditions. The student must use the v2 worksheet.

## Separation and purpose

Experiment 1 is finished. Its data, checkpoints, prompts, gold labels, parser test and recorded results remain byte-identical. Experiment 2 imports its statistical utilities and frozen scores but uses a new parser module, backend flags, utterances, cache and output tree under `results/experiment2/`. No Experiment 2 result may be inserted into an Experiment 1 result file. The original application remains the Experiment 1 demonstration.

The thesis tested here concerns how much intent one interaction can express. Offline synthetic requests cannot establish that language feels more natural, improves satisfaction or improves recommendation accuracy. The comparison concerns a specified item-feedback proxy, not every possible learned thumbs algorithm. An advantage over that proxy alone is insufficient evidence of an LLM contribution; the same utterances also go through an extended rule parser.

## Hypotheses and decision rules

- H1, expressiveness: the LLM achieves greater induced intent satisfaction than A and than the rule parser. Report each of four classes and their pooled result. H1 passes only if both pooled differences are positive and both corresponding one-sided Wilcoxon tests have BH-adjusted q below 0.05. Class-specific results remain explicit; a pooled pass does not establish a pass in every class.
- H2, information per interaction: the LLM produces greater intended-direction rank movement than A with exactly one interaction each. H2 passes only for a positive pooled difference and its one-sided BH-adjusted q below 0.05. This operational metric is not a measurement of Shannon information or human effort.
- H3, quality cost: describe paired NDCG@10 and HR@1 changes for every channel relative to A and recency popularity, with user-level bootstrap intervals. H3 has no pass threshold and no non-inferiority claim.

The confirmatory BH family contains exactly 11 tests: H1's four classes plus pooled, each for LLM versus A and LLM versus rule, and the pooled H2 LLM versus A test. No alternative threshold or test family will replace an unfavorable outcome. If either H1 or H2 fails, the conclusion will state that natural-language feedback did not demonstrate an expressiveness advantage under this protocol, and identify the failing contrast. An unexecuted hypothesis is **not assessed**, not failed or passed.

These are prespecified statistical decision rules, not proof that all inferential assumptions hold. Pratt signed-rank inference relies on a suitable symmetry interpretation and an asymptotic approximation with ties and sparse differences. BH control relies on independence or an appropriate positive-dependence structure, which this study does not establish for all 11 contrasts. Report these limits beside any future pass; a small q cannot validate the intent construct.

## Language material and human annotation gate

An independent author prepares 48 development utterances, 12 per class, and 100 reserved test utterances, 25 per class. Both splits span all 31 official identifiers `category_0` through `category_30`. These are opaque metadata labels, not inferred topic names. The corpus is AI-authored synthetic language. Dev and test text are disjoint. Test wording is authored without reading the parser implementation; the parser developer receives dev only.

`language-v2/test.sealed` is a procedural seal, not encryption. Its bytes, creation time, counts and category coverage are committed before parser development finishes. Root and parser implementers do not inspect its utterances during development. The blind student annotation sheet contains text and empty response columns, with no author gold or model outputs. The student must annotate every test item using `docs/experiment2-annotation-rubric.md`, identify themselves and date the pass. AI annotation does not fulfill this requirement.

Freeze the parser prompt, rule extensions, schema and implementation after dev work. Compare the student's independent labels with the author's initial labels before any model test inference. Report full-command exact agreement and Cohen's kappa on canonical command labels, plus operation, category, strength, floor and condition agreement. Report undefined kappa as undefined, not 1. Resolve disagreements without model predictions, preserve both original passes and record the final gold and reasons. The `compare-annotations` stage preserves the original student-only receipt, source bytes and independent labels, computes agreement before adjudication, and records a separate annotation opening. It makes no model or ranking calls. Full freeze requires this comparison record and a separate final receipt supplement, enforcing parser commitment <= student completion <= comparison <= adjudication <= full freeze. A genuine completed second pass and adjudication receipt are prerequisites for test execution. No agreement number is available while that pass is missing.

Adjudication must remain truthful. Independent student labels may use `clarify`, and these labels remain in the agreement calculation. Before full freeze, every final adjudicated command must match its committed intent class and the exact metric forms below: compound is a moderate boost plus moderate reduction; graded is a slight boost, strong reduction or exclusion; floor is a moderate reduction with floor 1; conditional is a moderate same-item boost. If any final consensus is `clarify` or outside its class form, stop this ranking study with explicit case IDs and reasons. Preserve the genuine labels and agreement. Do not silently exclude or relabel cases, coerce annotators, substitute cases or change thresholds to make the bank fit. Any replacement requires a separately committed prospective protocol and bank decision before inference, with independent annotation and freeze steps repeated as appropriate.

Annotation validation has its own auditable recovery rule. Preserve the immutable first-access marker and each started/finished attempt. A failed wording check may be retried only with an explicit prior-failure record and correction reason, unchanged canonical labels, annotator, parser and committed bank. A singleton successful-comparison marker prevents repeat success. This permits transport correction, not a new independent annotation after unblinding. It never opens evaluation or makes model calls.

The single evaluation opening occurs only after frozen code and the annotation gate are verified. Annotation and adjudication are distinct authorized accesses by the annotators, not opportunities for parser development. The evaluator records first opening, validates the committed bytes and refuses a fresh rerun into an existing output. Any interrupted execution retains its outputs and can only replay committed evidence without tuning. All test items remain in the parser-accuracy denominator. Parser exact accuracy by class and pooled is saved before ranking results are generated.

## Command representation and policies

The new facade accepts `rule_compound` and `ollama_compound`. Existing `rule` and `ollama` use unchanged Experiment 1 code. The compound object contains an operation (`set` or `clarify`) and at most two directives. Each directive contains an operation (`boost`, `reduce`, `exclude`), category, strength (`slight`, `moderate`, `strong`, `none`), floor (0 or 1), and nullable condition category. Directive order is semantically irrelevant; canonical comparison sorts by numeric category identifier. Unknown categories, ungrounded conditions and conflicting directives are invalid.

Scores use Experiment 1 min-max normalization. Slight, moderate and strong adjustments have magnitude 0.10, 0.25 and 0.50. Boost adds and reduction subtracts that amount. Exclusion removes matching items. A floor of 1 preserves at least one matching item in the top 10 when the catalogue and other directives permit it, by stable replacement using original adjusted-score order. This is explicit enforcement, not a learned language-model ability. Conditional boosts apply only to the intersection of the two categories; they do not prohibit all non-intersection items. Ties use ascending item identifier. Neither parser gets a stronger ranker.

Llama 3.1 8B is the only LLM backend, with temperature 0 and parser seed 42. Record model digest, Ollama version, options, complete prompt, schema, request, response, timestamps and cache-key hashes. No rule output substitutes for an unavailable LLM. A startup availability failure stops execution; individual failed or invalid responses remain recorded failures and yield no new control.

## Requests and one-interaction comparators

Use the same 865-user cohort, 2,593-item candidate policy and frozen SASRec checkpoints for seeds 42, 43 and 44. Each user receives one request per class, if a test-bank utterance has all its mentioned categories represented in that user's train plus request-history sequence. Sort eligible case IDs, compute SHA-256 of `2026:{user_id}:{class}`, interpret the first eight bytes as an unsigned big-endian integer, and select modulo the eligible count. Record absent eligibility; do not silently drop it or manufacture a category. This extends Experiment 1's deterministic history-based scheme. No held-out interaction, quality result or baseline ranking selects the request. Test-language material supplies wording, never behavioral outcome labels.

Reuse an exact utterance and its cached parse across users and seeds. Do not substitute category tokens after parsing. Language accuracy is based on 100 unique utterances, not the larger number of ranking rows. User intervals condition on this finite wording bank and do not estimate generalization to all possible language.

A receives one positive or negative reaction on the latest historical exemplar for the first directive in numeric category order. Conditional requests use a historical intersection exemplar when present, otherwise a target-category exemplar. Positive A adds 0.25 to that one item's normalized score; negative A removes that one item, exactly as Experiment 1's proxy. There is no second click, category inference or adaptive follow-up. Rule and LLM each receive the entire single utterance once. They share the same scores, candidate catalogue and ranker. This deliberately varies how much can be specified per interaction; it does not equalize semantic content or effort.

All channels and the recency comparator have the same permitted pre-test corpus: all training and request-history interactions plus catalogue metadata. SASRec weights remain trained on the training window and inference uses the user's earlier sequence; recency popularity counts all users' request-history items. Thus information availability and time boundary are matched, while actual estimator use differs and is stated. Recency is deterministic; its score vector is repeated across seed pairs without treating repetitions as independent evidence. No channel receives final-test labels until metric calculation. H3 compares predictive performance, not a causal effect of granting additional information.

## Prespecified top-10 measures

All satisfaction measures require a full ten-item list. Let n(S) count top-10 items in category set S; let X and Y denote target categories. First report band attainment, baseline band attainment and strictly induced satisfaction separately.

| Class | Band requirement | Intended movement M relative to uncontrolled ranking |
| --- | --- | --- |
| Compound, more X and less Y | n(X) >= 2 and n(Y) <= 1 | min(delta D(X), -delta D(Y)) |
| Graded, a bit more X | 2 <= n(X) <= 4 | delta D(X) |
| Graded, much less X | n(X) <= 1 | -delta D(X) |
| Graded, none of X | n(X) = 0 | -delta D(X) |
| Less X but not zero | 1 <= n(X) <= 2 | -delta D(X), zeroed if the nonzero floor is violated |
| More X only if also Y | n(X intersection Y) >= 2 and n(X outside Y) <= its baseline count | delta D(X intersection Y) minus max(0, delta D(X outside Y)) |

D(S) is discounted top-10 exposure: sum over ranks r=1..10 of membership in S divided by log2(r+1), normalized by the sum of those ten discounts. Missing slots contribute zero. Delta is channel exposure minus uncontrolled exposure. M is already per interaction because every channel receives one interaction. A decrease or collateral movement can make M negative. H2 compares this signed metric, not a count of all changes irrespective of intent.

Primary H1 satisfaction is 1 only when the band is met and M > 1e-12. An unchanged list that already meets a band is not an induced success. Report the band alone as descriptive evidence so mechanical enforcement and genuine directional change remain distinguishable. Bands and weights are design constants, not values optimized on dev or test ranking outcomes.

The cardinalities are operational conventions, not independently validated human interpretations of words such as "a bit." For example, an increase from five to six target items misses the slight-boost band despite moving upward. Student annotation validates the utterance-to-command mapping, not these numerical bands. Restrict all satisfaction claims to the prespecified operational metric.

Rare categories, impossible intersections and saturated baselines are expected. Keep every assigned request in the primary intention-to-treat denominator, including impossible ones, and report catalogue feasibility and no-opportunity flags. Supply descriptive feasible-stratum results only with their denominators and without a second hypothesis claim. Do not reassign requests, enlarge category bands or discard failures after seeing results.

## Analysis and quality caveats

Average seeds within each user/request before averaging requests within a class. Pool with equal class weight within user among eligible classes, reporting missing classes. The user is the resampling and hypothesis-test unit. Reuse Experiment 1's Pratt signed-rank implementation and 5,000-resample percentile bootstrap with seed 2026. Convert its two-sided p value to the prespecified greater-than alternative using the signed statistic's direction, including ties; do not choose a tail from the observed preferred result. Apply BH once to the 11-member family. Report effect sizes, user counts, nonzero counts, confidence intervals, raw p and q.

Report parser exact-match accuracy before any ranking table. Then report H1 per class and pooled against both comparators, H2 movement and floor violations, and H3 paired changes in first-next-item HR@1 and NDCG@10 versus A and recency popularity. Retain the low-baseline and sparse-pair warning from Experiment 1. A large interval, sparse hits or an absolute margin spanning the baseline cannot justify preserved useful quality. No Experiment 2 non-inferiority test will be performed.

## Execution, replay and release evidence

The Experiment 2 manifest records status, protocol and implementation hashes, data and checkpoint hashes, split commitments, annotation and freeze receipts, model provenance, timestamps and each produced file. Development results and synthetic unit-test fixtures are explicitly separate from reserved-test outcomes. Replay verifies hashes and recomputes summaries from recorded parser responses and rows; it must not invoke a different parser or quietly recompute a missing result with the rule backend.

Before release, independent cold reviewers receive only the rebuilt package: a raw-number recomputation; a claims/protocol/slide/plan audit; and fresh-environment engineering, archive, browser and replay checks. Findings remain verbatim. Execution failures, absent annotations and unperformed Windows/Colab checks remain visible. A blocked study cannot be certified complete by passing its software tests.
