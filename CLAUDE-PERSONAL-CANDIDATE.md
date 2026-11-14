# Personal Claude Code integration: historical status

This record describes the personal-CLI implementation and checks recorded through 11 November 2026. Its test counts, activation checklist and unresolved results are historical, not a status report for the current checkout. For the current implementation and supported demo entry points, start with [current progress](docs/current-progress.md) and [the app guide](docs/app.md). The original evidence and limitations below are retained for traceability.

The default `_run_process` still rejects launches. `make_claude_personal_infer` accepts an explicitly selected process runner, and `create_claude_personal_app` passes that selection through its transport configuration. No automatic fallback is enabled.

One real Claude Code call completed the fictional Lunaria lifecycle through the application’s Python methods, with scripted operator reviews and no browser clicks. The early 11 November category attempt failed after one invocation; its cause was not retained. A later separate batch proposed a category but stopped at clarification before membership or Apply. The definition conflicts with the existing unknown-facts rule. That batch also recorded two hunger calls selecting described food preparation and direct Python Apply/Undo 8→5→8, not browser/HTTP acceptance or personal appetite truth. See [current progress](docs/current-progress.md) for the evidence and limits.

The latest adapter projects only allowlisted CLI status, bounded numeric usage/cost, response hashes and known failure reasons. Arbitrary error text, account fields and unknown model names are not exported. This improves evidence retention without changing model input, successful-result validation or the execution gates.

## Intended use and checks still needed

