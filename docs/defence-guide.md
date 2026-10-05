# COMP 9500: supervisor discussion and defence guide

**Student:** Vibhor Malik  
**Updated:** 3 October 2026 UTC  
**Purpose:** Understand the reasoning, locate the evidence and explain the limitations. This is preparation, not certification of personal proficiency or completed student work.

Before the required Experiment 2 annotation, record your prior exposure and follow the annotation rubric. Do not inspect sealed text, author labels or parser predictions to prepare answers. AI annotations cannot become an independent student pass by signing them.

## A 45-second explanation

This project separates three jobs: predicting which videos to recommend, translating a request into a command, and enforcing that command. Experiment 1 shows that enforcement works, largely because of the deterministic ranking policy. The LLM and rule parser produce the same feeds for the simple templates. Llama gets 79 of 100 broader synthetic requests correct and misses the 85% target. Boosting also reduces historical next-item NDCG@10 by 45.7%, and the underlying recommender is weak. Experiment 2 is designed to test whether language satisfies compound intents better than one item reaction and a rule parser. Its reserved evaluation is pending, so an expressiveness or naturalness advantage is not established.

## Numbers and evidence

| Finding | Scope | Evidence in the repository |
| --- | --- | --- |
| 865 users; 2,593 items; seeds 42, 43, 44 | Filtered cohort and frozen training runs | `data/processed.json`; `results/models/seed_*/metadata.json` |
| TCP@10: 11.6% to 79.2% | A to C on boosts; C, D and E agree on canonical requests | `results/llm/combined-summary.json`; `results/llm/seed_*/request_metrics.csv` |
| TCER@10: 6.1% to zero | A to C on mutes; hard filtering supplies zero exposure by construction | Same ranking evidence |
| 120/120 canonical parses | 60 text inputs plus 60 profile inputs, reused across users; not 120 independent users | `results/llm/seed_*/summary.json`; recorded parse caches |
| Llama 79/100; rule 81/100 | Broader synthetic E1 parser test | `results/parser_ollama_test/summary.json`; `results/parser_rule/summary.json` |
| Llama 2/10 adversarial | Subset of the same 100 cases | Same parser summaries |
| Explanation selections: 10/10 equal the template | Ten cards for one user, no human quality study | `results/explanations.json`; `results/audit_revision/baselines.json` |
| Boost NDCG@10: 0.03012 to 0.01637 | Relative decrease 45.7%; paired change -0.01375, 95% CI [-0.02086, -0.00655] | `results/audit_revision/analysis-v1.json`, `boost_ndcg_tradeoff` |
| Uncontrolled HR@1: 0, 3 and 4 hits out of 865 | About 0.0%, 0.35% and 0.46% across seeds | `results/audit_revision/baselines.json` |
| Recency HR@1: 69/865, about 8.0% | Post-hoc comparator using pooled recent history | Same baseline file |
| E2 dev v1: rule 48/48, Llama 24/48 | Includes ten Llama operational errors | `results/experiment2/development-v1/summary.json` |
| E2 dev v2: both 48/48 | After development changes, not reserved-test accuracy | `results/experiment2/development-v2/summary.json` |
| E2 reserved ranking rows: 0 | H1/H2 not assessed; H3 not run; agreement unavailable | `results/experiment2/summary.json`; `results/experiment2/rows.jsonl` |

The boost NDCG interval is a **post-hoc secondary analysis**, outside the original primary BH family. Do not call it prespecified or attach it to pooled HR@1.

## Likely questions and answers

### What is the contribution if the LLM adds no advantage in Experiment 1?

An inspectable evaluation artifact and a bounded negative finding. The study separates parser accuracy, mechanical enforcement and predictive quality, exposing where apparent control success comes from the policy itself. It documents a weak backbone and a vacuous non-inferiority margin. The compound-intent protocol creates a testable follow-up, but an unexecuted protocol is not a successful experimental result. Publication strength depends on the evidence and its originality relative to prior work.

### Is this a new recommender or a new LLM?

Neither claim is made. A compact SASRec-style network supplies item scores. Llama 3.1 8B translates requests. Deterministic code changes scores or excludes items. Llama is not fine-tuned. The project does not establish a new recommendation architecture.

### What does SASRec-style mean here?

An independently implemented sequential model using item and position embeddings, causal self-attention and next-item training. It uses hidden dimension 32, two blocks, one head, context length 50, dropout 0.2, Adam learning rate 0.001, batch size 64 and 20 epochs. This is not an exact reproduction of the original SASRec experiments. Read `feedctrl/model.py` and checkpoint metadata before claiming implementation knowledge.

### What is a positive event and the prediction target?

A positive event has `watch_ratio > 2`, an engagement proxy rather than an explicit like. Shared global time cutoffs define training, request history and evaluation. The target is the first eligible positive item in the final window. The nominal split is 70/15/15 before positive filtering, so retained event counts need not have those proportions.

