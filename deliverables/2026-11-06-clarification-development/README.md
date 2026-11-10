# Clarification and local transport development revision

> **Dated correction, 2026-11-06.** The base line below is historical: this revision is
> contained in published `1b682eaa3af6bd60b7ee0f6f36562bc09a33f08a` (public branch
> `codex/comp9500-professor-demo-20261027`). The "durable pre-send reservation remains
> unimplemented" sentence is superseded: `feedctrl/hosted_spend_guard.py` now implements a
> durable SQLite reservation committed before the token-counter callback and any send, no refunds or resets after an
> error, and a fixed two-attempt/US$0.50 ledger (tested offline in `tests/test_hosted_spend_guard.py`).
> Still NOT established: the exact input-token/overhead proof, the provider-side counter,
> billing or account cap, and any live call. `make_openai_responses_infer` still accepts
> `spend_guard=None`, so callers must pass the guard. Paid execution remains disabled and was not run.

Base: published demo `1f578bbb3548e3b8e2d86dfe2c634f5100b95899`.
This separate development revision makes no new model calls and changes no semantic prompt or generation schema. Frozen studies, raw model outputs, references and the exhausted hunger run are untouched.

## Changes

- When the evidence model abstains because scope or negation is unresolved, retain its bounded reason and competing interpretations. The UI labels these as unverified model hypotheses. None is selected or applied; the user must explicitly rewrite and resubmit. No automatic rescue call, proposal repair or category substitution occurs.
- Reject malformed local-model envelopes, non-object output, duplicate JSON keys and nonfinite JSON through the handled error path. A completed response missing `message` no longer escapes as an unhandled exception during action interpretation.
- Check response depth, node count, text size and finite canonical JSON before recursive copying/hashing. Excessive nesting from either adapter also fails as a handled error, with no apply token or preference change.
- Bound clarification alternatives and reject control/format/surrogate characters that could obscure their review. React renders the explanation and alternatives as text, without HTML interpretation or executable controls.

The new exposed rehearsal-display fixture and malformed response fixtures are offline contract tests. Their authored expected values are not semantic gold. Old tests are regressions only; no study is rescored or reused for tuning.

## What this does not establish

The particular cooking/hunger request still has its original terminal clarification/no-apply result. Displaying the model's alternatives improves the user's ability to resolve an ambiguity; it does not establish a successful target selection or semantic accuracy. No replacement live trial, model substitution or retry is included.

The application's `infer(payload, schema)` interface accepts a configured provider, with a local Ollama transport and an existing bounded OpenAI Responses adapter. That source-level abstraction does not attest an actual automatic hosted call. The prior stronger-model success used operator-assisted Claude Copy replies.

## Automatic hosted-provider boundary

The user previously approved up to two GPT-6.1 Sol Medium calls using synthetic input, with a binding US$0.50 total ceiling. That approval is retained; it is not described as missing. No credential is read or used in this revision.

Current official documentation names `gpt-6.1-sol`, supports structured output and lists standard input/output prices of US$2/US$10 per million tokens. Public model documentation does not establish this account's availability. [Model documentation](https://developers.openai.com/api/docs/models/gpt-6.1-sol), [pricing](https://developers.openai.com/api/docs/pricing), checked November 6, 2026.

The reviewed adapter enforces an in-process shared call count, response/request byte bounds, output-token limit, no retries and fixed destination. It is **not** a persistent monetary spending cap. The earlier operational proposal's exact input-token/overhead proof, explicit tier setting and durable pre-send reservation remain unimplemented/unverified. Consequently this revision does not execute the paid path or claim the approved US$0.50 ceiling can be guaranteed. Neither a subscription UI session nor this application's configured adapter flag proves automatic API readiness.

## Delivery status

This is local development pending independent source review and publication scope. No public push, main merge, professor email, recording, credentials, installation of a new model or paid inference is part of it. Test/build/review and mock-browser receipts are kept with the separate development source packet; they must not be described as live model outcomes.
