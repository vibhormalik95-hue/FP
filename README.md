# Natural-language controls for short-video recommendation

**LLM-Mediated Natural Language Controls for Short-Video Recommender Systems: An Offline Study of Controllability.**
COMP 9500 M.Sc. research project at BCIT. Student: Vibhor Malik. Supervisor: Dr Borna Noureddin.

## What this project is

This project studies how a person can control a short-video feed with plain language.
A language model turns a request into an explicit proposal. The application checks the proposal. A person reviews it. A fixed, deterministic policy then applies exactly the approved change to the ranking.

The research question is about controllability and expressiveness.
Which requests can a person state in language? How reliably does a model turn them into an explicit control? What does the control cost in ranking quality?
The project does not claim that a language model makes recommendations more accurate or users more satisfied.

The study is offline. It uses the KuaiRec dataset (865 users and 2,593 items in the processed subset). There is no user study.
The repository holds a research application named Feed Control Lab (React and FastAPI), its tests, the experiment protocols and results, and the paper.

## Current state (17 November 2026)

This is the final state of the COMP 9500 work: branch `final/comp9500`, merged to `main` and tagged `comp9500-final-2026-11`.

- **One application on real KuaiRec.** `run-app.cmd` (Windows) or `python scripts/run_app.py` starts it at <http://127.0.0.1:8765>. It serves 865 users and 2,593 items, ranked by the trained SASRec seed-42 checkpoint, in three views: **Original study (A to E)**, **Language controls** (choose a category; a request in your own words; a new category from a description; new items with descriptions) and **Results**. In every language control a model only proposes; the server checks the proposal, a person reviews it, Apply changes exactly what was reviewed and Undo restores the previous feed. Everything is English: the KuaiRec text (titles, captions, cover text, topic tags, the three levels of category names) is translated into English before processing, and the app, the models and the screen use only that English text layer (`data/kuairec_text_en-v1.json`, machine translation of KuaiRec, CC BY-SA 4.0, SHA-256 `034f5ac9…`; built by `scripts/build_kuairec_english.py`). The assets it needs (processed data, the English text layer, checkpoints for seeds 42–44) are published as GitHub Release assets under CC BY-SA 4.0 (`comp9500-kuairec-assets-v1`, `comp9500-kuairec-english-v1`); `fetch-assets.cmd` (or `./fetch-assets.sh`) downloads them and verifies every SHA-256. Attribution: `notices/KUAIREC-ASSETS-ATTRIBUTION.md`.
- **Guide for the supervisor:** [docs/guide/PROFESSOR-GUIDE.md](docs/guide/PROFESSOR-GUIDE.md) (also as PDF): install, start, providers and keys, every workflow with screenshots, the Results page, the tests and troubleshooting.
- **Tests:** `run-all-tests.cmd` runs the Python tests, the page tests, the browser flows in Chrome, an English-only check that walks every screen and every demo step and fails on any visible CJK character, and every workflow through the HTTP API, and writes receipts to `runs/all-tests-<UTC>/`. It uses the mock provider by default (no key, no cost); `run-all-tests.cmd --provider openai --model gpt-5-mini` uses a real model. The root-level `test_*.py` files and the `tools/hosted_validation*` tests are outside it. The latest full run (mock, on the English-only code of r4; receipts in `FINAL2/receipts/r4-tests/`) gave pytest 1,763 passed, 75 skipped and 1 failed (frozen by design: `test_guarded_current_contract`), page tests 126/126, browser 29/29, the English-only check 53 screens with no visible CJK character, and workflows 14/14.
- **Experiment 3** measures the language controls on a frozen set of 40 new cases (20 English, 20 Chinese). Claude (Opus 5.5) drafted the cases and all 1,211 reference judgements; the student reviewed every row and corrected 24; the set was frozen before any prediction. Results are in [RESULTS.md](docs/evidence/lab-eval/20261117-main/RESULTS.md) and below; all of them were measured on the original-text run (17 Nov); English-input re-run pending.
- **Demo video:** `COMP9500-Feed-Control-Lab-demo.mp4` (sent separately, not in this repository): take 13: 10:12, 1920x1080, narrated, recorded on the English-only application (r4); research user 14 with the news and incident categories hidden first; the API key pasted into the masked field (never shown); gpt-5 at minimal reasoning effort for speed (the measured results use low effort). Checks: no silence of 5 s or more at -45 dB; transcript 96/96 script sentences (similarity 0.89); one frame every 30 s; live CJK check, 69 checks, no visible CJK. Takes 12 and 11 are kept as backups. Receipts: [docs/evidence/2026-11-17-video-take13/](docs/evidence/2026-11-17-video-take13/README.md).
- **Paper and slides:** `paper/research-paper-2026-11-17.pdf` (8 pages, draft) and `presentation-bcit/presentation-2026-11-17.pdf`.
- **Open:** gemma4:31b was probed but not run (too slow on this laptop; a full run needs a faster machine), and the Anthropic API route has never been run with a live key. The local models llama3.1:8b and qwen2.5-coder:7b-instruct are measured (below).
- **Requirements and evidence:** [docs/requirements-and-evidence.md](docs/requirements-and-evidence.md) maps each request of the supervisor and each proposal clause to code and evidence; the full audit is [deliverables/2026-11-17-completion/PROJECT-COMPLETION-AUDIT.md](deliverables/2026-11-17-completion/PROJECT-COMPLETION-AUDIT.md).

