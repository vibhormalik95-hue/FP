# Experiment 2 runbook

This runner writes only new directories inside `results/experiment2/`. It does not train or edit Experiment 1. Development results, synthetic software tests and reserved-test findings have separate statuses. A blocked test is not a passed study.

## Development and its recorded evidence

Use the project environment and a running local Ollama server containing `llama3.1:8b`:

```bash
.venv/bin/python scripts/run_experiment2.py --stage dev --output results/experiment2/development-next --num-thread 6 --timeout 600
```

If a server is not running, the existing wrapper can supply one:

```bash
.venv/bin/python scripts/with_ollama.py --models /tmp/ollama-models -- .venv/bin/python scripts/run_experiment2.py --stage dev --output results/experiment2/development-next --num-thread 6 --timeout 600
```

The default per-request timeout is 600 seconds. The v2 development run used this setting because the first cold CPU request took about 185 seconds. This is a development-based runtime allowance, not a change made after reserved outcomes. Use the same frozen settings for the subsequent full freeze and test.

Use a different output name for every authorized development run. The runner refuses a nonempty destination. A startup Ollama failure stops the stage; no rule-only replacement is presented as an LLM run. Individual parser errors are retained in the complete 48-case denominator for each parser.

Each run records policy/source hashes before inference, exact cases, per-case results, raw LLM request/response caches, accuracy and a terminal manifest containing hashes and timings. New executions also save source-file copies in `source_snapshot/`. The first development run began before this source-copy feature: its historical evaluator and runner hashes identify the implementation loaded at that time, but those exact historical source copies were not retained. Do not describe that run as execution of a later evaluator or runner. Its unchanged parser source and recorded raw parser outputs still support independent outcome recomputation.

The first development execution is complete and retained in `development-v1/`. Its parser failures are recorded outcomes, not discarded cases. The revised-bank execution is retained separately in `development-v2/`. A run is replayable only after all 48 outcomes per backend and its terminal `manifest.json` exist; the runner never reconstructs or invents a completion manifest for an ongoing run.

Development replay requires no Ollama process and does not open the reserved bank:

```bash
.venv/bin/python scripts/run_experiment2.py --stage replay --cache-run results/experiment2/development-v1 --output results/experiment2/development-replay-v1
```

This recomputes exact-match summaries from the original complete per-case cache after verifying the original manifest inventory. It makes no new parser or ranking calls. It does not count as reserved-test replay.

## Human evidence that blocks the reserved experiment

The returned CSV must retain these columns:

`annotation_id,text,operation,directives_json,annotator,timestamp_utc`

The student completes all 100 commands independently, identifies themselves in every row and includes timezone-aware timestamps. Student row and receipt timestamps must be no later than adjudication, and adjudication must be no later than the full freeze. Final adjudicated category references must belong to the frozen catalogue before freeze can succeed. Blind display IDs map to canonical case IDs through `language-v2/annotation-id-map.json`. Empty fields, generated substitute labels, partial passes, generic identities such as `student`, mismatching wording or missing attestations cannot fulfill the gate.

The parser-only commitment is mandatory before the earliest student annotation, including every row timestamp and the receipt timestamp. Preserve that commitment and both original annotation passes. Human annotation and adjudication are distinct authorized accesses to the reserved material; parser developers must not use that material to tune the parser. The full `freeze` stage below additionally freezes the completed human evidence before test inference.

For this current study, use the already packaged `results/experiment2/parser-freeze-v2.json` receipt with `results/experiment2/language-v2/`; these are the CLI defaults. Do not recreate the current parser freeze. The selected receipt must still match the final v2 parser and language hashes before full freeze can pass. The preserved v1 commitment and first v1 development run describe the historical draft; they are not a substitute for the v2 commitment. Do not overwrite any commitment, alter its timestamp or recreate it after annotations to claim a prior freeze. Only for a separate, explicitly authorized future prospective commitment, before any annotation, use a genuinely new directory such as the illustrative `parser-only-next` below. Do not run this to replace the packaged current-study receipt:

```bash
.venv/bin/python scripts/run_experiment2.py --stage parser-freeze --output results/experiment2/parser-only-next
```

The future-study example writes `parser-only-next/parser-commitment.json`, hashes the reserved bytes without loading their text, needs no Ollama process or human receipt, and refuses an existing test-opening marker. To use this newly created record, supply `--parser-commitment results/experiment2/parser-only-next/parser-commitment.json` on full freeze, test and test replay. A new commitment gets the actual new timestamp; it never borrows an earlier record's timestamp.

