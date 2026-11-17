"""Read-only check of the staged personal UI against the verified current build."""

import hashlib
import subprocess
import sys

EXPECTED = {
    "web/dist/assets/index-Dorkhqzc.css": "946bc49f98c5264dd84a0caf8493fd6e982552b6e549bb852b6cd7368667e178",
    "web/dist/assets/index-Dvwux7Tf.js": "0c8640a43d2941248e9ab07389ef06888255b46ce6d4b5402d5e745c8d670c0b",
    "web/dist/index.html": "bc8a2728e7548aae60af8640b824148715ce3060aca64b9dce96fad69e55c587"
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
