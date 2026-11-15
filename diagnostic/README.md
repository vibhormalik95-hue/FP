# Current personal CLI binding: isolated review candidate

This candidate extends the verified `8a33946147dafb2b4d57c95c4b155a9bd6435a01` base. It supports one explicitly bounded existing-label call, one combined caption-and-label call, or two bounded calls for an existing-item indirect request: interpretation, then evidence grounding. Each response still passes the unchanged adapter's single-turn and refusal gates. No new-category invocation is supplied. The offline tests are described below. A separate [15 November Windows direct-app check](../docs/evidence/2026-11-15-windows-combined/README.md) completed one real combined request, Preview, AI review, Apply and Undo with a task-local caller. It was not a browser test or a test of the example caller below.

The published adapter defaults to `safe_mode`; the historical `tools/hosted_validation_current/driver.py` and research evidence remain unchanged. This package itself starts no listener, model, hook, or provider on import.

## Identity and trust

`source-pins.json` identifies 46 runtime inputs: 39 `feedctrl` files, three built UI assets, three category/tag scenario input files and `pyproject.toml`. It records the base commit as provenance; its application hashes identify this candidate's optional wrapper and scoped-preview seams. It excludes README, research documents and `CURRENT-SOURCE-SHA256.txt`, so ordinary documentation edits do not change runtime identity. The qualifier checks every listed file, its transport pins, and rejects extra Python, bytecode and binary-extension files under `feedctrl`. It does not attest untracked files elsewhere, third-party packages, externally supplied inputs, managed provider context, or same-user time-of-check/time-of-use races.

The external caller must verify the SHA-256 of `diagnostic/bootstrap.py`, `diagnostic/app_binding.py` and any helper script independently before importing or running them. Bootstrap pins the qualifier; the qualifier pins the separate runtime inventory and operational modules. No manifest hashes itself. Regenerate and independently review these identities after any runtime change.

The transport and native runner originate in the previously reviewed Windows run. The native module is the Git LF blob; the successful worktree used CRLF. The source tests described here used fake backends; the separate live check is linked above. The reviewed-hooks context qualifier supports the specific previously inspected Caveman plugin layout, not arbitrary machines or hook implementations. It neither disables hooks nor establishes which hook shell or hidden managed context a provider uses. Do not treat a successful preflight as permission or as proof of provider identity.

## Setup and offline checks

On a reviewed Windows machine, obtain this source from a verified source package, review its patch and dependencies, and use a dedicated virtual environment. The project declares Python >=3.11 and its runtime dependencies in `pyproject.toml`; the personal adapter currently requires the separately reviewed Claude Code 2.1.321. No account, credential or plugin is distributed here. Creating/installing the environment is a separate operator action, not part of the recorded tests:

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
$env:COMP_OFFLINE_USE_STANDARD_SITE = '1'
.\.venv\Scripts\python.exe -I -B -u .\test_two_stage_app_offline.py
.\.venv\Scripts\python.exe -I -B -u .\test_preview_lifetime_offline.py
.\.venv\Scripts\python.exe -I -S -B -u .\test_two_stage_guards_offline.py
.\.venv\Scripts\python.exe -I -S -B -u .\test_personal_source_mismatch_offline.py
.\.venv\Scripts\python.exe -I -S -B -u .\test_context_builder_offline.py
```

The standard-venv route above has not been executed or independently qualified here. Recorded app tests used a separately reviewed local curated runtime; the context/marker and source tests used isolated standard-library Python. Review the virtual environment and its package provenance before use; Python isolation alone does not audit installed packages.

## Prepare a private context, then preflight

Review the absolute paths to the CLI executable, home, plugin cache directory and Node binary, the active settings, plugin files, commands, executable search path, managed policy, permitted data and possible costs. Do not copy private settings or context into the repository. After verifying the builder's identity, create a new context file outside the repository:

```powershell
.\.venv\Scripts\python.exe -I -B .\diagnostic\build_context.py --cli <ABS_CLI> --home <ABS_HOME> --plugin <ABS_PLUGIN> --node <ABS_NODE> --output <NEW_ABS_PRIVATE_CONTEXT_JSON> --tokens 16384
```

Replace placeholders with quoted absolute paths. The helper reads the named local files and writes only their hashes, hook-command hashes, a child-environment digest and the requested token limit; it prints the context SHA-256. It uses exclusive creation and will not overwrite a context. A generated hash is not a review, authorization or attestation of hidden managed instructions. Record and independently review the context and the builder identity. A separate action review is necessary for any external request.

From the **same approved parent environment** as any later authorized execution, use a new Python process. After independently verifying bootstrap, insert this source root into `sys.path`, import `diagnostic.bootstrap`, and call:

```python
bootstrap.preflight(context_file=ABS_CONTEXT, context_sha256=CONTEXT_SHA256,
                    cli=ABS_CLI, workdir=EMPTY_ABS_WORKDIR, home=ABS_HOME)