## The earlier demonstrator (14 November, invented scenarios)

Before the integrated application, a separate page served the language controls on small invented scenarios. This section describes it as history; the scripts still exist.

The view **Language controls** of that page has five methods. Each one follows the same stages: request, interpretation, evidence, preview, Apply, Undo.

| Method | What happens | Model calls |
| --- | --- | --- |
| Existing category | You choose an existing category and an action. This is the reference for the language controls. | 0 |
| A request matched to existing categories and tags | You write a request. It does not need a category name. The model chooses existing category and tag names. The application checks each name and selects the items that carry it. | 1 |
| A request matched to item descriptions | The model reads the direction from the request. It then selects items and cites a quotation from each description. | 2 |
| A mixed request matched to descriptions, categories and tags | One model reply proposes up to four controls using the supplied captions, cover text and existing labels. The application checks the cited evidence and the combined plan. | 1 |
| A new category from a description | The model proposes a definition, and you review it. The model then classifies every item. A separate call assesses the evidence without seeing the classifications. | 3 |

For every method:

- a proposal does not change the feed;
- the review shows what came back, the application checks and your decision in three separate blocks;
- a table shows each item in the scope and why it is selected or not selected;
- Apply uses exactly the reviewed set, and a two-step Undo restores the earlier feed.

![The evidence table of a review: each item of the scope, its categories and tags, why it is selected or not, and the result](docs/images/review-evidence-table.png)

*The evidence table of one review of 14 November 2026 (revision `b7c5a91`, before the merge with the published work branch). The request was "I'm not hungry, remove all the stuff that makes me hungry." The model chose existing category and tag names, and the application selected the items that carry them. The items are invented. The model output came through the file relay, and an AI operator reviewed it; no person reviewed this run. The complete review with its three blocks is in [docs/images/review-three-blocks.png](docs/images/review-three-blocks.png).*

The application also shows these things:

- **Mixed requests.** One request can hold several preferences, for example more of one subject and none of another. Choose either existing labels alone or descriptions and existing labels together. The review shows each control, and one approval applies the accepted plan together.
- **Requests that change nothing.** An ambiguous request, a negated command, a request that the controls cannot express, and a request with no match each give a plain result. Nothing is applied. A negated hide, exclude, remove, reduce or boost (for example "Do not hide ..."), or a negated "show ... more" or "show ... less", matches the negated-command pattern. The application stops it before any model call.
- **A fictional item.** A model writes a title and a description for an item that does not exist. The item goes to a separate feed. It never enters the dataset.
- **Model routes.** The application can reach a model through a command-line program, a hosted API with your own key, a model server on your computer, or by hand. See [model routes](docs/model-routes.md).
- **The original study.** The views "Original study (A to E)" and "Compare A to E" hold the five conditions of the original proposal. They are item feedback, explanations, a free-text category instruction, an editable profile, and all channels. The rule parser of C, D and E reads category IDs of the form `category_N` only. On the bundled scenarios, which have named categories, the instruction and the profile are disabled, and the page says why. The scenario `conditions` serves the built-in fixture, where they work.

