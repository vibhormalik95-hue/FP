# Feed Control Lab app guide

Feed Control Lab is a React/FastAPI research app for changing a recommendation feed through explicit controls. It displays item metadata, not playable KuaiRec videos. The original category IDs stay unchanged; the app does not invent meanings for them.

The recent work adds manual category selection, model-proposed categories and indirect language requests alongside the original A–E comparison. [Current progress](current-progress.md) separates observed examples from untested behavior.

**Current availability:** the default personal Claude launch is disabled; an explicitly selected runner has bounded headless evidence. Local models and the local recommender are not authorized for the current personal configuration. The local startup instructions later on this page are historical reproduction instructions. See [hosted configuration](hosted-only-configuration.md) and [personal Claude status](../CLAUDE-PERSONAL-CANDIDATE.md).

## The recent controls

In **Reviewed topic feed**, the **Experimental semantic groups** panel provides the following paths when their required provider is configured:

- **Manual: exact original category baseline.** Choose the existing category ID and the action yourself. This provides a no-LLM comparison.
- **Review definition, then classify all supplied items.** Ask for a category that is not already represented by the existing labels. A validated primary with competing interpretations can be explicitly selected unchanged for definition review, or cancelled, without another model call. Nothing is selected by default. Review its proposed definition, approve classification, then inspect the membership decisions and separate evidence check before applying it. See [category clarification resolution](category-clarification-resolution.md) for the retained evidence and session safeguards.
- **Propose a new category definition and membership.** This combines the proposal into one call. It is a separate path, not the same procedure as definition review followed by classification and evidence checking.
- **Indirect intent.** Describe the change without having to name a category. The configured model interprets the action and proposes related items from the supplied text. Review the proposed meaning and members before applying it.

A group covers the displayed candidate items, not an unseen catalogue. A new group does not alter the original dataset category mapping or create a new video. Review must consider whether each quoted passage actually supports membership. Exact quotes alone do not prove the model understood the request.

If the model cannot resolve the request, the app can show its competing interpretations. These are unverified suggestions, not selected preferences. The user can rewrite the request or explicitly confirm a concrete, observable target. Confirming a target changes who supplies the interpretation; it does not demonstrate that the model understood the original indirect wording.

A proposal does not change the feed until it is reviewed and applied. Clear and undo also require review of the displayed change. Session, source-version and expiry checks prevent applying an obsolete proposal. The dated [walkthrough](../deliverables/2026-11-05-final-demo/WALKTHROUGH.md) records specific examples; it is not evidence that automatic Claude integration works today.

The separate [fictional item draft panel](synthetic-item-drafts.md) creates metadata only. The latest source connects it to the configured hosted provider and shared call allowance. One real Claude Code Lunaria run completed the lifecycle through the application’s Python methods, without HTTP or browser interaction. The UI itself remains unverified live; see [current progress](current-progress.md). Without a configured adapter or permission to use a local model, generation remains disabled.

## The original A–E comparison

These controls retain the earlier experiment's meaning. They are separate from the new semantic-group workflow.

1. Select a pseudonymous dataset user. Controls are separate for each user within the browser session.
2. Choose A, B, C, D or E. The scorer is fixed across conditions. A applies item-only feedback. B preserves A's order and adds verified signal explanations. C applies one category instruction. D applies the saved profile. E combines C and D with explanations. Item feedback affects only A and B.
3. Enter an explicit category instruction such as `Show me more category_1` or `Mute category_0`. Click Apply instruction or press Ctrl+Enter / Cmd+Enter in its text area; Enter alone adds a new line. The latest instruction replaces the previous one but keeps unrelated profile preferences. In this earlier protocol, “less” means hard mute. Clarification leaves the existing state unchanged. Check the displayed operation because ambiguous language is not always interpreted correctly.
4. The editor starts with a factual summary of training/request history. That history is not automatically treated as a current preference. Write a profile of up to 200 words, such as `Show me more category_1. Mute category_0.` Saving parses and replaces the whole profile. The raw text is kept for the session/user, and individual parsed preferences can be removed. Name opaque category IDs explicitly.
5. In E, a command for a category replaces that category's profile weight rather than adding it twice. Reset clears category controls, profile and item feedback for the selected user.
6. The item-card plus/minus buttons provide item-only feedback in A/B. Plus adds 0.25 after score normalization; minus excludes only that item, not other items in its category.
7. Compare A–E to inspect item IDs, exposure counts and list fill. This is a preview of the current session, not a new benchmark result. The app checks A/B equality directly. It does not infer item feedback from a category request.

