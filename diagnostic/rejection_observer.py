"""Offline rejection-only observations; never admits frames or returns content.

The caller must still use the strict projector for all acceptance.
An observed terminal is metadata from a transport-rejected stream, not a valid
application response, a provider-request count or a billing statement.
"""
import json
import math

from . import stream_projection as strict

TARGET = 'claude-fable-5-2'
# Finite diagnostic vocabulary from the public Agent SDK TypeScript reference.
# This diagnostic list is not the acceptance allowlist.
DOCUMENTED_SYSTEM = frozenset(('init', 'compact_boundary', 'informational',
    'worker_shutting_down', 'permission_denied', 'hook_started', 'hook_progress',
    'hook_response', 'status', 'plugin_install', 'task_notification', 'task_started',
    'task_progress', 'task_updated', 'background_tasks_changed', 'thinking_tokens',
    'session_state_changed', 'files_persisted', 'commands_changed',
    'control_request_progress', 'model_refusal_fallback', 'model_refusal_no_fallback',
    'local_command_output', 'mirror_error',
    # Official TypeScript SDK changelog: memory_recall 0.2.105, api_retry
    # 0.2.77, model_fallback 0.3.174; diagnostic names only, no field data.
    'memory_recall', 'api_retry', 'model_fallback'))
DOCUMENTED_TOP = frozenset((*strict._TOP, 'rate_limit_event', 'tool_progress',
                            'tool_use_summary', 'prompt_suggestion'))
MAX_DIAGNOSTIC_DEPTH = 64
MODEL_FIELDS = ('inputTokens', 'outputTokens', 'cacheReadInputTokens',
                'cacheCreationInputTokens', 'webSearchRequests', 'contextWindow',
                'maxOutputTokens')


def _scan(data):
    """Decode every bounded line; any malformed/duplicate/overflow aborts scan."""
    if type(data) is not bytes or not data or len(data) > strict.MAX_STREAM_BYTES:
        return None
    lines = data.split(b'\n')
    if lines[-1] == b'':
        lines.pop()
    if not lines or len(lines) > strict.MAX_EVENTS:
        return None
    frames = []
    try:
        for line in lines:
            if line.endswith(b'\r'):
                line = line[:-1]
            if not line or len(line) > strict.MAX_LINE_BYTES:
                return None
            frame = json.loads(line.decode('utf-8'), object_pairs_hook=strict._pairs,
                               parse_int=strict._integer, parse_float=strict._float,
                               parse_constant=strict._constant)
            if not isinstance(frame, dict) or not isinstance(frame.get('type'), str):
                return None
            # Diagnostics decline deep input even when the JSON decoder can parse it.
            pending = [(frame, 1)]
            while pending:
                value, depth = pending.pop()
                if depth > MAX_DIAGNOSTIC_DEPTH:
                    return None
                if isinstance(value, dict):
                    pending.extend((child, depth + 1) for child in value.values())
                elif isinstance(value, list):
                    pending.extend((child, depth + 1) for child in value)
            frames.append(frame)
    except (strict.ProjectionError, ValueError, UnicodeError, RecursionError, OverflowError):
        return None
    return frames


