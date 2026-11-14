# Windows Opera manual-control check

Observed 14 November 2026 at 15:19 UTC on source commit `8db85240db0a947312c3551b5d0e06c71ee5c7b3`.

## Scope and provenance

The browser operator reported the visible result below in Opera on Windows at `http://127.0.0.1:8765/`. The application used the synthetic eight-item category fixture and the **manual** provider. Its banner read “No model provider · manual controls only.” No model or Claude call occurred. The browser operator was automated, not a human reviewer.

Launch command:

```powershell
python -B scripts/run_demo.py --scenario category --provider manual --port 8765
```

This is a transcription of the browser operator's contemporaneous result, not an independent rerun. The source revision was supplied by the server owner. No screenshot files or video are attached to this receipt.

## Observed sequence

| Step | Visible feed, in order | Result |
| --- | --- | --- |
| Baseline | 41006, 41007, 41008, 41001, 41002, 41003, 41004, 41005 | Eight items. |
| Preview exclusion of existing category K1 | 41006, 41007, 41008, 41001, 41002, 41003, 41004, 41005 | Proposal targeted only 41001 and 41004. Preview did not change the feed. |
| Apply | 41006, 41007, 41008, 41002, 41003, 41005 | Six items; exactly 41001 and 41004 were removed. |
| Undo review | 41006, 41007, 41008, 41002, 41003, 41005 | Six items remained until approval. |
| Approve Undo | 41006, 41007, 41008, 41001, 41002, 41003, 41004, 41005 | Original eight IDs restored in their original order. |

The initial form value `category_1` was rejected as an existing category ID. Entering the fixture's actual ID `K1` succeeded. Therefore this check does not establish that the initial category selection was correct.

## Evidence retention and cleanup

The browser operator reported five captured screenshots: baseline, Preview, applied feed, Undo review and restoration. They were not saved as separate files. This receipt does not provide independently inspectable image evidence or invent image paths or hashes.

Separately, the server owner reported stopping its own test server and verifying HTTP connection refusal and a clean checkout at **15:22:54 UTC**. This cleanup statement is the server owner's report, not a browser observation.

## What this establishes

This check supports reversible manual category control through the Windows Opera interface on the named revision: **8 → 6 → 8**, with exact item and order checks. It does not establish recommendation quality, model understanding, new-category induction, indirect category/tag inference, real CLI integration, a fresh installation or acceptance of later source revisions. The historical performance study remains separate from this synthetic demonstration.

## Revised chooser check at 15:57 UTC

On 14 November 2026 at **15:57 UTC**, the browser operator reported a new Opera check on source `5566fdfe7fedada556b6be0827be6bd6a75ab01a`, supplied by the server owner. This successor replaced the invalid initial category value with an explicit chooser. The same manual-only synthetic category scenario ran at `http://127.0.0.1:8765/`. Chrome and Claude were not used. The operator was automated.

| Check | Recorded observation |
| --- | --- |
| No category selected | Review was disabled. |
| Category chooser | K1, K2, K3 and K4 were displayed. |
| K1 Preview | The ordered eight-item feed stayed unchanged. |
| Apply | Exactly 41001 and 41004 were removed; six items remained. |
| Undo review | Six items remained until approval. |
| Approve Undo | The original eight IDs returned in their original order. |

The operator initially classified the result as partial because its supplied expectation was K1–K7. That expectation was wrong, not an observed missing-category defect. Inspection of the [published fixture](../../../tools/hosted_validation_current/inputs/01-category-discovery/app-data.json) at the tested revision establishes exactly four categories:

| Category | Fixture item IDs |
| --- | --- |
| K1 | 41001, 41004 |
| K2 | 41002, 41006 |
| K3 | 41003, 41007 |
| K4 | 41005, 41008 |

An independent source check also reported that the manual app's `/api/categories` returned exactly K1–K4. The observed chooser therefore covered the actual fixture. This correction reconciles the initial partial report; it does not replace it with an invented browser rerun.

The server owner separately reported stopping its own server after UI custody was released, confirming connection refusal and a clean checkout. No new screenshot files or video are attached. This section transcribes operator and server-owner reports, with a separate published-fixture check; it is not an independent visual review.

The revised chooser and manual Preview, Apply and two-step Undo passed on the named successor. This remains **manual-only acceptance**, not proof of live language inference, a real CLI model call, recommendation quality or completion of all transcript requirements.