### Why opaque category IDs?

They provide checkable labels without guessing topic meanings. `category_12` cannot be called comedy or sport without a verified mapping. This makes command compilation auditable but limits relevance to ordinary topic language. Semantic metadata would need separate validation.

### How did you prevent request leakage?

Assignments use training history, request history and catalog metadata. E1 hashes `2026:user_id:operation`, interprets the first eight digest bytes as an unsigned big-endian integer, and selects a historical category by modulo. The latest earlier item in that category becomes A's exemplar. Final labels enter only metric calculation. Mutation tests check that altered final labels cannot change requests or rankings. This avoids that information path; it does not make the retrospective sample representative or causal.

### Why does the baseline affect only one item?

KuaiRec lacks the required thumb stream, so A is a defined proxy. One positive reaction boosts the chosen item by 0.25 after score normalization; one negative reaction removes it. A does not infer category preferences. Real learned feedback systems might generalise from a thumb. Conclusions apply to this proxy, not every item-feedback algorithm.

### Why include a rule parser?

An advantage over A could result entirely from giving a channel category-level information. The rule parser receives the same text and shares enforcement, helping isolate language interpretation. Identical LLM and rule feeds in E1 show no additional LLM benefit on canonical inputs.

### What are B, C, D and E?

B adds display-only explanations to A. C compiles text. D compiles an editable profile sentence. E combines text, profile and explanations, deduplicating repeated commands. B must equal A because display changes no score. C, D and E can agree because their intended commands match. This is consistency evidence, not a usability comparison or complete factorial design.

### What exactly are TCP, TCER, HR@1 and NDCG@10?

TCP@10 is the target-category count in the top ten divided by ten. On mute requests, target-category exposure is reported as TCER@10, where lower is desirable. A multi-labelled item counts once for the requested category. List fill prevents an empty list being mistaken for useful success. HR@1 is one when the first recommendation is the held-out target, otherwise zero. With one relevant target, NDCG@10 is `1/log2(r+1)` when the target occurs at rank `r <= 10`, otherwise zero. The ideal gain is one.

### Why can control improve while accuracy worsens?

A synthetic control changes the objective, while the historical target was observed without the intervention. A boost can move the feed toward the assigned category and move the original target down. The NDCG decrease is real for that metric. It neither proves human dissatisfaction nor establishes useful personalization.

### Why is non-inferiority uninformative?

The absolute margin is 0.10, or ten percentage points, against pooled A HR@1 of 0.0025048, or 0.25048%. Losing every baseline hit still fits the allowed loss. A post-hoc relative reading uses 10% of baseline, or 0.00025048. The simultaneous lower bound is -0.00077071 and fails that sensitivity threshold. The supervisor can clarify the intended interpretation, but cannot retrospectively make a new margin prespecified. Neither reading establishes preserved useful quality.

### Is recency popularity a fair comparator?

It shares the catalog and target, but uses recent information differently. Popularity pools all users' request histories. SASRec weights use the earlier window, although inference receives each user's recent sequence. The comparison diagnoses a large weakness in this setup; it does not show that popularity generally beats SASRec.

### Why three seeds and user-level analysis?

Seeds probe limited training variability without creating new people. Seed outcomes are averaged within user before paired analysis. The user is the resampling and signed-rank unit. E1 adjusts six primary contrasts jointly with BH. E2 prespecifies eleven: ten H1 comparisons, covering four classes plus pooled against two comparators, and one pooled H2 comparison. Sparse pairs, ties, signed-rank assumptions and dependence across contrasts remain limitations.

### How is Experiment 2 different?

It adds a separate compound schema and backend flags while preserving the original path. Classes are compound, graded, nonzero-floor and conditional. A conditional boost applies to individual items in the category intersection, not a feed containing separate X and Y items. There are 48 development and 100 reserved utterances across all 31 category IDs per split. Current 48/48 scores are development results only.

### What would count as success in Experiment 2?

H1 needs positive pooled induced-satisfaction differences against both A and the rule parser, with both one-sided BH-adjusted q values below 0.05. H2 needs positive pooled intended-direction movement against A with q below 0.05. H3 describes paired NDCG@10 and HR@1 changes with intervals and has no pass threshold. Report H1 by class too. An unchanged feed already meeting a band is not induced success. Impossible assigned cases stay in the primary denominator.

### Does H2 measure information in bits?

No. It measures signed intended-direction movement in discounted top-ten exposure per interaction. Each channel receives one interaction, but semantic content and human effort differ. This is an operational definition, not Shannon information. Numerical satisfaction bands also are design conventions, not validated human meanings of words such as "slightly".

### Why is Experiment 2 unfinished?

