# Model adapters for indirect requests

The indirect-intent workflow calls `infer(payload, schema) -> dict`. Each provider needs an adapter that accepts that input and returns the expected data. Entering a model name alone does not connect its API.

The configuration described here covers indirect intent. Category creation has a [separate configuration interface](category-provider-configuration.md). The original A–E routes, local Ollama behavior and frozen experiments remain unchanged. The latest source also supplies the shared provider to the optional fictional-item adapter through `synthetic_infer_factory`. That wiring has offline tests, and a separate real Claude Code Lunaria check completed the lifecycle through the application’s Python methods. It did not use HTTP or a browser; support for one workflow does not by itself prove that another works. See [current progress](current-progress.md).

## Configure the provider at startup

`create_app(..., semantic_infer_factory=factory)` supplies a factory returning `(infer, provenance)`. Provenance must contain nonempty `backend`, `model` and `digest` strings. Without a factory, the UI does not offer this provider, and a direct request for it fails with HTTP 502.

The API option is `backend="configured_model", action_source="model"`. The provider handles both action/strength interpretation and matching the request to source items. Errors do not fall back to Ollama, manual selection or a rule parser. API requests cannot supply provider URLs, credentials or provider selection.

The app still checks the action against the request, item IDs, quotations, source changes and session identity. Review, ranking and undo keep their existing behavior.

The factory initializes at most once per app under a lock. All sessions and previews reuse the adapter, so preview requests cannot create a fresh call allowance. Changing provider/run settings requires a newly authorized run; the API cannot refill the allowance.

## OpenAI Responses adapter

`feedctrl.model_adapters.make_openai_responses_infer` connects to the fixed HTTPS endpoint `https://api.openai.com/v1/responses`. It uses strict `text.format` JSON Schema, one system and one user message, no tools or history, and `store=false`.

Model, reasoning effort, output-token limit, request-byte limit, timeout and shared call allowance are explicit. The adapter does not send unsupported temperature or seed parameters, retry, repair output or silently substitute a model ID.

Construction makes no network call and does not read credentials. It requires an explicitly supplied credential and `authorized=True`. That flag is a code setting, not proof of user approval. Before use, verify API access, the authorized data/destination and the paid-call ceiling, then record the exact run configuration. A ChatGPT or Claude browser subscription does not establish API access or a budget.

### Share the call allowance

Create one `HostedRunBudget(max_calls=2)` outside the factory. Pass the same object as `run_budget` to every adapter instance in that authorized run. It reserves attempts atomically across concurrent instances, is bound to the exact model/options configuration and cannot refill itself. Mutable receipt lists do not control the allowance. There is no implicit per-adapter allowance.

This is an in-process call limit, not a durable account billing cap. Restarting the process or creating another allowance must not be used to evade the authorized total. The [hosted-only configuration](hosted-only-configuration.md) also requires the durable spending guard.

Timeouts and HTTP errors still consume an attempt. Records retain exact request data without authorization headers, bounded original response bytes, HTTP/request IDs where available, elapsed time, usage and parsing outcome. Oversized captures are marked truncated. Refusals, incomplete responses, model mismatches, duplicate JSON keys, nonfinite values, unexpected content and invalid JSON fail without repair. The semantic workflow independently validates the parsed object afterward.

### Interpret model identity carefully

The hosted `digest` is a configuration SHA-256, not a model-weight digest. Requested and returned API identities must match exactly. Provider aliases and reported processing do not verify the weights. Use a verified explicit snapshot where available; do not silently accept another identifier. `store=false` does not mean the provider retains no data.

The API references checked on November 5, 2026 were [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) and the [GPT-6.1 Sol reference](https://developers.openai.com/api/docs/models/gpt-6.1-sol).

A correctly formatted response with exact source quotes can still be semantically wrong. Reviewers must reject unsupported or incomplete sets before applying them.

## What has actually been tested

The Responses adapter has offline network-substitute and API tests. The records for this revision contain no real paid API call. API latency, billed cost, account access and automatic hosted transport remain unverified. The earlier check reported Claude Code logged out; that is a dated observation, not a fresh account-status check.

A separate operator-assisted browser example used the observed Opus 5.5 Medium selector for two fresh messages, with replies captured through Copy. The configured-provider app route validated them, and explicit review/apply, clear and undo changed eligibility 8 to 5 to 8 to 5 to 8.

This was one exposed synthetic development example. It was not an automatic Claude API connection, a verification of provider-side processing or a held-out accuracy result. The tool observing the copied replies was separate from the application code. See the [5 November walkthrough](../deliverables/2026-11-05-final-demo/README.md) for the full record. The earlier capture failure, local Gemma timeout and frozen negative studies remain unchanged.
