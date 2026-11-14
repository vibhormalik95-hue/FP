# Scenario `tags`: existing categories and tags

This folder holds ten invented items. They are not KuaiRec items and they are not real videos. The scenario shows how a request is matched to category and tag values that already exist. The feed uses the labelled diagnostic scorer, not the trained recommender. A run on this scenario shows the steps of a control: proposal, checks, review, Apply and Undo. It does not measure accuracy or recommendation quality.

## Files

| File | Content |
| --- | --- |
| `app-data.json` | The ten items, one user with an empty history, and the fixture label. The category of an item is its first-level category. |
| `metadata.csv` | For each item: a description, the tags, and the first-level and second-level category. The seven columns are the item identifier and the six text columns that the application reads from the KuaiRec caption file. The three category identifier columns of that file are not present. |
| `requests.json` | The bundled request texts. The page can insert them. The key `label` is the name that the page gives to the control of the description request. |

Start the scenario from the repository root:

```
python scripts/run_demo.py --scenario tags --provider scripted
```

## Items

| Item | Category | Subcategory | Tags | Description |
| --- | --- | --- | --- | --- |
| 61001 | Cooking | Home recipes | recipe, dinner | Episode 12 of a weeknight series. Running time 58 seconds. |
| 61002 | Cooking | Baking | baking, bread | Part 3 of a weekend series. Running time 45 seconds. |
| 61003 | Travel | City walks | street food, night market | An evening walk between stalls. Running time 62 seconds. |
| 61004 | Repair | Bicycle repair | bicycle, tools | A mechanic cleans a bicycle chain between bites of a sandwich. |
| 61005 | Repair | Home repair | lamp, tools | An electrician replaces a desk lamp switch. |
| 61006 | Travel | Rail journeys | train, bridge | The camera follows a train crossing a bridge. |
| 61007 | Music | Guitar | guitar, practice | A player repeats a short guitar exercise. |
| 61008 | Music | Live sessions | piano, live | A pianist plays one piece in a small room. |
| 61009 | Cooking | Home recipes | recipe, salad | Episode 13 of a weeknight series. Running time 51 seconds. |
| 61010 | none | none | none | Untitled clip: no category or tag is supplied. |

The items are written so that labels and descriptions disagree in known places:

- Items 61001, 61002 and 61009 have a food category. Their descriptions say nothing about food.
- Item 61003 has a food tag in a category that is not about food.
- Item 61004 mentions food only in its description. It has no food category and no food tag.
- Item 61010 has no category and no tag.

A match to categories and tags can therefore select only what the labels state. A match through descriptions can select only what the descriptions state.

## Bundled requests

| Key in `requests.json` | Request | What it shows |
| --- | --- | --- |
| `vocabulary` | I'm not hungry, remove all the stuff that makes me hungry. | An indirect request. No category or tag name is in the text. |
| `vocabulary:literal` | Hide the Repair category. | A literal request that names an existing category. |
| `vocabulary:mixed` | Show me more music videos, and remove anything about food. | Two preferences in one request. The increase moves the two music items up in the list. |
| `vocabulary:ambiguous` | I have had enough of the heavy stuff. | A request with several possible meanings. |
| `vocabulary:unsupported` | Show me at most two cooking videos per day. | A quota. The controls cannot express it. |
| `vocabulary:negated` | Do not hide the cooking videos. | A request that matches the negated-command pattern. The application stops it before any model call and asks for a positive instruction. |
| `vocabulary:no_match` | Show me fewer videos about astronomy. | A subject that no existing term covers. |
| `configured_model` | Remove the videos where someone is eating. | The separate route that reads descriptions and quotes them. |
| `synthetic` | A fictional 40-second clip about repairing a kite, for a test feed. | A brief for a fictional item in the separate fictional feed. |

A key that starts with `vocabulary` is for the method that matches a request to existing categories and tags. The model receives the request and the list of existing terms. It does not receive a description. The application checks each returned term and selects the items that carry it.

## Rehearsal replies

`scripts/demo_scripted_replies.py` holds a hand-written reply for each bundled request. Provider `scripted` returns them. They are not model output. With these replies:

- the indirect request selects the category `Cooking` and the tag `street food`, and so the items 61001, 61002, 61003 and 61009;
- the literal request selects the category `Repair`, and so the items 61004 and 61005;
- the mixed request gives two controls: an increase for `Music`, and an exclusion for `Cooking` and `street food`. After Apply, item 61007 moves from rank 4 to rank 2 and item 61008 moves from rank 5 to rank 4;
- the description request selects item 61004 with the quotation "between bites of a sandwich".

The application names each control from its action and its terms, for example `Remove: category "Cooking", tag "street food"` and `Show more: category "Music"`. A name that is already in use gets a number, for example `(2)`.

A real model can select other terms. Review each proposal before you apply it.

## Limits to know

- The negated-command pattern is one English pattern: do not, don't, never or not to, followed by hide, exclude, remove, reduce or boost, or by "show ... more" or "show ... less". Another wording of a negated command is not detected. It goes to the model and then to the reviewer. "Do not show ..." without "more" or "less" is a plain request to remove and is not stopped.
- A control changes only the items of the evidence scope. This scenario has ten items and the scope is the whole list, so the difference cannot be seen here.
- The limits of one request (one control over at most half of the scope; the removals of one request over at most half of the scope) do not count controls that are already applied. The review lists overlaps, contradictions and a total removal of more than half of the items as notes. A note does not stop the request.
- At most eight controls stay applied. A ninth control is refused with a sentence that says what to do. The manual method and the method with item descriptions refuse it before any model call. The method with categories and tags decides after the interpretation call, because a reply can replace an applied control and then fits.
