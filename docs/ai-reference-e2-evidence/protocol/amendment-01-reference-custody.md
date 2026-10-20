# Reference custody attempt 2 (pre-inference administrative amendment)

The v1 receipt comparison stopped before agreement because both otherwise locked AI annotator receipts used `actualfinalized_utc` instead of the required `finalized_utc`. The original v1 labels, receipts, hashes and abort record remain untouched. No inference or result scoring occurred.

This second custody attempt reuses exactly the previously frozen 100 question texts, IDs, selection, prompt, rubric, ranking inputs, seeds, metrics, model digest and validators. No cases are authored or selected again. The earlier independent labels and receipts are not copied or shown to the new annotator contexts. Tanishq and Khushi independently annotate the unchanged question-only sheets anew. Their receipts must contain the exact `finalized_utc` field with a real timezone-aware UTC timestamp; `actualfinalized_utc` may be retained as extra metadata but does not replace the required key. Both initial bytes are locked before any label comparison. Any new malformed/incomplete input aborts this second attempt.

The original study ID remains the frozen bank/design identifier `AIREF-E2-20261014-v1`; this package is custody attempt 2, stored separately. Agreement is descriptive AI-reference agreement, with no human-ground-truth claim. No outcome-dependent change is permitted.
