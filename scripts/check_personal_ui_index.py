"""Read-only check of the staged personal UI against the verified error-handling build."""

import hashlib
import subprocess
import sys

EXPECTED = {
    "web/dist/index.html": "eb1c5da055b9c2eb1d9bf102ad51ec6177158fb24f24ad4f6fdcf9cc0fe9e495",
    "web/dist/assets/index-3Po6RtMZ.js": "3bc591e7b1e91b2a5a6b2b2c44f1e9460baba1dad0793ae30f8a4ae63c9d394d",
    "web/dist/assets/index-hBnJv3xo.css": "7a86a3861d714c72b3b13f57dcfc65ccb27ee9143dbf801b183bc81bdd4eb0bb",
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