```

All five values are explicit; no home or CLI path is hard-coded. The working directory must be empty and instruction-free. The returned `qualified` result is inert and expressly says `authorization_established=False`, `managed_context_verified=False`, and `live_calls=0`. Stop on mismatch. Do not change environment or hooks to force a pass. Managed context and hook-host resolution remain operator review matters.

## Direct-app binding after separate approval

The implementation is a Python app-construction API, not a packaged turnkey web server. No public launcher or browser workflow is claimed. A reviewed caller supplies an operator token, canonical loopback origin, model and effort, per-call CLI estimated threshold, explicit output mode and CLI version, a fresh marker, and the six distinct existing authorization/review flags. It must also give exact SHA-256 pins for the absolute data and caption-sidecar files in `reviewed_files`. The app verifies those inputs before construction and before each invocation. No private path or context value is included in this source.

For the two-call indirect mode, independently review the exact request, the candidate IDs and the canonical catalogue digest. Calculate the latter in a **separate Python process** from the reviewed data and sidecar, using the current source's `load_topic_index`, `scoped_index`, `_catalogue` and `diagnostic.flow_guard._digest`. Do not import `feedctrl` in the later binding process before binding: the bootstrap intentionally rejects preloaded application modules. `max_calls=2` requires the first prompt/schema to be the existing action interpreter, validates its returned action against that exact request, then permits only the existing grounding prompt/schema, that request and validated action, and the reviewed catalogue digest. A refusal, invalid first response or runner error latches the flow closed. A clarification ends the flow without grounding. `max_calls=1` retains the original one-call option.

For the separate combined route, supply `flow_mode="combined-v1"`, `max_calls=1`, the exact reviewed `request`, `catalogue_sha256`, `source_sha256` of the reviewed sidecar, and reviewed `candidate_ids`. The guarded scope binds the current session, user, revision and preview nonce internally. Its deadline is the supplied timeout from scope claim; reservation validates the scope while holding the application state lock and releases that lock before provider execution. Closure is irreversible and cannot replenish its marker or budget. The synchronous handler does not guarantee detection of a disconnected browser. The combined source tests used authored responses and a fake backend; the separate live check is linked above.

In the fresh approved process, after preflight and explicit review, call `diagnostic.app_binding.construct` with `enable_live=True`, the five context values as `context`, `marker=NEW_ABS_MARKER`, `reviewed_files={ABS_DATA: DATA_SHA256, ABS_SIDECAR: SIDECAR_SHA256}`, `data_path=ABS_DATA`, `semantic_path=ABS_SIDECAR`, `fixture=False`, and all explicit app, model, budget, output, version and approval arguments listed in its signature. For an indirect request also pass `max_calls=2`, `request=REVIEWED_REQUEST` and `catalogue_sha256=REVIEWED_CATALOGUE_SHA256`. The caller invokes the app's existing semantic Preview route, reviews the actual proposal, evidence and memberships, and separately reviews Apply and Undo. The wrapper does not silently approve those steps.

For example, in the separate reviewed process below, replace the absolute paths and candidate IDs before running with the dedicated interpreter's `-I -B` flags. It reads only the supplied local data and sidecar and prints their hashes and the canonical catalogue hash; it makes no model request. Verify bootstrap independently before importing it.

```python
import hashlib, json, sys
from pathlib import Path
ROOT = Path(r"ABS_SOURCE_ROOT")
if hashlib.sha256((ROOT / "diagnostic/bootstrap.py").read_bytes()).hexdigest() != "REVIEWED_BOOTSTRAP_SHA256":
    raise RuntimeError("bootstrap mismatch")
