# Hosted validation: current source and historical profile

## Current source and manual setup

The application source now has later reviewed changes to its definition prompt,
literal-reference handling and bounded review window. The 11 November scaffold
below pins the earlier definition prompt in `inputs/01-category-discovery/first-model-input.json`.
Its exact first-request check therefore rejects the revised application's prompt
before a runner call. Keep the historical input and manifest unchanged; neither its
saved results nor its incomplete configuration are a runnable current profile.

For offline verification, use a Python environment with the project dependencies
from `pyproject.toml` installed, then run from the project root:

```text
python -m unittest discover -s tests -p "test_*_regression_offline.py"
```

These tests use synthetic data and fake runners. They do not call a model, start a
server or demonstrate semantic accuracy. For the interactive workflow, follow the
[app guide](../../docs/app.md) and [hosted configuration](../../docs/hosted-only-configuration.md)
using a separately reviewed provider, data and runtime configuration. The personal
Claude adapter has no enabled default process launcher; a reviewed runner must be
supplied explicitly. This repository does not provide a current ready-to-run hosted
category scaffold or establish hosted acceptance. Review the definition, every
membership and its evidence before Apply, and review Undo separately.

The following sections describe the **11 November historical profile** and its
dated observations. Their pins, suggested commands and test counts apply to that
matching historical source, not to the revised application source above. To inspect
the scaffold as published immediately before this integration, use a separate checkout
of `bef8e1afea5222a35e3a89be722b15d2424c30be`. Reproducing a dated test count requires
the exact source identified in the profile provenance, not merely that later checkout.
Do not overwrite frozen inputs or reuse a consumed run.

## Historical profile: 11 November 2026

**Offline readiness only. No fresh hosted batch is authorized.** Both configuration templates are incomplete and all six execution gates remain false. No approved configuration, authorization receipt or consumed marker is supplied. Do not reuse any previous configuration/receipt/consumed marker, import a previous response, or resume an ended run. A new authorized run requires separate review of the exact new driver, source, input pins, current runtime/containment, cost estimate and permissions. Existing spend thresholds, bounded calls, Fable 5.2/max, no retry/fallback and containment requirements remain unchanged.

This separate package derives from `../hosted_validation`, which remains byte-for-byte historical evidence. Historical helper tests still reject the corrected category prompt before runner invocation; their old success reports do not apply to the new source. This profile does not overwrite or relabel them.

## Category definition update, 11 November 2026

This successor recognizes the existing counted-list form `all three conditions:` without treating its structural labels as factual numbers. It also asks definition generation to preserve source modality and tense: purpose or capability does not establish an outcome that actually occurred. The instruction applies to each rationale and evidence reason under the exact definition, including its alternatives. It adds no semantic detector, automatic repair, approval or preferred category.

The latest v4 one-call attempt returned a primary definition and alternatives. Explicit primary selection worked; human evidence review rejected an unsupported capability-to-actual-use claim. No classification, audit, Apply or Undo followed. This successor has no live observation. Earlier hunger and Lunaria successes are bounded direct Python endpoint examples, not browser acceptance or general semantic accuracy. No recording is included.

The current profile is `current-definition-context-20261111`. Its only model-bound request change from the notes-r3 source is `payload.system`; descriptions, metadata, objectives, actions, inventory, schemas, category membership and audit instructions are unchanged. Both configuration templates remain incomplete with all six execution gates false. No approved runtime configuration is supplied.

Review notes, all facts/unknowns and provenance are operator-only material. They are not inserted into model requests. There is no desired category or fixed target set. The old `Repaired and kept in use` output is historical and its missing-description exclusion remains inconsistent with the unknown contract; this profile neither repairs nor approves it. Future operators must review actual fresh output.

## Separate explicit choices

