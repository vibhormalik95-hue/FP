"""Read-only check of the staged personal UI against the verified current build."""

import hashlib
import subprocess
import sys

EXPECTED = {
    "web/dist/assets/index-DaEDo2Lm.js": "00551a7cbd843cdadb3a0160ee7c6e424fbff67d83efcabbeb68e86f99c13115",
    "web/dist/assets/index-DS5vWPp9.css": "7a82d8817b73302eb7157c6afdb9abeb84564106e7d6639968d2a9d00589df8a",
    "web/dist/index.html": "c2a88f53eff38c3d58107e883502f5aa9818a085796bdbe792b3884781a0048d"
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
