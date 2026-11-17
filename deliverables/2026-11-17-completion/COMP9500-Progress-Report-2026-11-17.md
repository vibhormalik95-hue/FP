---
title: "COMP 9500 progress report"
subtitle: "LLM-Mediated Natural Language Controls for Short-Video Recommender Systems"
author: "Vibhor Malik, for Dr Borna Noureddin, BCIT"
date: "17 November 2026"
---

# Summary

This round did three things. It put the language controls into the original application on real KuaiRec data. It built and froze a human-reviewed evaluation set. It measured three frontier models on that set against the reviewed reference. The local model (llama3.1:8b) is still running and its results are pending. <!-- LLAMA-PENDING -->

- **Code and evidence:** <https://github.com/vibhormalik95-hue/FP>, branch `final/comp9500`. It will be merged to `main` and tagged `comp9500-final-2026-11`.
- **Guide:** `docs/guide/PROFESSOR-GUIDE.md` / `.pdf`.
- **Results:** `docs/evidence/lab-eval/20261117-main/RESULTS.md`.
- **Full audit:** `deliverables/2026-11-17-completion/PROJECT-COMPLETION-AUDIT.md`.

# What was done this round (16–17 November)

1. **One application on real KuaiRec.** Run it with `run-app.cmd`. It covers 865 users and 2,593 items, ranked by the trained SASRec seed-42 checkpoint, and has three views:
   - **Original study (A to E).**
   - **Language controls**, with four workflows: choose a category; a request in your own words; a new category from a description; new items with descriptions.
   - **Results.**

   Each language control works the same way. The model proposes and the server checks the proposal. The user reviews it, Apply changes exactly what was reviewed, and Undo restores the previous feed. The controls use KuaiRec's 266 named categories and its topic tags, in Chinese with a machine-translated English gloss. Providers: OpenAI-compatible, Ollama, Anthropic, Claude CLI and mock.
2. **Tests.** `run-all-tests.cmd` runs pytest, the page tests, the browser flows in Chrome and every workflow through the API. A mock run on 17 Nov (01:14 UTC) gave pytest 1,745 passed and 1 failed. The failure is frozen by design: an 11 Nov guard blocks a Windows library. Page tests passed 126/126, browser 29/29 and workflows 13/13. A separate test checks that no example request is written into the code.
3. **Evaluation set, AI-drafted and human-reviewed.** Claude (Opus 5.5) drafted 40 cases (20 English, 20 Chinese):
   - 20 nonliteral requests (NL);
   - 14 cases where nothing should be proposed (AB);
   - 6 new-category descriptions (NC), judged over a shared pool of 150 KuaiRec items.

   I reviewed all 1,211 rows one by one and corrected 24. The set was frozen (commit `391d462`) before any model prediction. Claude is both the drafter's family and a measured model (Claude Sonnet 5.5); this is a disclosed bias risk.
4. **Measurement.** gpt-5, gpt-5-mini and Claude Sonnet 5.5 (CLI) ran all 40 cases with zero call errors. llama3.1:8b is running. <!-- LLAMA-PENDING --> The frontier models are a declared departure from the proposal's local-only plan.
5. **Re-checks.** Experiment 1 was replayed from the checkpoints on Windows. All reported metrics reproduce exactly (399/399 numeric values). The 33 proposal clauses were re-checked against the code, and several statements in the 4 November audit were corrected.

# Key measured numbers (frozen set, 17 November)

| Measure | Claude Sonnet 5.5 | gpt-5 | gpt-5-mini | llama3.1:8b |
|:------------------|:----------|:----------|:----------|:--------|
| Nonliteral request → exact intended labels (of 20) | 17 | 17 | 16 | pending <!-- LLAMA-PENDING --> |
| Correct abstention on ambiguous / unsupported (of 14) | 12 | 10 | 7 | pending <!-- LLAMA-PENDING --> |
| New-category member F1 (150-item pool) | 0.875 | 0.918 | 0.936 | pending <!-- LLAMA-PENDING --> |
| Target share in top 10, boost (none 0.006, reference 0.445) | 0.358 | 0.381 | 0.328 | pending <!-- LLAMA-PENDING --> |
| Target share in top 10, hide/reduce (none 0.012, reference 0) | 0 | 0 | 0 | pending <!-- LLAMA-PENDING --> |
| Cost of the 40 cases, USD | 5.86 (notional) | 2.39 | 0.47 | 0 <!-- LLAMA-PENDING --> |

- **The LLM works, and the manual reference is still better.** Model controls raise the target share from 0.6% to 33–38% of the top ten (reference: 44%). The gap to the reference is significant for every model (Wilcoxon, BH p ≤ 0.0054).
- **No model is significantly better than another.** Paired McNemar BH p ≥ 0.76 on 33, 32 and 29 successes out of 40. Claude abstains best. gpt-5-mini accepts 7 of the 14 requests it should refuse.
- **HR@1 non-inferiority.** It fails the relative 10% margin for every model and passes the absolute 0.10 margin, which is trivial at this base rate. The recommender itself is weak (base HR@1 about 0.5%), so this test says little.
- **Parser bank re-run (re-use of the exposed 100 cases, not new evidence).** llama3.1:8b 79/100 (same as frozen); qwen2.5-coder 74/100; gpt-5 and gpt-5-mini 60/100 strict. Both GPT models broke a stated format rule on reset/clarify replies; they reach 96 and 95 under a post-hoc lenient score. No model reaches the 85% target strictly.

# What remains

- llama3.1:8b results on the frozen set (this week). <!-- LLAMA-PENDING --> qwen2.5-coder:7b is deferred to next week. gemma4:31b does not fit in this laptop's memory at the needed context. The Anthropic API route has not run live (no key); Claude was measured through the CLI only.
- The demo video `COMP9500-Feed-Control-Lab-demo.mp4`. The recorder is built; the final recording is still to be made.
- A full test run on the final head; push, merge to `main` and tag.
- The paper (8-page draft) and the BCIT deck need the November results and departures.
- Proposal items still open: per-item explanations and their cache (R09, R10); the ~200-word profile (R12); channel isolation (R19, by design); a meaningful HR@1 non-inferiority result (R24, weak backbone). The new-items workflow is demonstrated but not measured.

# Next steps

1. Add the llama results to the Results page and to the report; then run qwen. <!-- LLAMA-PENDING -->
2. Send the demo video and the repository tag.
3. Choose a venue together and start the paper revision.

# Conference options (official pages read 16–17 November; deadlines 23:59 AoE)

| Venue | Deadline | Fit |
|:----------|:----------|:--------------------|
| ACM UMAP 2027, full/short papers (Chicago, 9–12 June 2027) | Abstract 22 Jan 2027; paper 29 Jan 2027 | Best fit: user control, editable user models, LLMs for personalization. Short: 4 + 2 pages |
| ACM SIGIR 2027, full papers (San Jose, 19–24 July 2027) | Abstract 14 Jan 2027; paper 21 Jan 2027 | Topic fit (LLM-based and conversational recommendation); harder target at 9 pages |
| ACM SIGIR 2027, demo papers | Abstract 4 Feb 2027; paper 11 Feb 2027 | Fallback: 4 pages; needs a video or a working interface |

RecSys 2027 has not announced a deadline; it is probably in April, so it is a later option.