def _location(error, frames):
    """Locate only codes whose first offending frame is unambiguous here."""
    for number, frame in enumerate(frames, 1):
        kind = frame.get('type')
        if error == 'invalid_rate_limit' and kind == 'rate_limit_event':
            try:
                strict._rate_limit(frame)
            except strict.ProjectionError as exc:
                if str(exc) == error:
                    return {'line_ordinal': number, 'frame_type': 'rate_limit_event'}
        if (error in ('invalid_status', 'permission_mode_mismatch') and kind == 'system'
                and frame.get('subtype') == 'status'):
            try:
                strict._status(frame)
            except strict.ProjectionError as exc:
                if str(exc) == error:
                    return {'line_ordinal': number, 'frame_type': 'system',
                            'documented_subtype': 'status'}
        if error == 'invalid_thinking_tokens' and kind == 'system' and frame.get('subtype') == 'thinking_tokens':
            try:
                strict._thinking_tokens(frame)
            except strict.ProjectionError as exc:
                if str(exc) == error:
                    return {'line_ordinal': number, 'frame_type': 'system',
                            'documented_subtype': 'thinking_tokens'}
        if error == 'unsupported_system' and kind == 'system':
            subtype = frame.get('subtype')
            if not isinstance(subtype, str) or subtype not in strict._SYSTEM:
                return {'line_ordinal': number, 'frame_type': 'system',
                        'documented_subtype': subtype if isinstance(subtype, str)
                        and subtype in DOCUMENTED_SYSTEM else 'other'}
        if error == 'unsupported_frame' and (not isinstance(kind, str) or kind not in strict._TOP):
            return {'line_ordinal': number, 'frame_type': kind if isinstance(kind, str)
                    and kind in DOCUMENTED_TOP else 'other'}
        if error == 'unsupported_stream_event' and kind == 'stream_event':
            event = frame.get('event')
            event_type = event.get('type') if isinstance(event, dict) else None
            if not isinstance(event_type, str) or event_type not in strict._STREAM:
                return {'line_ordinal': number, 'frame_type': 'stream_event',
                        'documented_subtype': 'other'}
    return None


def _system_structure(error, frames, location):
    """Finite rejection-only categories; never retain fields or unknown values."""
    if not location or location.get('frame_type') != 'system':
        return None
    frame = frames[location['line_ordinal'] - 1]
    if error == 'unsupported_system':
        if 'subtype' not in frame:
            state = 'missing'
        elif frame['subtype'] is None:
            state = 'null'
        elif not isinstance(frame['subtype'], str):
            state = 'non_string'
        elif frame['subtype'] in DOCUMENTED_SYSTEM:
            state = 'documented_not_allowed'
        else:
            state = 'unknown_string'
        return {'reason': 'subtype_not_allowed', 'subtype_state': state}
    if error in ('invalid_status', 'permission_mode_mismatch'):
        if set(frame) - strict._STATUS_FIELDS:
            reason = 'unexpected_fields'
        elif 'status' not in frame:
            reason = 'missing_required_field'
        elif frame['status'] is not None and (type(frame['status']) is not str
                or frame['status'] not in ('compacting', 'requesting')):
            reason = 'invalid_status_value'
        elif (type(frame.get('uuid')) is not str or not strict._UUID.fullmatch(frame['uuid'])
              or type(frame.get('session_id')) is not str
              or not 0 < len(frame['session_id']) <= 256):
            reason = 'invalid_identifier_shape'
        else:
            reason = 'permission_mode_mismatch'
        return {'reason': reason}
    if error == 'invalid_thinking_tokens':
        if set(frame) - strict._THINKING_FIELDS:
            reason = 'unexpected_fields'
        elif not strict._THINKING_REQUIRED <= set(frame):
            reason = 'missing_required_field'
        else:
            reason = 'invalid_identifier_shape'
        return {'reason': reason}
    return None


def _rate_structure(error, frames, location):
    """Classify only the first strict rate-metadata failure, without values or keys."""
    if error != 'invalid_rate_limit' or not location or location.get('frame_type') != 'rate_limit_event':
        return None
    frame = frames[location['line_ordinal'] - 1]
    if 'rate_limit_info' not in frame:
        reason = 'missing_info'
    else:
        info = frame['rate_limit_info']
        if not isinstance(info, dict):
            reason = 'info_not_object'
        elif 'status' not in info:
            reason = 'missing_status'
        elif type(info['status']) is not str or info['status'] not in strict._RATE_STATUS:
            reason = 'invalid_status'
        elif 'errorCode' in info and (type(info['errorCode']) is not str or info['errorCode'] != 'credits_required'):
            reason = 'invalid_error_code'
        elif (any(key in frame for key in ('error', 'is_error', 'errorCode', 'status'))
              or any(key in info for key in ('error', 'is_error', 'error_code'))):
            reason = 'unexpected_error_indicator'
        else:
            return None
    return {'reason':reason}


