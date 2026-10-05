# Experiment 2 language annotation rubric

Revision 2, 29 September 2026 UTC: use the v2 worksheet. A cold audit found that some development conditional wording could mean feed-level presence. The independent author corrected conditional wording in a separate v2 bank to require both labels on each boosted item, before any reserved inference. The original v1 bank and gold remain preserved; no gold label was changed and no model test outcome informed this revision.

## Purpose and authorship

This experiment evaluates interpretation of short category-preference requests. The corpus is AI-authored synthetic material, not a human language study. It contains 48 development cases and 100 reserved test cases. The four intended language classes are compound, graded, floor, and conditional. Development contains 12 of each class; reserved test contains 25 of each class. Every split references all 31 opaque category identifiers.

The first gold annotation was produced by the independent corpus author. It is an initial annotation, not established human ground truth. A student must independently annotate the reserved cases before inter-annotator agreement or final adjudicated accuracy can be reported. The student pass is pending. A second AI pass does not fulfil this requirement, and blank annotation fields must never be treated as completed labels.

The corpus author did not inspect the parser implementation or the earlier parser test file and did not run parser predictions. The development wording and reserved wording are distinct. Results on these synthetic examples should not be described as evidence of performance on naturally collected user requests.

## Files and the procedural seal

- `results/experiment2/language-v2/dev.jsonl` contains the development text and first gold labels. It is available to the parser author for development.
- `results/experiment2/language-v2/test.sealed` contains UTF-8 JSONL bytes with the reserved text and first gold labels. The seal is procedural, not encryption. Its SHA-256 is recorded in `commitment.json` and must be verified before use.
- `commitment.json` records split counts, category coverage, authorship, annotation status, and hashes without exposing reserved utterances.
- `reserved-test-manifest.json` exposes canonical case IDs and class labels only. It contains neither utterances nor gold directives and can be read by the evaluation pipeline author.
- `annotation-id-map.json` maps anonymous display IDs to canonical test IDs. It contains no utterances or gold labels.
- `COMP9500-Experiment2-Student-Annotations-v2.csv` is the student worksheet. Its 100 cases and display-ID row order are randomized. It contains text but no first-gold labels or parser output.

The parser author must not read `test.sealed`, the student worksheet text, or equivalent reserved text before both a parser freeze and an independent student annotation pass have been recorded. The student sees only this rubric and the blank worksheet, plus any separately authorized development calibration material. The student must not see first gold, parser implementation, predictions, or accuracy summaries during the independent pass.

Do not modify the committed reserved corpus in response to parser outcomes. Preserve the original file and hash if an adjudication later corrects a first-gold interpretation. Store final adjudicated labels as a separately versioned file with their own hash and an audit record.

## Output schema

For each request, produce this JSON object:

```json
{
  "operation": "set",
  "directives": [
    {
      "operation": "boost",
      "category": "category_0",
      "strength": "moderate",
      "floor": 0,
      "condition_category": null
    }
  ]
}
```

The example illustrates schema syntax only and is not a reserved-case answer.

Top-level fields:

| Field | Allowed values | Meaning |
| --- | --- | --- |
| `operation` | `set`, `clarify` | `set` means a supported preference change can be represented; `clarify` means the request cannot be safely resolved under this rubric. |
| `directives` | JSON array with at most two objects | Requested changes. Use an empty array for `clarify`; a `set` output must have one or two directives. |

Every directive contains all five fields:

| Field | Allowed values | Meaning |
| --- | --- | --- |
| `operation` | `boost`, `reduce`, `exclude` | Increase preference, decrease preference, or remove the category. |
| `category` | Exact identifier from `category_0` through `category_30` | The category whose preference changes. |
| `strength` | `slight`, `moderate`, `strong`, `none` | Magnitude of the adjustment. `none` is reserved for exclusion. |
| `floor` | Integer `0` or `1` | `1` requires a nonzero presence, represented as a minimum of one item. `0` imposes no minimum; it is not a command to remove the category. |
| `condition_category` | `null` or exact valid category identifier | A category that must also be present on the same recommended item for this directive to apply. |

Identifiers are opaque labels. Do not infer themes, similarity, or category relationships from their numeric suffixes. Preserve the exact underscore spelling. Strings, booleans, or fractional values are not valid substitutes for integer floors. Use JSON `null`, not the string `"null"`.

## Interpretation rules

| Language class | Intended interpretation |
| --- | --- |
| Compound | More X and less Y yields two directives: `boost` X with `moderate`, and `reduce` Y with `moderate`. Both have floor `0` and condition `null`. Mention order does not change meaning. |
| Graded: slight more | A bit, a little, slightly, a small increase, or a comparable minor upward adjustment yields `boost`, strength `slight`, floor `0`, condition `null`. |
| Graded: strong less | Much less, substantially fewer, a large reduction, or a comparable major downward adjustment yields `reduce`, strength `strong`, floor `0`, condition `null`. |
| Graded: none | No X, none of X, exclude X, or complete removal yields `exclude`, strength `none`, floor `0`, condition `null`. |
| Floor | Less X but not zero, retaining some X, not eliminating X, or keeping at least one X yields `reduce`, strength `moderate`, floor `1`, condition `null`. |
| Conditional | More X only when each boosted item itself has both the X and Y labels, or equivalent same-item wording, yields one `boost` directive for X with strength `moderate`, floor `0`, and `condition_category` Y. It does not create a separate boost directive for Y. |

Simple unqualified more or less uses `moderate`. Exclusion is distinct from a strong reduction. A requirement that some of a category remain is floor `1`, even when the wording does not literally mention the number one. A condition requires the same recommended item to have both category labels. A condition requiring Y merely somewhere else in the feed is a different, unsupported intent and must receive clarify under this schema. These are representational conventions for this experiment, not claims about the only possible semantics of English.

