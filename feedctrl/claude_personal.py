"""Opt-in personal Claude Code CLI transport; no construction-time execution.

This is not an API credential adapter or shared service. It requires a separately
reviewed, unmodified executable already signed into the operator's own account.
A logical invocation is not proof of one HTTP request or of a billing amount.
"""
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import threading
import time

from jsonschema import Draft202012Validator
from feedctrl.controls import ParserOperationalError
from feedctrl.model_adapters import HostedRunBudget, _json, _decode, _hash
from feedctrl.indirect_grounding import _response_snapshot

# These are the only schema features used by the existing workflows. Rejecting
# everything else also prevents remote $ref resolution and silent weakening.
_SCHEMA_KEYS = {'type', 'properties', 'required', 'additionalProperties', 'items',
                'enum', 'maxItems', 'minItems', 'minLength', 'maxLength'}
_ENV_ALLOW = ('SYSTEMROOT', 'WINDIR', 'APPDATA', 'LOCALAPPDATA', 'USERPROFILE',
              'HOMEDRIVE', 'HOMEPATH', 'HOME', 'PATH', 'TEMP', 'TMP', 'TMPDIR')


# Closed receipt vocabulary. Unknown/missing values are omitted, never guessed.
_CLI_ENUMS = {
    'type': ('result',),
    'subtype': ('success', 'error_during_execution', 'error_max_turns',
                'error_max_budget_usd', 'error_max_structured_output_retries'),
    'stop_reason': ('end_turn', 'max_tokens', 'stop_sequence', 'tool_use',
                    'pause_turn', 'refusal'),
}
_USAGE_FIELDS = ('input_tokens', 'output_tokens', 'cache_creation_input_tokens',
                 'cache_read_input_tokens')
_MODEL_USAGE_FIELDS = ('inputTokens', 'outputTokens', 'cacheReadInputTokens',
                       'cacheCreationInputTokens', 'webSearchRequests',
                       'contextWindow', 'maxOutputTokens')


def _safe_cost(value):
    return type(value) in (int, float) and 0 <= value <= 1000000 and math.isfinite(value)


def _safe_usage(value, fields, cost=False):
    if not isinstance(value, dict):
        return {}
    out = {k: value[k] for k in fields
           if type(value.get(k)) is int and 0 <= value[k] <= 2**53-1}
    if cost and _safe_cost(value.get('costUSD')):
        out['costUSD'] = value['costUSD']
    return out


def _safe_cli_evidence(envelope, model):
    """Project only bounded status/counters; never content or arbitrary model keys.

    This describes reported evidence, not a diagnosis, billing or identity proof.
    It deliberately does not interpret free-text errors as quota/access failures.
    """
    if not isinstance(envelope, dict):
        return {}
    status = {k: envelope[k] for k, allowed in _CLI_ENUMS.items()
              if envelope.get(k) in allowed}
    if type(envelope.get('is_error')) is bool:
        status['is_error'] = envelope['is_error']
    if type(envelope.get('num_turns')) is int and 0 <= envelope['num_turns'] <= 2**53-1:
        status['num_turns'] = envelope['num_turns']
    out = {'cli_status': status}
    if isinstance(envelope.get('usage'), dict):
        out['reported_usage'] = _safe_usage(envelope['usage'], _USAGE_FIELDS)
    models = envelope.get('modelUsage')
    if isinstance(models, dict) and set(models) == {model} and isinstance(models[model], dict):
        out['reported_model'] = model
        out['reported_model_usage'] = {model: _safe_usage(models[model], _MODEL_USAGE_FIELDS, True)}
    if _safe_cost(envelope.get('total_cost_usd')):
        out['estimated_cost_usd'] = envelope['total_cost_usd']
        out['estimated_cost_note'] = 'CLI estimate, not billing proof'
    return out