sys.path.insert(0, str(ROOT))
from diagnostic import bootstrap
bootstrap._load()
from feedctrl.semantic_controls import load_topic_index
from feedctrl.semantic_review import scoped_index
from feedctrl.indirect_grounding import _catalogue
from diagnostic.flow_guard import _digest
DATA = Path(r"ABS_DATA_JSON")
SIDECAR = Path(r"ABS_CAPTIONS_CSV")
ids = [1, 2]  # replace with the IDs to be reviewed
items = json.loads(DATA.read_bytes())["items"]
index = load_topic_index(SIDECAR, {int(item["item_id"]) for item in items})
print("data_sha256", hashlib.sha256(DATA.read_bytes()).hexdigest())
print("sidecar_sha256", hashlib.sha256(SIDECAR.read_bytes()).hexdigest())
print("catalogue_sha256", _digest(_catalogue(scoped_index(index, ids))))
```

Review the IDs, captions, hashes and intended disclosure independently. Close this process before starting the binding process so no `feedctrl` module is preloaded there.

The following direct-route outline is executable after replacing **all** placeholders and placing it in a separately reviewed caller script. Run it from a fresh approved process with the reviewed virtual-environment interpreter using `-I -B`; it starts no HTTP server. The placeholder catalogue digest must be calculated in the separate process described above, and the file hashes and provider disclosure must be reviewed before typing `AUTHORIZE`. This outline has not been executed against a provider.

```python
import hashlib, json, secrets, sys
from pathlib import Path
ROOT = Path(r"ABS_SOURCE_ROOT")
# Compare these values to independently distributed/reviewed hashes first.
for name, expected in {
    "diagnostic/bootstrap.py": "REVIEWED_BOOTSTRAP_SHA256",
    "diagnostic/app_binding.py": "REVIEWED_APP_BINDING_SHA256",
}.items():
    if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != expected:
        raise RuntimeError("source identity mismatch")
sys.path.insert(0, str(ROOT))
from diagnostic import bootstrap, app_binding
context = {"context_file": Path(r"ABS_CONTEXT"), "context_sha256": "REVIEWED_CONTEXT_SHA256",
           "cli": Path(r"ABS_CLI"), "workdir": Path(r"EMPTY_ABS_WORKDIR"), "home": Path(r"ABS_HOME")}
data = Path(r"ABS_DATA_JSON")
sidecar = Path(r"ABS_CAPTIONS_CSV")
files = {str(data): "REVIEWED_DATA_SHA256", str(sidecar): "REVIEWED_SIDECAR_SHA256"}
request = "REVIEWED_REQUEST"
candidate_ids = [1, 2]  # replace with the independently reviewed IDs in the supplied fixture
catalogue_sha = "REVIEWED_CATALOGUE_SHA256"
print(bootstrap.preflight(**context))
if input("After reviewing the exact disclosure, context and spend, type AUTHORIZE: ") != "AUTHORIZE":
    raise SystemExit("Not authorized")
