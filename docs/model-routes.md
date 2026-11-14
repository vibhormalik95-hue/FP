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
| `relay` | Request and reply files. A person carries each request to a chat application. | Any model that you can reach only by hand. | Real model output, with an operator in the transport: the run records of 13 November 2026 in `docs/evidence/2026-11-13/`. Those runs started the same relay code with `--provider relay`. The selection through a route file was tested without a model. Not yet recorded for the integrated final revision. |
| `cli`, profile `claude-code` | Starts the Claude Code CLI one time for each request, in print mode. | A Claude Code CLI on Windows or macOS that is signed in to your own account. | Stand-in program only. The real CLI was not run. |
| `cli`, profile `generic` | Starts any program that reads a prompt on standard input and writes the reply to standard output. | Other command-line tools, for example `ollama run MODEL --format json`. | Stand-in program only. |
| `openai-compatible` | `POST {base_url}/chat/completions` | A model server on your computer (Ollama, LM Studio) or a hosted provider that offers this API, with your own key. | Stand-in server only. No real server and no real provider was called. |
| `anthropic` | `POST https://api.anthropic.com/v1/messages` | The Anthropic API with your own key. | Stand-in server only. The real API was not called. |

A stand-in is a small program that answers in the documented format with replies that a person wrote by hand. It is not a model.
The stand-in tests show that each route sends the documented request, reads the documented reply and names each failure.
They do not show that a real provider or a real CLI accepts the request.
**A first real call through the `cli`, `openai-compatible` and `anthropic` routes on Windows or macOS is still to do.**

Other servers with an OpenAI-compatible API, for example the llama.cpp server or vLLM, can work with the `openai-compatible` route.
Their documentation was not read for this project, so they are not in the table.

## What a model must be able to do

- **Follow a JSON schema.** The reply must be exactly one JSON object that matches the schema of the request. The application does not repair a reply and does not ask a second time.
- **Read a few thousand tokens.** In the bundled scenarios one request has about 1,200 to 5,600 bytes as a route sends it: the instruction, the schema, and the item data or the category and tag names of eight to ten items. A context window of 8,000 tokens is sufficient for them.
- **Write a few thousand tokens.** The model replies in the 13 November runs had up to 5,700 bytes. A hosted reasoning model counts its reasoning in the output limit. For that reason the default output limit is 16,384 tokens for the hosted routes and 4,096 tokens for a model on your computer.

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

