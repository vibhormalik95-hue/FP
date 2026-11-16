# Install and run

> **Current guide.** It replaces the install sections of earlier pages.

This page gives the setup commands for Windows PowerShell and macOS zsh. The recorded checks below ran on Linux at revision `ff92666`, with authored replies or stand-ins. Native Windows and macOS verification of these setup commands remains open. The separate [Windows fictional-item result](fictional-lifecycle-2026-11-15.json) used a task-local transport, not this quickstart workflow.

For the separately configured Windows personal CLI binding, follow its [setup and qualification guide](../diagnostic/README.md). It needs an explicit caller and reviewed local context; the quickstart commands below do not activate it. Its [combined fixture result](evidence/2026-11-15-windows-combined/README.md) used direct application calls.

## What you need

- Python 3.11 or newer.
- A web browser.
- A model, through one of four routes (step 5). You can do steps 1 to 4 without a model.
- Node.js 22.12 or newer, only for the interface tests and the browser check of step 9.

## 1. Open a terminal in the source folder

The source folder is the folder that holds `pyproject.toml`.

## 2. Create the environment and install

| System | Commands |
| --- | --- |
| Windows PowerShell | `python -m venv .venv`<br>`.\.venv\Scripts\Activate.ps1`<br>`python -m pip install -e ".[test]"` |
| macOS zsh | `python3 -m venv .venv`<br>`source .venv/bin/activate`<br>`python -m pip install -e ".[test]"` |

After the activation, `python` is the Python of the environment on both systems. The commands below are then the same on both.

- If PowerShell refuses to run `Activate.ps1`, do not change a policy. Write `.\.venv\Scripts\python.exe` in place of `python` in every command.
- If `python` is not found on Windows, try `py -3` for the first command.
- PyTorch is not necessary for the application. It is necessary only for the trained recommender and the original experiments: `python -m pip install -e ".[test,recommender]"`.

## 3. Check the installation

```
python scripts/quickstart.py check
```

The command prints the source fingerprint, the Python version and the versions of the libraries. The last line must be `built interface: present`.
The source fingerprint is one SHA-256 value over the files that decide what the application does. A run record holds the same value, so you can match a record to your files.

## 4. Try the page without a model

```
python scripts/quickstart.py manual --scenario tags
```

Open <http://127.0.0.1:8765>. Without a model only the manual category control works; the model methods are marked "(needs a model provider)". There is no mode with hand-written replies.
To try the language-control screens with no key and no cost, use Feed Control Studio instead: run `run-studio.cmd` and choose the **Mock** provider (see the [Studio guide](studio-guide.md)).
Press Ctrl+C in the terminal to stop the server.

The original conditions A to E need category IDs of the form `category_N`. To try them, serve the built-in fixture:

```
python scripts/quickstart.py manual --scenario conditions
```

The page then opens on "Original study (A to E)". This scenario uses no model and has no language controls. On the other scenarios the instruction and the profile of C, D and E are disabled, and the page says why.

## 5. Choose a route to a model

```
python scripts/quickstart.py setup
```

The command asks how the application will reach a model. It writes the answer to `model-route.json`. That file never holds an API key.