The protocol requires a real independent student pass, agreement and blinded adjudication before the full freeze and reserved inference. Those records are absent. Also, the 3 October delivery check found no Ollama executable and a refused local endpoint. Historical inference and cached replay do not resolve current availability. H1/H2 are not assessed, not failed or passed. The next step is to fulfil the real gate and restore the specified runtime, not replace either with AI or rule output.

### What if the hypothesis fails?

State that natural-language feedback did not demonstrate an expressiveness advantage under this protocol and identify the failed contrast. Beating A but not the rule parser would support richer explicit controls over this proxy while leaving added LLM value unsupported. Do not choose a new subset or threshold to manufacture a pass.

### What did AI do, and what did you personally do?

Use a disclosure consistent with the record: "AI agents assisted substantially with literature synthesis, implementation, drafting, training, inference, testing and analysis. I am responsible for the submission. My personal reading, checks and reruns are documented in my activity log." Name only tasks actually completed, with dates and evidence. Do not claim everything was manual or personally rerun unless true. Mastery is shown by reconstructing a result and explaining its limits.

### Does checkpoint replay reproduce every byte?

No. The October automated audit reproduced all 25,950 controlled top-ten lists and ranked-item counts, but 2,009 full-catalogue ranking hashes and all 5,190 request score hashes differed. No headline metric changed. The exact cause has not been isolated, so do not assert a particular hardware or numerical explanation. Preserved checkpoints, saved results, raw recomputation and fresh inference are distinct evidence. See `october-verification.md` and the verbatim numerical report. This was agent execution; call it your own replay only after actually performing and recording it.

## Personal verification exercises

These remain pending until you perform and log them. Preserve commands, input hashes, timestamps, outputs and your explanation. Use new output locations, never overwrite frozen evidence.

| Exercise | What to explain | Evidence to save |
| --- | --- | --- |
| Trace one reported E1 request from history to ranking | Why test labels cannot choose the request; how A differs from C | Your annotated example |
| Calculate metrics on an invented list | Rank 3 gives `1/log2(4) = 0.5` NDCG; three target items give TCP 0.3 | Hand calculation and function comparison |
| Recompute the boost decrease | `(0.0163659690 - 0.0301167894) / 0.0301167894`, about -45.66% | Calculation and source pointers |
| Explain the NI margin | Fractions versus percentages versus percentage points | Worked example using pooled A |
| Read request generation and mutation tests | What hashes prove and what they cannot prove | Notes on `feedctrl/evaluation.py` and `tests/test_evaluation.py` |
| Run clean-environment checks yourself | Execution differs from reading a receipt | Fresh logs and environment versions |
| Replay development caches | Replay is not new model inference | New output retaining the original run |
| Read the key papers | Each source's task, finding and limits | Personal reading notes |
| Rehearse the demo | Backend labels, reset, isolation and failure behaviour | Timing and issues log |

Do not add a reserved E2 dry run. The test opens once only after genuine human and freeze gates are satisfied.

## Reading map

| Primary source | Inspect | Do not infer |
| --- | --- | --- |
| [Mozilla, 2022](https://www.mozillafoundation.org/en/research/library/user-controls/report/) | Historical Dislike 12% and Not interested 11% reductions under its study | Current YouTube behaviour or our proxy performance |
| [Ramos et al., ACL 2024](https://aclanthology.org/2024.acl-long.753/) | Table 2 and Section 5.4: profile-edit responsiveness; RMSE 0.941 versus MF 0.925 on Amazon-MT | Accuracy improvement in this project |
| [Sanner et al., RecSys 2023](https://arxiv.org/abs/2307.14225) | Language preferences near cold-start | Superiority on this cohort |
| [Radlinski et al., SIGIR 2022](https://arxiv.org/abs/2205.09403) | Rationale for inspectable language profiles | Validation of our ranker |
| [Chen and Pu, 2012](https://link.springer.com/article/10.1007/s11257-011-9108-6) | Earlier critiquing approaches | Novelty of the basic feedback idea |
| [Zhang et al., 2026](https://arxiv.org/html/2605.29141v1) | Vision paper on context and alignment measures | Validation of our metric bands |
| [Woźniak et al., 2025](https://dl.acm.org/doi/10.1145/3701716.3717734) | Obtain the full paper and compare its profile task and baselines | That our interface is the first integrated control system |

## Questions for the supervisor

1. Is the revised scope acceptable, with E1 complete and E2 gated?
2. How should the proposal's "within 10%" wording be documented while preserving the original and post-hoc interpretations?
3. Is the supplied BCIT slide template the final one, and is the current IEEE format acceptable?
4. What annotation arrangement is acceptable given actual prior exposure? Any replacement protocol must be prospective and separately identified.
5. What AI disclosure and personal reproduction evidence does the course require?
6. Which extensions fit the remaining course time, and which belong in a separate publication study?

When uncertain, explain what the evidence supports and what needs checking. A precise uncertainty is more defensible than a confident guess.