- `setup` asks a few questions and writes `model-route.json`.
- `doctor` confirms that the route works. See [Confirm that the route works](#confirm-that-the-route-works).
- `start` serves the application with the route. Open <http://127.0.0.1:8765>. The default scenario is `tags`: ten invented items with categories and tags. Add `--scenario category` (a new category) or `--scenario hunger` (an indirect request matched to descriptions) for another scenario.

The commands are the same on Windows (PowerShell) and macOS (zsh). On macOS, type `python3` if `python` is not found.
The sections below give the answers for each kind of route, and the same setup as one command without questions.

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

### A hosted provider with your own API key

You need an API key from the provider. A browser subscription to a chat product is not an API key.
The provider bills each call to your account. The data of each request goes to the provider.

```
python scripts/model_route.py setup --route openai-compatible --preset openai --model EXACT-MODEL-NAME
python scripts/model_route.py setup --route anthropic --model EXACT-MODEL-NAME
python scripts/model_route.py setup --route openai-compatible --base-url https://HOST/v1 --api-key-env MY_KEY --model EXACT-MODEL-NAME
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

### A command-line program on your computer

**Claude Code CLI.** Install the CLI and sign in to your own account once (`claude`, or `claude auth login`).

```
python scripts/model_route.py setup --route cli --profile claude-code --model FULL-MODEL-NAME
```

- Give the full model name, not a short alias. The route compares it with the model names that the CLI reports after each call.
- If `claude` is not on the PATH, add `--command "C:\full\path\to\claude.exe"` (Windows) or `--command /full/path/to/claude` (macOS).
- The route starts the CLI one time for each request: `claude -p --output-format json --model NAME --max-turns 1 --safe-mode --no-session-persistence --permission-mode dontAsk --no-chrome`, without tools. The request text goes to standard input.
- The CLI runs in an empty temporary folder and with a reduced environment. An `ANTHROPIC_API_KEY` in your terminal is not passed on. The CLI documentation says that such a key would replace your subscription sign-in in print mode. If you want that, add the line `"pass_environment": ["ANTHROPIC_API_KEY"]` to `model-route.json`.
- The CLI can repeat a failed API request by itself. The application starts one CLI process for each request and does not count the requests of the CLI.

**Another program.** The program must read the prompt on standard input and write only the reply to standard output.

```
python scripts/model_route.py setup --route cli --profile generic --model llama3.1:8b --program "ollama run llama3.1:8b --format json"
```

The model name of this profile is your declaration. The program does not report it.

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
2. The key is present, when the route needs one.
3. The server answers and lists the model, or the program starts. For the Claude Code CLI the check also reads the sign-in state.
4. One very small request goes to the model, and the reply passes the format checks. This request can use a few tokens. Add `--no-test-call` to leave this step out.

Each line starts with `OK` or `FAILED`. A failed line is followed by `What to do:`. The command ends with exit code 0 only when every step passed.

The check sends one very small request. To send the bundled requests of a scenario through the route without the browser, run `python scripts/quickstart.py try --scenario tags`. See [route trial](route-trial.md).

```
OK      configuration: Route: openai-compatible; Endpoint: http://127.0.0.1:11434/v1/chat/completions (preset ollama); Model: llama3.1:8b
FAILED  endpoint: Nothing listens at http://127.0.0.1:11434/v1/models on this computer.
        What to do: Start the model server (Ollama: open the Ollama application or run "ollama serve"; ...
```

## If something fails

The page shows the message of a failed call, and the terminal of the server prints one line for each call.
Nothing is applied after a failure. Each call counts toward the call allowance, also a failed one.

| Message starts with | Meaning | What to do |
| --- | --- | --- |
| Nothing listens at ... | No server runs at that address on your computer. | Start Ollama or the LM Studio server, or correct `base_url`. |
| The host name ... was not found | The address is wrong, or there is no network connection. | Check `base_url` and the connection. |
| The secure connection ... failed | A certificate was not accepted. | Check the address. On macOS with Python from python.org, run "Install Certificates.command". |
| The provider rejected the API key (HTTP 401) | The key is wrong, expired or missing. | Check the key in the variable that the message names. Start again. |
| The provider reports a billing or quota problem | The account has no credit or reached a spend limit. | Check credit and limits in the account of the provider. |
| The provider refused the request for this account | The account may not use the model, or a network filter stopped the request. | Check the access of the account. |
| The endpoint (or the API) did not find the model ... (HTTP 404) | The model name is wrong, or `base_url` does not end with `/v1`. | Run `doctor` to see the model names. For Ollama, run `ollama pull NAME`. |
| The endpoint did not accept "structured_output": ... | The server does not support that mode. | Set `structured_output` to the value that the message names. Run `doctor`. |
| The endpoint did not accept the output-limit field | The server expects the other field name. | Set `token_limit_field` to the value that the message names. |
| The provider limits the request rate | Too many requests in a short time. | Wait a minute. |
| ... is overloaded ... / ... had an internal error | A problem on the side of the provider or of the server. | Wait, then try again. |
| The model did not answer within the time limit | The model is slow, or the request is large. | Try again, or raise `timeout_seconds`. |
| The reply stopped at the output limit | The reply was cut. | Raise `max_output_tokens`, or choose a smaller evidence scope. |
| The model declined to answer | The model refused the request. | Change the request. |
| The reply was wrapped in a Markdown code fence / was not exactly one JSON object | The model did not follow the format. | Use `structured_output: json_schema` where the server supports it, or a stronger model. |
| The reply did not match the schema of the request | The model wrote JSON with wrong fields or values. | Try again, or use a stronger model. |
| The route file names the model ..., and the reply reports ... | Another model answered than the file names. | Put the reported name in `model`, or set `allow_reported_model_mismatch` to true. |
| The call allowance of this run ... is used | The run reached `max_calls`. | Start the server again, or raise `max_calls`. |
| The program ... was not found | The command is not installed or not on the PATH. | Install it, or give its full path. |
| The CLI did not accept its sign-in state | The CLI is not signed in. | Run `claude auth login`, then try again. |
| This version of the CLI does not know the option ... | The installed CLI is older or newer than the flags expect. | Update the CLI, or add the option to `omit_flags`. |

## What is recorded, and what is never recorded

- **The route file** holds the settings. `setup` refuses a setting that is a credential or looks like one.
- **The terminal** shows the route at the start and one line for each call: the duration, and for a failure the category, the message and the action.
- **Each call has a receipt**: number, times, hashes of the request and of the schema, the outcome, the HTTP status or exit code, the model that was requested, the model that the reply reported, and the token counts that the provider reported.
- **A record folder** `runs/route-SCENARIO-DATE-TIME/` holds, for each call, the exact request body and the raw reply. For a CLI route it holds the text that went to the program and what the program wrote. The request body contains your request text and the item descriptions of the evidence scope. `runs/` is not part of the Git repository. Add `--record-dir none` to `start` if you do not want these files.
- **Never recorded:** the API key and any request header. If a provider repeats the key in an error text, the route removes it before the text is shown or stored.

## Model choice and research claims

The route and the research results are separate.

- Every review in the page shows the provider line and stores the route identity: the kind of route, the model name as requested, and a hash of the route settings. The hash identifies the settings. It does not verify model weights or an account.
- The frozen experiments of this project (Experiment 1, Experiment 2 and the 4 November study) have their own recorded model configuration. A route does not rerun them and cannot change them.
- A run through a route is evidence about that model and those settings only. To compare two models, run the same requests through two route files and keep both record folders ([route trial](route-trial.md) does this without the browser). Such a comparison is a new experiment. It needs its own protocol before the first run.
- The route serves the reviewed language controls of the page. The original conditions A to E keep their own parser setting.

## Settings

`setup` writes every setting that is in effect, so the file shows the defaults too. An unknown setting is refused.

| Setting | Routes | Meaning | Default |
| --- | --- | --- | --- |
| `route` | all | `openai-compatible`, `anthropic`, `cli` or `relay` | required |
| `model` | all but relay | The exact model name | required |
| `base_url` | HTTP routes | Address of the API. `openai-compatible`: ends with `/v1` | from the preset; Anthropic: `https://api.anthropic.com` |
| `preset` | openai-compatible | `openai`, `ollama`, `lm-studio` or `custom`; sets defaults | `custom` |
| `api_key_env` | HTTP routes | NAME of the environment variable with the key | `OPENAI_API_KEY` (preset openai), `ANTHROPIC_API_KEY` (anthropic), none for local servers |
| `structured_output` | HTTP routes, claude-code | `json_schema`, `json_object` (openai-compatible only) or `prompt` | `json_schema`; claude-code: `prompt` |
| `token_limit_field` | openai-compatible | `max_tokens` or `max_completion_tokens` | `max_completion_tokens` for preset openai, else `max_tokens` |
| `max_output_tokens` | HTTP routes | Output limit of one reply | 16384 hosted, 4096 local |
| `temperature`, `seed` | openai-compatible | Sent only when set | preset ollama: 0 and 42 |
| `effort` | anthropic, claude-code | `low`, `medium`, `high`, `xhigh` or `max` | not sent |
| `timeout_seconds` | all | Time limit of one call | 600; relay 1800 |
| `max_calls` | all | Call allowance of one run. A counter in the program, not a billing limit | 40; relay 10 |
| `allow_reported_model_mismatch` | all but relay, generic | Accept and record a reply that reports another model | false |
| `allow_insecure_http` | HTTP routes | Allow `http://` to a computer other than this one | false |
| `extra_body` | HTTP routes | Further request fields, for example `{"reasoning_effort": "low"}` | none |
| `command`, `omit_flags`, `extra_args` | claude-code | The program, default flags to leave out, flags to add | `claude`, none, none |
| `argv` | generic | The program and its arguments | required |
| `pass_environment` | cli | Names of further environment variables for the program | none |
| `declared_model`, `transport_note` | relay | What the operator declares | required |

The structured-output modes of providers accept only a part of JSON Schema.
With `json_schema` the route sends the schema without length and count limits, and for Anthropic with closed objects.
The application then validates the complete schema itself. No check is lost.

The route does not follow a redirect, because a redirect could carry the key to another host.
`http://` is accepted for this computer only, unless `allow_insecure_http` is true.

## Add another adapter

An adapter returns three things, as every existing provider does:

1. `infer(payload, schema)`: sends one request and returns the reply as a Python dictionary.
2. `identity`: the backend name, the model name and a hash of the settings.
3. `receipts`: a list with one entry for each call.

To add a route kind, write a module that registers one `RouteAdapter` with `feedctrl.model_routes.register_route`:
`validate` (settings), `build` (the three things above), `check` (reachability), `describe` (lines for the terminal) and `key_env` (name of the key variable).
`make_infer` and `parse_reply` in `feedctrl/model_routes.py` supply the shared rules: the call allowance, the receipt, the record files and the one reply rule.
The recommendation logic, the API and the page need no change. `tests/test_model_routes_offline.py` has a complete small example.

## References checked

Read on 14 November 2026 (UTC). Each wire detail of the routes comes from these pages.

| Page | What was confirmed |
| --- | --- |
| <https://developers.openai.com/api/reference/python/resources/chat/subresources/completions/methods/create> | `POST /chat/completions`; `response_format` with `json_schema` and `json_object`; `max_tokens` is deprecated in favour of `max_completion_tokens`; response fields `model`, `choices[].message.content`, `refusal`, `finish_reason`, `usage`. The complete list of `finish_reason` values was not in the text that was read. |
| <https://developers.openai.com/api/docs/guides/structured-outputs> | Shape `{"type": "json_schema", "json_schema": {"name", "strict", "schema"}}`; refusals in `message.refusal`. The list of supported schema keywords was not on this page. |
| <https://developers.openai.com/api/docs/guides/error-codes.md> | Meaning of 401, 403, 429, 500 and 503. |
| <https://docs.ollama.com/api/openai-compatibility.md> | Base address `http://localhost:11434/v1/`; `/v1/chat/completions`, `/v1/models`; supported fields include `response_format`, `seed`, `temperature`, `max_tokens`. `max_completion_tokens` is not listed. A local server ignores the key. |
| <https://docs.ollama.com/capabilities/structured-outputs> | Structured outputs work through the OpenAI-compatible API with `response_format`; temperature 0 is recommended. The page shows no example of that request. |
| <https://docs.ollama.com/context-length> | Default context length by video memory (4k below 24 GiB); the settings slider; `OLLAMA_CONTEXT_LENGTH`; `ollama ps`. The page does not say what happens to a prompt that is longer than the context. |
| <https://lmstudio.ai/docs/developer/openai-compat> and <https://lmstudio.ai/docs/developer/openai-compat/structured-output> | `GET /v1/models`, `POST /v1/chat/completions`; examples on port 1234; `response_format` with `json_schema`. `json_object` and the need for a key are not stated. |
| <https://platform.claude.com/docs/en/api/overview> and <https://platform.claude.com/docs/en/api/versioning> | Headers `Authorization: Bearer` (or `x-api-key`), `anthropic-version`, `content-type`; version `2026-10-21` removes `temperature`, `top_p` and `top_k`; response header `request-id`. |
| <https://platform.claude.com/docs/en/api/messages/create> | Body fields `model`, `max_tokens`, `messages`, `system`, `output_config` with `format` and `effort`; response fields `content`, `model`, `stop_reason`, `usage`. |
| <https://platform.claude.com/docs/en/build-with-claude/structured-outputs> | `output_config.format` with `type: json_schema` is generally available without a beta header; unsupported schema keywords give a 400 error; `stop_reason` `refusal` and `max_tokens` can leave the reply outside the schema. |
| <https://platform.claude.com/docs/en/api/errors> and <https://platform.claude.com/docs/en/api/handling-stop-reasons> | Error types and status codes 400, 401, 402, 403, 404, 413, 429, 500, 504 and 529; the error body; the seven `stop_reason` values. |
| <https://platform.claude.com/docs/en/api/models/list> | `GET /v1/models`, `limit` up to 1000, response fields `data[].id` and `has_more`. |
| <https://code.claude.com/docs/en/headless> and <https://code.claude.com/docs/en/cli-reference> | `claude -p` with piped input; `--output-format json` with `result`, cost and session metadata; `--json-schema` and `structured_output`; the flags `--model`, `--effort`, `--max-turns`, `--max-budget-usd`, `--tools`, `--disallowedTools`, `--safe-mode`, `--no-session-persistence`, `--permission-mode`, `--no-chrome`; `claude auth status`; exit code 0 on success. The field `modelUsage` of the result object is not described on these pages; the route reads it as the earlier reviewed adapter of this project does. |
| <https://code.claude.com/docs/en/env-vars> | `ANTHROPIC_API_KEY` replaces the subscription sign-in in print mode when it is set. |

Not verified: the behaviour of any real server, provider or CLI with these requests. The official pages were read; the services were not called.
