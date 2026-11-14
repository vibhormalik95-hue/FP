"""HTTP routes: an OpenAI-compatible chat endpoint and the Anthropic Messages API.

Both send one request for each call and never a second one. The key travels
only in a request header. A redirect is refused, because a redirect could carry
the key to another host. Nothing here reads a credential from disk.

Wire formats were read on the official pages on 14 November 2026 (UTC); the
addresses are in ``docs/model-routes.md``. No real provider was called from the
workspace where this was written: the tests use stand-in servers.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import http.client
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request

from feedctrl import model_routes as routes
from feedctrl.model_adapters import _decode, _json
from feedctrl.model_routes import RouteError

USER_AGENT = 'feed-control-lab/1.0 (research prototype; urllib)'
# Keywords that a provider-side schema feature can reject. The app validates
# the complete schema itself after the reply, so the copy that goes to the
# provider may leave them out.
_RELAXED = frozenset({'minLength', 'maxLength', 'minItems', 'maxItems', 'pattern', 'format', 'minimum', 'maximum',
                      'exclusiveMinimum', 'exclusiveMaximum', 'multipleOf', 'uniqueItems', 'minProperties',
                      'maxProperties'})
_OPENAI_RESERVED = ('model', 'messages', 'stream', 'response_format', 'max_tokens', 'max_completion_tokens', 'n',
                    'tools', 'tool_choice', 'functions', 'function_call')
_ANTHROPIC_RESERVED = ('model', 'messages', 'system', 'stream', 'max_tokens', 'tools', 'tool_choice',
                       'output_config', 'temperature', 'top_p', 'top_k')
# A hosted reasoning model counts its reasoning in the output limit, so the
# hosted defaults are larger than the defaults for a model on this computer.
HOSTED_OUTPUT_TOKENS, LOCAL_OUTPUT_TOKENS = 16384, 4096
PRESETS = {
    'openai': {'base_url': 'https://api.openai.com/v1', 'api_key_env': 'OPENAI_API_KEY',
               'token_limit_field': 'max_completion_tokens', 'max_output_tokens': HOSTED_OUTPUT_TOKENS},
    'ollama': {'base_url': 'http://127.0.0.1:11434/v1', 'token_limit_field': 'max_tokens', 'temperature': 0, 'seed': 42},
    'lm-studio': {'base_url': 'http://127.0.0.1:1234/v1', 'token_limit_field': 'max_tokens'},
    'custom': {'token_limit_field': 'max_tokens'},
}
ANTHROPIC_VERSIONS = ('2026-10-21', '2023-06-01')


def provider_schema(schema, *, close_objects=False):
    """A copy of the schema without the keywords that provider features reject."""
    if isinstance(schema, list):
        return [provider_schema(item, close_objects=close_objects) for item in schema]
    if not isinstance(schema, dict):
        return deepcopy(schema)
    result = {}
    for name, value in schema.items():
        if name in _RELAXED:
            continue
        if name == 'properties' and isinstance(value, dict):
            result[name] = {key: provider_schema(item, close_objects=close_objects) for key, item in value.items()}
        elif name in ('enum', 'const', 'required'):
            result[name] = deepcopy(value)
        else:
            result[name] = provider_schema(value, close_objects=close_objects)
    if close_objects and result.get('type') == 'object':
        result['additionalProperties'] = False
    return result


def is_strict(schema):
    """True when every object lists all its properties as required and is closed.

    That is the condition of the strict structured-output modes. For any other
    schema the request says ``strict: false`` instead of failing.
    """
    if isinstance(schema, list):
        return all(is_strict(item) for item in schema)
    if not isinstance(schema, dict):
        return True
    if schema.get('type') == 'object':
        properties = schema.get('properties', {})
        if schema.get('additionalProperties') is not False or sorted(schema.get('required', [])) != sorted(properties):
            return False
    return all(is_strict(value) for name, value in schema.items() if name not in ('enum', 'const', 'required'))


# --------------------------------------------------------------------------
# One HTTP exchange
# --------------------------------------------------------------------------

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, handle, code, message, headers, new_url):
        raise RouteError('redirect_refused', f'The endpoint answered with a redirect (HTTP {code}). It is not followed.')


def _opener(url):
    handlers = [_NoRedirect()]
    if routes.is_loopback(urllib.parse.urlsplit(url).hostname or ''):
        # A server on this computer is never reached through a proxy.
        handlers.append(urllib.request.ProxyHandler({}))
    return urllib.request.build_opener(*handlers)


def _read(response, limit):
    data = response.read(limit + 1)
    if len(data) > limit:
        raise RouteError('reply_too_large', f'The endpoint sent more than {limit} bytes.')
    return data


def _network_error(reason, url):
    host = urllib.parse.urlsplit(url).hostname or ''
    place = urllib.parse.urlunsplit(urllib.parse.urlsplit(url)._replace(query='', fragment=''))
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return RouteError('timeout')
    if isinstance(reason, ssl.SSLError):
        return RouteError('tls', f'The secure connection to {host} failed ({type(reason).__name__}).')
    if isinstance(reason, ConnectionRefusedError):
        if routes.is_loopback(host):
            return RouteError('not_reachable', f'Nothing listens at {place} on this computer.',
                              'Start the model server (Ollama: open the Ollama application or run "ollama serve"; '
                              'LM Studio: turn on the local server in the Developer tab), or correct "base_url" in the route file.')
        return RouteError('not_reachable', f'The host {host} refused the connection.')
    if isinstance(reason, socket.gaierror):
        return RouteError('not_reachable', f'The host name {host} was not found.',
                          'Check the address in "base_url" and the network connection.')
    return RouteError('not_reachable', f'The endpoint {host} did not answer ({type(reason).__name__}).')


def exchange(request, timeout, limit):
    """Send one request. Return ``(status, headers, body)``; an HTTP error status is returned, not raised."""
    try:
        with _opener(request.full_url).open(request, timeout=timeout) as response:
            return response.status, response.headers, _read(response, limit)
    except urllib.error.HTTPError as error:
        try:
            body = _read(error, limit)
        except (RouteError, OSError, http.client.HTTPException):
            body = b''
        return error.code, error.headers, body
    except RouteError:
        raise
    except urllib.error.URLError as error:
        raise _network_error(error.reason, request.full_url) from None
    except (TimeoutError, socket.timeout):
        raise RouteError('timeout') from None
    except (http.client.HTTPException, OSError) as error:
        raise _network_error(error, request.full_url) from None


def _header(headers, *names):
    for name in names:
        value = headers.get(name) if headers is not None else None
        if isinstance(value, str) and value.strip():
            return routes.ascii_text(routes.one_line(value, 200))
    return None


def _json_object(raw):
    try:
        value = _decode(raw.decode('utf-8'))
    except (ValueError, UnicodeDecodeError, RecursionError):
        return None
    return value if isinstance(value, dict) else None


def _provider_message(body, clean):
    """A short, scrubbed text from an error body: ``(message, type or code)``."""
    error = (body or {}).get('error')
    if isinstance(error, str):
        message, kind = error, ''
    elif isinstance(error, dict):
        message = error.get('message') if isinstance(error.get('message'), str) else ''
        kind = ' '.join(str(error[name]) for name in ('type', 'code') if isinstance(error.get(name), str))
    else:
        message = body.get('message') if isinstance((body or {}).get('message'), str) else ''
        kind = ''
    return routes.ascii_text(routes.one_line(clean(message), 300)), routes.ascii_text(routes.one_line(clean(kind), 80))


def _quoted(message):
    return f' Provider message: "{message}"' if message else ''


def _begin(config, recorder, ordinal, receipt, body):
    data = _json(body)
    if len(data) > config['max_request_bytes']:
        raise RouteError('bad_request', f'The request has {len(data)} bytes. The limit of this route is '
                         f'{config["max_request_bytes"]} bytes. Nothing was sent and nothing was cut.',
                         'Choose a smaller evidence scope, or raise "max_request_bytes" in the route file.')
    recorder.write(ordinal, 'request.json', data)
    receipt.update(request_body_sha256=hashlib.sha256(data).hexdigest(), request_body_bytes=len(data))
    return data


def _end(recorder, ordinal, receipt, status, headers, raw, api_key):
    receipt.update(http_status=status, provider_request_id=_header(headers, 'request-id', 'x-request-id'),
                   response_sha256=hashlib.sha256(raw).hexdigest(), response_bytes=len(raw))
    stored = raw
    if api_key and api_key.encode('utf-8') in raw:
        # A provider can repeat the credential in an error text. The file then
        # holds the reply with the credential removed; the hash is of the original.
        stored = raw.replace(api_key.encode('utf-8'), b'[credential removed]')
        receipt['response_record_scrubbed'] = True
    recorder.write(ordinal, 'response.txt', stored)


# --------------------------------------------------------------------------
# OpenAI-compatible chat completions
# --------------------------------------------------------------------------

def _openai_validate(raw):
    routes.take(raw, {'route', 'preset', 'base_url', 'model', 'api_key_env', 'structured_output', 'token_limit_field',
                      'max_output_tokens', 'temperature', 'seed', 'allow_insecure_http', 'allow_reported_model_mismatch',
                      'extra_body', 'max_calls', 'timeout_seconds', 'max_request_bytes', 'max_response_bytes'},
                'openai-compatible')
    preset = routes.choice_setting(raw, 'preset', tuple(PRESETS), 'custom')
    merged = {**PRESETS[preset], **raw}
    insecure = routes.flag_setting(merged, 'allow_insecure_http')
    if 'base_url' not in merged:
        routes.reject('The "openai-compatible" route needs "base_url", for example http://127.0.0.1:11434/v1.')
    return {'preset': preset, 'base_url': routes.url_setting(merged, 'base_url', allow_insecure=insecure),
            'model': routes.text_setting(merged, 'model', 200, pattern=routes.MODEL_NAME),
            'api_key_env': routes.key_env_setting(merged),
            'structured_output': routes.choice_setting(merged, 'structured_output', ('json_schema', 'json_object', 'prompt'), 'json_schema'),
            'token_limit_field': routes.choice_setting(merged, 'token_limit_field', ('max_tokens', 'max_completion_tokens'), 'max_tokens'),
            'max_output_tokens': routes.number_setting(merged, 'max_output_tokens', 16, 200_000, LOCAL_OUTPUT_TOKENS),
            'temperature': routes.number_setting(merged, 'temperature', 0, 2, None, integer=False),
            'seed': routes.number_setting(merged, 'seed', 0, 2 ** 31 - 1, None),
            'allow_insecure_http': insecure or None,
            'allow_reported_model_mismatch': routes.flag_setting(merged, 'allow_reported_model_mismatch') or None,
            'extra_body': routes.extra_body_setting(merged, _OPENAI_RESERVED) or None,
            **routes.common_limits(merged)}


def _openai_headers(api_key):
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json', 'User-Agent': USER_AGENT}
    if api_key:
        headers['Authorization'] = 'Bearer ' + api_key
    return headers


def _openai_failure(status, raw, config, clean):
    message, kind = _provider_message(_json_object(raw), clean)
    words = (message + ' ' + kind).lower()
    mode, model = config['structured_output'], config['model']
    if status == 400:
        if any(word in words for word in ('response_format', 'json_schema', 'json_object', 'structured output', 'json mode')):
            others = [value for value in ('json_schema', 'json_object', 'prompt') if value != mode]
            return RouteError('structured_output_unsupported',
                              f'The endpoint did not accept "structured_output": "{mode}".' + _quoted(message),
                              f'Set "structured_output" to "{others[0]}" or "{others[1]}" in the route file and run the check.')
        if 'max_tokens' in words or 'max_completion_tokens' in words:
            other = 'max_tokens' if config['token_limit_field'] == 'max_completion_tokens' else 'max_completion_tokens'
            return RouteError('bad_request', 'The endpoint did not accept the output-limit field.' + _quoted(message),
                              f'Set "token_limit_field" to "{other}" in the route file.')
        if 'temperature' in words or 'seed' in words:
            return RouteError('bad_request', 'The endpoint did not accept "temperature" or "seed".' + _quoted(message),
                              'Remove "temperature" and "seed" from the route file.')
        return RouteError('bad_request', 'The endpoint rejected the request (HTTP 400).' + _quoted(message))
    if status == 401:
        name = config.get('api_key_env')
        return RouteError('authentication', 'The provider rejected the API key (HTTP 401).',
                          f'Check the key in the environment variable {name}, then start again.' if name else
                          'This endpoint needs a key. Add "api_key_env" to the route file and set that variable.')
    if status == 402 or (status == 429 and any(word in words for word in ('quota', 'credit', 'billing', 'spend', 'insufficient'))):
        return RouteError('billing', f'The provider reports a billing or quota problem (HTTP {status}).' + _quoted(message))
    if status == 403:
        return RouteError('permission', 'The provider refused the request for this account or network (HTTP 403).'
                          + _quoted(message))
    if status == 404:
        action = 'Run the check to list the model names. Check that "base_url" ends with /v1.'
        if config['preset'] == 'ollama':
            action = f'Run "ollama pull {model}" or correct "model". Check that "base_url" ends with /v1.'
        return RouteError('model_not_found', f'The endpoint did not find the model "{model}" or the address (HTTP 404).'
                          + _quoted(message), action)
    if status in (408, 504):
        return RouteError('timeout', f'The endpoint reported a timeout (HTTP {status}).')
    if status == 429:
        return RouteError('rate_limited', 'The provider limits the request rate (HTTP 429).' + _quoted(message))
    if status in (503, 529):
        return RouteError('provider_overloaded', f'The endpoint is overloaded or not ready (HTTP {status}).' + _quoted(message))
    if status >= 500:
        return RouteError('provider_error', f'The endpoint had an internal error (HTTP {status}).' + _quoted(message))
    return RouteError('bad_request', f'The endpoint rejected the request (HTTP {status}).' + _quoted(message))


def _openai_build(config, *, api_key=None, record_dir=None, relay_dir=None):
    clean = routes.scrubber(api_key)
    recorder, receipts = routes.Recorder(record_dir), []
    allowance = routes.CallAllowance(config['max_calls'])
    headers = _openai_headers(api_key)
    mode, model = config['structured_output'], config['model']

    def transport(ordinal, payload, schema, receipt):
        system, user = routes.render_messages(payload, schema)
        body = {'model': model, 'stream': False, config['token_limit_field']: config['max_output_tokens'],
                'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]}
        for name in ('temperature', 'seed'):
            if config.get(name) is not None:
                body[name] = config[name]
        if mode == 'json_schema':
            body['response_format'] = {'type': 'json_schema', 'json_schema': {
                'name': 'feed_control_reply', 'strict': is_strict(schema), 'schema': provider_schema(schema)}}
        elif mode == 'json_object':
            body['response_format'] = {'type': 'json_object'}
        body.update(deepcopy(config.get('extra_body') or {}))
        data = _begin(config, recorder, ordinal, receipt, body)
        receipt['structured_output'] = mode
        request = urllib.request.Request(config['base_url'] + '/chat/completions', data=data, method='POST', headers=headers)
        status, response_headers, raw = exchange(request, config['timeout_seconds'], config['max_response_bytes'])
        _end(recorder, ordinal, receipt, status, response_headers, raw, api_key)
        if status != 200:
            raise _openai_failure(status, raw, config, clean)
        envelope = _json_object(raw)
        choices = envelope.get('choices') if envelope else None
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            if envelope and envelope.get('error'):   # some servers report an error with status 200
                raise _openai_failure(400, raw, config, clean)
            raise RouteError('unexpected_reply', 'The endpoint did not return a chat completion object.')
        if isinstance(envelope.get('model'), str):
            receipt['reported_model'] = routes.ascii_text(routes.one_line(envelope['model'], 200))
        receipt['usage'] = routes.bounded_counts(envelope.get('usage'), ('prompt_tokens', 'completion_tokens', 'total_tokens'))
        choice = choices[0]
        message = choice.get('message') if isinstance(choice.get('message'), dict) else {}
        reason = choice.get('finish_reason')
        receipt['finish_reason'] = routes.ascii_text(routes.one_line(reason, 40)) if isinstance(reason, str) else None
        if reason == 'length':
            raise RouteError('reply_truncated')
        if reason == 'content_filter' or (isinstance(message.get('refusal'), str) and message['refusal'].strip()):
            raise RouteError('reply_refused')
        if reason in ('tool_calls', 'function_call'):
            raise RouteError('unexpected_reply', 'The model asked for a tool call. This route has no tools.')
        routes.require_model(model, envelope.get('model'), config.get('allow_reported_model_mismatch'))
        if not isinstance(message.get('content'), str):
            raise RouteError('reply_not_json', 'The reply holds no text.')
        return message['content']

    infer = routes.make_infer(config=config, transport=transport, recorder=recorder, receipts=receipts, allowance=allowance)
    identity = routes.identity_for(config, 'openai-compatible-chat',
                                   'Model name as requested; the model that each reply reports is in its receipt. '
                                   'No attestation of weights, account or provider-side processing.')
    return infer, identity, receipts


def _list_models(url, headers, timeout, limit):
    """Ask for the model list. Return ``(status, names, complete)``.

    ``names`` is ``None`` when the answer holds no list. ``complete`` is false
    when the endpoint says that more names exist than it sent.
    """
    request = urllib.request.Request(url, method='GET', headers=headers)
    status, _, raw = exchange(request, min(timeout, 30), limit)
    body = _json_object(raw) if status == 200 else None
    rows = body.get('data') if body else None
    if not isinstance(rows, list):
        return status, None, False
    names = [row['id'] for row in rows if isinstance(row, dict) and isinstance(row.get('id'), str)]
    return status, names, not body.get('has_more')


def _report_models(status, names, complete, model, step, how, failure):
    """Turn a model list into the ``endpoint`` step. Return whether the check may go on."""
    if status in (404, 405, 501) or (status == 200 and names is None):
        step('endpoint', True, f'The endpoint answered (HTTP {status}) but gave no model list. The test call decides.')
        return True
    if status != 200:
        error = failure(status)
        step('endpoint', False, error.message, error.action)
        return False
    shown = ', '.join(routes.ascii_text(name) for name in names[:20]) or 'none'
    if any(routes.model_matches(model, name) or routes.model_matches(name, model) for name in names):
        step('endpoint', True, f'The endpoint answered and lists the model "{model}" ({len(names)} models listed).')
        return True
    if not complete:
        step('endpoint', True, f'The endpoint answered. "{model}" is not among the first {len(names)} listed models; '
                               'the test call decides.')
        return True
    step('endpoint', False, f'The endpoint answered, but it does not list the model "{model}". Listed: {shown}.', how)
    return False


def _openai_check(config, *, api_key=None, step):
    clean = routes.scrubber(api_key)
    status, names, complete = _list_models(config['base_url'] + '/models', _openai_headers(api_key),
                                           config['timeout_seconds'], config['max_response_bytes'])
    how = 'Put one of the listed names in "model".'
    if config['preset'] == 'ollama':
        how = f'Run "ollama pull {config["model"]}", or put one of the listed names in "model".'
    return _report_models(status, names, complete, config['model'], step, how,
                          lambda code: _openai_failure(code, b'', config, clean))


def _openai_describe(config):
    lines = [f'Endpoint: {config["base_url"]}/chat/completions' + (f' (preset {config["preset"]})' if config['preset'] != 'custom' else ''),
             f'Model: {config["model"]}',
             f'Structured output: {config["structured_output"]}; output limit {config["max_output_tokens"]} tokens '
             f'({config["token_limit_field"]}); {config["timeout_seconds"]:g} s for one call']
    if config.get('temperature') is not None or config.get('seed') is not None:
        lines.append(f'Sampling: temperature {config.get("temperature", "not sent")}, seed {config.get("seed", "not sent")}')
    return lines


# --------------------------------------------------------------------------
# Anthropic Messages API
# --------------------------------------------------------------------------

def _anthropic_validate(raw):
    routes.take(raw, {'route', 'base_url', 'model', 'api_key_env', 'anthropic_version', 'auth_header',
                      'anthropic_workspace_id', 'structured_output', 'max_output_tokens', 'effort', 'allow_insecure_http',
                      'allow_reported_model_mismatch', 'extra_body', 'max_calls', 'timeout_seconds', 'max_request_bytes',
                      'max_response_bytes'}, 'anthropic')
    insecure = routes.flag_setting(raw, 'allow_insecure_http')
    return {'base_url': routes.url_setting(raw, 'base_url', default='https://api.anthropic.com', allow_insecure=insecure),
            'model': routes.text_setting(raw, 'model', 200, pattern=routes.MODEL_NAME),
            'api_key_env': routes.key_env_setting(raw, default='ANTHROPIC_API_KEY'),
            'anthropic_version': routes.choice_setting(raw, 'anthropic_version', ANTHROPIC_VERSIONS, ANTHROPIC_VERSIONS[0]),
            'auth_header': routes.choice_setting(raw, 'auth_header', ('authorization', 'x-api-key'), 'authorization'),
            'anthropic_workspace_id': routes.text_setting(raw, 'anthropic_workspace_id', 100, required=False,
                                                          pattern=routes.MODEL_NAME),
            'structured_output': routes.choice_setting(raw, 'structured_output', ('json_schema', 'prompt'), 'json_schema'),
            'max_output_tokens': routes.number_setting(raw, 'max_output_tokens', 16, 200_000, HOSTED_OUTPUT_TOKENS),
            'effort': routes.choice_setting(raw, 'effort', (None, 'low', 'medium', 'high', 'xhigh', 'max'), None),
            'allow_insecure_http': insecure or None,
            'allow_reported_model_mismatch': routes.flag_setting(raw, 'allow_reported_model_mismatch') or None,
            'extra_body': routes.extra_body_setting(raw, _ANTHROPIC_RESERVED) or None,
            **routes.common_limits(raw)}


def _anthropic_headers(config, api_key):
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json', 'User-Agent': USER_AGENT,
               'anthropic-version': config['anthropic_version']}
    if config['auth_header'] == 'x-api-key':
        headers['x-api-key'] = api_key or ''
    else:
        headers['Authorization'] = 'Bearer ' + (api_key or '')
    if config.get('anthropic_workspace_id'):
        headers['anthropic-workspace-id'] = config['anthropic_workspace_id']
    return headers


_ANTHROPIC_TYPES = {'authentication_error': 'authentication', 'billing_error': 'billing',
                    'permission_error': 'permission', 'not_found_error': 'model_not_found',
                    'rate_limit_error': 'rate_limited', 'overloaded_error': 'provider_overloaded',
                    'api_error': 'provider_error', 'timeout_error': 'timeout'}


def _anthropic_failure(status, raw, config, clean):
    body = _json_object(raw)
    message, kind = _provider_message(body, clean)
    kind = kind.split(' ')[0] if kind else ''
    name = config['api_key_env']
    if kind == 'authentication_error' or status == 401:
        return RouteError('authentication', 'The provider rejected the API key (HTTP 401).',
                          f'Check the key in the environment variable {name}, then start again.')
    if kind == 'not_found_error' or status == 404:
        return RouteError('model_not_found', f'The API did not find the model "{config["model"]}" (HTTP {status}).'
                          + _quoted(message))
    if kind == 'request_too_large' or status == 413:
        return RouteError('bad_request', 'The request is larger than the API accepts.',
                          'Choose a smaller evidence scope.')
    if kind == 'invalid_request_error' or status == 400:
        words = message.lower()
        if config['structured_output'] == 'json_schema' and any(word in words for word in ('output_config', 'schema', 'format')):
            return RouteError('structured_output_unsupported',
                              'The API did not accept the structured-output request.' + _quoted(message),
                              'Set "structured_output" to "prompt" in the route file and run the check.')
        if 'spend' in words or ('usage' in words and 'limit' in words):
            return RouteError('billing', 'The API reports a spend limit (HTTP 400).' + _quoted(message))
        return RouteError('bad_request', f'The API rejected the request (HTTP {status}).' + _quoted(message))
    category = _ANTHROPIC_TYPES.get(kind)
    if category is None:
        category = ('provider_overloaded' if status == 529 else 'rate_limited' if status == 429 else
                    'billing' if status == 402 else 'permission' if status == 403 else
                    'timeout' if status == 504 else 'provider_error' if status >= 500 else 'bad_request')
    sentence = routes.CATEGORIES[category][0][:-1] + f' (HTTP {status}).'
    return RouteError(category, sentence + (_quoted(message) if category != 'authentication' else ''))


def _anthropic_build(config, *, api_key=None, record_dir=None, relay_dir=None):
    clean = routes.scrubber(api_key)
    recorder, receipts = routes.Recorder(record_dir), []
    allowance = routes.CallAllowance(config['max_calls'])
    headers = _anthropic_headers(config, api_key)
    mode, model = config['structured_output'], config['model']

    def transport(ordinal, payload, schema, receipt):
        system, user = routes.render_messages(payload, schema)
        body = {'model': model, 'max_tokens': config['max_output_tokens'], 'system': system,
                'messages': [{'role': 'user', 'content': user}]}
        output = {}
        if mode == 'json_schema':
            # The documented limits: closed objects, no length or count keywords.
            output['format'] = {'type': 'json_schema', 'schema': provider_schema(schema, close_objects=True)}
        if config.get('effort'):
            output['effort'] = config['effort']
        if output:
            body['output_config'] = output
        body.update(deepcopy(config.get('extra_body') or {}))
        data = _begin(config, recorder, ordinal, receipt, body)
        receipt['structured_output'] = mode
        request = urllib.request.Request(config['base_url'] + '/v1/messages', data=data, method='POST', headers=headers)
        status, response_headers, raw = exchange(request, config['timeout_seconds'], config['max_response_bytes'])
        _end(recorder, ordinal, receipt, status, response_headers, raw, api_key)
        if status != 200:
            raise _anthropic_failure(status, raw, config, clean)
        envelope = _json_object(raw)
        if not envelope or envelope.get('type') != 'message' or not isinstance(envelope.get('content'), list):
            raise RouteError('unexpected_reply', 'The API did not return a message object.')
        if isinstance(envelope.get('model'), str):
            receipt['reported_model'] = routes.ascii_text(routes.one_line(envelope['model'], 200))
        receipt['usage'] = routes.bounded_counts(envelope.get('usage'), ('input_tokens', 'output_tokens'))
        reason = envelope.get('stop_reason')
        receipt['stop_reason'] = routes.ascii_text(routes.one_line(reason, 40)) if isinstance(reason, str) else None
        if reason == 'max_tokens':
            raise RouteError('reply_truncated')
        if reason == 'model_context_window_exceeded':
            raise RouteError('reply_truncated', 'The request and the reply together filled the context window of the model.',
                             'Choose a smaller evidence scope.')
        if reason == 'refusal':
            raise RouteError('reply_refused')
        if reason in ('tool_use', 'pause_turn'):
            raise RouteError('unexpected_reply', 'The model asked for a tool call. This route has no tools.')
        routes.require_model(model, envelope.get('model'), config.get('allow_reported_model_mismatch'))
        texts = [block.get('text') for block in envelope['content'] if isinstance(block, dict) and block.get('type') == 'text']
        if len(texts) != 1 or not isinstance(texts[0], str):
            raise RouteError('reply_not_json', f'The reply holds {len(texts)} text blocks; one is expected. '
                                               'Blocks are not joined.')
        return texts[0]

    infer = routes.make_infer(config=config, transport=transport, recorder=recorder, receipts=receipts, allowance=allowance)
    identity = routes.identity_for(config, 'anthropic-messages',
                                   'Model name as requested; the model that each reply reports is in its receipt. '
                                   'No attestation of weights, account or provider-side processing.')
    return infer, identity, receipts


def _anthropic_check(config, *, api_key=None, step):
    clean = routes.scrubber(api_key)
    headers = {name: value for name, value in _anthropic_headers(config, api_key).items() if name != 'Content-Type'}
    status, names, complete = _list_models(config['base_url'] + '/v1/models?limit=1000', headers,
                                           config['timeout_seconds'], config['max_response_bytes'])
    return _report_models(status, names, complete, config['model'], step, 'Put one of the listed names in "model".',
                          lambda code: _anthropic_failure(code, b'', config, clean))


def _anthropic_describe(config):
    lines = [f'Endpoint: {config["base_url"]}/v1/messages (API version {config["anthropic_version"]})',
             f'Model: {config["model"]}',
             f'Structured output: {config["structured_output"]}; output limit {config["max_output_tokens"]} tokens; '
             f'{config["timeout_seconds"]:g} s for one call']
    if config.get('effort'):
        lines.append(f'Effort: {config["effort"]}')
    return lines


def model_names(config, api_key=None, timeout=5):
    """The model names that the endpoint of an HTTP route lists. An empty list when it gives none."""
    if config['route'] == 'anthropic':
        headers = {name: value for name, value in _anthropic_headers(config, api_key).items() if name != 'Content-Type'}
        url = config['base_url'] + '/v1/models?limit=1000'
    else:
        headers, url = _openai_headers(api_key), config['base_url'] + '/models'
    _, names, _ = _list_models(url, headers, timeout, config['max_response_bytes'])
    return names or []


routes.register_route('openai-compatible', routes.RouteAdapter(
    _openai_validate, _openai_build, _openai_check, _openai_describe, lambda config: config.get('api_key_env')))
routes.register_route('anthropic', routes.RouteAdapter(
    _anthropic_validate, _anthropic_build, _anthropic_check, _anthropic_describe, lambda config: config['api_key_env']))
