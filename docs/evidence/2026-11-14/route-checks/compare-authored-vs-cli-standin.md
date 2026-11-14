# Two route trials of scenario `tags`

- The requests are exposed development requests of a bundled scenario with invented items.
- This puts two checks of a model route side by side. It is not an accuracy study.
- Equal outcomes in two trials are not proof of a correct interpretation. Different outcomes do not show which one is right.
- Each case ran one time in each trial. Nothing was approved and nothing was applied.
- Two routes can use different model settings, for example the output limit or the sampling. This table does not correct for that.

- Scenario: tags. Source fingerprint: ab1a9d846b33bf0e7e3840b91b69f65747386daec2cf5d38fc621d455c8fcefd
- Trial A: /home/claude/work/runs/final/route-checks/trial-authored (started 2026-11-14T17:11:28+00:00 UTC)
  - Provider: hand-written rehearsal replies. No model.
  - Configuration digest: f44e7ff87a9383d78fe688fe1381396af8b86212a5fc42b5e042774868ad341f
- Trial B: /home/claude/work/runs/final/route-checks/trial-cli-standin (started 2026-11-14T17:11:44+00:00 UTC)
  - Provider: model route; backend local-cli-claude-code; model standin-model (the name that the route declares; the application cannot attest it)
  - Route: cli
  - Program: /home/claude/work/runs/final/route-checks/files/bin/claude (Claude Code CLI, print mode, one process for each call)
  - Model: standin-model
  - Structured output: prompt; 600 s for one call
  - Call allowance for one run: 40 (a counter in this program, not a billing limit)
  - Configuration digest: 65138a4afd2dac1ce3bebaae9d831e7467705790611b36857a20b3a4d0587b71

| Case | Outcome A | Outcome B | Same outcome | Same items and action | Seconds A | Seconds B |
| --- | --- | --- | --- | --- | --- | --- |
| vocabulary | review | review | yes | yes | 0.0 | 0.2 |
| vocabulary:literal | review | review | yes | yes | 0.0 | 0.1 |
| vocabulary:mixed | review | review | yes | yes | 0.0 | 0.1 |
| vocabulary:ambiguous | clarify | clarify | yes | not applicable | 0.0 | 0.2 |
| vocabulary:unsupported | unsupported | unsupported | yes | not applicable | 0.0 | 0.1 |
| vocabulary:negated | clarify | clarify | yes | not applicable | 0.0 | 0.0 |
| vocabulary:no_match | no match | no match | yes | not applicable | 0.0 | 0.2 |
| configured_model | review | review | yes | yes | 0.0 | 0.3 |
| synthetic | draft ready | draft ready | yes | not applicable | 0.0 | 0.2 |

Cases that both trials ran: 9. Same outcome: 9. Both gave a review: 4; same items and action in 4 of them.

"Same items and action" compares two reviews: the same action and the same items in each control. It says nothing about which review is right.
