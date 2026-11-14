"""Read-only check of the staged personal UI against the verified current build."""

import hashlib
import subprocess
import sys

EXPECTED = {
    "web/dist/assets/index-BUimDrSr.css": "6e163c5d485bde5379890dc4b2dcb852aa7e9c91a36e880eb5bba58582e02aca",
    "web/dist/assets/index-CIeekwDd.js": "09c0d42e4b513abc589d557247d4b590e7e21a1d55135c7d0564bd56b924c965",
    "web/dist/index.html": "d27e1b388d3133703a6b6277d6167047102c4f2ca3c9dea20cb350118bbd0e3c"
}


def git(*args):
    return subprocess.check_output(["git", "--no-optional-locks", *args])


def main():
    try:
        records = git("ls-files", "--stage", "-z", "--", "web/dist/").split(b"\0")
        staged = {}
        for record in filter(None, records):
            metadata, path = record.split(b"\t", 1)
            mode, _, stage = metadata.decode("ascii").split()
            path = path.decode("utf-8")
            if path in staged:
                raise ValueError("duplicate index path")
            staged[path] = (mode, stage)
        if set(staged) != set(EXPECTED) or any(
            value != ("100644", "0") for value in staged.values()
        ):
            raise ValueError("staged web/dist paths or index entries differ from the verified build")
        for path, digest in EXPECTED.items():
            actual = hashlib.sha256(git("show", ":" + path)).hexdigest()
            if actual != digest:
                raise ValueError("staged content differs: " + path)
    except (OSError, subprocess.CalledProcessError, UnicodeError, ValueError) as error:
        print("FAIL: " + str(error), file=sys.stderr)
        return 1
    print("PASS: staged web/dist paths and bytes match the verified build")
    return 0


if __name__ == "__main__":
    sys.exit(main())
