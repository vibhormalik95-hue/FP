# Application code walkthrough

This guide maps the published application to its research controls. It is not a test receipt. See [current progress](current-progress.md) for dated results and unfinished acceptance, and the [11 November requirement worksheet](requirement-worksheet-2026-11-11.md) for the historical transcript-to-evidence map.

## From request to a reviewed feed change

1. `feedctrl/api.py` builds the app. `hosted_app.py` and `claude_personal_app.py` supply the configured provider while disabling local-model and trained-recommender execution. Manual category controls do not need inference.
2. For a new category, `staged_routes.py` coordinates definition preview and explicit definition review. `staged_induction.py` proposes and classifies the definition. `induction_integration.py` supplies the existing scoped inventory. Memberships and quoted evidence are checked in `evidence_audit.py` before final review and exact-ID Apply.
3. For indirect wording, `semantic_review.interpret_action` identifies the requested control and intent span. `indirect_grounding.py` matches that meaning to supplied metadata. Ambiguity, missing facts and unsupported quotes remain visible. A manually confirmed target is a separate path, not an automatic interpretation success.
4. `semantic_review.py` validates reviewed groups, source versions and eligible IDs before Apply. History supports reversing the change. These controls change eligibility without retraining the recommender.
5. `synthetic_drafts.py` validates fictional metadata and separates preview from admission. Removal and reviewed restoration operate on the retained draft. `shared_personal_factories` in `claude_personal_app.py` reuses the inference callable and call allowance; restoration does not need fresh generation.

## Model transport and definition review

`claude_personal.make_claude_personal_infer` validates the explicit runner configuration, builds bounded logical CLI requests, and checks reported model identity, one-turn completion and response schema. `_run_process` remains disabled by default. `windows_job_runner.py` and `windows_job_native.py` provide the optional bounded Windows runner; selecting it is not proof of containment in every environment.

Safe failure evidence in `claude_personal.py` retains allowlisted status fields and safe numeric usage/cost when supplied, with a response hash and known failure reason. Unknown fields and raw provider error text are excluded. Missing historical failure fields are not reconstructed.

`staged_routes.py` now separates clarification resolution from evidence approval. Choosing `review_primary` preserves the actual primary definition and alternatives and makes no model call. Cancellation consumes the token. Session binding, single use and expiry remain enforced. A resolved definition must still receive its own evidence review before classification, audit and final Apply review.

`source_constraints.py` ignores only complete, well-formed structural numbering outside quoted or bracketed content. Factual numbers and uncertain or malformed lists remain constraints. See [numbered constraints](numbered-source-constraints.md).

`tools/hosted_validation_current/driver.py` is the separate validation helper. Its guide identifies dated configurations and checks; template flags alone do not establish runtime availability. The original `tools/hosted_validation` remains historical evidence. The definition prompt states the unknown-facts rule.

## What the checks establish

The [current helper guide](../tools/hosted_validation_current/README.md) lists the offline commands and results for this source. Guarded tests block model/provider imports, checkpoint reads, process creation and network calls. Authored replies test software mechanics, not semantic accuracy or live availability. Node tests execute handlers without a browser; the cached frontend build is a separate software check.

The real one-call Lunaria lifecycle is separate from the later category/hunger batch. The later category proposal stopped before membership or Apply and conflicts with the unknown criterion. Hunger recorded a reviewed food-preparation interpretation and Apply/Undo 8→5→8 through direct Python calls. See [current progress](current-progress.md) for evidence boundaries and preserved earlier failures.

## Acceptance evidence

The [progress record](current-progress.md) separates current observations from historical failures and lists remaining acceptance work. The [11 November requirement worksheet](requirement-worksheet-2026-11-11.md) preserves the older runtime and verification snapshot. Neither an offline test nor a direct Python call is a browser demonstration.

Definition review displays the full cited field beside each quotation and reason. Missing or mismatched context is shown as unavailable. This display does not change model payloads, sealed proposals, approval or expiry rules, and does not establish that a quotation supports the model's claim.
