"""State-machine tests only; no OS process, CLI, model, or laptop access."""
import unittest
import threading
import time
from unittest.mock import patch
from feedctrl.windows_job_runner import run_with_backend, WindowsRunnerError, CleanupUncertain

class Clock:
    def __init__(self):self.t=0
    def now(self):return self.t
    def sleep(self,seconds):self.t+=seconds
class Run:
    def __init__(self,states,active=(0,),io=True,terminate_error=False,close_error=False):
        self.states=list(states);self.active=list(active);self.io=io;self.terminate_error=terminate_error;self.close_error=close_error
        self.terminated=0;self.closed=0;self.io_calls=0
    def poll(self,limit):return self.states.pop(0) if self.states else (b'',False,False,None,1)
    def terminate(self):
        self.terminated+=1
        if self.terminate_error:raise OSError()
    def active_count(self):return self.active.pop(0) if len(self.active)>1 else self.active[0]
    def cleanup_complete(self):return self.active_count()==0
    def finish_io(self,deadline):self.io_calls+=1;return self.io
    def check_io(self):pass
    def close(self):
        self.closed+=1
        if self.close_error:raise OSError()
class Backend:
    def __init__(self,run=None,error=None):self.run=run;self.error=error;self.calls=0
    def launch(self,*args):
        self.calls+=1
        if self.error:raise self.error
        return self.run
class Tests(unittest.TestCase):
    def invoke(self,run=None,backend=None,timeout=.1,limit=5):
        c=Clock();backend=backend or Backend(run)
        return run_with_backend(['/fake'],b'input',{},'/',timeout,limit,backend=backend,now=c.now,sleep=c.sleep,cleanup_timeout=.1)
    def test_success_waits_for_all_job_members_and_io(self):
        r=Run([(b'ab',True,False,None,1),(b'cd',True,True,0,0)])
        self.assertEqual(self.invoke(r),(0,b'abcd'));self.assertEqual((r.terminated,r.io_calls,r.closed),(1,1,1))
    def test_root_exit_with_descendant_fails_and_terminates(self):
        r=Run([(b'',True,False,0,1)])
        with self.assertRaisesRegex(WindowsRunnerError,'descendants'):self.invoke(r)
        self.assertEqual((r.terminated,r.io_calls,r.closed),(1,1,1))
    def test_output_overflow_terminates_and_does_not_return_partial(self):
        r=Run([(b'abcdef',False,False,None,1)])
        with self.assertRaisesRegex(WindowsRunnerError,'Output limit'):self.invoke(r)
        self.assertEqual(r.terminated,1)
    def test_timeout_stuck_io_kills_job(self):
        r=Run([])
        with self.assertRaises(TimeoutError):self.invoke(r)
        self.assertEqual((r.terminated,r.io_calls,r.closed),(1,1,1))
    def test_unconfirmed_job_or_io_cleanup_supersedes_success(self):
        for r in (Run([(b'',True,True,0,0)],active=(1,)),Run([(b'',True,True,0,0)],io=False),
                  Run([(b'',True,True,0,0)],terminate_error=True),Run([(b'',True,True,0,0)],close_error=True)):
            with self.subTest(run=r),self.assertRaises(CleanupUncertain):self.invoke(r)
            self.assertEqual(r.closed,1)
    def test_creation_failure_not_retried(self):
        b=Backend(error=OSError('create failed'))
        with self.assertRaises(OSError):self.invoke(backend=b)
        self.assertEqual(b.calls,1)
    def test_late_io_error_is_transport_failure_not_cleanup_uncertain(self):
        r=Run([(b'',True,True,0,0)])
        r.check_io=lambda: (_ for _ in ()).throw(WindowsRunnerError('late pipe error'))
        with self.assertRaisesRegex(WindowsRunnerError,'late pipe error'):self.invoke(r)
        self.assertEqual((r.terminated,r.io_calls,r.closed),(1,1,1))
    def test_nonfinite_timeout_rejected_before_launch(self):
        for bad in (float('nan'),float('inf'),float('-inf'),True,0,301):
            b=Backend(Run([]))
            with self.subTest(timeout=bad),self.assertRaises(ValueError):self.invoke(backend=b,timeout=bad)
            self.assertEqual(b.calls,0)
    def test_nonfinite_cleanup_timeout_rejected_before_launch(self):
        for bad in (float('nan'),float('inf'),True,0,31):
            c=Clock();b=Backend(Run([]))
            with self.subTest(timeout=bad),self.assertRaises(ValueError):
                run_with_backend(['/fake'],b'',{},'/',1,5,backend=b,now=c.now,sleep=c.sleep,cleanup_timeout=bad)
            self.assertEqual(b.calls,0)
    def test_cancellation_still_cleans_up(self):
        r=Run([])
        r.poll=lambda _: (_ for _ in ()).throw(KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt):self.invoke(r)
        self.assertEqual((r.terminated,r.io_calls,r.closed),(1,1,1))

