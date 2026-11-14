# Model routes

> **Current guide.** To install the application first, see [install and run](install-and-run.md).

This page tells you how to connect the application to a language model of your choice.
You do not need one vendor, one subscription or one operating system.

## What a route is

A route is the way a request reaches a model and the reply comes back.
The application gives every route the same two things: an instruction with input data, and a JSON schema for the reply.
Every route returns one JSON object, or an error that says what to change.

The route does not decide anything about recommendations.
The application checks each reply, a person reviews each proposal, and a fixed filter applies only the approved set.
A change of route changes who writes the proposal. It does not change the rest.

You select a route in one small file, `model-route.json`. The file never holds an API key.

## The routes

| Route | How it talks to the model | Use it for | How this project tested it |
| --- | --- | --- | --- |
| `relay` | Request and reply files. A person carries each request to a chat application. | Any model that you can reach only by hand. | Real model output, with an operator in the transport: the run records of 13 November 2026 in `docs/evidence/2026-11-13/`. Those runs started the same relay code with `--provider relay`. The selection through a route file was tested without a model. On the final build, three relay runs with real model output are recorded in `docs/evidence/2026-11-14/real-model-relay/`; they were started with `--provider relay`. |
| `cli`, profile `claude-code` | Starts the Claude Code CLI one time for each request, in print mode. | A Claude Code CLI on Windows or macOS that is signed in to your own account. | Stand-in program only. The real CLI was not run. |
| `cli`, profile `generic` | Starts any program that reads a prompt on standard input and writes the reply to standard output. | Other command-line tools, for example `ollama run MODEL --format json`. | Stand-in program only. |
| `openai-compatible` | `POST {base_url}/chat/completions` | A model server on your computer (Ollama, LM Studio) or a hosted provider that offers this API, with your own key. | Stand-in server only. No real server and no real provider was called. |
| `anthropic` | `POST https://api.anthropic.com/v1/messages` | The Anthropic API with your own key. | Stand-in server only. The real API was not called. |

A stand-in is a small program that answers in the documented format with replies that a person wrote by hand. It is not a model.
The stand-in tests show that each route sends the documented request, reads the documented reply and names each failure.
They do not show that a real provider or a real CLI accepts the request.

**All tests ran on Linux. No run on Windows or macOS exists.** A first real call through the `cli`, `openai-compatible` and `anthropic` routes on Windows and on macOS is still to do.
The parts of the code that apply only to Windows (the split of a command line, the check of a `.cmd` or `.bat` program, the completion of a program path, the stop of a program and of the server) were checked with unit tests on Linux only.

Other servers with an OpenAI-compatible API, for example the llama.cpp server or vLLM, can work with the `openai-compatible` route.
Their documentation was not read for this project, so they are not in the table.

## What a model must be able to do

- **Follow a JSON schema.** The reply must be exactly one JSON object that matches the schema of the request. The application does not repair a reply and does not ask a second time.
- **Read a few thousand tokens.** In the bundled scenarios one request has about 1,200 to 5,600 bytes as a route sends it: the instruction, the schema, and the item data or the category and tag names of eight to ten items. A context window of 8,000 tokens is sufficient for them.
- **Write a few thousand tokens.** The model replies in the 13 November runs had up to 5,700 bytes. A hosted reasoning model counts its reasoning in the output limit. For that reason the default output limit is 16,384 tokens for the preset `openai` and for the `anthropic` route. Every other `openai-compatible` route has 4,096 tokens. For another hosted provider, set a higher limit with `--max-output-tokens`.

A weak model can fail these requirements. Then the application rejects the reply and applies nothing.
That is a result about the model. It is not a defect of the application.
A reply in the correct format can still be wrong in meaning. The review before Apply stays necessary.

## Set up a route

Install the application first. See [install and run](install-and-run.md).
Then run the three steps from the source folder, with the virtual environment active.

```
python scripts/quickstart.py setup
python scripts/quickstart.py doctor
python scripts/quickstart.py start
```