Full freeze requires the selected commitment file and verifies its parser-module hash, complete prompt/schema/rule policy, development-bank hash and reserved commitment against the current artifacts. Its timestamp must be no later than the earliest student row or receipt. The record itself is included in the full frozen artifact inventory. These checks remain valid after exact-byte relocation; missing, altered, stale-policy or post-annotation commitments are rejected.

The first genuine student-only receipt JSON must contain the fields below. It must not yet contain adjudication, final-gold or agreement-record fields:

| Field | Required content |
| --- | --- |
| `annotator_identity` | Actual student's name or identifying institutional identity, matching every CSV row |
| `annotated_utc` | Timezone-aware timestamp |
| `student_attestation` | `true`, explicitly supplied by the student |
| `independent_annotation` | `true` |
| `no_model_outputs_seen` | `true` |
| `student_annotations_sha256` | SHA-256 of the returned original CSV bytes |
| `source_test_sha256` | Public committed reserved-bank SHA-256 |
| `case_ids` | All 100 canonical IDs, exactly once |

After the student pass and before adjudication, run the annotation-only comparison using that original receipt:

```bash
.venv/bin/python scripts/run_experiment2.py --stage compare-annotations --student-annotations /path/to/returned-student.csv --student-receipt /path/to/student-only-receipt.json --output results/experiment2/annotation-comparison-v2
```

This stage validates all 100 student rows, exact IDs, identity, timestamps, original source hashes and explicit independent/student/no-model-output attestations. It verifies that the matching parser commitment precedes the earliest annotation. It records actual first access in `language-v2/annotation.opened.json` and each attempt in `language-v2/annotation-attempts/`, then reads the bank solely for this authorized annotation comparison. The original author IDs and classes must exactly match the public manifest. Only after wording validation and agreement computation succeed does it create the singleton `language-v2/annotation.completed.json`, write the successful finished-attempt record, and finally commit the transaction in the output's `annotation-commit.json`. An agreement file alone cannot satisfy the human gate. It creates no evaluation-opening marker and makes no Ollama, parser-inference, scoring or ranking call. A final receipt already containing adjudication fields is refused.

The output `agreement-before-adjudication.json` contains actual full-command and directive-count agreement with explicit numerators and denominators, kappa, aligned field agreement, disagreements with both original labels, exact preserved source and student bytes, and the original student-only receipt. A separate evaluation opening still occurs only after adjudication and full freeze. There is no actual agreement result while the real student pass is missing.

The markers have distinct meanings:

| Record | Meaning |
| --- | --- |
| `annotation.opened.json` | Immutable first actual annotation access and its timestamp; never removed or replaced after a failed wording check |
| `annotation-attempts/ID-started.json` | Immutable sequential attempt number, inputs, original CSV/receipt bytes, command labels and pinned parser/bank hashes |
| `annotation-attempts/ID-finished.json` | Immutable success or failure outcome; wording-validation failures explicitly record whether retry is allowed |
| `annotation.completed.json` | Singleton successful comparison; once present, further comparison attempts are rejected |
| Output `annotation-commit.json` | Final successful transaction proof, written after the marker and finished record; binds the exact agreement, first marker, completion marker and complete journal bytes |
| `annotation-attempts/ID-commit-failed.json` | Permanent nonretryable evidence if the transaction fails after its successful finished record was written |
| `annotation.in-progress.json` | Exclusive temporary process lock; normal completion or a caught validation failure releases it |

A wording mismatch may fail after authorized annotation access but before IAA exists. Keep the failed CSV, receipt, attempt records and original opening unchanged. A corrected new CSV and student-only receipt may retry into a fresh output only when the recorded failure is a retryable wording-validation failure. Supply its exact finished-attempt path and an explicit correction reason:

```bash
.venv/bin/python scripts/run_experiment2.py --stage compare-annotations --student-annotations /path/to/corrected-student.csv --student-receipt /path/to/corrected-student-only-receipt.json --retry-annotation-attempt results/experiment2/language-v2/annotation-attempts/FAILED_ATTEMPT_ID-finished.json --annotation-correction-reason "Restore the exact worksheet wording after a transport error; command labels are unchanged." --output results/experiment2/annotation-correction-01
```

Replace `FAILED_ATTEMPT_ID` with the actual latest failed attempt reported by the runner. It validates every current start/finish pair in sequence; selecting an older retryable failure cannot bypass a newer attempt. A missing finish, orphan record, intervening nonretryable failure, completed attempt or unknown journal record blocks retry. Retry requires identical canonical command labels, case IDs, annotator, parser commitment, parser bytes, language bank, public manifest and ID map. It may correct worksheet wording or transport, not silently replace labels or change the parser. The successful agreement record embeds the original failed-pass evidence and first-access record. A changed label, completed comparison or evaluation-opening marker blocks retry. Other failures and interrupted attempts with a surviving process lock fail closed; this runner does not automatically delete a lock or invent a completed attempt. No annotation attempt creates a test/evaluation-opening marker or calls an LLM or scorer.

