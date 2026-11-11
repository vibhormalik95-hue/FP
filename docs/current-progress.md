# Current progress and remaining work

## Category definition update, 11 November 2026

This successor recognizes the existing counted-list form `all three conditions:` without treating its structural labels as factual numbers. It also asks definition generation to preserve source modality and tense: purpose or capability does not establish an outcome that actually occurred. The instruction applies to each rationale and evidence reason under the exact definition, including its alternatives. It adds no semantic detector, automatic repair, approval or preferred category.

The latest v4 one-call attempt returned a primary definition and alternatives. Explicit primary selection worked; human evidence review rejected an unsupported capability-to-actual-use claim. No classification, audit, Apply or Undo followed. This successor has no live observation. Earlier hunger and Lunaria successes are bounded direct Python endpoint examples, not browser acceptance or general semantic accuracy. No recording is included.

The current profile is `current-definition-context-20261111`. Its only model-bound request change from the notes-r3 source is `payload.system`; descriptions, metadata, objectives, actions, inventory, schemas, category membership and audit instructions are unchanged. Both configuration templates remain incomplete with all six execution gates false. No approved runtime configuration is supplied.


This page describes the recent application work as of 11 November 2026. The recent work follows the three directions agreed at the last meeting: manual category controls with measurable effects, new LLM-proposed categories that feed the filter, and natural-language requests that map intended meaning to existing categories or tags. The project also explores fictional item metadata and stronger-model comparisons. The [dated requirement audit](../deliverables/2026-11-05-final-demo/CLAIM-MATRIX.md) records that distinction.

## Manual category controls

The app can filter by a selected category while leaving the recommender's scores unchanged. The recovered 6 November synthetic HTTP/state record shows Design exclusion reducing 8 items to 5 (31001, 31002 and 31008 removed), reviewed clear restoring 8, Undo of clear returning to 5, and reset restoring 8. The restored full feed was checked for equality. No new model generation occurred. This is not direct Undo of the original exclusion. This checks that the selected control is enforced and can be reversed. It does not show that an LLM is needed or that the resulting recommendations are better.

The earlier A–E benchmark remains available as a separate comparison of item feedback, explanations, category commands and profiles. Its results have not been changed by the recent interface work.

## Creating a new category

The model first proposes a category definition. The user reviews it before the model classifies the items. A separate evidence check then examines the source text before the final proposal can be applied.

The recorded category “offline practice without account creation” crossed the existing Coding, Design and Language categories and was absent from the category registry. Three local model calls produced the development example. Applying the reviewed group changed eligibility from 8 to 5; undo restored 8. See the [category demonstration](../deliverables/2026-11-05-staged-induction/README.md) and [integration record](../deliverables/2026-11-05-induction-integration/README.md).

This is evidence of a new category entering the filter, not a broad test of category quality. A quote can exist in the source and still be irrelevant to the proposed membership. The reviewer must check the meaning, missing information and excluded items, not just whether a quote matches.

## Understanding indirect requests

The professor asked about expressing a cooking-related preference without using the word “cooking”. The student then suggested hunger as an example. The implementation explores this kind of indirect meaning by matching supplied source items into reviewed groups, without rewriting the original category labels.

The request “Hide desk tools that would tie me to a wall socket” did not name Lighting, Stationery, Comfort or Timing. In the recorded example, Claude identified the exclusion request and selected the three records that explicitly required mains power. Battery-powered and manual items remained eligible, along with two items whose power source was unknown.

The application recorded eligibility changing 8 → 5 → 8 → 5 → 8 through apply, clear, undo-clear and undo-original-apply. The original A–E controls, source records and category mappings were preserved. The [5 November walkthrough](../deliverables/2026-11-05-final-demo/README.md) contains the full evidence.

An operator copied the requests and replies between the app and two fresh Claude browser chats with the observed Opus 5.5 Medium selector. This was a real model-assisted example, but not an automatic API integration or a held-out accuracy test. The default launch remains disabled; a separate explicit runner path now has bounded headless evidence, described below.

The historical local-model cooking/hunger request did not produce a successful automatic selection. Later code displays the model's unresolved alternatives and lets the user explicitly confirm a concrete target. That clarification path has offline tests; it does not turn the earlier failed request into a success. See the [clarification change](../deliverables/2026-11-06-clarification-development/README.md) and [confirmed-target change](../deliverables/2026-11-06-confirmed-target-budget/README.md).

## Fictional item metadata

A separate recorded local-model example created fictional Lunaria Pod metadata, which could be reviewed, admitted to a separate feed, removed and restored. It created no real video or factual source record. The separate feed gives every item a neutral score and does not test trained cold-start recommendation quality.

