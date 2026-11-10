# Unactivated personal CLI candidate

This is a source-only candidate. No authenticated app call, project-source transfer,
provider activation, semantic validation, live browser test, or research result has
been performed. Authored mock responses test plumbing only. The existing OpenAI
transport and its fixed spending guard are unchanged and cannot authorize this route.
The fixed recommender and frozen experiments are unchanged; hosted-only mode still
refuses a local recommender checkpoint. A compatible fixed scorer remains unresolved.

The actual process-launch seam unconditionally fails closed. No Boolean gate can enable it. An experimental Windows process-containment implementation exists separately, but is not wired into the app and requires verification before any real call. The mocked tests replace that seam.

The candidate is solely for one person using their own, unmodified, already signed-in
Claude Code binary. It is not a service that routes or intermediates other users'
credentials. See Anthropic's [authentication conditions](https://code.claude.com/docs/en/legal-and-compliance#authentication-and-credential-use).
Explicitly choosing a provider is required; nothing in the app selects this one by default.

Before any activation, independently review the executable and its installed version,
account and billing/extra-usage configuration, model entitlement, actual data being
transmitted, managed policies and hooks, model fallback behavior, working directory,
and recipient/destination. The version parameter and authorization booleans, including the containment review, are operator
assertions, not verification, and must not be asserted by an unattended default. Managed
policy still applies in safe mode, and managed hooks can run or add context. An isolated
working directory and no built-in tools do not provide OS-level confinement. An experimental Windows Job Object runner is present separately, but it is not wired to the disabled app launch seam and has not been run on Windows. Do not use it
until a supported containment and cleanup approach has been reviewed for the actual
Windows environment. No source is transferred or runtime inspected by this candidate.

