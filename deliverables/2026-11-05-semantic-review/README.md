# Reviewed semantic item-set prototype

This opt-in development path tests a new implementation, not the frozen A-E
experiment. It does not establish semantic accuracy or recommendation benefit.
The published prior results, including the 48/100 supported-case prospective
result, remain unchanged.

## What this code does

1. The caller supplies a small explicit set of existing catalogue IDs. The UI
   supplies the first six or ten baseline items; the API accepts 2-20. No query
   retrieval, model-selected candidate pool or hidden truncation occurs.
2. A local model interprets one current operation, strength and original subject
   span. Separately, it may propose related existing items without literal overlap
   between request and source. An explicitly selected **manual-action ablation**
   bypasses action parsing but still uses real model membership inference. This
   is never an automatic fallback after failure.
3. Existing IDs and exact source quotes are validated. No-match, ambiguity,
   structural errors, excessive scope and unresolved negation apply nothing.
4. A named group stores the exact item set, original request, evidence, model
   provenance and source/action/request digests. The user must inspect and approve
   it. It is a session-defined category over old items, not an official new
   taxonomy label or a newly created video.
5. Apply revalidates source records and candidate inventory. The full saved-model
   score vector is normalized once and adjusted only for approved members.
   Boost/reduce use 0.10/0.25/0.40; reduce retains eligibility. Exclude/none is hard
   removal, with no graded strength. Exclusion wins overlap. Numeric ID breaks
   ties. No later literal rematching broadens the approved set.
6. Merge/replace, reviewed undo/clear and global reset affect separate semantic
   session state. Original A-E and the existing literal topic profile are kept
   independent.

## Source and code walkthrough

| Component | Responsibility |
| --- | --- |
| `feedctrl/indirect_grounding.py` | Review-only proposal, bounded evidence, exact ID/quote custody, snapshots and local inference adapter. Model name/digest rechecked after each response. |
| `feedctrl/semantic_review.py` | Action interpretation, explicit manual-category comparator, labelled manual-action ablation, sealed group review/apply, current-source checks, token lifetime/race checks and item-set ranking. |
| `feedctrl/semantic_induction.py` | Separate validation scaffold for a definition and complete match/not_match/unknown dispositions. It is not a live classifier or full-catalogue induction service. |
| `web/src/SemanticPanel.jsx` | Experimental panel under Reviewed topic feed, visible candidate scope/evidence/method, explicit approval and undo/clear review. |
| `tests/test_indirect_grounding.py` | 33 transferred offline contracts including callback/caller mutation isolation. Mocks are not semantic accuracy evidence. |
| `tests/test_indirect_adapter.py` | Response model identity and post-call digest consistency checks. |
| `tests/test_semantic_review.py` | API state isolation, exact enforcement, stale sources/reviews, races, undo/reset and explicit ablation. |

The corrected source prototype ZIP was verified at 16,817 bytes, SHA-256
`804696735748f44a9eb173a2025fe61ee5658e6de97322be44c56c4bea3268d7`.
Its 33 contract tests were reproduced locally. The owner then added the adapter
identity checks, explicit exclusion contract and reviewed application path.
These are assistant-generated/assisted changes; they do not establish student
manual authorship or a personal line-by-line rehearsal.

Source metadata comes from the [official KuaiRec caption/category sidecar](https://github.com/chongminggao/KuaiRec/blob/main/kuairec_caption_category.csv),
SHA-256 `7ccf10f348da6041742222f107da32e1be8b1c8c7b710d65963fa10d56a014f5`.
No sidecar CSV, model weights, private correspondence or raw transcript is bundled.

## Verification and remaining limits

The first integrated full suite passed **377 tests, 1 skipped** in 39.30 seconds;
the skip is the absent private parser bank. Later identity/action-ablation changes
were checked with **107 affected tests passing in 2.16 seconds**, not represented
as a second full-suite pass.
Vite production build passed. A real rendered manual comparator excluded six
reviewed category_28 IDs from 2593 candidates, leaving 2587, then reviewed undo
restored the neutral feed. That is manual policy evidence, not LLM success.

Qwen development runs with appetite-related English and Chinese language
clarified, and explicit cooking positive controls also failed to produce a
reviewable item set. The raw reasoning included a mistaken reading of
exclude/none as zero effect, prompting an explicit enum-contract correction;
subsequent Qwen attempts still clarified. These failures are retained privately.
Do not present this path as reliable indirect understanding merely because its
HTTP responses and integrity tests pass. The installed Llama comparison also failed: one action-binding rejection, one
inconsistent abstention carrying evidence, and one clarification. Across 14
retained development invocations spanning several prompt revisions and explicit
action ablations, none produced an approvable model set; all left A-E unchanged.
This is a development log, not a held-out accuracy estimate. Raw private receipts
remain separate from this public source description.

Exact quotes verify that text exists, not semantic entailment. This prototype
does not establish catalogue-wide recall, compositional multi-action semantic
dialogue, new video creation, universal negation/language support, calibrated
confidence, injection resistance or human satisfaction. A new independently
authored and locked semantic reference bank is required before evaluation.
No old held-out bank may be reopened for prompt tuning.

## Local use

Use the existing saved data/model and official sidecar, and an already installed
local model. Keep the app on loopback and use a spare port to preserve existing
sessions. No software/model download is required by this addition.

```powershell
$env:FEEDCTRL_DATA = '<existing processed.json>'
$env:FEEDCTRL_MODEL = '<existing seed_42 directory>'
$env:FEEDCTRL_CAPTION_SIDECAR = '<official sidecar CSV>'
$env:FEEDCTRL_STEERING_MODEL = 'qwen2.5-coder:7b-instruct'
python -m uvicorn feedctrl.api:app --host 127.0.0.1 --port 8774
```

Open Reviewed topic feed, expand Experimental semantic groups, inspect supplied
IDs, enter one instruction and a group label, then Review. If clarification or an
error is returned, nothing was applied. Approve only appropriate evidence.

The optional smoke script always starts a new session and preserves A-E. Its
development scope deliberately contains two source-labelled food items and six
nonfood items selected by numeric ID. This is disclosed source selection, not a
retrieval benchmark or an unbiased sample.

```powershell
python scripts/smoke_semantic_groups.py --scope deliverables/2026-11-05-semantic-review/development-scope.json --output '<private result.json>'
```

`--manual-action` is a separate labelled ablation. It fixes exclude/none manually;
its result cannot count as model operation/strength interpretation.