_TERMINAL_ERROR_CODES = frozenset(('unsupported_result', 'invalid_metadata',
                                   'invalid_frame', 'invalid_number', 'unsupported_stop_reason'))
_TERMINAL_REQUIRED = ('uuid', 'session_id', 'duration_ms', 'duration_api_ms', 'stop_reason',
                      'total_cost_usd', 'usage', 'modelUsage', 'permission_denials')


def _terminal_metadata(frame):
    """Return the same safe metadata or one fixed, non-content-bearing failure reason."""
    try:
        for key in _TERMINAL_REQUIRED:
            if key not in frame:
                return None, {'reason': 'missing_required_field', 'field': key}
        if any(not isinstance(frame[k], str) or not 0 < len(frame[k]) <= 256
               for k in ('uuid', 'session_id')):
            return None, {'reason': 'invalid_identifier_shape'}
        if not isinstance(frame['permission_denials'], list) or any(
                not isinstance(item, dict) for item in frame['permission_denials']):
            return None, {'reason': 'invalid_permission_denials_shape'}
        models = frame['modelUsage']
        if not isinstance(models, dict) or len(models) > 16:
            return None, {'reason': 'invalid_model_usage_shape'}
        try:
            projected = strict._terminal(frame)
        except strict.ProjectionError as exc:
            code = str(exc)
            if code in _TERMINAL_ERROR_CODES:
                reason = {'reason': 'strict_terminal_rejected', 'code': code}
                detail = getattr(exc, 'detail', None)
                if code == 'invalid_metadata' and isinstance(detail, str) and detail in (
                        'is_error_missing', 'is_error_not_boolean',
                        'subtype_error_flag_mismatch', 'usage_not_object'):
                    reason['detail'] = detail
                return None, reason
            return None, {'reason': 'terminal_validation_exception'}
        for name, info in models.items():
            if not isinstance(name, str) or len(name) > 256 or not isinstance(info, dict):
                return None, {'reason': 'invalid_model_usage_shape'}
            for key in MODEL_FIELDS:
                if key in info:
                    try:
                        strict._count(info[key])
                    except strict.ProjectionError:
                        return None, {'reason': 'invalid_model_counter'}
            if 'costUSD' in info:
                cost = info['costUSD']
                if type(cost) not in (int, float) or not 0 <= cost <= strict.MAX_COST or not math.isfinite(cost):
                    return None, {'reason': 'invalid_model_cost'}
        projected['model_identity'] = ('requested_only' if set(models) == {TARGET}
                                       else 'missing' if not models else 'different_or_multiple')
        projected['model_identity_count'] = len(models)
        if set(models) == {TARGET}:
            projected['requested_model_usage'] = {
                k: models[TARGET][k] for k in MODEL_FIELDS if k in models[TARGET]}
            if 'costUSD' in models[TARGET]:
                projected['requested_model_usage']['costUSD'] = models[TARGET]['costUSD']
        return projected, None
    except Exception:
        return None, {'reason': 'terminal_validation_exception'}


# Diagnostic vocabulary only. Never used by the strict acceptance projector.
# https://code.claude.com/docs/en/agent-sdk/typescript#sdkassistantmessage
# https://code.claude.com/docs/en/agent-sdk/typescript#sdkresultmessage
ASSISTANT_ERRORS = frozenset(('authentication_failed', 'oauth_org_not_allowed',
    'account_on_hold', 'billing_error', 'rate_limit', 'overloaded', 'invalid_request',
    'model_not_found', 'server_error', 'max_output_tokens', 'cloud_credential_error',
    'unknown'))
TERMINAL_REASONS = frozenset(('completed', 'max_turns', 'tool_deferred',
    'aborted_streaming', 'aborted_tools', 'hook_stopped', 'stop_hook_prevented',
    'background_requested', 'blocking_limit', 'rapid_refill_breaker',
    'prompt_too_long', 'image_error', 'model_error', 'api_error',
    'malformed_tool_use_exhausted', 'budget_exhausted',
    'structured_output_retry_exhausted', 'tool_deferred_unavailable', 'turn_setup_failed'))
