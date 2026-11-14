"""The guarded driver checks pass with the current-contract test inputs, and the frozen profile stays unchanged."""
import hashlib
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / 'tools' / 'hosted_validation_current'


def digest():
    lines = hashlib.sha256()
    for path in sorted(FROZEN.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts:
            lines.update(path.relative_to(FROZEN).as_posix().encode('utf-8') + b'\0' + hashlib.sha256(path.read_bytes()).digest())
    return lines.hexdigest()


def test_the_driver_checks_pass_on_a_copy_and_the_frozen_profile_is_not_changed():
    before = digest()
    done = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts' / 'run_guarded_current_contract.py')],
                          capture_output=True, text=True, cwd=str(ROOT), timeout=900)
    assert done.returncode == 0, done.stdout[-3000:] + done.stderr[-2000:]
    assert 'PASS: the driver checks pass with the current-contract test inputs.' in done.stdout
    assert 'NOT EXPECTED' not in done.stdout and 'Intercepted events: []' in done.stdout
    # The run names the state of the frozen profile; it does not repair it.
    assert '1. Frozen profile of 11 November 2026' in done.stdout
    assert digest() == before
