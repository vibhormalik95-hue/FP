# Current code walkthrough

## Category definition update, 11 November 2026

This successor recognizes the existing counted-list form `all three conditions:` without treating its structural labels as factual numbers. It also asks definition generation to preserve source modality and tense: purpose or capability does not establish an outcome that actually occurred. The instruction applies to each rationale and evidence reason under the exact definition, including its alternatives. It adds no semantic detector, automatic repair, approval or preferred category.

The latest v4 one-call attempt returned a primary definition and alternatives. Explicit primary selection worked; human evidence review rejected an unsupported capability-to-actual-use claim. No classification, audit, Apply or Undo followed. This successor has no live observation. Earlier hunger and Lunaria successes are bounded direct Python endpoint examples, not browser acceptance or general semantic accuracy. No recording is included.

The current profile is `current-definition-context-20261111`. Its only model-bound request change from the notes-r3 source is `payload.system`; descriptions, metadata, objectives, actions, inventory, schemas, category membership and audit instructions are unchanged. Both configuration templates remain incomplete with all six execution gates false. No approved runtime configuration is supplied.


11 November 2026. This describes the current implementation and the limits of its verification.

## From request to a reviewed feed change

1. `feedctrl/api.py` builds the app. `hosted_app.py` and `claude_personal_app.py` supply the configured provider while disabling local-model and trained-recommender execution. Manual category controls do not need inference.
2. For a new category, `staged_routes.py` coordinates definition preview and explicit definition review. `staged_induction.py` proposes and classifies the definition. `induction_integration.py` supplies the existing scoped inventory. Memberships and quoted evidence are checked in `evidence_audit.py` before final review and exact-ID Apply.
3. For indirect wording, `semantic_review.interpret_action` identifies the requested control and intent span. `indirect_grounding.py` matches that meaning to supplied metadata. Ambiguity, missing facts and unsupported quotes remain visible. A manually confirmed target is a separate path, not an automatic interpretation success.
4. `semantic_review.py` validates reviewed groups, source versions and eligible IDs before Apply. History supports reversing the change. These controls change eligibility without retraining the recommender.
5. `synthetic_drafts.py` validates fictional metadata and separates preview from admission. Removal and reviewed restoration operate on the retained draft. `shared_personal_factories` in `claude_personal_app.py` reuses the inference callable and call allowance; restoration does not need fresh generation.

## The Claude connection and latest change

`claude_personal.make_claude_personal_infer` validates the explicit runner configuration, builds bounded logical CLI requests, and checks reported model identity, one-turn completion and response schema. `_run_process` remains disabled by default. `windows_job_runner.py` and `windows_job_native.py` provide the optional bounded Windows runner; selecting it is not proof of containment in every environment.

Safe failure evidence in `claude_personal.py` retains allowlisted status fields and safe numeric usage/cost when supplied, with a response hash and known failure reason. Unknown fields and raw provider error text are excluded. Missing historical failure fields are not reconstructed.

`staged_routes.py` now separates clarification resolution from evidence approval. Choosing `review_primary` preserves the actual primary definition and alternatives and makes no model call. Cancellation consumes the token. Session binding, single use and expiry remain enforced. A resolved definition must still receive its own evidence review before classification, audit and final Apply review.

`source_constraints.py` ignores only complete, well-formed structural numbering outside quoted or bracketed content. Factual numbers and uncertain or malformed lists remain constraints. See [numbered constraints](numbered-source-constraints.md).

`tools/hosted_validation_current/driver.py` is the separate current helper. All six execution assertions remain false in its incomplete templates. The original `tools/hosted_validation` stays byte-for-byte historical evidence, including its known compatibility failures. Input descriptions, discovery objective and membership prompt are unchanged. The generic definition prompt now explicitly states the existing unknown-facts rule.

## What the checks establish

The [current helper guide](../tools/hosted_validation_current/README.md) lists the offline commands and results for this source. Guarded tests block model/provider imports, checkpoint reads, process creation and network calls. Authored replies test software mechanics, not semantic accuracy or live availability. Node tests execute handlers without a browser; the cached frontend build is a separate software check.

The real one-call Lunaria lifecycle is separate from the later category/hunger batch. The later category proposal stopped before membership or Apply and conflicts with the unknown criterion. Hunger recorded a reviewed food-preparation interpretation and Apply/Undo 8→5→8 through direct Python calls. See [current progress](current-progress.md) for evidence boundaries and preserved earlier failures.

## Still unfinished

This modality/counting successor has no fresh hosted observation; the preceding v4 attempt reached primary selection but was rejected at evidence review. The historical output cannot be resumed or repaired after the fact. The Windows broad offline suite retained 61 tests and 41 errors when the guard blocked kernel32 loading; a later seven-test portable subset passed with authored envelopes and an injected callable. Neither establishes native or whole-app acceptance. No browser acceptance or recorded demo is claimed. The laptop demo is excluded from the requested work; no new benchmark or human-annotation requirement is added here.

Definition review now shows the full cited field beside each exact quotation and reason, including clarification and resolved-primary review. Context is limited to the validated candidate scope; missing or mismatched context is shown as unavailable. It is a read-only display addition, outside model payloads and sealed proposals. Existing approval and expiry rules are unchanged. This fixes an API/UI context gap; the last headless review already displayed scoped records, so the gap did not cause its rejected model claim.
