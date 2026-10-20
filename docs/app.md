# Feed Control Lab

The React/FastAPI interface is a local research demonstrator. It displays item metadata; it does not distribute or play KuaiRec videos. Category IDs are opaque and are never given invented semantic labels. Run in a single process on localhost. This is not a hosted service with authentication or durable user accounts.

## Start

Install the project in `.venv` using the Python setup in [Windows and Colab instructions](windows-and-colab.md). Install Node.js 22.12 or newer, then run `npm ci` and `npm run build` in `web/` to create the local frontend. The npm lockfile fixes the JavaScript dependency resolution.

From the project folder in Windows PowerShell, run `.\.venv\Scripts\python.exe -m uvicorn feedctrl.api:app --host 127.0.0.1 --port 8000`. This does not require changing the PowerShell execution policy. The optional `.\scripts\run_app.ps1` launcher is available if scripts are already permitted. On Linux, run `bash scripts/run_app.sh`. Open <http://127.0.0.1:8000>.

Use the supplied Colab notebook for experiments and run the demonstration locally on Windows.

FastAPI's interactive API reference is at `/docs`. For frontend development only, use `npm run dev` in `web/` with uvicorn already running on port 8000. Vite proxies API requests; the production build uses same-origin requests and needs no CORS exceptions.

## Data and model configuration

The default data file is `data/processed.json`; the default model directory is `results/models/seed_42`. Before starting uvicorn, set `FEEDCTRL_DATA` and `FEEDCTRL_MODEL` to use other outputs, for example a seed-specific trained model. A missing data file activates clearly labeled deterministic fixture data. A missing model activates a clearly labeled deterministic diagnostic scorer. Neither represents an empirical LLM result. A model directory that exists but cannot load raises an error; it does not silently substitute the diagnostic scorer.

The status strip independently reports data mode, scorer and selected interpretation backend. `metadata.kind=synthetic_fixture` is recognized as fixture data. A real dataset can be explored using the diagnostic scorer, and the interface identifies both facts separately.

The default parser is the transparent rule comparator. Selecting Ollama sends real structured requests to the local Ollama server. The model defaults to the control module's model (`llama3.1:8b`); override with `FEEDCTRL_OLLAMA_MODEL`. No API key is required. Install/pull the model separately according to the project execution guide. Network/model/schema errors remain visible and preserve the previous control state. The interface never substitutes the rule parser after a failed LLM request.

## Controls and condition semantics

1. Select a pseudonymous dataset user. Each user has separate controls within the current browser session.
2. Choose A, B, C, D or E. The scorer is frozen across conditions. A applies item-only feedback; B has exactly the same order with verified signal explanations. C applies one category instruction to the frozen scores. D applies the saved profile. E combines C and D with explanations. Item feedback applies only in A and B, matching the evaluation channel contrast.
3. Enter a category instruction such as `Show me more category_1` or `Mute category_0`. Click Apply instruction or press Ctrl+Enter / Cmd+Enter in its text area. Ordinary Enter inserts a new line. The latest instruction replaces the previous command; unrelated profile preferences remain. “Less” maps to hard mute under the fixed protocol. A returned clarification preserves existing state. Review the displayed parsed operation: the measured parser does not reliably recognize all ambiguous wording.
4. The editor starts with a factual history summary from train/request-history only. These observations do not automatically become current preferences. Saved raw text is retained per session/user. Write a profile of up to 200 words with explicit preferences, such as `Show me more category_1. Mute category_0.` Saving parses and replaces the entire saved profile. The parsed preference list makes the interpretation visible; each preference can be removed. Opaque categories must be named explicitly.
5. In E, a command for the same category overwrites the profile weight rather than adding it a second time. Reset clears category controls, profile and item feedback for the selected user.
6. Use item-card plus/minus buttons for item-only feedback in A/B. Plus boosts the item by 0.25 after score normalization; minus excludes that item. Unlike category mute, it does not exclude sibling items.
7. Compare A–E to inspect the current item IDs, category exposure counts and fill. This is a within-session preview, not the benchmark's request-matched experimental output. A/B equality is checked directly in the preview. Manual feedback is not automatically inferred from a category request.

Hard mutes can shorten or empty the list; excluded items are never reinserted merely to fill ten positions. Exposure counts can sum beyond list length for multi-category items. “Show signals” only hides/shows explanations in the UI and cannot affect ranking. B/E cards use cached LLM selection of verified facts only where the exact item/history fact-set matches `results/explanations.json`. All other cards explicitly display “Verified template · no LLM”. Template fallback is not counted as an LLM experiment result. Additional active-control signals come from explicit feedback and boosts; they are not causal explanations of the neural model.

## API boundaries and state

`POST /api/session` creates a random session token. Send it in `X-Session-ID` for feed reads and mutations. State is in memory, separated by token and user, expires after 12 idle hours, and is capped at 1,024 sessions. Reloading creates a new session. Restarting the server clears every session. There is no persistence or multi-worker synchronization.

Inputs constrain category IDs, known user/item IDs, command lengths, profile words/weights and list length. The API only exposes training/request-history-derived information. Held-out items/labels are not returned or consulted for rankings. Backend failures do not mutate state. The application uses the control module's loopback-only Ollama client.

## Verification

Run `.venv/bin/python -m pytest tests/test_api.py` (Windows: `.venv/Scripts/python.exe -m pytest tests/test_api.py`). Tests cover isolation, A/B invariance, channel boundaries, hard-mute empty lists, natural-language profile parsing, clarification, operational failure visibility, reset, malformed inputs and held-out-label independence.

The separate full archive retains a Linux browser run with 17 checks using real processed data and the saved seed-42 model. Its captures and `results/audit_revision/verification/browser-acceptance.json` are not in this compact checkout. Those cached explanation labels are saved evidence, not fresh LLM generation.

To record browser acceptance separately, set `FEEDCTRL_VERIFICATION_DIR` to a new output folder, then run `node tests/browser_acceptance.cjs` with the Python environment and Playwright installed as described at the top of that script. Its unavailable-Ollama check deliberately targets loopback port 9. A 20 October Windows run in the public fixture mode passed 16 applicable checks, including the visible failure and preserved state; the real-data cached-explanation check did not apply. This is not successful fresh model inference.

The full archive also retains its release verifier and receipts. They are historical recorded checks; this compact checkout does not include `scripts/verify_release.py` or the raw inputs it expects.

Implementation references: [React createRoot](https://react.dev/reference/react-dom/client/createRoot), [FastAPI StaticFiles](https://fastapi.tiangolo.com/tutorial/static-files/), [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/).
