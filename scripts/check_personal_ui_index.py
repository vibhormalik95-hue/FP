"""Read-only check of the staged personal UI against the verified error-handling build."""

import hashlib
import subprocess
import sys

EXPECTED = {
    "web/dist/index.html": "ac86a853320b58bf6e5b935798fc05a7a9a90b6c5e494836a1a131b18b081adc",
    "web/dist/assets/index-CZ9L8i2t.js": "6178f0d52558b036e4a983a72d9ac7539de39023421f23ef2bd5bb82c7297f4b",
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
