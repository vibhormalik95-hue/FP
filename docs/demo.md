# Demonstration guide

This guide shows how to run the three controls on your own computer and how to check them.
It also says which kind of evidence each provider gives.

## What you see

The page has three ways to change a feed. Each one ends in the same deterministic filter.

1. **Manual category.** You choose an existing category and an action. No model is used.
2. **New category from natural language.** You describe what you want. A model proposes a definition. You review it. The model then classifies every supplied item, and a separate model call assesses the evidence without seeing those decisions. You review every item. Only then can you apply the result.
3. **Indirect request.** You write a request that names no category. A model interprets the action and proposes existing items, with a quotation from each item.

For every control the order is the same: proposal, review, Apply, and a two-step Undo. A proposal never changes the feed.

The two bundled scenarios use eight invented item descriptions each and a labelled diagnostic scorer. They show that the controls work. They do not measure recommendation quality.

## Install

Python 3.11 or newer. Node 22.12 or newer is needed only to rebuild the interface or to run the browser check.

```
python -m venv .venv
.venv\Scripts\Activate.ps1          # Windows PowerShell
source .venv/bin/activate           # Linux or macOS
python -m pip install -e ".[test]"
```

The built interface is in `web/dist`. PyTorch is not needed for the demonstration. Add it with `python -m pip install -e ".[test,recommender]"` when you want the trained recommender and the original experiments.

## Quick start

One command for each step. The commands are the same on Windows, Linux and macOS. Run them from the repository root, with the virtual environment active.

```
python scripts/quickstart.py check
python scripts/quickstart.py rehearse --scenario category
python scripts/quickstart.py live --scenario category --operator cli
python scripts/quickstart.py live --scenario hunger --operator cli
```

- `check` prints the source fingerprint and the installed versions.
- `rehearse` serves the app with hand-written replies. No model is used. Do each flow once before you use a model.
- `live --operator cli` serves the app with the relay provider and answers each request with the Claude Code CLI on your computer. See "An automatic operator" below.
- `live --operator manual` serves the app with the relay provider and prints the commands for a manual relay.

The scenario `category` holds the manual control and the new category. The scenario `hunger` holds the manual control and the indirect request. Open <http://127.0.0.1:8765>, choose **Reviewed topic feed**, then open **Experimental semantic groups**. Stop the server with Ctrl+C.

## Start a scenario

The quick start runs the launcher that this section describes. Run one server at a time from the repository root. Stop it with Ctrl+C.

```
python scripts/run_demo.py --scenario category --provider manual
python scripts/run_demo.py --scenario category --provider scripted
python scripts/run_demo.py --scenario hunger --provider scripted
```

Open <http://127.0.0.1:8765>. Choose **Reviewed topic feed**, then open **Experimental semantic groups**.

The status strip at the top of the page names the provider. Read it before you describe a run.

| Provider | What answers | Status strip | What a run shows |
| --- | --- | --- | --- |
| `manual` | Nobody. Only the manual control is offered. | No model provider · manual controls only | The manual control. |
| `scripted` | Hand-written replies for the two bundled requests. | AUTHORED REPLIES · NO MODEL | The screens, Apply and Undo. It is not model behaviour. |
| `relay` | A model that an operator carries each request to. | PROVIDER · operator-relay-file-queue · the declared model | Real model output, with an operator in the transport. The model name is the operator's declaration. |
| `personal-cli` | The signed-in Claude Code CLI on Windows. | PROVIDER · claude-code-personal-cli · the model | An automatic call. The CLI reports the model it used. |

## The three flows in the page

**Manual category.** Method: *Manual: exact original category baseline*. Type an existing category (`K1` in the category scenario, `Repair` in the hunger scenario). Manual action: *Exclude*. Press *Review semantic proposal*. Read the table. Press *Approve this exact item set and apply*. To undo, press *Review semantic undo*, then approve.

**New category.** Method: *Configured model: review definition, then classify all supplied items*. Press *Insert the bundled scenario request*, or write your own objective. Manual action: *Exclude*. Press *Propose a definition for review*.

- If the model gives competing meanings, the page lists them. Choose the unchanged primary meaning or cancel. This choice approves nothing.
- Read the definition, the quotations and the complete field text. Tick the review box and press *Approve definition and classify supplied items*. You have five minutes to decide. The model calls that follow may take longer.
- The table in the main area lists every supplied item: its description, the classification, the separate evidence assessment and the result. A disagreement between the two model calls is withheld as unknown. Read each row.
- Press *Approve this exact item set and apply*. You have five minutes from the moment the table appears.
- Press *Review semantic undo*, then approve. The feed returns to its starting state.

**Indirect request.** Method: *Operator-configured model provider: semantic proposal*. Press *Insert the bundled scenario request*. Press *Review semantic proposal*. Review, apply and undo as above.

## The relay provider

Use the relay when a model has no programmatic connection to the app. Each request is written to a folder. You carry it to the model and bring the reply back unchanged.

```
python scripts/run_demo.py --scenario category --provider relay --relay-dir runs/relay-01 \
    --declared-model "name of the model you will use" \
    --transport-note "how the request reaches the model" --relay-timeout 1800
```

