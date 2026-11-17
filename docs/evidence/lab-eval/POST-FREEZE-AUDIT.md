# Post-freeze audit of code changes (evaluation set frozen at commit 391d462)

The evaluation set was frozen and its hashes committed at `391d462` (2026-11-17T02:27:25Z) before any measured prediction. This page lists every later change to code that the measurement uses, and states whether it affects a measured output.

Two kinds of output are distinguished:

- **Predictions**: what a model returned for each case, produced by `scripts/lab_eval.py run` through `feedctrl/lab_workflows.py` (`interpret_request`, `classify_members`), the prompts, `feedctrl/llm_providers.py` and `quote_found`.
- **Scores**: the numbers computed from saved predictions by `scripts/lab_eval.py score` and `feedctrl/lab_metrics.py`. Scores can be recomputed at any time without calling a model.

## Which code produced the predictions

| Models | Prediction code commit | How it differs from the freeze |
| --- | --- | --- |
| gpt-5, gpt-5-mini, Claude Sonnet 5.5 (CLI) | `8dd978f` | Test-only change (an allow-list in `tests/test_no_hardcoded_examples.py`). Prediction code identical to `391d462`. |
| llama3.1:8b, qwen2.5-coder:7b-instruct | `9071f05` (worktree `FP-measure`) | Adds the local-only output cap (2,048 tokens) and no automatic retry in the Ollama path of `llm_providers.py`. Hosted calls do not run that path. Prompts, schemas, item views and `quote_found` are identical to `391d462`. |

All five models therefore ran the same prompts, schemas, item views and quotation rule. The local-only cap turns a runaway local generation into a recorded failure; it was added after llama's first attempt ran away (that attempt is kept in `20261117-main/runs/aborted/`).

## Every later change and its effect

| Commit | Change | Affects predictions? | Affects scores? |
| --- | --- | --- | --- |
| `8dd978f` | Test allow-list for Ollama context sizes | No | No |
| `e76958c`, `b90db75` | Recorder, page hooks, Results narration file; parser re-run saves raw replies | No | No (narration only) |
| `9071f05` | Local output cap, no retry (Ollama only) | Local models only (see above) | No |
| `1de3955` | Quotation rule ≥2 characters and whole tags (app); downstream scoring applies the exact proposed controls; metrics: a failed new-category case scores 0, errors not counted as clarifications; reset version; CLI argument checks; explicit base URLs; anti-framing headers | Not for any reported run: every reported prediction was produced with the freeze-time rule. A re-run today would use the stricter rule. | **Yes**: downstream TCP/TCER/NDCG/HR@1 and the fidelity test (re-scored at `4628bf2`); error handling in member F1 and clarification counts (no hosted errors; affects local rows) |
| `4628bf2` | Re-score published; parser re-run grounding rule applied by re-scoring saved predictions | No | Yes (parser operational-error counts; accuracy unchanged) |
| `335b884`, `5b8f9da`, `ff8f3b5`, `b5f27d5` | Page fixes, English display, notes text in `interpret_preview` (not in `interpret_request`) | No | No |
| `69b94b4`, `888517f` | DEFINE prompt (language; propose without sample support); scope clamp | No (define is not measured; every new-category case uses the reviewed reference definition) | No |
| `62b9f1c` | Base URL display | No | No |
| `d093815` | Base URL refused without scheme; Latin quotations need 3+ letters (app); line endings | No (same as `1de3955`) | No |
| `04d21ed` | Budget reservation before parallel calls; failed calls charged their reservation | No (no reported run hit a budget; failed hosted calls: none) | No |
| `e1851ac` | Results tables name their commits; fetch-assets | No | No (labels only) |
| r4 (English only) | The app, the prompts and the screen use the English text layer `data/kuairec_text_en-v1.json` (machine translation of KuaiRec, SHA-256 `034f5ac9…`) instead of the Chinese source text and the gloss; prompts say the text is English; no gloss field; quotations need at least 3 characters; the study-view topic prompt asks for English aliases | Not for any reported run: every reported prediction used the original text. A new run on the English layer is a separate run (`lab_eval.py run --text english`) | No: the 17 Nov runs are scored on the original text (`lab_eval.py score --text original`, the default) |

## Consequence for the tables

- Since the English-only change (r4), the Results page labels every run that used the original text: "Measured on the original-text run (17 Nov); English-input re-run pending." The result files themselves are frozen and are not edited.

- Every results table states the prediction commit of each model and the scoring commit (`scripts/lab_eval.py` adds the line to each table note and to `summary.json`).
- All rows of a table are scored by the same scoring code at the same commit, from predictions produced by prediction code that is identical across models (except the local-only cap). No table mixes scoring versions.
- The define change and the quotation-rule changes do not touch any reported number. The downstream re-score does; it is applied to all models at one scoring commit, so no model was re-run.
- The shipped app is stricter than the measured code in one respect: quotations must be at least two characters (three for Latin text) and tags must match whole. The measured member selections used the freeze-time rule; this is stated beside the new-category table.

## Notes on the local runs

- llama3.1:8b ran in two parts on the same prediction code: cases 1–21 in the main checkout after commit `9071f05` (its `meta.json` start time, 06:58:58Z, is from the later resume in the `FP-measure` worktree at `9071f05`, which rewrote the meta file), and the rest in `FP-measure` at `9071f05`. The interpret and classification paths are byte-identical in both, so no number depends on the split.
- Two llama cases, AB09 and AB11, failed with "Could not reach http://127.0.0.1:11434": the operator stopped the Ollama model while those cases were running, to free the machine for a video recording. The protocol keeps failures, so they are scored as errors (not as abstentions); they are not re-run. Five llama and five qwen cases failed at the local 2,048-token output cap; they are scored as errors too.