def _schema_check(schema, depth=0):
    if depth > 30 or not isinstance(schema, dict) or set(schema) - _SCHEMA_KEYS:
        raise ValueError('Unsupported response schema')
    if schema.get('type') not in ('object', 'array', 'string', 'integer', 'number', 'boolean', 'null'):
        raise ValueError('Explicit schema type required')
    for child in schema.get('properties', {}).values():
        _schema_check(child, depth + 1)
    if 'items' in schema:
        _schema_check(schema['items'], depth + 1)
    if isinstance(schema.get('additionalProperties'), dict):
        raise ValueError('Schema-valued additionalProperties unsupported')
    Draft202012Validator.check_schema(schema)


def _run_process(argv, input_bytes, env, cwd, timeout, max_response_bytes):
    """Intentionally unavailable pending reviewed Windows process-tree containment.

    Offline tests may mock this seam. Production activation needs a separately
    reviewed implementation; no Boolean authorization can enable this stub.
    """
    raise ParserOperationalError('CLI launch disabled pending reviewed process containment')


def make_claude_personal_infer(*, executable, workdir, model, effort, run_budget,
        estimated_per_invocation_usd, output_mode, runtime_authorized=False, data_authorized=False,
        subscription_and_usage_authorized=False, executable_reviewed=False,
        managed_runtime_reviewed=False, process_containment_reviewed=False, reviewed_cli_version=None,
        max_output_tokens=4096, max_request_bytes=20000, max_response_bytes=1000000,
        timeout=90, process_runner=None):
    """Create a personal CLI callable with process launch disabled by default.

    A supplied runner is an operator selection, not evidence of containment.

    Each boolean is an operator assertion, not proof. Provider billing, extra usage,
    account identity, binary integrity, managed hooks and data permission require independent review.
    Version is an operator assertion, not a CLI version probe or attestation.
    The process-level attempt allowance is not durable across process restart. The
    CLI's estimated budget is per process, may overshoot, and is not a billing cap.
    """
    if process_runner is not None and not callable(process_runner):
        raise ValueError('Process runner must be callable or None')
    if any(v is not True for v in (runtime_authorized, data_authorized,
                                  subscription_and_usage_authorized, executable_reviewed, managed_runtime_reviewed,
                                  process_containment_reviewed)):
        raise ValueError('Separate runtime, data, subscription/usage, binary, managed-policy and containment review required')
    if reviewed_cli_version != '2.1.321':
        raise ValueError('Explicitly reviewed CLI version 2.1.321 required')
    if not isinstance(run_budget, HostedRunBudget):
        raise ValueError('Explicit shared run allowance required')
    if not isinstance(executable, str) or not os.path.isabs(executable):
        raise ValueError('Explicit absolute executable path required')
    if not isinstance(workdir, str) or not os.path.isabs(workdir):
        raise ValueError('Explicit absolute isolated working directory required')
    if not isinstance(model, str) or not re.fullmatch(r'claude-[a-zA-Z0-9.-]{1,120}', model):
        raise ValueError('Explicit full model identifier required, not an alias')
    if output_mode not in ('schema_tool','plain_json'):
        raise ValueError('Explicit schema_tool or plain_json output mode required')
    if effort not in ('low', 'medium', 'high', 'max'):
        raise ValueError('Explicit supported effort required')
    if type(estimated_per_invocation_usd) not in (int, float) or not math.isfinite(estimated_per_invocation_usd) or estimated_per_invocation_usd <= 0:
        raise ValueError('Explicit positive estimated per-invocation threshold required')
    for v, low, high in ((max_output_tokens,1,5000), (max_request_bytes,1,50000),
                         (max_response_bytes,1,2000000)):
        if type(v) is not int or not low <= v <= high:
            raise ValueError('Invalid bounded transport setting')
    if type(timeout) not in (int,float) or not math.isfinite(timeout) or not 0 < timeout <= 300:
        raise ValueError('Invalid timeout')
    config = {'backend':'claude-code-personal-cli', 'model':model, 'requested_effort':effort,
              'output_mode':output_mode,
              'process_runner_selection':'explicit' if process_runner is not None else 'disabled_default',
              'executable':executable, 'workdir':workdir, 'reviewed_cli_version':reviewed_cli_version,
              'max_calls':run_budget.max_calls,
              'estimated_per_invocation_usd':estimated_per_invocation_usd,
              'max_output_tokens':max_output_tokens, 'max_request_bytes':max_request_bytes,
              'max_response_bytes':max_response_bytes, 'timeout_seconds':timeout,
              'safe_mode':True, 'tools':[], 'no_session_persistence':True,
              'retry_settings_requested':{'api':0,'nonstreaming_timeout':0,'structured_attempts':1},
              'fallback_policy':'refusal switching disabled; managed fallback chain requires separate review',
              'cost_limit_kind':'per-process estimate; may overshoot; not a billing cap'}
    digest = _hash(config)
    run_budget.bind(digest)
    provenance = {**config, 'digest':digest,
                  'digest_kind':'configuration_sha256_not_model_weights',
                  'identity_limit':'Requested CLI model, checked against reported modelUsage; no weight or account attestation',
                  'attempt_limit':'Logical CLI invocations only; underlying HTTP attempts unverified',
                  'request_digest_kind':'canonical CLI logical request; not HTTP wire bytes'}
    receipts = []
    run_lock = threading.Lock()
    cleanup_blocked = False

    def _infer(payload, schema):
        payload, schema = deepcopy(payload), deepcopy(schema)
        if not isinstance(payload,dict) or not isinstance(payload.get('system'),str) or not payload['system'].strip():
            raise ValueError('Explicit system prompt required')
        _schema_check(schema)
        if schema.get('type') != 'object':
            raise ValueError('Object response schema required')
        body = {k:v for k,v in payload.items() if k != 'system'}
        data = _json(body)
        schema_bytes = _json(schema)
        rendered_system=payload['system']
        if output_mode == 'plain_json':
            rendered_system += ('\n\nReturn exactly one JSON object matching this schema. '
                                'Do not use Markdown, prose, or additional text. Schema: '
                                + schema_bytes.decode('utf-8'))
        request = _json({'system':rendered_system, 'payload':body, 'schema':schema,
                         'output_mode':output_mode})
        if len(request) > max_request_bytes:
            raise ValueError('Request exceeds authorized evidence budget; no truncation')
        argv = [executable, '-p', '--safe-mode', '--tools', '', '--disallowedTools', 'mcp__*',
                '--no-chrome', '--no-session-persistence', '--permission-mode', 'dontAsk',
                '--permission-prompts', 'none', '--max-turns', '1',
                '--settings', '{"switchModelsOnFlag":false}', '--model', model,
                '--effort', effort, '--max-budget-usd', str(estimated_per_invocation_usd),
                '--output-format', 'json']
        if output_mode == 'schema_tool':
            argv.extend(['--json-schema', schema_bytes.decode('utf-8')])
        argv.extend(['--system-prompt', rendered_system])
        # Authentication is intentionally left to the already signed-in binary.
        # Do not forward API keys or token-bearing environment variables.
        env = {k:os.environ[k] for k in _ENV_ALLOW if k in os.environ}
        env.update({'CLAUDE_CODE_MAX_RETRIES':'0', 'CLAUDE_CODE_NONSTREAMING_TIMEOUT_RETRIES':'0',
                    'MAX_STRUCTURED_OUTPUT_RETRIES':'1', 'CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK':'1',
                    'CLAUDE_CODE_MAX_OUTPUT_TOKENS':str(max_output_tokens), 'DISABLE_AUTOUPDATER':'1',
                    'CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK':'1'})
        call_id = run_budget.reserve()
        receipt = {'logical_call_id':call_id, 'representation':'logical_invocation_reservation',
                   'request_sha256':hashlib.sha256(request).hexdigest(),
                   'request_digest_kind':'canonical CLI logical request; not HTTP wire bytes',
                   'schema_sha256':_hash(schema),
                   'outcome':'started', 'output_mode':output_mode, 'started_unix':time.time()}
        receipts.append(receipt)
        started=time.monotonic()
        try:
            # Existence checks are activation-time only, and do not assert binary integrity.
            if not Path(executable).is_file() or not Path(workdir).is_dir():
                raise ValueError('Reviewed executable or isolated working directory unavailable')
            runner = process_runner if process_runner is not None else _run_process
            status, raw = runner(argv, data, env, workdir, timeout, max_response_bytes)
            if type(status) is not int or not isinstance(raw, bytes) or len(raw) > max_response_bytes:
                raise ValueError('Invalid process runner result')
            receipt.update(exit_code=status, response_sha256=hashlib.sha256(raw).hexdigest())
            receipt['failure_reason'] = 'malformed_envelope'
            envelope = _decode(raw)
            if isinstance(envelope, dict):
                receipt.update(_safe_cli_evidence(envelope, model))
                receipt['failure_reason'] = 'incomplete_success'
            else:
                receipt['failure_reason'] = 'invalid_envelope_type'
            if (status != 0 or not isinstance(envelope,dict) or envelope.get('type') != 'result'
                    or envelope.get('subtype') != 'success' or envelope.get('is_error') is not False
                    or type(envelope.get('num_turns')) is not int or envelope['num_turns'] != 1
                    or not isinstance(envelope.get('usage'),dict)
                    or envelope.get('stop_reason') not in (None,'end_turn')):
                raise ValueError('CLI result was not a complete structured success')
            usage_models=envelope.get('modelUsage')
            if (not isinstance(usage_models,dict) or set(usage_models)!={model}
                    or not isinstance(usage_models[model],dict)):
                receipt['failure_reason'] = 'model_identity_validation_failed'
                raise ValueError('CLI reported missing or different model identity')
            receipt['failure_reason'] = 'invalid_metadata'
            _response_snapshot(envelope)  # all receipt metadata must be finite, bounded JSON
            usage=envelope['usage']
            for key in ('input_tokens','output_tokens'):
                if type(usage.get(key)) is not int or usage[key] < 0:
                    raise ValueError('Missing or invalid reported token usage')
            for key in ('cache_creation_input_tokens','cache_read_input_tokens'):
                if key in usage and (type(usage[key]) is not int or usage[key] < 0):
                    raise ValueError('Invalid reported cache token usage')
            estimate=envelope.get('total_cost_usd')
            if estimate is not None and (type(estimate) not in (int,float)
                                         or not math.isfinite(estimate) or estimate < 0):
                raise ValueError('Invalid estimated cost')
            receipt['failure_reason'] = 'invalid_output'
            if output_mode == 'schema_tool':
                if not isinstance(envelope.get('structured_output'),dict):
                    raise ValueError('Structured output missing')
                result=_response_snapshot(envelope['structured_output'])
            else:
                text=envelope.get('result')
                if not isinstance(text,str):raise ValueError('Plain JSON result missing')
                result=_response_snapshot(_decode(text.encode('utf-8')))
                if not isinstance(result,dict):raise ValueError('Plain JSON object required')
            Draft202012Validator(schema).validate(result)
            receipt.pop('failure_reason', None)
            receipt.update(outcome='parsed_transport_only')
            return deepcopy(result)
        except Exception as exc:
            receipt.update(outcome='error', error_type=type(exc).__name__)
            raise ParserOperationalError('Personal CLI invocation failed: '+type(exc).__name__) from exc
        finally:
            receipt['elapsed_seconds']=time.monotonic()-started
    def infer(payload, schema):
        nonlocal cleanup_blocked
        from feedctrl.windows_job_runner import CleanupUncertain
        # Serialize to ensure no later logical call starts after uncertain cleanup.
        with run_lock:
            if cleanup_blocked:
                raise ParserOperationalError('Run stopped after uncertain process cleanup')
            try:
                return _infer(payload, schema)
            except ParserOperationalError as exc:
                if isinstance(exc.__cause__, CleanupUncertain):
                    cleanup_blocked=True
                raise

    return infer, deepcopy(provenance), receipts