This code is intended for one person using their own unmodified, already signed-in Claude Code binary. It does not route other users' credentials. The provider must be chosen explicitly; the app never selects it by default. See Anthropic's [authentication conditions](https://code.claude.com/docs/en/legal-and-compliance#authentication-and-credential-use).

Before any future activation, verify:

- The actual installed binary, version, digest and path, and its effective policies.
- The operating-system user, signed-in account, subscription/model access, billing, quota and extra-usage settings. These have not been checked for this app.
- The requested model, effective fallback behavior, routing and reasoning effort. Requested effort may be reduced by provider or organization policy.
- The exact data and recipient authorized for the run, including context that managed hooks might add.
- Process containment, bounded output capture and timeout cleanup on the actual operating system.
- Personal-only access, a securely random operator token, loopback binding and browser behavior.
- The run's call allowance, estimated CLI threshold and any separately verified account-side limit.

Configuration flags and version strings are declarations, not proof that these checks happened. Safe mode still permits managed policy and hooks. An isolated working directory and disabled built-in tools are not an operating-system sandbox.

## Call limits and response validation

`HostedRunBudget` is a shared in-memory allowance for logical CLI invocations. An invocation consumes its allowance before launch; the allowance does not refill automatically. It does not survive restarts or enforce an account-wide dollar limit. Restarting the process starts a new run that requires authorization.

Retry-related environment settings request suppression of documented retry classes. One turn or subprocess does not prove that only one underlying request occurred. The per-invocation dollar threshold is an estimated CLI stopping point, not a hard billing cap, and resets for each invocation. Reported cost and usage do not verify account identity, quota, billing or model weights. See the [CLI reference](https://code.claude.com/docs/en/cli-reference) and [environment settings](https://code.claude.com/docs/en/env-vars).

The system prompt and schema are passed on the command line. The prompt must contain only reviewed, non-secret workflow instructions; request data goes through stdin. Provider errors are not echoed. A response must report success and the requested full model ID, then pass local schema validation. Those checks do not prove model identity at the weights level or semantic accuracy. Source evidence and user review remain necessary.

The optional `claude-personal` dependency adds jsonschema for local validation that rejects invalid output. No dependency installation or CLI run was part of this source change. Before live use, the installed CLI still needs checks for structured output, model reporting, retries, refusal/fallback, effort and containment behavior.

Category `model_revision` identifies the configuration digest, not model weights.

## Experimental Windows runner

The separate runner can be selected explicitly while the default launch function remains disabled. The earlier bounded live evidence does not establish universal Windows containment or deadline guarantees. The latest Windows offline suite reported 61 tests and 41 errors because the guard blocked `ctypes.dlopen` while importing kernel32. No model ran and no guard changed. A separate portable diagnostic subset subsequently passed seven tests on Windows with Python 3.14.0. It exercises the actual adapter and helper using authored envelopes and an injected callable, not the native backend or live provider. The broad suite remains failed. The relocated repository variant is cloud-checked, not a new Windows execution. See the [portable result](docs/evidence/2026-11-11/WINDOWS-PORTABLE-DIAGNOSTIC-SUMMARY.json).

`windows_job_native.py` assigns a Job Object at process creation, explicitly controls inherited handles, starts suspended, and uses synchronous anonymous pipes with dedicated I/O workers. It pins worker thread handles and repeatedly calls `CancelSynchronousIo` before a bounded join. `windows_job_runner.py` bounds captured output and elapsed runtime, terminates ordinary job members on completion or failure, and reports uncertain cleanup. The app rejects subsequent calls in that process after uncertain cleanup.

A Windows Job Object is not a security sandbox. Operating-system-brokered or alternate-parent processes may escape normal job inheritance. Synchronous Win32 startup calls are not proven to finish before the deadline. The code checks the deadline before resuming the process, but cannot enforce a hard bound during a blocked OS call.

If this optional runner is pursued later, first review containment and cleanup for the actual Windows environment. Use only harmless Python checks, never Claude, credentials or project data. `scripts/windows_runner_smoke.py` contains three scenarios: echo a small stdin token, detect and terminate a short-lived sleeping child left by its parent, and enforce the output bound. Startup-failure cleanup needs a separate Windows check. These test ordinary job behavior, not adversarial containment.

After a separately authorized transfer and review, the script can be run from the source root with `C:\Python314\python.exe -I -S scripts\windows_runner_smoke.py`. It uses only `COMP_RUNNER_OK` and short Python snippets, including the equivalent of `C:\Python314\python.exe -c` for the echo check. Verify exact output bytes, exit status and no active job members. This document does not require a laptop demonstration or authorize running the checks now.

## Output modes and recorded compatibility checks

A separate source-free check supplied by the project owner used `--json-schema`, one maximum turn and no built-in tools. It returned exit 0, a success wrapper and `{"ok":true}`, but reported `num_turns=2` and `stop_reason=tool_use`.

Receipt SHA-256: `83c09bb776e28924fe333f8ed5a6a4853188661622d82df5cb48216c08def205`.

The adapter rejects this response under its one-turn requirement. It has not been changed to allow two turns. The check does not verify app integration, recommendations, research accuracy, billing or HTTP-attempt count.

The code requires an explicit choice of `schema_tool` or `plain_json` and never tries one automatically after the other. In `plain_json`, the original response schema is appended to the system instruction. The CLI result must be one JSON object, decoded with duplicate-key and nonfinite-value checks and validated against the same local schema. Prose, Markdown, malformed or invalid JSON, two-turn responses and a reported non-final stop reason all fail without repair or retry.

Request hashes describe canonical logical CLI requests, not underlying HTTP bytes. The existing source-evidence, session, review and Apply checks remain unchanged. Earlier simple one-turn probes did not test this exact schema-bearing prompt or application path. Neither mode is activated by this code change.

A separate harmless plain-JSON check reported by the owner returned one reported turn with `end_turn`; its exact prompt bytes were verified.

Receipt SHA-256: `584caa325f927e937349227357b1971a5e72654acf09296c89ce8b33b0f0c90f`.

That check also did not execute the project or verify app integration.

## Browser access and operator token

The personal app requires an externally supplied operator token and an explicit canonical HTTP loopback origin with a non-default port, such as `http://127.0.0.1:8000`. A future launcher must bind directly to that address, disable proxy-header trust and protect the token. These checks do not isolate operating-system users.

Only the index and exact built assets are served without the token. Every API route requires the operator header. Remote peers, mismatched Host or Origin, forwarded headers and cross-site API requests are rejected.

The personal index enables a token-entry screen. After a successful check, the UI holds the token only in JavaScript memory and adds it to same-origin API request headers. This code does not put it in URLs, browser storage, application logs or model requests. The form requests autocomplete off. Browser extensions, password managers, debuggers, compromised same-origin scripts and other local processes remain outside this protection.

Lock clears the UI's token references, aborts outstanding fetches and starts a new UI session on the next unlock. Refresh also returns to token entry. Resetting the research user leaves the operator session unlocked.

Lock cannot revoke a copied token, immediately erase strings from browser memory, delete server sessions or guarantee that already-started backend work stops. Supply the token securely outside the app; these files do not generate or store it. The normal non-personal app has no token-entry requirement and retains its existing session header.

The token flow has offline tests, but browser verification is still outstanding. The default CLI launcher remains disabled; the explicit runner path has the bounded headless evidence described above.
