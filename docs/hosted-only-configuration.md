# Hosted-only configuration and current limits

The hosted-only code was added on 9 November 2026. The 9 November implementation checks were offline. A later explicit-runner Lunaria check supplied bounded evidence from direct calls to the application’s Python methods; see [current progress](current-progress.md). It does not establish access to Astra, Sol 6.1 or Terra 6.1. The automatic personal Claude route also remains disabled; see [personal Claude status](../CLAUDE-PERSONAL-CANDIDATE.md).

## Creating the hosted app

`feedctrl.hosted_app.create_openai_hosted_app` creates one OpenAI Responses adapter and shares its callable, call allowance and records across indirect intent, category creation and fictional metadata generation. Setup requires an explicit API credential, exact model identifier, reasoning level, run allowance, verified durable spending guard and authorization. Construction neither discovers credentials nor calls a model. The adapter rejects redirects, automatic retries and mismatched returned model identities.

The category producer supplies `instructions`; the bridge maps that field exactly to transport `system`, keeps the other data and rejects ambiguous input. Category `model_revision` is the transport configuration digest, not a model-weight hash. Proposal/response schemas, evidence checks and review before Apply remain unchanged.

The existing spending policy permits two attempts with its specified Sol 6.1/medium configuration and US$0.50 maximum. A definition-first category workflow needs three calls; ordinary indirect intent needs two. The five-call offline test checks shared counting only. It does not authorize more paid calls or prove a paid run. The spending guard must not be changed or bypassed to fit a workflow.

## Local execution stays disabled

The hosted factory sets `allow_local_models=False` and `allow_local_recommender=False`. Local parser, profile, topic, steering and indirect-intent routes reject before inference or preference changes. Fictional metadata generation uses the optional configured hosted adapter. If no adapter is supplied, it rejects before inference while local models are disabled; it never falls back to a local model. Unconfigured category routes reject without falling back to Ollama, and a configured provider error cannot switch to a local model.

If a non-fixture configuration points to an existing local recommender checkpoint, construction rejects it before loading. It does not quietly choose another scorer. The current restriction covers local models without clearly separating the language interpreter from the historical SASRec recommender. A live configuration that needs SASRec therefore remains unresolved. Frozen experiments and results are unchanged.

Importing `feedctrl.api` no longer constructs an app. Accessing `feedctrl.api:app` still lazily creates the older local-enabled app. The legacy shell and PowerShell launchers are not hosted-only launchers and must not be used to bypass the current restriction.

Missing data or checkpoints retain the visibly labeled fixture/diagnostic behavior. A fixture run is not evidence that the fixed research recommender ran.

## Interface and unfinished verification

In hosted-only mode, the interface hides local choices, shows configured category methods and explains external data transmission. Fictional item generation is offered when the hosted draft adapter is configured and disabled when no permitted adapter exists. For the earlier hosted UI, the exact locked npm dependencies were installed after approval with lifecycle scripts disabled and a cache inside the writable project workspace. Vite 7.3.1 built that interface twice, producing the same three output files byte-for-byte. The newer fictional-draft change reused those dependencies and also produced matching builds. The matching built files are saved in `web/dist`. Neither build result establishes browser behavior or deployment.

Before a live demonstration, the project still needs a supported authenticated runtime, verified account access, authorized data and cost limits, and a configuration consistent with the unchanged recommender. The matching frontend also needs browser checks and the applicable regression checks. Publishing source does not complete any of those steps.

## Offline checks

Run `PYTHONPATH=.:tests python -m unittest -v test_hosted_app_offline` for the dependency-light suite. It uses in-process endpoint calls, synthetic records and authored replies, without an HTTP server, browser, sockets, credentials or model calls.

The suite covers both category paths, indirect intent, review/Apply/undo, a shared allowance, blocked local entry points, missing providers and the non-fixture checkpoint restriction. The added hosted-draft tests exercise the optional factory and fictional-item lifecycle with authored responses. These checks concern code behavior, not semantic accuracy or real hosted transport.

Independent review of the hosted-draft revision passed 92 guarded Python checks, including 3 ASGI checks for both hosted constructors and their request/session/isolation, lifecycle and failure behavior. All 7 frontend index checks passed after correcting the exact build pins. No blocking adapter defect remained in that review. No real model call was made in that independent review. The later Lunaria result is separate headless evidence; a later category proposal stopped before membership or Apply, while two hunger calls recorded a bounded food-preparation interpretation and direct Python Apply/Undo 8→5→8. These are separate exposed development examples, not browser/HTTP acceptance or general accuracy; see [current progress](current-progress.md).
