# COMP 9500 presentation notes

**Student:** Vibhor Malik  
**Supervisor:** Borna Noureddin  
**Paper:** LLM-Mediated Natural Language Controls for Short-Video Recommender Systems: An Offline Study of Controllability  
**Version:** Supervisor review draft, 4 October 2026, Vancouver time  
**Format:** 22 main slides and six backup slides, using the supplied BCIT Beamer template  
**Timing:** Proposed 23-minute talk followed by 10 to 15 minutes of questions. This is a rehearsal plan, not a measured delivery time.

These notes describe the evidence in the package. They do not certify that the student has personally performed any reading, test, annotation or rehearsal. Mark personal checks in the activity log after doing them. Do not read reserved Experiment 2 material as preparation while the independent annotation and freeze requirements remain unresolved.

## Timed talk

| Slide | Subject | Time | Cumulative |
| --- | --- | ---: | ---: |
| 1 | Title | 0:30 | 0:30 |
| 2 | Current research position | 1:00 | 1:30 |
| 3 | Research question | 1:00 | 2:30 |
| 4 | Related work | 1:15 | 3:45 |
| 5 | System stages | 1:00 | 4:45 |
| 6 | Data and boundaries | 1:15 | 6:00 |
| 7 | Conditions | 1:00 | 7:00 |
| 8 | Parser results | 1:15 | 8:15 |
| 9 | Category enforcement | 1:15 | 9:30 |
| 10 | Predictive quality | 1:15 | 10:45 |
| 11 | Backbone and non-inferiority | 1:15 | 12:00 |
| 12 | Experiment 1 conclusion | 1:00 | 13:00 |
| 13 | Experiment 2 hypotheses | 1:00 | 14:00 |
| 14 | Intent classes | 1:15 | 15:15 |
| 15 | Matched interactions | 1:00 | 16:15 |
| 16 | Reserved procedure | 1:00 | 17:15 |
| 17 | Development results | 1:00 | 18:15 |
| 18 | Analysis plan | 1:15 | 19:30 |
| 19 | Current blockers | 0:45 | 20:15 |
| 20 | Contribution | 1:00 | 21:15 |
| 21 | Completion plan | 1:00 | 22:15 |
| 22 | Supervisor discussion | 0:45 | 23:00 |

### 1. Title

The project studies natural-language control around a fixed short-video recommender. This is a progress presentation, with a finished first experiment and an incomplete follow-up. Say that distinction at the beginning. The full paper title appears above, while the slide title is shorter for readability.

### 2. Current research position

The central result is that deterministic category controls work under the specified policy. That does not establish that the LLM is responsible for the benefit. The rule parser gives the same feeds on the templated task, and boosting reduces agreement with the held-out historical target. Experiment 2 is designed to test a stronger claim about richer requests, but there are no reserved-test results to report. An incomplete test is neither a pass nor a failure.

Evidence: `results/llm/combined-summary.json`, `results/audit_revision/analysis-v1.json`, `results/experiment2/summary.json`.

### 3. Research question

A single item reaction does not explicitly tell us which of an item's attributes caused the reaction. A language request can specify a category, another category to reduce, a degree of change or an exception. The experiment asks whether this extra specification produces the intended ranking change under one interaction. It also compares the LLM with rules on the same wording. The comparison is against a deliberately simple item-feedback proxy, so it cannot settle whether language beats every learned feedback system. Whether people find the channel more natural needs a human study.

### 4. Related work

Mozilla's 2022 result motivates investigating control, but it describes a different platform and historical setting. It is not a measurement of the present app or today's YouTube. Ramos and colleagues show that profile edits can change target coverage without further fine-tuning. Their RMSE comparison does not support a blanket accuracy improvement: 0.941 is worse than 0.925 because lower RMSE is better. Sanner and colleagues examine near cold-start movie recommendation. Chen and Pu establish the earlier critiquing tradition. The project should therefore claim an inspectable study and careful evaluation, rather than inventing natural-language recommendation.

Primary sources:

- [Mozilla, Does this button work?](https://www.mozillafoundation.org/en/youtube/user-controls/)
- [Ramos et al., ACL 2024](https://aclanthology.org/2024.acl-long.753/)
- [Sanner et al., RecSys 2023](https://arxiv.org/abs/2307.14225)
- [Chen and Pu, 2012](https://link.springer.com/article/10.1007/s11257-011-9108-6)

### 5. System stages

The recommender gives scores. The translator turns a sentence into a small structured command. Validation checks whether the command uses supported operations and categories. The enforcer changes scores or removes matching items. These stages let us locate errors: correct translation followed by a wrong ranking is different from a wrong translation. Explanations display verified facts and do not change rankings. The LLM is not trained as the recommender in this system.

Evidence: `feedctrl/controls.py`, `feedctrl/model.py`, `feedctrl/explanations.py`, and the methodology in `paper/manuscript.tex`.

### 6. Data and information boundaries

The source is KuaiRec. Filtering produces 865 eligible users and 2,593 candidate items. A positive event is a watch ratio greater than two, which is a proxy rather than an explicit like. Global time cutoffs separate training, request history and evaluation. The nominal 70/15/15 proportions refer to source time boundaries, so retained positive-event counts need not have exactly those proportions. Requests use earlier history only. The first eligible held-out positive is the prediction target. The category identifiers are opaque labels, so the task does not demonstrate understanding of semantic video topics.

Evidence: `data/processed.json`, run manifests, `feedctrl/data.py`. Background: Gao et al., CIKM 2022, cited in `paper/references.bib`.

### 7. Conditions

A changes one historical exemplar item. B displays an explanation but must leave A's ranking unchanged. C uses free text. D uses a preference sentence as a profile. E combines these paths while deduplicating equivalent controls. Every user receives a boost and a mute assignment under three trained seeds. Those seeds assess some training variability but are not additional independent users. Identical C, D and E rankings show consistency for equivalent commands, not equal usability.

Evidence: the matched configurations table in the paper and `feedctrl/evaluation.py`.

### 8. Parser results

The 120 canonical inputs consist of 60 text commands and 60 profile statements. They parse correctly, but their wording patterns informed development. The broader synthetic set gives 79 exact matches out of 100, including only two out of ten adversarial cases. The latter ten are a subset of the hundred. The overall score clears the proposal's 70% floor and misses its 85% target. The rule parser scores 81 out of 100. Do not infer a meaningful rule-versus-LLM difference from two extra correct cases without the relevant paired analysis. Seven Llama cases are recorded as operational errors caused by validation rejection, not network failures.

Evidence: `results/parser_ollama_test/summary.json`, `results/parser_rule/summary.json`, the paper's canonical-input accounting.

### 9. Category enforcement

The requested category share increases from 11.6% under A to 79.2% under category controls. Muted-category share decreases from 6.1% to zero. Hard exclusion produces the zero by construction when the command is correct. The boost policy directly changes every matching item's score while A touches one item. That difference in granularity explains why a large exposure difference is not evidence of sophisticated language understanding. Correct parsing matters, but the rule and LLM outputs give identical feeds in this templated comparison.

Evidence: `results/llm/combined-summary.json`, per-seed `request_metrics.csv` files and `results/audit_revision/analysis-v1.json`.

### 10. Predictive quality

Boost NDCG@10 decreases from approximately 0.03012 to 0.01637, a 45.7% relative decline. The paired post-hoc mean difference is about negative 0.01375, with a user-bootstrap interval from negative 0.02086 to negative 0.00655. This interval is exploratory and lies outside the frozen primary testing family. It describes worse recovery of a historical next item. Since the historical future was recorded without our intervention, this is not direct evidence that a user would be less satisfied after requesting the new feed. It is still a material cost against the selected prediction target.

Evidence: `results/llm/combined-summary.json`, `results/audit_revision/analysis-v1.json`.

### 11. Backbone and non-inferiority

The uncontrolled backbone has zero, three and four top-one hits among 865 users across the three seeds. Recency popularity has 69, or about 8%. Recency pools the request-history window across users, whereas the model weights were fitted on the earlier training window and inference uses each user's own earlier sequence. Both precede test outcomes, but their actual use of information differs. This is a descriptive diagnostic, not a controlled demonstration of model-class superiority. The absolute ten percentage point non-inferiority margin is much larger than the roughly quarter-percent A baseline for the pooled estimand. A numerical pass therefore cannot establish useful quality preservation.

Evidence: `results/audit_revision/baselines.json`, `results/audit_revision/analysis-v1.json`. Use backup slide 25 for the two margin interpretations.

### 12. Experiment 1 conclusion

Read the five findings in order. Add that all ten archived explanation selections equal the deterministic template's selected facts, so no LLM explanation advantage appears in those examples. The result supports bounded enforcement and exposes limitations in parsing and predictive quality. It does not establish an LLM expressiveness advantage, more natural interaction, improved accuracy or useful quality preservation. Avoid adding a speculative positive claim after this conclusion.

Evidence: `results/audit_revision/baselines.json`, specifically `explanation_checks`, and the paper conclusion.

### 13. Experiment 2 hypotheses

H1 compares induced satisfaction with both A and the rule parser. Beating only A would leave open whether a simple deterministic translator is enough. H2 measures intended-direction movement per interaction, with exactly one interaction for each channel. It is an operational measure of how much ranking change the request carries, not Shannon information. H3 describes quality costs with paired intervals and has no pass threshold. These hypotheses are prespecified but unassessed on the reserved bank.

Evidence: `docs/experiment2-protocol.md`, sections on hypotheses and decision rules.

### 14. Intent classes

Compound requests require more X and less Y together. Graded requests map words such as "a bit" to a declared band. Floor requests require some X to remain. Conditional requests apply to items labelled with both X and Y, not a feed that separately contains some X and some Y. The bands are design conventions rather than validated human interpretations. Each primary success also requires positive movement in the intended direction and a full list. An unchanged ranking that already meets the band is not an induced success.

Evidence: protocol metric table. The wording on this slide illustrates the class definitions and does not reproduce the reserved corpus.

### 15. Matched interactions

Each channel gets one interaction. A changes one exemplar item while the language channels receive the complete utterance. That intentionally varies the amount that can be specified in the interaction. It does not claim equal user effort or equal semantic information. Requests are assigned deterministically from earlier history, with missing eligibility recorded. The recency comparator has the same permitted pre-test corpus, but its estimator pools recent behavior differently. Quality comparisons should state that difference explicitly.

Evidence: protocol sections on requests and comparators.

### 16. Reserved procedure

There are 48 development cases and 100 reserved cases, with all 31 category identifiers represented in each split. The developer uses development material only. The parser commitment already exists. Before reserved inference, the student must provide an independent pass, agreement must be calculated, and disagreements must be adjudicated without parser predictions. Prior exposure must be recorded and resolved honestly. The final freeze follows those steps. Parser accuracy must be reported before ranking results. AI cannot impersonate the independent student annotator.

Evidence: `results/experiment2/parser-freeze-v2.json`, the protocol and annotation rubric. Do not open reserved cases during this presentation preparation.

### 17. Development results

In development v1 the rule parser scores 48 out of 48 and Llama 24 out of 48, including ten operational errors. After prompt and wording development, both score 48 out of 48 in v2. These are useful engineering observations, but they cannot estimate held-out accuracy. The changes to wording and prompt mean the improvement is not an isolated causal estimate of a single modification. The reserved parser score remains unknown and the reserved ranking row count is zero.

Evidence: `results/experiment2/summary.json`, `development-v1/` and `development-v2/` summaries.

### 18. Analysis plan

Average the three seeds within each user/request. The user remains the sampling unit. H1 supplies ten contrasts: four intent classes and pooled, each against A and rules. H2 adds one pooled contrast, making eleven in the single BH family. The protocol uses Wilcoxon signed-rank and 5,000 user bootstrap resamples. Sparse differences, symmetry assumptions and dependence between tests remain limitations. Keep infeasible cases in the assigned denominator and separately report feasibility. Never fix an unfavorable result by changing thresholds or selecting requests after seeing quality outcomes.

Evidence: protocol analysis section. H1 requires both pooled differences to be positive with adjusted q below .05. H2 requires its positive pooled difference and q below .05. If either fails, state that natural-language feedback did not demonstrate an expressiveness advantage under this protocol and identify the failed contrast.

### 19. Current blockers

Experiment 1 is finished. Experiment 2 still requires the independent student annotation and a completed reserved evaluation. The 3 October runtime check found no Ollama executable and a refused local endpoint. The specified Llama runtime must be restored and verified before reserved execution. Full research execution on Windows and Colab remains unverified. Software checks and archived summaries provide useful evidence, while the reserved experiment remains pending.

Evidence: `results/experiment2/summary.json` and `results/experiment2/verification/supervisor-2026-10-03/ollama-availability.json` in the full evidence archive. The 3 October runtime check is separate from the archived September 29 Llama runs.

### 20. Contribution

The supported contribution is an inspectable separation of parsing, validation, enforcement and measurement. The tested templates show no observed ranking benefit from LLM parsing, and category boosting has an explicit quality cost. The follow-up protocol adds a falsifiable comparison against both the item proxy and rules. A stronger paper needs completed reserved evidence and a clear justification for its intent construct. Broader language, human evaluation or a stronger backbone would need a separately identified extension with its own prospective decisions. Publication suitability remains a question for supervisor review after examining the evidence.

### 21. Completion plan

The proposed 135 hours cover future student reading, verification, completion, discussion and revision across eleven calendar weeks, 5 October through 18 December. The readiness decision is due by 23 October. Reserved evaluation is planned for 26 October to 1 November if the protocol requirements are satisfied, followed by analysis on 2 to 8 November. Reproduction work occupies 9 to 15 November, cold review 16 to 22 November, and the complete paper draft is due by 27 November. Supervisor revisions, repository handoff and presentation practice follow, with final review and submission preparation during 14 to 18 December. The exact final deadline needs confirmation. The proposed check-in is Wednesday at 10:00 am Vancouver time, with the update by Tuesday at 10:00 am. Record decisions and actions after each actual meeting. If the annotation or runtime requirements remain unmet, retain an explicit blocked status.

Evidence: user-supplied meeting transcripts and course email. The dated weekly plan in the supervision pack supplies task and hour detail.

### 22. Discussion

Ask the supervisor to confirm the revised scope and approval record, the interpretation of the original margin, annotation independence in light of prior exposure, the final date and the repository access route. The attached BCIT presentation template has now been applied. The paper format still needs explicit confirmation if the supervisor wants a particular IEEE or ACM variant. End with the evidence boundary: the enforcement result is complete, the expressiveness test is incomplete.

## Backup slide use

- **23, metrics:** Explain why TCP and TCER use the same fraction but have different desired directions. Demonstrate NDCG with a hypothetical target at rank two: `1 / log2(3)`, approximately 0.631. This is arithmetic illustration, not a reported experiment row.
- **24, implementation:** Know what attention masking, the fixed context length and the negative-sampling policy do. Do not claim exact reproduction of the original SASRec paper.
- **25, non-inferiority:** Distinguish percentage points from relative percent. The pooled A baseline is 0.2505%. Ten percent of that is 0.02505 percentage points. The simultaneous lower bound is -0.07707 percentage points, so the relative reading does not pass.
- **26, intended movement:** Explain that rank discounts give early slots more weight. A compound request uses the weaker of its two directional changes. Conditional movement subtracts increases outside the requested intersection. The floor rule prevents total exclusion from receiving credit.
- **27, evidence and authorship:** Point to exact files, then separate what the software archive records from what the student has personally checked. Do not say "I ran every test" unless the student actually ran and logged them.
- **28, references:** Use the primary papers. The references support motivation and study design, not a transferred claim that this implementation improves accuracy.

## Rehearsal and demo checklist

1. Deliver one timed rehearsal and record the actual duration. Trim explanations rather than racing through slides.
2. Explain one boost, one mute and one parser failure without reading the notes.
3. Recompute 45.7% as `(0.030116789365495843 - 0.016365969047470008) / 0.030116789365495843 * 100`.
4. Explain why 51,900 metric rows do not mean 51,900 independent users or language examples.
5. If demonstrating the app, identify it as the Experiment 1 interface and state the selected parser backend. A rule demo is not a live Llama test.
6. Keep the PDF available locally and verify the projector rendering on the actual presentation machine. That platform check remains the student's future action.
7. After rehearsal, log questions that could not be answered and resolve them against source files before claiming personal verification.