The latest source adds a hosted adapter for this feature. Both hosted app factories reuse their existing provider and shared call allowance. The generation request contains the drafting instruction, fictional brief and schema, without sending the catalogue or falling back to a local model. Independent review passed 92 guarded Python checks, including 3 ASGI checks covering both hosted constructors and the request, session, isolation, lifecycle and error-handling paths. All 7 frontend index checks passed after the build pins were corrected. These checks use authored replies, not real generated output. A later real Claude Code run completed the fictional Lunaria preview/admit/remove/restore lifecycle through the application’s Python methods. It made one logical invocation, targeted and reported Fable5.2, and requested max effort; effective effort was not independently established. Restore replayed the removed record without another model call. The default launcher remains disabled; this run used an explicitly selected runner. This is operator-reviewed headless synthetic evidence, not browser acceptance or trained recommendation evidence. The [public-safe receipt](evidence/2026-11-11/FABLE-LUNARIA-PUBLIC-SAFE-SUMMARY.json) records the limits. Without a configured adapter and with local models disabled, the endpoint still returns HTTP 403 before inference. See [fictional item drafts](synthetic-item-drafts.md).

## Stronger-model comparison

The [saved comparison summary](../deliverables/2026-11-05-final-demo/IMMEDIATE-PROFESSOR-PACKET.md) reports Claude matching 6/6 tasks and 36/36 item dispositions in a standalone six-case batch. The batch contained two proposals and four abstentions. Llama and the later Qwen extension failed strict JSON validation, leaving semantic answers missing; those failures are not a measured zero semantic-accuracy score.

This was a small synthetic comparison with different transports and settings. It was not an automatic app-to-app comparison or a general ranking of models. The original scoring and sealed archives remain unchanged.

## Latest validation and remaining work

The early 11 November category attempt failed with CLI exit 1 before definition or Apply. Its missing failure details remain unknown in the [retained failure record](evidence/2026-11-11/SAFE-FAILURE-SUMMARY.json). A later separate batch proposed “Repaired and kept in use” but stopped for clarification. No membership, evidence audit or Apply occurred, and its missing-description exclusion conflicts with the existing unknown-facts rule. Current code offers explicit unchanged-primary selection followed by separate evidence review, states the existing unknown rule in the definition prompt, and corrects structural numbering without removing factual digits. These changes do not repair or approve that recorded proposal.

In that later batch, the exact request “I'm not hungry, remove all the stuff that makes me hungry.” was interpreted as food preparation. Two calls selected pasta, bread and salad (81001, 81003 and 81006). Scripted reviews and direct Python endpoints recorded Apply/Undo 8→5→8, not browser or HTTP execution. Two undescribed records remain unknown. This supports the reviewed interpretation, not personal appetite truth or general accuracy. The receipts report Fable 5.2 with max effort requested; effective effort is unknown and CLI estimates are not verified billing. See the [two-scenario summary](evidence/2026-11-11/HOSTED-TWO-SCENARIO-SUMMARY.md).

A later manual 36→34→36 check is reported in earlier project summaries but is not independently verified here. It is not used as primary evidence. The latest Windows offline run reported 61 tests and 41 errors because the guard blocked `ctypes.dlopen` during the Windows import of kernel32. No model ran and no guard changed. That broad-suite failure remains separate from the passing cloud suite. A later portable diagnostic subset passed seven tests on Windows, Python 3.14.0, at 02:42:26–27 UTC on 11 November. It tested actual adapter/helper behavior with authored envelopes and an injected callable. Its six guard events were deliberate audit probes, not operations. It does not verify native containment, whole-app behavior or live-provider use. The relocated repository variant passed its focused cloud check but has not been rerun on Windows. See the [portable diagnostic result](evidence/2026-11-11/WINDOWS-PORTABLE-DIAGNOSTIC-SUMMARY.json). No browser acceptance result is claimed. Local model and trained recommender execution remain disabled for these checks.

The current default aggregate passed 176 guarded tests. Runtime/privacy/mocked-Windows checks passed 62 additional identities and integration preflight passed two, for 240 distinct successful Python tests. The historical helper still has eight passes and eight expected failures. The scoped definition context is now displayed beside the exact quotation and reason. All 59 Node checks passed using existing lock-matched cached dependencies; the Vite build reproduced the context patch author's assets exactly. These are offline UI checks, not browser acceptance. Earlier missing-esbuild failures remain retained as historical records. See the [validation guide](../tools/hosted_validation_current/README.md).

## Research limitations

The recorded examples do not establish general reliability for nuanced requests or new categories, improved recommendation quality, or user satisfaction. These are limits on the conclusions, not additional requirements for finishing the current implementation. The historical next-item results and negative language results remain part of the project.

The [hosted configuration guide](hosted-only-configuration.md) and [personal Claude status](../CLAUDE-PERSONAL-CANDIDATE.md) describe these implementation limits. Offline tests and a successful frontend build check software behavior; they do not replace live model or browser evidence. The dated studies, failures and sealed records remain unchanged.

The [current validation guide](../tools/hosted_validation_current/README.md) distinguishes software tests from model evidence. This modality/counting successor has no fresh hosted observation; the preceding v4 attempt reached primary selection but was rejected at evidence review. No demo recording is supplied. The original reports and failed model outputs remain unchanged.

Definition review now shows the full cited field beside each exact quotation and reason, including clarification and resolved-primary review. Context is limited to the validated candidate scope; missing or mismatched context is shown as unavailable. It is a read-only display addition, outside model payloads and sealed proposals. Existing approval and expiry rules are unchanged. This fixes an API/UI context gap; the last headless review already displayed scoped records, so the gap did not cause its rejected model claim.
