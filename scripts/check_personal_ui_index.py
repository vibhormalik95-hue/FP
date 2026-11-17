"""Read-only check of the staged personal UI against the verified current build."""

import hashlib
import subprocess
import sys

EXPECTED = {
    "web/dist/assets/index-D3GHG6Ir.js": "641f96fe284c40f06d3da181ee96fbaf6685a06ce977997f411c85c519bcf0d1",
    "web/dist/assets/index-DyF_3HqL.css": "750b04a3d058dd72d007f583c44dc0b6a2e57c09cabc81ed278bef4bf5c5886d",
    "web/dist/index.html": "2ecce836e39ce85c6f803fe21f0967e74930f85e6d45d11279f18eca5df33370"
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
