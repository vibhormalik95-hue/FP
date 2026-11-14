"""Write or check CURRENT-SOURCE-SHA256.txt.

The list holds one line for every file that Git tracks, except the list itself:
the SHA-256 of the staged bytes, two spaces, the path. The paths are in byte
order. The bytes are the bytes that Git stores, so the list is the same on
every operating system.

Use, from the repository root, after ``git add`` and before a commit:

    python scripts/refresh_source_manifest.py            # write the list, then stage it
    python scripts/refresh_source_manifest.py --check    # compare; exit code 1 names the differences

The list goes out of date with every staged change. It is a statement about
the commit that holds it, not a signature. Output is ASCII.
"""
import hashlib
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
NAME = 'CURRENT-SOURCE-SHA256.txt'


def git(*arguments):
    return subprocess.check_output(['git', '--no-optional-locks', *arguments], cwd=str(ROOT))


def staged_lines():
    lines = []
    for record in filter(None, git('ls-files', '--stage', '-z').split(b'\0')):
        metadata, path = record.split(b'\t', 1)
        mode, blob, stage = metadata.decode('ascii').split()
        if stage != '0':
            raise SystemExit('FAIL: the index holds an unmerged path: ' + path.decode('utf-8', 'backslashreplace'))
        if path.decode('utf-8') == NAME or mode == '160000':
            continue
        lines.append((path, hashlib.sha256(git('cat-file', 'blob', blob)).hexdigest()))
    return ''.join(f'{digest}  {path.decode("utf-8")}\n' for path, digest in sorted(lines))


def main(arguments):
    expected = staged_lines()
    target = ROOT / NAME
    if arguments == ['--check']:
        current = target.read_text(encoding='utf-8') if target.is_file() else ''
        if current == expected:
            print(f'PASS: {NAME} lists the {expected.count(chr(10))} staged files')
            return 0
        old, new = (dict(reversed(line.split('  ', 1)) for line in text.splitlines() if '  ' in line) for text in (current, expected))
        for path in sorted(set(old) | set(new)):
            if old.get(path) != new.get(path):
                state = 'not in the list' if path not in old else 'not staged' if path not in new else 'other bytes'
                print(f'{state}: {path}'.encode('ascii', 'backslashreplace').decode('ascii'))
        print(f'FAIL: {NAME} differs from the staged files')
        return 1
    if arguments:
        raise SystemExit('usage: refresh_source_manifest.py [--check]')
    target.write_bytes(expected.encode('utf-8'))
    print(f'WRITTEN: {NAME} with {expected.count(chr(10))} files. Stage it: git add {NAME}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
