---
title: "COMP 9500 progress report"
subtitle: "LLM-Mediated Natural Language Controls for Short-Video Recommender Systems"
author: "Vibhor Malik, for Dr Borna Noureddin, BCIT"
date: "17 November 2026"
---

# Summary

This round did four things. It put the language controls into the original application on real KuaiRec data. It built and froze an evaluation set that an AI (Claude Opus 5.5) drafted and I reviewed row by row. It measured three frontier models and two local models (llama3.1:8b, qwen2.5-coder:7b-instruct) on that set against the reviewed reference. It recorded the demo video.

- **Code and evidence:** <https://github.com/vibhormalik95-hue/FP>, branch `main`, tag `comp9500-final-2026-11` (merged from `final/comp9500`).
- **Guide:** `docs/guide/PROFESSOR-GUIDE.md` / `.pdf`. The KuaiRec assets the app needs (processed data, checkpoint, captions) are not in the repository: `fetch-assets.cmd` (or `fetch-assets.sh`) downloads them from the GitHub Release `comp9500-kuairec-assets-v1` (CC BY-SA 4.0, `notices/KUAIREC-ASSETS-ATTRIBUTION.md`) and verifies every SHA-256. A fresh-clone test passed: fetch-assets, fresh install, `run-app`, Results page.
- **Results:** `docs/evidence/lab-eval/20261117-main/RESULTS.md`. Every table names the prediction commits (hosted `8dd978f`, local `9071f05`) and the scoring commit (`fbb3e59`); every code change after the freeze is listed in `docs/evidence/lab-eval/POST-FREEZE-AUDIT.md`.
- **Demo video:** `COMP9500-Feed-Control-Lab-demo.mp4` (sent separately).
- **Full audit:** `deliverables/2026-11-17-completion/PROJECT-COMPLETION-AUDIT.md`.

# What was done this round (16–17 November)

1. **One application on real KuaiRec.** Run it with `run-app.cmd`. It covers 865 users and 2,593 items, ranked by the trained SASRec seed-42 checkpoint, and has three views:
   - **Original study (A to E).**
   - **Language controls**, with four workflows: choose a category; a request in your own words; a new category from a description; new items with descriptions.
   - **Results.**

   Each language control works the same way. The model proposes and the server checks the proposal. The user reviews it, Apply changes exactly what was reviewed, and Undo restores the previous feed. The controls use KuaiRec's 266 named categories and its topic tags. Everything is English: the KuaiRec text is translated into English before processing (English text layer `data/kuairec_text_en-v1.json`, machine translation of KuaiRec, CC BY-SA 4.0), and the app, the models and the screen use only that layer. Providers: OpenAI-compatible, Ollama, Anthropic (never run with a live key), Claude CLI and mock.
2. **Tests.** `run-all-tests.cmd` runs the Python tests, the page tests, the browser flows in Chrome and every workflow through the API (the root-level `test_*.py` files and the `tools/hosted_validation*` tests are outside it). The final full run (mock, 2026-11-17T06:59Z, on the final code after commit d824e13; receipts in `FINAL2/receipts/final-tests/`) gave pytest 1,752 passed, 75 skipped and 1 failed (frozen by design: `test_guarded_current_contract`), page tests 126/126, browser 29/29 and workflows 14/14. A separate test checks that no example request is written into the code or the prompts.
3. **Evaluation set, AI-drafted and human-reviewed.** Claude (Opus 5.5) drafted 40 cases (20 English, 20 Chinese):
   - 20 nonliteral requests (NL);
   - 14 cases where nothing should be proposed (AB);
   - 6 new-category descriptions (NC), judged over a shared pool of 150 KuaiRec items.

   I reviewed all 1,211 rows one by one and corrected 24. The set was frozen (commit `391d462`) before any model prediction. Claude is both the drafter's family and a measured model (Claude Sonnet 5.5); this is a disclosed bias risk.
