# Run on Windows 11 or Google Colab

The supplied research results were executed in a Linux CPU VM. Windows and Colab are documented rerun paths, but neither platform was available for an interactive acceptance run in this session. The user's Core i9 / 32 GB Windows laptop has sufficient RAM for the demonstrated small SASRec architecture and a local quantized 8B language model; exact inference speed depends on CPU generation, cooling and any compatible GPU. SASRec itself does not require paid compute.

## Windows: reproduce the experiment

Install Python 3.12 and unzip the project into a short path, for example `C:\CMP\cmp9500-recommender`. Open PowerShell in that folder. These commands call the virtual environment directly, so changing PowerShell execution policy is unnecessary.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -e ".[test,analysis]"
.\.venv\Scripts\python.exe -m pytest -q
```

The exact executed VM package versions are in the delivered environment evidence. Installing against the broad package compatibility range can resolve newer versions; record `python -m pip freeze` for every rerun. Do not promise identical floating-point scores across devices or library versions. Use the recorded PyTorch 2.5.1 environment for comparison with the original checkpoints; matching the version alone does not guarantee bit-identical results across hardware. The supplied saved checkpoints are the reference for result replay. An external Linux review reproduced top-10 lists and metrics using PyTorch 2.14.0 while reporting differences in some full-ranking/score hashes and in retrained weights; that external report is not a fresh Windows or Colab test.

Run the transparent rule diagnostic first. This downloads the official 432 MB archive, verifies its published checksum, creates the globally chronological cohort, trains the frozen 20-epoch / three-seed SASRec models, runs parser checks, and evaluates A–E. The rule backend is explicitly not an LLM result.

```powershell
.\.venv\Scripts\python.exe scripts\run_pipeline.py --backend rule --data data\rerun.json --models results\rerun_models --output results\rerun_rule --max-users 0 --epochs 20 --seeds 42 43 44
```

For actual language-model execution, install [Ollama for Windows](https://ollama.com/download/windows), open a new PowerShell terminal and run:

```powershell
ollama pull llama3.1:8b
.\.venv\Scripts\python.exe scripts\run_pipeline.py --backend ollama --data data\rerun.json --models results\rerun_models --output results\rerun_ollama --skip-data --skip-train --skip-tests
```

The Ollama Windows application normally starts its loopback API automatically. If it is unavailable, start `ollama serve` in a separate terminal. Record its version and model digest. The model weight layer observed in this project is about 4.92 GB; leave additional space for the installed runtime, archive and experiment outputs. See [LLM_RUNTIME.md](LLM_RUNTIME.md) for model configuration, error handling and detailed installation references.

## Windows: open the demonstration app

Use the main README commands to build the React frontend and run `feedctrl.api:app`. The app has genuine metadata cards; the dataset does not distribute playable source videos. Read the visible data/backend status before demonstrating it. Rule controls are a software diagnostic; select Ollama for actual LLM parsing.

## Google Colab

Upload `notebooks/Run-Experiments.ipynb` through File → Upload notebook at [Colab](https://colab.research.google.com/). The first cell asks for the delivered project ZIP, checks archive paths before extraction, and locates the package root. Run the notebook in order. It installs the package, records the runtime, runs tests, and reproduces the rule experiment. An optional section installs a pinned Ollama runtime and executes the actual LLM benchmark inside the notebook's own VM. The final cell downloads a ZIP of rerun evidence.

Keep CPU as the default for strict comparison with the supplied CPU run. The notebook permits an explicit `USE_GPU = True` when a CUDA runtime is available; the training CLI then selects CUDA. GPU results are a separate hardware replication, with runtime versions recorded. No TPU implementation is provided.

Colab's [official FAQ](https://research.google.com/colaboratory/faq.html) says resource availability, GPU type and session limits can vary, and idle VMs may be deleted. Use it for interactive notebook experiments and download results before disconnecting. The notebook does not expose the application or Ollama through a public tunnel, and it does not mount Google Drive or require API keys.

## What counts as a successful rerun

1. Tests pass, and the pipeline exits successfully with its execution manifest.
2. The dataset records the official archive hash, missing-timestamp exclusion, pre-cutoff candidate policy and strictly separated global time ranges.
3. There are three model checkpoints with train-only sequence hashes and finite training loss.
4. Each evaluation records its backend and model provenance; unavailable LLM calls are failures, never rule substitutions.
5. A and B ranking hashes agree; no negative-category item survives a successful hard mute; empty filtered feeds remain empty.
6. Aggregate uncertainty uses users as the sampling unit across seeds. Read warnings about exploratory results and the held-out engagement proxy before drawing conclusions.

The 135-hour plan is a prospective work allocation. Machine execution time and generated assistance are not a retrospective record of student work.

## Official sources checked September 28, 2026

- KuaiRec source and release: https://github.com/chongminggao/KuaiRec and https://zenodo.org/records/18164998
- PyTorch platform installation: https://pytorch.org/get-started/locally/
- Ollama Windows: https://docs.ollama.com/windows
- Ollama Linux: https://docs.ollama.com/linux
- Colab limits and allowed interactive use: https://research.google.com/colaboratory/faq.html

## Audit revision portability corrections

The API reads processed JSON explicitly as UTF-8. The direct evaluation and plotting scripts resolve relative input/output paths from the project root; absolute paths remain supported. `evaluate_matrix.py --cache-dir` and the API's `FEEDCTRL_PARSER_CACHE` likewise use project-relative or absolute paths; standalone evaluation defaults to a raw LLM cache inside its fresh output folder, and the temporary Ollama wrapper writes its server log under the project root even when invoked elsewhere. The standalone frozen control/model modules retain their recorded source; use the documented entry points or pass explicit paths when importing them directly.

The frontend declares Node `^20.19.0 || >=22.12.0`, matching the installed Vite 7.3.1 and React plugin 5.1.4 package requirements. Node 22.12 or newer is the documented build path. No Python upper bound was added: the package permits newer compatible PyTorch releases, while reproduction instructions explicitly select Python 3.12 and PyTorch 2.5.1.

Standalone `evaluate.py` and `evaluate_matrix.py` require a new output directory (an existing empty directory is allowed) and refuse frozen or nonempty destinations. The former treats `--parse-cache` as read-only input and writes its updated cache to the new output folder. Pipeline reruns place evaluation outputs under the new run's `evaluation/` subfolder, separate from its manifest, logs and parser outputs. These guards do not prevent reading the packaged frozen data or checkpoints for replay.
