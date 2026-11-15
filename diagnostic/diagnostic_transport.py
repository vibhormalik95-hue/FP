"""Unintegrated opt-in stream diagnostic wrapper; never creates a runner.

The supplied runner remains responsible for process containment and cleanup.
This module does not log or persist transport content or make a model call.
"""
from copy import deepcopy
import hashlib
import math
from pathlib import Path
import re
from threading import Lock

from . import rejection_observer, stream_projection
from .stream_projection import MAX_STREAM_BYTES, project_stream

OBSERVER_SHA256 = '30f6c19924fac26ceea934ca03d79039f52ed042b4d99a641659f670ed5a1440'
MAX_RECORDS = 3  # Matches the separately bounded category scenario, not an increased allowance.
_FIXED = {
    1: '-p', 2: '--safe-mode', 3: '--tools', 4: '', 5: '--disallowedTools',
    6: 'mcp__*', 7: '--no-chrome', 8: '--no-session-persistence',
    9: '--permission-mode', 10: 'dontAsk', 11: '--permission-prompts', 12: 'none',
    13: '--max-turns', 14: '1', 15: '--settings', 16: '{"switchModelsOnFlag":false}',
    17: '--model', 19: '--effort', 21: '--max-budget-usd', 23: '--output-format',
    24: 'json', 25: '--system-prompt',
}
_ENV_FIXED = {
    'CLAUDE_CODE_MAX_RETRIES': '0',
    'CLAUDE_CODE_NONSTREAMING_TIMEOUT_RETRIES': '0',
    'MAX_STRUCTURED_OUTPUT_RETRIES': '1',
    'CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK': '1',
    'CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK': '1',
    'DISABLE_AUTOUPDATER': '1',
}
_ENV_ALLOWED = frozenset(('SYSTEMROOT', 'WINDIR', 'APPDATA', 'LOCALAPPDATA',
    'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'HOME', 'PATH', 'TEMP', 'TMP', 'TMPDIR',
    'CLAUDE_CODE_MAX_OUTPUT_TOKENS', *_ENV_FIXED))
_MODEL = re.compile(r'claude-[a-zA-Z0-9.-]{1,120}\Z')
_POSITIVE = re.compile(r'(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z')


class DiagnosticTransportError(ValueError):
    """Constant error labels, never transport content."""


def _validate(argv, input_bytes, env, cwd, timeout, maximum, runtime_mode='safe_mode'):
    if runtime_mode == 'reviewed_hooks':
        if type(argv) is not list or len(argv) != 26:
            return 'invalid_arguments'
        argv = argv[:2] + ['--safe-mode'] + argv[2:]
    elif runtime_mode != 'safe_mode':
        return 'invalid_arguments'
    if (type(argv) is not list or len(argv) != 27
            or any(not isinstance(x, str) or '\x00' in x for x in argv)
            or any(argv[i] != v for i, v in _FIXED.items())
            or not argv[0] or len(argv[0]) > 32767 or not _MODEL.fullmatch(argv[18])
            or argv[20] not in ('low', 'medium', 'high', 'max')
            or len(argv[22]) > 32 or not _POSITIVE.fullmatch(argv[22])
            or len(argv[26]) > 50000 or not argv[26].strip()):
        return 'invalid_arguments'
    budget = float(argv[22])
    if not math.isfinite(budget) or budget <= 0:
        return 'invalid_arguments'
    if (type(input_bytes) is not bytes or len(input_bytes) > 50000 or type(env) is not dict
            or not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items())
            or not set(env).issubset(_ENV_ALLOWED)
            or any(env.get(k) != v for k, v in _ENV_FIXED.items())):
        return 'invalid_environment'
    output_tokens = env.get('CLAUDE_CODE_MAX_OUTPUT_TOKENS')
    if (not isinstance(output_tokens, str) or not re.fullmatch(r'[0-9]{1,5}', output_tokens)
            or not 1 <= int(output_tokens) <= 32768):
        return 'invalid_environment'
    if (not isinstance(cwd, str) or not cwd or len(cwd) > 32767 or type(timeout) not in (int, float)
            or not math.isfinite(timeout) or not 0 < timeout <= 600
            or type(maximum) is not int or not 1 <= maximum <= MAX_STREAM_BYTES):
        return 'invalid_bounds'
    return None


