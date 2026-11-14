# Route trial

This page tells you how to try a model route on the application's real tasks before you open the page.
It also tells you how to put two models side by side on the same requests.

Read [Model routes](model-routes.md) first. It tells you how to choose a route and how to confirm that it works.

## What the trial does

`doctor` confirms that a route is connected. It sends one very small test request.
The trial goes one step further. It sends the bundled requests of a scenario through the route and shows what the application made of each reply.

- The trial builds the application in the same way as the launcher. It uses the same scenario files, the same instructions to the model and the same checks.
- It sends each request to the application's own interface, with no server and no browser.
- It stops each case at the first point where a person must review.
- It never approves, applies or admits anything. After each case it reads the applied state back and records that nothing changed.

One command gives you a table and two files.

## What the trial does not show

- **It is not an accuracy study.** The requests are exposed development requests. The items are invented. A scenario has nine cases at most, and each case runs one time.
- **It has no reference labels.** The last column compares a reply with one hand-written rehearsal reply for the same request. "The same" does not mean "correct", and "other" does not mean "wrong". A clarification can be a good answer to a request.
- **It does not review meaning.** The application's checks are mechanical. A passed check shows that a category name, a tag, an item number or a quotation exists in the item data. A person must still judge the meaning in the page.
- **It does not measure recommendation quality or human satisfaction.**
- **It does not attest the model.** The model name is the name that the route declares.

Use the trial to answer one question: can this model, through this route, give replies that the application accepts for its real tasks?

## Run a trial

Install the application and set up a route first. Then run one command from the repository root, with the virtual environment active.

```
python scripts/quickstart.py try --scenario tags
```

This is the same as `python scripts/route_trial.py run --scenario tags`. It uses the route in `model-route.json`.

| Option | Meaning |
| --- | --- |
| `--scenario tags` | The scenario. `tags` has nine cases. `hunger` and `category` have one case each. |
| `--route-file FILE` | Another route file than `model-route.json`. |
| `--provider scripted` | Use the hand-written rehearsal replies. No model is called. Use this to see the tool work. |
| `--cases a,b` | Run only these cases. `python scripts/route_trial.py cases --scenario tags` lists them. |
| `--out FOLDER` | A new folder for the records. The default is a new folder under `runs/`. |

The cases of scenario `tags`:

| Case | Method in the page | Model calls at most | Request |
| --- | --- | --- | --- |
| `vocabulary` | categories and tags | 1 | "I'm not hungry, remove all the stuff that makes me hungry." |
| `vocabulary:literal` | categories and tags | 1 | "Hide the Repair category." |
| `vocabulary:mixed` | categories and tags | 1 | "Show me more repair videos, and remove anything about food." |
| `vocabulary:ambiguous` | categories and tags | 1 | "I have had enough of the heavy stuff." |
| `vocabulary:unsupported` | categories and tags | 1 | "Show me at most two cooking videos per day." |
| `vocabulary:negated` | categories and tags | 1 | "Do not hide the cooking videos." |
| `vocabulary:no_match` | categories and tags | 1 | "Show me fewer videos about astronomy." |
| `configured_model` | item descriptions | 2 | "Remove the videos where someone is eating." |
| `synthetic` | fictional item draft | 1 | "A fictional 40-second clip about repairing a kite, for a test feed." |

Scenario `hunger` has the indirect request that is matched to item descriptions. Scenario `category` has the first stage of a new category: the definition. The trial does not run the classification, because a person must approve the definition first.

For the fictional item, the page asks a person to confirm that the draft is fictional metadata before the model is called. The trial gives that confirmation. It does not admit the draft to a feed.

### Before the first call

The trial counts the model calls that the chosen cases can need. All cases of `tags` can need ten calls.
If the route file allows fewer calls (`max_calls`), the trial stops before any call and tells you what to change.
A hosted route can cost money for each call. Choose fewer cases with `--cases` if you want fewer calls.

A key for a hosted route comes from the environment variable that the route file names, or from a hidden prompt. The trial never writes it.

### With the relay route

