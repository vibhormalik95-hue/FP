# Configuring a model for category creation

The app can use an explicitly configured model for new category definitions and membership decisions. This configuration support does not by itself connect a live provider. The original local Ollama default remains available only where local models are allowed. See [hosted configuration](hosted-only-configuration.md) for the current restrictions.

## Supply the adapter

Trusted application setup calls `create_app(..., category_infer_factory=factory)`. The separate `semantic_infer_factory` argument configures indirect intent. Requests cannot choose a provider through a new endpoint or environment variable. Request/response schemas, producer schemas, and review before Apply are unchanged.

The factory takes no arguments and returns `(infer, provenance)` once per application. `infer(payload, schema)` returns JSON data. Provenance must contain exactly `backend`, `model_id` and `model_revision`, each nonempty valid UTF-8 text of at most 300 characters. Identify the provider, model and version or configuration truthfully. A declared configuration hash does not verify model weights. Test adapters must identify themselves as synthetic and must not return credentials or private account data.

## Follow the selected category workflow

The combined category route uses one wrapper. The definition-first route uses separate definition, membership and evidence-check wrappers, with user review before classification. Membership and the evidence check must retain the definition's complete provider identity.

One configured callable is reused across stages and later previews. Rebuilding a factory cannot refill its run allowance. Initialization is tried once; a configured failure never falls back to local Ollama.

Each wrapper permits one visible call to the supplied function. That does not limit the function's internal HTTP attempts, retries, runtime or price. The adapter must enforce those limits itself. This configuration module contains no network client, CLI, credentials or cancellation mechanism. A lock serializes calls and initialization, so a blocked function can block other configured category calls; the wrapper provides no timeout guarantee.

## What the records contain

For each call, the app records the stage, exact input and schema hashes, declared model identity, bounded raw JSON and its digest, error status and local elapsed time. These records describe the function call, not raw HTTP traffic.

Invalid, nonfinite or over-budget responses are rejected. A bounded response remains in the record if later validation rejects it. A response rejected by the size/depth checks cannot be retained in full. Errors before invocation may have no call record. The app checks and snapshots supplied model identity and detects changes before or after a call; it cannot independently verify the provider's claim.

The existing modules still check the definition, membership, original source version, exact quotations, uncertainty, session, nonce, revision and expiry. The evidence checker sees its own source input without the membership answers. No proposal changes preferences until reviewed and applied. The combined endpoint is not a substitute for the three-call definition-first procedure.

## Offline checks

Run `python -m pytest -p no:cacheprovider tests/test_category_provider.py tests/test_staged_induction.py tests/test_induction_integration.py`. Disable external pytest plugin autoload for an isolated run.

These synthetic tests check selected software behavior, not model accuracy, real transport, browser interaction or full workflow readiness. The original r2 result of 831 passes belongs to that earlier source and was not rerun for this change. Frozen study outcomes remain unchanged.
