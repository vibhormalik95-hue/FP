# Proposed scope revision for supervisor decision

Student: Vibhor Malik. Supervisor: Borna Noureddin. Intended course: COMP 9500.

Updated: 4 October 2026, Vancouver time.

The supplied COMP 9080 proposal is an **unsigned draft**. Neither research path is ticked, all three approval signature blocks are blank, and the office Approved field is unmarked. The copy therefore provides no evidence of approval. This package does not establish whether a separate approval exists. Ask the supervisor to confirm COMP 9500, select the appropriate research path and complete the applicable approval process before treating this revised scope as approved. This document records changes from the draft text; it is not an amendment to an evidenced approved scope.

Sources: `sources/COMP9080-Proposal-Unsigned.docx` (Research Path, Objectives, Expected Outcomes, Approval Signatures) and `sources/course-email-transcript.md` (student-supplied transcript of the 21 September 2026 course email), retained in the full evidence archive. The transcript states course requirements; it does not approve this student's methodology. The native email is not included. The separately supplied BCIT presentation template has been applied to the current deck and is documented in `presentation-bcit/README.md`.

Original proposed title retained pending decision: **LLM-Mediated Natural Language Controls for Short-Video Recommender Systems: An Offline Study of Controllability**.

## Implemented study

The project evaluates translation of synthetic natural-language preferences into controls over a short-video recommendation feed. It supplies an auditable offline benchmark using public KuaiRec interactions, an independently implemented SASRec variant, actual local Llama 3.1 8B inference, a deterministic parser comparator, and a React/FastAPI demonstration. Its contribution is a reproducible applied study of parsing, policy enforcement and quality trade-offs.

Global training, request-history and final-test windows are separate. Synthetic boost and mute requests use historical category support without final-test outcomes. Candidates are items observed positively before the training cutoff. Official category IDs remain opaque; the language benchmark does not assess understanding of named video topics.

Five configurations compare simulated item feedback (A), the same feedback with display-only explanations (B), free-text category controls (C), an explicit editable profile preference (D), and combined controls (E). B preserves A's ranking. Equivalent C/D/E commands share one policy and yield identical rankings in the recorded experiment. Rule and LLM canonical-request results are also identical. These are not five cells of a design that identifies every channel's independent contribution.

Primary outcomes are TCP@10 for boost requests and TCER@10 for mutes, with fill rate. Paired user-level analysis averages the three fixed training seeds and applies Wilcoxon tests, joint BH adjustment and bootstrap intervals. The direction/significance criterion in the draft primary hypothesis is met by C/D/E. However, hard mute guarantees zero target exposure when the category is correct, and category-wide +0.25 boosting is structurally advantaged over a one-item adjustment. Passing this exposure criterion under correctly parsed canonical commands does not demonstrate an LLM benefit or a useful recommender. Statistical significance is still conditional on the observed cohort and baseline exposure; it is not a universal theorem about every possible dataset.

## Material differences from the draft proposal

| Draft proposal text | Implemented scope and reason |
|---|---|
| Requests derived from held-out category shifts but called independent | Requests use earlier history only; hiding held-out item IDs would not remove outcome-category leakage. |
| Explanations as a separately effective ranking channel | B is A plus display text, evaluated as ranking invariance; human responses are not measured. |
| Five conditions make each channel contribution isolable | Five configuration comparison; the design cannot identify all independent effects or interactions. |
| Thumbs-up/down baseline | Synthetic historical item-feedback proxy; KuaiRec has no required per-interaction thumbs signal. |
| Existing open-source SASRec implementation | Independently written PyTorch SASRec variant; no exact reproduction of the original implementation is claimed. |
| Approximately 200-word profile initialized from history and editable at any time | The app supports editable history-initialized text; primary offline D tests one explicit preference, not a rich human-edited 200-word profile. |
| Test utterances systematically generated from category tags | A single agent authored and labelled 100 synthetic test cases and 24 development cases under a fixed rubric. There is no independently adjudicated systematic generation procedure. The two sets include a punctuation-only near duplicate. |
| Top-1 hit rate non-inferior within 10% | The draft is ambiguous. The original execution chose absolute 0.10; an analysis-only supplement also reports 10% of observed A baseline. Absolute is a non-informative exploratory numerical pass; relative is not supported. |
| Six-month schedule | The course is 15 weeks and approximately 135 hours. The current remaining-work plan allocates 135 future hours over 5 October to 18 December 2026, pending supervisor acceptance of that schedule and exact deadline. |
| 6–8-page paper | Course-email transcript permits approximately 6–10 pages; a paper within 6–8 pages also satisfies both stated ranges. |
| Each prior system studies only one isolated mechanism | Remove the overbroad novelty claim in light of integrated prior systems. |

## Proposal thresholds and results

The 85% target is explicitly stated in Objective 3 and Expected Outcomes, so it is a proposal-specified target. Expected Outcomes also says parser accuracy below 70% means the control channels are degraded. Llama scores **79/100**: it misses 85% and clears the 70% point-estimate floor. Its descriptive 95% Wilson interval is approximately 70.02%–85.83%. Clearing that aggregate floor does not remove its ambiguity/adversarial failures or establish unrestricted-language reliability.

For non-inferiority, both interpretations now remain visible. The matched A baseline averaged over users, boost/mute requests and seeds is 0.00250481696 (0.25048%). Ten percent of that baseline is 0.000250481696. The simultaneous lower bound for C/D/E minus A is approximately −0.0007707129: above −0.10, but below −0.000250481696. The absolute calculation passes numerically; relative non-inferiority is not supported under the same rule. Neither interpretation was specified unambiguously in the unsigned proposal. A later supervisor decision must not be presented as prospective approval of a margin after outcomes were inspected.

## Decisions requested

Use `supervisor-decision-packet.md` to confirm research-path and approval status, accept or revise each scope difference, decide whether the narrow offline study is sufficient, agree how to report the ambiguous margin, and confirm the supplied official slide template, final deadline and AI-assistance rules. Preserve the frozen experiment and failed parser target. Any model/prompt improvement belongs in a versioned follow-up using newly reserved evaluation data or explicitly labelled development analysis.
