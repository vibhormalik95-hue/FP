# Reviewed category induction integration

## Current evidence

The additive category producer is connected to the opt-in semantic review API,
UI and fixed ranker. This is engineering integration. Two actual Qwen development
inputs each returned `no_match` under the initial prompt and under one separately
declared overlap-coverage clarification; none produced an approvable category.
Successful real-model category induction and its semantic quality remain unproven.
The positive induction API tests use explicitly synthetic response doubles.

Independent review subsequently found a stale inventory bypass on undo in the
initial integration revisions. The current correction revalidates live scoped
original/source category mappings on every induced-group use, including restore,
and preserves the complete user state on rejection. See
[HISTORY-REVALIDATION-FIX.md](HISTORY-REVALIDATION-FIX.md) for reproduction and checks.

This work starts from public revision
`b3f2934d07159c7818a673bd6486dfd6eae5ad24`. It preserves the original A-E path,
the E1/E2 findings and the exposed November 4 prospective study. It does not
replace any failed empirical target. This new branch requires publication review.

## Five compatibility requirements

| Requirement | Implementation and verification |
| --- | --- |
| Local inference adapter | `feedctrl/induction_integration.py::make_induction_infer` explicitly maps the producer's `instructions` into the system message. One installed local-model generation per proposal, 90-second generation timeout, no repair retry or rule fallback. |
| Actual model identity | Existing loopback-only transport; installed model name/digest/runtime version are read before generation; response model and post-call digest are checked. Completed raw HTTP JSON is retained before content/schema validation. |
| Bounded evidence | At most 12 explicit existing candidate IDs, 7,000 UTF-8 bytes of producer payload and 10,000 bytes of the actual ASCII-escaped chat serialization. Oversized input blocks instead of truncating. The UI offers the first six or ten neutral baseline IDs and displays them. |
| Sealed definition and decisions | Entire envelope, generated definition, every disposition, exact source-field evidence, objective, inventory, model provenance and raw call receipt enter a server-owned group digest. Apply revalidates current source and category inventory, revision, nonce, session/user and a five-minute review token. Client approval cannot supply an edited category. |
| Approved existing IDs only | Only positive IDs accepted by the unchanged `validate_induced_category` scaffold enter `rank_groups`. No literal rematching or alias expansion occurs. Controls use the same normalized score vector and numeric-ID tie order as the explicit membership comparator. Exclusion removes approved IDs from the full eligible pool. |

## Workflow and code tour

1. Open **Reviewed topic feed**, then **Experimental semantic groups**.
2. Choose **Local LLM: propose a new category definition and membership**.
3. Select an evidence scope and enter a discovery objective. Direction/strength
   are explicitly manual in this induction path; this is not an action-parsing score.
4. `POST /api/semantic/induction/preview` snapshots current candidates and projects
   original categories, source taxonomy labels and saved groups onto that pool.
5. `category_induction_producer.propose_category` requests a generated label,
   definition and one `match`/`not_match`/`unknown` decision per supplied item.
   Non-unknown decisions must cite exact existing field quotes. Competing
   definitions, empty positives, duplicate labels/memberships and invalid evidence
   cannot become an approval token.
6. A reviewable result displays the definition, every disposition, unknowns,
   overlaps, model/digest, selected IDs and proposed feed. Nothing is saved yet.
7. **Approve this exact item set and apply** uses the existing server-owned token.
   `revalidate_category` and `validate_group` precede the state write. The separate
   semantic profile supports merge/replace, reviewed undo and clear/reset.

`semantic_review.py` owns the API, review token and apply boundary;
`induction_integration.py` owns adapter/custody conversion;
`category_induction_producer.py` owns proposal validation;
`semantic_induction.py` remains the unchanged definition/membership scaffold;
`SemanticPanel.jsx` renders discovery and explicit approval.

## Executed checks

- Full isolated suite before the final wire-budget accounting correction:
  **455 passed, 1 skipped**, 30.83 seconds. The skip is the absent private parser bank.
- Affected producer/API/review tests at that point: **87 passed**, 1.87 seconds.
- Final adapter/API regression result is recorded in `development-summary.json`.
  At that checkpoint, no full suite had been rerun after the bounded accounting change.
- Successor coverage-clarification check: **88 affected tests passed**, 1.53 seconds.
  This includes the functional contract that a distinct derived set can be reviewed
  even when the existing inventory covers every candidate. See `DIAGNOSIS.md`.
- Inventory-history correction: **48 affected API/review tests passed**, 1.68 seconds.
  The current full suite passed **460 tests, 1 skipped**, 30.89 seconds. Earlier
  counts above remain historical checkpoints.
