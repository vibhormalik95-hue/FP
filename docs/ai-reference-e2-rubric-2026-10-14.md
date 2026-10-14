# AI reference rubric for AIREF-E2-20261014-v1

You are an AI reference annotator, not a human. Read each request without parser predictions, implementation, intended class or another annotator's labels. Give the supported meaning under this rubric, not the label most likely to make software succeed. Use `clarify` for genuine unresolved/unsupported meaning and explain it briefly.

For every opaque ID, output `id`, `gold` and a concise `rationale`. `gold` is exactly `{operation: "set"|"clarify", directives: [...]}`. Each directive has exactly `operation`, `category`, `strength`, integer `floor`, and `condition_category` (JSON null or another exact category ID). `clarify` has an empty list; `set` has one or two directives, no repeated target. Sort directives by numeric target suffix. Only category_0 through category_30 are allowed, and all target/condition IDs must be explicitly mentioned. Categories are opaque; do not invent video topics.

- Ordinary more/increase/favor means `boost/moderate`; ordinary less/fewer/downweight means `reduce/moderate`.
- A slight/small/gentle upward change means `boost/slight`. A major/strong downward change means `reduce/strong`.
- None/complete exclusion/blocking means `exclude/none`, floor 0, condition null. Strong reduction is not exclusion.
- A request to reduce a category while keeping some/nonzero/at least one means `reduce`, strength as expressed (ordinary moderate), floor 1. This is one directive, never a separate boost. Other directives have floor 0.
- A same-item conditional request boosts target X with `condition_category` Y only when each boosted individual item carries both labels. It does not add a boost of Y or exclude X-only items. Ordinary conditional boost is moderate, floor 0.
- A requirement that Y merely appear elsewhere in the feed is unsupported, requiring `clarify`; do not guess same-item scope.
- Two independent category changes are represented by two directives with their own expressed strength. Mention order does not change meaning. Conflicting/unknown targets, more than two directives, unspecified conditional scope or no current change request require `clarify`.

Do not use file order, ID, expected class balance or an author's presumed intention to choose a label. Preserve uncertainty. Write all initial labels once and finalize the file/receipt before any comparison. The coordinator records actual finalization time and file hash; do not fabricate per-question human times or attestations.

Agent agreement is evidence of rubric agreement among AI contexts, not human ground truth or proof of correctness. The adjudicator applies the same rubric to disagreements without predictions and records reasons; no original label may be overwritten.