STARTUP_FAILURE_REASONS = frozenset(('org_pin_api_key_conflict', 'provider_not_allowed',
    'org_verify_failed', 'org_pin_mismatch', 'managed_settings_invalid',
    'remote_settings_required_unavailable', 'gateway_signin_required',
    'gateway_access_denied', 'proxy_invalid', 'temp_dir_unusable', 'cwd_unavailable',
    'shell_tool_missing', 'session_held_by_background', 'worktree_resume_refused',
    'worktree_unverified', 'cli_version_too_old', 'bypass_root',
    'org_config_required_unavailable', 'org_config_refused',
    'sandbox_required_unavailable', 'config_file_invalid'))


def _enum_observation(frame, key, allowed):
    if key not in frame:
        return {'state': 'missing'}
    value = frame[key]
    if value is None:
        return {'state': 'null'}
    if not isinstance(value, str):
        return {'state': 'non_string'}
    if value in allowed:
        return {'state': 'known', 'value': value}
    return {'state': 'unknown_string'}


def _documented_error_observations(frames, terminal):
    """Fixed-size diagnostics after the caller's complete/unique-final gate.

    Counts describe parsed assistant frames, not requests or complete provider
    coverage. Unknown values, message content and identifiers are never returned.
    """
    states = dict.fromkeys(('missing', 'null', 'non_string', 'unknown_string', 'known'), 0)
    known = dict.fromkeys(sorted(ASSISTANT_ERRORS), 0)
    count = 0
    for frame in frames:
        if frame.get('type') == 'assistant':
            count += 1
            observation = _enum_observation(frame, 'error', ASSISTANT_ERRORS)
            states[observation['state']] += 1
            if observation['state'] == 'known':
                known[observation['value']] += 1
    if 'api_error_status' not in terminal:
        api = {'state': 'missing'}
    elif terminal['api_error_status'] is None:
        api = {'state': 'null'}
    elif type(terminal['api_error_status']) is int and 100 <= terminal['api_error_status'] <= 599:
        api = {'state': 'valid_http_integer', 'value': terminal['api_error_status']}
    else:
        api = {'state': 'invalid'}
    return {'diagnostic_only': True,
            'assistant_errors': {'frame_count': count, 'states': states, 'known_counts': known,
                                 'finite_counts': [{'kind': name, 'count': known[name]}
                                                   for name in sorted(ASSISTANT_ERRORS)]},
            'terminal': {'api_error_status': api,
                         'terminal_reason': _enum_observation(terminal, 'terminal_reason', TERMINAL_REASONS),
                         'startup_failure_reason': _enum_observation(terminal, 'startup_failure_reason', STARTUP_FAILURE_REASONS)}}


