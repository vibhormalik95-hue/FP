"""Opt-in bounded lifecycle observations for an explicitly supplied backend.

This module launches nothing and retains no stream bytes, arguments or errors.
It is not connected to a live launcher or an acceptance decision.
"""
from copy import deepcopy

MAX_COUNT = 2**31 - 1
MAX_BYTES = 2_000_001
MAX_EXIT = 2**32 - 1


def _note(facts, key, value):
    try:
        facts[key] = value
    except Exception:
        pass  # Diagnostics must not replace the control loop's outcome.


class LifecycleProbe:
    """Wrap one backend invocation; the caller supplies the unchanged control loop."""

    __slots__ = ('_backend', '_run', '_facts', '_used')

    def __init__(self, backend):
        self._backend = backend
        self._used = False
        self._facts = {
            'launch': 'not_called', 'poll_calls': 0, 'poll_count_saturated': False,
            'stdout_bytes_observed': 0, 'stdout_bytes_seen': False, 'stdout_bytes_saturated': False,
            'last_stdin_done': None, 'last_stdout_eof': None,
            'last_root_exit': None, 'root_exit_seen': False, 'last_job_members': None,
            'terminate': 'not_called', 'cleanup_calls': 0,
            'cleanup_count_saturated': False, 'last_cleanup_complete': None,
            'finish_io': 'not_called', 'check_io': 'not_called', 'close': 'not_called',
        }
        # Allocate the proxy before launch, so successful launch never depends on
        # constructing a new object before the control loop takes ownership.
        self._run = _RunProxy(self._facts)

    def snapshot(self):
        """Return only a detached, fixed-shape metadata snapshot."""
        return deepcopy(self._facts)

    def launch(self, *args, **kwargs):
        if self._used:
            raise ValueError('Lifecycle probe is single-use')
        self._used = True
        _note(self._facts, 'launch', 'entered')
        try:
            run = self._backend.launch(*args, **kwargs)
        except BaseException:
            _note(self._facts, 'launch', 'raised')
            raise
        if run is None:
            _note(self._facts, 'launch', 'returned_none')
            return None
        self._run._wrapped = run
        _note(self._facts, 'launch', 'returned')
        return self._run


class _RunProxy:
    __slots__ = ('_wrapped', '_facts')

    def __init__(self, facts):
        self._wrapped = None
        self._facts = facts

    def _increment(self, key, saturated):
        try:
            n = self._facts[key]
            if n < MAX_COUNT:
                self._facts[key] = n + 1
            else:
                self._facts[saturated] = True
        except Exception:
            pass

    def poll(self, *args, **kwargs):
        self._increment('poll_calls', 'poll_count_saturated')
        value = self._wrapped.poll(*args, **kwargs)
        try:
            if type(value) is tuple and len(value) == 5:
                chunk, stdin_done, eof, root_exit, active = value
                if type(chunk) is bytes:
                    total = self._facts['stdout_bytes_observed'] + len(chunk)
                    self._facts['stdout_bytes_observed'] = min(total, MAX_BYTES)
                    self._facts['stdout_bytes_seen'] = True
                    if total > MAX_BYTES:
                        self._facts['stdout_bytes_saturated'] = True
                if type(stdin_done) is bool:
                    self._facts['last_stdin_done'] = stdin_done
                if type(eof) is bool:
                    self._facts['last_stdout_eof'] = eof
                if root_exit is None or type(root_exit) is int and 0 <= root_exit <= MAX_EXIT:
                    self._facts['last_root_exit'] = root_exit
                    self._facts['root_exit_seen'] = True
                if type(active) is int and 0 <= active <= MAX_COUNT:
                    self._facts['last_job_members'] = active
        except Exception:
            pass
        return value

    def terminate(self, *args, **kwargs):
        try:
            value = self._wrapped.terminate(*args, **kwargs)
        except BaseException:
            _note(self._facts, 'terminate', 'raised')
            raise
        _note(self._facts, 'terminate', 'returned')
        return value

    def cleanup_complete(self, *args, **kwargs):
        self._increment('cleanup_calls', 'cleanup_count_saturated')
        value = self._wrapped.cleanup_complete(*args, **kwargs)
        if type(value) is bool:
            _note(self._facts, 'last_cleanup_complete', value)
        return value

    def finish_io(self, *args, **kwargs):
        try:
            value = self._wrapped.finish_io(*args, **kwargs)
        except BaseException:
            _note(self._facts, 'finish_io', 'raised')
            raise
        _note(self._facts, 'finish_io', 'true' if value is True else
              'false' if value is False else 'other')
        return value

    def check_io(self, *args, **kwargs):
        try:
            value = self._wrapped.check_io(*args, **kwargs)
        except BaseException:
            _note(self._facts, 'check_io', 'raised')
            raise
        _note(self._facts, 'check_io', 'returned')
        return value

    def close(self, *args, **kwargs):
        try:
            value = self._wrapped.close(*args, **kwargs)
        except BaseException:
            _note(self._facts, 'close', 'raised')
            raise
        _note(self._facts, 'close', 'returned')
        return value
