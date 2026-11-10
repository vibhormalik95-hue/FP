"""Optional Windows-only, source-free local runner smoke test. Never calls Claude.

Run only after the candidate source is legitimately present on the laptop and a
the script and runner have been independently reviewed. This launches only the current Python executable and, for
one scenario, a short-lived Python descendant. It does not inspect account state.
"""
from pathlib import Path
import os
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from feedctrl.windows_job_runner import run_windows_job, WindowsRunnerError


def main():
    if os.name != 'nt':raise SystemExit('Windows required; no test was run.')
    exe=os.path.abspath(sys.executable)
    env={k:os.environ[k] for k in ('SYSTEMROOT','WINDIR','TEMP','TMP') if k in os.environ}
    if 'SYSTEMROOT' not in env:raise SystemExit('SYSTEMROOT is required.')
    with tempfile.TemporaryDirectory(prefix='comp-runner-smoke-') as directory:
        result=run_windows_job([exe,'-I','-S','-c','import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())'],
                               b'COMP_RUNNER_OK',env,directory,10,64)
        if result != (0,b'COMP_RUNNER_OK'):raise AssertionError('Echo result mismatch')
        print('Echo and normal exit: PASS',flush=True)
        child=('import subprocess,sys,time; '
               'subprocess.Popen([sys.executable,"-I","-S","-c","import time; time.sleep(30)"]); '
               'print("CHILD_STARTED",flush=True); time.sleep(0.25)')
        try:run_windows_job([exe,'-I','-S','-c',child],b'',env,directory,10,128)
        except WindowsRunnerError as exc:
            if str(exc)!='Root exited while job descendants remained':raise
            print('Ordinary child cleanup after parent exit: PASS',flush=True)
        else:raise AssertionError('Expected a remaining descendant to be detected')
        try:run_windows_job([exe,'-I','-S','-c','import sys; sys.stdout.write("x"*65536)'],
                            b'',env,directory,10,64)
        except WindowsRunnerError as exc:
            if str(exc)!='Output limit exceeded':raise
            print('Output bound and cleanup: PASS',flush=True)
        else:raise AssertionError('Expected output limit to stop the job')
    print('Smoke checks complete; no Claude or project data used.',flush=True)

if __name__=='__main__':main()