The relay route has no connection to a model. The trial prints the relay folder and the relay commands, then it waits for each reply as the application does.
Answer each request in a second window with `scripts/relay_tools.py`, as [the demonstration guide](demo.md#the-relay-provider) tells you.

### If you stop the trial

Press Ctrl+C. The trial records the cases that are finished and stops. A model call that is in progress is not recorded as a case.

## Read the table

This is the table of a run through the `openai-compatible` route against the stand-in server of the tests.
The stand-in answers with the hand-written rehearsal replies. It is not a model, so every row is the same as the rehearsal reply, and each call takes almost no time.
A run with a model shows the same columns.

```
Case                    Method in the page    Calls  Outcome      Same as authored rehearsal reply  Seconds
----------------------  --------------------  -----  -----------  --------------------------------  -------
vocabulary              categories and tags   1      review       same outcome, same selection      0.1
vocabulary:literal      categories and tags   1      review       same outcome, same selection      0.1
vocabulary:mixed        categories and tags   1      review       same outcome, same selection      0.1
vocabulary:ambiguous    categories and tags   1      clarify      same outcome                      0.1
vocabulary:unsupported  categories and tags   1      unsupported  same outcome                      0.1
vocabulary:negated      categories and tags   0      clarify      same outcome                      0.0
vocabulary:no_match     categories and tags   1      no match     same outcome                      0.1
configured_model        item descriptions     2      review       same outcome, same selection      0.1
synthetic               fictional item draft  1      draft ready  same outcome                      0.0
```

**Calls.** The number of model calls that the case made. The case `vocabulary:negated` makes no call: the application itself answers a request that negates a command.

**Outcome.** The class that the application gave to the reply.

| Outcome | Meaning |
| --- | --- |
| `review` | The reply passed the application's checks. In the page a person would now review the proposed change. |
| `clarify` | The application asks the person to state the request more exactly. The model found competing meanings, or the application's own rules found a negated command, a contradiction or a scope that is too broad. |
| `no match` | The model found no existing category, tag or item for the request. |
| `unsupported` | The request asks for an operation that these controls do not have, for example a quota or a time condition. |
| `definition for review` | A new category: the model proposed a definition, and a person would now review it. |
| `draft ready` | A fictional item: the model wrote a draft, and a person would now review it. Nothing is admitted to a feed. |
| `error` | The route failed, or the application rejected the reply. The text below the table says what happened and what to do. |

**Selection.** Below the table, one line for each case gives the action, the category and tag names or the quotations that the model chose, and the items. The model chooses names or quotations. The application selects the items.

**Application checks.** For the category and tag route the application returns a list of named checks. The line gives the number that passed.

**Same as the authored rehearsal reply.** The trial runs each case a second time with the hand-written rehearsal reply, in a second copy of the application with no model.

- `same outcome`: the outcome class is the same.
- `same selection`: both are reviews, and each control has the same action and the same items.
- `other selection`: both are reviews, and the action or the items differ. Read both. Neither is marked as right.
- `no (rehearsal: ...)`: the outcome class differs.

**Exit code.** 0: no case ended in an error. 2: at least one case ended in an error. 1: the trial could not start, was interrupted, or could not state that nothing was applied.

## Compare two models

Run the trial one time with each route. Give each run its own folder. Then compare the two folders.

```
python scripts/route_trial.py run --scenario tags --route-file route-local.json --out runs/trial-local
python scripts/route_trial.py run --scenario tags --route-file route-hosted.json --out runs/trial-hosted
python scripts/route_trial.py compare runs/trial-local runs/trial-hosted --out runs/local-and-hosted.md
```

The comparison prints one row for each case: the outcome of each trial, whether the outcomes are the same, whether two reviews select the same items with the same action, and the seconds.

The comparison refuses two trials that cannot be compared:

- trials of different scenarios, because the requests differ;
- trials of different source files, because the application, the requests or the items differ. Each trial records the source fingerprint (`python scripts/run_demo.py --fingerprint`).

Read the comparison with these limits in mind.

- It shows that two models gave the same or different outcomes on a few exposed requests. It does not show which model is better.
- Each case ran one time. A model can give another reply to the same request the next time.
- The two routes can use different settings, for example the output limit, the reasoning effort or the sampling. The route identity in each record shows the settings. The comparison does not correct for them.
- The number of seconds includes the network and the provider's load at that time.

A result that supports a research claim needs its own protocol: requests that the model and the authors have not seen, reference labels with a stated origin, repeated runs and a fixed analysis. This tool does not replace that.

## The files

Each trial writes into its own folder. The trial refuses a folder that is not empty, so that no record is overwritten.

| File | Content |
| --- | --- |
| `trial.md` | The table, the route identity, the source fingerprint, the times in UTC and the limits. |
| `trial.json` | The complete record: each request text and its hash, the outcome, the controls, the chosen names or quotations, the selected items, the application's checks, every raw model reply, the route's receipt of each call, the comparison with the rehearsal reply and the applied state after the case. |
| `route-calls/` | With an HTTP or command-line route: the exact request body and the raw reply of each call, written by the route. No header and no key. |
| `relay/` | With the relay route: the request, reply and receipt files. |

No file holds a credential. The route layer removes a key from every text, and the trial passes its own records through the same filter one more time.

## How this tool was tested

The tests of this tool use the hand-written rehearsal replies and a stand-in server that answers in the documented format. They show that the tool reports each outcome class, stops before a review, applies nothing, counts the calls before it starts, reports a failing route with a text that says what to do, and writes no credential. They are not evidence about any model.
