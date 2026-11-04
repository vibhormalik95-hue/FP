# Experiment 1 replay discrepancy: evidence and remaining limit

4 November 2026. This is a read-only reconciliation of the saved October audit, not a new checkpoint run, language inference, training run or recalculation of experimental outcomes. Frozen records were not changed.

## What differs

The October checkpoint audit scored each of 865 users once per seed and reconstructed five conditions for boost and mute. Its results were:

| Seed | Top-ten lists and ranked counts matched | Full-ranking hashes differed | Request-score hashes differed |
| --- | ---: | ---: | ---: |
| 42 | 8,650/8,650 | 652 | 1,730/1,730 |
| 43 | 8,650/8,650 | 536 | 1,730/1,730 |
| 44 | 8,650/8,650 | 821 | 1,730/1,730 |
| Total | 25,950/25,950 | 2,009 | 5,190/5,190 |

Each user's score vector is reused for boost and mute. The 5,190 score-hash records therefore represent **2,595 user/seed vectors**, not 5,190 independent scoring draws. Saved rule and LLM rankings are equal, so the corresponding rule rows have the same replay issue; the table does not double-count them. No headline top-ten metric changed in that historical audit. This does not establish byte-identical scores or complete rankings.

## What this reconciliation actually checked

The preserved `numbers-evidence.tar.gz` contains `recomputed-results.json`, all 7,199 individual mismatch records, and `hash-definition-check.json`. This pass read those files in memory and matched every recorded expected hash to the original `results/llm/seed_{42,43,44}/requests.json` fields. All **7,199/7,199** matched: 5,190 score digests plus 2,009 ranking digests. The boost/mute reuse and identical history hashes were checked for all 2,595 user/seed pairs. All inspected source-file hashes remained unchanged.

| Preserved evidence | SHA-256 |
| --- | --- |
| Verbatim numerical report | `af578c49ab2bbdb608eca5a834a94140d1239104ed9377a70c3994974296d101` |
| Numerical evidence archive | `c88547adbd7d017dc2049fa0ef4b1c945668585a896811964d19532ad206dd86` |
| R3 numerical follow-up | `efa4a3d91c6516830fa1a08683abe8c9a1d2b7df91b4c573607b902c62b1b61e` |

These files are in the private research archive under `results/experiment2/verification/supervisor-2026-10-03/reviews/numbers/`. The frozen request records are not published by this note.

## Causes already examined

The historical audit used Python 3.12.14, PyTorch 2.5.1+cpu, NumPy 2.3.5 and Linux x86_64, with two intra-op threads, nine observed inter-op threads and MKLDNN enabled. Matching the recorded PyTorch version and intra-op count did not reproduce every digest.

The hash definition is SHA-256 of compact JSON: `json.dumps(value, sort_keys=True, separators=(",", ":")).encode()`. Scores are cast to Python floats without rounding; candidate IDs are numerically sorted. For one actual differing request per seed, both the original ranking/hash functions and the independent audit functions produced identical replay lists and digests, while still differing from the saved record. This excludes an audit-side serialization or policy-formula discrepancy for those representative cases. It does not identify the underlying scoring cause.

## Why this is still unresolved

The original request records contain score hashes, not the original numeric score vectors. They also retain top tens and complete-ranking hashes rather than complete original ranking arrays. A digest cannot reveal the numerical error size, the scores responsible or the exact changed tail positions. This read-only inspection cannot recover those missing values. No particular hardware, numerical kernel, tie behavior or library version is established as the cause.

The useful next source investigation would be to locate any separately preserved original numerical score vectors/full lists and their runtime record, then compare those existing bytes. If none exist, another scoring run could characterize its own behavior but could not recreate the missing historical vectors or prove a cause merely by producing similar hashes. No new run is required to report the recorded top-ten findings honestly; complete bitwise replay remains a disclosed limitation.

This finding concerns frozen Experiment 1. It neither reopens the archived original human-reference route nor changes the completed revised AI-reference Experiment 2.
