# COMP 9500 Research Project

**Progress report for the supervisor**

**Project:** LLM-Mediated Natural Language Controls for Short-Video Recommender Systems: An Offline Study of Controllability

**Student:** Vibhor Malik | **Supervisor:** Borna Noureddin | **Prepared:** 3 October 2026 UTC

The project has a working research prototype, a completed first experiment and a prepared follow-up experiment. The main finding is straightforward: explicit category rules can control the feed, but the first experiment does not show that an LLM improves on a rule parser. Experiment 2 is intended to test that missing contribution. Its reserved results are still pending, so the project is ready for a substantive supervisor review, not a claim that the central thesis has been proved.

## What the study is asking

A reaction to one video does not explicitly state which attribute a user wants changed. A sentence can specify several attributes, degrees and exceptions. This project asks whether that richer channel produces more of the requested change than one item-feedback interaction, and whether an LLM provides a benefit beyond a simpler rule parser. It also measures the cost to historical recommendation quality. The offline design can test these operational questions; it cannot establish that people find language more natural or easier to use.

The evaluation uses a filtered public KuaiRec cohort of 865 users and 2,593 candidate items. A positive event has watch_ratio greater than 2, and the predictive target is the first eligible held-out positive item. Requests use opaque category identifiers. They are synthetic instructions, not statements collected from participants.

## Experiment 1: what is established

Deterministic category enforcement works: target-category proportion rises from 11.6% to 79.2%, while muted-category exposure falls from 6.1% to zero, with hard exclusion enforced by construction. Llama parses 120/120 templated requests, but only 79/100 broader synthetic requests and 2/10 adversarial cases, above the 70% floor and below the 85% target. All 10/10 recorded explanations equal the template. Steering costs quality: boost NDCG@10 falls by 45.7%, from approximately 0.03012 to 0.01637, and the non-inferiority check is uninformative at this baseline. The uncontrolled backbone reaches HR@1 of 0.0 to 0.46% across seeds, versus about 8.0% for recency popularity. These findings establish bounded mechanical control and its limitations; they do not establish an LLM expressiveness advantage, human naturalness or improved recommendation accuracy.

Each user receives one historical-category boost and one mute request. Five conditions share the same recommender: A applies feedback to one historical item; B adds display-only explanations; C uses a free-text request; D uses an explicit profile preference; E combines the text and profile controls with deduplication. The LLM and rule parser produce identical rankings for the templated requests. A and B also rank identically. There is therefore no measured ranking benefit from either LLM translation or display-only explanations in this setting.

The exposure hypothesis meets its recorded directional tests, while the parser misses the 85% target. The absolute quality margin passes only because it is larger than the very small baseline and permits complete baseline loss. The relative interpretation is unsupported. The supervisor still needs to resolve the original margin wording. Recency popularity uses pooled recent information that differs from the frozen backbone's training access, so its much stronger result is a diagnostic comparison rather than an information-matched model comparison.

## Experiment 2: what exists and what has not run

The follow-up has a dated protocol, separate compound parser and ranker, staged runner, development caches, a language bank, an annotation rubric and a parser commitment. The bank has 48 development cases and 100 reserved cases, covering compound, graded, reduction with a nonzero floor and conditional intents. Each split covers all 31 category identifiers. The existing v2 parser commitment is dated 29 September 2026 at 05:32 UTC and must remain unchanged.

Development v2 records 48/48 exact matches for both the rule parser and Llama, including 12/12 in each class. The earlier development run is retained: Llama scored 24/48 with ten operational errors, while the rule parser scored 48/48. Wording and prompt both changed before v2, so this is not a controlled estimate of prompt improvement. Neither run measures held-out performance.

H1 asks whether the LLM produces higher induced intent satisfaction than both the one-item proxy and the rule parser. H2 asks whether one language interaction produces more intended-direction rank movement than one thumb. H3 describes paired NDCG@10 and HR@1 changes, with confidence intervals and stated information access, against A and recency popularity. H1 and H2 are not assessed. H3 has not run. The reserved ranking file has zero rows, and inter-annotator agreement is unavailable. Pending outcomes must not be described as passes or failures.

Two requirements prevent completion today. First, the protocol requires a genuine independent student annotation pass, an honest declaration of prior exposure, agreement measurement and blinded adjudication. An AI-generated second pass would not meet that requirement. Second, the runtime check at 00:40 UTC on 3 October found no Ollama executable and a refused localhost connection. Fresh Llama inference is stopped; historical caches cannot be presented as a new model run. Restore the recorded Llama 3.1 8B runtime before execution.

Once the annotation and runtime gates are satisfied, verify the existing commitment, complete the full freeze and open the reserved evaluation once. Report parser accuracy before ranking outcomes, retain failures and use the prespecified user-level analysis. If either H1 or H2 fails, the conclusion must say that natural-language feedback did not demonstrate an expressiveness advantage under this protocol and explain the failed comparison.

## Verification, authorship and contribution

The September 29 recovery reports record recomputation of 51,900 Experiment 1 metric rows, 271 passing tests with 44 passing subtests, 17 browser checks and 22 release checks. They also record a byte-identical frontend rebuild and development-cache replay. These are historical verification records, not claims that the same checks were newly executed on 3 October. Current review results belong in separately dated reports and logs. Replaying cached output, executing a model and inspecting code are different forms of evidence.

AI agents performed substantial implementation, experimental execution, analysis and drafting. This report does not attribute those actions to the student's manual work. The student must demonstrate understanding through source notes, code walkthroughs, independent checks and an actual activity log. Windows 11 and Colab execution remain unverified. The supplied proposal copy is unsigned; the course email and meeting transcript establish expectations, not approval of the revised research scope.

The defensible current contribution is a reproducible offline evaluation that separates a deterministic control effect from language interpretation and documents the quality cost. A publication case would need the completed Experiment 2 comparison and a clear account of how the evaluation differs from prior work. A negative result can support a careful failure analysis; it cannot support a superiority claim. A human study and any stronger-backbone extension would require their own prospective design and applicable approvals. The separate publication roadmap sets out those options without promising acceptance.

## Plan for the remaining term

The proposed schedule allocates 135 future student hours across 11 weeks from 5 October to 18 December. This is a completion and verification plan for the remaining term, not a replacement claim that a new 15-week course has started, and not a record of hours already worked. The exact December deadline needs confirmation. The weekly plan identifies concrete evidence to bring to each discussion and an alternative task if Experiment 2 remains blocked.

The individual meeting arrangement is Wednesday at 10:00 am Vancouver time, approximately 30 minutes, subject to the supervisor's invitation. The progress update is due Tuesday by 10:00 am, at least 24 hours beforehand. Minutes follow each meeting and record progress, obstacles, decisions and actions. The first proposed update is 6 October and the first proposed check-in is 7 October; these are planning dates, not records of meetings already held.

The official BCIT slide template and logo have now been supplied. The revised presentation uses that template; the earlier PowerPoint is retained as a superseded historical draft. A private repository handoff guide is prepared, but no repository destination or invitation has been created. The next supervisor discussion should settle scope approval, AI disclosure, the annotation exposure procedure, the original NI margin reading, the final deadline and repository access.

The immediate goal is to complete the committed study honestly and make every claim traceable to evidence. The package supports that work now. Student verification, the human annotation requirement, real meetings and the final presentation still require participation over the remaining term.
