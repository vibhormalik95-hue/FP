# Timed professor-facing demo

Use 12 to 15 minutes, then discussion. Read the actual status badges aloud. This script prepares a demonstration; it is not a record that the student rehearsed or delivered it.

| Time | Show and say |
|---|---|
| 0:00 to 1:00 | Open the [paper](../2026-10-19/README-2026-10-19.md). "The project separates base ranking, translation of a request and deterministic enforcement. We test control together with historical next-item quality." |
| 1:00 to 2:15 | Open the app and report its actual dataset, scorer and parser modes. "These are opaque category IDs and item metadata, not video assets." If the status is fixture or diagnostic, say so. |
| 2:15 to 4:30 | Choose user 14, compare A and B. "A is one-item feedback. B adds explanations, so rank should stay identical. The model scores are held fixed across conditions." Confirm the visible order before stating equality. |
| 4:30 to 6:30 | In C with the rule backend, submit `Show me more category_1`. Show the parsed boost and the changed list. "This manual click is an example, not a benchmark estimate." |
| 6:30 to 8:30 | Submit `Mute category_28`. Show the parsed mute and excluded category. Open D and save `Show me more category_1. Mute category_28.` as an editable profile. "The profile is explicit stated preference; the initial history summary is an observation, not a preference." Open E briefly to show the combined channels, then reset user 14 and confirm the original top item returns. |
| 8:30 to 10:00 | Open [E1 protocol](../../docs/evaluation-protocol.md). "Frozen E1 raised boost target-category proportion in the ten-item lists from 11.6% to 79.2%; mute exposure fell from 6.1% to zero by hard filtering. Broader parser scores were Llama 79/100 and rules 81/100; Llama missed the old 85% target. Boosting reduced historical next-item NDCG@10 by about 45.7%. This is a control-quality tradeoff, not demonstrated human satisfaction." |
| 10:00 to 12:15 | Open [fresh E2 results](../../docs/ai-reference-e2-results-2026-10-14.md). "On 100 synthetic requests with model-generated references, Llama matched 76 commands and rules 11. Mean induced control success was 20.145% against 3.815% for the item-feedback proxy; NDCG@10 was lower, 0.02580 versus 0.03184. H1_AI and H2_AI passed under this revision's tests, but conditional requests had zero successes. Only 100 unique language cases were used; 865 users were the ranking analysis units across three averaged seeds." |
| 12:15 to 13:30 | Open the [current plan audit](PLAN-ACCEPTANCE-AUDIT-2026-10-27.md). "The revised AI-reference E2 completed its parser and ranking evaluation. On 20 October, the student's completed worksheet matched 99/100 initial AI labels, and a separate parser-only check used exposed practice wording. The archived human-reference route did not run its reserved evaluation; it is not a prerequisite of the completed revision." |
| 13:30 to 15:00 | Summarize the completed revised study. Ask for paper feedback timing, the course deadline and the expected submission package. Record only answers actually given. |

## Defence answers

**Where is the LLM value?** E1 canonical feeds did not show an LLM advantage over rules. Fresh E2 shows an advantage on the specified synthetic AI-reference bank, alongside many validation failures and zero conditional successes. It does not prove value in live user experience.

**Why did quality fall?** Category enforcement changes the objective and can move the historical next item down. The base model's hit rate is weak; the original absolute 10-percentage-point non-inferiority margin is much larger than its approximately 0.25% baseline HR@1 and does not establish useful preservation. The post-hoc relative sensitivity does not pass.

**What does a parser failure do?** It remains in the denominator and is surfaced. The app does not silently replace a failed Ollama call with a successful rule call; previous control state is preserved.

**What did AI do?** Agents assisted substantially with research artifacts, execution, analysis and writing; the fresh E2 references came from separate AI contexts sharing a model family. Attribute any personal student reading, verification and hours only to dated records. Saved receipts are not today's fresh inference.

**What if the app fails?** Use the existing paper, slides, result summaries and audit receipts. State whether a screenshot or result is historical. Do not turn a fixture view into a real-model claim.
