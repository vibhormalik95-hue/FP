"""Run the guarded driver checks against the current prompt contract.

``tools/hosted_validation_current/`` is frozen evidence: its inputs, its driver
and its templates belong to the reviewed profile of 11 November 2026. The
prompts of the application changed after that date, so the frozen first model
input no longer equals the request that the application builds, and
``python tools/hosted_validation_current/run_guarded.py .`` reports failures
for every check that starts a scenario. That result is correct: no reviewed
successor profile exists for the current source.

This script checks the driver logic against the current prompts without a
change to the frozen directory. It copies the two validation folders to a
temporary folder, puts the test inputs of ``tests/fixtures/personal_cli_current``
over the copy, sets the manifest pin of the copied driver, and runs the same
guarded checks on the copy. The guard blocks network use, processes and model
imports, as in the original runner. Nothing here is a review, a profile or
model evidence.

Use, from the repository root:

    python scripts/run_guarded_current_contract.py

Exit code 0: every check passed on the copy, except the checks that this script
names as checks of the frozen files themselves. Output is ASCII.
"""
import hashlib
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools'
OVERLAY = ROOT / 'tests' / 'fixtures' / 'personal_cli_current'
# These checks compare the frozen files with each other or with the driver file. On the copy they
# cannot pass: the copy has other inputs and another pin on purpose.
FROZEN_FILE_CHECKS = ('test_templates_false_gated_and_pins_current', 'test_current_input_delta_is_only_system_prompt')


def run(runner, *names):
    done = subprocess.run([sys.executable, '-B', str(runner), str(ROOT), *names], capture_output=True, text=True,
                          cwd=str(ROOT), timeout=600)
    text = done.stdout + done.stderr
    ran = re.search(r'^Ran (\d+) tests?', text, re.M)
    problems = sorted(set(re.findall(r'^(?:FAIL|ERROR): (\w+)', text, re.M)))
    intercepted = re.search(r'^GUARD intercepted events: (.*)$', text, re.M)
    return {'exit': done.returncode, 'ran': int(ran.group(1)) if ran else 0, 'problems': problems,
            'intercepted': intercepted.group(1) if intercepted else 'not reported', 'text': text}


def copy_verdict(current):
    """Problems of the run on the copy. The run fails when no check ran, when a check failed that is not a check of
    the frozen files, or when the runner exited nonzero and the parsed failures do not explain it (a crash, a guard
    interception or a collection error can end the runner without a FAIL or ERROR line)."""
    problems = []
    unexpected = [name for name in current['problems'] if name not in FROZEN_FILE_CHECKS]
    if current['ran'] == 0:
        problems.append('no check ran')
    if unexpected:
        problems.append('unexpected failures: ' + ', '.join(unexpected))
    if current['exit'] != 0 and not current['problems']:
        problems.append(f"runner exit {current['exit']} without a parsed FAIL or ERROR line")
    if current['exit'] == 0 and current['problems']:
        problems.append('runner exit 0 although failures were parsed')
    if current['intercepted'] not in ('[]', 'not reported') and current['intercepted']:
        problems.append('guard intercepted events: ' + current['intercepted'])
    return problems


def count_words(problems):
    return 'no check with a failure' if not problems else (
        '1 check with a failure' if len(problems) == 1 else f'{len(problems)} checks with a failure')


def main():
    with tempfile.TemporaryDirectory() as folder:
        copy = Path(folder) / 'tools'
        for name in ('hosted_validation', 'hosted_validation_current'):
            shutil.copytree(TOOLS / name, copy / name)
        inputs = copy / 'hosted_validation_current' / 'inputs'
        for path in sorted(OVERLAY.rglob('*')):
            if path.is_file() and path.name != 'README.md':
                shutil.copyfile(path, inputs / path.relative_to(OVERLAY))
        # A checkout can hold CR LF line ends. The manifest counts LF bytes.
        for path in inputs.rglob('*'):
            if path.is_file():
                path.write_bytes(path.read_bytes().replace(b'\r\n', b'\n'))
        pin = hashlib.sha256((inputs / 'MANIFEST.json').read_bytes()).hexdigest()
        driver = copy / 'hosted_validation_current' / 'driver.py'
        text, count = re.subn(r"INPUT_MANIFEST_SHA256 = '[0-9a-f]{64}'", f"INPUT_MANIFEST_SHA256 = '{pin}'",
                              driver.read_text(encoding='utf-8'))
        if count != 1:
            raise SystemExit('FAIL: the manifest pin of the driver was not found')
        driver.write_text(text, encoding='utf-8')
        current = run(copy / 'hosted_validation_current' / 'run_guarded.py')
    frozen = run(TOOLS / 'hosted_validation_current' / 'run_guarded.py')

    print('Guarded driver checks')
    print(f'1. Frozen profile of 11 November 2026 (tools/hosted_validation_current, unchanged): {frozen["ran"]} checks, '
          f'{count_words(frozen["problems"])}. Intercepted events: {frozen["intercepted"]}')
    print('   A failure here means that the current prompts differ from the frozen first model input.')
    print(f'2. The same checks with the current-contract test inputs, on a temporary copy: {current["ran"]} checks, '
          f'{count_words(current["problems"])}. Intercepted events: {current["intercepted"]}')
    print(f'   Runner exit code on the copy: {current["exit"]}; on the frozen profile: {frozen["exit"]}')
    for name in current['problems']:
        print(f'   {"expected on the copy (a check of the frozen files)" if name in FROZEN_FILE_CHECKS else "NOT EXPECTED"}: {name}')
    problems = copy_verdict(current)
    if problems:
        sys.stdout.write(current['text'][-4000:])
        print('FAIL: the driver checks do not pass with the current-contract test inputs (' + '; '.join(problems) + ')')
        return 1
    print('PASS: the driver checks pass with the current-contract test inputs. The frozen profile is unchanged.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
