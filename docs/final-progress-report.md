# COMP 9500 Research Progress

Completed work and priorities for supervisor review

Student: Vibhor Malik    Supervisor: Dr Borna Noureddin

Prepared: 4 October 2026, Vancouver time

LLM-Mediated Natural Language Controls for Short-Video Recommender Systems: An Offline Study of Controllability

The project has a working research prototype, a completed first experiment and a prepared follow-up experiment. The clearest result so far is that category rules change the feed as intended, while the simple requests tested show no added ranking benefit from an LLM. The next priority is to test the richer-intent question in Experiment 2 and make the final paper fully traceable to evidence.

This update covers the current project records, reviewed as of 4 October 2026. Completed artifacts and recorded checks are reported separately from the verification and experimental work still planned.

## Work already in place

| Area | Completed artifact or recorded work | Remaining responsibility |
| --- | --- | --- |
| Research prototype | Recommendation model, rule and LLM parser interfaces, deterministic reranking, explanations and a working demonstration interface. | Personal walkthrough and reproducibility checks; retain documented limits. |
| Experiment 1 | Recorded evaluation on 865 users and 2,593 items; frozen results and explicit conclusions. | Explain the findings and limits; preserve all frozen evidence. |
| Experiment 2 preparation | Dated protocol, compound parser and ranker, staged runner, language bank, annotation rubric, dev caches and parser commitment. | Student annotation, runtime readiness and reserved evaluation. |
| Verification records | Numerical, claims, software, browser and release reviews with retained findings. | Resolve or document remaining reproduction issues. |

## What Experiment 1 establishes

The evaluation uses public KuaiRec data and synthetic requests with opaque category identifiers. A positive event means watch_ratio greater than 2; it is an engagement proxy, not an explicit like. The prediction target is the first eligible held-out positive item. There was no recruited user study. [1, 2]

Category enforcement works. Target-category proportion rises from 11.6% to 79.2%, and muted-category exposure falls from 6.1% to zero. The zero exposure follows from deterministic hard exclusion by construction.

Parsing succeeds on templates but is less reliable on varied language. Llama parses 120/120 templated inputs, 79/100 broader synthetic inputs and 2/10 adversarial cases. The 79% broader-set score clears the 70% floor but misses the 85% target. These finite synthetic sets do not establish general language reliability.

Explanations show no LLM advantage in the recorded sample. All 10/10 explanation cards, for one user, equal the template. The rule and LLM parsers also produce identical feeds for the templated ranking task.

Steering has a quality cost. Boost NDCG@10 falls by 45.7%, from about 0.03012 to 0.01637. The non-inferiority check is uninformative at this low baseline; it does not establish preservation of useful recommendation quality.

The backbone is weak. HR@1 ranges from 0.0% to 0.46% across the three seeds, compared with about 8.0% for recency popularity. Recency uses different recent aggregate information, so this is a diagnostic comparison, not an information-matched superiority test.

The study establishes bounded category control and its observed costs. It does not establish improved recommendation accuracy, a more natural user experience or an LLM expressiveness advantage. [2]

### Recorded verification and remaining limits

The recovery records include recomputation of 51,900 Experiment 1 metric rows. The October engineering review records 271 passing tests plus 44 passing subtests, 17 Chromium browser checks and a byte-identical frontend rebuild. These are recorded project checks, not a claim that I personally reran them today. [3]

The later numerical audit reproduced all 25,950 top-10 lists, but found 2,009 full-ranking hash differences and 5,190 request-score hash differences with an unresolved cause. That issue remains visible in the verification plan. Windows 11 and Google Colab execution are still unverified. Software checks alone do not validate the central research hypothesis. [4]

## Experiment 2 and the completion path

Experiment 2 is designed to compare richer instructions with one item-feedback interaction and an extended rule parser. It covers two-category commands, graded preferences, reduction with a nonzero floor, and conditional preferences. The committed bank contains 48 development cases and 100 reserved cases, with all 31 category identifiers reported in each split. [5]

Development v2 records 48/48 exact matches for both Llama and the rule parser. This is development fit, not a held-out result or LLM advantage. The earlier Llama result of 24/48, including ten operational errors, is retained. Both wording and prompt changed before v2, so the difference is not a controlled estimate of prompt improvement. [5]

The reserved evaluation has not run: H1 expressiveness and H2 intended movement per interaction are not assessed, and H3 quality-cost analysis has not run.

### What I propose to finish next

The attached plan allocates 135 future active student hours across the proposed 5 October to 18 December window. It covers source reading, personal verification, the gated experiment, analysis, paper revisions, repository handoff and presentation practice. A readiness decision is scheduled for 23 October, followed by reserved evaluation only if the protocol requirements are satisfied.

The intended contribution is a reproducible comparison that separates language interpretation, deterministic enforcement and predictive-quality cost. Experiment 2 may strengthen that contribution or provide a useful negative result. If H1 or H2 fails, the paper will say that natural-language feedback did not demonstrate an expressiveness advantage under this protocol and explain the failed comparison. Publication readiness is not yet established.

## Evidence references

[1] docs/evaluation-protocol.md and docs/academic-use.md.

[2] Frozen E1 records in results/llm/, results/rule/ and results/audit_revision/, indexed in the full research archive.

[3] results/experiment2/verification/recovery-20260929/ and docs/october-verification.md in the full research archive.

[4] Numerical review and unresolved hash differences indexed in docs/october-verification.md in the full research archive.

[5] docs/experiment2-protocol.md and the full archive: results/experiment2/summary.json, development-v1/ and development-v2/.
