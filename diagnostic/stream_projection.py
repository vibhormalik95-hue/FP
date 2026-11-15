"""Offline-only, fail-closed projection of a bounded Claude CLI JSONL stream.

This module does not launch processes, perform I/O, or validate model answers.
It intentionally emits no untrusted text, identifiers, tool details, or content.
"""
import json
import math
import re

MAX_STREAM_BYTES = 1_000_000
MAX_LINE_BYTES = 262_144
MAX_EVENTS = 4096
MAX_INT = 2**53 - 1
MAX_COST = 1_000_000

_TOP = frozenset(('system', 'assistant', 'user', 'stream_event', 'result', 'rate_limit_event'))
_SYSTEM = frozenset(('thinking_tokens', 'status', 'init', 'compact_boundary', 'informational',
                     'worker_shutting_down', 'permission_denied',
                     'hook_started', 'hook_progress', 'hook_response'))
_SYSTEM_ABORT = frozenset(('permission_denied', 'worker_shutting_down', 'api_retry',
                           'model_fallback', 'model_refusal_fallback',
                           'model_refusal_no_fallback'))
_STREAM = frozenset(('message_start', 'content_block_start', 'content_block_delta',
                     'content_block_stop', 'message_delta', 'message_stop', 'ping'))
_BLOCK = frozenset(('text', 'thinking', 'redacted_thinking', 'tool_use', 'server_tool_use'))
_DELTA = frozenset(('text_delta', 'thinking_delta', 'signature_delta', 'input_json_delta'))
_DELTA_FIELD = {'text_delta': 'text', 'thinking_delta': 'thinking',
                'signature_delta': 'signature', 'input_json_delta': 'partial_json'}
_RESULT = frozenset(('success', 'error_during_execution', 'error_max_turns',
                     'error_max_budget_usd', 'error_max_structured_output_retries'))
_STOP = frozenset(('end_turn', 'max_tokens', 'stop_sequence', 'tool_use',
                   'pause_turn', 'refusal', 'model_context_window_exceeded'))
_USAGE = ('input_tokens', 'output_tokens', 'cache_creation_input_tokens',
          'cache_read_input_tokens')


class ProjectionError(ValueError):
    """Fixed, non-content-bearing failure codes only."""
    def __init__(self, code, detail=None):
        super().__init__(code)
        self.detail = detail


def _fail(code, detail=None):
    raise ProjectionError(code, detail)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _fail('duplicate_key')
        result[key] = value
    return result


def _integer(text):
    # Reject oversized numeric literals even in discarded content.
    if len(text.lstrip('-')) > 16:
        _fail('invalid_number')
    value = int(text)
    if abs(value) > MAX_INT:
        _fail('invalid_number')
    return value


def _float(text):
    value = float(text)
    if not math.isfinite(value) or abs(value) > MAX_INT:
        _fail('invalid_number')
    return value


def _constant(_text):
    _fail('invalid_number')


def _count(value):
    if type(value) is not int or not 0 <= value <= MAX_INT:
        _fail('invalid_number')
    return value


def _stop(value):
    if value is None:
        return None
    if not isinstance(value, str) or value not in _STOP:
        _fail('unsupported_stop_reason')
    return value


def _usage(value):
    if not isinstance(value, dict):
        _fail('invalid_metadata', 'usage_not_object')
    return {key: _count(value[key]) for key in _USAGE if key in value}


def _terminal(frame):
    subtype = frame.get('subtype')
    if not isinstance(subtype, str) or subtype not in _RESULT:
        _fail('unsupported_result')
    if type(frame.get('is_error')) is not bool:
        _fail('invalid_metadata', 'is_error_missing' if 'is_error' not in frame
              else 'is_error_not_boolean')
    if (subtype == 'success') == frame['is_error']:
        _fail('invalid_metadata', 'subtype_error_flag_mismatch')
    if subtype == 'success' and not isinstance(frame.get('result'), str):
        _fail('invalid_frame')
    if subtype != 'success' and (not isinstance(frame.get('errors'), list)
                                 or any(not isinstance(x, str) for x in frame['errors'])):
        _fail('invalid_frame')
    result = {'subtype': subtype, 'is_error': frame['is_error'],
              'num_turns': _count(frame.get('num_turns')),
              'stop_reason_present': 'stop_reason' in frame,
              'stop_reason': _stop(frame.get('stop_reason'))}
    for key in ('duration_ms', 'duration_api_ms', 'queued_turn_count'):
        if key in frame:
            result[key] = _count(frame[key])
    if 'usage' in frame:
        result['usage'] = _usage(frame['usage'])
    if 'total_cost_usd' in frame:
        value = frame['total_cost_usd']
        if type(value) not in (int, float) or not 0 <= value <= MAX_COST or not math.isfinite(value):
            _fail('invalid_number')
        result['total_cost_usd'] = value
    return result