The supervisor asked for three of these things in a meeting. The student supplied the transcript of that meeting on 4 November 2026. The three things are the manual category control with measured performance, a new category from natural language, and requests that do not use the literal category words. The integrated application and Experiment 3 now answer all three on real KuaiRec data.

### Run the earlier demonstrator in five steps

You need Python 3.11 or newer. [Install and run](docs/install-and-run.md) gives every command for Windows and for macOS.

1. **Install.** Create a virtual environment. Then run `python -m pip install -e ".[test]"`.
2. **Choose a route to a model.** Run `python scripts/quickstart.py setup`. It asks a few questions and writes `model-route.json`. The file never holds an API key.
3. **Confirm the route.** Run `python scripts/quickstart.py doctor`.
4. **Start.** Run `python scripts/quickstart.py start --scenario tags`.
5. **Use the page.** Open <http://127.0.0.1:8765>. The page opens on **Language controls**. The [guide to the language controls](docs/demo.md) describes each method.

Three more commands help:

- `python scripts/quickstart.py manual --scenario tags` serves the page with no model: only the manual category control works. To try the language controls with no key and no cost, use the integrated application (`run-app.cmd`) with its default **mock** provider.
- `python scripts/quickstart.py manual --scenario conditions` serves the original conditions A to E on the built-in fixture (36 items, categories `category_0` to `category_5`, three users). It uses no model and has no language controls.
- `python scripts/quickstart.py try --scenario tags` runs the bundled requests through your route without the browser. See [route trial](docs/route-trial.md).

The general CLI, hosted API and local-server routes have stand-in test records from Linux; full native Windows and macOS verification remains open. A separate [Windows fictional-item run on 15 November](docs/fictional-lifecycle-2026-11-15.json) used Fable 5.2 through a task-local transport and a modified personal adapter. It completed draft, admit, remove, restore and reset. That run did not test the general quickstart route, category discovery or the later publication candidate.

A [16 November Windows Opera trial](docs/evidence/2026-11-16-windows-general-cli/README.md) used the general Claude Code route for one fictional mixed request. An AI operator reviewed the proposal, applied it and undid it. The trial used an isolated candidate with modified combined prompt and schema descriptions; it does not establish acceptance of the unmodified main branch. A separate [new-category definition attempt](docs/evidence/2026-11-16-windows-category-timeout/README.md) timed out before classification or assessment.

On 15 November, two further Windows checks used Fable 5.2 through the separate personal Claude Code adapter: [a description-based indirect request](docs/evidence/2026-11-15-windows-indirect/README.md) changed a 36-item feed to 34 and back, and [a mixed request over existing categories and tags](docs/evidence/2026-11-15-windows-vocabulary/README.md) changed a ten-item feed to six and back. An AI operator reviewed both. These were direct application calls with task-local launchers, not browser runs, new-category discovery or a portable quickstart test.

A separate [combined descriptions-and-labels check](docs/evidence/2026-11-15-windows-combined/README.md) completed Preview, Apply and Undo with one logical Claude Code invocation reporting Fable 5.2 and AI review on a fictional Windows fixture. It used a task-local launcher and direct application routes; it was not a browser or general quickstart test.

## Experiments and results

Every number below is copied from the document that is named after it.

