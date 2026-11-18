"""Regression test for r6 finding D1b: the guarded-contract wrapper must not pass a runner that exited nonzero
without a parsed FAIL or ERROR line, or one whose guard intercepted an event."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("rgcc", ROOT / "scripts" / "run_guarded_current_contract.py")
rgcc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rgcc)
EXPECTED = list(rgcc.FROZEN_FILE_CHECKS)


def result(exit_code, ran, problems, intercepted="[]"):
    return {"exit": exit_code, "ran": ran, "problems": problems, "intercepted": intercepted, "text": ""}


def test_nonzero_exit_without_a_parsed_failure_fails():
    assert rgcc.copy_verdict(result(1, 12, []))


def test_crash_after_some_checks_fails():
    assert rgcc.copy_verdict(result(2, 3, [], intercepted="not reported"))


def test_guard_interception_fails():
    assert rgcc.copy_verdict(result(1, 12, EXPECTED, intercepted="['socket.connect']"))


def test_only_the_frozen_file_checks_failing_passes():
    assert rgcc.copy_verdict(result(1, 12, EXPECTED)) == []


def test_an_unexpected_failure_or_no_checks_fails():
    assert rgcc.copy_verdict(result(1, 12, EXPECTED + ["test_other"]))
    assert rgcc.copy_verdict(result(0, 0, []))
