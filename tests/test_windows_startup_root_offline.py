"""Fake Win32 calls only: no native libraries, processes, threads or sockets."""
import ctypes
from ctypes import wintypes as w
import unittest
from unittest.mock import patch

from feedctrl.windows_job_native import WindowsBackend, _NativeRun
from feedctrl.windows_job_runner import CleanupUncertain, WindowsRunnerError


class Clock:
    def __init__(self):self.t=0
    def now(self):return self.t
    def sleep(self,seconds):self.t+=seconds


class Function:
    def __init__(self,kernel,name):self.kernel=kernel;self.name=name
    def __call__(self,*args):return self.kernel.call(self.name,*args)


class Kernel:
    """Every declared function is a Python fake, including CreateProcessW."""
    def __init__(self):
        self.events=[];self.overrides={};self.contained=False;self.active=0
        self.signaled=False;self.root=12;self.primary=13;self.next_pipe=21
        self.resume=1;self.signal_after_terminate=True;self.exit_code=9
        self.api=None
    def __getattr__(self,name):
        f=Function(self,name);setattr(self,name,f);return f
    def call(self,name,*args):
        # Pointer arguments are kept out of the trace; exact handle values remain.
        self.events.append((name,args[0] if args and isinstance(args[0],int) else None))
        if name in self.overrides:return self.overrides[name](*args)
        if name=='CreateJobObjectW':return 11
        if name=='CreatePipe':
            for p in args[:2]:
                ctypes.cast(p,ctypes.POINTER(w.HANDLE)).contents.value=self.next_pipe
                self.next_pipe+=1
        elif name=='CreateFileW':return 25
        elif name=='InitializeProcThreadAttributeList':
            ctypes.cast(args[3],ctypes.POINTER(ctypes.c_size_t)).contents.value=8
        elif name=='CreateProcessW':
            pi=ctypes.cast(args[-1],ctypes.POINTER(self.api.PI)).contents
            pi.hProcess=self.root;pi.hThread=self.primary
        elif name=='IsProcessInJob':
            ctypes.cast(args[2],ctypes.POINTER(w.BOOL)).contents.value=self.contained
        elif name=='ResumeThread':return self.resume
        elif name=='QueryInformationJobObject':
            ctypes.cast(args[2],ctypes.POINTER(self.api.ACCOUNT)).contents.ActiveProcesses=self.active
        elif name=='TerminateJobObject':
            self.active=0
            if self.contained:self.signaled=True
        elif name=='WaitForSingleObject':return 0 if self.signaled else 258
        elif name=='GetExitCodeProcess':
            ctypes.cast(args[1],ctypes.POINTER(w.DWORD)).contents.value=self.exit_code
        elif name=='TerminateProcess':
            if self.signal_after_terminate:self.signaled=True
        return True


class FakeThread:
    def __init__(self,*,target,args=(),daemon=False):self.run=target.__self__;self.name=target.__name__[1:]
    def start(self):
        self.run.thread_handles[self.name]=self.run._own(31 if self.name=='writer' else 32)
        self.run.thread_ready[self.name].set()
    def is_alive(self):return False