Use the preserved successful comparison to adjudicate disagreements without model outputs. A genuine adjudication JSON must contain:

| Field | Required content |
| --- | --- |
| `adjudicator_identity` | Actual responsible person's identity |
| `completed_utc` | Timezone-aware timestamp |
| `disagreements_resolved` | `true` after actual resolution |
| `blind_before_model_outputs` | `true` |
| `original_annotations_preserved` | `true` |
| `source_test_sha256` | Same reserved commitment |
| `student_annotations_sha256` | Same original CSV hash |
| `final_gold` | All 100 records, each `{id, gold, reason}` |

After adjudication, create a separate final receipt supplement, preserving every original student-only field unchanged and adding:

| Added field | Required content |
| --- | --- |
| `adjudication_sha256` | SHA-256 of the completed adjudication JSON bytes |
| `final_gold_sha256` | Canonical hash described below |
| `agreement_record_sha256` | SHA-256 of `agreement-before-adjudication.json` |
| `student_only_receipt_sha256` | SHA-256 of the preserved original student-only receipt bytes |

Keep the original receipt file unchanged. The final receipt is a separate file supplied at full freeze, evaluation and reserved-test replay. The gate recomputes IAA from the preserved original source and annotations, checks their byte hashes against the committed bank and returned CSV, verifies the original attestations, and requires parser commitment <= original student completion <= first annotation access <= attempt <= completed comparison transaction <= adjudication <= full freeze. The embedded first-access record must exactly equal the actual preserved marker, including its timestamp and byte hash. The gate checks the current public manifest and ID-map bytes against the comparison anchors before full freeze or evaluation opening. Missing, changed, invented or post-adjudication agreement records fail the gate.

Keep `annotation-commit.json` beside `agreement-before-adjudication.json`, and retain the first marker, completion marker and entire attempt journal beside the selected reserved bank. Downstream gates require all these records to match; a failure to write the completion marker, successful finished record or final commit leaves any agreement file unusable. A surviving process lock beside the current bank also blocks the human gate and full freeze, including when final lock cleanup failed after the commit proof was written. No partial transaction is automatically repaired or retried. Exact-byte relocation is supported: the runner finds the state beside the current `--test` path and the commit beside the current `--agreement-record`, while old absolute paths inside records remain provenance only.

Final consensus must also fit the committed case's prespecified ranking class before the study can reach full freeze:

| Committed class | Supported final command form |
| --- | --- |
| `compound` | Exactly two directives on distinct targets: `boost/moderate` and `reduce/moderate`; both floor `0`, condition `null` |
| `graded` | Exactly one directive: `boost/slight`, `reduce/strong`, or `exclude/none`; floor `0`, condition `null` |
| `floor` | Exactly one `reduce/moderate` directive; floor `1`, condition `null` |
| `conditional` | Exactly one `boost/moderate` directive; floor `0`, with a non-null distinct condition category |

These forms come from the fixed interpretation rubric and metric definitions. Unknown classes, `clarify` final consensus and other directive shapes produce a blocking report containing every affected case ID, committed class and reason. The same check runs before assignment, so no unsupported case disappears from the selection pool and no convenient replacement is selected. The code never rewrites human labels or relabels classes. Preserve the adjudication and make an explicit prospective study-design decision if this occurs; do not coerce agreement merely to pass the gate.

Independent students remain free to use `clarify` honestly: the annotation-comparison stage accepts it and retains the case in all relevant agreement denominators. Parser predictions can also clarify or fail and remain recorded outcomes. The new block concerns unsupported final consensus for a ranking metric, not independent annotation or model correctness.

Every final record needs an agreement or resolution reason. `gold` uses the protocol's strict command schema. `final_gold_sha256` is `feedctrl.experiment2_evaluation.fingerprint([{ "id": i, "gold": canonical_gold_i } for i in sorted_case_ids])`; commands are canonicalized with numeric category order. Hashes establish artifact identity, not a person's identity. The runner checks complete evidence and explicit human attestations and cannot independently authenticate a person. Never generate a fictitious receipt to pass this gate.

The annotation-comparison stage computes agreement before adjudication. Full freeze verifies that computation, and evaluation repeats it as a consistency check after its separate authorized single opening. The runner reports undefined kappa as null, verifies exact student wording and uses the adjudicated gold only for the later parser/ranking evaluation. Field comparisons align the union of target category IDs within each case; a missing directive counts as a disagreement for every field. The output supplies field agreement numerators and their common target-comparison denominator, plus separate top-level operation and exact target-set agreement. Full-command exact agreement and directive-count agreement each expose their own matching-case numerator and all-case denominator. Directive-count kappa treats 0, 1 and 2 directives as unweighted categories; it is null when expected agreement is one. With no directives to compare, field agreement is null rather than perfect agreement. No IAA number exists while annotations are absent.

