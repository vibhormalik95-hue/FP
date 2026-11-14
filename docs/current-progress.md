# Application progress and remaining work

Updated 14 November 2026 (UTC), against source commit `8db85240db0a947312c3551b5d0e06c71ee5c7b3` on `codex/comp9500-llm-upgrades-20261110`. This is an evidence map, not a declaration that all requirements are complete.

## Latest professor requirements

The latest supplied transcript was received on 4 November; its meeting date is not independently verified. The [dated requirement worksheet](requirement-worksheet-2026-11-11.md) records the three requested paths at 08:22 and 08:38. Fictional descriptions and stronger-model comparison were additional student commitments at 02:08-02:35. The table below keeps those scopes separate.

| Requirement | Available evidence | Remaining acceptance |
| --- | --- | --- |
| Manual categories and measurable performance | [4 November evaluation](../deliverables/2026-11-04-prospective-evaluation/PROTOCOL-AND-RESULTS.md): intended manual profile HR@1 0.023333, NDCG@10 0.061120, fill 1.000; 24 users, 100 authored language cases, three seeds. Separately, the [14 November Windows Opera check](evidence/2026-11-14/OPERA-MANUAL-CONTROLS.md) at 15:19 UTC recorded manual K1 exclusion: 8 to 6 to 8, removing only 41001 and 41004. Preview and Undo review left the feed unchanged; approved Undo restored exact IDs and order. | Manual browser control is established on the named source revision by the browser operator’s recorded report; screenshot files were not retained. The initial category_1 value needed correction to K1. Recheck affected behavior after later source changes. Historical performance and this synthetic manual check remain separate. |
| Create a new category from language and feed it into filtering | [5 November staged induction](../deliverables/2026-11-05-staged-induction/README.md) records a rendered-browser Llama check on seven synthetic coffee, gardening and cycling items. It proposed mains-electric equipment: positives 2/4/6, negatives 1/3/5, unknown 7. Reviewed exclusion changed 7 to 4; Clear restored seven items; Undo restored the excluded group and four-item feed. This historical two-stage example is not the current three-stage flow. Current code also includes separate evidence review. | A complete current Windows model-backed definition, membership, review, Apply and Undo run is not established by the tests below. Bind any submitted recording to the source and provider actually used. |
| Indirect intent matched to existing categories or tags | [11 November hosted example](evidence/2026-11-11/HOSTED-TWO-SCENARIO-SUMMARY.md) used descriptions of pasta, bread and salad, with direct-Python 8 to 5 to 8. Current [metadata-only regression](../tests/test_existing_metadata_offline.py) removes descriptions and tests `topic_tag` and `first_level_category_name`: accepted authored proposals remove only items 3 and 4, then restore the 36-item baseline. Invalid source fields, quotations and item references are rejected. | The historical description example does not satisfy the stronger category/tag evidence claim. The metadata regression proves handling of authored proposals, not that a real model inferred the correct existing category or tag. Demonstrate that inference separately. |

Feed counts prove reversible control, not recommendation quality, general language accuracy or user satisfaction. The manual performance result uses the original dated study, not the eight-item demonstration scorer.

## Published implementation and current offline check

The inspected source includes the integrated application and built interface, demo quick-start, file relay, CLI operator, metadata-only regression and frozen-input byte checks. Source and interface are not separate unpublished candidates. Shipped code does not establish Windows CLI inference or browser acceptance.

On 14 November, the following command ran on Windows with Python 3.14 against the source above:

```powershell
python -X utf8 -B -m pytest -q -p no:cacheprovider tests/test_existing_metadata_offline.py tests/test_cli_safe_evidence_offline.py tests/test_relay_transport_parity.py
```

Result: **26 passed**, with two dependency deprecation warnings. These tests cover category/tag evidence contracts, bounded CLI failure evidence and strict relay decoding. They use authored responses and test doubles. No provider or real-model request was made. This is a focused check, not the whole suite or a fresh installation test.

The [app guide](app.md) describes the manual provider, authored rehearsal, file-relay operator and local CLI operator. The no-model manual provider and the manual file-relay operator are different routes. Fresh macOS setup and current real Windows CLI acceptance are not verified here.

## Recording and delivered external evidence

A separate execution report supplied by the student describes a `b9220b4` integration recording: manual 8 to 6 to 8, new category 8 to 5 to 8 with 29 checks, and indirect request 8 to 5 to 8 with 27 checks. It reports 1,101 passing tests and file-relayed real-model responses. These are **reported external results**, not a rerun of the current commit in this update. The report identifies an automated reviewer, no real Windows CLI test, and descriptions rather than existing food categories/tags for the indirect example. No final video is tracked in this source snapshot.

Use a recording only with its actual code revision, provider route, data and reviewer provenance. Do not present an older or externally reported recording as a verified current Windows run. An offline suite or configured adapter does not substitute for those observations.

## Additional commitments and research boundaries

- **Fictional metadata:** a historical hosted Lunaria example completed preview, admission, removal and restoration through direct Python methods. It generated no real video and established no trained cold-start quality. See the [public-safe summary](evidence/2026-11-11/FABLE-LUNARIA-PUBLIC-SAFE-SUMMARY.json).
- **Stronger-model comparison:** the [historical worksheet](requirement-worksheet-2026-11-11.md) retains the six-case results and strict-JSON failures. Small exposed samples and different settings/transports do not support a general superiority claim.
- **Implementation explanation and venues:** the [code walkthrough](current-code-walkthrough.md) maps the implementation. UMAP, SIGIR and RecSys remain venue candidates, not a confirmed submission plan; confirm the relevant current call and fit with the supervisor.
- **Research evidence:** the original A-E comparison, Experiment 1 and revised Experiment 2 are separate studies. Interface work does not alter their results. See the [evaluation protocol](evaluation-protocol.md), [Experiment 2 results](ai-reference-e2-results-2026-10-14.md) and [research provenance](academic-use.md).

The [validation guide](../tools/hosted_validation_current/README.md) and [provider implementation notes](../CLAUDE-PERSONAL-CANDIDATE.md) retain dated configurations and failures. Older profiles and counts are historical unless a newer result names the exact successor. Preserve frozen inputs and original outcomes. Finish the outstanding real execution evidence before claiming all three latest transcript requirements are complete.
