---
title: "COMP 9500 progress report"
subtitle: "LLM-Mediated Natural Language Controls for Short-Video Recommender Systems"
author: "Vibhor Malik, for Dr Borna Noureddin, BCIT"
date: "17 November 2026"
---

# Summary

This round did four things. It put the language controls into the original application on real KuaiRec data. It built and froze an evaluation set that an AI (Claude Opus 5.5) drafted and I reviewed row by row. It measured three frontier models on that set against the reviewed reference. It recorded the demo video. The local model (llama3.1:8b) completed 21 of 40 cases before its run was paused; the run is being resumed and its results will follow in next week's update. <!-- LLAMA-PENDING -->

- **Code and evidence:** <https://github.com/vibhormalik95-hue/FP>, branch `main`, tag `comp9500-final-2026-11` (merged from `final/comp9500`).
- **Guide:** `docs/guide/PROFESSOR-GUIDE.md` / `.pdf`. The app needs the private archive (processed data, checkpoint, captions), which is not in the repository.
- **Results:** `docs/evidence/lab-eval/20261117-main/RESULTS.md`.
- **Demo video:** `COMP9500-Feed-Control-Lab-demo.mp4` (sent separately).
- **Full audit:** `deliverables/2026-11-17-completion/PROJECT-COMPLETION-AUDIT.md`.

# What was done this round (16–17 November)

1. **One application on real KuaiRec.** Run it with `run-app.cmd`. It covers 865 users and 2,593 items, ranked by the trained SASRec seed-42 checkpoint, and has three views:
   - **Original study (A to E).**
   - **Language controls**, with four workflows: choose a category; a request in your own words; a new category from a description; new items with descriptions.
   - **Results.**

   Each language control works the same way. The model proposes and the server checks the proposal. The user reviews it, Apply changes exactly what was reviewed, and Undo restores the previous feed. The controls use KuaiRec's 266 named categories and its topic tags. The page opens in English (machine translation of the Chinese KuaiRec text, labelled); one switch shows the original text. Providers: OpenAI-compatible, Ollama, Anthropic (never run with a live key), Claude CLI and mock.
2. **Tests.** `run-all-tests.cmd` runs the Python tests, the page tests, the browser flows in Chrome and every workflow through the API (the root-level `test_*.py` files and the `tools/hosted_validation*` tests are outside it). The final full run (mock, 2026-11-17T06:59Z, on the final code after commit d824e13; receipts in `FINAL2/receipts/final-tests/`) gave pytest 1,752 passed, 75 skipped and 1 failed (frozen by design: `test_guarded_current_contract`), page tests 126/126, browser 29/29 and workflows 14/14. A separate test checks that no example request is written into the code or the prompts.
3. **Evaluation set, AI-drafted and human-reviewed.** Claude (Opus 5.5) drafted 40 cases (20 English, 20 Chinese):
   - 20 nonliteral requests (NL);
   - 14 cases where nothing should be proposed (AB);
   - 6 new-category descriptions (NC), judged over a shared pool of 150 KuaiRec items.

   I reviewed all 1,211 rows one by one and corrected 24. The set was frozen (commit `391d462`) before any model prediction. Claude is both the drafter's family and a measured model (Claude Sonnet 5.5); this is a disclosed bias risk.
4. **Measurement.** gpt-5, gpt-5-mini and Claude Sonnet 5.5 (CLI) ran all 40 cases with zero call errors. llama3.1:8b: 21 of 40 cases, being resumed on the measurement commit `9071f05`. <!-- LLAMA-PENDING --> The frontier models are a declared departure from the proposal's local-only plan.
5. **Independent reviews.** Two independent reviews (documents and code) were run on 17 November. The code findings were fixed (commit `1de3955`): the quotation check now needs at least two characters and a whole tag (the measured runs keep the earlier rule), and the downstream scoring now applies each model's exact controls with the app's policy. The downstream numbers below are this re-scoring of the same predictions.
6. **Demo video.** 9:23, 1920x1080, Kokoro narration, gpt-5 through the OpenAI API (key from the environment, never shown), English display mode. Checks: no silence of 5 s or more at −45 dB; the transcript matches 96/96 script sentences (similarity 0.936); one frame every 30 s (`docs/evidence/2026-11-17-video/`).
7. **Re-checks.** Experiment 1 was replayed from the checkpoints on Windows (rule arm). All reported metrics reproduce exactly (399/399 numeric values). The 33 proposal clauses were re-checked against the code, and several statements in the 4 November audit were corrected.

# Key measured numbers (frozen set, 17 November)

