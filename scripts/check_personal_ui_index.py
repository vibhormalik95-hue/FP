"""Read-only check of the staged personal UI against the verified current build."""

import hashlib
import subprocess
import sys

EXPECTED = {
    "web/dist/assets/index-BDkAvLYu.js": "bc601a3718b5a0017de618351970e8f9d24c3a5f7bd77d2acbeed7bfcebf2cf7",
    "web/dist/assets/index-CrI4oyqz.css": "d1e9de2a32d7cb39a678d31f500065da6465508553bb7735ccbfefb5d5c2258d",
    "web/dist/index.html": "c6034ce55b7cf13f18afe3cb470a586a1f6005fc77e0ce90b9dfb5c364f3043a"
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