Annotate the supported intent of the full sentence. Do not guess from an ID, row position, anticipated class balance, or superficial keyword alone. If a request is genuinely unresolved under this schema, use `clarify` and an empty directives array, record the concern separately, and let blinded adjudication address it. No deliberately ambiguous or adversarial cases were intended.

## Category and structural validation

1. The only valid category strings are `category_0` through `category_30`, without zero padding.
2. A `set` label has one or two directives, and no target category may appear twice.
3. Each target category and each non-null condition category must be explicitly referenced by the text. A directive cannot condition on itself.
4. A compound request has two distinct targets; a conditional request has one target and a different condition category.
5. `exclude` always uses strength `none`, floor `0`, and condition `null` in this experiment. `boost` and `reduce` cannot use strength `none`.
6. Floor `1` is used only for `reduce` and preserves a minimum presence. The reserved floor class uses strength `moderate`.
7. The reserved conditional class uses `boost`, strength `moderate`, floor `0`, and a non-null condition category.
8. Do not add directives for categories merely serving as conditions. Do not add unrequested fallback actions or inferred preferences.
9. For serialization and exact-match comparison, sort directives by the target category's numeric suffix. Field order and whitespace inside JSON do not affect semantic equality.

## Student worksheet procedure

Each worksheet row contains `annotation_id`, `text`, `operation`, `directives_json`, `annotator`, and `timestamp_utc`. Preserve the ID and text. Read each case independently in the provided order. Fill `operation` with `set` or `clarify`, and enter only the directive array in `directives_json`. Populate `annotator` with your name or agreed study identifier and `timestamp_utc` with the actual completion time in ISO 8601 UTC form, such as `2026-09-29T14:30:00Z`. The example time is not a supplied completion timestamp.

The student may use JSON syntax checking and this rubric, but may not obtain replacement labels from the parser, a language model, or the hidden first annotation. Record annotation uncertainty in a separate notes file keyed by the display ID. Finish the independent pass before opening any first labels for adjudication. Retain an unchanged copy of the completed independent worksheet and its hash.

The pipeline may use `annotation-id-map.json` to convert completed rows to canonical records of the form `{"id":"e2-test-001","gold":{...}}`. This conversion changes identifiers and structure only; it must not invent missing annotations. Before conversion is accepted, verify there are exactly 100 unique annotation IDs and canonical IDs, all required annotation fields are complete, every directive validates, and there are no extra or missing cases.

Record the student's identity, actual annotation completion time, an explicit student attestation, the hash of the completed worksheet or converted independent labels, and the source test hash. A receipt is evidence only when supplied or confirmed by the actual annotator; software must not fabricate the student's attestation.

## Agreement, adjudication, and freezing

After the parser-only commitment and genuine student-only receipt, use `compare-annotations` as documented in `docs/experiment2-runbook.md`. It records an annotation-only opening, preserves both original passes and computes agreement before adjudication without model calls. Preserve its agreement record and the unchanged student-only receipt; after adjudication, add the required hashes in a separate final receipt supplement.

Compute agreement on the two independent annotation sets before adjudication. Both sets must cover the same 100 canonical IDs. Parse and validate JSON, normalize object field order, and sort directives as described above. Do not let parser predictions participate in annotation decisions.

Exact-match agreement is the number of cases whose entire normalized top-level operation and directive array agree, divided by the number of independently double-annotated cases. Report its numerator and denominator. Also report component agreement for top-level operation, directive count, target category set, directive operation, strength, floor, and condition category. For directive components, align by target category. A missing directive is a disagreement represented by a distinct missing label, rather than silently dropping that case. State the denominator used for each component.

Cohen's kappa may supplement raw agreement for categorical components, such as operation, strength, floor, and condition category. State the labels and units used, and calculate kappa as `(observed agreement - chance agreement) / (1 - chance agreement)`. If the denominator is zero because a component is constant across annotators, report kappa as undefined rather than inventing a value. Whole-record exact-match agreement is not itself Cohen's kappa.

Exact-match agreement, component agreement, and Cohen's kappa are currently uncomputable because the independent student pass has not occurred. Do not substitute the AI author's self-review or repeated model output for an independent student annotation.

After the independent pass, identify and document every disagreement. An adjudicator resolves disagreements using the text and this rubric while blinded to parser outputs and evaluation results. Preserve both original annotations, the final decision, a brief rationale, the adjudicator identity, and the actual adjudication time. All disagreements must be resolved before freezing the final adjudicated gold and before the first held-out parser run.

The parser implementation must first be frozen without access to reserved text. Record its commit or content hash and actual freeze time. Complete independent student annotation and blinded adjudication, then freeze the final gold artifact and its hash. Only after these gates are satisfied may the procedural test seal be opened for the held-out evaluation. The pipeline must fail closed when required student or adjudication evidence is missing. No reported test result may be presented as a final independently annotated result until these steps are complete.

## Unsupported final consensus

Your independent pass may truthfully use `clarify`; do not copy the first author's presumed class or change your judgment to satisfy a software gate. Agreement preserves that label. After blinded adjudication, final gold that is unclear or outside the committed class's supported metric form blocks full freeze and ranking with the affected IDs and reasons. The study must preserve the genuine consensus and make a prospective protocol/bank decision. It must not drop, relabel or replace cases silently or pressure an annotator to make a test executable.

If the worksheet wording was accidentally altered during transfer, preserve the failed files and access record. The runbook permits an explicit, logged correction attempt with unchanged command labels, annotator, parser and bank. It never permits changing labels after disclosure or repeating a completed comparison.