class StartupRootTests(unittest.TestCase):
    def setUp(self):
        self.api=WindowsBackend.__new__(WindowsBackend);self.api.k=Kernel();self.api._declare()
        self.k=self.api.k;self.k.api=self.api;self.clock=Clock();self.run=None
        self.stack=[]
        for p in (patch('ctypes.get_last_error',return_value=5,create=True),
                  patch('feedctrl.windows_job_native.time.monotonic',self.clock.now),
                  patch('feedctrl.windows_job_native.time.sleep',self.clock.sleep),
                  patch('feedctrl.windows_job_native.threading.Thread',FakeThread)):
            p.start();self.addCleanup(p.stop)

    def construct(self,after_create=None):
        original=_NativeRun._create
        def create(run,*args):
            self.run=run
            original(run,*args)
            if after_create:after_create(run)
        with patch.object(_NativeRun,'_create',create):
            return _NativeRun(self.api,'fake.exe','fake.exe',b'',{},'/',10,100)

    def calls(self,name):return [h for op,h in self.k.events if op==name]
    def uncertain(self,after_create=None):
        with self.assertRaises(CleanupUncertain) as caught:self.construct(after_create)
        self.assertIsNotNone(caught.exception.__cause__)
        self.assertIn(11,self.calls('CloseHandle'))
        self.assertTrue(self.run.stop.is_set())
        return caught.exception

    def test_outside_empty_job_terminates_exact_handle_once_then_rethrows_original(self):
        with self.assertRaisesRegex(WindowsRunnerError,'not assigned') as caught:self.construct()
        self.assertNotIsInstance(caught.exception,CleanupUncertain)
        self.assertEqual(self.calls('TerminateProcess'),[12]);self.assertEqual(self.calls('TerminateJobObject'),[])
        self.assertEqual(self.calls('ResumeThread'),[]);self.assertIs(self.run.root_membership,False)
        e=self.k.events
        self.assertLess(e.index(('QueryInformationJobObject',11)),e.index(('TerminateProcess',12)))
        self.assertLess(e.index(('WaitForSingleObject',12)),e.index(('TerminateProcess',12)))
        self.assertLess(e.index(('GetExitCodeProcess',12)),e.index(('CloseHandle',12)))
        self.assertLess(e.index(('CloseHandle',12)),e.index(('CloseHandle',11)))
        self.assertEqual(self.run.root_exit_code,9);self.assertTrue(self.run.root_released)
        self.assertEqual(self.calls('CloseHandle').count(12),1)

    def test_membership_api_failure_cannot_turn_unknown_into_inside(self):
        def failure(h,j,p):
            ctypes.cast(p,ctypes.POINTER(w.BOOL)).contents.value=True
            return False
        self.k.overrides['IsProcessInJob']=failure
        with self.assertRaisesRegex(OSError,'IsProcessInJob'):self.construct()
        self.assertIsNone(self.run.root_membership);self.assertEqual(self.calls('TerminateProcess'),[12])

    def test_membership_api_exception_stays_unknown(self):
        self.k.overrides['IsProcessInJob']=lambda *a: (_ for _ in ()).throw(ValueError('membership'))
        with self.assertRaisesRegex(ValueError,'membership'):self.construct()
        self.assertIsNone(self.run.root_membership);self.assertEqual(self.calls('TerminateProcess'),[12])

    def test_failure_before_membership_check_cleans_root_but_failed_close_stays_uncertain(self):
        self.k.overrides['CloseHandle']=lambda h:h!=21
        self.uncertain()
        self.assertEqual(self.calls('IsProcessInJob'),[]);self.assertIsNone(self.run.root_membership)
        self.assertEqual(self.calls('TerminateProcess'),[12]);self.assertEqual(self.calls('CloseHandle').count(21),1)

    def test_invalid_primary_handle_still_cleans_owned_root(self):
        self.k.primary=0
        with self.assertRaisesRegex(OSError,'Invalid Windows handle'):self.construct()
        self.assertIsNone(self.run.root_membership);self.assertEqual(self.calls('TerminateProcess'),[12])

    def test_job_query_failure_does_not_skip_root_io_or_close(self):
        self.k.overrides['QueryInformationJobObject']=lambda *a:False
        self.uncertain();self.assertEqual(self.calls('TerminateProcess'),[12])
        self.assertTrue(self.run.root_released)

    def test_job_termination_failure_does_not_skip_root_io_or_close(self):
        self.k.active=1;self.k.overrides['TerminateJobObject']=lambda *a:False
        self.uncertain();self.assertEqual(self.calls('TerminateProcess'),[12])
        self.assertTrue(self.run.root_released)
        self.assertLess(self.k.events.index(('TerminateJobObject',11)),self.k.events.index(('TerminateProcess',12)))

    def test_already_exited_root_does_not_terminate(self):
        self.k.signaled=True
        with self.assertRaisesRegex(WindowsRunnerError,'not assigned'):self.construct()
        self.assertEqual(self.calls('TerminateProcess'),[]);self.assertEqual(self.calls('GetExitCodeProcess'),[12])

    def test_asynchronous_termination_waits_until_signaled(self):
        self.k.signal_after_terminate=False
        def wait(h,delay):return 0 if self.clock.t>=.02 else 258
        self.k.overrides['WaitForSingleObject']=wait
        with self.assertRaisesRegex(WindowsRunnerError,'not assigned'):self.construct()
        self.assertGreaterEqual(self.clock.t,.02);self.assertEqual(self.calls('TerminateProcess'),[12])
        self.assertEqual(self.calls('GetExitCodeProcess'),[12]);self.assertTrue(self.run.root_released)

    def test_perpetual_pending_root_times_out_even_with_empty_job(self):
        self.k.signal_after_terminate=False
        self.uncertain();self.assertGreaterEqual(self.clock.t,3)
        self.assertEqual(self.calls('TerminateProcess'),[12]);self.assertEqual(self.calls('GetExitCodeProcess'),[])
        with self.assertRaises(CleanupUncertain):self.run.cleanup_complete()

    def test_termination_false_exception_and_exit_race_remain_uncertain(self):
        for error in (False,PermissionError('access denied'),RuntimeError('termination')):
            for race in (False,True):
                with self.subTest(error=error,race=race):
                    self.setUp()
                    def terminate(*args):
                        self.k.signaled=race
                        if isinstance(error,BaseException):raise error
                        return error
                    self.k.overrides['TerminateProcess']=terminate
                    self.uncertain();self.assertEqual(self.calls('TerminateProcess'),[12])
                    before=list(self.k.events)
                    with self.assertRaises(CleanupUncertain):self.run._terminate_uncontained_startup_root()
                    self.assertEqual(self.k.events,before)
                    self.assertEqual(self.run.root_released,race)

    def test_observation_failures_remain_uncertain_without_termination(self):
        for name in ('WaitForSingleObject','GetExitCodeProcess'):
            for raises in (False,True):
                with self.subTest(name=name,raises=raises):
                    self.setUp();self.k.signaled=True
                    def fail(*args):
                        if raises:raise OSError('fake observation error')
                        return 0xffffffff if name=='WaitForSingleObject' else False
                    self.k.overrides[name]=fail
                    self.uncertain();self.assertEqual(self.calls('TerminateProcess'),[])

    def test_failed_root_close_never_reuses_handle_for_any_operation(self):
        for raises in (False,True):
            with self.subTest(raises=raises):
                self.setUp();self.k.signaled=True
                def close(h):
                    if h==12:
                        if raises:raise OSError('close error')
                        return False
                    return True
                self.k.overrides['CloseHandle']=close;self.uncertain()
                index=self.k.events.index(('CloseHandle',12))
                for operation in (self.run.cleanup_complete,self.run._terminate_uncontained_startup_root,self.run.close):
                    with self.assertRaises(CleanupUncertain):operation()
                self.assertFalse(any(h==12 for _,h in self.k.events[index+1:]))

    def test_failed_job_close_is_never_queried_terminated_or_closed_again(self):
        self.k.overrides['CloseHandle']=lambda h:h!=11
        self.uncertain();index=self.k.events.index(('CloseHandle',11))
        with self.assertRaises(CleanupUncertain):self.run.terminate()
        with self.assertRaises(CleanupUncertain):self.run.cleanup_complete()
        with self.assertRaises(CleanupUncertain):self.run.close()
        self.assertFalse(any(h==11 for _,h in self.k.events[index+1:]))

    def test_resume_attempt_excludes_every_return_and_exception(self):
        for result in (0,1,2,0xffffffff,RuntimeError('resume'),KeyboardInterrupt()):
            with self.subTest(result=result):
                self.setUp();self.k.contained=True;self.k.active=1
                def resume(h):
                    self.assertTrue(self.run.resume_attempted)
                    # Deliberately clear membership to challenge the independent
                    # resume latch, including failure after a successful return.
                    self.run.root_membership=None
                    if isinstance(result,BaseException):raise result
                    return result
                self.k.overrides['ResumeThread']=resume
                def later(run):raise ValueError('after successful resume')
                with self.assertRaises(BaseException):self.construct(later)
                self.assertTrue(self.run.resume_attempted);self.assertEqual(self.calls('ResumeThread'),[13])
                self.assertEqual(self.calls('TerminateProcess'),[]);self.assertEqual(self.calls('TerminateJobObject'),[11])

    def test_created_but_unowned_or_replaced_root_remains_uncertain_without_root_operations(self):
        for lost in ('invalid_return','not_retained','replacement'):
            with self.subTest(lost=lost):
                self.setUp()
                if lost=='invalid_return':self.k.root=0
                else:
                    def membership(*args):
                        self.run.owned.remove(12)
                        if lost=='replacement':self.run.process=99;self.run.owned.append(99)
                        raise OSError('lost ownership')
                    self.k.overrides['IsProcessInJob']=membership
                self.uncertain();self.assertTrue(self.run.root_created)
                self.assertEqual(self.calls('TerminateProcess'),[])
                self.assertEqual(self.calls('WaitForSingleObject'),[]);self.assertEqual(self.calls('GetExitCodeProcess'),[])

    def test_no_created_process_means_no_root_operation(self):
        self.k.overrides['CreateProcessW']=lambda *a:False
        with self.assertRaisesRegex(OSError,'CreateProcessW'):self.construct()
        self.assertFalse(self.run.root_created)
        for name in ('TerminateProcess','WaitForSingleObject','GetExitCodeProcess','ResumeThread'):
            self.assertEqual(self.calls(name),[])
        self.assertNotIn(12,self.calls('CloseHandle'))

    def test_repeated_cleanup_never_repeats_root_termination_or_release(self):
        with self.assertRaisesRegex(WindowsRunnerError,'not assigned'):self.construct()
        before=list(self.k.events)
        for _ in range(3):
            self.run._terminate_uncontained_startup_root();self.assertTrue(self.run.cleanup_complete())
            self.run.finish_io(100);self.run.close()
        self.assertEqual(self.k.events,before)

    def test_known_contained_root_uses_only_job_cleanup_before_resume(self):
        self.k.contained=True;self.k.active=1
        with patch.object(FakeThread,'start',side_effect=RuntimeError('worker start')):
            with self.assertRaisesRegex(RuntimeError,'worker start'):self.construct()
        self.assertFalse(self.run.resume_attempted);self.assertIs(self.run.root_membership,True)
        self.assertEqual(self.calls('TerminateProcess'),[]);self.assertEqual(self.calls('TerminateJobObject'),[11])

    def test_normal_contained_creation_and_cleanup_remain_available_only_to_fake_backend(self):
        self.k.contained=True;self.k.active=1
        run=self.construct();self.assertFalse(run.startup_failed);self.assertTrue(run.resume_attempted)
        run._terminate_uncontained_startup_root();self.assertEqual(self.calls('TerminateProcess'),[])
        run.terminate();self.assertTrue(run.cleanup_complete());self.assertTrue(run.finish_io(100));run.close()
        self.assertEqual(self.calls('ResumeThread'),[13]);self.assertEqual(self.calls('CloseHandle').count(12),1)

    def test_io_and_final_handle_errors_still_supersede_clean_root(self):
        for kind in ('false','exception','pipe_close'):
            with self.subTest(kind=kind):
                self.setUp()
                if kind=='pipe_close':
                    self.k.overrides['CloseHandle']=lambda h:h!=22
                    self.uncertain()
                else:
                    kwargs={'return_value':False} if kind=='false' else {'side_effect':OSError('I/O cleanup')}
                    with patch.object(_NativeRun,'finish_io',**kwargs):
                        with self.assertRaises(CleanupUncertain):self.construct()
                self.assertTrue(self.run.root_released);self.assertIn(11,self.calls('CloseHandle'))


if __name__=='__main__':unittest.main()
