# Prospective synthetic-language evaluation, 4 November 2026

## Result

The frozen reviewed-topic pipeline matched the complete intended final profile on **48/100 supported requests**. It correctly clarified and preserved the initial profile on **19/20 diagnostic requests**. This does not establish reliable autonomous language control or an LLM recommendation benefit. The earlier E1 79/100 and revised AI-reference E2 76/100 results remain separate, unchanged studies.

| Supported stratum | Complete profile correct |
| --- | --- |
| single boost | 11/20 |
| single reduce | 7/20 |
| single exclude | 8/20 |
| two topic | 15/20 |
| profile replacement | 1/10 |
| single subject context | 6/10 |

Across all 120 invocations there were 49 ready proposals, 61 clarifications, five grounding errors and five parser/schema rejections recorded under the runner status `operational_error`. These five were four invalid undo/clear plans containing topic actions and one graded hard exclusion, not evidence of a network or runtime outage. The 49 ready proposals comprise 48 correct supported cases and one incorrect diagnostic case. The other 52 supported cases were 42 clarifications and ten errors. Clarification is not counted as successful execution of a supported request. Of all clarification dispositions, 58 originated in the model and three in deterministic prechecks. All attempted cases and failures are retained; no case was rerun.

This is a dated supplement to the existing seven-page paper review; that earlier PDF has not been silently rewritten to include this study.

## What was frozen and executed

- Source behavior: [ef1bf295](https://github.com/vibhormalik95-hue/FP/tree/ef1bf2950e9e67882c20f394f4b179a7d72327a2), installed `qwen2.5-coder:7b-instruct`, Ollama 0.34.0. The model digest is `dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`.
- An isolated AI author prepared 100 supported requests and 20 ambiguous/unsupported diagnostics, with separately locked references reviewed by another AI role. These are synthetic intended commands, not human annotations or participant preferences. Grading is deterministic; no LLM judged its own output.
- Each input supplied text, instruction/profile mode, initial profile and focus. Subjects were quoted literal Chinese source phrases. This tests named source-scope control, not discovery of a validated ontology or universal multilingual semantics. No preconfirmed binding or expected answer was given to inference.
- The operator protocol froze at 20:08:46 UTC. Inference ran once from 20:24:39 to 20:27:04 UTC. All 120 cases were attempted within the fixed 60-second per-case and 21:00 UTC overall cutoff. The receipt records 117 model calls; other provenance requests are retained separately. No case retry, repair or outcome-driven stopping was used.
- Predictions were hashed before references opened at 20:32:13 UTC. Ranking finished at 20:34:39 UTC. Complete final profiles were compared by operation, strength and full catalogue-membership fingerprint, so equivalent aliases were not penalized for spelling alone. Diagnostic credit required machine clarification and an unchanged profile; runtime and grounding errors did not receive that credit.

## Manual, neutral and LLM ranking comparison

The same 72 numeric score vectors, one for each of 24 deterministically selected users and seeds 42/43/44, were reused for every comparator. Each vector contains all 2,593 catalogue scores. All vectors and all 28,800 complete rankings are retained. The 100 language cases remain the language analysis units; 7,200 user/case/seed rows are not 7,200 independent utterances.

Across changed reference scopes, the intended manual profile changed top-ten exposure by **5.3579 percentage points** relative to the initial profile; the LLM-proposed profile changed it by **2.9292 points**. The paired actual-minus-reference exposure error was **-2.4287 points**. These are signed descriptive averages, not a success rate. Removing or weakening a reduction may increase exposure, so direction was measured against the actual reference change. Zero reference movement was not credited as positive directional success. Averaging was scopes within cases, then cases within seeds, seeds within users and users.

| Path | HR@1 | NDCG@10 | Fill rate |
| --- | --- | --- | --- |
| History-only neutral | 0.027778 | 0.068697 | 1.000 |
| Initial profile | 0.025417 | 0.064981 | 1.000 |
| Intended manual profile | 0.023333 | 0.061120 | 1.000 |
| LLM proposed profile | 0.022917 | 0.061683 | 1.000 |

The LLM comparator retains the unchanged initial profile for clarification or failed interpretation; it does not invent a replacement command. All paths filled ten slots in these cases. The next-item labels are reused historical labels; these numbers do not establish satisfaction, independently known human relevance, non-inferiority or fresh behavioral generalization. No sampling confidence intervals or p-values are reported for this finite authored-bank census. The manual and LLM profiles use the same deterministic ranking policy; differences arise from interpretation and the resulting profile.

## Evidence and interpretation

The source owner received only the question bank before inference. References were supplied after the prediction commitment. The preserved original reference commitments are `cdce83a4d4495f89e68b58c9767d4de383f10877aad135eca1004b49cab83764` (100 supported) and `664c9201895fe57cb4c9a7f190859ab7fbb822afe4deb1a7f4bc5f2a576ad473` (20 diagnostics). The frozen protocol hash is `c16d5215edf32fb233a5525a691df7ef143b1bcca80acd75be47f13d752e7d20`; predictions are `83097deb3792f7c0f29f7edd72e0f2b8d78da154db03e9047b9a393fa9f2cb70`.

A separate AI review reproduced the command counts, strata, status totals, all 7,200 top-ten exposure rows, aggregate arithmetic and 72 finite vectors. It checked HR/NDCG arithmetic without independently inspecting the historical relevance labels; this is not a fresh scientific reproduction. The accompanying [machine-readable summary](RESULTS-SUMMARY.json) gives the aggregates. Local study evidence retains the locked protocol, question/reference bytes, every model request/response/error, profile memberships, grades, score vectors and complete rankings. The study directory is `results/experiment2/comp9500-reviewed-topic-20261104-v1`; retaining it locally does not imply raw material has been publicly published.

The professor can see a working reviewed-control mechanism and inspect its limits. The strict first-pass result is a negative finding for current autonomous reliability, especially profile replacement and single-operation requests. No source, prompt, model or validator was adjusted in response to this bank. It is now exposed and must not be reused to claim a future unseen test. Human relevance, universal language capability and LLM superiority remain unestablished. Personal code understanding, final feedback, presentation and submission cannot be certified by this execution.