- `setup` asks a few questions and writes `model-route.json`. At the end it offers the check of `doctor`.
- `doctor` confirms that the route works. See [Confirm that the route works](#confirm-that-the-route-works).
- `start` serves the application with the route. Open <http://127.0.0.1:8765>. The default scenario is `tags`: ten invented items with categories and tags. Add `--scenario category` (a new category) or `--scenario hunger` (an indirect request matched to descriptions) for another scenario.

The commands are the same on Windows (PowerShell) and macOS (zsh). On macOS, type `python3` if `python` is not found.
The sections below give the answers for each kind of route, and the same setup as one command without questions.

**`setup` with options** asks no question. It writes the file and then runs the check at once.
If the check fails, for example because the model server is not running, the command ends with exit code 1. The file is written all the same.
Add `--no-check` to write the file only. Add `--yes` to replace a file that exists. The [options](#options-of-the-commands) are at the end of this page.

### A model server on your computer

No key is necessary. The data stays on your computer.

**Ollama.** Install Ollama and get a model, for example `ollama pull llama3.1:8b`. Ollama listens on `http://127.0.0.1:11434`.

```
python scripts/model_route.py setup --route openai-compatible --preset ollama --model llama3.1:8b
```

The preset sets temperature 0 and seed 42, as the original local experiments of this project did.

Set the context length of Ollama to 8,192 tokens or more. The documentation of Ollama gives a default of 4,096 tokens for a computer with less than 24 GiB of video memory, and one request with its reply can be longer than that.
Use the context length slider in the settings of the Ollama application, or start the server with the variable `OLLAMA_CONTEXT_LENGTH`:

| System | Command |
| --- | --- |
| Windows PowerShell | `$env:OLLAMA_CONTEXT_LENGTH = "8192"; ollama serve` |
| macOS zsh | `OLLAMA_CONTEXT_LENGTH=8192 ollama serve` |

`ollama ps` shows the context length that a loaded model uses.

**LM Studio.** Load a model and turn on the local server in the Developer tab. The examples of LM Studio use `http://localhost:1234`.

```
python scripts/model_route.py setup --route openai-compatible --preset lm-studio --model EXACT-MODEL-NAME
```

`setup` with questions lists the model names that the server reports, so that you can choose an exact name.
LM Studio states that not all models can produce structured output, in particular models below 7 billion parameters.
Choose a context length of 8,192 tokens or more when you load the model.

**A server on another computer of your network.** Give its address, for example `http://192.168.1.20:11434/v1`.
An `http://` address of another computer sends the requests without encryption. `setup` with questions asks you to accept that. With options, add `--set allow_insecure_http=true`.

### A hosted provider with your own API key

You need an API key from the provider. A browser subscription to a chat product is not an API key.
The provider bills each call to your account. The data of each request goes to the provider.

```
python scripts/model_route.py setup --route openai-compatible --preset openai --model EXACT-MODEL-NAME
python scripts/model_route.py setup --route anthropic --model EXACT-MODEL-NAME
python scripts/model_route.py setup --route openai-compatible --base-url https://HOST/v1 --api-key-env MY_KEY --model EXACT-MODEL-NAME --max-output-tokens 16384
```

**The key.** The file holds only the name of an environment variable, for example `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`.
The safest way is to leave the variable unset. `doctor` and `start` then ask for the key with a hidden prompt and keep it in memory for that run only.
You can also set the variable for one terminal session:

| System | Command for one session |
| --- | --- |
| Windows PowerShell | `$env:OPENAI_API_KEY = "paste-the-key-here"` |
| macOS zsh | `export OPENAI_API_KEY="paste-the-key-here"` |

A shell can keep typed commands in a history file. If you do not want the key there, use the hidden prompt.
Close the terminal to remove the variable.

**One key, one host.** The key of one provider never goes to another host by default.

- For another provider, name the variable of its key with `--api-key-env`. `setup` with questions gives no default name for another provider.
- The preset `openai` and the `anthropic` route give their key variable only to their own address. With another `base_url`, the route file must name the variable in `api_key_env`. This computer is another host too.
- Before `setup` with questions sends a key, for example to list the model names, it names the host and asks you to confirm.
- At the start, the terminal shows the host that receives the key.

### A command-line program on your computer

**Claude Code CLI.** Install the CLI and sign in to your own account once (`claude`, or `claude auth login`).

```
python scripts/model_route.py setup --route cli --profile claude-code --model FULL-MODEL-NAME
```

- Give the full model name, not a short alias. The route compares it with the model names that the CLI reports after each call. See [Which model answered](#which-model-answered).
- If `claude` is not on the PATH, add `--command "C:\full\path\to\claude.exe"` (Windows) or `--command /full/path/to/claude` (macOS). A relative path and `~` are made into a full path.
- The route starts the CLI one time for each request: `claude -p "..." --output-format json --model NAME --max-turns 1 --safe-mode --no-session-persistence --permission-mode dontAsk --no-chrome --tools "" --disallowedTools "mcp__*"`. The request text goes to standard input. The model gets no tool.
- `extra_args` can add a diagnostic flag such as `--verbose`. It cannot add a flag that gives a tool or a permission, or that changes the model, the output format, the prompt or the session. It cannot hold a key.
- The CLI runs in an empty temporary folder and with a reduced environment. An `ANTHROPIC_API_KEY` in your terminal is not passed on. The CLI documentation says that such a key would replace your subscription sign-in in print mode. If you want that, add the line `"pass_environment": ["ANTHROPIC_API_KEY"]` to `model-route.json`. The same applies to another sign-in variable of the CLI.
- The CLI can repeat a failed API request by itself. The application starts one CLI process for each request and does not count the requests of the CLI.
- The CLI documentation says that `--bare` will become the default of print mode in a future release, and that bare mode does not use the subscription sign-in. The route does not set the mode. When that default changes, a route that uses the sign-in can stop working.

**Another program.** The program must read the prompt on standard input and write only the reply to standard output.

```
python scripts/model_route.py setup --route cli --profile generic --model llama3.1:8b --program "ollama run llama3.1:8b --format json"
```

The model name of this profile is your declaration. The program does not report it.
Put a path that holds a space in double quotes. An argument cannot carry a key (for example `--api-key=...`). If the program needs a key, set it in an environment variable and name that variable in `pass_environment`.
The program gets the variables `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8`, so that a Python program reads the UTF-8 prompt correctly on Windows too.

### By hand

```
python scripts/model_route.py setup --route relay --declared-model "NAME OF THE MODEL" --transport-note "copied by hand into a chat application"
```

`start` then prints the commands for each request. See [the relay provider](demo.md#the-relay-provider).

## Confirm that the route works

```
python scripts/quickstart.py doctor
```

The check does these steps in order and stops at the first step that fails:

1. The route file is valid.
2. The key is present, when the route needs one. A key that cannot be used gets its real cause, for example a space in the value.
3. The server answers and lists the model, or the program starts. For the Claude Code CLI the check also reads the sign-in state. When the server lists the model under a longer name (for example with `:latest` or a date), the line names that listed name and the rule that accepts it.
4. One very small request goes to the model, and the reply passes the format checks. This request can use a few tokens. Add `--no-test-call` to leave this step out.

Each line starts with `OK` or `FAILED`. A failed line is followed by `What to do:`. The command ends with exit code 0 only when every step passed.

The check sends one very small request. To send the bundled requests of a scenario through the route without the browser, run `python scripts/quickstart.py try --scenario tags`. See [route trial](route-trial.md).

```
OK      configuration: Route: openai-compatible; Endpoint: http://127.0.0.1:11434/v1/chat/completions (preset ollama); Model: llama3.1:8b
FAILED  endpoint: Nothing listens at http://127.0.0.1:11434/v1/models on this computer.
        What to do: Start the model server (Ollama: open the Ollama application or run "ollama serve"; ...
```

## Stop the server

Press Ctrl+C in the window of the server, or of `quickstart.py`.

- The application then refuses every new model call.
- A running HTTP call is ended: its connection is closed. A running program is ended, together with the programs that it started. Its temporary folder is removed.
- The server waits at most 10 seconds for open requests, then it stops. A second Ctrl+C stops the wait at once.
- A stop signal (SIGTERM) to `quickstart.py` alone also stops the server in this way.
- A call that was ended fails with the message "The application is stopping".

What was tested: on Linux, Ctrl+C ended the server and a running CLI program in less than 2 seconds, and no second call started (`tests/test_route_launcher_offline.py`). A stop also ended a running HTTP call to a slow stand-in server.
What was not tested: Windows and macOS. On Windows, `quickstart.py` starts the server in a process group of its own and stops it with Ctrl+Break, and a program of a CLI route is ended with `taskkill /T /F`. These steps follow the code of Python and of uvicorn; they were not run on Windows.
If the server process is killed by force (for example `kill -9`, or the end of the process in the Task Manager), it cannot end a running program. That program then runs to its own end.

## If something fails

The page shows the message of a failed call, and the terminal of the server prints one line for each call.
Nothing is applied after a failure. Every call that the route starts counts toward the call allowance, also a failed one.
Every message names the HTTP status that came, when there is one. Messages that are less frequent are in [all messages](#all-messages) at the end of this page.

| Message starts with | Meaning | What to do |
| --- | --- | --- |
| Nothing listens at ... | No server runs at that address on your computer. | Start Ollama or the LM Studio server, or correct `base_url`. |
| The host name ... was not found | The address is wrong, or there is no network connection. | Check `base_url` and the connection. |
| The secure connection ... failed | A certificate was not accepted. | Check the address. On macOS with Python from python.org, run "Install Certificates.command". |
| The environment variable ... is not set | The route needs a key, and the variable is empty. | Set the variable, or start in a terminal: the hidden prompt then asks for the key. |
| The provider rejected the API key (HTTP 401) | The key is wrong, expired or missing. | Check the key in the variable that the message names. Start again. |
| The provider reports a billing, quota or usage-limit problem | The account has no credit, or it reached a spend or usage limit. | Check credit and limits in the account of the provider. |
| The provider refused this request for this account | The account may not use the model, or a network filter stopped the request. | Check the access of the account. |
| The endpoint (or the API) did not find the model ... (HTTP 404) | The model name is wrong, or `base_url` does not end with `/v1`. | Run `doctor` to see the model names. For Ollama, run `ollama pull NAME`. |
| The endpoint did not accept "structured_output": ... | The server does not support that mode. | Set `structured_output` to a value that the message names. Run `doctor`. |
| The endpoint did not accept the output-limit field | The server expects the other field name. | Set `token_limit_field` to the value that the message names. |
| The endpoint did not accept the output limit or the size of the request | The output limit is higher than the model allows, or the request is too long. | Lower `max_output_tokens`, or choose a smaller evidence scope. |
| The provider limits the request rate | Too many requests in a short time. | Wait a minute. |
| ... is overloaded ... / ... had an internal error | A problem on the side of the provider or of the server. | Wait, then try again. |
| The model did not answer within the time limit / The endpoint did not finish its answer within ... | The model is slow, or the request is large. | Try again, or raise `timeout_seconds`. |
| The reply stopped at the output limit | The reply was cut. | Raise `max_output_tokens`, or choose a smaller evidence scope. |
| The model declined to answer | The model refused the request. | Change the request. |
| The reply was wrapped in a Markdown code fence / was not exactly one JSON object | The model did not follow the format. | Use `structured_output: json_schema` where the server supports it, or a stronger model. |
| The reply did not match the schema of the request | The model wrote JSON with wrong fields or values. | Try again, or use a stronger model. |
| The route file names the model ..., and the reply reports ... | Another model answered than the file names. | See [Which model answered](#which-model-answered). |
| The call allowance of this run ... is used | The run reached `max_calls`. | Start the server again, or raise `max_calls`. |
| The program ... was not found | The command is not installed or not on the PATH. | Install it, or give its full path. |
| The CLI did not accept its sign-in state | The CLI is not signed in. | Run `claude auth login`, then try again. If the CLI signs in through a variable, name it in `pass_environment`. |
| The CLI reports a usage or rate limit of the account | The subscription or the account reached a limit. | Wait until the limit resets, or use another route. |
| This version of the CLI does not know the option ... | The installed CLI is older or newer than the flags expect. | Update the CLI, or add the option to `omit_flags`. |
| The application is stopping | The server received a stop signal. | Start the application again. |
| A record file in ... could not be written | The record folder was removed, is full or cannot be written. No further call is made in this run. | Check the folder and the free space, then start again. |

## What is recorded, and what is never recorded

- **The route file** holds the settings. `setup` refuses a setting with the name of a credential, and a value that holds the shape of a key at any place, also inside a JSON text, an argument or an address. It refuses an argument that carries a key, such as `--api-key=...` or `--token`. A key with no known shape cannot be found in every place. At the start, the route also compares the file with the key that it was given, for a key of 16 characters or more.
- **The terminal** shows the route at the start and one line for each call: the duration, and for a failure the category, the message and the action. The terminal shows program paths and arguments in full; the page and the reviews do not.
- **Each call has a receipt**: number, times in UTC, hashes of the request and of the schema, the outcome, the HTTP status or exit code, the model that was requested, the model that the reply reported, the rule that accepted the reported name, and the token counts that the provider reported.
- **A record folder** `runs/route-SCENARIO-DATE-TIMEZ/` (UTC) holds, for each call, the exact request body and the raw reply. For a CLI route it holds the text that went to the program and what the program wrote; standard error is cut at 1,000,000 bytes. The request body contains your request text and the item descriptions of the evidence scope. `runs/` is not part of the Git repository. Add `--record-dir none` to `start` if you do not want these files. A record folder must be new or empty; a `.DS_Store`, `Thumbs.db` or `desktop.ini` file in it does not count.
- **Never recorded:** the API key and any request header. The route keeps the key in memory and removes it from every message, receipt and record file, also in the escaped forms of JSON and of an address. A provider can repeat the key in an error text; it is removed before the text is shown or stored. A key that is a common word (for example `ollama` for a local server, which accepts any key) is removed as a word, so a message can show `[credential removed]` in its place. That shows the word to a reader; use a real key or no key for a hosted provider.

## Model choice and research claims

The route and the research results are separate.

- Every review in the page shows the provider line and stores the route identity: the kind of route, the address, the model name as requested, the limits and the other settings, and a hash of all settings. Program paths and arguments (`command`, `argv`, `extra_args`) and `extra_body` are stored only as a hash. The hash identifies the settings. It does not verify model weights or an account.
- The frozen experiments of this project (Experiment 1, Experiment 2 and the 4 November study) have their own recorded model configuration. A route does not rerun them and cannot change them.
- A run through a route is evidence about that model and those settings only. To compare two models, run the same requests through two route files and keep both record folders ([route trial](route-trial.md) does this without the browser). Such a comparison is a new experiment. It needs its own protocol before the first run.
- The route serves the reviewed language controls of the page. The original conditions A to E keep their own parser setting.

### Which model answered

After each call, the route compares the model name that the reply reports with the name in the route file. It accepts the reported name only by one of these rules, and it writes the rule into the receipt:

| Rule | Example (requested, reported) |
| --- | --- |
| `equal` | `llama3.1:8b`, `llama3.1:8b` |
| `default_tag`: the name plus `:latest`, the default tag of Ollama | `llama3.1`, `llama3.1:latest` |
| `dated_snapshot`: the name plus a date, `-YYYYMMDD` or `-YYYY-MM-DD` | `gpt-4o`, `gpt-4o-2024-08-06` |
| `accepted_by_setting`: an exact name in `accept_reported_models` | `gpt-4`, `gpt-4-0613` with `"accept_reported_models": ["gpt-4-0613"]` |

Every other difference stops the call with "The route file names the model ..., and the reply reports ...". A version suffix is not a date: `claude-opus-5` and `claude-opus-5-5` are two models.
For the Claude Code CLI, the requested model must also be the one that wrote the most output tokens. A small helper model can take part; a fallback model that wrote the answer is another model.
`"allow_reported_model_mismatch": true` accepts and records any difference (rule `difference_allowed_by_setting`). Do not use it for a comparison of models.

## Settings

`setup` writes the settings that are in effect. A setting that is off or not set is left out of the file. An unknown setting is refused, with the nearest known name.

| Setting | Routes | Meaning | Default |
| --- | --- | --- | --- |
| `route` | all | `openai-compatible`, `anthropic`, `cli` or `relay` | required |
| `model` | all but relay | The exact model name | required |
| `base_url` | HTTP routes | Address of the API. `openai-compatible`: ends with `/v1` | from the preset; Anthropic: `https://api.anthropic.com` |
| `preset` | openai-compatible | `openai`, `ollama`, `lm-studio` or `custom`; sets defaults | `custom` |
| `api_key_env` | HTTP routes | NAME of the environment variable with the key | `OPENAI_API_KEY` (preset openai), `ANTHROPIC_API_KEY` (anthropic), only for their own address; none for local servers |
| `profile` | cli | `claude-code` or `generic` | required |
| `structured_output` | HTTP routes, claude-code | `json_schema`, `json_object` (openai-compatible only) or `prompt` | `json_schema`; claude-code: `prompt` |
| `max_output_tokens` | HTTP routes | Output limit of one reply, 16 to 200,000 | 16384 for preset openai and anthropic; 4096 for every other openai-compatible route |
| `timeout_seconds` | all | Time limit of one call, from the first byte sent to the last byte read, 1 to 1800 | 600; relay 1800 |
| `max_calls` | all | Call allowance of one run, 1 to 500. A counter in the program, not a billing limit | 40; relay 10 (at most 10) |

The rare settings are in [the reference of all settings](#reference-of-all-settings).

The structured-output modes of providers accept only a part of JSON Schema.
With `json_schema` the route sends the schema without length and count limits, and for Anthropic with closed objects.
The application then validates the complete schema itself. No check is lost.

The route does not follow a redirect, because a redirect could carry the key to another host.
`http://` is accepted for this computer only, unless `allow_insecure_http` is true. A server on this computer is never reached through a proxy.

## Add another adapter

An adapter returns three things, as every existing provider does:

1. `infer(payload, schema)`: sends one request and returns the reply as a Python dictionary.
2. `identity`: the backend name, the model name and a hash of the settings.
3. `receipts`: a list with one entry for each call.

To add a route kind, write a module that registers one `RouteAdapter` with `feedctrl.model_routes.register_route`:
`validate` (settings), `build` (the three things above), `check` (reachability), `describe` (lines for the terminal) and `key_env` (name of the key variable).
`make_infer` and `parse_reply` in `feedctrl/model_routes.py` supply the shared rules: the call allowance, the stop flag, the receipt, the record files and the one reply rule.
Raise `RouteError` for a failure that a person can act on. Its text is cleaned of keys, made one line of ASCII and bounded when it is built, so the page can show it (`page_safe`).
The recommendation logic, the API and the page need no change. `tests/test_model_routes_offline.py` has a complete small example.

## Reference of all settings

| Setting | Routes | Meaning | Default |
| --- | --- | --- | --- |
| `token_limit_field` | openai-compatible | `max_tokens` or `max_completion_tokens` | `max_completion_tokens` for preset openai, else `max_tokens` |
| `temperature`, `seed` | openai-compatible | Sent only when set; temperature 0 to 2 | preset ollama: 0 and 42 |
| `effort` | anthropic, claude-code | `low`, `medium`, `high`, `xhigh` or `max`. Leave it out for the default of the provider | not sent |
| `anthropic_version` | anthropic | Value of the `anthropic-version` header: `2026-10-21` or `2023-06-01` | `2026-10-21` |
| `auth_header` | anthropic | `authorization` (`Authorization: Bearer KEY`) or `x-api-key` | `authorization` |
| `anthropic_workspace_id` | anthropic | Value of the `anthropic-workspace-id` header, for a key that is not bound to one workspace | not sent |
| `accept_reported_models` | all but relay, generic | Exact model names that a reply may report in place of `model`. See [Which model answered](#which-model-answered) | none |
| `allow_reported_model_mismatch` | all but relay, generic | Accept and record a reply that reports any other model | false |
| `allow_insecure_http` | HTTP routes | Allow `http://` to a computer other than this one | false |
| `extra_body` | HTTP routes | Further request fields, for example `{"reasoning_effort": "low"}`. It cannot replace a field that the route sets (`model`, `messages`, the output limit, `temperature`, `seed` and others) | none |
| `max_request_bytes` | all but relay | Largest request, 1,000 to 5,000,000 bytes. A larger request is refused whole, not cut | 400000 |
| `max_response_bytes` | all but relay | Largest reply or program output, 1,000 to 20,000,000 bytes | 2000000 |
| `command` | claude-code | The CLI: a name on the PATH or a full path | `claude` |
| `omit_flags` | claude-code | Default flags to leave out for an older CLI: `--max-turns`, `--safe-mode`, `--no-session-persistence`, `--permission-mode`, `--no-chrome`, `--tools` | none |
| `extra_args` | claude-code | Diagnostic flags to add, for example `--verbose` | none |
| `max_budget_usd` | claude-code | Cost limit of one call that the CLI applies (`--max-budget-usd`), 0.01 to 1000 | not sent |
| `argv` | generic | The program and its arguments | required |
| `pass_environment` | cli | Names of further environment variables for the program | none |
| `declared_model`, `transport_note` | relay | What the operator declares | required |

## Options of the commands

`python scripts/model_route.py setup` (and `quickstart.py setup`):

| Option | Meaning |
| --- | --- |
| `--file PATH` (also `--route-file`) | The route file. Default: `model-route.json` in the source folder. `check` and `show` take it too. |
| `--yes` | Replace a route file that exists. |
| `--no-check` | Write the file only. Without it, `setup` with options runs the check and ends with exit code 1 when the check fails. |
| `--route`, `--profile`, `--preset`, `--base-url`, `--model`, `--api-key-env`, `--structured-output`, `--command`, `--program`, `--declared-model`, `--transport-note`, `--effort` | The settings of the same names. With `--route`, no question is asked. |
| `--max-calls`, `--timeout-seconds`, `--max-output-tokens` | The limits of the same names. |
| `--set NAME=VALUE` | Any other setting. The value is read as JSON, for example `--set allow_insecure_http=true` or `--set 'accept_reported_models=["gpt-4-0613"]'`. |

`python scripts/model_route.py check` (and `quickstart.py doctor`): `--file PATH`, `--no-test-call`.

`python scripts/quickstart.py start`:

| Option | Meaning |
| --- | --- |
| `--scenario NAME` | `tags` (default), `category` or `hunger`. |
| `--port N` | The port on 127.0.0.1. Default 8765. A port in use stops the command with a message and exit code 1. |
| `--route-file PATH` | The route file. A relative path is read from your current folder. |
| `--record-dir PATH` | A new folder for the call records, or `none`. A relative path is read from your current folder. |

`python scripts/run_demo.py --provider route` also takes `--max-calls N`: it sets the call allowance of this run, within the limits of the route kind. The options `--declared-model`, `--transport-note` and `--relay-timeout` belong to `--provider relay`; with a route file, put these settings in the file.

## All messages

The table [If something fails](#if-something-fails) has the frequent messages. These are the others. Each message is followed by what to do.

| Message starts with | Meaning |
| --- | --- |
| The endpoint answered with a redirect (HTTP N) to ... | A redirect is not followed. Put the final address in `base_url` if it is the right one. |
| The endpoint rejected the request (HTTP N) / The API rejected the request (HTTP N) | Read the provider message and change the setting that it names. |
| The endpoint answered HTTP N, which is not a reply ... | The server answered with a status that a chat request does not get. Check that the route kind matches the server. |
| The endpoint answered HTTP 200 with an error object | Some servers report an error this way, for example while a model loads. Wait and try again. |
| The endpoint did not accept "temperature" or "seed" | Remove `temperature` and `seed` from the route file. |
| The request has N bytes | The request is larger than `max_request_bytes`. Nothing was sent. Choose a smaller evidence scope, or raise the limit. |
| The request is larger than the API accepts | The API refused the size (HTTP 413). Choose a smaller evidence scope. |
| The endpoint sent more than N bytes / The program ... wrote more than N bytes | The reply is larger than `max_response_bytes`. The program was stopped. |
| The reply JSON holds more text than the application accepts | A fixed limit of the application (2,000,000 characters). Choose a smaller evidence scope. |
| The reply JSON is nested deeper than 64 levels / holds a number that is not finite / repeats a key | The reply breaks the fixed reply rule. Use a model that follows the schema. |
| The reply starts or ends with the character U+... | A character that is not white space of JSON (for example a non-breaking space) stands around the object. It is not removed. |
| The endpoint did not return a chat completion object / The API did not return a message object | The server answered in another form. Check the route kind and `base_url`. |
| The endpoint returned N choices; one is expected | The route asks for one reply and never chooses between several. |
| The model asked for a tool call | The route gives the model no tool. Use another model or `structured_output`. |
| The reply holds no text / holds N text blocks | The reply has no single text to read. Try again, or use another model. |
| The request and the reply together filled the context window | Choose a smaller evidence scope, or a model with a larger context. |
| The API reports a spend or usage limit | Check the limits of the account. |
| The host ... refused the connection / The endpoint ... did not answer | The server is not reachable. Check the address and the network. |
| The program ... did not finish within N s | The program was stopped at `timeout_seconds`. |
| The CLI stopped at its turn limit | Try again. If it continues, add `--max-turns` to `omit_flags`. |
| The CLI stopped at the cost limit of this call | Raise `max_budget_usd`. |
| The CLI ended with exit code N / The program ended with exit code N | Read the message. Run the same program by hand to see more. |
| The CLI output was not one JSON result object. It started with: ... | The CLI printed another line, for example a notice. Remove its cause, or check that `command` is the Claude Code CLI. |
| The output of the CLI repeats a key or holds a number that is not finite | The output breaks the reply rule. Try again, or set `structured_output` to `prompt`. |
| The CLI returned no structured output | With `json_schema` the CLI gave no `structured_output`. The model may have declined. |
| The output of the program is not UTF-8 text | Make the program write UTF-8. |
| The program ... could not be started | The file is not a program, or it may not run. On Windows give a `.exe`, `.cmd` or `.bat` file. |
| A value for the command line holds a character that cmd.exe gives a meaning to | A `.cmd` or `.bat` program gets its arguments through cmd.exe. Remove `& | < > ^ % ! "`, or give the program file itself. |
| The value of ... holds a space or a line break / a character that is not a printable ASCII character | Copy the key again without the text around it, and without the word "Bearer". |
| The route file holds the API key itself | Remove the key from the file. Keep it in the environment variable only. |
| The route file ... does not exist / is not valid JSON / cannot be read / cannot be written | Write the file with `setup`, or check its folder and permissions. |
| The record folder ... is not empty / cannot be used | Give a new folder for each run, or `none`. |
| The relay folder ... is not empty / cannot be used | Give a new folder with `--relay-dir`, or leave the option out. |
| The route failed in an unexpected way | A defect of the route, not of the provider. Report it with the receipt of the call. |
| The setting ... is missing or not valid / must be ... / The route file has a setting that ... does not know | Correct the setting that the message names. The message gives the allowed values or the nearest known name. |
| A credential must not be in the route file / A value in the route file looks like a credential / The setting ... holds an argument that carries a credential | Put the key in an environment variable and name it in `api_key_env` (or in `pass_environment` for a program). |
| The preset ... is for ... / The default key variable of this route is for ... | The file names another address. Name the key variable for that host in `api_key_env`. |
| The setting "extra_args" must not hold ... / "omit_flags" can name only ... | These flags would give the model a tool, a permission, another model or another output format. |
| No usable answer after 8 tries | `setup` with questions got no answer that it can use. Nothing was written. |

## References checked

Read on 14 November 2026 (UTC). Each wire detail of the routes comes from these pages.

| Page | What was confirmed |
| --- | --- |
| <https://developers.openai.com/api/reference/python/resources/chat/subresources/completions/methods/create> | `POST /chat/completions`; `response_format` with `json_schema` and `json_object`; `max_tokens` is deprecated in favour of `max_completion_tokens`; response fields `model`, `choices[].message.content`, `refusal`, `finish_reason`, `usage`. The complete list of `finish_reason` values was not in the text that was read. |
| <https://developers.openai.com/api/docs/guides/structured-outputs> | Shape `{"type": "json_schema", "json_schema": {"name", "strict", "schema"}}`; refusals in `message.refusal`. The list of supported schema keywords was not on this page. |
| <https://developers.openai.com/api/docs/guides/error-codes.md> | Meaning of 401, 403, 429, 500 and 503. "429 - Organization usage limit reached" is a limit of the account, not of the request rate, so the route reports it as a billing or usage-limit problem. |
| <https://docs.ollama.com/api/openai-compatibility.md> | Base address `http://localhost:11434/v1/`; `/v1/chat/completions`, `/v1/models`; supported fields include `response_format`, `seed`, `temperature`, `max_tokens`. `max_completion_tokens` is not listed. A local server ignores the key. |
| <https://docs.ollama.com/capabilities/structured-outputs> | Structured outputs work through the OpenAI-compatible API with `response_format`; temperature 0 is recommended. The page shows no example of that request. |
| <https://docs.ollama.com/context-length> | Default context length by video memory (4k below 24 GiB); the settings slider; `OLLAMA_CONTEXT_LENGTH`; `ollama ps`. The page does not say what happens to a prompt that is longer than the context. |
| <https://lmstudio.ai/docs/developer/openai-compat> and <https://lmstudio.ai/docs/developer/openai-compat/structured-output> | `GET /v1/models`, `POST /v1/chat/completions`; examples on port 1234; `response_format` with `json_schema`; the example key `lm-studio`. The example writes `"strict": "true"` as text; the route sends a boolean, and the effect of that difference is not known. `json_object` and the need for a key are not stated. |
| <https://platform.claude.com/docs/en/api/overview> and <https://platform.claude.com/docs/en/api/versioning> | Headers `Authorization: Bearer` (or `x-api-key`), `anthropic-version`, `content-type`, `anthropic-workspace-id` ("Required with an API key that isn't scoped to a workspace"); version `2026-10-21` removes `temperature`, `top_p` and `top_k`; response header `request-id`. |
| <https://platform.claude.com/docs/en/api/messages/create> | Body fields `model`, `max_tokens`, `messages`, `system`, `output_config` with `format` and `effort`; response fields `content`, `model`, `stop_reason`, `usage`. |
| <https://platform.claude.com/docs/en/build-with-claude/structured-outputs> | `output_config.format` with `type: json_schema` is generally available without a beta header; unsupported schema keywords give a 400 error; `stop_reason` `refusal` and `max_tokens` can leave the reply outside the schema. |
| <https://platform.claude.com/docs/en/api/errors> and <https://platform.claude.com/docs/en/api/handling-stop-reasons> | Error types and status codes 400, 401, 402, 403, 404, 413, 429, 500, 504 and 529; the error body; the seven `stop_reason` values. The errors page advises against a large `max_tokens` without streaming. The route does not stream, so keep `max_output_tokens` and `timeout_seconds` near their defaults. |
| <https://platform.claude.com/docs/en/api/models/list> | `GET /v1/models`, `limit` up to 1000, response fields `data[].id` and `has_more`. |
| <https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions> and <https://platform.claude.com/docs/en/about-claude/models/overview> | From the 4.6 generation, the dateless ID is the canonical ID of a release, and IDs such as `claude-opus-5` and `claude-opus-5-5` are two models. That is why a suffix that is not a date is not accepted as a snapshot. |
| <https://code.claude.com/docs/en/headless> and <https://code.claude.com/docs/en/cli-reference> | `claude -p` with piped input; `--output-format json` with `result`, cost and session metadata; `--json-schema` and `structured_output`; the flags `--model`, `--effort`, `--max-turns`, `--max-budget-usd`, `--tools`, `--disallowedTools`, `--safe-mode`, `--no-session-persistence`, `--permission-mode`, `--no-chrome`; `claude auth status` (exit code 0 if signed in, 1 if not); `--bare` will become the default of `-p`. The field `modelUsage` of the result object is not described on these pages; the route reads it as the earlier reviewed adapter of this project does. |
| <https://code.claude.com/docs/en/env-vars> | `ANTHROPIC_API_KEY` replaces the subscription sign-in in print mode when it is set; `CLAUDE_CODE_GIT_BASH_PATH` (Windows only) is passed to the CLI. |

The pages about model IDs, the error codes of OpenAI, the workspace header, the `--bare` mode, the Git Bash variable and the LM Studio example were read by the independent review of the routes on 14 November 2026; its report quotes them.
The Windows stop steps follow the source of Python 3.13 (`subprocess.Popen.send_signal` with `CTRL_BREAK_EVENT`) and of uvicorn 0.42 (it handles `SIGBREAK` on Windows).

Not verified: the behaviour of any real server, provider or CLI with these requests. The official pages were read; the services were not called.
