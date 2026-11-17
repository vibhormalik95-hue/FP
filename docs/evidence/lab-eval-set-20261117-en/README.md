# English version of the frozen evaluation set (for the English-input re-run)

`cases.en.json` is derived from the frozen, human-reviewed set `../lab-eval-set-20261117/cases.frozen.json`
by `scripts/build_english_eval_set.py`, so that the models can be measured on the English text layer the
application now uses.

- Every label (required, acceptable, distractors) is mapped to its English label through the label map of
  the English text layer (`data/kuairec_text_en-v1.label-map.json`, release `comp9500-kuairec-english-v1`).
  The map gives one English label per original label, so every label's member set is unchanged.
- The 33 text fields that held Chinese (10 NL and 6 AB requests, AB reasons, 3 NC descriptions, labels and
  definitions) were machine-translated once by gpt-5-mini (the translator of the text layer), USD 0.006.
- Item ids, the 150-item pool, members, actions and expected statuses are unchanged. No case was edited by
  hand; this is preprocessing of the reviewed set, not a new review.
- `FROZEN-EN.json` holds the SHA-256 of `cases.en.json`, of the source set, of the label map and of the
  text layer. It was committed before any prediction of the English-input re-run.

Limit: a machine translation can shift the meaning of a request or a definition; the human review was made
on the original text.
