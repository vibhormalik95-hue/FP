# Built interface and release checks

The app serves the built interface in `web/dist`. That folder is tracked in this repository, so a fresh clone can run the demonstration without Node.

## After a change to `web/src`

```
cd web
npm ci
npm run build
```

Then update the three paths and SHA-256 values in `scripts/check_personal_ui_index.py`, stage the new files, and run:

```
python scripts/check_personal_ui_index.py
```

The check compares the staged files with the pinned build. `tests/test_personal_ui_index_offline.py` compares the files on disk with the same pins.

## Line endings

`.gitattributes` keeps the built interface, the saved study evidence, the dated deliverables and the pinned scenario inputs byte-exact. Do not let an editor or a Git setting convert their line endings: several files are identified by SHA-256.

## What these checks do not show

A matching build and passing tests identify the files. They do not show model behaviour, browser behaviour or a working model connection. For those, see the [demonstration guide](demo.md).