**Experiment 3: language controls on a reviewed KuaiRec set (17 November).** Every number in this list was measured on the original-text run (17 Nov); English-input re-run pending. Set and freeze: [docs/evidence/lab-eval-set-20261117/](docs/evidence/lab-eval-set-20261117/README.md). Results: [docs/evidence/lab-eval/20261117-main/RESULTS.md](docs/evidence/lab-eval/20261117-main/RESULTS.md). Every table names the prediction commits (hosted models `8dd978f`, local models `9071f05`) and the scoring commit (`fbb3e59`); every code change after the freeze is listed in [POST-FREEZE-AUDIT.md](docs/evidence/lab-eval/POST-FREEZE-AUDIT.md).

- 20 nonliteral requests to existing KuaiRec labels (exact intended label profile): gpt-5 17, Claude Sonnet 5.5 17, gpt-5-mini 16 of 20.
- 14 requests that should change nothing (correct abstention): Claude Sonnet 5.5 12, gpt-5 10, gpt-5-mini 7 of 14. gpt-5-mini proposed a control for 7 of them.
- 6 new categories over a shared pool of 150 items (member F1, reviewed definition): gpt-5-mini 0.936, gpt-5 0.918, Claude Sonnet 5.5 0.875.
- Downstream on 200 users with the trained ranker: the reviewed reference control raises the target share of the top ten (TCP@10) from 0.0063 to 0.5290, and the model controls reach 0.5178 to 0.5625; no hosted model differs significantly from the reviewed control (Wilcoxon, BH p 0.6214–0.6543). These values apply each model's exact controls with the application's own policy; they were re-scored on 17 November after an independent code review, with the same predictions. Hide and reduce bring TCER@10 from 0.0118 to zero.
- Negative: NDCG@10 falls from 0.0242 to 0.0144–0.0156; HR@1 non-inferiority fails the relative 10% margin for every hosted model (the absolute 0.10 margin passes trivially at a base HR@1 of 0.0050). No pair of hosted models differs significantly (McNemar BH p ≥ 0.55).
- Local versus frontier: on this laptop the two local 7–8B models proposed almost nothing. On the 20 nonliteral requests llama3.1:8b matched no exact profile (it declined 17, 16 of them as ambiguous; 2 calls failed at the output cap; 1 proposal) and qwen2.5-coder:7b-instruct matched none and declined all 20 (10 as no match, 10 as unsupported). Their abstention scores (11/14, 9/14) therefore reflect declining everything, not judgement. On new categories qwen was precise but missed most members (precision 0.97, recall 0.33, F1 0.47); llama reached F1 0.18. The frontier models reached 16–17/20 exact and member F1 0.88–0.94, and every frontier model beats both local models (McNemar BH p ≤ 0.0024). Local calls cost nothing but took about two minutes each (median 126 s and 109 s). gemma4:31b fit in memory (37 GB) but generated 0.90 tokens per second, too slow to measure.
- The set is AI-drafted and human-reviewed, not human-written. Claude is both the drafter's family and a measured model, which can favour Claude. Using hosted frontier models is a declared departure from the proposal's local-only plan.
- Parser bank re-run (re-use of the exposed Experiment 1 bank, not new evidence; original prompt, schema, validator and grounding rule): llama3.1:8b 79/100 with 7 operational errors, as frozen; qwen2.5-coder:7b 74/100; gpt-5 and gpt-5-mini 60/100 strict, 96 and 95 under a post-hoc format-lenient score ([summary.json](docs/evidence/lab-eval/20261117-b-parser-rerun/summary.json)). No model meets the 85% target.

**Experiment 1 (frozen).** Protocol: [docs/evaluation-protocol.md](docs/evaluation-protocol.md).

