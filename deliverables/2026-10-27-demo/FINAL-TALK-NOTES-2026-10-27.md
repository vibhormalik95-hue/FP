# Full talk notes for the existing BCIT deck

Use [the current 30-page BCIT review deck](../2026-10-19/COMP9500-Presentation-2026-10-19.pdf). Pages 1 to 24 form a target 22-minute talk; pages 25 to 30 are backup. These notes are preparation, not a student rehearsal record. The shorter professor-meeting walkthrough is in [professor-meeting script](PROFESSOR-DEMO-SCRIPT.md).

| Slide | Clock | Speaker cue |
|---|---|---|
| 1 Title | 0:00-0:35 | Introduce an offline study of language control and ranking. The interface shows metadata, not videos or human satisfaction. |
| 2 E2 result | 0:35-1:30 | Lead with 76/100 validated Llama commands against model-generated references versus 11/100 rules. State 23 rejections, one accepted mismatch, zero conditional successes and lower NDCG. |
| 3 Question | 1:30-2:15 | Ask whether one utterance can express a richer change than one item reaction. Keep translation separate from deterministic enforcement. Naturalness to people was not tested. |
| 4 Prior work | 2:15-3:00 | Use Mozilla, profiles and critiquing as motivation in different settings, not directly comparable baselines. |
| 5 Architecture | 3:00-3:50 | Name the frozen scorer, parser, shared enforcer and factual display. A hard mute proves enforcement after a valid command, not LLM understanding. |
| 6 Data | 3:50-4:40 | State 865 filtered users, 2,593 items and 31 opaque category IDs. Watch ratio above two is an engagement proxy; the next-item target is not satisfaction. |
| 7 A-E | 4:40-5:35 | A changes one item, B adds display explanations, C uses text, D uses an editable profile, E combines channels. The E2 compound and conditional parser is not live in this UI. |
| 8 E1 parser | 5:35-6:30 | Templated 120/120, broader Llama 79/100 versus rules 81/100, adversarial 2/10. The broader result misses the 85% target despite exceeding the 70% floor. |
| 9 E1 control | 6:30-7:20 | TCP@10 is target-category items divided by ten: 11.6% to 79.2%. TCER@10 is muted-category share: 6.1% to zero. The hard filter supplies zero exposure. |
| 10 Quality cost | 7:20-8:10 | Boost NDCG@10 fell from 0.03012 to 0.01637, a 45.7% relative drop. The interval is post-hoc and outside the primary test family. Do not infer dissatisfaction. |
| 11 Weak backbone | 8:10-9:00 | SASRec seed HR@1 ranges 0.000%-0.462%; recency popularity is 7.977% in a descriptive comparison with different history use. The absolute 10-point non-inferiority margin is too broad to establish useful preservation. |
| 12 E1 conclusion | 9:00-9:35 | Summarize bounded enforcement, weak parser generalization and quality cost. E1 does not establish an incremental LLM ranking gain. If showing the app here, cap it at two minutes and read its real data, model and parser badges aloud. |
| 13 Fresh E2 question | 9:35-10:20 | Introduce the distinct AI-reference revision, comparing Llama, rules and one-item feedback on richer synthetic requests. |
| 14 Intent classes | 10:20-11:15 | Explain compound, graded, floor and conditional constraints. Valid parsing alone is insufficient: the feed must be full and move in the intended direction. Conditional requires joint item labels. |
| 15 Interaction budget | 11:15-12:00 | Each channel gets one interaction, but semantic content and user effort are not equalized. A is a proxy, not every commercial feedback method. |
| 16 Prospective design | 12:00-12:45 | The AI-reference procedure was fixed before its 100 requests. Two passes used separate contexts within the same model family, measuring consistency rather than human truth. |
| 17 Fresh requests | 12:45-13:30 | There are 25 requests per class. Screening against exposed wording does not prove semantic or pretraining novelty. No human adjudication of model references occurred. |
| 18 Development | 13:30-14:15 | Keep the exposed practice result separate: Llama 73/100, rules 18/100, 24 validation failures and lower NDCG than item feedback. It is not an unseen test. |
| 19 Analysis | 14:15-15:15 | The analysis unit is 865 users, not 41,520 independent rows. Average three seeds within user. State 5,000 paired user bootstraps and joint BH correction across 11 tests. |
| 20 Fresh results | 15:15-16:30 | State 76/100 versus 11/100, induced success 20.145% versus item feedback 3.815%, NDCG@10 0.02580 versus 0.03184, and zero conditional successes. Saved diagnostics count 987 structurally infeasible request-seed cases, 2,170 baseline-satisfied and 5,586 without directional opportunity; these are not additional independent subjects. |
| 21 Contribution | 16:30-17:15 | Claim a bounded control gain under this model-reference benchmark. Failed outputs stay in the denominator. Do not generalize to human agency or all models. |
| 22 Interpretation | 17:15-18:10 | Pooled control gain coexists with conditional failure and lower historical next-item quality. The weak ranker limits usefulness claims. |
| 23 Limits | 18:10-18:55 | Reiterate 100 language cases, 865 users and shared model-family references. Full E1 Windows/Colab replay and earlier full-score hash reconciliation remain open; 288/288 proves byte preservation only. |
| 24 Student check | 18:55-20:00 | The 20 October worksheet is one reported student pass, 99/100 versus AI initial labels under later rubric encoding. It is not two-human agreement. A separate exploratory parser-only check on exposed wording scored Llama 73/100 and rules 18/100, without ranking. The original human-reference route remains gated. |
| Close | 20:00-22:00 | Summarize the fixed-setting gain, zero conditional successes and lower NDCG. Invite questions. Use extra time for a brief A/B/C app example only if the talk slot permits it. |

## Backup slides and 10-15 minutes of questions

Pages 25-30 contain definitions, settings, non-inferiority, direction, records and references. Practise the following aloud with a timer; no student rehearsal is recorded here.

1. **What is TCP@10?** Target-category items divided by ten, not the proportion of feeds containing any target item. TCER@10 uses the same denominator for muted-category exposure.
2. **Why is E1 category gain not an LLM gain?** The enforcer is shared, and canonical rule and Llama feeds match. E2 separately tests translation with model references.
3. **Does H2 prove quality preservation?** No. H2 concerns intended control movement. NDCG falls, and the old absolute non-inferiority margin dwarfs baseline HR@1; relative sensitivity fails.
4. **What happened to parser failures?** They remain failures, with no silent rule fallback. Full-list and movement gates apply. The three feasibility counts are diagnostics that may overlap; use saved definitions before adding or comparing them.
5. **Where is human validation?** It is absent from the AI-reference study. The later worksheet is one student pass compared with AI labels. The original human-reference reserved study lacks final adjudication and ranking analysis.
6. **Is it reproducible?** A 27 October isolated archive check verified 1,613 manifest files and opened the saved-data, saved-model app. The complete 278-test Python suite passed in an isolated Windows copy. Earlier full-score hash differences and clean Colab replay remain unresolved. Do not call archive verification a fresh scientific rerun.

Finish by asking the supervisor to confirm accepted scope, disposition of the original human-reference route, paper feedback timing and course deadline. Record only answers actually given.
