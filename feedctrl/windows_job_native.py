"""Experimental, unactivated Windows native Job Object backend.

Windows APIs are loaded only by WindowsBackend(). No executable is run on import.
Not yet verified on Windows. Job objects handle ordinary descendant processes; they
are not a sandbox against WMI/alternate-parent brokers or hostile same-user code.
"""
import ctypes
from ctypes import wintypes as w
import os
import subprocess
import threading
import time

from feedctrl.windows_job_runner import CleanupUncertain, WindowsRunnerError

# Win32 declarations are constructed only on Windows so Linux can import this file.
class WindowsBackend:
    def __init__(self):
        if os.name != 'nt': raise WindowsRunnerError('Windows is required')
        self.k=ctypes.WinDLL('kernel32',use_last_error=True)
        self._declare()

    def _declare(self):
        k=self.k; H=w.HANDLE; P=ctypes.c_void_p; D=w.DWORD; B=w.BOOL
        SIZE=ctypes.c_size_t
        class SA(ctypes.Structure):
            _fields_=[('nLength',D),('lpSecurityDescriptor',P),('bInheritHandle',B)]
        class SI(ctypes.Structure):
            _fields_=[('cb',D),('lpReserved',w.LPWSTR),('lpDesktop',w.LPWSTR),('lpTitle',w.LPWSTR),
              ('dwX',D),('dwY',D),('dwXSize',D),('dwYSize',D),('dwXCountChars',D),('dwYCountChars',D),
              ('dwFillAttribute',D),('dwFlags',D),('wShowWindow',w.WORD),('cbReserved2',w.WORD),
              ('lpReserved2',P),('hStdInput',H),('hStdOutput',H),('hStdError',H)]
        class SIX(ctypes.Structure):_fields_=[('StartupInfo',SI),('lpAttributeList',P)]
        class PI(ctypes.Structure):_fields_=[('hProcess',H),('hThread',H),('dwProcessId',D),('dwThreadId',D)]
        class BASIC(ctypes.Structure):
            _fields_=[('PerProcessUserTimeLimit',ctypes.c_longlong),('PerJobUserTimeLimit',ctypes.c_longlong),
              ('LimitFlags',D),('MinimumWorkingSetSize',SIZE),('MaximumWorkingSetSize',SIZE),
              ('ActiveProcessLimit',D),('Affinity',SIZE),('PriorityClass',D),('SchedulingClass',D)]
        class IOC(ctypes.Structure):
            _fields_=[(x,ctypes.c_ulonglong) for x in ('ReadOperationCount','WriteOperationCount',
                'OtherOperationCount','ReadTransferCount','WriteTransferCount','OtherTransferCount')]
        class EXT(ctypes.Structure):
            _fields_=[('BasicLimitInformation',BASIC),('IoInfo',IOC),('ProcessMemoryLimit',SIZE),
              ('JobMemoryLimit',SIZE),('PeakProcessMemoryUsed',SIZE),('PeakJobMemoryUsed',SIZE)]
        class ACCOUNT(ctypes.Structure):
            _fields_=[(x,ctypes.c_longlong) for x in ('TotalUserTime','TotalKernelTime',
              'ThisPeriodTotalUserTime','ThisPeriodTotalKernelTime')]+[(x,D) for x in
              ('TotalPageFaultCount','TotalProcesses','ActiveProcesses','TotalTerminatedProcesses')]
        self.SA,self.SIX,self.PI,self.EXT,self.ACCOUNT=SA,SIX,PI,EXT,ACCOUNT
        defs={
          'CreateJobObjectW':([P,w.LPCWSTR],H), 'SetInformationJobObject':([H,D,P,D],B),
          'QueryInformationJobObject':([H,D,P,D,ctypes.POINTER(D)],B),
          'TerminateJobObject':([H,w.UINT],B), 'TerminateProcess':([H,w.UINT],B), 'CloseHandle':([H],B),
          'CreatePipe':([ctypes.POINTER(H),ctypes.POINTER(H),ctypes.POINTER(SA),D],B),
          'SetHandleInformation':([H,D,D],B),
          'CreateFileW':([w.LPCWSTR,D,D,ctypes.POINTER(SA),D,D,H],H),
          'InitializeProcThreadAttributeList':([P,D,D,ctypes.POINTER(SIZE)],B),
          'UpdateProcThreadAttribute':([P,D,SIZE,P,SIZE,P,P],B),
          'DeleteProcThreadAttributeList':([P],None),
          'CreateProcessW':([w.LPCWSTR,w.LPWSTR,P,P,B,D,P,w.LPCWSTR,ctypes.POINTER(SIX),ctypes.POINTER(PI)],B),
          'IsProcessInJob':([H,H,ctypes.POINTER(B)],B), 'ResumeThread':([H],D),
          'WaitForSingleObject':([H,D],D), 'GetExitCodeProcess':([H,ctypes.POINTER(D)],B),
          'ReadFile':([H,P,D,ctypes.POINTER(D),P],B), 'WriteFile':([H,P,D,ctypes.POINTER(D),P],B),
          'GetCurrentProcess':([],H), 'GetCurrentThread':([],H),
          'DuplicateHandle':([H,H,H,ctypes.POINTER(H),D,B,D],B),
          'CancelSynchronousIo':([H],B),
        }
        for name,(args,result) in defs.items():
            f=getattr(k,name);f.argtypes=args;f.restype=result

    def _ok(self,value,op):
        if not value:raise OSError(ctypes.get_last_error(),op)
        return value

    def launch(self,argv,input_bytes,env,cwd,output_limit,deadline):
        if not os.path.isabs(argv[0]) or not argv[0].lower().endswith('.exe'):
            raise ValueError('Absolute native executable required')
        if not os.path.isabs(cwd) or any('\x00' in x for x in argv):raise ValueError('Invalid process arguments')
        if not all(isinstance(k,str) and isinstance(v,str) and k and '=' not in k and '\x00' not in k+v for k,v in env.items()):
            raise ValueError('Invalid environment')
        command=subprocess.list2cmdline(argv)
        if len(command)>32766:raise ValueError('Windows command line too long')
        return _NativeRun(self,argv[0],command,input_bytes,env,cwd,output_limit,deadline)


