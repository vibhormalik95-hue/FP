# Research provenance and limits

The study compares language translation, deterministic category enforcement and historical next-item ranking on a fixed short-video cohort. [Experiment 1](evaluation-protocol.md) uses frozen model scores and canonical requests. The completed [fresh Experiment 2](ai-reference-e2-protocol-2026-10-14.md) uses 100 synthetic requests and model-generated reference commands; the [earlier exposed practice run](execution-2026-10-14.md) is reported separately.

Two passes using the same model family generated the initial fresh E2 references and agreed on all 100 commands. Vibhor Singh Malik reports completing the original 100-question worksheet himself and submitting his responses on 20 October without seeing reference answers. Applying the study's existing annotation rules, his responses matched 99 of the 100 initial AI-authored labels. His original submission is preserved. This is a descriptive student-versus-AI comparison, not agreement between independent human annotators.

The original human-reference evaluation still lacks an adjudicated human reference set and its planned parser and ranking analysis. The worksheet did not record exact completion times, and earlier accounts of exposure to development summaries remain unresolved. No participant study is available. Synthetic wording, opaque category IDs and a historical next-item proxy limit claims about real user understanding, trust, satisfaction and recommendation quality.

## Separate exploratory parser comparison, 20 October 2026

After the student responses and initial model references had been compared, a separate parser-only analysis was specified before new inference. It used the unchanged, rubric-encoded student responses and frozen parser settings. On the same 100 synthetic requests, Llama 3.1 8B matched **73/100** complete commands and the rule parser matched **18/100**. All **200** parser attempts are recorded, with one attempt per parser and request and no retries. Llama produced **24** validation failures, including 23 conditional-grounding failures and one invalid floor; failures remained in the 100-case denominator. Comparison with the initial model-written labels gave the same aggregate scores because both parsers missed the one case on which the two label sets differ.

The exact request texts had already appeared in the earlier exposed practice run, so this is not an unseen-language test. It was specified after the student's labeling and a descriptive opening of the initial references, so it is not the original preregistered human-reference evaluation. No ranking, category-control or user-preference measure was run in this comparison. Neither label set nor the parser was changed to resolve the disagreement.

The specification was frozen at 23:46:26 UTC, predictions at 23:50:13 UTC, and scoring completed at 23:50:24 UTC on 20 October. The private evidence archive contains the specification, question-only input, 200 attempt records, 200 results, 100 raw model responses and scoring record. The following SHA-256 values identify the saved inputs and outputs without publishing student answers or reference labels:

| Record | SHA-256 |
| --- | --- |
| Specification | `38e3306f68e68dad4895ea218cb92f4a335b872156db2702ab2a44a6b3652538` |
| Question-only input | `5f55e342a53214f43a7073ba16e775f8470826d9582e932adedba505ba3c038d` |
| Unchanged student submission | `8d2b5918ad678a5e5ee2a660d5bcacbd2a3daf2d649e5885cbf7951e0d5b7e40` |
| Rubric-encoded student responses | `1494509ebb2c98064e5ae724fbbc1c0b17519384daae4b6f89d674ad99a8b26f` |
| Frozen `feedctrl/experiment2_controls.py` source (LF line endings) | `2566f41a94770a2a2904fda35262fc0d8d6f4be0a6b47879d1b0da452b18a8b6` |
| Prediction freeze | `8b6912354549884985186e6951f47b2490abace02dd4c27ff0d679ba00d47427` |
| Scoring summary | `6c20d866128de6733d6626ddd04badff740501da64cbafefdf1349a238fbc3bf` |
| Private evidence archive | `60eddfaab12ca265b675884a0a7c8d5f66f23080adb104af920c740eb4955787` |

Study ID: `E2-STUDENT-EXPLORATORY-20261020-v1`. The local model digest was `46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e` under Ollama 0.34.0, with temperature 0, seed 42, context 4096 and prediction limit 768. These results add a documented exploratory parser comparison; they do not complete the original protocol's pending adjudication or ranking study.

## Comparison with the earlier proposal

The supplied COMP 9080 proposal was an unsigned draft with a different human-reference design. Its 85% parser target was missed by the frozen 79/100 broader-set result. Its top-1 hit-rate non-inferiority threshold of 10% did not specify an absolute or relative margin. The observed A baseline was 0.00250481696; ten percent of it is 0.000250481696. The simultaneous lower bound for C/D/E minus A was approximately -0.0007707129. It exceeds an absolute -0.10 margin but not the relative -0.000250481696 margin. This is a post-outcome interpretation of an ambiguous draft threshold, not a prospective non-inferiority result.

Experiment 1 results, model checkpoints, prompts, labels and `data/parser_test.jsonl` remain frozen. The public repository holds compact summaries and evidence receipts; the larger research archive holds raw study records. KuaiRec upstream data and Llama weights are not redistributed. See [third-party notices](../NOTICE.md) for attribution.