## Full freeze, then single reserved-test execution

The required order is parser commitment, independent student-only receipt, annotation comparison, blind adjudication, final receipt supplement, full freeze, then evaluation. Provide the same completed human and comparison paths at freeze, test and test replay. The following placeholders represent real returned files, not files the runner creates:

```bash
.venv/bin/python scripts/run_experiment2.py --stage freeze --student-annotations /path/to/returned-student.csv --student-receipt /path/to/final-student-receipt.json --adjudication /path/to/adjudication.json --agreement-record results/experiment2/annotation-comparison-v2/agreement-before-adjudication.json --output results/experiment2/freeze-v1
```

Freeze records the prior parser-only commitment, exact parser module, prompt, schema, rule version, evaluator, runner, imported Experiment 1 utilities and model implementation, protocol, development bank, reserved commitment, data, all three model files and metadata, public language manifest, blind ID map, student CSV, final receipt, prior agreement record, successful annotation-commit proof and adjudication. It also freezes parser options, Ollama version and model digest. It reads the reserved file only as bytes for SHA-256, not as text cases.

```bash
.venv/bin/python scripts/run_experiment2.py --stage test --freeze-receipt results/experiment2/freeze-v1/freeze-receipt.json --student-annotations /path/to/returned-student.csv --student-receipt /path/to/final-student-receipt.json --adjudication /path/to/adjudication.json --agreement-record results/experiment2/annotation-comparison-v2/agreement-before-adjudication.json --output results/experiment2/test-v1
```

The runner verifies every frozen logical artifact and hash and the live Ollama provenance before the opening. It atomically creates `language-v2/test.opened.json` with exclusive creation. A second opening is rejected. Each of the 100 exact utterances is parsed once by each parser, then reused across users and seeds. Accuracy is saved and printed before any model loading, scoring or ranking.

All assigned requests retain all four channels and all three seeds. Individual parser errors produce the unchanged baseline as no new control, remain errors and stay in the denominator. All three frozen SASRec checkpoints must have matching seed and train-cohort provenance. Band attainment, baseline band attainment and induced satisfaction each have separate channel-by-class and pooled descriptive tables with user aggregates, user counts, assigned-request counts and request-seed row counts. Signed intended movement, floor violations, infeasible assignments and conservative no-directional-opportunity flags are recorded. Every H3 contrast also reports its number of nonzero paired user differences. H1 and H2 use the complete prespecified 11-test BH family; H3 is descriptive and has no noninferiority conclusion.

## Reserved-test replay and interruptions

```bash
.venv/bin/python scripts/run_experiment2.py --stage replay --cache-run results/experiment2/test-v1 --freeze-receipt results/experiment2/freeze-v1/freeze-receipt.json --student-annotations /path/to/returned-student.csv --student-receipt /path/to/final-student-receipt.json --adjudication /path/to/adjudication.json --agreement-record results/experiment2/annotation-comparison-v2/agreement-before-adjudication.json --output results/experiment2/test-replay-v1
```

Test replay verifies the same human gate and every frozen artifact by logical label and bytes (relocation is allowed, and original paths remain provenance), then verifies the original run's complete file inventory. It recomputes parser summaries and analysis from recorded commands and ranking rows. It never invokes a parser, loads a model or creates missing ranking evidence. It requires no Ollama process. A missing, modified or incomplete parse cache blocks replay; missing ranking rows yield an explicit incomplete-evidence status. An interrupted test must not be reopened or silently rerun with changed code. Preserve the opening flag and all evidence. If no terminal manifest survived an interruption, this version fails closed rather than reconstructing a receipt retrospectively.

The terminal manifest identifies execution errors separately from the hypothesis results. A parser error exit code does not remove cases or invalidate an unfavorable measured outcome. No ranking rows means H1/H2 are not assessed. No quality threshold gates whether results are saved.

## Synthetic software checks

```bash
.venv/bin/python -m pytest tests/test_experiment2_controls.py tests/test_experiment2_evaluation.py -q
```

These tests use independent synthetic fixtures, including explicitly synthetic 100-case human-gate records, three fixture scorers, immutable replay and poisoned held-out labels. Their artificial identities and labels remain temporary test data and never satisfy the real study's human annotation prerequisite. Passing these checks demonstrates software behavior, not support for H1, H2, H3 or completed reserved-test replay.
