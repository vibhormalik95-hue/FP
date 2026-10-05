# Local Llama runtime

The research backend is Ollama with `llama3.1:8b`. Actual experiments must record the Ollama version and model digest, because a tag alone is not a permanent version. The implementation calls `/api/chat` with a JSON Schema in `format`, `stream:false`, temperature 0, seed 42, context length 4096, and maximum 256 generated tokens for a single control (1536 for a multi-preference profile). Application validation checks category allowlists, exact keys, numeric values, and operation-specific strength after model output. Temperature zero is a reproducibility aid, not a guarantee of cross-hardware bitwise identity.

Only loopback HTTP origins are accepted. `localhost` is canonicalized to `127.0.0.1`; credentials, remote IPs/hosts, paths, query strings, fragments, and redirects are rejected. No API key is required for a local server. Do not expose the development Ollama port to the public Internet.

## Windows 11 (the user's 32 GB RAM laptop)

1. Install Ollama from <https://ollama.com/download/windows>.
2. Open PowerShell and run `ollama pull llama3.1:8b` once. The model download observed in this project is approximately 4.92 GB; allow additional runtime and cache disk space.
3. Install the project Python dependencies per the main README. Ollama normally runs in the Windows background already.
4. From the project root, run:

```powershell
.\.venv\Scripts\python.exe scripts/run_parser.py --data data/parser_dev.jsonl --backend ollama --output results/my-parser-dev
.\.venv\Scripts\python.exe scripts/run_parser.py --data data/parser_test.jsonl --backend ollama --output results/my-parser-test
```

CPU inference is supported but speed depends on the exact CPU, available memory, cooling, and other work. No GPU is assumed from “Core i9.” A compatible GPU may accelerate it. Do not run another memory-intensive workload concurrently on a tight machine.

## Linux / Colab

Ollama's official Linux instructions are at <https://docs.ollama.com/linux>. Install the official package or inspect and run the official installer. This project does not silently execute an installer on the user's laptop. In an ephemeral notebook, preserve outputs before the runtime disconnects. Colab GPU type/availability and session lifetime are not guaranteed.

After installation, the wrapper starts a temporary local server, optionally pulls the model, runs a command, then terminates the server:

```bash
python scripts/with_ollama.py --pull -- python scripts/run_parser.py --backend ollama --output results/parser_ollama_test
```

If Ollama is already running, run `scripts/run_parser.py` directly. The wrapper is intended for an otherwise unused port 11434 and exits if its server cannot start.

## Execution VM used for this package

The VM has an 8 GiB cgroup memory limit and no detected GPU. The official Ollama v0.34.4 Linux archive was streamed and only CPU binaries/libraries extracted (about 58 MB) to `/tmp/ollama-runtime`. Its upstream URL is <https://github.com/ollama/ollama/releases/download/v0.34.4/ollama-linux-amd64.tar.zst>. Models reside temporarily in `/tmp/ollama-models`; neither runtime nor model weights are distributed in the project archive. The model manifest downloaded from the official registry identifies a 4,920,738,944-byte model layer with SHA-256 `667b0c1932bc6ffc593ed1d03f895bf2dc8dc6df21db3042284a6f4416b06a29`. Record the manifest digest from `/api/tags` separately.

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
