# Guide to the language controls

> **Legacy guide (earlier demonstrator, 13–15 November).** This page describes the fixture scenarios and the SemanticPanel page started by `scripts/quickstart.py`, not the current application. The current application is the four-tab Lab (Choose a category, Say it your way, New category, New items; new-category scope 10–200 items of the current feed; editable definition; provider setup in the page), started by `run-app.cmd` (`scripts/run_app.py`, port 8765). Its guide is [docs/guide/PROFESSOR-GUIDE.md](guide/PROFESSOR-GUIDE.md).

This guide shows how to use each language control in the page, from the request to Undo, and how to check a run.
It also says which kind of evidence each provider gives.

## What the page shows

The page has three views.

- **Original study (A to E)** and **Compare A to E** hold the five conditions of the original proposal. See the [application reference](app.md#the-original-study-a-to-e).
- **Language controls** holds the controls of this guide. It opens first when a bundled scenario is served.

In **Language controls** a model can propose a change. The application checks the proposal. You review it. Nothing changes until you approve, and you can undo each change.
A control is a named set of existing items with one action. It is not a new video and not a new category in the dataset.

The bundled scenarios use invented items and a labelled diagnostic scorer. The status line says "deterministic diagnostic scorer (a fixed formula, not the trained recommender)". A run on these scenarios shows that a control works as described. It does not measure accuracy, recommendation quality or satisfaction.

## Start a scenario

Run one server at a time from the source folder. Stop it with Ctrl+C.

```
python scripts/quickstart.py start --scenario tags
python scripts/quickstart.py manual --scenario tags
python scripts/quickstart.py manual --scenario conditions
```

- `start` uses your [model route](model-routes.md).
- `manual` (the same as `python scripts/run_demo.py --provider manual`) serves the page without a model. Only the manual method works. The page lists the model methods as "(needs a model provider)" and names the commands that start a provider.
- There is no mode with hand-written replies. To try the language controls with no key and no cost, use the current four-tab Lab (`run-app.cmd` or `python scripts/run_app.py`, port 8765, default **Mock** provider; see the [guide for the supervisor](guide/PROFESSOR-GUIDE.md)). The mock provider matches words literally and is only for trying the screens.
- `manual --scenario conditions` serves the original conditions A to E on the built-in fixture, with no model. `python scripts/run_demo.py --scenario conditions` does the same. This scenario has no language controls.

| Scenario | Items | Existing category for the manual method | Bundled requests |
| --- | --- | --- | --- |
| `tags` | Ten invented items with categories, subcategories and tags. Item 61010 has no category and no tag. | `Cooking` | A request matched to categories and tags, with six further examples; a request matched to descriptions; a description of a fictional item. |
| `category` | Eight invented items. | `K1` | An objective for a new category. |
| `hunger` | Eight invented items. | `Repair` | An indirect request matched to descriptions. |
| `conditions` | The built-in fixture: 36 items, categories `category_0` to `category_5`, three users. No item descriptions. | none | none. The view "Language controls" is disabled, and the page says why. |

The rule parser of the conditions C, D and E reads category IDs of the form `category_N` only. On `tags`, `category` and `hunger` the categories have names. There, the instruction (panel 02) and the profile (panel 03) are disabled, and the page gives the reason and the command for the scenario `conditions`.

Open <http://127.0.0.1:8765>. Read the status line at the top of the page before you describe a run. It names the data, the scorer and the provider.

## The stages and the review

The panel **Change the feed with a reviewed request** shows the line **One control, six stages**: Request, Interpretation, Evidence, Preview, Apply, Undo. Each stage shows its state, for example `done`, `now`, `not yet`, `now: your decision`, `stopped; nothing applied` or `expired; nothing applied`. For the manual method, Interpretation shows `not used: no model`. The Undo stage shows `available` while an earlier state exists.

After a request, the result appears in the main area, above the feed. On a narrow screen it appears below the panel. The page moves the focus to the heading of the result. The link **Go to your decision** goes to the decision block.

A proposed change carries the flag **PREVIEW · NOTHING IS APPLIED YET** and the heading "Proposed change: NAME" (or "Proposed change: 2 controls"). Your request stands above three blocks.

| Block | Content |
| --- | --- |
| **Model output (not verified)** | What the model returned: the direction and strength, the part of your request that names the subject, the reason that the model gave, and the names or quotations that it chose. The raw reply is in a folded element. The model can be wrong. For the manual method, for Undo and for the removal of every control, it is **Your selection**. |
| **Application checks** | Mechanical checks with `Passed`, `Failed` or `Not confirmed on this page`, the items that each chosen name selects, the items of the control outside the evidence scope, and the provider line. The provider line names the provider and the model as the server settings name them. It says that the application did not verify which model answered. A passed check shows that names, IDs and quotations exist in the item data. It does not show that the meaning is right. |
| **Your decision** | What will change if you approve, the time limit "Approve before HH:MM:SS", and the two buttons **Approve this exact item set and apply** and **Discard this review and apply nothing**. |

The server sends its own list of checks for the method with categories and tags and for the method with item descriptions. The page shows it as "Checks of the reply". The page also repeats the checks that the reviewed record lets it confirm.

**Notes about the whole plan.** Under "Application checks" the review can list notes: two controls that contradict each other on the same items, two controls that overlap, or removals that together take more than half of the items. A note is not a failed check. Read it before you approve.

Below the blocks are two more parts.

- **Evidence for every item in the scope.** One row for each item: its description, its categories and tags, why it is selected or not selected, and the result if you approve. The result names the score change and the position, for example "Score +0.25; ranked higher: position 4 to 2".
- **Preview: the first ten items now and after approval.** The items that leave, enter or move are marked in words.

The feed below stays as it is until you approve. The cards of the language feed show the score as "Score 1.250 (base 1.000 + 0.25)".

The server accepts a review for five minutes. The page ends it a few seconds earlier. After that time the flag reads **EXPIRED · NOTHING WAS APPLIED**, and the only button is **Close this expired review**. Send the request again to get a new review. If the server refuses a review because it is too old or a newer request replaced it, the heading is "This review has expired".

After Apply, the main area shows **What changed**: the new controls, the items, the number of eligible items before and after, the time, and the button **Undo this change (review first)**. When you start a new request, this record folds to "Last applied change (time)".

While a call runs, the button shows the seconds. **Stop waiting** discards the result on this page. It does not stop the call on the server.

Two settings apply to every method.

- **Evidence scope.** "First 6 items of the starting list" or "First 10 items of the starting list". The application uses no other item.
- **How to combine with the applied controls.** "Add to the applied controls" or "Replace every applied control". "Add" keeps the applied controls. A new manual control replaces an applied control of the same name only when both have the same category and the same action. Another control with the same name stops the request with "An applied control has the same name". The method with categories and tags gives a generated name a number when the name is in use, for example ` (2)`.

Limits that the page states: at most 8 applied controls; at most 4 controls in one request; a review is valid for five minutes; Undo goes back at most 10 changes. A ninth control stops the request with the heading "At most eight controls can be applied". The manual method and the method with item descriptions stop before any model call. The method with categories and tags decides after the interpretation, because a reply can replace an applied control and then fits; the page then says that a model call was made.

## Existing category (manual, no model)

This method is the reference for the language controls. No model is called.

1. Method: **Existing category (manual, no model)**.
2. Existing category: choose one from the list, for example `Cooking` in the scenario `tags`. At the start no category is selected, and the button of step 5 stays disabled until you choose one.
3. Action: **Show more (raise the score)**, **Show less (lower the score, still in the feed)** or **Remove from the feed**. For more or less, choose the strength: Light 0.10, Standard 0.25 or Strong 0.40.
4. Name of this control: keep the name `Manual: Cooking` or write your own.
5. Press **Show the proposed change**.
6. Read the review. The first block is "Your selection". The table says for each item whether its category is the chosen one.
7. Press **Approve this exact item set and apply**.

Example in the scenario `tags`: `Cooking` with "Remove from the feed" selects the items 61001, 61002 and 61009. The feed goes from 10 eligible items to 7. Undo restores 10.

## My request, matched to existing categories and tags (model)

Use this method when the request should become a control over category and tag names that already exist. The request does not need to contain a name.

1. Method: **My request, matched to existing categories and tags (model)**.
2. The panel lists **Existing categories and tags in the scope**, with the number of items for each name. This list needs no model call.
3. Write your request, or press **Insert the bundled scenario request**. The list **More bundled examples** holds further requests.
4. Press **Interpret my request**. The application makes one model call.
5. Read the three blocks and the table. The table says through which category or tag each item is selected. For an item that is not selected it says "not selected: none of its categories or tags was chosen".
6. Press **Approve this exact item set and apply**.

What the model receives: your request, the category and tag names of the scope with the number of items for each name, and the number of items in the scope. It does not receive the item descriptions.

What the application does with the reply:

- It checks that every returned name exists with exactly the supplied value.
- It checks that the quoted part of the request is an exact part of the request.
- It checks that no control is too broad and that two controls do not give opposite instructions to the same items.
- It then selects the items that carry the chosen names. The model does not select items.
- It names each control from its action and its names, for example `Remove: category "Cooking", tag "street food"`.

Example of the mechanics in the scenario `tags`: a reply that chooses the category `Cooking` and the tag `street food` with the action "remove" gives the control `Remove: category "Cooking", tag "street food"`. The category `Cooking` selects 61001, 61002 and 61009. The tag `street food` selects 61003. The feed goes from 10 eligible items to 6. Undo restores 10.
Item 61004 mentions a sandwich in its description only. It has no food category and no food tag, so this method cannot select it. Which names fit a request is the decision of the model; the application holds no answer for any request.

Limits that the application enforces:

- One control cannot select more than half of the items in the scope. The removals of one request together cannot remove more than half.
- The list of names that goes to the model has at most 120 names and 12,000 bytes. A larger list asks you for a smaller scope.
- A request that matches the negated-command pattern stops before any model call. The pattern is a negated hide, exclude, remove, reduce or boost, for example "Do not hide ...", or a negated "show ... more" or "show ... less". It is one English pattern: another wording of a negated command goes to the model and then to you. "Do not show ..." without "more" or "less" does not match the pattern. It goes to the model as a request to remove.
- A request with a control character or a format character is refused (HTTP 422).

## My request, matched to item descriptions (model)

Use this method when the answer is in what the descriptions say, not in a category or tag.

1. Method: **My request, matched to item descriptions (model)**.
2. Write your request, or press **Insert the bundled scenario request**.
3. Name of this control: keep the name or write your own.
4. Press **Interpret my request**. The application makes two model calls at most. Call 1 reads the direction and strength from the request. Call 2 selects items and cites a quotation from each one.
5. Read the review. The block "Application checks" shows the complete text around each quotation. Check it for a negation or a contrary meaning.
6. Press **Approve this exact item set and apply**.

What the model receives: your request and the item data of the scope: descriptions, categories and tags.
What the application checks: every selected item is in the scope and has its own quotation, and every quotation is an exact part of the text of its own item. Any other reply is rejected and nothing is proposed. The negated-command pattern and the size of the item data are checked before the first call.

Example of the mechanics in the scenario `tags`: a reply for "Remove the videos where someone is eating." that cites the quotation "between bites of a sandwich" selects item 61004. The feed goes from 10 eligible items to 9. The category and tag method cannot find this item, because no label says it. Which items fit a request is the decision of the model.

The option **I will state the target meaning and the action myself.** lets you write the target and choose the action. Tick "I confirm this target and the action below as my intended instruction." The model then only proposes related items. The review says that you supplied the interpretation.

## A new category from my description, in stages (model)

Use this method when no existing category or tag covers what you want.

1. Method: **A new category from my description, in stages (model)**.
2. Describe the category that you want, or press **Insert the bundled scenario request** in the scenario `category`.
3. Action: choose the direction and strength yourself, for example **Remove from the feed**.
4. Press **Propose a definition for review**. Call 1 proposes a name, a definition and quotations.
5. If the model names competing meanings, the heading is **Choose between the meanings of the category**. Tick "I choose this exact, unchanged definition for review." and press **Continue to definition review**, or press **Cancel category clarification**. This choice makes no model call and approves nothing.
6. Under **Review the proposed definition**, read the definition, each quotation and the complete field that it comes from. Tick "I checked that the quotations support the complete definition." Press **Approve the definition and classify the items of the scope**. To get another definition, press **Reject this definition** and change your description. The decision has the same five-minute limit as every review.
7. Call 2 classifies every item in the scope. Call 3 assesses the evidence without seeing the classifications. The two calls that follow your approval can take longer than five minutes.
8. Read the table. It has one row for each item, with the classification (call 2), the separate evidence assessment (call 3) and the decision of the application. Where the two calls disagree, the item gets no decision and is not selected.
9. Press **Approve this exact item set and apply**.

The name that the model proposes becomes the name of the control. It cannot be changed on this page. A name that already exists stops the request with the heading "The proposed name already exists".
An approved definition is used once. If the classification stops, press **Propose a definition for review** again.

The two calls can use the same model, and both can be wrong. A quotation that exists is not proof that the definition is right. Reject a definition that states a property that the descriptions do not state.

Example of the mechanics in the scenario `category`: when both calls support the items 41001, 41002 and 41003 as members, those three items are selected and the feed goes from 8 eligible items to 5. Undo restores 8. When the two calls disagree on an item, its row reads "Not selected: the two calls do not agree".

The page also offers two earlier methods where the server allows them: **A new category in one call (earlier method)**, and **My request, matched to item descriptions (local model NAME)** through a local Ollama model.

## A mixed request

One request can hold several preferences. The existing categories-and-tags method selects items by their labels. The separate **My mixed request, matched to descriptions, categories and tags** method sends the supplied captions, cover text and existing labels in one call, then checks each selected item and its cited evidence. Review every proposed control before Apply.

Example in the scenario `tags`: "Show me more music videos, and remove anything about food." A reply that proposes the two controls below gives one review with two controls. `Show more: category "Music"` covers the items 61007 and 61008 (score +0.25). `Remove: category "Cooking", tag "street food"` covers the items 61001, 61002, 61003 and 61009. After Apply, item 61007 moves from position 4 to 2, item 61008 moves from position 5 to 4, and the feed goes from 10 eligible items to 6.
The table has one group of rows for each control. In the existing-label method, an item in several controls shows one net result and removal takes priority. The combined descriptions-and-labels method rejects overlapping member sets. One approval applies the accepted controls together, and one Undo reverses them.

Two controls that give opposite instructions to the same items get a request for clarification.

## Requests that change nothing

Some requests must not change the feed. The result then carries the flag **NO CHANGE PROPOSED · NOTHING WAS APPLIED**. The first block says what came back. The block "Application checks" says what the application did and how many calls started. The block "Your decision" says what you can do next.

| Result | Heading in the page | Bundled example in the scenario `tags` |
| --- | --- | --- |
| The reply says that the request has several possible meanings. | The request has more than one possible meaning | "I have had enough of the heavy stuff." |
| The request matches the negated-command pattern. The application stops it with its own check. No model is called. | The application stopped the request | "Do not hide the cooking videos." |
| The reply says that the controls cannot express the request, for example a quota, a time or an exception. | The reply reports that the controls cannot express this request | "Show me at most two cooking videos per day." |
| The reply says that no existing name or description matches. | The reply reports no match | "Show me fewer videos about astronomy." |
| A call started, and no usable reply came back. | The call to the provider failed | none |
| A reply came back, and the application rejected it. | The application rejected the reply | none |

The application accepts a "no match", "cannot express" or clarification result because the reply selects nothing. It does not check the reason in the reply. The reason stands in the first block, as text of the reply.

When a model names alternatives, each one has a button. In the method with categories and tags it is **Add this meaning to my request**: it adds the meaning to your request in the panel. In the method with item descriptions it is **Use this as my stated target**. Nothing is sent until you submit the request again.
The message of an error comes from the application or from the model provider. See the [failure table](model-routes.md#if-something-fails).

A real model can answer one of these examples with a proposal. Then review it as any other proposal. You are not obliged to approve it.

## Undo and removal

- **Undo the last change (review first)** in the panel, or **Undo this change (review first)** in the record "What changed", shows the review "Undo: restore the state before the last approved change". Press **Approve the undo** to restore the earlier feed. The application keeps up to ten earlier states.
- **Remove every applied control (review first)** shows the review "Remove every applied control". Press **Approve: remove every control** to remove them.
- **Reset this user** at the top of the page asks first. **Yes, remove everything** clears every control, all item feedback and the fictional items of the selected user. You cannot undo a reset.

The list **Applied controls** in the panel shows what is active. Applied controls last for one browser session. A reload of the page starts a new session without them.

## The fictional item

Below the panel, under **Fictional items (separate list)**, open **Open the fictional items**.

1. Describe the fictional item, or press **Insert the example description**.
2. Tick "I want a fictional item, not a real video or an item of the catalogue."
3. Press **Write a fictional draft**. The application makes one model call. The model receives your description and the drafting instruction. It does not receive the catalogue.
4. Read the draft under "Review the fictional item before you add it". Press **Approve and add to the list of fictional items**.
5. Remove the item with **Remove fictional item ID**, or every item with **Remove every fictional item**.

A fictional item never enters the dataset, the scope of a language control, the conditions A to E or the trained scorer. The list of fictional items has no score: it shows the items in the order in which you added them. See [fictional item drafts](synthetic-item-drafts.md).

## The earlier topic tool

Below the fictional items, **Open the earlier topic tool** holds the tool **Exact phrases** of 4 November. It matches exact phrases in the item text and keeps its own controls and its own feed. Its buttons are **Review the change**, **Approve and apply**, **Undo the last phrase change (review first)** and **Remove every phrase (review first)**. Its language input needs a local Ollama model. Without one, it accepts the phrases that you type.

## Which evidence each provider gives

| Provider | Start with | What answers | Status line | What a run shows |
| --- | --- | --- | --- | --- |
| `manual` | `quickstart.py manual` or `run_demo.py --provider manual` | Nobody. Only the manual method works. | `No model provider · manual controls only` | The manual control. |
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
- The page opens directly; there is no password or token. The server uses port 8765 on 127.0.0.1 only and refuses requests from other hosts or origins.
- A configuration file is marked as used and is refused a second time. The first request must equal the pinned scenario request exactly.
- The report holds the facts of the provider: the exact inputs, the call receipts and the number of attempts.
- The configuration templates in `tools/hosted_validation_current/` are incomplete on purpose, and every statement in them is false. These dated inputs and their driver are frozen evidence. A later prompt or source revision needs a separate reviewed successor profile; do not overwrite this directory.
- With the source of this revision this provider does not start a scenario: the pinned first request and the source hashes of the frozen profile belong to the source of 11 November 2026, and this repository holds no successor profile. For the general quickstart CLI route, use `python scripts/quickstart.py setup` ([guide](model-routes.md)). The separate [personal Windows binding](../diagnostic/README.md) requires explicit setup, reviewed inputs and a separately authorized caller; it is not a replacement profile for this frozen driver.

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
| `manual` | An existing category chosen by hand. No model call. | `tags`, `category`, `hunger` |
| `vocabulary` | The bundled request matched to categories and tags: three blocks, preview, Apply, Undo. | `tags` |
| `mixed` | One request with several preferences: one review, one Apply, Undo. It checks that the increase moves its items. | `tags` |
| `outcomes` | The four requests that must change nothing. | `tags` |
| `description` | The bundled request matched to descriptions. | `tags` |
| `fictional` | A fictional item: draft, review, add, remove. | `tags` |
| `category` | A new category in stages. | `category` |
| `reject` | A new category: the definition under review is rejected, and the server no longer accepts it. | `category` |
| `indirect` | An indirect request matched to descriptions. | `hunger` |
| `history` | Two manual controls; Undo returns to the state with the first one; the removal of every control and its undo. | `tags`, `category`, `hunger` |
| `failure` | A request that gets no usable reply: the page names the failed call, never "no call", and nothing changes. | `tags`, `category`, `hunger` |
| `expired` | The page clock passes five minutes; then the server refuses a review that a newer request replaced. | `tags`, `category`, `hunger` |
| `original` | The conditions A to E: on `conditions` the instruction and the profile work; on the other scenarios both are disabled with the reason. | all |

Without `--flows`, the script runs every flow of the scenario. `--flows manual,vocabulary` runs a part. On the scenario `conditions` the script runs `original` only.

For each flow the script checks these things against the server's own state:

- a preview changes nothing, also in the conditions A to E, the topic tool and the fictional items;
- the preview feed and the applied feed have the order that the approved controls give;
- Apply has exactly the approved effect;
- the two-step Undo restores the identical feed.

For `outcomes` it records the result that it observed beside the expected result. It asserts that nothing changed. If a model proposes a change there, the script discards the proposal and records that.
For `failure` it accepts an answer with HTTP 200 or a structured answer with HTTP 502.

**Review modes.**

- `--review auto` (the default): the script ticks the review boxes itself. Use it only with a server that has no model provider (`manual`) or with a test double. With a model as provider, the script stops with a failed check.
- `--review wait --reviewer "your name"`: the script stops at each review. It writes `gate-NAME.json` and a screenshot into the `--out` folder. It continues only when you write the word `APPROVE` into `decision-NAME.txt` in that folder. Any other text is recorded as a decline, and the flow stops with nothing applied.

**The receipt.** `browser-receipt.json` in the `--out` folder lists the checks of the script and the review decisions with the name of the reviewer. It also lists every provider call with a reply, the number of calls that the server says it started (`calls_attempted`, failed calls included), the text of the status line and the source fingerprint of the server. `python scripts/run_demo.py --fingerprint` prints the fingerprint of your files.

**Exit codes.** 0: every flow completed. 2: a flow stopped early, for example after a declined review or a rejected reply. 1: a check failed.

With `--video` the script records the page to `video/SCENARIO.webm` in the `--out` folder.

## Other checks

```
python -m pytest -q -p no:cacheprovider
python scripts/run_guarded_current_contract.py
node --test "web/tests/*.mjs"
python scripts/check_personal_ui_index.py
python scripts/refresh_source_manifest.py --check
```

The second command runs the guarded driver checks on the frozen profile of 11 November and on a temporary copy with the current-contract test inputs. On the frozen profile some checks do not pass, because the prompts changed after that date; the command says which result is expected.

The Node tests need `npm ci` in `web/` first. These are checks of the program with test doubles and stand-ins. They are not model evidence.
`npm run build` in `web/` reproduces the built interface in `web/dist` byte for byte. See [the built interface](source-verification.md).
