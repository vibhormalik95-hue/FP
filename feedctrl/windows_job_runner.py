"""Fail-closed Windows runner control loop; no execution occurs on import.

A backend must atomically assign the suspended process to an unnamed, noninherited
kill-on-close job before resuming it, and must use bounded pipe I/O with pinned-thread cancellation.
Tests inject a fake backend; they do not validate Windows. This module does not
assert that a Job Object confines externally brokered process creation.
"""
from __future__ import annotations
import os
import math
import time


class WindowsRunnerError(RuntimeError):
    pass


class CleanupUncertain(WindowsRunnerError):
    pass


def run_with_backend(argv, input_bytes, env, cwd, timeout, output_limit, *, backend,
                     now=time.monotonic, sleep=time.sleep, cleanup_timeout=3):
    """Run with one hard deadline and no retries. backend is an injected Win32 API.

    Backend contract: launch returns an already-contained run whose primary thread
    has not run until assignment was checked. Synchronous anonymous pipes use worker
    threads; their real handles remain pinned through cancellation and join. poll() returns (new_stdout_bytes,
    stdin_done, stdout_eof, root_exit_or_None, active_job_members). terminate() must
    terminate the job. finish_io(deadline) cancels outstanding I/O and waits for its
    completion; cleanup_complete() confirms root exit/release and empty job;
    check_io() reports transport failures; close() closes owned handles.
    Any inability to prove cleanup fails.
    """
    if (not isinstance(argv,list) or not argv or not all(isinstance(x,str) and '\x00' not in x for x in argv)
            or not isinstance(input_bytes,bytes) or not isinstance(env,dict) or not isinstance(cwd,str)
            or type(output_limit) is not int or not 1 <= output_limit <= 2000000
            or type(timeout) not in (int,float) or not math.isfinite(timeout) or not 0 < timeout <= 300
            or type(cleanup_timeout) not in (int,float) or not math.isfinite(cleanup_timeout)
            or not 0 < cleanup_timeout <= 30):
        raise ValueError('Invalid process-runner inputs')
    run=None
    start=now(); deadline=start+timeout; output=bytearray(); result=None; primary_error=None
    try:
        # launch must clean its own partial resources if it raises.
        run=backend.launch(argv, input_bytes, env, cwd, output_limit, deadline)
        while True:
            if now() >= deadline:
                raise TimeoutError('Process deadline exceeded')
            chunk, input_done, eof, exit_code, active = run.poll(output_limit-len(output)+1)
            if not isinstance(chunk,bytes) or type(input_done) is not bool or type(eof) is not bool:
                raise WindowsRunnerError('Invalid Windows I/O state')
            if type(active) is not int or active < 0 or (exit_code is not None and type(exit_code) is not int):
                raise WindowsRunnerError('Invalid Windows process state')
            output.extend(chunk)
            if len(output)>output_limit:
                raise WindowsRunnerError('Output limit exceeded')
            if exit_code is not None:
                if active:
                    raise WindowsRunnerError('Root exited while job descendants remained')
                if input_done and eof:
                    result=(exit_code,bytes(output));break
            sleep(min(.01,max(0,deadline-now())))
    except BaseException as exc:
        primary_error=exc
    if run is not None:
        errors=[]
        try:
            run.terminate()  # also on success; no descendant may outlive this invocation
        except BaseException as exc:
            errors.append(type(exc).__name__)
        cleanup_deadline=now()+cleanup_timeout
        try:
            while not run.cleanup_complete():
                if now()>=cleanup_deadline:raise TimeoutError('Job still has processes')
                sleep(min(.01,max(0,cleanup_deadline-now())))
        except BaseException as exc:
            errors.append(type(exc).__name__)
        try:
            if not run.finish_io(cleanup_deadline):errors.append('UnconfirmedIoCompletion')
        except BaseException as exc:
            errors.append(type(exc).__name__)
        if primary_error is None and not errors:
            try:run.check_io()
            except BaseException as exc:primary_error=exc
        try:
            run.close()
        except BaseException as exc:
            errors.append(type(exc).__name__)
        if errors:
            raise CleanupUncertain('Windows process or I/O cleanup could not be confirmed') from primary_error
    if primary_error is not None:
        raise primary_error
    return result


def run_windows_job(argv,input_bytes,env,cwd,timeout,output_limit):
    """Experimental Windows entry point. The app launch seam remains separately disabled."""
    if os.name != 'nt':
        raise WindowsRunnerError('Windows is required')
    from feedctrl.windows_job_native import WindowsBackend
    return run_with_backend(argv,input_bytes,env,cwd,timeout,output_limit,backend=WindowsBackend())
