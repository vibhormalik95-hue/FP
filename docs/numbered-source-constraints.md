# Numbered criteria and literal source requirements

The literal-witness check in `feedctrl/source_constraints.py` extracts digit-bearing
terms from the objective and reviewed definition. These are necessary text witnesses,
not semantic evidence. Source presence does not establish truth, and absent facts,
classifier/audit disagreements and primary unknowns still cannot become positives.

## Narrow formatting exception

The corrected revision ignores only label occurrences in a complete list of this form:

`all three of: (1) an object ...; (2) that object ...; and (3) the object ...`

The supported grammar requires all of the following after the existing Unicode
NFKC/casefold normalization:

- The explicit introduction `all N of:` or `all N conditions:`, where N is a word
  from `two` through `ten`. No other introduction wording is inferred.
- Exactly that many parenthesized integer labels, consecutively starting at `(1)`.
- Top-level semicolons between clauses, with optional `and` after a semicolon.
- Each label followed by whitespace, then `a`, `an`, `the`, `that`, `each`, `every`,
  `its` or `it`, then whitespace and an ASCII letter starting the clause text.
- The introduction, labels and separators are outside quotes, backticks and
  parenthesized/square-bracketed/braced text. Quoted or embedded list-shaped text
  stays literal. Quoted/bracketed semicolons cannot complete an outer list.
- There are exactly N minus one top-level semicolons before the next independent
  introduction or end of input. Any additional top-level semicolon leaves the
  entire candidate list unchanged, even a trailing semicolon, an empty clause,
  commentary or a decimal/other malformed extra label.
- Delimiters are balanced and unambiguous for the simple scanner. Unmatched or
  mismatched quotes/brackets and multi-backtick spans/fences disable the exception
  for that input. Apostrophes inside words such as `item's` and `isn't` do not open
  quotes. This is not a complete Markdown, programming-language or prose parser.

Only those specific label spans are masked in a temporary normalized copy used for
term extraction. The objective, definition, original response, prompt, source text,
quotes and receipts are not modified. A factual `1`, `2` or `3` elsewhere survives,
including the same number inside a clause, a quantity, rating, date, ID or version.
The source-witness matcher and result schema are unchanged.

This is a deliberately limited formatting rule, not a general parser or a proof of
meaning. Isolated `(1)`, numbered values/units, uncued lists, numeric counts such as
`all 3 of:`, comma-separated lists, nonconsecutive/duplicate/incomplete labels,
leading-zero labels, decimal labels and unsupported wording stay fail-closed. Their
numbers remain literal requirements, potentially causing withholding. The code does
not attempt to repair ambiguous lists or infer what a number means.

The first candidate failed independent review: it stripped digits from required
quoted text, allowed a quoted separator to complete an incomplete list, and accepted
valid-looking prefixes before empty or decimal extra clauses. One authored audit
fixture consequently lost numeric gating. The corrected revision covers those exact
failures plus related quote/bracket/delimiter cases. Original failure receipts remain
preserved separately; the initial candidate is not an accepted fix.

## Observed defect and verification scope

The retained 11 November Fable definition used the exact three-clause structure
above. The old extractor declared `1`, `2` and `3` as required factual terms, although
none of the eight captions contains these standalone digits. The real application
stopped earlier for competing alternatives, before classification. This fix addresses
a verified source-level, predictable downstream blocker, not an observed model
classification failure or a newly successful live run.

`tests/test_numbered_source_constraints_offline.py` retains the exact definition and
captions for an extraction regression, with their source SHA-256. Separate authored
fixtures exercise the existing staged membership and audit functions. They check
that factual numeric restrictions still withhold matches, primary unknown/negative
rows cannot become positive, disagreement still withholds and review remains
mandatory. A deliberately wrong agreement on negated text remains explicitly marked
as unverified semantic truth. These fixtures are software tests, not model evidence.

From the source root, using already available dependencies:

```sh
python -B tools/hosted_validation/run_guarded.py . test_numbered_source_constraints_offline test_review_state_labels_offline test_evidence_context_offline
```

No provider, trained scorer, native process runner, browser, network request,
installation, research study, publication or source transfer is part of this fix.
Historical results and research files remain unchanged. Any candidate release needs
fresh release manifests and independent review; the copied manifest still identifies
the base source and is not a checksum for these new candidate files.

## Counted conditions introduction

The later retained definition used `all three conditions: (1) ...; (2) ...; and
(3) ...`. The previous scanner recognized only `all three of:`, so the actual
extractor retained the three label digits. The successor adds only `conditions`
as an alternative introduction word. No marker, quote/bracket, separator,
conjunction or fallback rules change. The latest run stopped before classification
because definition evidence review was declined; this is an extraction regression,
not evidence of a live classifier failure or success.

`tests/test_counted_conditions_offline.py` retains the exact latest objective and
definition, and exercises malformed syntax and factual-number preservation.

## Apostrophes and ambiguous single quotes

In-word apostrophes are treated consistently inside and outside active quotes. A trailing apostrophe after a word may be a possessive or a single-quote delimiter. In that ambiguous context, structural-number masking is disabled for the input and all digit-bearing terms remain requirements. This deliberately can withhold a valid list containing a single-quoted body such as `'ready'`. Ordinary contractions in unquoted list bodies and unambiguous double-quoted bodies retain existing behavior. This conservative boundary does not infer semantic truth or discard factual digits.
