# Fresh synthetic-request Experiment Two: compact evidence

The 14 October evaluation used 100 fresh synthetic requests and model-generated reference commands. It is separate from the exposed 100-question practice run at commit `c6ebda06008c92e4141aa2d91991ac2c0328a1de`. Two separately contextualized model annotation passes produced the references. Their agreement measures consistency between model outputs.

This directory contains 29 scientific protocol, custody, inference, result and computational audit files. `INDEX.json` lists the byte length and SHA-256 of each file in this public subset. Earlier custody and inventory corrections remain with their original records; the unchanged full archive holds the complete execution and delivery history.

The public screening receipt includes all 300 candidate request texts across
100 case IDs, including the selected wording. Public parser-failure receipts
also include request text. Complete structured cases, both original model labels,
final references, 200 predictions, pre-call journals, full failure records,
41,520 ranking rows, 2,595 complete score vectors, execution logs and
per-file hashes are in the separate local evidence archive
`COMP9500-AIREF-E2-Execution-and-Audit-Evidence-2026-10-14.zip`.
Its SHA-256 is `6aa7a16186a86973c26fdf7ad280aaafb1f73893acfaa58cd04624e1a8692824` and size is 91,345,636 bytes.
The large `evaluation/ranking-rows.json` (48,213,615 bytes), assigned-request array (4,564,390 bytes), and raw references remain in the local ZIP rather than Git. A full replay needs that archive and the recorded model runtime. The bank has already been used for evaluation, so any later test needs new requests.

The model was local `llama3.1:8b` Q4_K_M on Ollama 0.34.0, digest
`46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e`.
