# Natural language controls for short video recommendation

COMP 9500 research project by Vibhor Malik, supervised by Dr Borna Noureddin. This repository contains the offline benchmark implementation, methods, compact evidence and current [paper, presentation and progress note](deliverables/2026-10-19/README-2026-10-19.md).

The study separates language translation from deterministic category enforcement on a fixed recommender. Experiment 1 shows large exposure changes under the category policy, alongside weaker historical next-item ranking for boosts. The fresh Experiment 2 benchmark uses 100 synthetic requests. Llama matches 76 of 100 model-generated reference commands; measured category control improves over item feedback, while conditional requests have no successes and next-item NDCG@10 is lower. The [results record](docs/ai-reference-e2-results-2026-10-14.md) gives exact measures, denominators and reference provenance.

## Project files

| Purpose | Files |
|---|---|
| Study methods | [Experiment 1 protocol](docs/evaluation-protocol.md), [fresh Experiment 2 protocol](docs/ai-reference-e2-protocol-2026-10-14.md), [rubric](docs/ai-reference-e2-rubric-2026-10-14.md), [research provenance](docs/academic-use.md) |
| Saved evidence | [Experiment 2 index](docs/ai-reference-e2-evidence/README.md), [exposed practice record](docs/execution-2026-10-14.md), `docs/evidence/2026-10-14/` |
| Implementation | `feedctrl/`, `scripts/`, `tests/`, and the `web/` source |
| Reproduction | [Windows and Colab](docs/windows-and-colab.md), [model runtime](docs/LLM_RUNTIME.md), [app guide](docs/app.md) |
| Publication sources | `paper/research-paper-2026-10-19.tex`, `paper/references.bib`, `presentation-bcit/ai-reference-main.tex` |

The public screening records include all 300 candidate request texts, including the selected wording. Complete cases, model-generated labels, responses, ranking outputs, SASRec checkpoints and caches are in the separate research archive `COMP9500-Research-Project-Recovered.zip` (SHA-256 `fe9ef07dbb55902626fe5e5aab20261a57b6fb6e86832267e2249b052d587cc1`). Llama weights must be downloaded separately. See the [reproduction guide](docs/windows-and-colab.md) and [notices](NOTICE.md).
