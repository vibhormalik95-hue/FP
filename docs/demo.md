# Guide to the language controls

> **Current guide.** To install the application first, see [install and run](install-and-run.md).

This guide shows how to use each language control in the page, from the request to Undo, and how to check a run.
It also says which kind of evidence each provider gives.

## What the page shows

The page has three views.

- **Original study (A to E)** and **Compare A to E** hold the five conditions of the original proposal. See the [application reference](app.md#the-original-study-a-to-e).
- **Language controls** holds the controls of this guide. It opens first when a bundled scenario is served.

In **Language controls** a model can propose a change. The application checks the proposal. You review it. Nothing changes until you approve, and you can undo each change.
A control is a named set of existing items with one action. It is not a new video and not a new category in the dataset.

The bundled scenarios use invented items and a labelled diagnostic scorer. A run on them shows that a control works as described. It does not measure accuracy, recommendation quality or satisfaction.

## Start a scenario

Run one server at a time from the source folder. Stop it with Ctrl+C.

```
python scripts/quickstart.py rehearse --scenario tags
python scripts/quickstart.py start --scenario tags
python scripts/run_demo.py --scenario tags --provider manual
```

- `rehearse` uses replies that a person wrote by hand for the bundled requests. No model is used.
- `start` uses your [model route](model-routes.md).
- `--provider manual` serves the page without a model. Only the manual method is offered.

| Scenario | Items | Existing category for the manual method | Bundled requests |
| --- | --- | --- | --- |
| `tags` | Ten invented items with categories, subcategories and tags. Item 61010 has no category and no tag. | `Cooking` | A request matched to categories and tags, with six further examples; a request matched to descriptions; a brief for a fictional item. |
| `category` | Eight invented items. | `K1` | An objective for a new category. |
| `hunger` | Eight invented items. | `Repair` | An indirect request matched to descriptions. |

Open <http://127.0.0.1:8765>. Read the status line at the top of the page before you describe a run. It names the data, the scorer and the provider.

## The stages and the review

The panel on the left shows the line **One control, six stages**: Request, Interpretation, Evidence, Preview, Apply, Undo. Each stage shows its state: `done`, `now`, `not yet` or `not used`.

After a request, the result appears in the main area, above the feed. A proposed change carries the flag **PREVIEW · NOTHING IS APPLIED YET** and three blocks.

| Block | Content |
| --- | --- |
| **Model output (not verified)** | What the model returned: the direction and strength, the part of your request that names the subject, the relation that the model states, and the names or quotations that it chose. The raw reply is in a folded element. The model can be wrong. |
| **Application checks** | Mechanical checks with `Passed` or `Failed`, the items that each chosen name selects, and the provider and model as the route declares them. A passed check shows that names, IDs and quotations exist in the supplied data. It does not show that the meaning is right. |
| **Your decision** | What will change if you approve, and the two buttons **Approve this exact item set and apply** and **Discard this review and apply nothing**. |

For the method with categories and tags, the server sends its list of checks. For the other methods the server makes its checks before it answers, and the page repeats the checks that the answer lets it confirm.

Below the blocks are two more parts.

- **Evidence for every item in the scope.** One row for each item: its description, its categories and tags, and why it is selected or not selected.
- **Preview: the first ten items now and after approval.** The items that leave or move are marked in words.

The feed below stays as it is until you approve. A review expires five minutes after it appears.
After Apply, the main area shows **What changed**: the new controls, the items, the time, and how to undo.

Two settings apply to every method.

- **Evidence scope.** The first 6 or the first 10 items of the starting list. The application uses no other item.
- **How to combine with the applied controls.** "Add this control (a control with the same name is replaced)" or "Replace every applied control".

## Existing category (manual, no model)

This method is the reference for the language controls. No model is called.

1. Method: **Existing category (manual, no model)**.
2. Existing category: choose one from the list, for example `Cooking` in the scenario `tags`.
3. Action: **Show more (rank higher)**, **Show less (rank lower, still in the feed)** or **Remove from the feed**. For more or less, choose the strength: 0.10, 0.25 or 0.40.
4. Press **Show the proposed change**.
5. Read the review. The table says for each item whether its category is the chosen one.
6. Press **Approve this exact item set and apply**.

Example in the scenario `tags`: `Cooking` with "Remove from the feed" selects the items 61001, 61002 and 61009. The feed goes from 10 eligible items to 7. Undo restores 10.

## My request, matched to existing categories and tags (model)

Use this method when the request should become a control over category and tag names that already exist. The request does not need to contain a name.

1. Method: **My request, matched to existing categories and tags (model)**.
2. The panel lists **Existing categories and tags in the scope**, with the number of items for each name. This list needs no model call.
3. Write your request, or press **Insert the bundled scenario request**. The list **More bundled examples** holds further requests.
4. Press **Interpret my request**. The application makes one model call.
5. Read the three blocks and the table. The table says through which category or tag each item is selected. For an item that is not selected it says "none of its categories or tags was chosen".
6. Press **Approve this exact item set and apply**.

What the model receives: your request, and the category and tag names of the scope with the number of items for each name. It does not receive the item descriptions.

What the application does with the reply:

- It checks that every returned name exists with exactly the supplied value.
- It checks that the quoted part of the request is an exact part of the request.
- It checks that no control is too broad.
- It then selects the items that carry the chosen names. The model does not select items.

Example in the scenario `tags`, with the hand-written replies of `rehearse`: the request "I'm not hungry, remove all the stuff that makes me hungry." gives the control `Exclude: Cooking + street food`. The category `Cooking` selects 61001, 61002 and 61009. The tag `street food` selects 61003. The feed goes from 10 eligible items to 6. Undo restores 10.
Item 61004 mentions a sandwich in its description only. It has no food category and no food tag, so this method does not select it. A real model can choose other names.

Limits that the application enforces:

- One control cannot select more than half of the items in the scope. The exclusions of one request together cannot remove more than half.
- A request with a negated command, for example "Do not hide ...", gets a request for clarification before any model call. The check is a conservative English wording pattern.

## My request, matched to item descriptions (model)

Use this method when the answer is in what the descriptions say, not in a category or tag.

1. Method: **My request, matched to item descriptions (model)**.
2. Write your request, or press **Insert the bundled scenario request**.
3. Name of this control: keep the name or write your own.
4. Press **Interpret my request**. The application makes two model calls at most. Call 1 reads the direction and strength from the request. Call 2 selects items and cites a quotation from each one.
5. Read the review. The block "Application checks" shows the complete text around each quotation. Check it for a negation or a contrary meaning.
6. Press **Approve this exact item set and apply**.

What the model receives: your request and the item data of the scope: descriptions, categories and tags.
What the application checks: every selected item is in the scope and has its own quotation, and every quotation is an exact part of the text of its own item. Any other reply is rejected and nothing is proposed.

Examples with the hand-written replies of `rehearse`:

- Scenario `tags`: "Remove the videos where someone is eating." selects item 61004 with the quotation "between bites of a sandwich". The category and tag method cannot find this item, because no label says it.
- Scenario `hunger`: "I'm not hungry, remove all the stuff that makes me hungry." selects the items 81001, 81003 and 81006 from their descriptions. The feed goes from 8 eligible items to 5. Undo restores 8.

The option **I will state the target meaning and the action myself.** lets you write the target and choose the action. The model then only proposes related items. The review says that you supplied the interpretation.

## A new category from my description (model, in stages)

Use this method when no existing category or tag covers what you want.

1. Method: **A new category from my description (model, in stages)**.
2. Describe the category, or press **Insert the bundled scenario request** in the scenario `category`.
3. Action: choose the direction and strength yourself, for example **Remove from the feed**.
4. Press **Propose a definition for review**. Call 1 proposes a label, a definition and quotations.
5. If the model names competing meanings, the review is titled **Resolve competing category meanings**. Select "I resolve the competing meanings by choosing this exact, unchanged primary definition for review." and press **Continue to definition review**, or press **Cancel category clarification**. This choice makes no model call and approves nothing.
6. In **Stage 1: review the whole definition**, read the definition, each quotation and the complete field that it comes from. Tick "I reviewed whether the source evidence supports the entire definition." Press **Approve definition and classify supplied items**. You have five minutes for this decision.
7. Call 2 classifies every item in the scope. Call 3 assesses the evidence without seeing the classifications. The two calls that follow your approval can take longer than five minutes.
8. Read the table. It has one row for each item, with the classification, the separate evidence assessment and the result. Where the two calls disagree, the item stays unknown and is not selected.
9. Press **Approve this exact item set and apply**.

The two calls can use the same model, and both can be wrong. A quotation that exists is not proof that the definition is right. Reject a definition that states a property that the descriptions do not state.

Example in the scenario `category`, with the hand-written replies of `rehearse`: the items 41001, 41002 and 41003 become members of a category about a repaired object that is kept. Item 41005 is withheld as unknown, because the two calls disagree. The feed goes from 8 eligible items to 5. Undo restores 8.

## A mixed request

One request can hold several preferences. Use the method with categories and tags.

Example in the scenario `tags`: "Show me more repair videos, and remove anything about food." With the hand-written replies, the review shows two controls from one model call. `Increase: Repair` covers the items 61004 and 61005. `Exclude: Cooking + street food` covers the items 61001, 61002, 61003 and 61009.
The table has one group of rows for each control. An item in several controls shows one net result. Removal takes priority over a rank change. One approval applies both controls together, and one Undo reverses both.

A name cannot be in two controls with different directions. The application then asks for clarification.

## Requests that change nothing

Some requests must not change the feed. The result then carries the flag **NO CHANGE PROPOSED · NOTHING WAS APPLIED**. The block "Your decision" says what you can do next.

| Result | Heading in the page | Bundled example in the scenario `tags` |
| --- | --- | --- |
| The request has several possible meanings. | The request needs clarification | "I have had enough of the heavy stuff." |
| The request negates a command. The application stops it with its own check. No model is called. | The request needs clarification | "Do not hide the cooking videos." |
| The controls cannot express the request, for example a quota, a time or an exception. | The controls cannot express this request | "Show me at most two cooking videos per day." |
| No existing name or description matches. | No existing category or tag matches the request | "Show me fewer videos about astronomy." |
| A call failed, or the reply was rejected. | The step stopped with an error | none |

When the model names alternatives, each one has the button **Use this as my new request**. It puts the alternative into the request box. Nothing is sent until you submit it.
The message of an error comes from the application or from the model provider. See the [failure table](model-routes.md#if-something-fails).

A real model can answer one of these examples with a proposal. Then review it as any other proposal. You are not obliged to approve it.

## Undo and removal

- **Undo the last change (review first)** shows the review "Undo: restore the state before the last approved change". Approve it to restore the earlier feed. The application keeps up to ten earlier states.
- **Remove every applied control (review first)** shows the review "Remove every applied control". Approve it to remove them.
- **Reset this user** at the top of the page clears every control of the selected user.

The list **Applied controls** in the panel shows what is active. Applied controls last for one browser session.

## The fictional item

Below the panel, under **Fictional item drafts (separate feed)**, open "Fictional item drafts: metadata that a model writes, in a separate feed".

1. Write a brief, or press **Insert the example brief**.
2. Tick "I want fictional metadata, not a real video or observed item."
3. Press **Generate fictional metadata draft**. The application makes one model call. The model receives the brief and the drafting instruction. It does not receive the catalogue.
4. Read the draft under "Review fictional metadata before admission". Press **Approve fictional draft and admit to synthetic feed**.
5. Remove the item with **Remove synthetic item**.

A fictional item never enters the dataset, the scope of a language control, the conditions A to E or the trained scorer. Every item of the separate feed has score 0. See [fictional item drafts](synthetic-item-drafts.md).

## Which evidence each provider gives

| Provider | Start with | What answers | Status line | What a run shows |
| --- | --- | --- | --- | --- |
| `manual` | `run_demo.py --provider manual` | Nobody. Only the manual method is offered. | `No model provider · manual controls only` | The manual control. |
| `scripted` | `quickstart.py rehearse` | Replies that a person wrote for the bundled requests. | `AUTHORED REPLIES · NO MODEL` | The screens, Apply and Undo. It is not model behaviour. |
| `route` | `quickstart.py start` | The model of your route file. | `PROVIDER · backend · model` | Output of that model with those settings. The model name is the name that you requested; each call records the name that the reply reports. |
| `route` with the relay, or `relay` | `quickstart.py start`, or `run_demo.py --provider relay` | A model that a person carries each request to. | `PROVIDER · operator-relay-file-queue · declared model` | Real model output with a person in the transport. The model name is a declaration. The relay cannot confirm it. |
| `personal-cli` | `run_demo.py --provider personal-cli` | The signed-in Claude Code CLI, through a reviewed configuration. | `PROVIDER · claude-code-personal-cli · model` | An automatic call under a reviewed configuration. |

State the provider, the reviewer and the scenario each time that you show a run. A run with a stand-in server or a stand-in program is a test of the route. It is not model evidence.

## The relay provider

Use the relay when a model has no programmatic connection to the application. The application writes each request to a folder. You carry it to the model and bring the reply back unchanged.

Choose "By hand" in `python scripts/quickstart.py setup`, then run `python scripts/quickstart.py start --scenario tags`. The terminal prints the relay folder and these commands. For request `N`, in a second terminal:

```
python scripts/relay_tools.py show RELAY-FOLDER N request-N.txt
python scripts/relay_tools.py check RELAY-FOLDER N answer-N.json
python scripts/relay_tools.py deliver RELAY-FOLDER N answer-N.json
```

1. `show` writes the exact text for the model to `request-N.txt`.
2. Give the whole text to the model in a new conversation. Save the reply as `answer-N.json`. The reply must be one JSON object with nothing around it: no Markdown fence and no sentence before or after it.
3. `check` says whether the application would accept the file. Nothing is delivered.
4. `deliver` makes the same checks and then gives the file to the application. It refuses a file that the application would reject. A refusal does not use the call: copy the reply of the model again.

If the reply of the model is itself not a valid answer, deliver it with `--force`. The application then rejects it, and that is the true result of the call.
The application decodes a reply strictly and checks it against the schema of the request. It does not repair a reply and it does not ask again.

Calls for one complete flow:

- a request matched to categories and tags: one;
- a request matched to descriptions: two;
- a new category: three;
- a fictional item: one.

The launcher can also start the relay without a route file:

```
python scripts/run_demo.py --scenario category --provider relay --relay-dir runs/relay-01 --declared-model "name of the model" --transport-note "copied by hand into a chat application" --relay-timeout 1800
```

`python scripts/quickstart.py live --scenario category --operator manual` starts the same relay for the scenario `category` or `hunger` and prints the commands. With `--operator cli`, the script `scripts/relay_claude_cli.py` answers each request with the Claude Code CLI on your computer. It makes one CLI call for each request. It makes no second call and it changes no reply. That script was tested with a stand-in program only. The route "A command-line program on this computer" of `quickstart.py setup` is the direct way to use a CLI.

## The signed-in Claude Code CLI

`--provider personal-cli` is a separate, reviewed connection to the Claude Code CLI on Windows. It serves the scenarios `category` and `hunger`.

```
python scripts/run_demo.py --provider personal-cli --reviewed-config my-config.json --report runs/category-report.json
```

- `tools/hosted_validation_current/driver.py` checks a reviewed configuration file before anything runs. The file holds six explicit statements by the operator, the hash of every application source file, the pinned scenario inputs, the path and hash of the executable, and the call allowance.
- The page asks for the operator token of the configuration. The server uses port 8765 on 127.0.0.1 only.
- A configuration file is marked as used and is refused a second time. The first request must equal the pinned scenario request exactly.
- The report holds the facts of the provider: the exact inputs, the call receipts and the number of attempts.
- The configuration templates in `tools/hosted_validation_current/` are incomplete on purpose, and every statement in them is false. After a change to a prompt or to application source, run `python tools/hosted_validation_current/refresh_pins.py NEW-PROFILE-ID "what changed"` and review the result.

The operator must confirm four conditions that the code cannot confirm:

- the program is the unmodified CLI of the reviewed version;
- it is signed in to the operator's own account;
- the operator accepts the usage;
- the data may go to the provider.

This command was not run for this guide. Its tests use a stand-in for the process runner.

## Check a run in a real browser

The script `tests/browser/demo_flows.cjs` drives the page in a real browser and compares the page with the state of the server.

```
node tests/browser/demo_flows.cjs --base http://127.0.0.1:8765 --scenario tags --out runs/browser-tags-01
```

It needs Node.js, the `playwright` package and its Chromium browser. See [install and run](install-and-run.md#9-final-verification-sequence).

| Flow | What it does | Scenario |
| --- | --- | --- |
| `manual` | An existing category chosen by hand. No model call. | all |
| `vocabulary` | The bundled request matched to categories and tags: three blocks, preview, Apply, Undo. | `tags` |
| `mixed` | One request with several preferences: one review, one Apply, Undo. | `tags` |
| `outcomes` | The four requests that must change nothing. | `tags` |
| `description` | The bundled request matched to descriptions. | `tags` |
| `fictional` | A fictional item: draft, review, admit, remove. | `tags` |
| `category` | A new category in stages. | `category` |
| `indirect` | An indirect request matched to descriptions. | `hunger` |

Without `--flows`, the script runs every flow of the scenario. `--flows manual,vocabulary` runs a part.

For each flow the script checks three things against the server's own state:

- a preview changes nothing;
- Apply has exactly the approved effect;
- the two-step Undo restores the identical feed.

For `outcomes` it records the result that it observed beside the expected result. It asserts only that nothing changed. If a model proposes a change there, the script discards the proposal and records that.

**Review modes.**

- `--review auto` (the default): the script ticks the review boxes itself. Use it only with the hand-written replies of `rehearse`. With a model as provider, the script stops with a failed check.
- `--review wait --reviewer "your name"`: the script stops at each review. It writes `gate-NAME.json` and a screenshot into the `--out` folder. It continues only when you write the word `APPROVE` into `decision-NAME.txt` in that folder. Any other text is recorded as a decline, and the flow stops with nothing applied.

**The receipt.** `browser-receipt.json` in the `--out` folder lists the checks of the script and the review decisions with the name of the reviewer. It also lists every provider call, the text of the status line and the source fingerprint of the server. `python scripts/run_demo.py --fingerprint` prints the fingerprint of your files.

**Exit codes.** 0: every flow completed. 2: a flow stopped early, for example after a declined review or a rejected reply. 1: a check failed.

With `--video` the script records the page to `video/SCENARIO.webm` in the `--out` folder. For the `personal-cli` provider, set the variable `FEEDCTRL_OPERATOR_TOKEN`.

## Other checks

```
python -m pytest -q -p no:cacheprovider
python tools/hosted_validation_current/run_guarded.py .
node --test "web/tests/*.mjs"
python scripts/check_personal_ui_index.py
```

The Node tests need `npm ci` in `web/` first. These are checks of the program with hand-written replies and stand-ins. They are not model evidence.
`npm run build` in `web/` reproduces the built interface in `web/dist` byte for byte. See [the built interface](source-verification.md).
