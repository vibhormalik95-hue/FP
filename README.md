# Natural language controls for short video recommendation

COMP 9500 project by Vibhor Malik, supervised by Dr Borna Noureddin.

The recent work focuses on three ways to control a feed: choosing categories manually, asking an LLM to propose a genuinely new category, and expressing a preference indirectly in ordinary language. The app keeps the recommender separate from these controls so that a model suggestion can be checked before it changes the feed.

## Current progress

- **Manual category controls:** implemented, with recorded examples of filtering and restoring a feed. These provide a baseline for checking what the language-based controls add.
- **New LLM-proposed categories:** implemented as definition, membership and evidence-review steps. A recorded example created “offline practice without account creation” across Coding, Design and Language, rather than renaming an existing category.
- **Indirect requests:** one recorded Claude example handled “Hide desk tools that would tie me to a wall socket.” It selected records that explicitly required mains power. The replies were copied between Claude and the app by an operator; this was not an automatic Claude connection. Other requests remain unsuccessful or ambiguous.
- **Fictional item descriptions:** a separate local-model example generated metadata for a fictional item. The hosted adapter shares the configured provider and call allowance. One real Claude Code Lunaria run completed preview, admission, removal and restoration through the application’s Python methods. It used one logical invocation; restoration made no additional model call. This was operator-reviewed, headless synthetic evidence, not an HTTP, browser or full-study result.

These are specific development examples, not a general accuracy result or proof that recommendations improve. See [current progress and remaining work](docs/current-progress.md) for the evidence and [the app guide](docs/app.md) for how the controls fit together.

**The default personal Claude launch remains disabled.** An explicitly selected runner can connect the installed CLI to the app. The bounded Lunaria run used that path; it does not verify every control path. The current configuration keeps local model and recommender execution disabled. The older setup instructions remain available for reproducing the earlier experiments. See [hosted configuration](docs/hosted-only-configuration.md) and [personal Claude status](CLAUDE-PERSONAL-CANDIDATE.md).

The early 11 November category call failed with CLI exit 1. A separate later hosted run proposed “Repaired and kept in use” but stopped for clarification before membership, evidence audit or Apply. Its exclusion of missing descriptions conflicts with the existing unknown-facts rule. The later hunger example selected the pasta, bread and salad descriptions and recorded Apply/Undo of 8→5→8 through Python application calls. These are separate exposed development examples, not browser acceptance or personal appetite predictions. The [11 November evidence summary](docs/evidence/2026-11-11/HOSTED-TWO-SCENARIO-SUMMARY.md) explains both outcomes and their limits.

## Category definition update, 11 November 2026

This successor recognizes the existing counted-list form `all three conditions:` without treating its structural labels as factual numbers. It also asks definition generation to preserve source modality and tense: purpose or capability does not establish an outcome that actually occurred. The instruction applies to each rationale and evidence reason under the exact definition, including its alternatives. It adds no semantic detector, automatic repair, approval or preferred category.

The latest v4 one-call attempt returned a primary definition and alternatives. Explicit primary selection worked; human evidence review rejected an unsupported capability-to-actual-use claim. No classification, audit, Apply or Undo followed. This successor has no live observation. Earlier hunger and Lunaria successes are bounded direct Python endpoint examples, not browser acceptance or general semantic accuracy. No recording is included.

The current profile is `current-definition-context-20261111`. Its only model-bound request change from the notes-r3 source is `payload.system`; descriptions, metadata, objectives, actions, inventory, schemas, category membership and audit instructions are unchanged. Both configuration templates remain incomplete with all six execution gates false. No approved runtime configuration is supplied.

## Where to start

- [Current code walkthrough](docs/current-code-walkthrough.md) and [requirement worksheet](docs/requirement-worksheet-2026-11-11.md): code locations, actual evidence and unfinished validation.
- [Current validation helper](tools/hosted_validation_current/README.md): separate current profile and guarded offline checks. The original helper is preserved as historical evidence.
- [Current progress](docs/current-progress.md): the recent requirements, observed examples and unfinished work.
- [App guide](docs/app.md): manual controls, category creation, indirect requests and review before applying a change.
- [Provider configuration](docs/model-provider-adapters.md) and [category configuration](docs/category-provider-configuration.md): what the code supports and what has not been tested live.
- [Fictional item drafts](docs/synthetic-item-drafts.md): what is generated, how review works and what remains unverified in the hosted path.
- [Source verification](docs/source-verification.md): frontend build files, checksums and release checks.
- Implementation: `feedctrl/`, `scripts/`, `tests/` and `web/`.

