# Requirements and evidence

> **Current page, 17 November 2026** (branch `final/comp9500`, merged to `main` and tagged `comp9500-final-2026-11`). It maps each of the supervisor's requests, each of the student's commitments and each of the 33 proposal clauses to code and evidence.
>
> **History.** Earlier versions of this page are kept in git. The 14 November version (last committed in `6093806`, present on `main` at `8d70bbc`) documented the language controls on invented 8–10-item scenarios, relay runs with an AI operator, and the checks of 13–14 November. View it with `git show 8d70bbc:docs/requirements-and-evidence.md`. Its dated facts are still true as history. This page replaces it as the statement of current status.

Full clause-by-clause audit: [`deliverables/2026-11-17-completion/PROJECT-COMPLETION-AUDIT.md`](../deliverables/2026-11-17-completion/PROJECT-COMPLETION-AUDIT.md).
Guide to run the application: [`docs/guide/PROFESSOR-GUIDE.md`](guide/PROFESSOR-GUIDE.md).

## Facts that apply to every row

- **One application on real KuaiRec.** `run-app.cmd` (Windows) or `python scripts/run_app.py` starts it. It covers 865 users and 2,593 items, ranked by the trained SASRec seed-42 checkpoint. It has three views: Original study (A–E), Language controls (manual, your own words, new category, new items), and Results. The page opens in English (machine translation of the Chinese KuaiRec text, labelled); one switch shows the original text.
- **Reference set: AI-drafted, human-reviewed.** The 40-case set was drafted by Claude (Opus 5.5). Vibhor Malik reviewed it row by row: 1,211 rows, 24 corrections. It was frozen in commit `391d462` before any prediction ([set README](evidence/lab-eval-set-20261117/README.md), [FROZEN.json](evidence/lab-eval-set-20261117/FROZEN.json)). Claude is both the drafter's family and a measured model (Claude Sonnet 5.5 through the CLI). This is a disclosed bias risk.
- **Frontier models are a declared departure** from the proposal's local-only plan (P024). gpt-5 and gpt-5-mini ran through the OpenAI API and Claude Sonnet 5.5 through the Claude Code CLI.
- **Local model llama3.1:8b: evaluation on the frozen set is incomplete.** It completed 21 of 40 cases before it was paused; it is being resumed on the measurement commit `9071f05`, and its results will be added in next week's update. <!-- LLAMA-PENDING -->
- Measured results: [RESULTS.md](evidence/lab-eval/20261117-main/RESULTS.md), [summary.json](evidence/lab-eval/20261117-main/summary.json), [per-case.csv](evidence/lab-eval/20261117-main/per-case.csv). The downstream tables were re-scored on 17 November with each model's exact controls and the application's own policy (strength and mixed actions exactly; all "only" labels of a case are treated as one group, because the saved predictions do not record groups — this can differ from the app for NL06, NL08 and NL15); the predictions were not re-run. Parser re-run (re-use of the exposed bank, with the original prompt, schema, validator and grounding rule; grounding applied by re-scoring the saved predictions): [summary.json](evidence/lab-eval/20261117-b-parser-rerun/summary.json).
- Demo video `COMP9500-Feed-Control-Lab-demo.mp4` (sent separately, not in the repository): 9:23, 1920x1080, gpt-5, English display mode. Checks: [video README and check.json](evidence/2026-11-17-video/README.md).

## The supervisor's requests (meeting transcript supplied by the student on 4 November; email of 10 November, not in the evidence folder)

Paraphrases with transcript times, not quotations.

