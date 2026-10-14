# Verified local practice execution on 14 October 2026

Final report length, rendering route, reviewed artifact identities and local evidence location are in [the delivery record](delivery-2026-10-14.md). The data-free [prospective amendment](formal-e2-prospective-amendment.md) is prepared for decision; it is not an approval or a new bank.

Ollama 0.34.0 on AI_WORK; llama3.1:8b, Q4_K_M, 4,920,753,328 bytes; digest 46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e. The model digest matches the archived runtime; the Ollama version differs from historical 0.34.4.

Llama structured agreement with the supplied AI reference is 73/100; rule agreement is 18/100. Parser/validation errors: Llama 24, rule 0, retained in the denominator. These are exposed-practice agreement scores, not human-label accuracy or unseen-test performance.

The Llama errors comprise 23 conditional-grounding rejections and one invalid floor command. A post hoc raw-response recount finds 95/100 reference matches before application validation. That supplementary count explains failures and does not replace the fixed validated-parser score.

The run saved 41,508 ranking rows for 3,459 assigned user/class requests and 865 users, across three frozen recommender seeds and four conditions. It saved 2,595 complete score vectors. Requests with no eligible practice case remain in the exclusion record.

User-averaged induced-success proportions: A 0.0392, rule 0.0840, llm 0.2381, recency 0.0726. User means average seeds within class and eligible classes within user. The existing evaluator retains descriptive intervals; no formal H1/H2 decision is claimed.

All 288 frozen Experiment 1 files match the pinned manifest before and after execution; zero missing or mismatched. The September 29 parser commitment and original E2 protocol remain unchanged. No recommender was retrained or prompt tuned.

A fresh-process audit independently recomputed all 41,508 rows' control and relevance metrics and pooled means from saved score vectors, top-10 lists and exposed references, with no discrepancies. The same AI agent performed this computational audit; it is not a second human or blinded review. Bootstrap intervals and signed-rank calculations were not independently reimplemented.

Week 1 retains 13 self-reported active hours. Week 2 actual hours, personal reading and human annotation remain unreported. Agent time and unattended runtime are not entered as student hours. Sending of the October 13 update and occurrence of the October 14 meeting are not verified.

## Formal execution blocker

Formal E2 requires Borna's prospective approval of a replacement unseen bank and valid annotation route, genuine independent labels, pre-adjudication agreement, blinded adjudication and full freeze. The current 100 worked questions cannot supply that unseen bank.

## Reproducibility record

The methods bundle includes protocol-before-inference.json with the complete literal prompt, schema, fixed options, source and input hashes, source snapshots, actual model/API provenance, raw responses, parse records, full ranking score vectors, per-request metrics, all failures and excluded user/class pairs. It also retains the aborted wrong-model attempt, its preflight error and interruption receipt; no result from that attempt is used. The original AI label timestamp strings are preserved as supplied, with their timezone-format limitation disclosed in the protocol.

The completed run and audit use scripts/run_exposed_practice.py and scripts/audit_exposed_practice.py. The original scripts/run_experiment2.py, parser source, models, reserved bank, human gates and September 29 receipt are unchanged. No model is trained, no response is invented, and no new student hours are recorded.

## Scope of review

The independent computational audit checks parser denominators, immutable file hashes, exact questions and reference provenance, fixed runtime and prompt, every ranking metric and user aggregate. The same AI agent conducted it in a fresh process with a separate stdlib implementation; this is not an independent human study or blinded review. Historical E1 score/full-ranking hash discrepancies and full Colab reproduction remain unresolved.

## Windows source byte provenance

The existing Git checkout uses CRLF while the original archive uses LF. The parser, evaluator and protocol are identical after LF normalization, but their raw SHA-256 values differ. The run snapshot pins the actual Windows bytes, and source-line-ending-comparison.json records both identities. No normalization or historical commitment replacement was performed.

## Descriptive practice quality

Practice NDCG@10 is 0.02461 for Llama versus 0.03128 for item feedback. HR@1 is 0.183% versus 0.193%, with recency at 7.977%. These are descriptive quality proxies, not a formal H3 conclusion or a claim of improved recommendation accuracy.
