# Natural language controls for short video recommendation

**Start with [START-HERE.md](START-HERE.md) for the supervisor handoff. Experiment 2 is not complete.** Its reserved test is blocked by the required genuine independent student annotation, exposure review and blinded adjudication. The 3 October 2026 runtime check also found no Ollama executable and a refused localhost connection, so new Llama inference is stopped. H1 and H2 are not assessed; no reserved ranking results or agreement statistic exist. Read `docs/experiment2-status.md`, `docs/annotation-handoff.md` and the dated `docs/experiment2-protocol.md`. The compound parser and staged runner use a separate namespace and output tree. The application and all historical results below describe the finished Experiment 1. An engineering pass does not complete Experiment 2.

COMP 9500 research artifact for Vibhor Malik. This repository contains a React and FastAPI demonstration, a SASRec implementation, real KuaiRec preprocessing and experiment outputs, a local Llama 3.1 8B parser, a frozen synthetic language benchmark, statistical analysis, an IEEE-format paper and a presentation draft.

The Experiment 1 audit interpretation is in `docs/audit-resolution.md`, `docs/evaluation-protocol.md` and `results/audit_revision/analysis-v1.json`; the original `results/llm/` and `results/rule/` summaries are preserved historical records. The supplied proposal is unsigned, with research-path and approval fields blank; individual scope approval is not evidenced. `docs/sources/` includes a documented punctuation-normalized proposal copy, the supplied course-email transcript and meeting excerpts. The updated 135-hour schedule is a prospective allocation over the proposed remaining 11 weeks, 5 October to 18 December 2026, not a record of completed work. The exact December deadline still requires confirmation.

The individual meeting arrangement is Wednesday at 10:00 am Vancouver time, approximately 30 minutes, subject to the supervisor's invitation. Submit the update Tuesday by 10:00 am and record minutes afterwards. Use `docs/supervision/README.md` for weekly records and `docs/repository-handoff.md` for private repository preparation. No remote repository or supervisor invitation has been created.

## Quick start on Windows 11

Install Python 3.12 from its official distribution. Extract this entire folder, then open PowerShell inside it. Your Core i9 and 32 GB RAM are suitable for this CPU workflow; the exact speed on your laptop has not been measured.

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\python -m pip install -e ".[test,analysis]"
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m uvicorn feedctrl.api:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. The packaged frontend build requires no Node installation to view. The default app loads `data/processed.json` and `results/models/seed_42` when present. Check the visible data and scorer labels. The application provides research metadata cards, not licensed video playback.

To use the actual local language model, install Ollama from https://ollama.com/download/windows and run:

```powershell
ollama pull llama3.1:8b
```

Keep Ollama running and choose the Ollama backend in the application. Rule mode is a separately labeled diagnostic parser. An Ollama failure is an error, never a hidden switch to rule mode. The model download is about 5 GB. The source package does not bundle the Llama weights or Ollama runtime.

## Reproduce the scientific workflow

With the Ollama service running, execute:

```powershell
.venv\Scripts\python scripts/run_pipeline.py --backend ollama --data data/my-rerun.json --models results/my-models --output results/my-llm-run
```

Use a new output directory for each run. Frozen packaged data, checkpoints and results are protected from overwrite; full-run defaults place new inputs and models under that run directory. Explicit `--skip-data --skip-train` replays the packaged inputs read-only.

This runs software checks, downloads the official KuaiRec archive with a publisher checksum check, reconstructs the full eligible cohort, trains three 20-epoch SASRec models, evaluates the frozen 100-case parser set, runs the five conditions and writes user-level statistical analysis. It fails explicitly if a required stage fails. The aggregate is saved under `OUT/evaluation/combined-summary.json`. `pipeline_manifest.json` records configuration, stage commands, timings and exit codes. Internet is needed for installation and upstream downloads; inference uses loopback only.

To reuse packaged data and trained models without retraining:

```powershell
.venv\Scripts\python scripts/run_pipeline.py --backend ollama --skip-data --skip-train --output results/my-replay
```

For a fast synthetic software check without an LLM:

```powershell
.venv\Scripts\python scripts/run_pipeline.py --fixture --backend rule --epochs 1 --seeds 7
```

For the real-data rule diagnostic, use `--backend rule --skip-data --skip-train`. Rule results measure the deterministic control policy and cannot substitute for measured LLM results. The first Llama call can be much slower than subsequent calls. Cache identities include inputs, prompts and model provenance; cached canonical controls reused across users are not independent language tests.

On Linux and macOS use `.venv/bin/python` instead of `.venv\Scripts\python`. For environments where the local server and client must share one process tree, `scripts/with_ollama.py` starts a temporary loopback server and runs the requested command. Do not run it alongside an already-running Ollama service.

## Colab

Upload `notebooks/Run-Experiments.ipynb` to Google Colab and follow its cells. Use Colab for notebook-based experiments; run the web demonstration locally on Windows. GPU availability and session duration vary, so save outputs before disconnecting. The notebook has been syntax checked here; execution inside your signed-in Colab account has not been performed. See `docs/windows-and-colab.md` for details and the official Colab FAQ.

## What the experiment measures

The main cohort includes all 865 eligible KuaiRec users and 2,593 items observed positively before the global training cutoff. A positive event is `watch_ratio > 2`, an engagement proxy. Rows without orderable timestamps are excluded and counted. Global training, request-history and test windows prevent future-user interaction leakage. The next held-out positive item is the HR@1 and NDCG@10 target.

