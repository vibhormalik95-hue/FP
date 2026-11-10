# Natural language controls for short video recommendation

> **Current personal candidate: do not run the historical local app, model or recommender.** No local model or recommender execution is authorized for this candidate. Do not use the historical commands, launchers or scripts below as a workaround. The current hosted personal launch is disabled pending real validation; these historical instructions and results do not establish that validation. See [candidate status](CLAUDE-PERSONAL-CANDIDATE.md) and [hosted-only configuration](docs/hosted-only-configuration.md).

COMP 9500 research project by Vibhor Malik, supervised by Dr Borna Noureddin. This repository contains the offline benchmark implementation, methods, compact evidence and professor-review materials.

## Personal UI publication note

The personal app serves the verified `web/dist/` build, but `.gitignore` excludes it. An ordinary Git add may therefore omit the UI. Deliberately include the exact verified build in the eventual publication through the chosen publication process, and inspect the resulting Git index before publishing. The following check reads the index only: it neither stages files nor uploads anything. It requires exactly the three paths and SHA-256 values pinned in `scripts/check_personal_ui_index.py`, and compares the actual staged blob bytes, not merely working-tree files. From the repository root in Windows PowerShell, run:

```powershell
C:\Python314\python.exe scripts\check_personal_ui_index.py
```

The check uses Python's standard library and Git; it also runs on other platforms with Python 3 and Git. Run it only after the publication index is prepared. It does not itself prepare the index.

The `PERSONAL-AUTH-SHA256SUMS.txt` receipt is historical and remains unchanged. In this combined reviewed v6 source candidate, the receipt-covered paths that differ or are absent are `feedctrl/claude_personal.py`, `feedctrl/windows_job_native.py`, `feedctrl/windows_job_runner.py`, `web/src/personalApi.js`, `web/dist/index.html`, `web/dist/assets/index-DTzE0yVt.js`, `tests/test_windows_job_runner_offline.py`, `pyproject.toml`. The old `web/dist/assets/index-DTzE0yVt.js` is replaced by `web/dist/assets/index-CZ9L8i2t.js`; the staged-UI check pins the new error-handling build. `pyproject.toml` now declares `jsonschema` in the test extra. Use [`CURRENT-SOURCE-SHA256.txt`](CURRENT-SOURCE-SHA256.txt), beside this README, for the current repository-relative source hashes. Verify it from the repository root in a Git checkout or from `source/` in a packaged copy; it records exact bytes for every release source file except the manifest itself, which is excluded to avoid self-reference. Checkout line-ending conversion must preserve those bytes when verifying. The separate package-root `SOURCE-FILE-SHA256.txt` is the full package-layout manifest and includes the portable manifest with `source/`-prefixed paths. The historical receipt describes an earlier candidate, not this build or a complete current-tree checksum. Offline tests and a successful build do not establish hosted-model or browser acceptance; the actual personal launch remains disabled.

## Current professor-review materials

- [5 November delivery walkthrough and claim matrix](deliverables/2026-11-05-final-demo/README.md): manual control, a new cross-cutting induced category, one operator-assisted indirect-intent example, fictional metadata drafts, and the retained negative results. These bounded demonstrations do not establish general semantic reliability or automatic Claude API integration.
- [Complete proposal and course-deliverable audit](deliverables/2026-11-04-completion-review/PROJECT-COMPLETION-AUDIT.md), with achieved results, departures and remaining limits.
- [Current seven-page paper review](deliverables/2026-11-04-completion-review/COMP9500-Current-Paper-Review.pdf), matching the current paper source. The [19 October paper, presentation and progress packet](deliverables/2026-10-19/README-2026-10-19.md) remains a dated historical release.
- [Pipeline and matching code walkthrough](deliverables/2026-10-27-feedback/PIPELINE-AND-CODE-WALKTHROUGH.md), [current code/contribution map](deliverables/2026-10-27-feedback/CODE-MAP-AND-AI-ASSISTANCE.md), and [reviewed topic-workflow addendum](deliverables/2026-11-04-reviewed-workflow/README.md).
- [Separate prospective synthetic-language results](deliverables/2026-11-04-prospective-evaluation/PROTOCOL-AND-RESULTS.md): 48/100 supported final profiles correct and 19/20 correct diagnostic clarifications. This later study does not replace E1 or revised E2, or establish an LLM recommendation benefit.
- [Five-condition examples](deliverables/2026-10-27-feedback/FIVE-CONDITION-EXAMPLES.md), [professor-request coverage](deliverables/2026-11-04-reviewed-workflow/CAPABILITY-AND-TRANSCRIPT-AUDIT.md) and [E1 replay limitation](deliverables/2026-11-04-completion-review/E1-REPLAY-DISCREPANCY.md).

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