Hard mutes can shorten or empty the list. Excluded items are not put back to fill ten positions. Multi-category items can make exposure counts sum to more than the list length.

“Show signals” changes only the display. B/E cards use cached LLM selections of verified facts when the exact item/history fact set matches `results/explanations.json`. Other cards display “Verified template · no LLM”. Templates do not count as LLM results. Feedback and boost signals describe explicit controls, not causal explanations of the neural model.

## Session and API behavior

`POST /api/session` creates a random token, sent in `X-Session-ID` for feed reads and changes. State is separated by token and user, expires after 12 idle hours, and is limited to 1,024 sessions. Reloading creates a new session. Restarting the server clears all sessions. There is no persistence or synchronization across server workers.

The API checks category, user and item IDs, instruction lengths, profile words/weights and list length. It exposes only training/request-history information. Held-out items and labels are not returned or used for rankings. Backend errors leave preferences unchanged. The original local model client accepts only loopback connections.

## Historical local setup

This section describes the earlier local research app, not the current explicit-runner hosted configuration. Run it only with separate authorization for local execution and the required inputs. It is a single-process localhost app, not a hosted service with durable accounts or authentication.

Install the project in `.venv` using the [Windows and Colab guide](windows-and-colab.md). With Node.js 22.12 or newer, run `npm ci` and `npm run build` in `web/`. The lockfile fixes JavaScript dependency resolution.

From the project folder in Windows PowerShell, run `.\.venv\Scripts\python.exe -m uvicorn feedctrl.api:app --host 127.0.0.1 --port 8000`. No PowerShell execution-policy change is needed. The optional `.\scripts\run_app.ps1` launcher requires scripts to be permitted already. On Linux, use `bash scripts/run_app.sh`. The app opens at <http://127.0.0.1:8000>.

The supplied Colab notebook is for experiments; the earlier demonstration ran locally on Windows. FastAPI's interactive API reference is at `/docs`. For frontend development, `npm run dev` in `web/` uses Vite's API proxy with uvicorn on port 8000. The built app uses same-origin requests and needs no CORS exceptions.

### Historical data and model setup

The defaults are `data/processed.json` and `results/models/seed_42`. Set `FEEDCTRL_DATA` and `FEEDCTRL_MODEL` before starting uvicorn to use different outputs. Missing data activates labeled deterministic fixture data. A missing model activates a labeled diagnostic scorer. Neither is an empirical LLM result. An existing model directory that fails to load produces an error instead of switching scorers.

The status strip reports data mode, scorer and interpretation backend separately. `metadata.kind=synthetic_fixture` identifies fixture data. Real data can also be shown with the diagnostic scorer, with both facts visible.

The original default parser is the rule comparator. Ollama sends structured requests to the local server using `llama3.1:8b`, unless `FEEDCTRL_OLLAMA_MODEL` overrides it. It requires a separately installed model but no API key. Network, model and schema errors remain visible and preserve the previous controls; the app does not substitute a rule result after an LLM error.

## Recorded checks and reproduction

The command `.venv/bin/python -m pytest tests/test_api.py` (Windows: `.venv/Scripts/python.exe -m pytest tests/test_api.py`) covers session isolation, A/B equality, control boundaries, empty hard-mute results, profile parsing, clarification, visible errors, reset, malformed inputs and held-out-label independence. It is a software check, not a fresh model evaluation.

The separate full archive retains a Linux browser run with 17 checks using processed data and the saved seed-42 model. Its captures and `results/audit_revision/verification/browser-acceptance.json` are absent from this compact checkout. Cached explanation labels in those records were not freshly generated.

For a separately authorized browser check, set `FEEDCTRL_VERIFICATION_DIR` to a new folder and run `node tests/browser_acceptance.cjs` with Python and Playwright installed as described in that script. Its unavailable-Ollama check uses loopback port 9. A 20 October Windows fixture run passed 16 applicable checks, including visible failure with preserved state. The real-data cached-explanation check did not apply. This did not establish fresh model inference.

The full archive retains its historical release verifier and receipts. This compact checkout lacks `scripts/verify_release.py` and the inputs it expects.

Implementation references: [React createRoot](https://react.dev/reference/react-dom/client/createRoot), [FastAPI StaticFiles](https://fastapi.tiangolo.com/tutorial/static-files/), [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/).
