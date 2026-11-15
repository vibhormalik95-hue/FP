"""Offline opt-in composition of a pinned probe with explicitly supplied functions.

No native backend, application, provider or runner is constructed by this module.
Only validated detached lifecycle metadata can be returned for checkpointing.
"""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

PROBE_SHA256 = '472ecd7509a4c236c73a135e45aaa354a5ac807f9a0f058bb3fb6deba7863174'
RUNNER_SHA256 = '693931dbf1b02e121a38dab0e150857b589071b347fc7f763dfa5c831d9b41b4'
_path = Path(__file__).resolve().with_name('lifecycle_probe.py')
if hashlib.sha256(_path.read_bytes()).hexdigest() != PROBE_SHA256:
    raise ValueError('Lifecycle probe identity mismatch')
_spec = importlib.util.spec_from_file_location('reviewed_lifecycle_probe', _path)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
LifecycleProbe = _module.LifecycleProbe
MAX_COUNT, MAX_BYTES, MAX_EXIT = _module.MAX_COUNT, _module.MAX_BYTES, _module.MAX_EXIT
MAX_RECORDS = 3

_FIELDS = frozenset(('launch','poll_calls','poll_count_saturated','stdout_bytes_observed',
    'stdout_bytes_seen','stdout_bytes_saturated','last_stdin_done','last_stdout_eof',
    'last_root_exit','root_exit_seen','last_job_members','terminate','cleanup_calls',
    'cleanup_count_saturated','last_cleanup_complete','finish_io','check_io','close'))
_ENUMS = {'launch': frozenset(('not_called','entered','raised','returned_none','returned')),
          'terminate': frozenset(('not_called','returned','raised')),
          'finish_io': frozenset(('not_called','true','false','other','raised')),
          'check_io': frozenset(('not_called','returned','raised')),
          'close': frozenset(('not_called','returned','raised'))}
_BOOLS = ('poll_count_saturated','stdout_bytes_seen','stdout_bytes_saturated',
          'root_exit_seen','cleanup_count_saturated')
_OPTIONAL_BOOLS = ('last_stdin_done','last_stdout_eof','last_cleanup_complete')
_REASONS = frozenset(('backend_unavailable','snapshot_unavailable','invalid_records'))


def _facts(value):
    if type(value) is not dict or set(value) != _FIELDS:
        return None
    for key, allowed in _ENUMS.items():
        if type(value[key]) is not str or value[key] not in allowed:
            return None
    if any(type(value[k]) is not bool for k in _BOOLS):
        return None
    if any(value[k] is not None and type(value[k]) is not bool for k in _OPTIONAL_BOOLS):
        return None
    for key, bound in (('poll_calls',MAX_COUNT),('cleanup_calls',MAX_COUNT),
                       ('stdout_bytes_observed',MAX_BYTES)):
        if type(value[key]) is not int or not 0 <= value[key] <= bound:
            return None
    for key, bound in (('last_root_exit',MAX_EXIT),('last_job_members',MAX_COUNT)):
        n = value[key]
        if n is not None and (type(n) is not int or not 0 <= n <= bound):
            return None
    if not value['root_exit_seen'] and value['last_root_exit'] is not None:
        return None
    if not value['stdout_bytes_seen'] and (value['stdout_bytes_observed'] != 0 or value['stdout_bytes_saturated']):
        return None
    if any(value[flag] and value[count] != maximum for flag,count,maximum in (
        ('poll_count_saturated','poll_calls',MAX_COUNT),
        ('cleanup_count_saturated','cleanup_calls',MAX_COUNT),
        ('stdout_bytes_saturated','stdout_bytes_observed',MAX_BYTES))):
        return None
    return {key: value[key] for key in sorted(_FIELDS)}


def sanitize_records(value):
    """Return a finite safe list; never copy unknown keys or invalid values."""
    if type(value) is not list or len(value) > MAX_RECORDS:
        return [{'available': False, 'reason': 'invalid_records'}]
    result = []
    for item in value:
        if type(item) is dict and set(item) == {'available','facts'} and item['available'] is True:
            facts = _facts(item['facts'])
            if facts is not None:
                result.append({'available': True, 'facts': facts})
                continue
        if (type(item) is dict and set(item) == {'available','reason'} and item['available'] is False
                and type(item['reason']) is str and item['reason'] in _REASONS):
            result.append({'available': False, 'reason': item['reason']})
        else:
            result.append({'available': False, 'reason': 'invalid_records'})
    return result


class ObservedRunner:
    """Compose one probe per call with a supplied loop and backend factory."""

    def __init__(self, control_loop, backend_factory):
        if not callable(control_loop) or not callable(backend_factory):
            raise ValueError('Explicit control loop and backend factory required')
        module = sys.modules.get(getattr(control_loop, '__module__', None))
        module_path = Path(getattr(module, '__file__', '')).resolve()
        code_path = Path(getattr(getattr(control_loop, '__code__', None), 'co_filename', '')).resolve()
        if (module is None or getattr(module, 'run_with_backend', None) is not control_loop
                or module_path != code_path or not module_path.is_file()
                or hashlib.sha256(module_path.read_bytes()).hexdigest() != RUNNER_SHA256):
            raise ValueError('Explicit control loop identity mismatch')
        self._loop, self._backend_factory = control_loop, backend_factory
        self._runner_module, self._runner_path = module, module_path
        self._records, self._attempts = [], 0

    def records(self):
        return deepcopy(self._records)

    def __call__(self, argv, input_bytes, env, cwd, timeout, maximum):
        if self._attempts >= MAX_RECORDS:
            raise ValueError('Lifecycle record limit')
        if (getattr(self._runner_module, 'run_with_backend', None) is not self._loop
                or hashlib.sha256(self._runner_path.read_bytes()).hexdigest() != RUNNER_SHA256):
            raise ValueError('Explicit control loop identity changed')
        self._attempts += 1
        probe = None
        try:
            probe = LifecycleProbe(self._backend_factory())
            return self._loop(argv, input_bytes, env, cwd, timeout, maximum, backend=probe)
        finally:
            try:
                if probe is None:
                    item = {'available': False, 'reason': 'backend_unavailable'}
                else:
                    facts = _facts(probe.snapshot())
                    item = ({'available': True, 'facts': facts} if facts is not None else
                            {'available': False, 'reason': 'snapshot_unavailable'})
                json.dumps(item, allow_nan=False)
            except BaseException:
                item = {'available': False, 'reason': 'snapshot_unavailable'}
            try:
                self._records.append(item)
            except BaseException:
                pass  # Diagnostic failure must not replace the loop's outcome.
