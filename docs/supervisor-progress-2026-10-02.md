> Historical draft from 2 October. The current supervisor report is [final-progress-report.md](final-progress-report.md), updated to the revised 4 October Word document. Repository status and the current schedule should be read there and in [repository-handoff.md](repository-handoff.md).

# COMP 9500 progress report for the supervisor

**Project:** LLM-Mediated Natural Language Controls for Short-Video Recommender Systems: An Offline Study of Controllability  
**Student:** Vibhor Malik  
**Supervisor:** Dr Borna Noureddin  
**Prepared:** 2 October 2026, Vancouver time  
**Status:** Draft for student review before sharing

The project has a working research artifact and a clear result from Experiment 1. Category controls change the feed as intended, but the evidence does not show that an LLM is needed for the simple requests tested. The more important question, whether natural language can satisfy richer preferences better than one item reaction or a rule parser, is the focus of Experiment 2. That experiment is prepared but its reserved evaluation has not run.

## What Experiment 1 establishes

On 865 users and 2,593 candidate items, deterministic category enforcement raises the target-category proportion from **11.6% to 79.2%** and reduces muted-category exposure from **6.1% to zero**, with hard exclusion guaranteed by construction. Llama parses **120/120 templated requests**, but only **79/100 broader synthetic requests** and **2/10 adversarial requests**, clearing the 70% floor and missing the 85% target. All **10/10 explanation outputs equal the template**, so this sample shows no LLM explanation advantage. Steering has a quality cost: **NDCG@10 falls 45.7% on boosts**, and the non-inferiority check is uninformative at this baseline. The backbone's **HR@1 is 0.0 to 0.46%**, compared with **8.0% for recency popularity**, whose access to more recent aggregate information makes this a descriptive diagnostic. This study establishes bounded category control and its costs; it does not establish better recommendation accuracy, a more natural user experience or an LLM expressiveness advantage.

## What Experiment 2 still needs

The follow-up uses four intent classes: two-category requests, graded preferences, reduction with a nonzero floor, and conditional preferences. The language bank contains 48 development cases and 100 reserved cases, with all 31 category identifiers covered in each split. The recovered development v2 record gives both Llama and the rule parser 48/48 exact matches. This is development fit, not a held-out result or evidence of LLM superiority.

H1 will compare induced intent satisfaction against both the one-item proxy and the rule parser. H2 will compare intended-direction movement with exactly one interaction per channel. H3 will describe paired NDCG@10 and HR@1 changes with confidence intervals; it makes no non-inferiority claim. H1 and H2 are currently **not assessed**, and H3 has not run.

Two gates remain. The protocol requires a genuine independent student annotation pass, agreement reporting and blinded adjudication. Prior exposure must be checked before any independence statement is signed. The current environment also has no available Ollama runtime, so fresh Llama inference is stopped. AI-generated labels cannot count as the student pass, and rule output cannot substitute for the required model. The existing parser commitment must be preserved.

## Plan for the remaining term

The new plan allocates **135 future active student hours from 5 October to 18 December**, subject to confirmation of the final deadline. It covers source reading, personal verification, the gated experiment, analysis, paper revisions, repository handoff and presentation practice. It does not claim that those hours have already been worked. The official BCIT presentation template and logo are now available.

The proposed routine follows our individual meeting discussion: Wednesday at 10:00 am, an update by Tuesday at 10:00 am, and minutes after each meeting. The folder includes a separate update and minutes template for each remaining week, plus an actual-hours log. Repository access still needs to be provided after the private repository is created and checked.

## Questions for our next meeting

1. Can we confirm the revised scope, COMP 9500 approval route and exact December deadline?
2. What personal reading, reproduction evidence and AI disclosure should accompany the final submission?
3. Is the student still eligible for the required independent annotation pass after reviewing prior exposure, and what is the appropriate prospective alternative if not?
4. How should the original NI wording be interpreted? The absolute reading is uninformative here, while the relative reading is unsupported.
5. Is the supplied IEEE paper format suitable, alongside the BCIT presentation template?

AI agents have contributed substantially to implementation, analysis and drafting. Personal reading, checks and explanations will be recorded as they occur. The current contribution is a reproducible separation of language parsing, deterministic enforcement and recommendation quality. Publication readiness remains a question for a complete evaluation and related-work review, rather than a result already established.

**Evidence:** `results/experiment2/summary.json`, `results/experiment2/parser-freeze-v2.json`, `results/experiment2/verification/supervisor-2026-10-03/ollama-availability.json`, `docs/experiment2-protocol.md`, `docs/final-progress-report.md` and the frozen Experiment 1 records identified there. This report does not certify a fresh student rerun.