1. The application generates a fresh definition once. Invalid/no-primary/no-match remains terminal.
2. A resolvable clarification displays the complete exact response: candidate label, definition, rationale, source evidence, every alternative, model reason, notice/question and model calls, alongside all eight metadata records and full facts/unknowns notes. The operator must enter exactly `review_primary` (unchanged primary only) or `cancel`. A generic APPROVE, boolean, empty response or other string cannot select a meaning. Alternatives are never silently selected or stripped.
3. Resolution submits only user ID, current server token and exact choice through the same session. It performs no model call. Cancel consumes the token and ends. Choosing the primary produces a distinct ordinary definition token; it is NOT evidence approval or Apply.
4. A separate APPROVE after viewing the exact resolved definition, original clarification and resolution record allows classification with `evidence_reviewed:true`. Full tri-state membership and blind evidence assessment remain unchanged, within the three-call category cap.
5. Separate explicit reviews still gate Apply and Undo. No automatic target/semantic score is asserted.

The 11 November profile enforced single-use, monotonic 300-second expiry and session/user/request/source/inventory/revision/nonce binding. Delays, stale state or consumed tokens failed closed; the helper did not recover by generating or resuming automatically. The revised source keeps the initial 300-second review window and uses a separately bounded in-flight classification window; its other binding and review checks remain in force.

## Historical offline checks

The following commands describe the historical profile and are not the current-source regression command above. Historical aggregate from its matching source root: `PYTHONDONTWRITEBYTECODE=1 python tools/hosted_validation_current/run_guarded.py .`

Historical focused helper only: `PYTHONDONTWRITEBYTECODE=1 python tools/hosted_validation_current/run_guarded.py . test_current_driver`

The default current aggregate deliberately does not import historical `test_driver`. To reproduce its retained compatibility failure separately: `PYTHONDONTWRITEBYTECODE=1 python tools/hosted_validation/run_guarded.py . test_driver`. That historical suite is 8 passed / 8 failed against the corrected prompt, not green. Neither aggregate is the full legacy pytest suite; pytest is absent in this environment. These commands run authored offline tests only, never a hosted invocation.

These are authored callable fixtures with blocked network, subprocess, model/provider imports and checkpoint reads. They test mechanics only, not real semantic performance, native Windows behavior or actual hosted availability. The results below describe this combined source; historical reports remain separate. The original audit guards are unchanged; the default module list includes the current helper, category-resolution, cited-context, numeric/apostrophe, modality and UI-pin regressions.

## Successor offline checks, 11 November 2026

- Current aggregate: 176 successful unittest identities, including the cited-context, apostrophe, counted-condition and modality regressions and the existing 19 numeric-scanner checks. Zero guard events.
- Runtime/privacy/mocked-Windows selection: 62 additional successful identities, zero guard events. No native Windows backend ran.
- Separate integration preflight: two additional successful identities. Actual adapter output reproduces the pinned first request byte-for-byte; both templates have consistent source, driver and input pins and fail closed at the six false gates.
- These selections contain 240 distinct successful unittest identities. They are software checks, not model observations. The two integration checks remain with the verification receipt; the default command reproduces the 176 included aggregate checks.
- The historical helper still has eight passes and eight expected failures. Its files and previous failure records remain unchanged; this successor does not relabel them green.
- The integrated context UI passed 59 Node checks using the existing lock-matched dependency cache. Vite transformed 32 modules and reproduced the separately built context assets exactly. No package installation, browser or server ran. The prior missing-esbuild failure remains retained with its original candidate.

The driver changes only its profile identifier and input-manifest pin. Model, effort, call caps, timeouts, spending rules and approval requirements are unchanged. Earlier counts in dated evidence describe earlier artifacts and are not added to these totals.

The R2 scanner handles in-word apostrophes consistently inside and outside quotes. A trailing apostrophe after a word in a single-quote context can be a possessive or closing delimiter, so the structural-number exception is disabled for that input. This can conservatively retain genuine list labels, including a list with a single-quoted body such as `'ready'`; it never discards ambiguous factual digits. The current notes test explicitly reads UTF-8, and the source-verification guide states the manifest path base accurately. These changes do not alter model-bound inputs or approval rules.

Definition review now shows the full cited field beside each exact quotation and reason, including clarification and resolved-primary review. Context is limited to the validated candidate scope; missing or mismatched context is shown as unavailable. It is a read-only display addition, outside model payloads and sealed proposals. Existing approval and expiry rules are unchanged. This fixes an API/UI context gap; the last headless review already displayed scoped records, so the gap did not cause its rejected model claim.