| Choice | Route | What you need |
| --- | --- | --- |
| 1 | A command-line program on this computer | The Claude Code CLI, signed in to your own account, or another program that reads a prompt and prints a reply. See [a command-line program](model-routes.md#a-command-line-program-on-your-computer). |
| 2 | A hosted provider with your own API key | An API key for an OpenAI-compatible API or for the Anthropic API. The provider bills each call. See [a hosted provider](model-routes.md#a-hosted-provider-with-your-own-api-key). |
| 3 | A model server on this computer | Ollama or LM Studio with a model that can follow a JSON schema. No key. The data stays on your computer. See [a model server](model-routes.md#a-model-server-on-your-computer). |
| 4 | By hand | Any chat application. You carry each request to it and bring the reply back. See [by hand](model-routes.md#by-hand). |

[Model routes](model-routes.md) gives the settings for each route, the same setup as one command without questions, and what a model must be able to do.

## 6. Confirm the route

```
python scripts/quickstart.py doctor
```

Each line starts with `OK` or `FAILED`. A failed line is followed by `What to do:`.
If the route needs a key and its variable is not set, the command asks for the key with a hidden prompt. It keeps the key in memory for that run only.
The last step sends one very small request to the model. It can use a few tokens. Add `--no-test-call` to leave that step out.

Example with a model server on this computer:

```
OK      configuration: Route: openai-compatible; Endpoint: http://127.0.0.1:11434/v1/chat/completions (preset ollama); Model: llama3.1:8b
OK      endpoint: The endpoint answered and lists the model "llama3.1:8b" (1 models listed).
The next step sends one very small request to the model. It can use a few tokens.
OK      test call: The model returned the requested JSON object in 2.1 s. Model reported by the reply: llama3.1:8b (accepted as the requested model by the rule "equal").

Result: the route works.
```

The lines above show the form of the output. They were produced with a stand-in server; the address, the model name and the time are examples.

## 7. Start the application

```
python scripts/quickstart.py start --scenario tags
```

Open <http://127.0.0.1:8765>. The page opens on **Language controls**. The status line names the route and the model: `PROVIDER · backend · model`.

| Scenario | Content |
| --- | --- |
| `tags` (default) | Ten invented items with categories and tags. All methods, a mixed request, requests that change nothing, and a fictional item. |
| `category` | Eight invented items. The manual control and a new category from natural language. |
| `hunger` | Eight invented items. The manual control and an indirect request matched to item descriptions. |

`start` does not serve the scenario `conditions`, because that scenario has no language controls. Use `manual --scenario conditions` for it.

- The terminal prints one line for each model call.
- The exact request and the raw reply of each call go to a new folder `runs/route-SCENARIO-DATE-TIME/`. Add `--record-dir none` if you do not want these files.
- Add `--port 8770` if port 8765 is in use.
- With the route "by hand", the terminal prints the relay commands. See [the relay provider](demo.md#the-relay-provider).

## 8. Use the page

Follow the [guide to the language controls](demo.md). In short:

1. Choose a **Method**.
2. Write a request, or press **Insert the bundled scenario request**.
3. Press **Interpret my request** (for the manual method: **Show the proposed change**).
4. Read the three blocks of the review and the table of items.
5. Press **Approve this exact item set and apply**.
6. Press **Undo the last change (review first)**, then press **Approve the undo**.

You can also run the bundled requests through your route without the browser:

```
python scripts/quickstart.py try --scenario tags
```

See [route trial](route-trial.md).

## 9. Final verification sequence

Run these checks from the source folder. They use no model.

1. **The files.** `python scripts/quickstart.py check` prints the checkout's source fingerprint. The recorded value for `ff92666` was `22ba794e2091685fa879dcc43b68233dae1963fa4231c38dd73a36f13639068a`. Commit `836cdff6` changed an application file, so this earlier value must not be used to identify that later source.
2. **The Python tests.** `python -m pytest -q -p no:cacheprovider`. Recorded on `ff92666`: 1786 passed and 1 skipped with PyTorch; 1782 passed and 2 skipped in a fresh environment without PyTorch.
3. **The guarded driver checks.** `python scripts/run_guarded_current_contract.py`. The last line must start with `PASS`. The script runs the guarded checks two times: on the frozen profile of 11 November 2026 in `tools/hosted_validation_current/`, and on a temporary copy with the current-contract test inputs. On the frozen profile 16 of the 180 checks have a failure, because the prompts changed after that date. That is expected, and the script says so. No reviewed profile exists for the current source.
4. **The interface tests.** They need Node.js.

   ```
   cd web
   npm ci
   cd ..
   node --test "web/tests/*.mjs"
   ```

   Recorded on `ff92666`: 132 passed.
5. **The browser check.** It drives the page in a real browser and compares the page with the state of the server. Install the browser once:

   ```
   npm install --no-save playwright
   npx playwright install chromium
   ```

   Without a model, start the server of step 4 in one terminal. In a second terminal run the flows that need no model:

   ```
   node tests/browser/demo_flows.cjs --base http://127.0.0.1:8765 --scenario tags --flows manual,history --out runs/browser-tags-01
   ```

   The last lines must be `OUTCOME all flows completed` and the path of the receipt. `--out` must name a new or empty folder. For the scenario `conditions` (served with `manual --scenario conditions`) the script runs the flow `original`.
   Recorded on `ff92666` (with the rehearsal provider that has since been removed) on Linux: `tags` 222 checks, `category` 106, `hunger` 98, `conditions` 12; all passed, exit code 0 each.
   For the model flows, start the server with `start` and a model route, and add `--review wait --reviewer "your name"`. The script then stops at each review and waits for your decision. See [check a run in a real browser](demo.md#check-a-run-in-a-real-browser).

The two commands that install the browser were not run for this page: the workspace that produced it already had Playwright and Chromium.

These checks identify the files and test the behaviour of the program. They do not show how a model behaves.

## Stop

Press Ctrl+C in the terminal of the server. Controls and reviews last for one browser session only. A restart of the server clears them.

## Common problems

| What you see | What to do |
| --- | --- |
| `python` is not found | macOS: use `python3` for the first command. Windows: use `py -3`, or install Python from python.org and open a new terminal. |
| PowerShell refuses `Activate.ps1` | Write `.\.venv\Scripts\python.exe` in place of `python`. |
| A message that the address is already in use | Another program uses port 8765. Stop it, or add `--port 8770` and open that port. |
| `The built interface is missing` | Run `npm ci` and `npm run build` in `web/`. The built interface is part of the repository, so this message means that files are absent. |
| `Run "python scripts/quickstart.py setup" first.` | The route file `model-route.json` does not exist yet, or it has an error. Run `setup`. |
| A line that starts with `FAILED` in `doctor` | Read the line `What to do:` below it. The [failure table](model-routes.md#if-something-fails) lists every message. |
| The page shows "The call to the provider failed", "The application rejected the reply" or "The request failed" | Read the message in the block "Application checks". It comes from the application or from the model provider. Nothing was applied. |
| The model methods are marked "(needs a model provider)" | The server runs without a model (`manual`). Start it with `start` and a model route, or use Feed Control Studio (`run-studio.cmd`, **Mock** provider) to try the screens with no key. |
| The instruction and the profile of the conditions C, D and E are disabled | The scenario has named categories. Use `python scripts/quickstart.py manual --scenario conditions`. |
