# Source and frontend verification

This page keeps build and checksum details separate from the project summary. They help identify the files under review; they do not establish model accuracy or a working hosted connection.

## Include the built interface

The personal app serves `web/dist/`, but `.gitignore` excludes it. A normal Git add may omit the UI. A source release must deliberately include the verified frontend build and check the Git index before publication.

From the repository root in Windows PowerShell, after preparing the index, run:

```powershell
C:\Python314\python.exe scripts\check_personal_ui_index.py
```

This read-only check requires the exact three paths and SHA-256 values pinned in `scripts/check_personal_ui_index.py`. Refresh those pins when the verified frontend changes, before checking the release index. It compares the actual staged blob bytes, not just the working files. It neither stages nor uploads files. It uses Python's standard library and Git and also runs on other platforms with Python 3 and Git.

## Keep historical receipts separate

`PERSONAL-AUTH-SHA256SUMS.txt` describes an earlier version and remains unchanged. In the combined reviewed v6 source, these receipt-covered paths differ or are absent:

- `feedctrl/claude_personal.py`
- `feedctrl/windows_job_native.py`
- `feedctrl/windows_job_runner.py`
- `web/src/personalApi.js`
- `web/dist/index.html`
- `web/dist/assets/index-DTzE0yVt.js`
- `tests/test_windows_job_runner_offline.py`
- `pyproject.toml`

In v6, `web/dist/assets/index-CZ9L8i2t.js` replaced the old `web/dist/assets/index-DTzE0yVt.js`, and the index check pinned that error-handling build. The later hosted-draft interface produces a different asset, and its index pins were updated to that verified build. All 7 index checks passed. These checks identify the packaged UI; they do not test live model generation. `pyproject.toml` declares `jsonschema` in the test extra. The old receipt is not a checksum of the whole current tree.

## Verify the source manifest

Each release should carry an updated [`CURRENT-SOURCE-SHA256.txt`](../CURRENT-SOURCE-SHA256.txt). Its paths are relative to the repository root, or to `source/` in a packaged copy. It covers every release source file except the manifest itself, which is excluded to avoid self-reference. Git checkout line-ending conversion must preserve the recorded bytes.

The separate package-root `SOURCE-FILE-SHA256.txt` covers the source tree within the package, including the portable manifest, using paths relative to `source/`, without a `source/` prefix. Verify it with `source/` as the working directory (for example, `cd source` followed by `sha256sum -c ../SOURCE-FILE-SHA256.txt`). It excludes the outer verification records, other package documents and itself. Regenerate release manifests after approved source or documentation changes, then verify them against the final files. Never replace an older test or evidence receipt with a new checksum and present it as the original record.

Offline checks and builds do not establish hosted-model behavior or successful browser interaction. The automatic personal launch remains disabled.

## Current cited-context interface

The integrated definition-context interface was rebuilt using existing dependencies matching package-lock.json, without installation. All 59 offline Node checks passed and Vite transformed 32 modules. The build contains index-C2wfZ-Ft.js and index-hBnJv3xo.css. The complete dist tree reproduces the context patch author's build exactly; scripts/check_personal_ui_index.py pins all three current asset paths and hashes. Its seven mocked-index checks pass within the current aggregate. No real Git index, browser or server was exercised. Earlier build and missing-dependency receipts remain historical evidence.