## Earlier research and dated records

The original study separates language translation from deterministic category enforcement on a fixed recommender. Experiment 1 found large exposure changes under the category policy, with weaker historical next-item ranking for boosts. The fresh Experiment 2 used 100 synthetic requests. Llama matched 76 of 100 model-generated reference commands; category control improved over item feedback, but conditional requests had no successes and next-item NDCG@10 was lower. The [results record](docs/ai-reference-e2-results-2026-10-14.md) retains the exact measures, denominators and reference history.

The following files are dated records. Their results and wording have been preserved; they should not be read as a description of everything that works in the latest app.

- [5 November demonstration](deliverables/2026-11-05-final-demo/README.md), including its [walkthrough](deliverables/2026-11-05-final-demo/WALKTHROUGH.md), [claim matrix](deliverables/2026-11-05-final-demo/CLAIM-MATRIX.md) and retained failures.
- [4 November proposal and deliverable audit](deliverables/2026-11-04-completion-review/PROJECT-COMPLETION-AUDIT.md), [seven-page paper review](deliverables/2026-11-04-completion-review/COMP9500-Current-Paper-Review.pdf) and [E1 replay limitation](deliverables/2026-11-04-completion-review/E1-REPLAY-DISCREPANCY.md). The paper covers the earlier study, not all the recent application work.
- [4 November synthetic-language study](deliverables/2026-11-04-prospective-evaluation/PROTOCOL-AND-RESULTS.md): 48/100 supported final profiles correct and 19/20 correct diagnostic clarifications. It does not replace E1 or revised E2 or establish an LLM recommendation benefit.
- [27 October pipeline walkthrough](deliverables/2026-10-27-feedback/PIPELINE-AND-CODE-WALKTHROUGH.md), [code and contribution map](deliverables/2026-10-27-feedback/CODE-MAP-AND-AI-ASSISTANCE.md), [five-condition examples](deliverables/2026-10-27-feedback/FIVE-CONDITION-EXAMPLES.md), and the later [4 November workflow](deliverables/2026-11-04-reviewed-workflow/README.md) and [professor-request audit](deliverables/2026-11-04-reviewed-workflow/CAPABILITY-AND-TRANSCRIPT-AUDIT.md).
- [19 October paper, presentation and progress packet](deliverables/2026-10-19/README-2026-10-19.md).

Study methods: [Experiment 1](docs/evaluation-protocol.md), [fresh Experiment 2](docs/ai-reference-e2-protocol-2026-10-14.md), [rubric](docs/ai-reference-e2-rubric-2026-10-14.md) and [research provenance](docs/academic-use.md). Saved evidence: [Experiment 2 index](docs/ai-reference-e2-evidence/README.md), [exposed practice run](docs/execution-2026-10-14.md) and `docs/evidence/2026-10-14/`. The earlier paper and presentation sources remain in `paper/research-paper-2026-10-19.tex`, `paper/references.bib` and `presentation-bcit/ai-reference-main.tex`.

The public screening records contain all 300 candidate request texts, including the selected wording. Complete cases, model-generated labels, responses, ranking outputs, SASRec checkpoints and caches are held in `COMP9500-Research-Project-Recovered.zip` (SHA-256 `fe9ef07dbb55902626fe5e5aab20261a57b6fb6e86832267e2249b052d587cc1`). Llama weights are separate. The [Windows and Colab guide](docs/windows-and-colab.md) and [local model guide](docs/LLM_RUNTIME.md) retain the historical reproduction steps. See [third-party notices](NOTICE.md) for data and software attribution.

Definition review now shows the full cited field beside each exact quotation and reason, including clarification and resolved-primary review. Context is limited to the validated candidate scope; missing or mismatched context is shown as unavailable. It is a read-only display addition, outside model payloads and sealed proposals. Existing approval and expiry rules are unchanged. This fixes an API/UI context gap; the last headless review already displayed scoped records, so the gap did not cause its rejected model claim.