- Vite production build: **30 modules, passed**, using a private local copy of
  already installed dependencies; no download/install was needed.
- Real served status at localhost port 8775: processed data, trained model,
  official sidecar, 865 users, 2,593 items and 31 original categories.
- Actual browser: induction controls rendered and Qwen `no_match` was visible.
  Separate explicit manual category review/apply excluded four scoped IDs;
  eligibility changed 2,593 to 2,589 with full fill. Reviewed undo restored the
  original top ten and 2,593 eligible items. This manual check is not LLM success.
- Real API: second Qwen invocation returned `no_match`; A-E comparison and saved
  semantic state were exactly unchanged before/after in that same test session.

Tests cover generated-definition review/apply/undo with synthetic inference,
boost/reduce at light/strong strengths and hard exclusion against one shared
numeric score vector, invalid/boolean/unknown IDs, field and definition tampering,
current-source changes, inventory changes, expiry/session/user/revision races,
payload budgets, model-identity changes and retention of malformed model content.

## Live local-model development findings

The two initial attempts were declared before inference, with no prompt changes
between them. A successor development pass explicitly clarified that existing
coverage does not preclude an overlapping derived group, then repeated the same
two inputs once each under a new recorded prompt hash. It changed no validator,
source data, model, sampling settings or frozen study. All four calls abstained.
These are two exposed inputs under two prompt revisions, not four independent
cases or a held-out accuracy estimate. Raw responses remain private, including
contradictory/unsubstantiated text inside the model's abstentions.

| Attempt | Evidence pool | Result | Generation adapter time |
| --- | --- | --- | --- |
| English, actual browser review button | First six neutral user-14 baseline items | HTTP 200, `no_match`, one real call, no apply | 7.772 s |
| Chinese, served HTTP API | Previously exposed eight-item development scope: two food-labelled records and six other captioned records | HTTP 200, `no_match`, one real call, no apply | 2.831 s |
| English repeat, served HTTP API | Same six-item pool and objective as initial English case; overlap-coverage clarification only | HTTP 200, `no_match`, no apply; inconsistent rationale about an existing family/emotional relationship category | 9.121 s |
| Chinese repeat, served HTTP API | Same eight-item pool and objective as initial Chinese case; same clarification | HTTP 200, `no_match`, no apply; unsubstantiated food/car category definition in the raw abstention | 3.053 s |

Runtime: Ollama 0.34.0, `qwen2.5-coder:7b-instruct`, digest
`dae161e27b0e90dd1856c8bb3209201fd6736d8eb66298e75ed87571486f4364`.
Qwen was explicitly unloaded afterward; `/api/ps` was empty and GPU usage was 0 MiB.
No other model/process or existing demo session was stopped.

The final accounting fix measures the exact serialization used by the existing
transport. Offline reconstruction confirms the two actual requests were 7,789
and 8,929 wire bytes, both within the unchanged 10,000-byte cap. It changes no
prompt, model, semantic validation rule or recorded outcome.

## Limits and attribution

- Generated categories are temporary, explicitly reviewed groups over observed
  item IDs. This path creates no videos, source descriptions, synthetic items or
  official taxonomy records. It performs no full-catalogue semantic retrieval.
- Novelty checks compare labels and sets only against the projected supplied
  inventory. A duplicate within this small pool can block a useful broader
  distinction; a passing result would not establish globally new concepts.
- Exact quotes prove source existence, not entailment, relevance, completeness,
  safety against all prompt injection, or user benefit. The scaffold deliberately
  reports `semantic_entailment_verified: false`.
- Abstentions are not scored as semantically correct merely because transport
  succeeded. There are no independent reference judgements for these two cases.
- New independent language/reference custody and protocol freeze remain necessary
  before a confirmatory study. No paid-provider calls or new grants occurred.
- The supplied producer and this integration/tests/docs are assistant-created
  work. They are not evidence of Vibhor's personal line-by-line review. His prior
  direction/review/push account remains an attributed self-report about his work.

## Reproduce the engineering checks

```powershell
python -m pytest tests/test_category_induction_producer.py tests/test_induction_integration.py tests/test_semantic_review.py -q
python -m pytest -q
cd web
npm run build
```

Use the existing local saved-data launch configuration and set
`FEEDCTRL_STEERING_MODEL=qwen2.5-coder:7b-instruct`. Start this isolated worktree
with `python -m uvicorn feedctrl.api:app --host 127.0.0.1 --port 8775`.
Saved inputs are deliberately not bundled. Verify `/api/status` on the actual
process; a cached browser page does not prove a server is running.