| Measure | Claude Sonnet 5.5 | gpt-5 | gpt-5-mini | llama3.1:8b |
|:------------------|:----------|:----------|:----------|:--------|
| Nonliteral request → exact intended labels (of 20) | 17 | 17 | 16 | pending <!-- LLAMA-PENDING --> |
| Correct abstention on ambiguous / unsupported (of 14) | 12 | 10 | 7 | pending <!-- LLAMA-PENDING --> |
| New-category member F1 (150-item pool) | 0.875 | 0.918 | 0.936 | pending <!-- LLAMA-PENDING --> |
| Target share in top 10, boost/only (none 0.006, reference 0.529) | 0.563 | 0.552 | 0.518 | pending <!-- LLAMA-PENDING --> |
| Target share in top 10, hide/reduce (none 0.012, reference 0) | 0 | 0 | 0 | pending <!-- LLAMA-PENDING --> |
| Cost of the 40 cases, USD | 5.86 (notional) | 2.39 | 0.47 | 0 <!-- LLAMA-PENDING --> |

Source: `docs/evidence/lab-eval/20261117-main/RESULTS.md`.

- **Model controls move exposure about as far as the reviewed reference control.** They raise the target share from 0.6% to 52–56% of the top ten (reviewed control: 53%). The difference from the reviewed control is not significant for any model (Wilcoxon, BH p 0.6543, 16 cases); this is not evidence of equivalence.
- **No model is significantly better than another.** Paired McNemar BH p ≥ 0.76 on 33, 32 and 29 successes out of 40. On the 14 cases that should change nothing, Claude abstains on 12, gpt-5 on 10 and gpt-5-mini on 7 (descriptive, 14 cases; possible drafter-family bias). gpt-5-mini accepts 7 of the 14 requests it should refuse.
- **HR@1 non-inferiority.** It fails the relative 10% margin for every model and passes the absolute 0.10 margin, which is trivial at this base rate. The recommender itself is weak (base HR@1 about 0.5%), so this test says little. NDCG@10 falls with every control.
- **Parser bank re-run (re-use of the exposed 100 cases, not new evidence; original prompt, schema, validator and grounding rule).** llama3.1:8b 79/100 with 7 operational errors (the frozen record); qwen2.5-coder 74/100 (13 errors); gpt-5 and gpt-5-mini 60/100 strict. Both GPT models broke a stated format rule on reset/clarify replies; they reach 96 and 95 under a post-hoc lenient score (run 2). No model reaches the 85% target strictly.
- **New-domain check (software check, not evaluation data).** With gpt-5, 6/6 new requests (family-safe, travel, mood, fitness, vehicles, celebrity) were mapped to existing labels and two new items were classified to existing categories. For two new descriptions the define step now proposes a definition even when the sampled items do not fit; classification of 100 items selected none for either. The define step is not part of the measured evaluation.

# What remains

- llama3.1:8b results on the frozen set: 21 of 40 cases done; they will be added in next week's update. <!-- LLAMA-PENDING --> qwen2.5-coder:7b is deferred. gemma4:31b was not attempted: the memory was held by the llama run (19 GB model, 8 GB GPU, and the 21k-token prompt needs a 32k context). The Anthropic API route has never run live (no key); Claude was measured through the CLI only.
- (Done 17 Nov: full run on the final code, `runs/all-tests-final`: pytest 1,752 passed, 1 frozen-by-design failure; Node 126/126; browser 29/29; workflows 14/14.)
- The paper (8-page draft) and the BCIT deck contain the November results; the llama rows are pending, and I still have to confirm one sentence of the paper.
- Proposal items still open: per-item explanations and their cache (R09, R10); the ~200-word profile (R12); channel isolation (R19, by design); a meaningful HR@1 non-inferiority result (R24, weak backbone). The new-items workflow is demonstrated but not measured.

# Next steps

1. Add the llama results to the Results page and to the report; then run qwen. <!-- LLAMA-PENDING -->
2. Share the private archive so that the app can run on your machine.
3. Choose a venue together and start the paper revision.

# Conference options (official pages read 16–17 November; deadlines 23:59 AoE)

| Venue | Deadline | Fit |
|:----------|:----------|:--------------------|
| ACM UMAP 2027, full/short papers (Chicago, 9–12 June 2027) | Abstract 22 Jan 2027; paper 29 Jan 2027 | Best fit: user control, editable user models, LLMs for personalization. Short: 4 + 2 pages |
| ACM SIGIR 2027, full papers (San Jose, 19–24 July 2027) | Abstract 14 Jan 2027; paper 21 Jan 2027 | Topic fit (LLM-based and conversational recommendation); harder target at 9 pages |
| ACM SIGIR 2027, demo papers | Abstract 4 Feb 2027; paper 11 Feb 2027 | Fallback: 4 pages; needs a video or a working interface |

RecSys 2027 has not announced a deadline; it is probably in April, so it is a later option.