def _safe_project(stream):
    # Never pass an unexpected projector exception or its raw input to a receipt.
    try:
        return project_stream(stream)
    except Exception:
        return {'ok': False, 'error': 'projector_failed'}


class DiagnosticRunner:
    """Wrap exactly one explicitly supplied runner; construction never invokes it.

    The three-record bound matches the category scenario cap. The accepted adapter
    still owns its independent budget, schema, model identity, and cleanup latch.
    """
    def __init__(self, runner, *, runtime_mode='safe_mode'):
        if runtime_mode not in ('safe_mode', 'reviewed_hooks'):
            raise DiagnosticTransportError('invalid_runtime_mode')
        if not callable(runner):
            raise DiagnosticTransportError('explicit_runner_required')
        path = Path(__file__).resolve().parent / 'rejection_observer.py'
        if (Path(rejection_observer.__file__).resolve() != path
                or hashlib.sha256(path.read_bytes()).hexdigest() != OBSERVER_SHA256
                or rejection_observer.strict is not stream_projection):
            raise DiagnosticTransportError('observer_identity_mismatch')
        self._runner = runner
        self._runtime_mode = runtime_mode
        self._records = []
        self._lock = Lock()

    @property
    def records(self):
        with self._lock:
            return deepcopy(self._records)

    def __call__(self, argv, input_bytes, env, cwd, timeout, maximum):
        with self._lock:
            if len(self._records) >= MAX_RECORDS:
                del argv, input_bytes, env, cwd
                raise DiagnosticTransportError('record_limit')
            invalid = _validate(argv, input_bytes, env, cwd, timeout, maximum, self._runtime_mode)
            if invalid is not None:
                del argv, input_bytes, env, cwd
                raise DiagnosticTransportError(invalid)
            stream_argv = list(argv)
            output_index = 24 if self._runtime_mode == 'safe_mode' else 23
            stream_argv[output_index] = 'stream-json'
            stream_argv[output_index + 1:output_index + 1] = ['--verbose', '--include-partial-messages']
            record = {'evidence_kind': 'transport_projection_only', 'adapter_acceptance': None,
                      'logical_answer_mode': 'plain_json', 'requested_cli_output_format': 'stream-json',
                      'requested_verbose': True, 'requested_partial_messages': True,
                      'runner_returned': False, 'runner_exit_code': None,
                      'runner_exit_code_available': False, 'projection': None}
            if self._runtime_mode == 'reviewed_hooks':
                record['requested_runtime_mode'] = 'reviewed_hooks'
            self._records.append(record)
            # Preserve runner errors and CleanupUncertain while dropping wrapper references.
            try:
                result = self._runner(stream_argv, input_bytes, env, cwd, timeout, maximum)
            except BaseException:
                del argv, input_bytes, env, cwd, stream_argv
                raise
            record['runner_returned'] = True
            if (type(result) is not tuple or len(result) != 2 or type(result[0]) is not int
                    or type(result[1]) is not bytes or len(result[1]) > maximum):
                del result, argv, input_bytes, env, cwd, stream_argv
                raise DiagnosticTransportError('invalid_runner_result')
            status, stream = result
            if -(2**31) <= status <= 2**32 - 1:
                record['runner_exit_code'] = status
                record['runner_exit_code_available'] = True
            projection = _safe_project(stream)
            record['projection'] = projection
            if projection.get('ok') is not True:
                try:
                    record['rejection_observation'] = rejection_observer.observe_rejection(stream)
                except Exception:
                    record['rejection_observation'] = {'diagnostic_only': True, 'acceptance': False,
                                                       'ok': False, 'error': 'observer_exception',
                                                       'scan_complete': False}
                del stream, result, argv, input_bytes, env, cwd, stream_argv
                raise DiagnosticTransportError('stream_projection_rejected')
            # Remove only the JSONL frame delimiter, preserving the final JSON bytes.
            body = stream[:-1] if stream.endswith(b'\n') else stream
            final_envelope = body.rsplit(b'\n', 1)[-1]
            return status, final_envelope
