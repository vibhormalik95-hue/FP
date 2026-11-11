# Explicit category clarification resolution

This is a future in-session workflow correction, tested with authored offline responses. It does not replay, import, repair, reseal or resume a previously ended model run, and it does not establish semantic accuracy.

## Supported path

When the definition model returns `propose` with competing alternative strings, the server now checks the whole primary candidate with the ordinary bounded-label, definition, inventory and exact-source-quotation rules before offering resolution. A valid primary remains **clarify**, with its original objective, model identity, hashes and raw response unchanged. The UI shows its exact label, definition, rationale, supporting quotations and alternatives as unapproved text. A quotation's existence is not proof that it supports every definition clause.

Nothing is selected by default. The operator can explicitly choose the unchanged primary meaning for review or cancel. Alternatives are descriptions, not complete evidence-backed definitions, so they are not selectable candidates. To propose another meaning, change the objective and explicitly submit a new proposal within the separately authorized call budget.

`POST /api/semantic/definition/resolve` accepts only `user_id`, the server-issued `plan_id`, and `choice` (`review_primary` or `cancel`). It performs no provider lookup or inference. The single-use, five-minute token is bound to the session, user, request, action, scope, source, eligible catalogue, inventory, semantic revision and preview nonce. Server-held data is revalidated. Reset, superseding reviews, source changes, expiry, tampering and replay reject the token.

Selecting the primary records an explicit operator resolution separately and retains the complete original sealed clarification. It issues a **new ordinary definition-review token**, not a classification or Apply authorization. Cancelling consumes the clarification. Editing, changing user, reset and closing the UI clear displayed choices and discard stale responses. Repeated clicks cannot submit duplicate in-flight requests.

## Gates that remain required

1. Read the exact definition and evidence. Reject unsupported substantive conditions or a missing-data clause that conflicts with the existing membership contract.
2. Check the explicit evidence-review box and approve the definition. Only this starts membership classification.
3. Classify every supplied ID once as match, not_match or unknown. A match needs affirmative evidence for every condition; a not_match needs evidence that a condition is false. Missing substantive facts remain unknown.
4. Run the existing separate evidence assessment, blind to the primary decisions. It can withhold positives but cannot upgrade unknowns or negatives. Same-model agreement is not independent semantic proof.
5. Review the exact supported IDs and apply explicitly. Clear and Undo retain their separate review and Apply gates.

No-match, ambiguous results without a valid primary, unsupported/malformed source quotations, and duplicate labels cannot enter resolution. Mechanical validation does not certify semantic entailment: selecting an unchanged primary must not be used to cure a semantically invalid definition.

## Definition-prompt consistency correction

The definition prompt now states the existing membership evidence rules explicitly, including that missing information remains unknown and absent evidence must not become an exclusion condition. It also distinguishes definition-stage `no_match` (no supported proposal) from negative item membership. The discovery objective, supplied records, generation schema and membership/audit prompts are unchanged.

This prompt change applies prospectively. Historical response files and the headless helper's frozen first-request profile remain unchanged. The existing helper still terminates at clarification and has no resolution/resume feature. A future authorized headless run needs a separately labeled current request profile; old request bytes must not be overwritten to conceal the prompt change. The historical Fable candidate's missing-data clause is not edited or endorsed by this feature.

## Verification scope

The focused tests invoke the API functions with authored responses and execute the real JSX handlers/effects in an offline component harness. They exercise strict inputs, provenance custody, stale/cancelled/repeated actions and the complete guarded continuation. They are engineering fixtures, not semantic gold, live observations, browser-layout validation or frozen-study results. No live model, local trained scorer, Windows native runner, network call or new dependency installation is needed for these checks.
