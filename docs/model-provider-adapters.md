# Model providers in the reviewed semantic workflow

The semantic algorithms accept `infer(payload, schema) -> dict`. The runtime
must supply an adapter for the selected provider. A model name alone does not
make different APIs interchangeable.

The existing Ollama default, original A–E routes, staged category induction,
synthetic-item generation and frozen experiments are unchanged. This addition
exposes an operator-injected provider only for the separate indirect-intent
workflow. It is not a claim that all project workflows support every provider.

## Explicit startup configuration

`create_app(..., semantic_infer_factory=factory)` installs a factory returning
`(infer, provenance)`. Provenance must contain nonempty `backend`, `model` and
`digest` strings. An app without this factory does not offer the provider option
in the UI; a direct configured-provider request fails closed with HTTP 502.

The API option is `backend="configured_model", action_source="model"`.
Both direction/strength interpretation and item grounding use that provider.
There is no fallback to Ollama, manual selection or a rule parser. Provider
selection, credentials and URLs cannot be supplied by an API request. Existing
request-bound action validation, ID/quote checks, substantive review, stale
source checks, session isolation, ranking and undo remain in force.

The configured factory is initialized at most once per app, under a lock, and its
adapter is reused by all previews and sessions. Preview requests cannot create a
fresh allowance. A changed provider/run configuration needs a new authorized run;
there is no API route to replenish the allowance.

## First-party Responses adapter

`feedctrl.model_adapters.make_openai_responses_infer` implements the seam for
the fixed HTTPS endpoint `https://api.openai.com/v1/responses`. It uses strict
`text.format` JSON Schema, one system and one user message, no tools, no history,
`store=false`, and explicit model, reasoning effort, output-token, request-byte,
timeout and shared call limits. It does not set unsupported temperature or seed
parameters, perform retries, repair output or silently substitute model IDs.

The constructor makes no network call and does not read credentials. It requires
an explicitly supplied credential and `authorized=True`. That flag is an
operational gate, **not evidence of user approval**. Before enabling it, the
operator must establish actual API access, data destination/scope and a paid-call
spend ceiling, then freeze the exact run. A ChatGPT or Claude browser subscription
does not establish this API entitlement or budget.

Create one `HostedRunBudget(max_calls=2)` outside the factory and pass that same
object as `run_budget` to every adapter instance belonging to the authorized run.
It reserves each attempt atomically across concurrent adapter instances. The
allowance is bound to the exact model/options configuration, cannot replenish
itself, and is independent of mutable receipt lists. No implicit per-adapter
allowance is provided. This is an in-process call limit, not a durable billing
account cap; process restart or creation of a new allowance is a new run and must
not be used to evade the authorized total.

All attempted calls, including timeout and HTTP error, consume the shared cap.
The returned receipts retain exact request data (without authorization headers),
bounded original response bytes, HTTP/request IDs when available, elapsed time,
usage and parsing disposition. Oversized captures are explicitly marked as
truncated. A refusal, incomplete response, model mismatch, duplicate JSON key,
nonfinite value, unexpected content or invalid JSON fails without repair.
The semantic workflow then validates the parsed object independently.

The hosted `digest` is explicitly a **configuration SHA-256, not a model weight
digest**. Requested/returned API identity is checked exactly. Mutable provider
aliases and provider-side processing are not weight attestations. Use a verified
explicit snapshot where available; do not silently accept a different returned
identifier. `store=false` is not a claim of zero retention by the provider.

Authoritative API contract consulted on November 5, 2026:

- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [GPT-6.1 Sol model reference](https://developers.openai.com/api/docs/models/gpt-6.1-sol)

Structured formatting and exact source quotes do not establish semantic truth.
The reviewer must still reject incomplete or unsupported sets before applying.

## Current verification boundary

The new adapter has offline transport and API-mechanics tests using injected
network doubles. No real hosted call has been made for this revision. Existing
Claude browser access was observed as Ultra / Opus 5.5 Medium, while Claude Code
reported logged out. That browser observation is not an integrated provider run.
The earlier local Gemma timeout and all frozen negative studies remain intact.

Real hosted latency, billed cost, current account entitlement, provider output
quality and an actual live indirect-intent apply/undo path remain unverified.
No publication or claim of general semantic reliability follows from these tests.
