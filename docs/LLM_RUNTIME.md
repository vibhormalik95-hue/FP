# Local Llama runtime

The fresh Experiment Two run completed locally on AI_WORK on 14 October with Ollama 0.34.0 and the `llama3.1:8b` digest recorded in the [study evidence](ai-reference-e2-evidence/README.md). This page lists the runtime settings and steps for a separate rerun.

The backend is Ollama with `llama3.1:8b`. The original Experiment One implementation defaults to a maximum of 256 generated tokens for a single control and 1536 for a multi-preference profile. The completed Experiment Two run instead recorded a 768-token maximum for each question. Both use `/api/chat` with structured output, temperature 0, seed 42 and context length 4096. Application validation checks allowed categories, exact keys, numeric values and operation-specific strength. Record the Ollama version and model digest for a rerun; a model tag alone is not a permanent version.

Only loopback HTTP origins are accepted. `localhost` is canonicalized to `127.0.0.1`; credentials, remote IPs/hosts, paths, query strings, fragments, and redirects are rejected. No API key is required for a local server. Do not expose the development Ollama port to the public Internet.

## Week 3 local runtime check, 20 October 2026 UTC

At 03:27 UTC, the documented temporary-server wrapper started installed Ollama 0.34.0 on `127.0.0.1:11434`. `ollama list` reported local `llama3.1:8b` with digest prefix `46e0c10c039e`; the installed model manifest's SHA-256 was the complete committed digest `46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e`. The model layer was present at its declared 4,920,738,944 bytes. No model pull was requested.

One existing development utterance, `e2-dev-001` (`I would like more category_0 and less category_12.`), passed through the unchanged `ollama_compound` parser with seed 42, six threads and a temporary cache. It returned a validated `set` command with moderate boost of `category_0` and moderate reduction of `category_12`, both with floor 0 and no condition, and reported the complete digest above. The temporary cache response has SHA-256 `e66d49d69cb872fa4efeb6473976b451ba9e607a3a163e36a5f88d5dbbb73491`; the local server log is `results/ollama_server.log`. The wrapper stopped the server after the check, and no Ollama process remained in the post-run process check.

This verifies one development parse and local runtime availability. It did not open reserved Experiment Two test inputs, perform a new evaluation, or complete the original human-annotation and full-freeze gate.

## Windows 11 (32 GB RAM laptop)

1. Install Ollama from <https://ollama.com/download/windows>.
2. Open PowerShell and run `ollama pull llama3.1:8b` once. The model download observed in this project is approximately 4.92 GB; allow additional runtime and cache disk space.
3. Install the project Python dependencies using the [Windows setup steps](windows-and-colab.md#windows-reproduce-the-experiment). The public checkout omits both parser banks. Ollama normally runs in the Windows background already.
4. With an authorized development input, run from the project root:

```powershell
.\.venv\Scripts\python.exe scripts/run_parser.py --data data/parser_dev.jsonl --backend ollama --output results/my-parser-dev
```

The reserved parser test and frozen Experiment One outputs are not a development target. Their original bank and labels remain unchanged; any authorized replay must be recorded separately from the saved result.

CPU inference is supported but speed depends on the exact CPU, available memory, cooling, and other work. No GPU is assumed from “Core i9.” A compatible GPU may accelerate it. Do not run another memory-intensive workload concurrently on a tight machine.

## Linux and Colab reruns

Ollama's official Linux instructions are at <https://docs.ollama.com/linux>. Install the official package or inspect and run the official installer. This project does not silently execute an installer on the user's laptop. In an ephemeral notebook, preserve outputs before the runtime disconnects. Colab GPU type/availability and session lifetime are not guaranteed.

After installation, the wrapper starts a temporary local server, optionally pulls the model, runs a command, then terminates the server:

```bash
python scripts/with_ollama.py -- python scripts/run_parser.py --data data/parser_dev.jsonl --backend ollama --output results/parser_ollama_dev
```

If Ollama is already running, run `scripts/run_parser.py` directly. The wrapper is intended for an otherwise unused port 11434 and exits if its server cannot start.

## Earlier Experiment One Linux VM

This section describes the earlier Experiment One Linux VM, not the 14 October Experiment Two run on AI_WORK. The VM had an 8 GiB cgroup memory limit and no detected GPU. The official Ollama v0.34.4 Linux archive was streamed and only CPU binaries/libraries extracted (about 58 MB) to `/tmp/ollama-runtime`. Its upstream URL is <https://github.com/ollama/ollama/releases/download/v0.34.4/ollama-linux-amd64.tar.zst>. Models resided temporarily in `/tmp/ollama-models`; neither runtime nor model weights are distributed in the project archive. The model manifest identified a 4,920,738,944-byte model layer with SHA-256 `667b0c1932bc6ffc593ed1d03f895bf2dc8dc6df21db3042284a6f4416b06a29`. Record the manifest digest from `/api/tags` separately.

Each shell tool invocation has its own network namespace in this environment. A localhost server and client must therefore run inside the same wrapper invocation; files remain shared. This is a VM property, not a requirement for normal Windows/Linux use:

```bash
python scripts/with_ollama.py --binary /tmp/ollama-runtime/bin/ollama --models /tmp/ollama-models -- python scripts/run_parser.py --backend ollama --output results/parser_ollama_test
```

## Official API references (checked September 28, 2026)

- Structured output and application validation: <https://docs.ollama.com/capabilities/structured-outputs>
- Chat request/response fields: <https://docs.ollama.com/api/chat>
- Windows local installation and endpoint: <https://docs.ollama.com/windows>
- Linux installation: <https://docs.ollama.com/linux>
- Llama 3.1 model entry: <https://ollama.com/library/llama3.1>

Ollama's hosted Cloud service currently does not support this structured-output feature. “Cloud compute” here means running the local Ollama server inside a cloud VM/notebook; it does not mean using Ollama Cloud.

## Grounded explanations

`feedctrl.explanations` sends the model only verified item/category/history facts. The response schema permits one to three verbatim statements from that fact set. Application validation checks item identity and every selected statement, and renders the explanation from the validated strings. This is **LLM selection of grounded statements**, not unrestricted narrative generation or evidence of human-perceived explanation quality. Category labels remain opaque; historical association is not a causal explanation of the model.

`python scripts/generate_explanations.py --backend ollama --count 10` creates a limited cache for the first processed user's baseline top ten items using seed 42. The UI uses an exact fact-set hash to reuse a matching record; other cards receive a visibly labeled verified-template fallback. The final report must distinguish the number of actual LLM records from total possible user/item pairs. Neither cached statements nor the act of displaying explanations changes the rank order in condition B.
