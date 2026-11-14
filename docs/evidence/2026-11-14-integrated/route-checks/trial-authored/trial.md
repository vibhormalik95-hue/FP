# Route trial: scenario `tags`

- The requests are exposed development requests of a bundled scenario with invented items.
- This is a check of a model route. It is not an accuracy study.
- An outcome that equals the authored rehearsal reply is not proof of a correct interpretation.
- Each case ran one time. Nothing was approved and nothing was applied.

- Started (UTC): 2026-11-14T20:05:20+00:00. Finished (UTC): 2026-11-14T20:05:20+00:00.
- Source fingerprint: `22ba794e2091685fa879dcc43b68233dae1963fa4231c38dd73a36f13639068a`
- Provider: hand-written rehearsal replies. No model.
- Configuration digest: 0d746e68d25ba67d501d549ebd4985b8806fb1f29902345616371098af5ff577
- Cases: 9. Model calls: 9. Cases that ended in an error: 0.
- The applied state was read back after each case: nothing was applied.

| Case | Method in the page | Model calls | Outcome | Selection or reason | Application checks | Same as the authored rehearsal reply | Seconds |
| --- | --- | --- | --- | --- | --- | --- | --- |
| vocabulary | categories and tags | 1 | review | exclude through category "Cooking", tag "street food": 61001, 61002, 61003, 61009 | 16 of 16 passed | this run is the rehearsal | 0.0 |
| vocabulary:literal | categories and tags | 1 | review | exclude through category "Repair": 61004, 61005 | 16 of 16 passed | this run is the rehearsal | 0.0 |
| vocabulary:mixed | categories and tags | 1 | review | boost standard through category "Music": 61007, 61008; exclude through category "Cooking", tag "street food": 61001, 61002, 61003, 61009 | 16 of 16 passed | this run is the rehearsal | 0.0 |
| vocabulary:ambiguous | categories and tags | 1 | clarify | 3 alternatives; Semantic scope or negation has competing interpretations | 5 of 5 passed | this run is the rehearsal | 0.0 |
| vocabulary:unsupported | categories and tags | 1 | unsupported | Authored rehearsal reply, not model output. A limit for each day is a quota. The controls can increase, decrease or exclude whole terms. They cannot count items or use the date. | 5 of 5 passed | this run is the rehearsal | 0.0 |
| vocabulary:negated | categories and tags | 0 | clarify | The request matches the negated-command pattern (for example "do not hide ..."). The application does not guess what a negated control means. Write a positive instruction, for example "show more ..... | 1 of 2 passed; failed: The request text does not match the negated-command pattern | this run is the rehearsal | 0.0 |
| vocabulary:no_match | categories and tags | 1 | no match | Authored rehearsal reply, not model output. No existing category or tag is about astronomy. | 5 of 5 passed | this run is the rehearsal | 0.0 |
| configured_model | item descriptions | 2 | review | exclude: 61004 (quotation "between bites of a sandwich") | no list | this run is the rehearsal | 0.0 |
| synthetic | fictional item draft | 1 | draft ready | title "Kite repair clip (authored rehearsal)" | no list | this run is the rehearsal | 0.0 |

## How to read the table

- **Outcome** is the class that the application gave to the reply: a review for a person, a clarification, no match, unsupported, a definition for review, a draft, or an error. A clarification can be the right answer to a request.
- **Selection** lists the action, the existing category or tag names or the quotations, and the items. The application selected the items; the model chose the names or quotations.
- **Application checks** are mechanical. A passed check shows that names, identifiers and quotations exist in the item data. It does not show that the meaning is right.
- **Same as the authored rehearsal reply** compares with one hand-written answer for the same request. "Same selection" means the same action and the same items in each control. It is not a correctness label.

The complete record, with every raw reply, is in `trial.json` in this folder.
