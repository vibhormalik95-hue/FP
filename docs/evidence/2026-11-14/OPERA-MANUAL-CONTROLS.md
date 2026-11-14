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
