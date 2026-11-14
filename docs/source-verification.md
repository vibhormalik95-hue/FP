# Built interface and release checks

> **Current guide.** For the complete verification sequence, see [install and run](install-and-run.md#9-final-verification-sequence).

The app serves the built interface in `web/dist`. That folder is tracked in this repository, so a fresh clone can run the demonstration without Node.

## After a change to `web/src`

```
cd web
npm ci
npm run build
```

Then write the new pins, stage the files and run the check, from the repository root:

```
python scripts/repin_built_interface.py
git add web/dist scripts/check_personal_ui_index.py
python scripts/check_personal_ui_index.py
```

`repin_built_interface.py` reads `web/dist` and rewrites only the table of paths and SHA-256 values in `scripts/check_personal_ui_index.py`. The check compares the staged files with that table, so stage `web/dist` first. `tests/test_personal_ui_index_offline.py` compares the files on disk with the same pins.

A new build also changes the source fingerprint (`python scripts/run_demo.py --fingerprint`), because the fingerprint covers `web/dist`. A run record of an earlier build then names another fingerprint.

## Line endings

`.gitattributes` keeps the built interface, the saved study evidence, the dated deliverables and the pinned scenario inputs byte-exact. Do not let an editor or a Git setting convert their line endings: several files are identified by SHA-256.

## What these checks do not show

A matching build and passing tests identify the files. They do not show model behaviour, browser behaviour or a working model connection. For those, see the [guide to the language controls](demo.md).
