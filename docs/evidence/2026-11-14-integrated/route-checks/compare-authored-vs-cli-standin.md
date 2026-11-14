Scenario: tags. Source fingerprint: 22ba794e2091685fa879dcc43b68233dae1963fa4231c38dd73a36f13639068a
Trial A: /home/claude/work/runs/build-22ba794/route-checks/trial-authored (started 2026-11-14T20:05:20+00:00 UTC)
  Provider: hand-written rehearsal replies. No model.
  Configuration digest: 0d746e68d25ba67d501d549ebd4985b8806fb1f29902345616371098af5ff577
Trial B: /home/claude/work/runs/build-22ba794/route-checks/trial-cli-standin (started 2026-11-14T20:05:23+00:00 UTC)
  Provider: model route; backend local-cli-claude-code; model standin-model (the name that the route declares; the application cannot attest it)
  Route: cli
  Program: /home/claude/work/runs/build-22ba794/route-checks/files/bin/claude (Claude Code CLI, print mode, one process for each call)
  Model: standin-model
  Structured output: prompt; 600 s for one call
  Call allowance for one run: 40 (a counter in this program, not a billing limit)
  Configuration digest: b7344ec3275177613eee5fc620bfeada1357cbb814f62928c3cd9cdffa52aef8

Case                    Outcome A    Outcome B    Same outcome  Same items and action  Seconds A  Seconds B
----------------------  -----------  -----------  ------------  ---------------------  ---------  ---------
vocabulary              review       review       yes           yes                    0.0        0.2
vocabulary:literal      review       review       yes           yes                    0.0        0.2
vocabulary:mixed        review       review       yes           yes                    0.0        0.1
vocabulary:ambiguous    clarify      clarify      yes           not applicable         0.0        0.2
vocabulary:unsupported  unsupported  unsupported  yes           not applicable         0.0        0.1
vocabulary:negated      clarify      clarify      yes           not applicable         0.0        0.0
vocabulary:no_match     no match     no match     yes           not applicable         0.0        0.2
configured_model        review       review       yes           yes                    0.0        0.3
synthetic               draft ready  draft ready  yes           not applicable         0.0        0.1

Cases that both trials ran: 9. Same outcome: 9. Both gave a review: 4; same items and action in 4 of them.
"Same items and action" compares two reviews: the same action and the same items in each control.
The requests are exposed development requests of a bundled scenario with invented items.
This puts two checks of a model route side by side. It is not an accuracy study.
Equal outcomes in two trials are not proof of a correct interpretation. Different outcomes do not show which one is right.
Each case ran one time in each trial. Nothing was approved and nothing was applied.
Two routes can use different model settings, for example the output limit or the sampling. This table does not correct for that.