def _observed_response_and_stop_counts(frames):
    """Count bounded observed metadata only; never export message identifiers.

    Partial-stream starts cover the main session; complete assistant messages may
    include other scopes. Their distinct counts are kept separate and describe
    shape-valid values observed, not verified rounds, calls or full coverage.
    """
    def empty_ids():
        return {'frames': 0, 'missing': 0, 'null': 0, 'malformed': 0,
                'shape_valid': 0, 'distinct_shape_valid': None}

    complete, starts = empty_ids(), empty_ids()
    complete_ids, start_ids = set(), set()
    states = dict.fromkeys(('missing', 'null', 'malformed', 'unknown_string', 'known'), 0)
    reasons = dict.fromkeys(sorted(strict._STOP), 0)
    deltas = 0
    unclassified = 0

    def record_id(target, seen, message, partial):
        target['frames'] += 1
        if (not isinstance(message, dict) or message.get('role') != 'assistant'
                or (partial and message.get('type') != 'message')):
            target['malformed'] += 1
        elif 'id' not in message:
            target['missing'] += 1
        elif message['id'] is None:
            target['null'] += 1
        elif type(message['id']) is not str or not 0 < len(message['id']) <= 256:
            target['malformed'] += 1
        else:
            target['shape_valid'] += 1
            seen.add(message['id'])

    for frame in frames:
        if frame.get('type') == 'assistant':
            record_id(complete, complete_ids, frame.get('message'), False)
        elif frame.get('type') == 'stream_event':
            event = frame.get('event')
            if (not isinstance(event, dict) or type(event.get('type')) is not str
                    or event['type'] not in strict._STREAM):
                unclassified += 1
            elif event['type'] == 'message_start':
                record_id(starts, start_ids, event.get('message'), True)
            elif event['type'] == 'message_delta':
                deltas += 1
                delta = event.get('delta')
                if not isinstance(delta, dict):
                    states['malformed'] += 1
                else:
                    observation = _enum_observation(delta, 'stop_reason', strict._STOP)
                    state = observation['state']
                    states['malformed' if state == 'non_string' else state] += 1
                    if state == 'known':
                        reasons[observation['value']] += 1
    if complete_ids:
        complete['distinct_shape_valid'] = len(complete_ids)
    if start_ids:
        starts['distinct_shape_valid'] = len(start_ids)
    return {'diagnostic_only': True, 'coverage': 'observed_frames_only',
            'complete_assistant_messages': complete, 'main_session_stream_starts': starts,
            'unclassified_stream_event_frames': unclassified,
            'message_delta_stop_reasons': {'frames': deltas, 'states': states,
                'finite_counts': [{'kind': name, 'count': reasons[name]}
                                  for name in sorted(strict._STOP)]}}


def observe_rejection(data):
    """Return safe diagnostics only; no response bytes, even when a result exists."""
    base = {'diagnostic_only': True, 'acceptance': False}
    try:
        original = strict.project_stream(data)
    except Exception:
        return {**base, 'ok': False, 'error': 'projector_exception', 'scan_complete': False}
    if original.get('ok') is True:
        return {**base, 'status': 'not_rejected'}
    result = {**base, 'ok': False, 'error': original['error'], 'scan_complete': False,
              'failing_frame': None, 'terminal_count': None, 'terminal_last': None,
              'terminal_ambiguous': None, 'terminal_metadata': None}
    frames = _scan(data)
    if frames is None:
        return result
    result['scan_complete'] = True
    result['failing_frame'] = _location(original['error'], frames)
    terminal_indexes = [i for i, frame in enumerate(frames) if frame.get('type') == 'result']
    result['terminal_count'] = len(terminal_indexes)
    result['terminal_last'] = bool(terminal_indexes and terminal_indexes[-1] == len(frames) - 1)
    if terminal_indexes:
        result['terminal_ambiguous'] = len(terminal_indexes) != 1 or not result['terminal_last']
    if len(terminal_indexes) == 1 and result['terminal_last']:
        terminal = frames[terminal_indexes[0]]
        structure = _system_structure(original['error'], frames, result['failing_frame'])
        if structure is not None:
            result['system_structure'] = structure
        rate_structure = _rate_structure(original['error'], frames, result['failing_frame'])
        if rate_structure is not None:
            result['rate_structure'] = rate_structure
        subtype = terminal.get('subtype')
        flag = terminal.get('is_error')
        result['terminal_facts'] = {
            'subtype': subtype if isinstance(subtype, str) and subtype in strict._RESULT else 'other',
            'is_error_state': ('missing' if 'is_error' not in terminal else
                               'true' if flag is True else 'false' if flag is False else 'nonboolean'),
            'usage_shape': ('missing' if 'usage' not in terminal else
                            'object' if isinstance(terminal['usage'], dict) else 'nonobject'),
        }
        result['documented_error_observations'] = _documented_error_observations(frames, terminal)
        result['observed_response_and_stop_counts'] = _observed_response_and_stop_counts(frames)
        metadata, reason = _terminal_metadata(terminal)
        if metadata is not None:
            result['terminal_metadata'] = {'evidence_kind': 'transport_rejected', **metadata}
        elif reason is not None:
            result['terminal_rejection_reason'] = reason
    return result
