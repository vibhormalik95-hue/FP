# Route trial: scenario `tags`

- The requests are exposed development requests of a bundled scenario with invented items.
- This is a check of a model route. It is not an accuracy study.
- An outcome that equals the authored rehearsal reply is not proof of a correct interpretation.
- Each case ran one time. Nothing was approved and nothing was applied.

- Started (UTC): 2026-11-14T17:11:44+00:00. Finished (UTC): 2026-11-14T17:11:46+00:00.
- Source fingerprint: `ab1a9d846b33bf0e7e3840b91b69f65747386daec2cf5d38fc621d455c8fcefd`
- Provider: model route; backend local-cli-claude-code; model standin-model (the name that the route declares; the application cannot attest it)
- Route: cli
- Program: /home/claude/work/runs/final/route-checks/files/bin/claude (Claude Code CLI, print mode, one process for each call)
- Model: standin-model
- Structured output: prompt; 600 s for one call
- Call allowance for one run: 40 (a counter in this program, not a billing limit)
- Configuration digest: 65138a4afd2dac1ce3bebaae9d831e7467705790611b36857a20b3a4d0587b71
- Cases: 9. Model calls: 9. Cases that ended in an error: 0.
- The applied state was read back after each case: nothing was applied.

| Case | Method in the page | Model calls | Outcome | Selection or reason | Application checks | Same as the authored rehearsal reply | Seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| vocabulary | categories and tags | 1 | review | exclude through category "Cooking", tag "street food": 61001, 61002, 61003, 61009 | 16 of 16 passed | same outcome, same selection | 0.2 |
| vocabulary:literal | categories and tags | 1 | review | exclude through category "Repair": 61004, 61005 | 16 of 16 passed | same outcome, same selection | 0.1 |
| vocabulary:mixed | categories and tags | 1 | review | boost standard through category "Music": 61007, 61008; exclude through category "Cooking", tag "street food": 61001, 61002, 61003, 61009 | 16 of 16 passed | same outcome, same selection | 0.1 |
| vocabulary:ambiguous | categories and tags | 1 | clarify | 3 alternatives; Semantic scope or negation has competing interpretations | 5 of 5 passed | same outcome | 0.2 |
| vocabulary:unsupported | categories and tags | 1 | unsupported | Authored rehearsal reply, not model output. A limit for each day is a quota. The controls can increase, decrease or exclude whole terms. They cannot count items or use the date. | 5 of 5 passed | same outcome | 0.1 |
| vocabulary:negated | categories and tags | 0 | clarify | The request matches the negated-command pattern (for example "do not hide ..."). The application does not guess what a negated control means. Write a positive instruction, for example "show more ..... | 1 of 2 passed; failed: The request text does not match the negated-command pattern | same outcome | 0.0 |
| vocabulary:no_match | categories and tags | 1 | no match | Authored rehearsal reply, not model output. No existing category or tag is about astronomy. | 5 of 5 passed | same outcome | 0.2 |
| configured_model | item descriptions | 2 | review | exclude: 61004 (quotation "between bites of a sandwich") | no list | same outcome, same selection | 0.3 |
| synthetic | fictional item draft | 1 | draft ready | title "Kite repair clip (authored rehearsal)" | no list | same outcome | 0.2 |

## How to read the table

- **Outcome** is the class that the application gave to the reply: a review for a person, a clarification, no match, unsupported, a definition for review, a draft, or an error. A clarification can be the right answer to a request.
- **Selection** lists the action, the existing category or tag names or the quotations, and the items. The application selected the items; the model chose the names or quotations.
- **Application checks** are mechanical. A passed check shows that names, identifiers and quotations exist in the item data. It does not show that the meaning is right.
- **Same as the authored rehearsal reply** compares with one hand-written answer for the same request. "Same selection" means the same action and the same items in each control. It is not a correctness label.

The complete record, with every raw reply, is in `trial.json` in this folder.