4. **Measurement.** gpt-5, gpt-5-mini and Claude Sonnet 5.5 (CLI) ran all 40 cases with zero call errors (commit `8dd978f`). llama3.1:8b and qwen2.5-coder:7b-instruct ran all 40 cases locally through Ollama (commit `9071f05`, which adds only a 2,048-token output cap for local models), with 13 and 10 call errors. gemma4:31b was probed but not run (too slow on this laptop). The frontier models are a declared departure from the proposal's local-only plan.
5. **Later fixes.** Budget (commit `04d21ed`): each call reserves an upper-bound cost before it runs, so parallel calls cannot overspend, and a failed call is charged its reservation; tests added. The manual control now accepts several labels in one preview.
6. **Independent reviews.** Two independent reviews (documents and code) were run on 17 November. The code findings were fixed (commit `1de3955`): the quotation check now needs at least two characters and a whole tag (the measured runs keep the earlier rule), and the downstream scoring now applies each model's exact controls with the app's policy. The downstream numbers below are this re-scoring of the same predictions.
7. **Demo video.** Take 12: 10:22, 1920x1080, Kokoro narration, user 14 with the news and incident categories hidden first, the API key pasted into the masked field (never shown), gpt-5 at minimal reasoning effort for speed (measured results use low effort), recorded before the English text layer; take 11 (9:23) kept as backup. Checks: no silence of 5 s or more at −45 dB; the transcript matches 97/97 script sentences (similarity 0.898); one frame every 30 s (`docs/evidence/2026-11-17-video-take12/`).
8. **Re-checks.** Experiment 1 was replayed from the checkpoints on Windows (rule arm). All reported metrics reproduce exactly (399/399 numeric values). The 33 proposal clauses were re-checked against the code, and several statements in the 4 November audit were corrected.

# Key measured numbers (frozen set, 17 November; measured on the original-text run (17 Nov); English-input re-run pending)

| Measure | Claude Sonnet 5.5 | gpt-5 | gpt-5-mini | llama3.1:8b | qwen2.5-coder:7b |
|:------------------|:--------|:--------|:--------|:--------|:--------|
| Nonliteral request → exact intended labels (of 20) | 17 | 17 | 16 | 0 | 0 |
| Correct abstention on ambiguous / unsupported (of 14) | 12 | 10 | 7 | 11* | 9* |
| New-category member F1 (150-item pool) | 0.875 | 0.918 | 0.936 | 0.179 | 0.469 |
| Target share in top 10, boost/only (none 0.006, reference 0.529) | 0.563 | 0.552 | 0.518 | 0.017 | 0.059 |
| Target share in top 10, hide/reduce (none 0.012, reference 0) | 0 | 0 | 0 | 0.011 | 0.012 |
| Median seconds per call | 6.6 | 12.5 | 11.7 | 126 | 109 |
| Cost of the 40 cases, USD | 5.86 (notional) | 2.39 | 0.47 | 0 | 0 |

\* The local models declined almost every request, so these abstentions do not show judgement (see below).

Source: `docs/evidence/lab-eval/20261117-main/RESULTS.md`. Predictions: hosted models at commit `8dd978f`, local models at `9071f05`; all tables scored at `fbb3e59`. Every code change after the freeze is listed in the post-freeze audit, `POST-FREEZE-AUDIT.md`, in `docs/evidence/lab-eval/`.

- **Local versus frontier.** On this laptop the two local 7–8B models proposed almost nothing. On the 20 nonliteral requests llama3.1:8b matched no exact profile: it declined 17 (16 as ambiguous, 1 as no match), failed 2 at the output cap and proposed once. qwen2.5-coder:7b matched none and declined all 20 (10 as no match, 10 as unsupported). Their abstention scores (11/14 and 9/14) therefore reflect declining everything, not judgement; only 5 and 3 of their statuses match the reference. On new categories qwen was precise but missed most members (precision 0.97, recall 0.33, F1 0.47); llama reached F1 0.18, with 4 of 6 cases failing at the output cap. The frontier models reached 16–17 of 20 exact and member F1 0.88–0.94. The local calls cost nothing but took about two minutes each (median 126 s and 109 s; 90th percentile 267 s and 159 s). gemma4:31b fit in memory (37 GB, 89% CPU / 11% GPU) but generated 0.90 tokens per second, too slow to measure: its first reply was unfinished after about 45 minutes, and the full set would take tens of hours.

