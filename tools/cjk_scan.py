"""Find visible CJK characters (U+3000-U+303F, U+3400-U+9FFF, U+FF00-U+FFEF) in text files.

    python tools/cjk_scan.py [paths...]        (default: every file git tracks)

Prints one line per file with hits: path, count, first hit in context. Binary files are skipped
(a PNG or PDF is checked by rendering, not by bytes). Exit code 1 when any hit is found.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

CJK = re.compile("[\u3000-\u303f\u3400-\u9fff\uff00-\uffef]")
ROOT = Path(__file__).resolve().parents[1]


def scan(path: Path):
    data = path.read_bytes()
    if b"\0" in data[:4096]:
        return None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    hits = CJK.findall(text)
    if not hits:
        return None
    m = CJK.search(text)
    context = text[max(0, m.start() - 30):m.start() + 30].replace("\n", " ")
    return len(hits), context


def main(argv=None):
    args = (argv if argv is not None else sys.argv[1:])
    paths = [Path(a) for a in args] or [ROOT / p for p in subprocess.run(
        ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8").stdout.splitlines()]
    found = 0
    for path in paths:
        if not path.is_file():
            continue
        result = scan(path)
        if result:
            found += 1
            rel = path.relative_to(ROOT) if path.is_absolute() and ROOT in path.parents else path
            print(f"{rel.as_posix()}\t{result[0]}\t{result[1]}")
    print(f"{found} file(s) with CJK characters", file=sys.stderr)
    return 1 if found else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
