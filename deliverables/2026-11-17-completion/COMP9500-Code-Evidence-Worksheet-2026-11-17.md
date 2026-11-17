---
title: "COMP 9500 code and evidence worksheet"
subtitle: "Every supervisor request, student commitment and proposal clause, mapped to code and evidence"
author: "Vibhor Malik"
date: "17 November 2026 (branch final/comp9500, merged to main and tagged comp9500-final-2026-11)"
---

Paths are relative to the repository root (<https://github.com/vibhormalik95-hue/FP>). **Status**: done / partial / not done; "dep." means a departure from the proposal. The reference set was AI-drafted (Claude Opus 5.5) and human-reviewed row by row by Vibhor Malik. Claude is also a measured model (Sonnet 5.5, CLI). Frontier models are a declared departure from the local-only plan (P024). Local models llama3.1:8b and qwen2.5-coder:7b-instruct ran all 40 cases (predictions at commit `9071f05`; hosted at `8dd978f`; all scored at `d9dd6cc`; post-freeze changes in `docs/evidence/lab-eval/POST-FREEZE-AUDIT.md`). Downstream values apply each model's exact controls with the app's policy (re-scored 17 Nov). RES = `docs/evidence/lab-eval/20261117-main/RESULTS.md`; SET = `docs/evidence/lab-eval-set-20261117/`; AUD = `deliverables/2026-11-17-completion/PROJECT-COMPLETION-AUDIT.md`.

| ID | Requirement | Code file(s) | Evidence file(s) | Status | Note |
|:---|:-------------|:--------------|:--------------|:-----|:----------------|
| T1 | Manual categories as reference; measured performance shows the LLM working | `feedctrl/lab_workflows.py` (manual_preview), `feedctrl/lab.py`, `feedctrl/kuairec_catalog.py`, `web/src/LabView.jsx`, `scripts/lab_eval.py`, `feedctrl/lab_metrics.py` | RES; SET (README, FROZEN.json) | done | NL exact 17/17/16 of 20; TCP@10 none 0.006, reference 0.529, models 0.518–0.563 (no significant difference, BH p 0.62–0.65); local models NL 0/20 |
| T2 | NLP creates new categories from a description, classifies, feeds the filter | `feedctrl/lab_workflows.py` (define_category, classify_category, assess_quotes), `feedctrl/lab.py` | RES (NC table); `docs/guide/PROFESSOR-GUIDE.md` §5.5 | done | Member F1 0.875 / 0.918 / 0.936 with the reviewed definition; definition step not scored (it now proposes a definition even when the sampled items do not fit; scope up to 200); local: llama 0.179, qwen 0.469 |
| T3 | NLP maps nonliteral requests to existing categories and tags | `feedctrl/lab_workflows.py` (interpret_request), `feedctrl/kuairec_catalog.py` (label_vocabulary) | RES (NL, AB tables) | done | 467-term vocabulary; abstention 12/10/7 of 14; local NL 0/20, AB 11/14 and 9/14 by declining everything |
| T4 | Concise report of done / remaining | — | Progress report (this folder); AUD | done | Draft, not sent |
| T5 | 2–3 conferences, deadlines around January | — | `FINAL2/conference-options-verified.md` (private) | done | UMAP 22/29 Jan; SIGIR full 14/21 Jan; SIGIR demo 4/11 Feb 2027 |
| T6 | Demo video | `tools/recording/record_demo.py`, `demo_script.py`, `check_take.py` | `docs/evidence/2026-11-17-video-take12/` (README, check.json, contact sheet) | done | `COMP9500-Feed-Control-Lab-demo.mp4` (take 12): 10:22, 1920x1080, gpt-5 at minimal effort (measured: low), English display, key pasted in the masked field; take 11 (9:23) kept as backup; no silence ≥5 s; transcript 97/97 (0.898); sent separately |
| S1 | New items with descriptions | `feedctrl/lab_workflows.py` (add_items_preview), `web/src/LabView.jsx` | Guide §5.6; live smoke checks (local `runs/`); new-domain check `tools/generalization_examples.json`, `runs/generalization-gpt5*/summary.md` (local) | partial | Demonstrated, not measured; gpt-5 mapped 6/6 new requests and classified 2 new items |
| S2 | Local vs frontier comparison | `feedctrl/llm_providers.py`, `scripts/lab_eval.py` | RES; `docs/evidence/lab-eval/20261117-b-parser-rerun/summary.json` | done | 3 frontier and 2 local measured (local: NL 0/20; NC F1 0.18 / 0.47; median 126 / 109 s per call); gemma4:31b probed, too slow (0.90 tokens/s), not run; Anthropic API never run live |
| R01 | Offline study of controllability (P018, P025) | `feedctrl/evaluation.py`, `scripts/lab_eval.py` | E1 frozen results; RES | done | No human subjects |
| R02 | Prior work incl. Shu 2024 (P023, P031) | — | `paper/references-2026-11-14.bib` | partial | Shu citation unresolved |
| R03 | Common short-video testbed (P023, P117) | `scripts/run_app.py`, `run-app.cmd`, `feedctrl/lab.py` | Guide §1, §5 | done | A–E and language controls on one KuaiRec/SASRec ranking |
| R04 | React frontend, FastAPI backend (P033, P118a) | `web/src/main.jsx`, `web/src/LabView.jsx`, `feedctrl/api.py`, `feedctrl/lab_routes.py` | `tests/browser/lab_flows.cjs`; run-all-tests receipt (17 Nov 01:14Z) | done | Browser 29/29, node 126/126 (mock); not repeated on the final head |
| R05 | Open-source SASRec (P024, P033, P118b) | `feedctrl/model.py` | Checkpoint provenance | done, dep. | Independently written variant |
| R06 | Trained on KuaiRec (P024, P033) | `feedctrl/data.py`, `scripts/train.py` | 3 checkpoints; `FINAL2/AUDIT.md` | done | 865 users, 2,593 items; weak backbone |
| R07 | Local Llama 3.1 8B via Ollama (P024, P033) | `feedctrl/controls.py`, `feedctrl/llm_providers.py` | Parser re-run summary; RES | done | Re-run 79/100; frozen set 40/40 cases, NL 0/20, NC F1 0.179 |
| R08 | No paid APIs / external transfer (P024) | `feedctrl/llm_providers.py` | `FINAL2/cost-ledger.csv` (private) | done (E1), dep. | Frontier arm declared; total USD 26.83 |
| R09 | Per-item explanations (P024, P033) | `feedctrl/explanations.py` | `clauses-recheck.md` (private) | partial | Fixed-fact selection; E1 B = A |
| R10 | Precomputed explanation cache (P025, P118d) | `scripts/generate_explanations.py`, `scripts/prepare_demo_explanations.py` | `deliverables/2026-11-04-completion-review/CACHE-COVERAGE-RECEIPT.json` | partial | 10 records verified; 25 only by receipt |
| R11 | Free text to filter / boost / re-rank (P024, P033) | `feedctrl/lab_workflows.py`, `feedctrl/lab.py` | RES | done | Boost / reduce / hide / only on named KuaiRec labels; frontier and local measured |
| R12 | ~200-word editable profile from history (P024, P033) | `feedctrl/api.py` | — | partial | ~40-word category-count profile |
| R13 | (E) all combined (P025, P037) | `feedctrl/evaluation.py`, `feedctrl/controls.py` | E1 | done | No double counting |
| R14 | History initializes recommender (P025) | `feedctrl/evaluation.py`, `feedctrl/api.py` | E1 | done | — |
| R15 | Dominant-shift request script (P025) | `feedctrl/evaluation.py` | E1 protocol | done, dep. | Hash-selected from history (no leakage) |
| R16 | Request independent of answer key (P025) | `feedctrl/evaluation.py` | — | dep. | Premise invalid; test data never read |
| R17 | Thumbs-up/down baseline (P025, P037) | `feedctrl/evaluation.py` | — | done, dep. | Simulated proxy; KuaiRec has no thumbs |
| R18 | Five evaluation conditions (P025, P037, P118a) | `feedctrl/evaluation.py`, `web/src/main.jsx` | E1 (3 seeds); `tests/browser/lab_flows.cjs` | done | 4 Nov "22/22" claim had no receipt; replaced |
| R19 | Each channel isolable (P025, P117, P119) | — | E1 seed summaries | not done | B = A; C = D = E by design |
| R20 | TCP and TCER primary (P025, P037) | `feedctrl/evaluation.py`, `scripts/lab_eval.py` | E1; RES | done | New TCP 0.006 → 0.52–0.56 (reference 0.53); TCER 0.012 → 0; local TCP 0.017 / 0.059 |
| R21 | 100-case parser set and rubric (P035, P118c) | `feedctrl/parser_benchmark.py`, `scripts/parser_rerun.py` | Parser re-run summary | done | Re-run is re-use, not new evidence; grounding rule applied by re-scoring |
| R22 | Systematic from KuaiRec tags (P035) | — | SET README | partial, dep. | Frozen bank: 4 of 31 IDs; new set AI-drafted |
| R23 | ≥85% parser accuracy, 95% CI (P025, P035, P116) | `feedctrl/parser_benchmark.py` | Parser re-run summary | done, target missed | llama 79 (7 op. errors, as frozen), qwen 74, gpt-5 60, gpt-5-mini 60 strict |
| R24 | HR@1 non-inferiority 10% (P025, P037, P116) | `scripts/lab_eval.py` | RES | not done | Relative fails, absolute passes (llama passes relative only because it applied almost no control) |
| R25 | Wilcoxon, BH, α = .05 (P025, P037, P116) | `feedctrl/lab_metrics.py`, `feedctrl/evaluation.py` | E1; RES | done | Fidelity vs reviewed control n.s. for hosted models (BH p 0.62–0.65); hosted pairs n.s.; every hosted model beats both local models (McNemar BH p ≤ 0.0024) |
| R26 | Directional hypothesis (P116) | `scripts/analyze.py` | E1 combined summary | done | E1 p_BH ≤ 1e-65; new effect descriptive |
| R27 | LLM only parses at evaluation (P025) | `feedctrl/evaluation.py` | E1 | done | — |
| R28 | Reusable harness and scripts (P118d, P119) | `scripts/evaluate.py`, `scripts/analyze.py`, `scripts/verify_frozen_e1.py`, `scripts/lab_eval.py` | `FINAL2/AUDIT.md` §4 | partial | Rule arm: 399/399 metrics reproduce; rankings not bit-identical |
| R29 | 6–8 page IEEE/ACM paper (P039, P118e) | `paper/research-paper-2026-11-17.tex` | `paper/research-paper-2026-11-17.pdf` | partial | 8-page draft with the 17 Nov results for five models; one sentence for the student to confirm |
| R30 | BCIT presentation (P039, P118e) | `presentation-bcit/presentation-2026-11-17.tex` | `presentation-bcit/presentation-2026-11-17.pdf` | partial | 43 pages with the 17 Nov results (five models) and the 4 Nov negative finding |
| R31 | Source shared (P118) | — | GitHub `main`, tag `comp9500-final-2026-11` | done | Merged and tagged |
| R32 | Six-month Gantt (P042–P112) | — | `deliverables/2026-10-27-demo/PLAN-ACCEPTANCE-AUDIT-2026-10-27.md` | dep. | Replaced by the course plan |
| R33 | Artifact, comparison, protocol (P119) | all of the above | AUD | partial | Channel comparison collapses; local-vs-frontier model comparison added |
