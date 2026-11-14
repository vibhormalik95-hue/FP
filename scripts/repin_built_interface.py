"""Regenerate the pin of the built interface after a rebuild of web/dist.

The check ``scripts/check_personal_ui_index.py`` compares the staged files of
``web/dist`` with a table of paths and SHA-256 digests (``EXPECTED``). After a
rebuild that table is out of date. This script writes the table again from the
files that are in ``web/dist`` now.

Use, from the repository root:

    cd web && npm run build && cd ..
    python scripts/repin_built_interface.py
    git add web/dist scripts/check_personal_ui_index.py
    python scripts/check_personal_ui_index.py

The script reads only ``web/dist`` and changes only the ``EXPECTED`` block of
``scripts/check_personal_ui_index.py``. Stage ``web/dist`` before the check:
the check reads the git index, not the working tree. Output is ASCII.
"""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / 'scripts' / 'check_personal_ui_index.py'


def digests():
    dist = ROOT / 'web' / 'dist'
    if not dist.is_dir():
        raise SystemExit('FAIL: web/dist does not exist. Build the interface first: cd web && npm run build')
    return {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(dist.rglob('*')) if path.is_file()}


def main():
    expected = digests()
    text = GUARD.read_text(encoding='utf-8')
    new, count = re.subn(r'EXPECTED = \{.*?\n\}', lambda _: 'EXPECTED = ' + json.dumps(expected, indent=4), text, flags=re.S)
    if count != 1:
        raise SystemExit('FAIL: the EXPECTED block was not found in ' + GUARD.relative_to(ROOT).as_posix())
    GUARD.write_text(new, encoding='utf-8')
    for path, digest in expected.items():
        print(f'{digest}  {path}')
    print(f'PINNED: {len(expected)} files of web/dist in {GUARD.relative_to(ROOT).as_posix()}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
