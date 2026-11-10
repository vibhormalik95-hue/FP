# Natural language controls for short video recommendation

COMP 9500 project by Vibhor Malik, supervised by Dr Borna Noureddin.

The recent work focuses on three ways to control a feed: choosing categories manually, asking an LLM to propose a genuinely new category, and expressing a preference indirectly in ordinary language. The app keeps the recommender separate from these controls so that a model suggestion can be checked before it changes the feed.

## Current progress

- **Manual category controls:** implemented, with recorded examples of filtering and restoring a feed. These provide a baseline for checking what the language-based controls add.
- **New LLM-proposed categories:** implemented as definition, membership and evidence-review steps. A recorded example created “offline practice without account creation” across Coding, Design and Language, rather than renaming an existing category.
- **Indirect requests:** one recorded Claude example handled “Hide desk tools that would tie me to a wall socket.” It selected records that explicitly required mains power. The replies were copied between Claude and the app by an operator; this was not an automatic Claude connection. Other requests remain unsuccessful or ambiguous.
- **Fictional item descriptions:** a separate local-model example generated metadata for a fictional item. The latest source adds a hosted-generation adapter using the existing shared provider and call allowance. Independent offline and ASGI checks pass, but live generation through the hosted app has not been verified.

These are specific development examples, not a general accuracy result or proof that recommendations improve. See [current progress and remaining work](docs/current-progress.md) for the evidence and [the app guide](docs/app.md) for how the controls fit together.

**The automatic personal Claude launch is still disabled.** The installed Claude Code CLI is the intended runtime, but it has not yet been verified through the app. The current configuration keeps local model and recommender execution disabled. The older setup instructions remain available for reproducing the earlier experiments. See [hosted configuration](docs/hosted-only-configuration.md) and [personal Claude status](CLAUDE-PERSONAL-CANDIDATE.md).

## Where to start

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
