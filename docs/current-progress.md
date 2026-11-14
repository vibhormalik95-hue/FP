# Application progress and remaining work

Updated 14 November 2026 (UTC). This page separates published implementation from development evidence. It does not declare the professor's requirements complete.

## Published implementation

The inspected source snapshot is commit `8a12661a36f0173e13c26964c4867e7bb52f2380` on `codex/comp9500-llm-upgrades-20261110`. It includes the integrated application, built interface, demo quick-start, file-relay and CLI operator, offline regression tests, and frozen-input byte checks. The source and interface are no longer separate unpublished candidates. Their inclusion does not establish successful Windows CLI inference or browser acceptance.

The earlier interface release `acbf5895b05cf44c1a11676cbd71b83d2337ada7` distinguished authored fixture data from verified dataset provenance and reported category availability explicitly. Its seven passing research-label tests are a historical result, not a test count for the current snapshot.

## Evidence for the three control paths

- **Manual category filtering:** a guarded direct-Python check on 14 November used an authored 36-item catalogue. Preview selected items 1 and 7, Apply reduced eligibility to 34, and Undo restored the exact 36-item baseline. Three fixture checks passed. These checks made no model call and did not run a browser or server. The earlier [manual demonstration](../deliverables/2026-11-05-final-demo/README.md) remains a separate dated record.
- **New categories from language:** the earlier local-model example created “offline practice without account creation” across existing Coding, Design and Language categories, then recorded 8 → 5 → 8 through reviewed Apply and Undo. See the [staged-induction record](../deliverables/2026-11-05-staged-induction/README.md). The current hosted successor has not established the full definition → membership → evidence review → Apply → Undo flow in the evidence reviewed for this update. A new input-binding candidate passed a guarded admission probe with synthetic responses and a blocked fake runner; it is not a real-model success.
- **Indirect requests:** the [11 November hosted summary](evidence/2026-11-11/HOSTED-TWO-SCENARIO-SUMMARY.md) records a hunger-related request selecting the described pasta, bread and salad items, with direct-Python Apply and Undo changing 8 → 5 → 8. It is a bounded development example, not browser acceptance, general language accuracy, or evidence about personal appetite. Earlier operator-copied examples remain in the [5 November walkthrough](../deliverables/2026-11-05-final-demo/README.md).

## Recording preparation

A separate isolated recording fixture now accepts explicitly supplied inference factories while leaving them disabled by default. Source review passed. Guarded checks confirmed that supplied adapters are visible, absent adapters remain unavailable, and invalid factory values are rejected. No inference was invoked in these checks. The fixture is preparation for a real demonstration, not the demonstration itself.

The runtime and built interface are now in the same published tree. End-to-end acceptance still needs results tied to the exact code and execution route used. No final video is tracked in this source snapshot.

## Remaining acceptance

1. Complete the actual hosted new-category flow, including source-evidence review, Apply and exact Undo restoration.
2. Verify the three required controls in the actual demonstration interface, retaining the requests, source items and observed results.
3. Verify the integrated runtime and interface together on the intended execution route, retaining the exact commit and test results.
4. Record the verified application and provide the professor with the video and accurate requirement-to-evidence summary.

A passing offline suite, configured adapter, or published commit does not substitute for these observations. Historical failed calls and their original outcomes remain in the dated evidence and repository history.

## Research results and related work

The original A–E comparison, Experiment 1 and revised Experiment 2 remain separate from application-development examples. Their results and limitations have not been changed by interface work. See the [evaluation protocol](evaluation-protocol.md), [Experiment 2 results](ai-reference-e2-results-2026-10-14.md), and [research provenance](academic-use.md).

Fictional-item metadata is a separate extension. A historical hosted Lunaria example completed preview, admission, removal and restoration through direct Python methods; it generated no real video and did not establish trained cold-start recommendation quality. See the [public-safe summary](evidence/2026-11-11/FABLE-LUNARIA-PUBLIC-SAFE-SUMMARY.json).

The [validation guide](../tools/hosted_validation_current/README.md) and [provider implementation notes](../CLAUDE-PERSONAL-CANDIDATE.md) retain dated technical details. Their older profile and test descriptions are historical unless a newer, explicitly dated result identifies the exact successor. No general model ranking, recommendation-quality improvement or user-satisfaction result is claimed here.