class _NativeRun:
    def __init__(self,api,exe,cmd,payload,env,cwd,limit,deadline):
        self.api=api;self.k=api.k;self.job=None;self.process=None;self.primary=None
        self.root_exit_code=None;self.root_release_failed=False;self.close_failed=False
        self.root_created=False;self.root_handle=None;self.root_released=False
        self.root_membership=None  # Unknown until IsProcessInJob succeeds.
        self.resume_attempted=False;self.startup_failed=False
        self.root_termination_attempted=False;self.root_cleanup_failed=False
        self.input_handle=None;self.output_handle=None;self.threads=[];self.thread_handles={}
        self.thread_ready={'writer':threading.Event(),'reader':threading.Event()}
        self.lock=threading.Lock();self.stop=threading.Event();self.data=bytearray()
        self.input_done=False;self.output_eof=False;self.io_error=None;self.limit=limit
        self.owned=[];self.child=[];self.attribute=None;self.attribute_initialized=False
        try:self._create(exe,cmd,payload,env,cwd,deadline)
        except BaseException as exc:
            self.startup_failed=True
            errors=[]
            # A failed startup may still own the suspended primary-thread handle.
            # Release it before waiting for job accounting, but never hide failure.
            if self.primary is not None:
                try:self._close(self.primary);self.primary=None
                except BaseException as failure:errors.append(type(failure).__name__)
            try:self.terminate()
            except BaseException as failure:errors.append(type(failure).__name__)
            # Job cleanup cannot reach a never-resumed root outside that job.
            # Keep this independent so a job error does not skip owned-root cleanup.
            try:self._terminate_uncontained_startup_root()
            except BaseException as failure:errors.append(type(failure).__name__)
            deadline=time.monotonic()+3
            try:
                while not self.cleanup_complete():
                    if time.monotonic()>=deadline:raise TimeoutError('Startup job drain timed out')
                    time.sleep(.01)
            except BaseException as failure:errors.append(type(failure).__name__)
            try:
                if not self.finish_io(deadline):errors.append('UnconfirmedIoCompletion')
            except BaseException as failure:errors.append(type(failure).__name__)
            try:self.close()
            except BaseException as failure:errors.append(type(failure).__name__)
            if errors:raise CleanupUncertain('Windows startup cleanup unconfirmed') from exc
            raise

    def _own(self,h):
        if not h or h==ctypes.c_void_p(-1).value:raise OSError(ctypes.get_last_error(),'Invalid Windows handle')
        self.owned.append(h);return h
    def _close(self,h):
        if h in self.owned:
            # A failed close leaves ownership uncertain. Never try the same value
            # again: it may no longer name the original object by then.
            self.owned.remove(h)
            try:self.api._ok(self.k.CloseHandle(h),'CloseHandle')
            except BaseException:
                self.close_failed=True
                if h==self.root_handle:self.root_release_failed=True
                raise
    def _pipe(self):
        a,b=w.HANDLE(),w.HANDLE();sa=self.api.SA(ctypes.sizeof(self.api.SA),None,True)
        self.api._ok(self.k.CreatePipe(ctypes.byref(a),ctypes.byref(b),ctypes.byref(sa),0),'CreatePipe')
        return self._own(a.value),self._own(b.value)

    def _create(self,exe,cmd,payload,env,cwd,deadline):
        k=self.k;api=self.api; D=w.DWORD
        self.job=self._own(k.CreateJobObjectW(None,None))
        limits=api.EXT();limits.BasicLimitInformation.LimitFlags=0x2000  # KILL_ON_JOB_CLOSE only
        api._ok(k.SetInformationJobObject(self.job,9,ctypes.byref(limits),ctypes.sizeof(limits)),'SetInformationJobObject')
        stdin_r,stdin_w=self._pipe();stdout_r,stdout_w=self._pipe()
        self.input_handle,self.output_handle=stdin_w,stdout_r
        for h in (stdin_w,stdout_r):api._ok(k.SetHandleInformation(h,1,0),'SetHandleInformation')
        sa=api.SA(ctypes.sizeof(api.SA),None,True)
        stderr=self._own(k.CreateFileW('NUL',0x40000000,3,ctypes.byref(sa),3,0x80,None))
        self.child=[stdin_r,stdout_w,stderr]
        size=ctypes.c_size_t()
        k.InitializeProcThreadAttributeList(None,2,0,ctypes.byref(size))
        if not size.value:raise OSError(ctypes.get_last_error(),'Attribute list size')
        self.attribute=ctypes.create_string_buffer(size.value)
        api._ok(k.InitializeProcThreadAttributeList(self.attribute,2,0,ctypes.byref(size)),'InitializeProcThreadAttributeList')
        self.attribute_initialized=True
        self.attribute_jobs=(w.HANDLE*1)(self.job);self.attribute_handles=(w.HANDLE*3)(*self.child)
        jobs=self.attribute_jobs;handles=self.attribute_handles
        api._ok(k.UpdateProcThreadAttribute(self.attribute,0,0x0002000D,ctypes.byref(jobs),ctypes.sizeof(jobs),None,None),'Job list')
        api._ok(k.UpdateProcThreadAttribute(self.attribute,0,0x00020002,ctypes.byref(handles),ctypes.sizeof(handles),None,None),'Handle list')
        startup=api.SIX();startup.StartupInfo.cb=ctypes.sizeof(startup);startup.StartupInfo.dwFlags=0x100
        startup.StartupInfo.hStdInput=stdin_r;startup.StartupInfo.hStdOutput=stdout_w;startup.StartupInfo.hStdError=stderr
        startup.lpAttributeList=ctypes.cast(self.attribute,ctypes.c_void_p)
        environment='\x00'.join(f'{key}={value}' for key,value in sorted(env.items(),key=lambda kv:kv[0].upper()))+'\x00\x00'
        envbuf=ctypes.create_unicode_buffer(environment);cmdbuf=ctypes.create_unicode_buffer(cmd);pi=api.PI()
        flags=0x00000004|0x00000400|0x00080000|0x08000000
        api._ok(k.CreateProcessW(exe,cmdbuf,None,None,True,flags,envbuf,cwd,ctypes.byref(startup),ctypes.byref(pi)),'CreateProcessW')
        self.root_created=True;self.root_handle=pi.hProcess
        self.process=self._own(self.root_handle);self.primary=self._own(pi.hThread)
        for h in list(self.child):self._close(h)
        self.child=[]
        contained=w.BOOL()
        api._ok(k.IsProcessInJob(self.process,self.job,ctypes.byref(contained)),'IsProcessInJob')
        self.root_membership=bool(contained.value)
        if not self.root_membership:raise WindowsRunnerError('Process was not assigned to job')
        self.threads=[threading.Thread(target=self._writer,args=(payload,),daemon=True),
                      threading.Thread(target=self._reader,daemon=True)]
        for t in self.threads:t.start()
        for name in ('writer','reader'):
            remaining=deadline-time.monotonic()
            if remaining <= 0 or not self.thread_ready[name].wait(min(1,remaining)):
                raise TimeoutError('I/O worker initialization deadline exceeded')
        with self.lock:
            if self.io_error or set(self.thread_handles)!={'writer','reader'}:
                raise WindowsRunnerError('I/O worker initialization failed')
        if time.monotonic()>=deadline:raise TimeoutError('Startup deadline exceeded before resume')
        # Even an exception or unexpected return may follow an effective resume.
        self.resume_attempted=True
        previous=k.ResumeThread(self.primary)
        if previous != 1:raise WindowsRunnerError('Primary thread did not resume as expected')
        self._close(self.primary);self.primary=None

    def _pin_worker(self,name):
        handle=w.HANDLE()
        try:
            proc=self.k.GetCurrentProcess();current=self.k.GetCurrentThread()
            self.api._ok(self.k.DuplicateHandle(proc,current,proc,ctypes.byref(handle),0,False,2),
                         'Duplicate worker thread handle')
            with self.lock:
                self.thread_handles[name]=self._own(handle.value)
        finally:
            self.thread_ready[name].set()

    def _writer(self,payload):
        try:
            self._pin_worker('writer')
            if not self.stop.is_set():
                count=w.DWORD();buf=ctypes.create_string_buffer(payload)
                self.api._ok(self.k.WriteFile(self.input_handle,buf,len(payload),ctypes.byref(count),None),'WriteFile')
                if count.value != len(payload):raise WindowsRunnerError('Short stdin write')
            with self.lock:self.input_done=True
        except BaseException as exc:
            if not self.stop.is_set():
                with self.lock:self.io_error=type(exc).__name__
        finally:
            try:self._close(self.input_handle);self.input_handle=None
            except BaseException:
                with self.lock:self.io_error='InputCloseError'

    def _reader(self):
        try:
            self._pin_worker('reader')
            while not self.stop.is_set():
                buf=ctypes.create_string_buffer(8192);count=w.DWORD()
                ok=self.k.ReadFile(self.output_handle,buf,len(buf),ctypes.byref(count),None)
                if not ok:
                    if ctypes.get_last_error()==109:
                        with self.lock:self.output_eof=True
                        return
                    raise OSError(ctypes.get_last_error(),'ReadFile')
                if count.value==0:
                    with self.lock:self.output_eof=True
                    return
                with self.lock:
                    remaining=self.limit+1-len(self.data)
                    self.data.extend(buf.raw[:min(count.value,max(0,remaining))])
                    if len(self.data)>self.limit:return
        except BaseException as exc:
            if not self.stop.is_set():
                with self.lock:self.io_error=type(exc).__name__
        finally:
            try:self._close(self.output_handle);self.output_handle=None
            except BaseException:
                with self.lock:self.io_error='OutputCloseError'

    def active_count(self):
        if not self.job:return 0
        if self.job not in self.owned:raise CleanupUncertain('Job handle ownership unconfirmed')
        info=self.api.ACCOUNT()
        self.api._ok(self.k.QueryInformationJobObject(self.job,1,ctypes.byref(info),ctypes.sizeof(info),None),'QueryInformationJobObject')
        return info.ActiveProcesses
    def _observe_root(self):
        # Retain the exact process handle until the exit is signaled and its code
        # captured. Never use its value again after any release attempt.
        if self.root_release_failed:
            raise CleanupUncertain('Root process handle release unconfirmed')
        if not self.root_created:return None
        if self.root_released:return self.root_exit_code
        if self.process is None or self.process!=self.root_handle or self.process not in self.owned:
            self.root_cleanup_failed=True
            raise CleanupUncertain('Root process handle ownership unconfirmed')
        try:
            status=self.k.WaitForSingleObject(self.process,0)
            if status==258:return None
            if status!=0:raise OSError(ctypes.get_last_error(),'Process wait failed')
            code=w.DWORD()
            self.api._ok(self.k.GetExitCodeProcess(self.process,ctypes.byref(code)),'GetExitCodeProcess')
            self.root_exit_code=code.value
            self._close(self.process)
        except BaseException:
            self.root_cleanup_failed=True
            raise
        self.process=None;self.root_released=True
        return self.root_exit_code
    def _terminate_uncontained_startup_root(self):
        # Never reopen by PID, enumerate, or reach a possibly resumed root here.
        if (not self.startup_failed or not self.root_created or self.resume_attempted
                or self.root_membership is True):return
        if self.root_cleanup_failed or self.root_release_failed:
            raise CleanupUncertain('Startup root cleanup already unconfirmed')
        if self.root_termination_attempted:return
        if self._observe_root() is not None:return
        self.root_termination_attempted=True
        try:self.api._ok(self.k.TerminateProcess(self.process,1),'TerminateProcess')
        except BaseException:
            self.root_cleanup_failed=True
            raise
        # Success only requests asynchronous termination. The bounded drain must
        # still observe exit, capture its code and release this exact handle.
    def cleanup_complete(self):
        # Job accounting alone cannot prove the retained root has exited. The job
        # handle stays open until this check and I/O cleanup have completed.
        self._observe_root()
        if self.root_cleanup_failed:raise CleanupUncertain('Root cleanup previously failed')
        if self.process is not None:return False
        return self.active_count()==0
    def poll(self,remaining):
        with self.lock:
            if self.io_error:raise WindowsRunnerError('Windows pipe I/O failed: '+self.io_error)
            data=bytes(self.data[:remaining]);del self.data[:len(data)]
            done,eof=self.input_done,self.output_eof
        exit_code=self._observe_root()
        return data,done,eof,exit_code,self.active_count()
    def terminate(self):
        if self.job and self.active_count():self.api._ok(self.k.TerminateJobObject(self.job,1),'TerminateJobObject')
    def finish_io(self,deadline):
        self.stop.set()
        cancellation_failed=False
        while any(t.is_alive() for t in self.threads):
            with self.lock:
                handles=list(self.thread_handles.values())
            # Handles were duplicated by the workers themselves and remain pinned
            # until after join, so thread-ID reuse cannot target another thread.
            for handle in handles:
                if not self.k.CancelSynchronousIo(handle) and ctypes.get_last_error()!=1168:
                    cancellation_failed=True
            if time.monotonic()>=deadline:return False
            for t in self.threads:t.join(timeout=.01)
        return not cancellation_failed
    def check_io(self):
        with self.lock:
            if self.io_error:raise WindowsRunnerError('Windows pipe I/O failed: '+self.io_error)
    def close(self):
        # Closing the noninherited job is attempted even if I/O cancellation or
        # a preceding termination failed. Pending pipe handles remain owned by
        # their workers until those synchronous operations finish.
        errors=[]
        if self.job:
            try:self._close(self.job);self.job=None
            except BaseException as failure:errors.append(type(failure).__name__)
        alive=any(t.is_alive() for t in self.threads)
        if self.attribute_initialized:
            try:self.k.DeleteProcThreadAttributeList(self.attribute);self.attribute_initialized=False
            except BaseException as failure:errors.append(type(failure).__name__)
        retained=({self.input_handle,self.output_handle}|set(self.thread_handles.values())) if alive else set()
        for h in list(reversed(self.owned)):
            if h in retained or h==self.job:continue
            try:self._close(h)
            except BaseException as failure:errors.append(type(failure).__name__)
        self.process=None
        if getattr(self,'close_failed',False):errors.append('UnconfirmedHandleClose')
        if alive:errors.append('LiveIoWorkers')
        if errors:raise CleanupUncertain('Windows handles or I/O cleanup unconfirmed')
