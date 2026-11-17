# Project completion audit, 17 November 2026

Branch `final/comp9500` of <https://github.com/vibhormalik95-hue/FP>, merged to `main` and tagged `comp9500-final-2026-11`. This audit replaces the [4 November audit](../2026-11-04-completion-review/PROJECT-COMPLETION-AUDIT.md) for current status. The 4 November file is kept unchanged as history.

Status words: **done**, **partial**, **not done**. Where it matters, a status also says **executed** (an evaluation actually ran, adverse results included) or **departure** (the method differs from the proposal).

Every number below comes from a file in the repository or from the phase receipts in `C:\Users\vs981\comp9500\FINAL2\` (`AUDIT.md`, `PROGRESS.md`, `BLOCKERS.md`, `cost-ledger.csv`, `clauses-recheck.md`, `conference-options-verified.md`). Those receipts are private working notes and are not in the repository.

## 1. Statements that apply to the whole audit

- **Reference set.** The 40-case evaluation set (`docs/evidence/lab-eval-set-20261117/`) was **AI-drafted by Claude (Opus 5.5)** and **human-reviewed row by row by Vibhor Malik**. He judged all 1,211 rows individually. He agreed with 1,187 and corrected 24 (label 9, member 10, definition 2, expected status 3). The set was frozen at 2026-11-17T02:27:25Z in commit `391d462` before any measured prediction. `cases.frozen.json` has SHA-256 `d4af21e6…3a82` and `review_human.csv` has SHA-256 `384c4777…50b2` (`FROZEN.json`).
- **Bias risk.** Claude is both the drafter's model family and one of the measured models (Claude Sonnet 5.5 through the Claude Code CLI). The set README states this risk. The reviewer widened "acceptable" label sets where other readings were defensible. The risk is reduced, not removed.
- **Frontier models are a declared departure from P024.** P024 commits to a "locally hosted open-weight model" and to "avoiding paid APIs and external data transfer". This round measured gpt-5 and gpt-5-mini (OpenAI API) and Claude Sonnet 5.5 (CLI). KuaiRec item text and the requests were sent to those providers. The local arm is llama3.1:8b and qwen2.5-coder:7b-instruct through Ollama.
- **Local models.** llama3.1:8b and qwen2.5-coder:7b-instruct ran all 40 cases on the measurement commit `9071f05` (13 and 10 call errors). The first llama attempt was aborted because of runaway generation and is kept in `docs/evidence/lab-eval/20261117-main/runs/aborted/`. Commit `9071f05` added a 2,048-token output cap and no automatic retry. Prompts and scoring did not change.
- **Provenance.** Every results table names the prediction commits (hosted `8dd978f`, local `9071f05`) and the scoring commit (`d9dd6cc`). Every code change after the freeze and its effect on predictions and scores: [`docs/evidence/lab-eval/POST-FREEZE-AUDIT.md`](../../docs/evidence/lab-eval/POST-FREEZE-AUDIT.md).
- **Not measured here:** benefit to real users, real user intent, human satisfaction. The study is offline on KuaiRec.

## 2. What was done in this round (16–17 November)

| Commit | Change |
| --- | --- |
| `6cfd24f` | `.gitignore` covers private `data/` and `results/` |
| `5ad66d8` | Removed the legacy token gate and the hand-written rehearsal replies |
| `8ffc5a7` | **One app on real KuaiRec**: `run-app.cmd` → `scripts/run_app.py`, A–E view plus language controls, ranked by the trained SASRec seed-42 checkpoint (`feedctrl/lab.py`, `lab_routes.py`, `lab_workflows.py`, `kuairec_catalog.py`, `llm_providers.py`, `web/src/LabView.jsx`) |
| `e51900b` | `run-all-tests.cmd` / `scripts/run_all_tests.py`, `tests/test_lab.py`, `tests/test_no_hardcoded_examples.py`, `tests/browser/lab_flows.cjs`; fixes for Windows test failures |
| `9c9d393`, `3c3387b` | Evaluation harness `scripts/lab_eval.py`, metrics `feedctrl/lab_metrics.py` and their tests; parser-bank re-run `scripts/parser_rerun.py` |
| `391d462` | Froze the human-reviewed set before any prediction (pushed to `origin/final/comp9500`) |
| `8dd978f`, `e76958c`, `b90db75` | Test fix; demo recorder; professor guide `docs/guide/PROFESSOR-GUIDE.md` / `.pdf` with screenshots |
| `9071f05` | Local models: 2,048-token output cap, no retry (operational) |
| `ac05de4` | Measured results: `docs/evidence/lab-eval/20261117-main/` (RESULTS.md, summary.json, per-case.csv, raw runs) and the parser re-run `docs/evidence/lab-eval/20261117-b-parser-rerun/` |
| `d069c13` | Documents of 17 November: paper, deck, this audit, requirements page, report and worksheet sources |
| `1de3955` | Fixes from the independent code review: quotation check at least two characters and whole tags (app only; the measured runs keep the rule of `9071f05`); downstream scoring with the exact controls; no-hardcoding test scans the prompts; monotonic version after Reset; locked reads; Claude CLI argument validation; explicit provider base URLs; anti-framing headers; errored NC cases score zero |
| `4628bf2` | Re-score: downstream with the exact controls; parser re-run with the grounding rule of `controls.parse_control` (re-scoring of the saved predictions) |
| `6f255d8` to `b5f27d5` | Recorder and page: the server reads `OPENAI_API_KEY` from its environment (the key never goes to the clipboard or the page); English display by default with one switch to the original text; focus and timing fixes |
| `888517f` | The define step proposes a definition even when the sampled items do not fit; scope up to 200; new-domain examples `tools/generalization_examples.json` |
| `04d21ed` | Budget: an upper-bound cost is reserved before each call, so parallel calls cannot overspend; a failed call is charged its reservation; tests |
| `e1851ac`, `182b87f` | `fetch-assets.cmd` / `.sh` download the KuaiRec assets from the GitHub Release `comp9500-kuairec-assets-v1` (CC BY-SA 4.0, `notices/KUAIREC-ASSETS-ATTRIBUTION.md`) and verify every SHA-256; results tables name their commits; post-freeze audit. Fresh-clone test passed: fetch-assets, fresh install, `run-app`, Results page |
| `1ac2566` | Measured results with all five models (llama3.1:8b and qwen2.5-coder:7b-instruct added); gemma4:31b probe recorded, not run |
| `af9082e` | The manual control accepts several labels in one preview (one Undo removes them) |

All of these commits are merged to `main` and tagged `comp9500-final-2026-11`.

The Phase 1 audit also re-ran Experiment 1 from the checkpoints on Windows (`results/e1-replay-20261116/`, private). All 399 numeric leaves of `combined-summary.json` match the frozen file. Full-ranking hashes differ below the top ten (`FINAL2/AUDIT.md` §4).

Recorded software check, mock provider, 2026-11-17T01:14Z (`runs/all-tests-20261117T011407Z/summary.md`, ignored folder; copy in `FINAL2/receipts/run-all-tests-mock.txt`). pytest: 1,745 passed, 76 skipped, 1 failed. The failure is `test_guarded_current_contract`, which is frozen by design: an offline guard from the 11 November profile blocks ctypes on Windows. Node: 126/126. Browser: 29/29. Workflows: 13/13. That check ran before commits `9c9d393`–`888517f`. The final full run (mock, 2026-11-17T06:59Z, on the final code after commit d824e13; receipts in `FINAL2/receipts/final-tests/`) gave pytest 1,752 passed, 75 skipped and 1 failed (frozen by design: `test_guarded_current_contract`), page tests 126/126, browser 29/29 and workflows 14/14.

Cost ledger (`FINAL2/cost-ledger.csv`): running total USD 26.83 (running total of rounded rows; the rows sum to 26.82), which includes USD 15.50 for earlier sessions (stated by the user). The Claude CLI costs are CLI-reported and notional (subscription sign-in). The ledger ends with the guide screenshots; the new-domain checks and the video take with gpt-5 are not in it.

## 3. Measured results on the frozen set (`docs/evidence/lab-eval/20261117-main/RESULTS.md`)

| Measure | Claude Sonnet 5.5 (CLI) | gpt-5 | gpt-5-mini | llama3.1:8b (local) | qwen2.5-coder:7b-instruct (local) |
| --- | --- | --- | --- | --- | --- |
| NL exact intended profile (20) | 17/20 [0.640, 0.948] | 17/20 [0.640, 0.948] | 16/20 [0.584, 0.919] | 0/20 [0.000, 0.161] | 0/20 [0.000, 0.161] |
| NL label F1 | 0.917 | 0.943 | 0.930 | 0.040 | 0.000 |
| AB correct abstention (14) | 12/14 (2 false acceptances) | 10/14 (4) | 7/14 (7) | 11/14 (0) | 9/14 (0) |
| NC member F1, 150-item pool (P / R) | 0.875 (1.000 / 0.793) | 0.918 (0.958 / 0.894) | 0.936 (0.942 / 0.934) | 0.179 (0.291 / 0.131) | 0.469 (0.972 / 0.330) |
| Downstream TCP@10, boost/only (none 0.0063; reference 0.5290) | 0.5625 | 0.5521 | 0.5178 | 0.0167 | 0.0585 |
| Downstream TCER@10, hide/reduce (none 0.0118; reference 0) | 0 | 0 | 0 | 0.0109 | 0.0118 |
| NDCG@10 (none 0.0242; reference 0.0153) | 0.0144 | 0.0156 | 0.0145 | 0.0237 | 0.0217 |
| HR@1 non-inferiority vs none, relative 10% / absolute 0.10 | fails / passes | fails / passes | fails / passes | passes (almost no control applied) / passes | fails / passes |
| TCP fidelity vs reviewed control (mean diff, BH p) | +0.034, 0.6214 | +0.023, 0.6543 | −0.011, 0.6214 | −0.512, 0.0001 | −0.470, 0.0001 |
| Successes of 40 (paired McNemar between models, BH) | 33 | 32 | 29 | 11 | 9 |
| Median s/call; cost USD | 6.6; 5.86 (notional) | 12.5; 2.39 | 11.7; 0.47 | 125.8; 0 | 109.0; 0 |
| Calls; call errors; case errors | 136; 0; 0 | 137; 0; 0 | 138; 0; 0 | 106; 13; 9 | 138; 10; 5 |

Predictions produced at commit `8dd978f` (hosted) and `9071f05` (local); all rows scored at commit `d9dd6cc` (named under every table of RESULTS.md; see [`POST-FREEZE-AUDIT.md`](../../docs/evidence/lab-eval/POST-FREEZE-AUDIT.md)).

All hosted runs completed 40/40 cases with zero call errors. No pair of hosted models differs significantly (McNemar BH p ≥ 0.55, Wilcoxon BH p ≥ 0.22); every hosted model differs from both local models (McNemar BH p ≤ 0.0024); llama and qwen do not differ (p 0.81).

**Local versus frontier.** On this laptop the two local 7–8B models proposed almost nothing. On the 20 nonliteral requests llama3.1:8b matched no exact profile: it declined 17 (16 as ambiguous, 1 as no match), failed 2 at the output cap and proposed once. qwen2.5-coder:7b-instruct matched none and declined all 20 (10 as no match, 10 as unsupported). Their abstention scores (11/14 and 9/14) therefore reflect declining everything, not judgement; only 5 and 3 of their statuses match the reference, and their remaining AB cases are call failures. On new categories qwen was precise but missed most members (precision 0.97, recall 0.33, F1 0.47); llama reached F1 0.18, with 4 of 6 cases failing at the output cap. The frontier models reached 16–17/20 exact and member F1 0.88–0.94. The local calls cost nothing but took about two minutes each (median 126 s and 109 s; 90th percentile 267 s and 159 s). gemma4:31b fit in memory (37 GB with nothing else loaded, 89% CPU / 11% GPU, 32k context) but was too slow to measure: a 21,086-token prompt took 181 s, generation ran at 0.90 tokens/s, the first reply was unfinished after about 45 minutes, and the full set would take tens of hours (`runs/local-chain.log`). Not run. The downstream analysis used 200 sampled users with seed 2026. Each model's exact controls are applied to the same SASRec ranking with the application's own policy (strength and mixed actions exactly; all "only" labels of a case are treated as one group, because the saved predictions do not record groups — this can differ from the app for NL06, NL08 and NL15); the reference control applies the required labels at standard strength. These values were re-scored on 17 November (commit `4628bf2`) after the code review found that the earlier scoring ignored strength; the predictions did not change. No hosted model differs significantly from the reviewed control (BH p 0.6214–0.6543). A model that errs or abstains keeps the uncontrolled ranking. TCP/TCER are computed against the reference target set. In NC, every model classified with the reviewed reference definition. NC therefore measures membership, not the quality of a definition the model wrote itself.

**Parser bank re-run** (`20261117-b-parser-rerun/summary.json`). This is a **re-use** of the exposed 100-case bank, unchanged, and not new evidence. It uses the original prompt, schema, validator and grounding rule of `controls.parse_control`; the grounding rule was applied by re-scoring the saved predictions (`scripts/parser_rerun_rescore.py`).

| Model | Strict exact (target 85%) | Operational errors | Clarify correct |
| --- | --- | --- | --- |
| llama3.1:8b | 79/100 [0.700, 0.858] (same as frozen) | 7 (same as frozen) | 9/30 |
| qwen2.5-coder:7b | 74/100 | 13 | 10/30 |
| gpt-5-mini | 60/100 | 36 | 0/30 |
| gpt-5 | 60/100 | 35 | 0/30 |

In run 2, which saved the raw replies, gpt-5-mini scored 95/100 and gpt-5 96/100 under a post-hoc format-lenient score. That score ignores the strength field on reset/clarify replies, a rule the frozen prompt states and both models broke. The strict score is primary. No model meets 85% strict.

## 4. Professor's transcript requirements (meeting transcript supplied by the student on 4 November; email of 10 November, not in the evidence folder)

| # | Requirement (paraphrase; transcript time) | Evidence now | Status |
| --- | --- | --- | --- |
| T1 | Manual categories as the reference, with **measured** performance that shows the LLM working (08:22) | Manual control on KuaiRec's 266 named categories and tags: `lab_workflows.manual_preview`, tab "Choose a category". The human-reviewed reference set is the manual reference. Model vs reference: NL exact 17/17/16 of 20; TCP@10 0.52–0.56 vs reference 0.53 vs none 0.006; no significant difference from the reviewed control (BH p 0.62–0.65). Local models: NL 0/20 | **done, executed** (frontier and local) |
| T2 | NLP **creates new categories** from a description, classifies items, feeds the filter (08:38) | `define_category` → `classify_category` (quotation required, separate quotation check) → Apply as only/more/less/hide (`feedctrl/lab_workflows.py`; guide §5.5). NC member F1 0.875/0.918/0.936 on 6 descriptions × 150 items | **done, executed** for membership. The model-written definition step is demonstrated (live checks of gpt-5-mini and Claude CLI) but not scored; since `888517f` it proposes a definition even when the sampled items do not fit (scope up to 200). Local: member F1 0.179 (llama), 0.469 (qwen) |
| T3 | NLP maps **nonliteral** requests to existing categories and tags (07:49, 08:38) | `interpret_request` over 467 terms (266 categories plus 201 tags with ≥3 items). NL: 20 nonliteral requests (10 EN, 10 ZH), exact 17/20 (gpt-5, Claude), 16/20 (gpt-5-mini). AB: 14 should-not-propose cases, abstention 12/10/7. Local: NL 0/20 each; AB 11/14 and 9/14 by declining everything | **done, executed** (frontier and local) |
| S1 | Student commitment: **new items with descriptions** (01:28–02:08) | `add_items_preview`, tab "New items" (guide §5.6). Live smoke checks (gpt-5-mini, Claude CLI): a hiking item got 旅游/景物摄影; a cooking item got 美食教程 (`runs/live-*`, ignored folder). New-domain check with gpt-5 (`tools/generalization_examples.json`; `runs/generalization-gpt5/summary.md`, `runs/generalization-gpt5-nc/summary.md`, ignored folder): 6/6 new requests mapped to existing labels; 2 new items classified to existing categories; for 2 new descriptions a definition was proposed, and classification of 100 items selected 0 for each. A new item has no history and starts at the user's median score | **partial**: implemented and demonstrated, not measured |
| S2 | Student commitment: **local vs frontier comparison** (02:35) | Frozen set: gpt-5, gpt-5-mini, Claude Sonnet 5.5 (hosted) and llama3.1:8b, qwen2.5-coder:7b-instruct (local) measured on all 40 cases (§3). gemma4:31b probed, not run: it fits at 37 GB but generates 0.90 tokens/s; the set would take tens of hours (`runs/local-chain.log`). Anthropic API adapter never run live (no key) | **done, executed** (gemma4:31b and the Anthropic API route open) |
| T4 | Concise report of what is done and what remains (09:18) | `COMP9500-Progress-Report-2026-11-17` (docx/pdf; source in this folder); this audit; `docs/requirements-and-evidence.md` | **done** (draft; not sent) |
| T5 | 2–3 conferences with deadlines around January (11:48–12:05) | `FINAL2/conference-options-verified.md`, official pages read 16–17 Nov: **UMAP 2027** abstract 22 Jan, paper 29 Jan 2027; **SIGIR 2027 full** abstract 14 Jan, paper 21 Jan 2027; **SIGIR 2027 demo** abstract 4 Feb, paper 11 Feb 2027 (all AoE) | **done** (not sent) |
| T6 | Demo video by Friday (email of 10 Nov) | `COMP9500-Feed-Control-Lab-demo.mp4` (take 11, `FINAL2/recording/take-11/`): 9:23, 1920x1080, Kokoro af_heart narration, gpt-5 through the OpenAI API (key from the environment, never shown), English display mode. Checks (`check.json`, `contact.png`; copy in `docs/evidence/2026-11-17-video/`): no silence ≥5 s at −45 dB; whisper transcript 96/96 script sentences (similarity 0.936); one frame every 30 s. Recorder `tools/recording/` | **done** (video sent separately, not in the repository) |

## 5. The 33 proposal clauses

P### = paragraph of the supplied proposal form (SHA-256 `1bc68ff0…a27bd`), counted as in the 4 November audit. "Change since 4 Nov" includes corrections found by the 16 November re-check (`FINAL2/clauses-recheck.md`).

| ID | Requirement (short quote, P###) | Evidence now | Status | Change since 4 Nov | Remaining |
| --- | --- | --- | --- | --- | --- |
| R01 | "…An Offline Study of Controllability"; offline, no human subjects (P018, P025) | Paper title `paper/research-paper-2026-11-17.tex`; E1 harness `feedctrl/evaluation.py`; new evaluation also offline (`scripts/lab_eval.py`) | done, executed | New offline evaluation added | none |
| R02 | Investigate prior work (Niu, Lu, Dai, Ramos; "Shu et al., 2024") (P023, P031) | `paper/references-2026-11-14.bib` has the other works; no Shu entry | partial | Re-check confirms the Shu gap | Cite a resolved Shu paper (candidate RAH, arXiv 2308.09904) or mark it unresolved |
| R03 | "compare these channels on a common short-video testbed" (P023, P117) | One app on real KuaiRec: A–E and language controls on the same SASRec seed-42 ranking (`8ffc5a7`, `scripts/run_app.py`); E1 shared score vectors | done, executed (channels collapse; see R19) | Language controls moved from invented 8–10-item scenarios onto real KuaiRec | none |
| R04 | "React frontend, FastAPI backend" (P033, P118a) | `web/src/main.jsx`, `web/src/LabView.jsx`; `feedctrl/api.py`, `feedctrl/lab_routes.py`; browser flows 29/29 (mock, `lab_flows.cjs`) | done | Integrated Lab view, loopback guard replaces the token; anti-framing headers (`1de3955`) | Re-run `run-all-tests.cmd` on the final head |
| R05 | "open-source SASRec implementation (Kang & McAuley)" (P024, P033, P118b) | `feedctrl/model.py`, independently written SASRec-style model; NOTICE: no code licence chosen | done, departure (minor) | none | Disclose in the paper; choose a licence |
| R06 | "trained on KuaiRec" (P024, P033) | 865 users, 2,593 items, 31 opaque IDs; checkpoints seeds 42/43/44; backbone weak (HR@1 0.000–0.462%) | done, executed | App now also uses KuaiRec caption text: 266 category names, tags, gloss (`feedctrl/kuairec_catalog.py`) | none (stronger backbone optional) |
| R07 | "locally hosted open-weight model (Llama 3.1 8B via Ollama)" (P024, P033) | E1 and frozen parser: llama3.1:8b. Parser re-run 79/100 reproduced. App has an Ollama provider (`llm_providers.py`). Frozen-set llama run: 40/40 cases, NL 0/20, NC F1 0.179 | done, executed | The 4 Nov "implemented" was stale: November controls ran on hosted Claude. Now a local arm (llama, qwen) is part of the evaluation | none (gemma4:31b needs a faster machine) |
| R08 | "avoiding paid APIs and external data transfer" (P024) | E1 local only. New evaluation used OpenAI and Claude CLI; ledger USD 26.83 total | done for E1; **departure** for the frontier arm (declared) | Departure now declared, with costs recorded | Keep the disclosure in the paper |
| R09 | "plain-English per-item explanations of why each item was recommended" (P024, P033) | `feedctrl/explanations.py`: the LLM selects 1–3 fixed facts. E1 condition B used one template sentence; B = A by construction | partial | Re-check: the 4 Nov wording described the app, not the evaluated B | Per-item explanations over named KuaiRec categories not built; no offline metric |
| R10 | "Per-item explanations are pre-computed and cached" (P025, P118d) | 10 cached records verified (user 14); the 25-record cache exists only as a receipt (`CACHE-COVERAGE-RECEIPT.json`); app falls back to templates | partial | Re-check: the 25-record cache was not found in the private assets | Regenerate or locate the cache |
| R11 | "free-text controls translated into filter, boost, and re-rank operations" (P024, P033) | Real KuaiRec: `interpret_request` → boost/reduce/hide/only with strength; manual, new-category, new-item workflows; measured NL 16–17/20, AB 7–12/14 | done, executed (frontier and local) | Was "only `category_N`" on real data; now named categories and tags, EN and ZH | none |
| R12 | "editable natural-language user profile (~200 words, initialized from history)" (P024, P033) | `api.py`: about 40 words of category-ID counts; 200 is a maximum; E1 D is one sentence | partial | Re-check correction; not changed this round | Build a ~200-word history profile with named categories |
| R13 | "(E) all combined" (P025, P037) | `evaluation.py` E = C + D; `controls.py` stops double counting | done | none | none |
| R14 | "watch history initializes the recommender" (P025) | train + request history scored (`evaluation.py`, `api.py`); Lab uses the same scorer | done | none | none |
| R15 | "deterministic script identifies the dominant category-proportion shift…" (P025) | Requests chosen by hash from history categories, never held-out data | done, departure (avoids leakage) | none | none (disclosed) |
| R16 | "The LLM never sees the held-out item IDs, so the request is independent…" (P025) | Hiding IDs does not hide categories; pipeline never reads test data | departure (premise invalid) | none | none (disclosed) |
| R17 | "(A) thumbs-up/down baseline" (P025, P037) | Simulated one-item reaction; KuaiRec has no thumbs signal | done, departure (synthetic proxy) | none | none (disclosed) |
| R18 | "five evaluation conditions" (P025, P037, P118a) | E1 A–E, 3 seeds; A–E view on KuaiRec in the integrated app, browser flow in `lab_flows.cjs` (mock, 29/29) | done, executed | Re-check: the 4 Nov "22/22 fresh served checks" has no receipt (it is the 27 Oct verifier). Replaced by the KuaiRec browser flow | Re-run on the final head |
| R19 | "so each channel's contribution is isolable" (P025, P117, P119) | B ≡ A; C = D = E on 100% of E1 requests | not done (unestablished by design) | none | Not fixable without a new design |
| R20 | "TCP… TCER… primary outcome" (P025, P037) | E1: TCP 11.615% → 79.222%, TCER 6.112% → 0. New: TCP@10 none 0.0063 → models 0.5178–0.5625 (reference 0.5290); TCER 0.0118 → 0; local 0.0167 / 0.0585 | done, executed | Fresh downstream TCP/TCER on the frozen set | none |
| R21 | "100-utterance labelled validation set… rubric" (P035, P118c) | 100 test / 24 dev, hashes match; re-run with 4 models (re-use) | done, executed | Re-run added, labelled re-use | none |
| R22 | "generated systematically from KuaiRec content-category tags" (P035) | Frozen bank: 4 of 31 opaque IDs, no KuaiRec names. New set: 40 cases on KuaiRec named labels (467-term vocabulary), but AI-drafted, not generated by a systematic procedure | partial / departure | Re-check: the 4 Nov audit omitted the 4-of-31 restriction. New set uses KuaiRec names | Disclose; no fix for the frozen bank |
| R23 | "parser accuracy (target ≥85%)… 95% CI; <70% degraded" (P025, P035, P116) | Frozen llama 79/100 [70.02, 85.83], 7 operational errors, clarify 9/30; re-run llama 79 (7 operational errors, as frozen), qwen 74, gpt-5 / gpt-5-mini 60 strict | done, executed; **target missed** | Re-run added; frozen result unchanged | none (report as a finding) |
| R24 | "top-1 hit-rate non-inferiority within 10%" (P025, P037, P116) | E1: absolute 0.10 passes, relative fails. New: all three hosted models fail relative 10% (CI lower −0.0027/−0.0023/−0.0021 vs margin −0.0005), pass absolute 0.10; llama passes only because it applied almost no control, qwen fails | not done (unestablished) | Fresh test, same conclusion | Needs a stronger backbone |
| R25 | "Wilcoxon signed-rank at α=0.05 with Benjamini–Hochberg" (P025, P037, P116) | E1 (6 contrasts); new: Wilcoxon + BH for TCP fidelity, McNemar/Wilcoxon + BH between models (`feedctrl/lab_metrics.py`) | done, executed | Fresh paired tests (five models, BH over ten pairs) | none |
| R26 | "TCP… significantly higher… TCER… lower under at least one condition than A" (P116) | E1 supported, p_BH ≤ 1e-65. New: TCP/TCER move strongly vs no control (descriptive; no significance test vs none in this run) | done, executed (E1); descriptive (new) | none | Optional: test model control vs none |
| R27 | "the LLM only parses control requests at evaluation time" (P025) | E1 explanations are templates; LLM only parses | done | Re-check: E1 used no cache | none |
| R28 | "reusable offline ablation harness with analysis scripts" (P118d, P119) | `scripts/evaluate.py`, `analyze.py`, `verify_frozen_e1.py`, new `scripts/lab_eval.py run/score`, `scripts/parser_rerun.py`. Windows E1 replay of the rule arm: 399/399 numeric leaves identical; full-ranking hashes differ | partial (metrics reproduce; bit-identical rankings do not) | Replay executed 16–17 Nov | none feasible (original score vectors not recoverable) |
| R29 | "6–8 page applied research paper in IEEE or ACM format" (P039, P118e) | `paper/research-paper-2026-11-17.pdf`, 8 pages, IEEEtran, draft with Experiment 3 (five models) and the departures; one "[student to confirm]" marker | partial (draft) | 4 Nov cited a 7-page PDF; now the 8-page 17 Nov draft | The student reviews the text; final acceptance is a real event |
| R30 | "presentation using the official BCIT slide template" (P039, P118e) | `presentation-bcit/presentation-2026-11-17.pdf`, 43 pages: Experiments 1–3, the 4 Nov negative finding (48/100, 19/20), the video and the conferences; all five models | partial (draft) | Updated for November work | Delivery is a real event |
| R31 | "Source code will be shared with the supervisor and program" (P118) | Public repo; `final/comp9500` merged to `main` and tagged `comp9500-final-2026-11` | done | Branch pushed (freeze commit public before predictions); merged and tagged | Supervisor receipt is a real event |
| R32 | Gantt Month 1–6 plus contingency (P042–P112) | Replaced by the 135-hour course plan (`deliverables/2026-10-27-demo/PLAN-ACCEPTANCE-AUDIT-2026-10-27.md`) | departure (schedule replaced) | none | none |
| R33 | "(1) applied artifact (2) like-for-like comparison of three control channels (3) reusable protocol" (P119) | (1) integrated KuaiRec app; (2) collapses (B = A, C = D = E), but a model comparison now exists; (3) harnesses exist | partial | (1) and (3) strengthened; a local-vs-frontier comparison was added (two local, three hosted models) | Channel isolation stays limited |

**Counts (primary status).** Done: 20 (R01, R03, R04, R05, R06, R07, R08, R11, R13, R14, R15, R17, R18, R20, R21, R23, R25, R26, R27, R31). R23's done means the evaluation ran; its 85% target was missed. Partial: 9 (R02, R09, R10, R12, R22, R28, R29, R30, R33). Not done: 2 (R19, R24). Departure only: 2 (R16, R32). Departure flags also apply to R05, R08 (frontier arm), R15, R17 and R22.

## 6. Remaining work

1. A live test of the Anthropic API route (needs a key; Claude was measured through the CLI only).
2. A full gemma4:31b run on the frozen set; it needs a faster machine (probe: 0.90 tokens/s on this laptop).
3. Extra polish: send the demo video `COMP9500-Feed-Control-Lab-demo.mp4`; re-run `run-all-tests.cmd` on the final head; add the Shu citation (R02). (The app's assets are now public through `fetch-assets`.)
4. Author review of the paper: the student reviews the text and removes the "[student to confirm]" marker.
5. Code-review findings not fixed in code (the budget reservation is fixed in `04d21ed`): resumed runs overwrite `meta.json`; URL userinfo is not stripped from the displayed base URL; CLI replies are not schema-checked; the Results narration is fixed text.
6. Not fixable by software: R15, R16, R17, R19 (design), the frozen 79/100 (R23), R32. Real events: supervisor receipt, defence, paper acceptance.

Note on failures in the local runs: two llama3.1:8b cases (AB09, AB11) failed because the operator stopped the Ollama model during a video recording; they are kept and scored as errors. See `docs/evidence/lab-eval/POST-FREEZE-AUDIT.md`.