| # | Request | Code | Evidence | Status |
| --- | --- | --- | --- | --- |
| T1 | Manual categories as the reference, with measured performance that shows the LLM working (08:22) | `feedctrl/lab_workflows.py` (`manual_preview`), `feedctrl/lab.py` (`apply_controls`), `feedctrl/kuairec_catalog.py`, `web/src/LabView.jsx`; scoring `scripts/lab_eval.py`, `feedctrl/lab_metrics.py` | Reviewed reference controls vs model controls: NL exact gpt-5 17/20, Claude 17/20, gpt-5-mini 16/20. Downstream TCP@10: none 0.0063, reference 0.5290, models 0.5178–0.5625. Model vs reference not significant, Wilcoxon BH p 0.6543 ([RESULTS.md](evidence/lab-eval/20261117-main/RESULTS.md)) | done, executed; llama pending <!-- LLAMA-PENDING --> |
| T2 | NLP creates new categories from a description, classifies, feeds the filter (08:38) | `lab_workflows.define_category`, `classify_category`, `assess_quotes`; Apply as only/more/less/hide | NC member F1 on 6 descriptions × 150 KuaiRec items: Claude 0.875, gpt-5 0.918, gpt-5-mini 0.936 (with the reviewed definition). Definition step shown in the guide §5.5, not scored; since 17 Nov it proposes a definition even when the sampled items do not fit (scope up to 200) | done for membership; llama pending <!-- LLAMA-PENDING --> |
| T3 | NLP maps nonliteral requests to existing categories and tags (07:49, 08:38) | `lab_workflows.interpret_request` over 467 terms (266 categories, 201 tags) | NL 20 nonliteral requests (10 EN, 10 ZH): exact 17/17/16. AB 14 should-not-propose cases: correct abstention Claude 12, gpt-5 10, gpt-5-mini 7 | done, executed; llama pending <!-- LLAMA-PENDING --> |
| T4 | Concise report of done / remaining (09:18) | — | Progress report 17 Nov ([source](../deliverables/2026-11-17-completion/COMP9500-Progress-Report-2026-11-17.md)); [completion audit](../deliverables/2026-11-17-completion/PROJECT-COMPLETION-AUDIT.md) | done (draft, not sent) |
| T5 | 2–3 conferences, deadlines around January (11:48–12:05) | — | UMAP 2027 (abstract 22 Jan, paper 29 Jan 2027); SIGIR 2027 full (14 / 21 Jan 2027); SIGIR 2027 demo (4 / 11 Feb 2027), all AoE, official pages read 16–17 Nov | done (not sent) |
| T6 | Record a demo video (email of 10 Nov) | `tools/recording/record_demo.py`, `demo_script.py`, `check_take.py` | `COMP9500-Feed-Control-Lab-demo.mp4` (take 11): 9:23, 1920x1080, Kokoro af_heart narration, gpt-5 via the OpenAI API (key from the environment, never shown), English display mode. No silence ≥5 s at −45 dB; transcript 96/96 script sentences (similarity 0.936); one frame every 30 s ([evidence](evidence/2026-11-17-video/README.md)) | done (sent separately) |

## The student's own commitments

| # | Commitment | Code | Evidence | Status |
| --- | --- | --- | --- | --- |
| S1 | New items with descriptions (02:08) | `lab_workflows.add_items_preview`; tab "New items" | Guide §5.6 with screenshots; live smoke checks with gpt-5-mini and the Claude CLI on two example items; new-domain check with gpt-5 (`tools/generalization_examples.json`; local `runs/generalization-gpt5*/summary.md`): 6/6 new requests mapped to existing labels, 2 new items classified to existing categories. A new item starts at the user's median score | partial: demonstrated, not measured |
| S2 | Local vs frontier model comparison (02:35) | `feedctrl/llm_providers.py` (OpenAI-compatible, Ollama, Anthropic, Claude CLI, mock) | Three frontier models measured; llama3.1:8b 21 of 40 cases, being resumed, results next week <!-- LLAMA-PENDING -->; qwen2.5-coder:7b deferred (parser re-run 74/100); gemma4:31b not attempted (memory held by the llama run; 19 GB model, 8 GB GPU; the 21k-token prompt needs a 32k context); Anthropic API never run live (no key) | partial |

## The 33 proposal clauses