For request `N`, in a second terminal:

```
python scripts/relay_tools.py show runs/relay-01 N runs/request-N.txt
```

Give the whole text of `runs/request-N.txt` to the model in a new conversation. Save the reply as `runs/answer-N.json`. The reply must be one JSON object with nothing around it: no Markdown fence and no sentence before or after. Then:

```
python scripts/relay_tools.py check runs/relay-01 N runs/answer-N.json
python scripts/relay_tools.py deliver runs/relay-01 N runs/answer-N.json
```

`check` says whether the app would accept the file. `deliver` makes the same checks and refuses a file that the app would reject. A refusal does not spend the call: copy the model's reply again, without the text around the JSON object. If the model's reply itself is not a valid answer, deliver it with `--force`; the app then rejects it, and that is the true result of the call.

The app decodes the reply strictly and checks it against the schema. It does not repair a reply and it does not ask again. A new category needs three requests. An indirect request needs two.

### An automatic operator for the Claude Code CLI

`scripts/relay_claude_cli.py` does the work of the operator by program. For each request it runs the Claude Code CLI on your computer one time in print mode, with the request text on standard input, and delivers the reply unchanged.

```
python scripts/relay_claude_cli.py runs/relay-01 --calls 3
```

- It makes one CLI call for each request and never a second one. It never edits a reply.
- If a call fails, or the reply is not an acceptable answer, it stops and leaves the request open. You can then answer that request by hand with `relay_tools.py`.
- It checks that the CLI reports only the requested model (default `claude-fable-5-2`). Use `--model`, `--effort` and `--claude PATH` to change the defaults.
- It writes `cli-call-000N.json` for each call: times, exit code, flags, hashes, the reported token usage and model names. It stores no request text there.

This operator is not the reviewed connection of the next section. It has no reviewed configuration, no check of the executable and no process containment. You are responsible for the CLI, for the account that it is signed in to, and for the usage. It was tested with a stand-in program for the CLI. It was not run with the real CLI before this page was written.

State the transport honestly when you show a relay run. The page shows the declared model name; the relay cannot confirm it.

## The signed-in Claude Code CLI

`--provider personal-cli` serves the app that `tools/hosted_validation_current/driver.py` builds. The driver checks a reviewed configuration file before anything runs: six explicit assertions by the operator, the hash of every application source file, the pinned scenario inputs, the executable path and hash, and the call allowance (three for a new category, two for an indirect request). Each call may return at most 16,384 output tokens and may take at most 300 s.

```
python scripts/run_demo.py --provider personal-cli --reviewed-config my-config.json --report runs/category-report.json
```

- The page asks for the operator token from the configuration. Every API call needs it.
- The server uses port 8765 on 127.0.0.1 only.
- A configuration file is marked as used and is refused a second time. A busy port or a wrong `--scenario` is reported before the file is marked.
- The first request must equal the pinned scenario request exactly. Use *Insert the bundled scenario request*.
- The report holds the provider facts: the exact inputs, the call receipts and the number of attempts. Reviews, Apply and Undo are recorded by the browser check, not by this report.

Conditions that the operator must check, and that this code cannot check for you: the binary is the unmodified CLI of the reviewed version; it is signed in to your own account; you accept the usage it causes; the data may be sent to the provider; and the Windows process runner has been tested on your computer. The configuration templates in `tools/hosted_validation_current/` are incomplete on purpose and every assertion in them is false.

After a change to a prompt or to application source, run `python tools/hosted_validation_current/refresh_pins.py NEW-PROFILE-ID "what changed"` and review the result before you fill in a configuration.

## Check a run in a real browser

The script drives the page and compares it with the server's own state.

```
npm install --no-save playwright
npx playwright install chromium
node tests/browser/demo_flows.cjs --base http://127.0.0.1:8765 --scenario category \
    --flows manual,category --out runs/browser-01
node tests/browser/demo_flows.cjs --base http://127.0.0.1:8765 --scenario hunger \
    --flows manual,indirect --out runs/browser-02
```

It checks that a preview leaves the applied feed unchanged, that Apply removes exactly the approved items, and that Undo restores the identical feed. It writes screenshots and `browser-receipt.json`.

The receipt records the source fingerprint of the server that it used. `python scripts/run_demo.py --fingerprint` prints the fingerprint of your files. The function is designed to give the same value on Windows, Linux and macOS for the same files, so that a receipt can be matched to a source tree without Git. It was tested on Linux only.

With a model connected, add `--review wait --reviewer "your name"`. The script stops at each review. It continues only when you write `APPROVE` into the decision file that it names. Any other text is recorded as a decline. Set `FEEDCTRL_OPERATOR_TOKEN` when the page asks for a token.

Exit code 0 means every flow completed. Exit code 2 means a flow stopped early, for example after a declined review or a rejected reply. Exit code 1 means a check failed.

## Other checks

```
python -m pytest
python tools/hosted_validation_current/run_guarded.py .
cd web && npm ci && cd ..
node --test web/tests/*.mjs
```

These are software checks with authored replies. They are not model evidence. A rebuild with `npm run build` in `web/` reproduces the tracked interface files byte for byte.
