# Windows engineering verification — 13 October 2026

Executed by the coding agent on the user's AI_work Windows computer against public repository base `e3070020271baaf64a3e5b1fd0fe6d91f280261b`. This is a current, bounded engineering check, not student activity hours, a full experimental replay or formal E2 execution. See [methods and provenance](academic-use.md).

## Checks and results

- Existing synthetic checks: **48 passed, 1 deselected**, 2 deprecation warnings, in 2.77 seconds. Command: `python -m pytest -q tests/test_data.py tests/test_api.py tests/test_output_safety.py tests/test_controls.py -k "not benchmark_splits" --basetemp <fresh-task-local-directory> -p no:cacheprovider`.
- The deselected `test_benchmark_splits` reads omitted archive files. No E2 test files, bank, labels or predictions were inspected or run.
- An earlier sandbox attempt returned 18 passes and 15 setup errors because its temporary directory was inaccessible. The successful run used approved execution and a fresh task-local temporary directory. These setup errors were not silently counted as passes.
- The standalone `scripts/verify_frozen_e1.py` verified **288/288 matching E1 hashes**, zero missing and zero mismatched, in the previously extracted recovered archive. Manifest SHA-256: `80ff8138e6ad7abd3e8482bc59fcaa044dfe7f7ca507edabdd569d217635e595`. The verifier reads the manifest and streams evidence bytes for hashing only; it does not parse labels, load checkpoints or execute experiments.
- Six new synthetic verifier cases **passed**, with one deprecation warning, in 0.12 seconds. They cover matching/changed/missing bytes, forbidden E2 paths, traversal, absolute paths, alternate data streams and incorrect inventory size. Command: `python -m pytest -q tests/test_frozen_e1_manifest.py --basetemp <another-fresh-task-local-directory> -p no:cacheprovider`.
- `git diff --check` and PowerShell syntax parsing of `scripts/run_app.ps1` passed. The launcher now points its missing-environment message to the actual setup instructions. The launcher was not executed.

## Runtime observation

Python 3.14 is the selected interpreter. Installed distribution metadata compared with `requirements-tested.txt`:

| Package | Windows version | Recorded version | Match |
| --- | --- | --- | --- |
| numpy | 2.3.5 | 2.3.5 | yes |
| scipy | 1.16.3 | 1.17.1 | no |
| torch | 2.9.1 | 2.5.1 | no |
| fastapi | 0.141.1 | 0.135.1 | no |
| uvicorn | 0.53.0 | 0.42.0 | no |
| pytest | 8.4.2 | 9.0.2 | no |
| httpx | 0.28.1 | 0.28.1 | yes |
| pydantic | 2.13.5 | 2.13.5 | yes |

Node is `v22.20.0`; npm is `10.9.3`. `ollama --version` reports client `0.34.0` and warns that it could not connect to a running instance. This establishes a present client and an unsuccessful service connection at the time checked, not a verified Llama runtime. No packages or models were installed or downloaded, and no model service was started. The separate cloud audit's missing Ollama finding describes its own environment.

## Remaining October 4 plan work

This advances evidence preservation and Windows engineering checks from the scope/evidence and reproduction portions of the plan. Full Windows/Colab research execution, a fresh dependency environment, frontend rebuild/browser acceptance, relocated live-server checks, and the cause of historical hash differences remain unverified here. The recorded 5,190 score-hash and 2,009 full-ranking differences are historical; this check did not regenerate rankings or resolve their cause.

Formal E2 remains blocked on the prospective supervisor amendment, replacement-bank provenance, valid annotation/exposure route, full freeze and verified runtime. The original protocols and frozen evidence remain unchanged. The five cloud-authored deliverables are pending final version notification and are excluded from this change. Personal reading, hours, meetings, supervisor decisions and final submission remain tasks for the student to document when they occur.