- For boost requests, TCP@10 was 11.615% with item feedback and 79.222% under the category policy. For mute requests, TCER@10 was 6.112% and zero (`deliverables/2026-10-27-feedback/RESULTS-AND-LIMITATIONS.md`). The zero comes from the hard filter. It shows that the policy is enforced. It does not show an advantage of the language model.
- Negative: the Llama parser matched 79 of 100 requests exactly. The 85% target was missed (`docs/evaluation-protocol.md`). The rule parser matched 81 of 100 (`deliverables/2026-11-05-final-demo/RESULTS-AND-LIMITS.md`).
- Negative: boost lowered NDCG@10 from 0.03012 to 0.01637 (`deliverables/2026-10-27-feedback/RESULTS-AND-LIMITATIONS.md`).
- Negative: a complete replay of Experiment 1 is not established (`deliverables/2026-11-04-completion-review/E1-REPLAY-DISCREPANCY.md`).

**Experiment 2, with model-generated reference labels (frozen).** Protocol, rubric and prompts: `docs/ai-reference-e2-*.md` and `.json`. Results: [docs/ai-reference-e2-results-2026-10-14.md](docs/ai-reference-e2-results-2026-10-14.md). Evidence: `docs/ai-reference-e2-evidence/`.

- Whole-command agreement with the reference labels was 76 of 100 for Llama and 11 of 100 for rules.
- Induced control success was 20.145% for Llama, 3.854% for rules and 3.815% for item feedback.
- Negative: NDCG@10 was 0.02580 for Llama and 0.03184 for item feedback. Conditional-control success was zero (`deliverables/2026-10-27-feedback/RESULTS-AND-LIMITATIONS.md`).
- The reference labels came from two AI annotators. They do not measure independent human accuracy.
- The two annotators are AI roles. They carry first names in the frozen file paths (`annotations/khushi/`, `annotations/tanishq/`), and no person of those names made the labels.

**Synthetic-language study of 4 November (used once, now exposed).** Protocol and results: `deliverables/2026-11-04-prospective-evaluation/PROTOCOL-AND-RESULTS.md`.

- The pipeline matched the complete intended profile on 48 of 100 supported requests. It clarified correctly on 19 of 20 diagnostic requests.
- The 120 cases gave 49 ready proposals, 61 clarifications, five grounding errors and five parser or schema rejections.
- The intended profile (the model-written reference, applied without a model) against the language pipeline: the intended profile changed top-ten exposure by 5.3579 percentage points, and the model-proposed profile by 2.9292 points. These are signed descriptive averages. They are not a success rate. An AI author wrote the intended profiles, and another AI role reviewed them. They are not human annotations.

The complete cases, model responses, ranking outputs and recommender checkpoints are in a separate research archive. They are not in this repository.

The paper is in [`paper/`](paper/README.md). The current draft is `paper/research-paper-2026-11-17.pdf` (8 pages). It reports Experiments 1 to 3 (five models) and the integrated application; it is not ready for submission (the author still reviews one marked sentence). The revisions of 14 November and 19 October are dated records.

## Experiment evidence and demonstration evidence

Keep three kinds of evidence apart.

**Experiment evidence** comes from a study with a protocol that was fixed before the run: Experiment 1, Experiment 2, the 4 November study and Experiment 3. Their inputs, prompts, labels and results stay as they are.

**Demonstration evidence** is a recorded run of the application on a small invented scenario. It shows that a control ran from request to Undo. It is not an accuracy result.

- *13 November 2026, earlier revisions (`26a0b16` to `936d0f4`).* The manual control, a new category and an indirect request matched to descriptions each completed in a real browser. The model replies came through a file relay. An AI agent made the review decisions. No person reviewed those runs. Records: [docs/evidence/2026-11-13](docs/evidence/2026-11-13/README.md).
- *14 November 2026, the package line before the merge.* On revision `b7c5a91` (source fingerprint `ab1a9d846b33...`), every method completed in a real browser with real model output through the file relay: the request matched to existing categories and tags, a mixed request, the request matched to item descriptions, the new category in stages and the fictional item, with the manual control as reference (13 model calls, 308 script checks passed). Four requests that must change nothing changed nothing. An AI operator made all 19 review decisions; no person has reviewed a run. The model name is declared, not attested. Records: [docs/evidence/2026-11-14/](docs/evidence/2026-11-14/README.md).
- *14 November 2026, the integrated revision.* The published work branch and the package line were merged (`e797ce1`). A comparison of every line of the published branch and two independent reviews of the merge gave corrections (revision `ff92666`, source fingerprint `22ba794e2091...`). The revision has the prompts of the published branch for the new category and the page and routes of the package line. Between 20:05 and 20:13 UTC every method completed on it in a real browser with real model output through the file relay (13 model calls, 321 script checks passed), and the four requests that must change nothing changed nothing. An AI operator made all 19 review decisions; no person has reviewed a run. The model name is declared, not attested. Two earlier passes of the same runs on the merged source selected the same items. Records: [docs/evidence/2026-11-14-integrated/](docs/evidence/2026-11-14-integrated/README.md).

