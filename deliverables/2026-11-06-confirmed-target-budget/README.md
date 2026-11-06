# Confirmed target and durable spending development

Base: independently reviewed `1c25041a65e369e172a9e6a65b91ebecc4e04016`. This is a separate development branch. No frozen request/output/reference, semantic prompt or model schema is changed. No new inference, credential access, paid request, desktop control, recording or publication occurs in this work.

## A safe path after unresolved personal intent

The normal automatic interpretation remains unchanged. A separate opt-in path lets the user state an observable target and choose the action/strength explicitly. The model then proposes membership from the supplied source text only. This can support a clarified food/cooking target after an appetite-related request, but does not prove what makes a person hungry or establish automatic hunger recognition.

The original request, user-confirmed target and their hashes remain visible and sealed. The model receives only the confirmed target, not the ambiguous personal context. Provenance labels the action and interpretation as user-supplied. There is one grounding attempt, no rescue call or silent repair. Model abstention still stops without an apply token. Existing ID, quotation, half-scope, source, review, session, undo and reset gates remain in force.

API example (a newly authored usage example, **not an executed model test**):

```json
{"user_id":1,"text":"I want to avoid tempting food imagery while I work.","label":"My confirmed food-content target","candidate_ids":[1,2,3,4,5,6],"backend":"ollama","action_source":"confirmed","confirmed_target":"Items whose own supplied captions describe preparing, plating, or eating food.","target_confirmed":true,"operation":"exclude","strength":"none","mode":"replace"}
```

The candidate IDs must actually exist in the caller's isolated catalogue. This request still needs actual evidence-backed model execution and user review. The old exhausted hunger test is not rerun, replaced or reclassified as a success. New tests use an unrelated synthetic equipment/alarm fixture and test doubles; they establish contract and state behavior, not semantic quality.

The UI requires a current acknowledgment tied to user, backend, original text, target, candidate count, action/strength and mode. Editing any of those invalidates it. Withdrawing acknowledgment clears the fresh pending proposal. Historical clear/undo reviews preserve their normal approval flow. No browser test was performed in this revision because the shared desktop was reserved.

## Conditional enforcement of the approved US$0.50 run

`DurableHostedSpendGuard` uses one fixed SQLite ledger. Initialization is exclusive; missing, partial, corrupt or mismatched ledgers are not automatically recreated. Every connection pins and checks DELETE journal mode plus EXTRA synchronization. A committed reservation precedes any counter callback. Each attempt permanently reserves250000 microUSD; two attempts consume the500000 microUSD ceiling. No refunds, expiration, duplicate request, concurrent in-flight attempt or automatic resumption is allowed. Failure or unexpected model/tier/usage blocks the run. Restarting an adapter does not reset this file's allowance.

Requests are frozen as exact canonical byte hashes and allowlisted. Only the approved exact model/effort, explicit default service tier, text/object-schema input, no tools/history, bounded input count and output cap are accepted. The existing Responses adapter accepts this optional guard and records its binding. **The legacy adapter without a guard still has no monetary-cap claim and must not be used for this approved bounded live test.**

The counter must count the same complete model/input/reasoning/schema configuration. Its verified implementation must make at most one HTTP attempt, with no redirects/retries, and return a receipt hash bound to the generation bytes. This code invokes the counter callable once; it cannot police arbitrary callback internals. Real counter networking is deliberately not implemented/activated until its billing ceiling and applicability are established.

With conservative input/cache-write rate5 USD/million, output10 USD/million,16000 input tokens and4096 total output tokens, generation is bounded by120960 microUSD per attempt. A separately proven counter charge and other applicable extras must fit the remaining129040 microUSD of that fixed reservation. Exact rational arithmetic rounds upward. Evidence hashes identify external proofs; they do not verify those proofs or make guessed rates authoritative.

This is conditional enforcement for one cooperative owned run on its fixed local ledger, not an account-wide billing limit, defense against ledger deletion/rollback/cloning, or guarantee of a final invoice. Power-loss behavior was not physically tested. See [SQLite synchronization](https://www.sqlite.org/pragma.html#pragma_synchronous), [official per-run controller guidance](https://developers.openai.com/cookbook/articles/per_run_spending_controller_responses_api), [counting configuration](https://developers.openai.com/api/docs/guides/token-counting), [count endpoint](https://developers.openai.com/api/reference/python/resources/responses/subresources/input_tokens/methods/count), [Responses parameters](https://developers.openai.com/api/reference/python/resources/responses/methods/create), and [pricing](https://developers.openai.com/api/docs/pricing). Checked November6,2026. Cookbook sample prices are not used as real prices.

## Executable checks and remaining activation steps

Offline checks, requiring no model or credential:

```text
python -m pytest tests/test_confirmed_target.py
python -m pytest tests/test_hosted_spend_guard.py tests/test_model_adapters.py
cd web
npm run build
```

Before any real use:

1. Establish an authoritative bound for token-count endpoint billing and all applicable account/region/cache charges; verify exact account/model access and current pricing. No such account access or billing proof is asserted here.
2. Freeze a **new** synthetic request/source/expected-set protocol, exact one or two complete request byte hashes, model/effort, strict call/failure stops and a reviewed credential-free preflight. Do not use the exhausted hunger fixture or held-out banks.
3. Independently verify the real counter implementation's complete-payload projection and single-attempt behavior. The public endpoint schema documents model, input, reasoning and text configuration; it does not in the inspected reference establish a billing bound.
4. Complete the currently disabled `LIVE-PREFLIGHT.json`, preserving the user's existing two-call/US$0.50 approval. Create one owned ledger once, then configure the adapter with that guard and one shared in-process call budget. Confirm the guard binding in provenance before permitting credentials/transmission. Do not create another ledger after uncertainty.
5. Only when every prerequisite and applicable authority is satisfied may a separate bounded live attempt run. Capture count/provider requests, HTTP/failures, timing, model/tier/usage and review/apply/clear/reset receipts. A failure remains a failure. Current development makes zero such calls.

`LIVE-PREFLIGHT.json` remains explicitly blocked. Missing external proof is not relabelled as missing user approval. The final professor paper remains later work, and no email or recording is authorized here.