- **Model controls move exposure about as far as the reviewed reference control.** They raise the target share from 0.6% to 52–56% of the top ten (reviewed control: 53%). The difference from the reviewed control is not significant for any frontier model (Wilcoxon, BH p 0.62–0.65, 16 cases); this is not evidence of equivalence. The local controls barely move the feed.
- **No frontier model is significantly better than another.** Paired McNemar BH p ≥ 0.55 on 33, 32 and 29 successes out of 40. Every frontier model beats both local models (11 and 9 successes; BH p ≤ 0.0024). On the 14 cases that should change nothing, Claude abstains on 12, gpt-5 on 10 and gpt-5-mini on 7 (descriptive, 14 cases; possible drafter-family bias). gpt-5-mini accepts 7 of the 14 requests it should refuse.
- **HR@1 non-inferiority.** It fails the relative 10% margin for every model except llama (which passes only because it applied almost no control) and passes the absolute 0.10 margin, which is trivial at this base rate. The recommender itself is weak (base HR@1 about 0.5%), so this test says little. It is also strongly concentrated on popular items: under the seed-42 ranker, item 8958 is in the top ten of all 865 users and item 1116 in 862. NDCG@10 falls with every control.
- **Parser bank re-run (re-use of the exposed 100 cases, not new evidence; original prompt, schema, validator and grounding rule).** llama3.1:8b 79/100 with 7 operational errors (the frozen record); qwen2.5-coder 74/100 (13 errors); gpt-5 and gpt-5-mini 60/100 strict. Both GPT models broke a stated format rule on reset/clarify replies; they reach 96 and 95 under a post-hoc lenient score (run 2). No model reaches the 85% target strictly.
- **New-domain check (software check, not evaluation data).** With gpt-5, 6/6 new requests (family-safe, travel, mood, fitness, vehicles, celebrity) were mapped to existing labels and two new items were classified to existing categories. For two new descriptions the define step now proposes a definition even when the sampled items do not fit; classification of 100 items selected none for either. The define step is not part of the measured evaluation.

# What remains

- A live test of the Anthropic API route (never run with a key; Claude was measured through the CLI only).
- A full gemma4:31b run on the frozen set; it needs a faster machine than this laptop.
- Extra polish of the app and the documents.
- (Done 17 Nov: full run on the final code, `runs/all-tests-final`: pytest 1,752 passed, 1 frozen-by-design failure; Node 126/126; browser 29/29; workflows 14/14.)
- The paper (8-page draft) and the BCIT deck contain the November results for all five models; I still have to review the paper and confirm its one marked sentence.
- Proposal items still open: per-item explanations and their cache (R09, R10); the ~200-word profile (R12); channel isolation (R19, by design); a meaningful HR@1 non-inferiority result (R24, weak backbone). The new-items workflow is demonstrated but not measured.

# Next steps

1. Test the Anthropic API route live; run gemma4:31b on a faster machine.
2. Choose a venue together and start the paper revision.

# Conference options (official pages read 16–17 November; deadlines 23:59 AoE)

| Venue | Deadline | Fit |
|:----------|:----------|:--------------------|
| ACM UMAP 2027, full/short papers (Chicago, 9–12 June 2027) | Abstract 22 Jan 2027; paper 29 Jan 2027 | Best fit: user control, editable user models, LLMs for personalization. Short: 4 + 2 pages |
| ACM SIGIR 2027, full papers (San Jose, 19–24 July 2027) | Abstract 14 Jan 2027; paper 21 Jan 2027 | Topic fit (LLM-based and conversational recommendation); harder target at 9 pages |
| ACM SIGIR 2027, demo papers | Abstract 4 Feb 2027; paper 11 Feb 2027 | Fallback: 4 pages; needs a video or a working interface |

RecSys 2027 has not announced a deadline; it is probably in April, so it is a later option.