The explicit `HostedRunBudget` is a shared in-memory allowance for logical CLI invocations,
consumed before launch and never automatically replenished. It is not durable across
process restarts, an account-wide limit, proof of one HTTP/model attempt, or a charge cap.
A restarted process is a new run needing fresh authorization. Retry-related environment
settings request suppression of documented retry classes; one turn or one subprocess is
not proof of one underlying request. The per-invocation dollar threshold is an estimated
CLI stop setting, not a hard cap: estimates can differ from billing and spend may exceed
it. It resets for each invocation. CLI cost and usage are reported estimates/metadata,
not proof of billing, account identity, quota or model weights. See the [CLI reference](https://code.claude.com/docs/en/cli-reference) and [environment settings](https://code.claude.com/docs/en/env-vars).

The adapter sets a system prompt on the process command line. It must contain only the
reviewed, non-secret workflow instruction; request data are sent by stdin. The schema is
also passed on the command line. Provider errors are not echoed. Responses must report a
successful envelope, the requested full model ID, and a locally schema-valid structured
object. Model reports are not weight attestation. Exact source evidence and user review
remain required by the app; a valid structured response is not semantic accuracy.

The separate optional dependency `claude-personal` adds jsonschema for fail-closed local
validation. No dependency was installed or CLI run as part of this candidate. The developer
must verify the whole source and the installed CLI's actual structured-output, model-report,
retry, refusal/model fallback, effort and containment behavior before any allowed live use. Requested effort may be lowered by provider or organization policy and is not an attestation of effective effort.

The app adds a loopback-peer and caller-supplied operator-token boundary as defense in depth. A future launcher must bind to loopback and protect the token. This does not establish OS-user isolation and has not been browser-tested. Category model_revision is the configuration digest, not a model-weight hash.

## Pending activation review manifest (all unverified)

- Exact unmodified binary version and digest, installed path, and effective policy.
- Operating-system user and actual signed-in account; subscription entitlement and
  billing, quota and extra-usage settings. No account was checked for this candidate.
- Model ID, effective fallback chain and provider routing; verified absence of an
  unapproved fallback, including managed policy. Requested effort is not proof of
  effective effort.
- Specific data and recipients authorized for each run, plus managed-hook behavior.
- Reviewed Windows process-tree containment, bounded capture and timeout cleanup.
- Personal-only access, securely random operator token, loopback binding and browser
  verification of the implemented memory-only personal token handoff.
- Run-specific logical invocation allowance and separately chosen estimated CLI
  threshold, with any account-side limit independently established if required.

Any eventual decision to activate must bind to reviewed exact values rather than
claiming the placeholder assertions in this candidate prove those facts.

## Experimental Windows runner

`windows_job_native.py` uses creation-time Job Object assignment, explicit inherited
handles, suspended startup, synchronous anonymous pipes with dedicated I/O workers,
pinned worker thread handles and repeated `CancelSynchronousIo` before bounded join.
`windows_job_runner.py` bounds output and elapsed runtime, terminates ordinary job
members on completion or failure, and reports cleanup uncertainty. A Windows Job
Object is not a security sandbox: operating-system-brokered or alternate-parent
processes can escape ordinary job inheritance. Synchronous Win32 startup calls are not
proven to finish before the deadline; the code checks the deadline before resuming the
process but cannot guarantee a hard bound during a blocked OS call. The app permanently
blocks subsequent calls in the same process after uncertain cleanup. The actual launch
seam remains disabled. Windows verification has not run because the diagnostic has not been materialized successfully.

The smallest useful Windows smoke check after a legitimate transfer is a harmless,
source-free local Python program, never Claude: run the experimental runner once with
`C:\Python314\python.exe -c` to echo a tiny stdin token and verify exact bytes, exit
status and no active job members. Then run one bounded scenario where the Python parent
starts a short-lived sleeping Python child and exits, verifying that the runner reports
the lingering child and terminates it. The bundled scripts/windows_runner_smoke.py supplies those two local-only scenarios
and a third output-bound scenario. Startup-failure cleanup still needs a separate
Windows check. These are checks for normal job behavior, not proof of adversarial containment.
They must be performed on the actual laptop only after reviewed source is legitimately
available there. Do not test credentials, project data, or live model calls in this smoke.

The browser token handoff is implemented and covered by offline tests, but has not
received browser acceptance. The structured-output combination produced two reported
turns in a separate compatibility check and is rejected by the one-turn rule; do not
silently increase the limit. The app is not ready for live browser or provider use.

After legitimate transfer and review, from the source root on the laptop run `C:\Python314\python.exe -I -S scripts\windows_runner_smoke.py`. It uses only the literal stdin token `COMP_RUNNER_OK` and short Python snippets; it does not invoke Claude. The Windows smoke test has not run because the diagnostic has not been materialized successfully.

## Explicit output modes and observed compatibility

A separate source-free live compatibility check supplied by the project owner used
`--json-schema`, one maximum turn and no built-in tools. It returned exit 0, a success
wrapper and `{"ok":true}`, but reported `num_turns=2` and `stop_reason=tool_use`.
Receipt SHA-256: `83c09bb776e28924fe333f8ed5a6a4853188661622d82df5cb48216c08def205`.
The adapter correctly rejects that result under its existing one-turn requirement.
It has not been changed to accept two turns, and this result does not verify app
integration, recommendation output, research accuracy, billing or HTTP-attempt count.

The source now requires an explicit selection of `schema_tool` or `plain_json`; neither
mode is automatically tried after the other. In `plain_json`, the original response
schema is appended to the system instruction, the CLI's result text must be one JSON
object, and a strict duplicate-key/nonfinite-aware decoder plus the same local schema
validator checks it. Prose, Markdown, malformed JSON, invalid objects and two-turn
results fail without repair or retry; a reported non-final stop reason also fails.
Request hashes identify canonical CLI logical requests, not underlying HTTP wire bytes.
Existing downstream evidence, session, review
and apply rules remain unchanged. The previous simple one-turn CLI probes did not test
this exact schema-bearing prompt or application path; a separate permitted validation
is required. No output mode is activated by this source change.

## Personal browser token boundary

The personal app requires a separately supplied operator token and an explicit canonical
HTTP loopback origin with a non-default port, for example `http://127.0.0.1:8000`. The
server must bind directly to that address and disable proxy-header trust; this is not
an OS-user isolation mechanism. The app serves only its index and exact built assets
without the token. Every API route requires the operator header; remote peers, mismatched
Host or Origin, forwarded headers and cross-site API requests are rejected.

The personal index marks the UI to show a token entry form. A successful check holds
the token only in JavaScript memory and adds it as a header to same-origin API requests.
It is not placed in URLs, browser storage, application logs or model request bodies by
this code. The form requests autocomplete off, but browser extensions, password
managers, debuggers, a compromised same-origin script or other local processes are
outside this control. Lock clears the UI's references, aborts outstanding fetches and
starts a fresh UI session on the next unlock; a browser refresh also returns to the
token entry screen. Ordinary research-user reset leaves the operator session unlocked.

Lock does not revoke a copied server-configured token, erase strings from browser
memory immediately, delete server sessions, or guarantee already-started backend work
stops. The token should be supplied securely from outside this app, not generated or
stored by these files. The candidate has no launcher, and actual browser acceptance and
the disabled CLI launch remain unverified. The normal non-personal app has no entry
gate and continues to use its existing session header.

A separate harmless plain-JSON CLI compatibility check, reported by the project owner,
returned one reported turn with `end_turn`; its exact prompt bytes were verified.
Receipt SHA-256: `584caa325f927e937349227357b1971a5e72654acf09296c89ce8b33b0f0c90f`.
It did not execute the project and is not evidence of app integration or acceptance.