Status words: done / partial / not done; departure where the method differs. Details and "change since 4 Nov" are in the [audit](../deliverables/2026-11-17-completion/PROJECT-COMPLETION-AUDIT.md#5-the-33-proposal-clauses).

| ID | Subject (P###) | Code | Evidence | Status |
| --- | --- | --- | --- | --- |
| R01 | Offline controllability study (P018, P025) | `feedctrl/evaluation.py`, `scripts/lab_eval.py` | E1 frozen results; 17 Nov results | done |
| R02 | Prior work incl. "Shu 2024" (P023, P031) | `paper/references-2026-11-14.bib` | No Shu entry | partial |
| R03 | Common short-video testbed (P023, P117) | `scripts/run_app.py`, `feedctrl/lab.py` | A–E and language controls on the same KuaiRec/SASRec ranking | done |
| R04 | React + FastAPI (P033, P118a) | `web/src/`, `feedctrl/api.py`, `feedctrl/lab_routes.py` | Browser 29/29, node 126/126 (mock, 17 Nov 01:14Z, before the final head) | done |
| R05 | SASRec (Kang & McAuley) (P024, P033) | `feedctrl/model.py` | Independently written variant | done, departure (minor) |
| R06 | Trained on KuaiRec (P024, P033) | `feedctrl/data.py`, `scripts/train.py`, `feedctrl/kuairec_catalog.py` | 865 users, 2,593 items; 3 checkpoints | done |
| R07 | Local Llama 3.1 8B via Ollama (P024, P033) | `feedctrl/controls.py`, `feedctrl/llm_providers.py` | E1, frozen parser 79/100, re-run 79/100; frozen-set run pending <!-- LLAMA-PENDING --> | partial |
| R08 | No paid APIs / external transfer (P024) | `feedctrl/llm_providers.py` | E1 local; frontier arm used OpenAI and Claude CLI (cost ledger total USD 26.83, private receipts) | done for E1; departure (declared) |
| R09 | Per-item explanations (P024, P033) | `feedctrl/explanations.py` | Fixed-fact selection; E1 B = A | partial |
| R10 | Precomputed explanation cache (P025, P118d) | `scripts/generate_explanations.py`, `scripts/prepare_demo_explanations.py` | 10 records verified; 25 only by receipt | partial |
| R11 | Free-text filter/boost/re-rank (P024, P033) | `feedctrl/lab_workflows.py`, `feedctrl/lab.py` | NL / AB / NC results above | done (frontier); llama pending <!-- LLAMA-PENDING --> |
| R12 | ~200-word editable profile from history (P024, P033) | `feedctrl/api.py` | ~40-word category-count profile | partial |
| R13 | (E) all combined (P025, P037) | `feedctrl/evaluation.py`, `feedctrl/controls.py` | E1 | done |
| R14 | History initializes recommender (P025) | `feedctrl/evaluation.py`, `feedctrl/api.py` | E1 and app | done |
| R15 | Dominant-shift request script (P025) | `feedctrl/evaluation.py` | Hash-selected from history | departure |
| R16 | Request independent of answer key (P025) | `feedctrl/evaluation.py` | Premise invalid; test data never read | departure |
| R17 | Thumbs baseline (P025, P037) | `feedctrl/evaluation.py` | Simulated proxy | departure |
| R18 | Five conditions (P025, P037, P118a) | `feedctrl/evaluation.py`, `web/src/main.jsx`, `tests/browser/lab_flows.cjs` | E1 3 seeds; A–E browser flow on KuaiRec | done |
| R19 | Each channel isolable (P025, P117, P119) | — | B = A; C = D = E | not done |
| R20 | TCP and TCER (P025, P037) | `feedctrl/evaluation.py`, `scripts/lab_eval.py` | E1 11.6% → 79.2%; new TCP 0.006 → 0.52–0.56 (reference 0.529), TCER 0.012 → 0 | done; llama pending <!-- LLAMA-PENDING --> |
| R21 | 100-case parser set and rubric (P035, P118c) | `feedctrl/parser_benchmark.py`, `scripts/parser_rerun.py` | Frozen + [re-run](evidence/lab-eval/20261117-b-parser-rerun/summary.json) (operational errors: llama 7, qwen 13, gpt-5-mini 36, gpt-5 35) | done |
| R22 | Systematic from KuaiRec tags (P035) | — | Frozen bank 4 of 31 IDs; new set AI-drafted on KuaiRec names | partial / departure |
| R23 | ≥85% parser accuracy (P025, P035, P116) | `feedctrl/parser_benchmark.py` | 79/100; re-run: llama 79, qwen 74, gpt-5 60, gpt-5-mini 60 strict (gpt-5 96, gpt-5-mini 95 post-hoc format-lenient, run 2) | done, target missed |
| R24 | HR@1 non-inferiority 10% (P025, P037, P116) | `scripts/lab_eval.py` | Relative 10% fails, absolute 0.10 passes (all models) | not done; llama pending <!-- LLAMA-PENDING --> |
| R25 | Wilcoxon + BH (P025, P037, P116) | `feedctrl/lab_metrics.py`, `feedctrl/evaluation.py` | E1; 17 Nov fidelity and paired tests | done |
| R26 | Directional hypothesis (P116) | `scripts/analyze.py` | E1 p_BH ≤ 1e-65; new descriptive | done |
| R27 | LLM only parses at evaluation (P025) | `feedctrl/evaluation.py` | E1 | done |
| R28 | Reusable harness (P118d, P119) | `scripts/evaluate.py`, `scripts/lab_eval.py`, `scripts/verify_frozen_e1.py` | Windows replay of the rule arm: 399/399 metric leaves identical | partial |
| R29 | 6–8 page paper (P039, P118e) | `paper/research-paper-2026-11-17.tex` | 8-page draft with the 17 Nov results and departures; llama rows pending; one "[student to confirm]" marker | partial |
| R30 | BCIT presentation (P039, P118e) | `presentation-bcit/presentation-2026-11-17.tex` | 43 pages with the 17 Nov results, the 4 Nov negative finding and the video; llama rows pending | partial |
| R31 | Source shared (P118) | — | Public repo; merged to `main` and tagged `comp9500-final-2026-11` | done (supervisor receipt is a real event) |
| R32 | Six-month Gantt (P042–P112) | — | Replaced by the course plan | departure |
| R33 | Artifact, comparison, protocol (P119) | all of the above | (1) and (3) exist; (2) partial | partial; llama pending <!-- LLAMA-PENDING --> |

## Checks

- `run-all-tests.cmd` (mock, 2026-11-17T01:14Z): pytest 1,745 passed, 76 skipped, 1 failed. The failure is frozen by design: the 11 November profile's guard blocks ctypes on Windows. Node 126/126, browser 29/29, workflows 13/13. The root-level `test_*.py` files and the `tools/hosted_validation*` tests are outside the runner. That check ran before commit `9c9d393`. The final full run (mock, 2026-11-17T06:59Z, on the final code after commit d824e13; receipts in `FINAL2/receipts/final-tests/`) gave pytest 1,752 passed, 75 skipped and 1 failed (frozen by design: `test_guarded_current_contract`), page tests 126/126, browser 29/29 and workflows 14/14.
- `tests/test_no_hardcoded_examples.py` checks that no example request or label is written into the application code, including the prompts (only docstrings and comments are exempt, since commit `1de3955`).
- Code-review fixes of 17 November (commit `1de3955`): quotation check needs at least two characters and a whole tag (the measured runs used the earlier rule of the measurement commit); downstream scoring applies the exact controls; Reset keeps the version increasing; model name and effort validated for the Claude CLI; explicit provider base URLs; anti-framing headers. Not changed: the budget is checked before each call without a reservation, and a failed call is booked at zero cost.
- Experiment 1 replay on Windows from the checkpoints: all 399 numeric leaves identical to the frozen summary. Full-ranking hashes differ below the top ten.

## What remains

1. llama3.1:8b results on the frozen set: 21 of 40 cases done; the run is being resumed and will be added in next week's update. <!-- LLAMA-PENDING -->
2. qwen2.5-coder:7b evaluation deferred; gemma4:31b not attempted (retry when no other model holds the memory); Anthropic API route needs a key.
3. Full test run on the final code: done 17 Nov (pytest 1,752 passed, 1 frozen by design; Node 126/126; browser 29/29; workflows 14/14).
4. Paper and deck: fill the llama rows; the student reviews the text and removes the "[student to confirm]" marker.
5. Not measured: recommendation benefit to real users; real intent.
