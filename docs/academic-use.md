# Research provenance and limits

The study compares language translation, deterministic category enforcement and historical next-item ranking on a fixed short-video cohort. [Experiment 1](evaluation-protocol.md) uses frozen model scores and canonical requests. The completed [fresh Experiment 2](ai-reference-e2-protocol-2026-10-14.md) uses 100 synthetic requests and model-generated reference commands; the [earlier exposed practice run](execution-2026-10-14.md) is reported separately.

Two passes using the same model family generated the initial fresh E2 references and agreed on all 100 commands. Vibhor Singh Malik reports completing the original 100-question worksheet himself and submitting his responses on 20 October without seeing reference answers. Applying the study's existing annotation rules, his responses matched 99 of the 100 initial AI-authored labels. His original submission is preserved. This is a descriptive student-versus-AI comparison, not agreement between independent human annotators.

The original human-reference evaluation still lacks an adjudicated human reference set and its planned parser and ranking analysis. The worksheet did not record exact completion times, and earlier accounts of exposure to development summaries remain unresolved. No participant study is available. Synthetic wording, opaque category IDs and a historical next-item proxy limit claims about real user understanding, trust, satisfaction and recommendation quality.

## Comparison with the earlier proposal

The supplied COMP 9080 proposal was an unsigned draft with a different human-reference design. Its 85% parser target was missed by the frozen 79/100 broader-set result. Its top-1 hit-rate non-inferiority threshold of 10% did not specify an absolute or relative margin. The observed A baseline was 0.00250481696; ten percent of it is 0.000250481696. The simultaneous lower bound for C/D/E minus A was approximately -0.0007707129. It exceeds an absolute -0.10 margin but not the relative -0.000250481696 margin. This is a post-outcome interpretation of an ambiguous draft threshold, not a prospective non-inferiority result.

Experiment 1 results, model checkpoints, prompts, labels and `data/parser_test.jsonl` remain frozen. The public repository holds compact summaries and evidence receipts; the larger research archive holds raw study records. KuaiRec upstream data and Llama weights are not redistributed. See [third-party notices](../NOTICE.md) for attribution.