class NativeCleanupTests(unittest.TestCase):
    def test_startup_cleanup_attempts_every_step_after_terminate_error(self):
        from feedctrl.windows_job_native import _NativeRun
        class API: k=object()
        with patch.object(_NativeRun,'_create',side_effect=OSError('create')), \
             patch.object(_NativeRun,'terminate',side_effect=OSError('terminate')) as term, \
             patch.object(_NativeRun,'finish_io',return_value=True) as finish, \
             patch.object(_NativeRun,'close') as close:
            with self.assertRaises(CleanupUncertain):_NativeRun(API(),'x','x',b'',{},'/',10,100)
        self.assertEqual((term.call_count,finish.call_count,close.call_count),(1,1,1))
    def test_cancel_uses_pinned_handle_and_reports_cancel_failure(self):
        from feedctrl.windows_job_native import _NativeRun
        class Worker:
            alive=True
            def is_alive(self):return self.alive
            def join(self,timeout):self.alive=False
        class Kernel:
            def __init__(self):self.cancelled=[]
            def CancelSynchronousIo(self,handle):self.cancelled.append(handle);return False
        run=_NativeRun.__new__(_NativeRun);run.stop=threading.Event();run.lock=threading.Lock()
        run.thread_handles={'writer':456};run.threads=[Worker()];run.k=Kernel();run.io_error=None
        with patch('ctypes.get_last_error',return_value=5,create=True):
            self.assertFalse(run.finish_io(time.monotonic()+1))
        self.assertEqual(run.k.cancelled,[456])
    def test_cancel_not_found_can_mean_already_finished(self):
        from feedctrl.windows_job_native import _NativeRun
        class Worker:
            alive=True
            def is_alive(self):return self.alive
            def join(self,timeout):self.alive=False
        class Kernel:
            def CancelSynchronousIo(self,handle):return False
        run=_NativeRun.__new__(_NativeRun);run.stop=threading.Event();run.lock=threading.Lock()
        run.thread_handles={'writer':456};run.threads=[Worker()];run.k=Kernel();run.io_error=None
        with patch('ctypes.get_last_error',return_value=1168,create=True):
            self.assertTrue(run.finish_io(time.monotonic()+1))
    def test_close_job_even_when_worker_alive(self):
        from feedctrl.windows_job_native import _NativeRun
        class T:
            def is_alive(self):return True
        run=_NativeRun.__new__(_NativeRun);run.job=11;run.process=12;run.input_handle=13;run.output_handle=14
        run.threads=[T()];run.thread_handles={'writer':15};run.attribute_initialized=False
        run.owned=[11,12,13,14,15];closed=[]
        def close(h):closed.append(h);run.owned.remove(h)
        run._close=close
        with self.assertRaises(CleanupUncertain):run.close()
        self.assertIn(11,closed);self.assertIn(12,closed)
        self.assertNotIn(13,closed);self.assertNotIn(14,closed);self.assertNotIn(15,closed)