**Software tests** use test doubles with fixed replies (under `tests/` only), stand-in servers and stand-in programs. They check program behaviour. They are not model evidence.

## Limits

- The demonstration scenarios of 13–14 November used invented item descriptions and a labelled diagnostic scorer, not the trained recommender. The integrated application and Experiment 3 use real KuaiRec data and the trained ranker.
- There is no user study. Requests in the experiments are synthetic. The ranking measure is a historical next-item proxy.
- A quotation or a category name shows that words exist in the item data. It does not show that a membership decision is right. Two model calls can agree and both be wrong.
- The development examples are small and exposed. They cannot serve as an unseen test.
- The manual control check shows that a control is enforced and can be reversed. It does not show that recommendations are better.
- The local-versus-frontier comparison covers two small local models (7–8B) on one laptop; a larger local model (gemma4:31b) was too slow to run there. The earlier six-case comparison used different transports and settings.
- Experiment 3 has small groups (20, 14 and 6 cases) with wide intervals, an AI-drafted reference, and (on the 17 November run) half of the requests in the original language, judged through an English machine-translation gloss. The application now works on an English machine translation of KuaiRec; a wrong translation can mislead a label or a quotation.
- A fictional item is authored demonstration data. It is not a new playable item of the research dataset.

## AI assistance and attribution

- Research provenance and the use of AI assistance: [docs/academic-use.md](docs/academic-use.md) and [the code and contribution map](deliverables/2026-10-27-feedback/CODE-MAP-AND-AI-ASSISTANCE.md). The recent application work, its tests and its documentation were produced with substantial AI assistance (Claude Code), and an AI agent made the review decisions in the 13 November runs and wrote their records. The Experiment 3 reference set was drafted by Claude Opus 5.5 and reviewed row by row by the student. Those documents state what the student did himself.
- Third-party data and software: [NOTICE.md](NOTICE.md). KuaiRec licence: [notices/KuaiRec-LICENSE.txt](notices/KuaiRec-LICENSE.txt).

## Map of the repository

| Path | Content |
| --- | --- |
| `run-app.cmd`, `run-all-tests.cmd` | Start the integrated application; run every test suite and workflow (Windows). |
| `docs/guide/` | The guide for the supervisor (Markdown, PDF, screenshots). |
| `feedctrl/` | The application and the experiment code (Python). |
| `web/` | The interface source and the built interface (`web/dist`). |
| `scripts/` | The quick start, the launcher, the route tool, the relay tools, the checks of the source list and of the built interface, and the experiment scripts. |
| `scenarios/`, `tools/hosted_validation_current/inputs/` | The three bundled scenarios with invented items. |
| `tests/` | Python tests, the browser check and the stand-ins. |
| `docs/` | Guides, protocols, results and run records. Start with the [index](docs/README.md). |
| `deliverables/` | Dated records of earlier work. |
| `paper/`, `presentation-bcit/` | Paper and presentation sources. |
| `tools/` | The validation driver for the reviewed Claude Code CLI connection. Its inputs and templates are the frozen profile of 11 November 2026. |
| `CURRENT-SOURCE-SHA256.txt` | The SHA-256 of every tracked file of this revision. `python scripts/refresh_source_manifest.py --check` compares it. |
