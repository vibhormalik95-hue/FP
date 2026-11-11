# Hosted synthetic validation helper

This portable helper exercises two bounded application paths: category discovery and the exact historical hunger request. It calls application endpoints directly, with explicit review stages. It is not a browser test or the frozen research benchmark.

## Offline checks

The following command passed on the cloud/Linux environment (39 tests). From the repository root, with the project's existing test dependencies available:

```sh
python -B tools/hosted_validation/run_guarded.py . test_cli_safe_evidence_offline test_driver test_cli_runner_opt_in_offline test_personal_ui_index_offline
```

The guard blocks network, subprocesses, named ctypes library loads, model/provider imports and checkpoint reads. It permits `ctypes.dlopen(None)` and is not a general operating-system sandbox. This procedure is not a passing Windows check: the current Windows run failed when the guard blocked the kernel32 import. See the [current Windows limitation](../../docs/current-progress.md#latest-validation-and-remaining-work). `test_driver.py` uses authored fake responses, not live inference. Importing the helper does not start a model.

## Portable diagnostic subset

A separate seven-test adapter/helper subset passed on Windows with Python 3.14.0 on 11 November. It uses authored envelopes and an injected callable, with the byte-identical guard above plus an additional rejection of ctypes imports. It does not load the native backend or call a provider. The six reported guard events are deliberate `sys.audit` probes, not operations. The broad 61-test Windows run remains failed.

The repository version changes only the helper path and expected driver hash. The driver hash differs from the executed original because its non-model input-manifest metadata changed. This relocated variant passed a focused cloud check; it is not a new Windows execution. From the repository root:

```sh
python -B tools/hosted_validation/run_guarded.py . test_diagnostics_portable
```

See the [public-safe result and exact hashes](../../docs/evidence/2026-11-11/WINDOWS-PORTABLE-DIAGNOSTIC-SUMMARY.json). Passing this subset does not establish native containment, whole-application behavior or live-provider acceptance.

## Inputs and configuration

`inputs/` contains the exact synthetic records, initial logical model payload/schema, source provenance and reviewer notes. Notes are not part of the model prompt. `MANIFEST.json` binds every input file; the driver pins the manifest, and both templates pin the driver. Documentation-only changes therefore require updated dependent pins, even when every model-bound byte is unchanged.

`reviewed-config.TEMPLATE.json` and `reviewed-indirect-config.TEMPLATE.json` are deliberately incomplete. Execution assertions are false and executable, work directory, token and review references are absent. Do not treat these templates as approved live configurations. The existing validation and execution gates are unchanged; no live run is part of these instructions.

The category attempt on 11 November stopped after one failed CLI invocation with no definition or Apply. The hosted hunger continuation has not run. The earlier local hunger failure remains in `inputs/02-hunger-continuation/historical-source.json`. See [current progress](../../docs/current-progress.md) for actual evidence and limits.