class NativeRootLifecycleTests(unittest.TestCase):
    """Fake-kernel ordering only. These tests make no claims about Windows timing."""
    def make_run(self, *, signaled=True, code=7, active=0):
        import ctypes
        from ctypes import wintypes as w
        from feedctrl.windows_job_native import _NativeRun
        class Account(ctypes.Structure):
            _fields_=[('ActiveProcesses',w.DWORD)]
        class Kernel:
            def __init__(self):
                self.events=[];self.signaled=signaled;self.code=code;self.active=active
                self.fail_close=False;self.fail_wait=False;self.fail_exit=False;self.fail_query=False;self.fail_terminate=False
            def WaitForSingleObject(self,h,delay):
                self.events.append(('wait',h))
                if self.fail_wait:return 0xffffffff
                return 0 if self.signaled else 258
            def GetExitCodeProcess(self,h,p):
                self.events.append(('exit',h))
                if self.fail_exit:return False
                ctypes.cast(p,ctypes.POINTER(w.DWORD)).contents.value=self.code;return True
            def CloseHandle(self,h):
                self.events.append(('close',h))
                return not self.fail_close
            def QueryInformationJobObject(self,h,kind,p,size,returned):
                self.events.append(('query',h))
                if self.fail_query:return False
                ctypes.cast(p,ctypes.POINTER(Account)).contents.ActiveProcesses=self.active;return True
            def TerminateJobObject(self,h,code):
                self.events.append(('terminate',h))
                if self.fail_terminate:return False
                self.signaled=True;self.active=0;return True
        class API:
            ACCOUNT=Account
            def __init__(self):self.k=Kernel()
            def _ok(self,value,op):
                if not value:raise OSError(op)
                return value
        run=_NativeRun.__new__(_NativeRun);run.api=API();run.k=run.api.k
        run.job=11;run.process=12;run.primary=None;run.root_exit_code=None;run.root_release_failed=False
        run.root_created=True;run.root_handle=12;run.root_released=False;run.root_cleanup_failed=False
        run.root_membership=True;run.resume_attempted=True;run.startup_failed=False;run.root_termination_attempted=False
        run.owned=[11,12];run.lock=threading.Lock();run.io_error=None;run.data=bytearray()
        run.input_done=True;run.output_eof=True;run.input_handle=None;run.output_handle=None
        run.threads=[];run.thread_handles={};run.attribute_initialized=False;run.stop=threading.Event()
        return run
    def test_exit_captured_and_handle_released_before_job_query_cached_forever(self):
        r=self.make_run();self.assertEqual(r.poll(10),(b'',True,True,7,0))
        self.assertEqual(r.k.events,[('wait',12),('exit',12),('close',12),('query',11)])
        self.assertEqual(r.poll(10),(b'',True,True,7,0));self.assertTrue(r.cleanup_complete())
        r.close();self.assertEqual(r.k.events.count(('close',12)),1)
        self.assertEqual(r.k.events.count(('wait',12)),1);self.assertEqual(r.k.events.count(('exit',12)),1)
        self.assertEqual(r.k.events[-1],('close',11))
    def test_root_pending_prevents_cleanup_even_when_job_count_zero(self):
        r=self.make_run(signaled=False,active=0)
        self.assertFalse(r.cleanup_complete());self.assertEqual(r.process,12)
        self.assertNotIn(('close',12),r.k.events)
        r.k.signaled=True;self.assertTrue(r.cleanup_complete())
    def test_descendant_accounting_is_not_ignored(self):
        r=self.make_run(active=1)
        self.assertEqual(r.poll(10)[3:],(7,1));self.assertFalse(r.cleanup_complete())
    def test_wait_exit_and_close_failures_never_prove_cleanup(self):
        for failure in ('fail_wait','fail_exit','fail_close'):
            with self.subTest(failure=failure):
                r=self.make_run();setattr(r.k,failure,True)
                with patch('ctypes.get_last_error',return_value=5,create=True):
                    with self.assertRaises(OSError):r.poll(10)
                    if failure=='fail_close':
                        with self.assertRaises(CleanupUncertain):r.cleanup_complete()
                        self.assertEqual(r.k.events.count(('wait',12)),1)
                        self.assertEqual(r.k.events.count(('exit',12)),1)
                        r.k.fail_close=False
                        with self.assertRaises(CleanupUncertain):r.close()
                        self.assertEqual(r.k.events.count(('close',12)),1)
                    self.assertNotIn(('query',11),r.k.events)
    def test_job_query_and_terminate_fail_closed(self):
        for failure in ('fail_query','fail_terminate'):
            with self.subTest(failure=failure):
                r=self.make_run(signaled=False,active=1);setattr(r.k,failure,True)
                with self.assertRaises(OSError):r.terminate()
    def test_timeout_and_cancellation_terminate_then_capture_then_account(self):
        for cancel in (False,True):
            with self.subTest(cancel=cancel):
                r=self.make_run(signaled=False,active=1)
                if cancel:
                    original=r.poll
                    def interrupt(_):raise KeyboardInterrupt()
                    r.poll=interrupt
                c=Clock();b=Backend(r)
                with self.assertRaises(KeyboardInterrupt if cancel else TimeoutError):
                    run_with_backend(['/fake'],b'',{},'/',.03,5,backend=b,now=c.now,sleep=c.sleep,cleanup_timeout=.1)
                e=r.k.events
                self.assertLess(e.index(('terminate',11)),e.index(('exit',12)))
                self.assertLess(e.index(('exit',12)),e.index(('close',12)))
                self.assertLess(e.index(('close',12)),len(e)-1)
                self.assertEqual(e[-1],('close',11));self.assertEqual(e.count(('close',12)),1)
    def test_startup_failure_releases_primary_before_drain_and_retains_job(self):
        from feedctrl.windows_job_native import _NativeRun
        r=self.make_run(signaled=False,active=1)
        def create(self,*args):
            self.root_created=True;self.root_handle=12;self.root_membership=True
            self.job=11;self.process=12;self.primary=13;self.owned=[11,12,13]
            self.k=r.k
            raise ValueError('startup')
        r.api._ok=lambda value,op: value if value else (_ for _ in ()).throw(OSError(op))
        with patch.object(_NativeRun,'_create',create):
            with self.assertRaisesRegex(ValueError,'startup'):_NativeRun(r.api,'x','x',b'',{},'/',10,100)
        e=r.k.events
        self.assertLess(e.index(('close',13)),e.index(('terminate',11)))
        self.assertLess(e.index(('exit',12)),e.index(('close',12)))
        self.assertLess(e.index(('close',12)),len(e)-1);self.assertEqual(e[-1],('close',11))

    def test_startup_primary_close_failure_is_not_retried(self):
        from feedctrl.windows_job_native import _NativeRun
        r=self.make_run(signaled=False,active=1)
        normal=r.k.CloseHandle
        def close(h):
            if h==13:
                r.k.events.append(('close',h));return False
            return normal(h)
        r.k.CloseHandle=close
        def create(self,*args):
            self.root_created=True;self.root_handle=12;self.root_membership=True
            self.job=11;self.process=12;self.primary=13;self.owned=[11,12,13]
            raise ValueError('startup')
        with patch.object(_NativeRun,'_create',create):
            with self.assertRaises(CleanupUncertain):_NativeRun(r.api,'x','x',b'',{},'/',10,100)
        self.assertEqual(r.k.events.count(('close',13)),1)
        self.assertIn(('terminate',11),r.k.events)
        self.assertIn(('close',12),r.k.events);self.assertIn(('close',11),r.k.events)
    def test_failed_termination_or_accounting_supersedes_result(self):
        for failure in ('fail_query','fail_terminate'):
            with self.subTest(failure=failure):
                r=self.make_run(signaled=False,active=1);setattr(r.k,failure,True)
                r.poll=lambda _: (_ for _ in ()).throw(KeyboardInterrupt())
                c=Clock()
                with self.assertRaises(CleanupUncertain):
                    run_with_backend(['/fake'],b'',{},'/',.03,5,backend=Backend(r),now=c.now,sleep=c.sleep,cleanup_timeout=.1)
                self.assertIn(('close',11),r.k.events)

    def test_normal_startup_close_failure_remains_uncertain(self):
        from feedctrl.windows_job_native import _NativeRun
        for handle in (13,14):  # primary or child handle closed during creation
            with self.subTest(handle=handle):
                r=self.make_run(signaled=False,active=1)
                normal=r.k.CloseHandle
                def close(h):
                    if h==handle:r.k.events.append(('close',h));return False
                    return normal(h)
                r.k.CloseHandle=close
                def create(self,*args):
                    self.root_created=True;self.root_handle=12;self.root_membership=True
                    self.job=11;self.process=12;self.primary=13;self.owned=[11,12,13,14]
                    self._close(handle)
                with patch.object(_NativeRun,'_create',create):
                    with self.assertRaises(CleanupUncertain):_NativeRun(r.api,'x','x',b'',{},'/',10,100)
                self.assertEqual(r.k.events.count(('close',handle)),1)
                self.assertIn(('close',11),r.k.events)
    def test_worker_close_failure_persists_to_cleanup(self):
        r=self.make_run();r.input_handle=13;r.owned.append(13)
        normal=r.k.CloseHandle
        def close(h):
            if h==13:r.k.events.append(('close',h));return False
            return normal(h)
        r.k.CloseHandle=close;r._pin_worker=lambda _:None;r.stop.set()
        r._writer(b'')
        self.assertEqual(r.io_error,'InputCloseError')
        with self.assertRaises(CleanupUncertain):r.close()
        self.assertEqual(r.k.events.count(('close',13)),1)

if __name__=='__main__':unittest.main()