Each user receives one historical-category boost and one mute assignment. A simulates feedback on one historical exemplar; B adds explanations without changing A's ranking; C parses a free-text request; D parses an explicit editable profile preference; E combines C and D without counting the same preference twice. The rule comparator and actual Llama parser are reported separately. Category IDs remain opaque: this benchmark does not establish real-world semantic category understanding or human satisfaction.

The primary paired tests use user-aggregated effects across three training seeds. Six Wilcoxon tests compare C, D and E to A for positive TCP@10 and negative TCER@10, with Benjamini-Hochberg correction. Bootstrap intervals resample users. Full-feed rate prevents an empty ranking from passing mute compliance. The proposal's ambiguous "within 10%" is reported under both readings using the same paired Bonferroni bound. Absolute 0.10 passes numerically but exceeds the pooled A baseline 0.002504817 and permits complete baseline loss. Relative 0.10 times the baseline equals 0.000250482 and fails against the lower bound -0.000770713. Both readings are exploratory; neither establishes useful quality preservation.

## Recorded findings

The actual Llama experiment completed all three seeds with 25,950 request-condition rows and no canonical-input operational errors. All 120 unique text/profile inputs matched the assigned intent. Its rankings and metrics equal the rule diagnostic for these simple inputs: positive target proportion rises from 0.11615 in A to 0.79222 in C/D/E; negative target exposure falls from 0.06112 to zero, with full feeds. A and B are identical; matched C/D/E are identical.

The broader frozen language benchmark scores **79/100**, below the proposal’s **85% target** but above its **70% degradation floor**, while the rule diagnostic scores 81/100. The backbone has extremely low next-item accuracy, and positive-control NDCG@10 falls from 0.03012 to 0.01637. These findings establish narrow control enforcement, not useful recommendations or general language reliability. The primary exposure criterion is numerically supported, but it measures category-policy enforcement against a weaker single-item comparator; rule and LLM results are identical.

Post-hoc baselines on the same candidates and first test target find request-window popularity HR@1=7.977% and NDCG@10=0.11866, versus SASRec HR@1=0–0.462%. That baseline pools recent pre-test information across users; SASRec weights use older training data while inference accesses each user’s history, so this is not an information-matched model comparison. See `results/audit_revision/baselines.json`.

All ten recorded LLM explanations equal the first-three-facts deterministic template. The retained cohort has no repeated training items or test/history overlap; permitting seen-item recommendations remains a frozen design choice, not a repeated-target necessity. A follow-up with unseen-only candidates needs a separate experimental record.

Reproduce the supplemental analyses without rerunning inference or changing frozen inputs:

```powershell
.venv\Scripts\python scripts/analyze_revision.py
.venv\Scripts\python scripts/benchmark_revision.py
```

The paired post-hoc boost NDCG contrast is −0.01375 (95% CI −0.02086 to −0.00655; unadjusted Wilcoxon p=3.23e−10). It remains exploratory. Pinning PyTorch2.5.1 supports checkpoint replay, but does not guarantee bitwise-identical retraining across hardware or versions. Preserve packaged models as the original anchor and record every replication separately.

## Repository map

| Path | Purpose |
|---|---|
| `feedctrl/` | Data, model, controls, API and evaluation code |
| `web/` | Editable React source and production build |
| `tests/` | Unit, integration and independent acceptance checks |
| `data/processed.json` | Derived research cohort with provenance |
| `data/parser_test.jsonl` | Frozen 100-case synthetic parser benchmark |
| `results/models/` | Three trained SASRec checkpoints and metadata |
| `results/rule/` | Real-data deterministic parser diagnostic |
| `results/llm/` | Completed actual local Llama ranking experiment |
| `results/parser_ollama_test/` | Actual local Llama language benchmark |
| `results/verification/` | Historical first-release verification records |
| `results/audit_revision/` | Supplemental analysis, corrected interpretation and fresh verification |
| `docs/sources/` | Original unsigned proposal and supplied course-email transcript |
| `paper/` | LaTeX source, bibliography and IEEE template |
| `deliverables/` | Paper, presentation and prospective 135-hour plan |
| `docs/` | Protocol, literature review, independent review and runbooks |

## Develop the frontend

Install a current Node LTS release and run `npm ci` then `npm run build` inside `web/`. The FastAPI app serves `web/dist`. `web/package-lock.json` pins the frontend build. This is a local, single-process research demonstration with in-memory session state. It is not a deployed multi-user production service.

## Paper and presentation

Run `pdflatex manuscript.tex`, `bibtex manuscript`, then `pdflatex manuscript.tex` twice from `paper/` using a LaTeX installation. The manuscript uses IEEEtran conference formatting. Its numerical claims must match the saved result files. The current presentation is `deliverables/COMP9500-BCIT-Presentation.pdf`, based on the supplied official BCIT Beamer template. The earlier `deliverables/COMP9500-Research-Presentation.pptx` is retained as a superseded historical draft. The paper and slides still require supervisor review and integration of any valid reserved Experiment 2 results before final assessed submission.

The historical PowerPoint generation script is included for traceability and uses a hosted authoring runtime. It is not part of the Windows/Colab experiment installation. The current Beamer presentation has editable LaTeX source. Scientific execution, document authoring and presentation rehearsal are separate activities.

See `docs/academic-use.md` for AI assistance and authorship responsibilities. Supervisor approval, student understanding, actual progress meetings and final presentation are separate from technical artifact completion.
