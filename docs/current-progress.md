# Current progress and remaining work

This page describes the recent application work as of 10 November 2026. The recent work follows the three directions agreed at the last meeting: manual category controls with measurable effects, new LLM-proposed categories that feed the filter, and natural-language requests that map intended meaning to existing categories or tags. The project also explores fictional item metadata and stronger-model comparisons. The [dated requirement audit](../deliverables/2026-11-05-final-demo/CLAIM-MATRIX.md) records that distinction.

## Manual category controls

The app can filter by a selected category while leaving the recommender's scores unchanged. A recorded development example reduced the eligible set from 8 to 5 and restored it. This checks that the selected control is enforced and can be reversed. It does not show that an LLM is needed or that the resulting recommendations are better.

The earlier A–E benchmark remains available as a separate comparison of item feedback, explanations, category commands and profiles. Its results have not been changed by the recent interface work.

## Creating a new category

The model first proposes a category definition. The user reviews it before the model classifies the items. A separate evidence check then examines the source text before the final proposal can be applied.

The recorded category “offline practice without account creation” crossed the existing Coding, Design and Language categories and was absent from the category registry. Three local model calls produced the development example. Applying the reviewed group changed eligibility from 8 to 5; undo restored 8. See the [category demonstration](../deliverables/2026-11-05-staged-induction/README.md) and [integration record](../deliverables/2026-11-05-induction-integration/README.md).

This is evidence of a new category entering the filter, not a broad test of category quality. A quote can exist in the source and still be irrelevant to the proposed membership. The reviewer must check the meaning, missing information and excluded items, not just whether a quote matches.

## Understanding indirect requests

The professor asked about expressing a cooking-related preference without using the word “cooking”. The student then suggested hunger as an example. The implementation explores this kind of indirect meaning by matching supplied source items into reviewed groups, without rewriting the original category labels.

The request “Hide desk tools that would tie me to a wall socket” did not name Lighting, Stationery, Comfort or Timing. In the recorded example, Claude identified the exclusion request and selected the three records that explicitly required mains power. Battery-powered and manual items remained eligible, along with two items whose power source was unknown.

The application recorded eligibility changing 8 → 5 → 8 → 5 → 8 through apply, clear, undo-clear and undo-original-apply. The original A–E controls, source records and category mappings were preserved. The [5 November walkthrough](../deliverables/2026-11-05-final-demo/README.md) contains the full evidence.

An operator copied the requests and replies between the app and two fresh Claude browser chats with the observed Opus 5.5 Medium selector. This was a real model-assisted example, but not an automatic API integration or a held-out accuracy test. The automatic personal Claude launch remains disabled.

The cooking/hunger request did not produce a successful automatic selection. Later code displays the model's unresolved alternatives and lets the user explicitly confirm a concrete target. That clarification path has offline tests; it does not turn the earlier failed request into a success. See the [clarification change](../deliverables/2026-11-06-clarification-development/README.md) and [confirmed-target change](../deliverables/2026-11-06-confirmed-target-budget/README.md).

## Fictional item metadata

A separate recorded local-model example created fictional Lunaria Pod metadata, which could be reviewed, admitted to a separate feed, removed and restored. It created no real video or factual source record. The separate feed gives every item a neutral score and does not test trained cold-start recommendation quality.

The latest source adds a hosted adapter for this feature. Both hosted app factories reuse their existing provider and shared call allowance. The generation request contains the drafting instruction, fictional brief and schema, without sending the catalogue or falling back to a local model. Independent review passed 92 guarded Python checks, including 3 ASGI checks covering both hosted constructors and the request, session, isolation, lifecycle and error-handling paths. All 7 frontend index checks passed after the build pins were corrected. These checks use authored replies, not real generated output. Live generation through the app remains unverified, and the personal Claude launcher is still disabled. Without a configured adapter and with local models disabled, the endpoint still returns HTTP 403 before inference. See [fictional item drafts](synthetic-item-drafts.md).

## Stronger-model comparison

The [saved comparison summary](../deliverables/2026-11-05-final-demo/IMMEDIATE-PROFESSOR-PACKET.md) reports Claude matching 6/6 tasks and 36/36 item dispositions in a standalone six-case batch. The batch contained two proposals and four abstentions. Llama and the later Qwen extension failed strict JSON validation, leaving semantic answers missing; those failures are not a measured zero semantic-accuracy score.

This was a small synthetic comparison with different transports and settings. It was not an automatic app-to-app comparison or a general ranking of models. The original scoring and sealed archives remain unchanged.

## Remaining implementation work

- A working, verified connection from the app to the installed Claude Code CLI, which is the intended runtime. The personal launcher remains disabled; small CLI compatibility checks did not test the full application.
- Live verification of the new hosted fictional-metadata path, including generation and the review/admission lifecycle.
- Live verification of the hosted workflow and a configuration that respects the restriction on the local recommender. Fixture data and a diagnostic scorer do not demonstrate the fixed research recommender.

## Research limitations

The recorded examples do not establish general reliability for nuanced requests or new categories, improved recommendation quality, or user satisfaction. These are limits on the conclusions, not additional requirements for finishing the current implementation. The historical next-item results and negative language results remain part of the project.

The [hosted configuration guide](hosted-only-configuration.md) and [personal Claude status](../CLAUDE-PERSONAL-CANDIDATE.md) describe these implementation limits. Offline tests and a successful frontend build check software behavior; they do not replace live model or browser evidence. The dated studies, failures and sealed records remain unchanged.
