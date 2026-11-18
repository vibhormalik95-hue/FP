# Documents

> **Index.** Each line names one document and what it is. Dates are in 2026.

## Current guides

| Document | Content |
| --- | --- |
| [Guide for the supervisor](guide/PROFESSOR-GUIDE.md) | **Start here.** The current application: install, `fetch-assets`, `run-app.cmd` (`scripts/run_app.py`, port 8765), the four-tab Lab (Choose a category, Say it your way, New category, New items; scope 10–200 items of the current feed; editable definition; provider setup in the page), the Results page, the tests and troubleshooting. |
| [Requirements and evidence](requirements-and-evidence.md) | Each request of the supervisor, the student's own commitments and the clauses of the proposal, mapped to code and to evidence. |
| [Recording and QA history](notes/2026-11-17-recording-and-qa-history.md) | Take 13 and take 14 recording details and earlier test runs, moved out of the professor-facing files. |
| [The built interface](source-verification.md) | How to rebuild `web/dist` after a change to the interface source. |

## Legacy guides (earlier demonstrator)

These pages describe the fixture scenarios and the SemanticPanel page started by `scripts/quickstart.py` (13–15 November). They are kept for the earlier demonstrator and its records; they do not describe the current Lab. Use the [guide for the supervisor](guide/PROFESSOR-GUIDE.md) for the current application.

| Document | Content |
| --- | --- |
| [Install and run](install-and-run.md) | Setup of the earlier demonstrator on Windows and macOS, the scenario `conditions` for A to E, and its verification sequence. |
| [Guide to the language controls](demo.md) | Each method of the earlier page from the request to Undo. |
| [Model routes](model-routes.md) | Routes of the earlier page: a command-line program, a hosted API, a model server, or by hand. |
| [Route trial](route-trial.md) | Run the bundled requests through a route without the browser. |
| [Application reference](app.md) | The views, endpoints and review records of the earlier page. |
| [Delivery index, 15 November](DELIVERY-INDEX-2026-11-15.md) | A short map of the paper, practical guides, requirements and dated integration records on 15 November. |
| [Fictional item drafts](synthetic-item-drafts.md) | Metadata that a model writes for an item that does not exist, in a separate list. |
| [Literal source requirements](numbered-source-constraints.md) | Method note: how the staged category method treats digits and quoted terms in a definition. |

## Research records

These documents are fixed. They are not edited after the study that they belong to.

| Document | Content |
| --- | --- |
| [Evaluation protocol](evaluation-protocol.md) | Experiment 1: the frozen protocol and its interpretation note. |
| [Experiment 2 protocol with model-generated references](ai-reference-e2-protocol-2026-10-14.md), [rubric](ai-reference-e2-rubric-2026-10-14.md), [role prompts](ai-reference-e2-role-prompts-2026-10-14.json) | Experiment 2 as it was run on 14 October. |
| [Experiment 2 results](ai-reference-e2-results-2026-10-14.md) | Results of Experiment 2, with the negative results. |
| [Experiment 2 evidence](ai-reference-e2-evidence/README.md) | Protocol, custody, inference, result and audit files of Experiment 2. |
| [Original Experiment 2 protocol](experiment2-protocol.md), [annotation rubric](experiment2-annotation-rubric.md) | The earlier design with human reference labels. Its reserved evaluation was not run. |
| [Practice run of 14 October](execution-2026-10-14.md) | A run on questions that were already exposed. It is separate from Experiment 2. |
| [Research provenance and limits](academic-use.md) | What each study can and cannot show, and how AI assistance was used. |
| `evidence/2026-10-14/` | Records of the practice run. |
| `evidence/2026-11-11/` | Summaries of the runs through the Claude Code CLI of 10 and 11 November. |
| [evidence/2026-11-13/](evidence/2026-11-13/README.md) | Browser runs of three controls on earlier revisions (`26a0b16` to `936d0f4`), with real model output through the file relay. |
| [evidence/2026-11-14/](evidence/2026-11-14/README.md) | Run records of 14 November for revision `b7c5a91` (the package line before the merge): real model output through the file relay, authored replies, route checks with stand-ins. The folder also holds `OPERA-MANUAL-CONTROLS.md`, a record of the published work branch; the checksum list of the folder does not cover that file. |
| [evidence/2026-11-14-integrated/](evidence/2026-11-14-integrated/README.md) | Run records of 14 November for the integrated revision `ff92666`: the same three kinds of run on the merged source. The guide of the folder lists two earlier passes. |
| [Provider checks, 15 November](evidence/2026-11-15-provider-checks/README.md) | Windows Ollama fictional-item lifecycle and an OpenAI quota-blocked connectivity attempt. |
| [Windows indirect request, 15 November](evidence/2026-11-15-windows-indirect/README.md) | Description-grounded direct application Preview, Apply and Undo. |
| [Windows existing labels, 15 November](evidence/2026-11-15-windows-vocabulary/README.md) | Existing-category and tag controls through direct application calls. |
| [Windows combined request, 15 November](evidence/2026-11-15-windows-combined/README.md) | One mixed request grounded in descriptions and labels, with direct application Preview, Apply and Undo. |
| [Windows general CLI browser request, 16 November](evidence/2026-11-16-windows-general-cli/README.md) | Mixed fictional request through the general CLI route, with browser-reported Preview, Apply and Undo. |
| [Windows new-category timeout, 16 November](evidence/2026-11-16-windows-category-timeout/README.md) | Definition-stage timeout; later stages were not reached. |

The study of 4 November and the dated records of October and November are in [`deliverables/`](../deliverables/). The paper is in [`paper/`](../paper/README.md).

## Dated records of earlier work

These pages describe the project on the date in their first lines. They are not current guidance.

| Document | Date | Content |
| --- | --- | --- |
| [Current progress and remaining work](current-progress.md) | 11 November | Status on that date, with the negative findings of the first model connections. |
| [Requirement and evidence worksheet](requirement-worksheet-2026-11-11.md) | 11 November | The earlier form of the requirements page. |
| [Code walkthrough](current-code-walkthrough.md) | 11 November | From a request to a reviewed feed change, as the code was on that date. |
| [Hosted-only configuration](hosted-only-configuration.md) | 9 to 11 November | The guarded OpenAI Responses application. |
| [Model adapters for indirect requests](model-provider-adapters.md) | 5 to 11 November | The guarded OpenAI Responses adapter. |
| [Configuring a model for category creation](category-provider-configuration.md) | 10 November | The adapter interface for category creation. |
| [Category clarification resolution](category-clarification-resolution.md) | 11 November | How the choice between competing category meanings was added. |
| [Windows 11 and Google Colab setup](windows-and-colab.md) | September and October | Setup of the original experiments. |
| [Local Llama runtime](LLM_RUNTIME.md) | September and October | Runtime of the local model in Experiments 1 and 2. |