# SDKStatusMessage: fixed documented fields, no raw metadata retained.
_STATUS_FIELDS = frozenset(('type', 'subtype', 'status', 'permissionMode', 'uuid', 'session_id'))
_UUID = re.compile(r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\Z')


def _status(frame):
    if set(frame) - _STATUS_FIELDS or 'status' not in frame:
        _fail('invalid_status')
    status = frame['status']
    if status is not None and (type(status) is not str or status not in ('compacting', 'requesting')):
        _fail('invalid_status')
    uuid, session = frame.get('uuid'), frame.get('session_id')
    if (type(uuid) is not str or not _UUID.fullmatch(uuid) or type(session) is not str
            or not 0 < len(session) <= 256):
        _fail('invalid_status')
    if 'permissionMode' in frame and frame['permissionMode'] != 'dontAsk':
        _fail('permission_mode_mismatch')


# SDKThinkingTokensMessage: validate its closed metadata shape, retain no values.
_THINKING_FIELDS = frozenset(('type', 'subtype', 'estimated_tokens',
                              'estimated_tokens_delta', 'user_message_uuid',
                              'uuid', 'session_id'))
_THINKING_REQUIRED = _THINKING_FIELDS - {'user_message_uuid'}


def _thinking_tokens(frame):
    if set(frame) - _THINKING_FIELDS or not _THINKING_REQUIRED <= set(frame):
        _fail('invalid_thinking_tokens')
    _count(frame['estimated_tokens'])
    _count(frame['estimated_tokens_delta'])
    uuid, session = frame['uuid'], frame['session_id']
    if (type(uuid) is not str or not _UUID.fullmatch(uuid) or type(session) is not str
            or not 0 < len(session) <= 256):
        _fail('invalid_thinking_tokens')
    if 'user_message_uuid' in frame:
        user_uuid = frame['user_message_uuid']
        if type(user_uuid) is not str or not _UUID.fullmatch(user_uuid):
            _fail('invalid_thinking_tokens')


# Only rate status and errorCode are authoritative here; other metadata is discarded.
_RATE_TOP = frozenset(('type', 'rate_limit_info', 'uuid', 'session_id'))
_RATE_INFO = frozenset(('status', 'resetsAt', 'utilization', 'errorCode',
                        'canUserPurchaseCredits', 'hasChargeableSavedPaymentMethod',
                        'overageEnabled', 'rateLimitType', 'overageStatus',
                        'overageResetsAt', 'overageDisabledReason'))
_RATE_STATUS = frozenset(('allowed', 'allowed_warning', 'rejected'))
_RATE_TYPE = frozenset(('five_hour', 'seven_day', 'seven_day_opus', 'seven_day_sonnet', 'overage',
                        'seven_day_overage_included'))


def _rate_limit(frame):
    if frame.get('type') != 'rate_limit_event' or 'rate_limit_info' not in frame:
        _fail('invalid_rate_limit')
    info = frame['rate_limit_info']
    if not isinstance(info, dict) or 'status' not in info:
        _fail('invalid_rate_limit')
    if type(info['status']) is not str or info['status'] not in _RATE_STATUS:
        _fail('invalid_rate_limit')
    if info['status'] == 'rejected':
        _fail('rate_limit_rejected')
    if 'errorCode' in info:
        if type(info['errorCode']) is not str or info['errorCode'] != 'credits_required':
            _fail('invalid_rate_limit')
        _fail('rate_limit_rejected')
    # Do not silently discard direct error indicators in an unexpected location.
    if (any(key in frame for key in ('error', 'is_error', 'errorCode', 'status'))
            or any(key in info for key in ('error', 'is_error', 'error_code'))):
        _fail('invalid_rate_limit')


def _project_stream(data, coverage):
    """Return bounded metadata from a complete JSONL buffer, or raise ProjectionError.

    Coverage of intermediate events is always unknown. A single result frame must
    be last; the documented SDK trailing-system case is deliberately unsupported.
    """
    if type(data) is not bytes or not data or len(data) > MAX_STREAM_BYTES:
        _fail('invalid_stream_size')
    lines = data.split(b'\n')
    if lines[-1] == b'':
        lines.pop()
    if not lines or len(lines) > MAX_EVENTS:
        _fail('invalid_event_count')
    counts = {name: 0 for name in sorted(_TOP) if name != 'rate_limit_event'}
    stream_counts = {name: 0 for name in sorted(_STREAM)}
    stops = []
    terminal = None
    message_open = False
    delta_phase = False
    open_blocks = {}
    seen_blocks = set()
    for line in lines:
        if line.endswith(b'\r'):
            line = line[:-1]
        if not line or len(line) > MAX_LINE_BYTES:
            _fail('invalid_line_size')
        try:
            frame = json.loads(line.decode('utf-8'), object_pairs_hook=_pairs,
                               parse_int=_integer, parse_float=_float, parse_constant=_constant)
        except ProjectionError:
            raise
        except (ValueError, UnicodeError, RecursionError, OverflowError):
            _fail('invalid_json')
        if not isinstance(frame, dict):
            _fail('invalid_frame')
        kind = frame.get('type')
        if not isinstance(kind, str) or kind not in _TOP:
            _fail('unsupported_frame')
        if terminal is not None:
            _fail('terminal_not_last')
        counts[kind] = counts.get(kind, 0) + 1
        if kind == 'result':
            if message_open:
                _fail('incomplete_message')
            # In the no-tools workflow, absent or nonempty authoritative denial
            # data cannot establish that no attempted tool was denied.
            if type(frame.get('permission_denials')) is not list or frame['permission_denials']:
                _fail('permission_denials_not_empty_or_missing')
            terminal = _terminal(frame)
        elif kind == 'system':
            subtype = frame.get('subtype')
            if type(subtype) is not str or not 0 < len(subtype) <= 256:
                _fail('unsupported_system')
            if subtype in _SYSTEM_ABORT:
                _fail('system_operational_failure')
            if subtype == 'control_request_progress':
                if frame.get('status') != 'started':
                    _fail('system_operational_failure')
            elif subtype == 'hook_response':
                if (frame.get('outcome') != 'success' or
                        ('exit_code' in frame and (type(frame['exit_code']) is not int or frame['exit_code'] != 0))):
                    _fail('system_operational_failure')
            elif subtype == 'informational':
                if ('prevent_continuation' in frame and type(frame['prevent_continuation']) is not bool):
                    _fail('invalid_system_metadata')
                if frame.get('prevent_continuation') is True or frame.get('tag') == 'hook_no_verdict':
                    _fail('system_operational_failure')
            elif subtype == 'plugin_install':
                if frame.get('status') not in ('started', 'installed', 'completed'):
                    _fail('system_operational_failure')
            elif subtype == 'status':
                _status(frame)
            elif subtype == 'thinking_tokens':
                _thinking_tokens(frame)
            elif subtype not in _SYSTEM:
                # A coverage flag, never evidence of what the opaque event meant.
                coverage['unknown_system_seen'] = True
        elif kind in ('assistant', 'user'):
            message = frame.get('message')
            if (not isinstance(message, dict) or message.get('role') != kind
                    or not isinstance(message.get('content'), (str, list))):
                _fail('invalid_frame')
            if kind == 'assistant':
                if frame.get('error') is not None or message.get('stop_reason') == 'refusal':
                    _fail('assistant_operational_failure')
                if isinstance(message['content'], list) and any(
                        isinstance(block, dict) and block.get('type') in ('tool_use', 'server_tool_use', 'refusal')
                        for block in message['content']):
                    _fail('assistant_operational_failure')
        elif kind == 'rate_limit_event':
            info = frame.get('rate_limit_info')
            if set(frame) - _RATE_TOP:
                coverage['unknown_rate_top_seen'] = True
            if isinstance(info, dict) and set(info) - _RATE_INFO:
                # Track presence only; do not export extension names or values.
                coverage['unknown_rate_info_seen'] = True
            if isinstance(info, dict) and set(info) - {'status', 'errorCode'}:
                coverage['optional_rate_info_seen'] = True
            _rate_limit(frame)
        else:
            event = frame.get('event')
            if not isinstance(event, dict) or not isinstance(event.get('type'), str) or event['type'] not in _STREAM:
                _fail('unsupported_stream_event')
            event_type = event['type']
            stream_counts[event_type] += 1
            if event_type == 'message_start':
                if message_open:
                    _fail('invalid_event_order')
                message = event.get('message')
                if (not isinstance(message, dict) or message.get('type') != 'message'
                        or message.get('role') != 'assistant'
                        or not isinstance(message.get('content'), list)):
                    _fail('invalid_frame')
                message_open = True
                delta_phase = False
                open_blocks.clear()
                seen_blocks.clear()
            elif event_type != 'ping' and not message_open:
                _fail('invalid_event_order')
            if event_type.startswith('content_block_'):
                if delta_phase:
                    _fail('invalid_event_order')
                index = _count(event.get('index'))
            if event_type == 'content_block_start':
                if index in seen_blocks:
                    _fail('invalid_event_order')
                block = event.get('content_block')
                if (not isinstance(block, dict) or not isinstance(block.get('type'), str)
                        or block['type'] not in _BLOCK):
                    _fail('unsupported_content')
                block_type = block['type']
                if block_type in ('tool_use', 'server_tool_use'):
                    _fail('assistant_operational_failure')
                field = {'text': 'text', 'thinking': 'thinking', 'redacted_thinking': 'data'}.get(block_type)
                if field is not None and not isinstance(block.get(field), str):
                    _fail('invalid_frame')
                if block_type in ('tool_use', 'server_tool_use') and (
                    not isinstance(block.get('id'), str) or not isinstance(block.get('name'), str)
                    or not isinstance(block.get('input'), dict)):
                    _fail('invalid_frame')
                open_blocks[index] = block_type
                seen_blocks.add(index)
            if event_type == 'content_block_delta':
                if index not in open_blocks:
                    _fail('invalid_event_order')
                delta = event.get('delta')
                if (not isinstance(delta, dict) or not isinstance(delta.get('type'), str)
                        or delta['type'] not in _DELTA):
                    _fail('unsupported_content')
                allowed = {'text': ('text_delta',), 'thinking': ('thinking_delta', 'signature_delta'),
                           'tool_use': ('input_json_delta',), 'server_tool_use': ('input_json_delta',),
                           'redacted_thinking': ()}
                if delta['type'] not in allowed[open_blocks[index]]:
                    _fail('invalid_event_order')
                if not isinstance(delta.get(_DELTA_FIELD[delta['type']]), str):
                    _fail('invalid_frame')
            if event_type == 'content_block_stop':
                if index not in open_blocks:
                    _fail('invalid_event_order')
                del open_blocks[index]
            if event_type == 'message_delta':
                if open_blocks:
                    _fail('invalid_event_order')
                delta = event.get('delta')
                if not isinstance(delta, dict):
                    _fail('invalid_frame')
                delta_phase = True
                if 'stop_reason' in delta and delta['stop_reason'] is not None:
                    if delta['stop_reason'] == 'refusal':
                        _fail('assistant_operational_failure')
                    stops.append(_stop(delta['stop_reason']))
            if event_type == 'message_stop':
                # A cut-off tool block may lack content_block_stop.
                if any(kind not in ('tool_use', 'server_tool_use') for kind in open_blocks.values()):
                    _fail('invalid_event_order')
                message_open = False
                delta_phase = False
                open_blocks.clear()
    if terminal is None:
        _fail('missing_terminal')
    return {'frame_counts': counts, 'stream_event_counts': stream_counts,
            'unknown_system_seen': coverage['unknown_system_seen'],
            'unknown_rate_info_seen': coverage['unknown_rate_info_seen'],
            'unknown_rate_top_seen': coverage['unknown_rate_top_seen'],
            'optional_rate_info_seen': coverage['optional_rate_info_seen'],
            'intermediate_stop_reasons': stops, 'intermediate_coverage': None,
            'final_result': terminal}


def project_stream(data):
    """Return a closed success/error object; never return an exception or raw input.

    The caller remains responsible for not logging or persisting the input buffer.
    """
    coverage = {'unknown_system_seen': False, 'unknown_rate_info_seen': False,
                'unknown_rate_top_seen': False, 'optional_rate_info_seen': False}
    try:
        result = _project_stream(data, coverage)
    except ProjectionError as error:
        result = {'ok': False, 'error': str(error)}
        if any(coverage.values()):
            # These are observations in the parsed prefix, not full coverage.
            result.update(coverage, coverage_scope='parsed_prefix')
        return result
    return {'ok': True, **result}