approvals = {key: True for key in app_binding._APPROVALS}
app, observations = app_binding.construct(
    enable_live=True, context=context, marker=Path(r"NEW_ABS_MARKER"),
    operator_token=secrets.token_urlsafe(32), allowed_origin="http://127.0.0.1:8000",
    model="REVIEWED_FULL_MODEL_ID", effort="max", estimated_per_invocation_usd=5.0,
    output_mode="plain_json", reviewed_cli_version="2.1.321", approvals=approvals,
    reviewed_files=files, max_calls=2, request=request, catalogue_sha256=catalogue_sha,
    data_path=data, semantic_path=sidecar, fixture=False)
from feedctrl.semantic_review import SemanticPreview, SemanticApply, SemanticHistory
routes = {r.path: r.endpoint for r in app.routes if hasattr(r, "endpoint")}
session = app.state.demo.create_session()
preview = routes["/api/semantic/preview"](
    SemanticPreview(user_id=1, text=request, label="Reviewed request", candidate_ids=candidate_ids,
                    backend="configured_model", action_source="model"), x_session_id=session)
print(json.dumps(preview, ensure_ascii=False, indent=2))
if not preview.get("ready") or input("Review proposal and evidence; type APPLY: ") != "APPLY":
    raise SystemExit("Not applied")
print(routes["/api/semantic/apply"](SemanticApply(user_id=1, plan_id=preview["plan_id"]), x_session_id=session))
undo = routes["/api/semantic/history/preview"](SemanticHistory(user_id=1, action="undo"), x_session_id=session)
print(json.dumps(undo, ensure_ascii=False, indent=2))
if undo.get("ready") and input("Review undo; type UNDO: ") == "UNDO":
    print(routes["/api/semantic/apply"](SemanticApply(user_id=1, plan_id=undo["plan_id"]), x_session_id=session))
```

This example gives user 1 and IDs as placeholders, prints potentially sensitive proposal data locally, and must be adapted to the independently reviewed fixture. Treat any exception, refusal or uncertain cleanup as a stop; do not rerun or replace the marker automatically. The app's source and the caller, dependencies, inputs and destination must all be reviewed; booleans are assertions, not evidence of review.

For a guarded two-call indirect preview, the route claims one opaque session/user/nonce scope under the existing application state lock. Each call validates revision and nonce and reserves its attempt while holding that lock; the reservation is the dispatch linearization point. The application lock is released before any provider execution. A supersession after reservation cannot revoke that already-reserved call, but the existing application state checks still prevent an obsolete preview from being applied. The route closes the scope on every exit after it is claimed, including early validation, clarification, exception and cancellation; a closed scope cannot be reopened or refill its allowance. One-call routes and providers that do not opt into this protocol retain their existing behavior.

Synchronous route handlers do not guarantee detection of a browser disconnect while provider work is running. A running owned call must finish or follow its existing bounded cleanup; disconnecting a page is not proof that it stopped. Never infer a fresh execution authority from a page reload or automatically reset a marker.

Each dispatch checks context and input identity again. The first call exclusively creates and fsyncs the marker; the second exclusively creates and fsyncs `<marker>.2`. An existing marker, error, refusal or uncertain cleanup prevents reuse; the wrapper adds no retry or fallback. File fsync is not a guarantee of directory-entry survival in every crash. The shared process budget is one or two calls, and each CLI cost threshold is only an estimate, not a guaranteed bill or independently verified token cap.

## Recorded test boundary

Fake fixtures and authored exclusion replies for “I'm not hungry, remove all the stuff that makes me hungry.” exercised two-stage direct app Preview, AI review callbacks, Apply and exact Undo, first/second refusal, invalid first output, fake cleanup uncertainty, input/context drift, per-call marker exclusivity and budget exhaustion. The preview-lifetime tests covered supersession, reset, undo, manual and overlapping previews, early exits, exceptions and cancellation using bounded threads and fake responses. The separate source-identity test changed documentation without changing identity, then rejected modified app source, fixture and an unexpected Python module. These are not model-quality evidence, native process containment, a browser or HTTP/ASGI test, or portable live qualification. The earlier run's separate task-local results remain unchanged.
