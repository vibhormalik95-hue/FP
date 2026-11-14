# Natural language controls for short video recommendation

COMP 9500 project by Vibhor Malik, supervised by Dr Borna Noureddin.

This project studies how people can control a short-video feed through category choices and natural-language requests. Language interpretation is separate from deterministic filtering: proposed changes are reviewed before they affect the feed, and applied changes can be reversed.

## Application

The recent application work covers three controls:

- **Manual category filtering:** select a category, inspect the resulting feed and restore the previous state.
- **New categories from natural language:** review a proposed definition, item membership and supporting source evidence before applying the category to the filter.
- **Indirect requests:** translate a preference that does not name an existing category into a reviewable selection of source items.

Start with the [bundled demonstration commands](docs/app.md#start-the-bundled-demonstration). The [app guide](docs/app.md) explains the workflow. The [code walkthrough](docs/current-code-walkthrough.md) and [requirement worksheet](docs/requirement-worksheet-2026-11-11.md) connect requirements to implementation and evidence.

Recorded development examples establish particular behaviors, not general language accuracy or improved recommendation quality. Some examples used operator-copied model replies or direct Python calls rather than the complete browser workflow. End-to-end acceptance of the current hosted new-category flow remains unfinished in the evidence reviewed for this overview. See the explicitly dated [progress record](docs/current-progress.md) and [validation guide](tools/hosted_validation_current/README.md) for successful examples, retained failures and remaining checks. A configured connector or passing offline test is not a substitute for a successful application run.

## Paper and evaluation

The original study separates language translation from category enforcement on a fixed recommender. Experiment 1 found substantial exposure changes under category policies, with weaker historical next-item ranking for boosts. Fresh Experiment 2 used 100 synthetic requests: Llama matched 76 of 100 model-generated reference commands; category control improved over item feedback, but conditional requests had no successes and next-item NDCG@10 was lower. These results are separate from the later application examples.

- [Paper source](paper/research-paper-2026-10-19.tex) and [references](paper/references.bib)
- [Experiment 1 protocol](docs/evaluation-protocol.md)
- [Fresh Experiment 2 protocol](docs/ai-reference-e2-protocol-2026-10-14.md), [rubric](docs/ai-reference-e2-rubric-2026-10-14.md) and [results](docs/ai-reference-e2-results-2026-10-14.md)
- [Research provenance and limitations](docs/academic-use.md)
- [Proposal and deliverable audit](deliverables/2026-11-04-completion-review/PROJECT-COMPLETION-AUDIT.md)

The published results, denominators, failures and model-generated reference history are preserved. The examples do not establish real-user satisfaction or a general recommendation benefit.

## Running and inspecting the code

Implementation lives in `feedctrl/`, `scripts/`, `tests/` and `web/`.

- [Hosted configuration](docs/hosted-only-configuration.md)
- [Provider adapters](docs/model-provider-adapters.md) and [category configuration](docs/category-provider-configuration.md)
- [Source and build verification](docs/source-verification.md)
- [Historical Windows and Colab setup](docs/windows-and-colab.md) and [local model setup](docs/LLM_RUNTIME.md)
- [Separate fictional-item metadata experiment](docs/synthetic-item-drafts.md)

Configuration and validation records distinguish installed code from enabled execution and actual model observations. Follow the relevant configuration guide rather than assuming a default launch is enabled.

## Evidence and reproducibility

Dated records are retained without rewriting their outcomes:

- [5 November demonstration and claim matrix](deliverables/2026-11-05-final-demo/README.md)
- [4 November synthetic-language evaluation](deliverables/2026-11-04-prospective-evaluation/PROTOCOL-AND-RESULTS.md)
- [27 October pipeline walkthrough](deliverables/2026-10-27-feedback/PIPELINE-AND-CODE-WALKTHROUGH.md)
- [19 October paper and presentation packet](deliverables/2026-10-19/README-2026-10-19.md)
- [Experiment 2 evidence index](docs/ai-reference-e2-evidence/README.md) and [separate exposed practice run](docs/execution-2026-10-14.md)

The public screening records retain all 300 candidate request texts, including selected wording. Complete cases, model-generated labels, responses, ranking outputs, SASRec checkpoints and caches are held in `COMP9500-Research-Project-Recovered.zip` (SHA-256 `fe9ef07dbb55902626fe5e5aab20261a57b6fb6e86832267e2249b052d587cc1`). Llama weights are separate. See [third-party notices](NOTICE.md) for data and software attribution.