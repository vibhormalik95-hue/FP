"""Read-only staged-UI guard contracts using mocked Git responses, never staging."""
import contextlib
import hashlib
import importlib.util
import io
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("personal_ui_index_guard", ROOT / "scripts/check_personal_ui_index.py")
GUARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUARD)


class PersonalUiIndexTests(unittest.TestCase):
    def setUp(self):
        self.blobs = {path: (ROOT / path).read_bytes() for path in GUARD.EXPECTED}
        self.records = [(path, "100644", "0") for path in self.blobs]

    def run_guard(self):
        def git(*args):
            if args == ("ls-files", "--stage", "-z", "--", "web/dist/"):
                return b"".join(f"{mode} {'0' * 40} {stage}\t{path}\0".encode()
                                for path, mode, stage in self.records)
            self.assertEqual(args[0], "show")
            self.assertTrue(args[1].startswith(":"))
            return self.blobs[args[1][1:]]

        output = io.StringIO()
        with patch.object(GUARD, "git", side_effect=git), \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            status = GUARD.main()
        return status, output.getvalue()

    def test_pins_exact_current_build_paths_and_bytes(self):
        actual = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in (ROOT / "web/dist").rglob("*") if p.is_file()}
        self.assertEqual(GUARD.EXPECTED, actual)
        status, output = self.run_guard()
        self.assertEqual(status, 0)
        self.assertIn("PASS", output)

    def test_rejects_missing_asset(self):
        self.records.pop()
        self.assertEqual(self.run_guard()[0], 1)

    def test_rejects_extra_or_old_asset(self):
        self.records.append(("web/dist/assets/stale-build.js", "100644", "0"))
        self.assertEqual(self.run_guard()[0], 1)

    def test_rejects_changed_staged_blob_even_if_working_tree_is_unchanged(self):
        self.blobs["web/dist/index.html"] += b"staged modification"
        status, output = self.run_guard()
        self.assertEqual(status, 1)
        self.assertIn("staged content differs", output)

    def test_rejects_symlink_or_conflicted_index_entries(self):
        path = self.records[0][0]
        for mode, stage in (("120000", "0"), ("100644", "1")):
            with self.subTest(mode=mode, stage=stage):
                self.records[0] = (path, mode, stage)
                self.assertEqual(self.run_guard()[0], 1)

    def test_rejects_duplicate_index_path(self):
        self.records.append(self.records[0])
        status, output = self.run_guard()
        self.assertEqual(status, 1)
        self.assertIn("duplicate index path", output)

    def test_git_failure_is_fail_closed(self):
        with patch.object(GUARD, "git", side_effect=subprocess.CalledProcessError(128, "git")), \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(GUARD.main(), 1)


if __name__ == "__main__":
    unittest.main()
