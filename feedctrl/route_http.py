"""HTTP routes: an OpenAI-compatible chat endpoint and the Anthropic Messages API.

Both send one request for each call and never a second one. The key travels
only in a request header. A redirect is refused, because a redirect could carry
the key to another host. Nothing here reads a credential from disk.

One call has one time limit, from the first byte sent to the last byte read. A
stop of the application ends a running call: a watcher closes its connection.

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
import threading
import time
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
# Places in a schema where the names are names of the application, not keywords.
_NAME_MAPS = ('properties', '$defs', 'definitions', 'patternProperties', 'dependentSchemas')
_OPENAI_RESERVED = ('model', 'messages', 'stream', 'response_format', 'max_tokens', 'max_completion_tokens', 'n',
                    'tools', 'tool_choice', 'functions', 'function_call', 'temperature', 'seed')
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
ANTHROPIC_URL = 'https://api.anthropic.com'
ANTHROPIC_VERSIONS = ('2026-10-21', '2023-06-01')
_BILLING_WORDS = ('quota', 'credit', 'billing', 'spend', 'insufficient', 'usage limit', 'usage_limit', 'payment')


def _is_object(schema):
    kind = schema.get('type')
    return kind == 'object' or (isinstance(kind, list) and 'object' in kind)


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
        if name in _NAME_MAPS and isinstance(value, dict):
            result[name] = {key: provider_schema(item, close_objects=close_objects) for key, item in value.items()}
        elif name in ('enum', 'const', 'required', 'default', 'examples'):
            result[name] = deepcopy(value)
        else:
            result[name] = provider_schema(value, close_objects=close_objects)
    # An object that lists the schema of its further properties is a map; it stays open.
    if close_objects and _is_object(result) and not isinstance(result.get('additionalProperties'), dict):
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
    if _is_object(schema):
        properties = schema.get('properties', {})
        if schema.get('additionalProperties') is not False or sorted(schema.get('required', [])) != sorted(properties):
            return False
    return all(is_strict(value) for name, value in schema.items() if name not in ('enum', 'const', 'required'))


# --------------------------------------------------------------------------
# One HTTP exchange
# --------------------------------------------------------------------------

def _place(url):
    """An address without a query, a fragment or a user name, for a message."""
    try:
        parts = urllib.parse.urlsplit(url)
        host = parts.hostname or ''
        port = f':{parts.port}' if parts.port else ''
    except ValueError:
        return 'another address'
    return urllib.parse.urlunsplit((parts.scheme, host + port, parts.path, '', '')) if host else 'another address'


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, handle, code, message, headers, new_url):
        error = RouteError('redirect_refused',
                           f'The endpoint answered with a redirect (HTTP {code}) to {_place(new_url)}. It is not followed.',
                           'If that address is the right one, put it in "base_url" in the route file.')
        error.http_status = code
        raise error


class _Connections:
    """The connections of one exchange, so that a watcher can end it from another thread."""

    def __init__(self):
        self._lock, self._sockets, self.reason = threading.Lock(), [], None

    @staticmethod
    def _end(connection):
        # The plain shutdown wakes a read that waits in another thread, also for
        # a TLS connection. The close is for a system where the shutdown does not.
        for action in (lambda: socket.socket.shutdown(connection, socket.SHUT_RDWR), connection.close):
            try:
                action()
            except (OSError, ValueError):
                pass

    def add(self, connection):
        with self._lock:
            self._sockets.append(connection)
            ended = self.reason is not None
        if ended:
            self._end(connection)

    def cancel(self, reason):
        with self._lock:
            if self.reason is not None:
                return
            self.reason = reason
            sockets = list(self._sockets)
        for connection in sockets:
            self._end(connection)


def _tracked(base, connections):
    class Connection(base):
        def connect(self):
            super().connect()
            connections.add(self.sock)
    return Connection


class _TrackedHTTP(urllib.request.HTTPHandler):
    def __init__(self, connections):
        super().__init__()
        self._connections = connections

    def do_open(self, http_class, req, **http_conn_args):
        return super().do_open(_tracked(http_class, self._connections), req, **http_conn_args)


class _TrackedHTTPS(urllib.request.HTTPSHandler):
    def __init__(self, connections):
        super().__init__()
        self._connections = connections

    def do_open(self, http_class, req, **http_conn_args):
        return super().do_open(_tracked(http_class, self._connections), req, **http_conn_args)


def _opener(url, connections):
    handlers = [_NoRedirect(), _TrackedHTTP(connections), _TrackedHTTPS(connections)]
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
    place = _place(url)
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


def _ended(reason, timeout):
    if reason == 'stop':
        return RouteError('stopped', 'The application is stopping. The running model call was ended.')
    return RouteError('timeout', f'The endpoint did not finish its answer within {timeout:g} s. The call was ended.')


def exchange(request, timeout, limit):
    """Send one request. Return ``(status, headers, body)``; an HTTP error status is returned, not raised.

    ``timeout`` is the limit for the whole exchange, not for one read: a server
    that sends one byte at a time is ended at the limit as well.
    """
    connections = _Connections()
    token = routes.watch(connections.cancel, time.monotonic() + timeout)
    try:
        try:
            with _opener(request.full_url, connections).open(request, timeout=timeout) as response:
                status, headers, body = response.status, response.headers, _read(response, limit)
        except urllib.error.HTTPError as error:
            status, headers = error.code, error.headers
            try:
                body = _read(error, limit)
            except (RouteError, OSError, ValueError, http.client.HTTPException):
                body = b''
        if connections.reason:
            raise _ended(connections.reason, timeout)
        return status, headers, body
    except RouteError:
        raise
    except Exception as error:   # noqa: BLE001  (a connection that the watcher ended can fail in many ways)
        if connections.reason:
            raise _ended(connections.reason, timeout) from None
        if isinstance(error, urllib.error.URLError):
            raise _network_error(error.reason, request.full_url) from None
        if isinstance(error, (TimeoutError, socket.timeout)):
            raise RouteError('timeout') from None
        if isinstance(error, (http.client.HTTPException, OSError)):
            raise _network_error(error, request.full_url) from None
        raise
    finally:
        routes.unwatch(token)


def _header(headers, *names):
    for name in names:
        value = headers.get(name) if headers is not None else None
        if isinstance(value, str) and value.strip():
            return routes.ascii_text(routes.one_line(routes.scrub(value), 200))
    return None


def _json_object(raw):
    try:
        value = _decode(raw.decode('utf-8'))
    except (ValueError, UnicodeDecodeError, RecursionError):
        return None
    return value if isinstance(value, dict) else None


def _provider_message(body):
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
    return (routes.ascii_text(routes.one_line(routes.scrub(message), 300)),
            routes.ascii_text(routes.one_line(routes.scrub(kind), 80)))


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


def _send(config, request, receipt):
    """One exchange. A refused redirect still leaves its status in the receipt."""
    try:
        return exchange(request, config['timeout_seconds'], config['max_response_bytes'])
    except RouteError as error:
        if error.http_status is not None:
            receipt['http_status'] = error.http_status
        raise


def _end(recorder, ordinal, receipt, status, headers, raw):
    receipt.update(http_status=status, provider_request_id=_header(headers, 'request-id', 'x-request-id'),
                   response_sha256=hashlib.sha256(raw).hexdigest(), response_bytes=len(raw))
    # A provider can repeat the credential in its answer. The file then holds
    # the reply with the credential removed; the hash is of the original.
    if recorder.write_after(ordinal, 'response.txt', raw, receipt):
        receipt['response_record_scrubbed'] = True


def _foreign_key_default(raw, base_url, home, name, what):
    """Refuse a key variable that a preset supplies for one host when the file names another host.

    This computer is another host too: a proxy or a stand-in there must not get
    the key of the provider unless the file names the variable itself.
    """
    host = routes.address_host(base_url) or ''
    if 'api_key_env' not in raw and host != routes.address_host(home):
        routes.reject(f'{what} is for {home}. This file names the address {base_url}, and it names no key variable.',
                      f'The key in {name} is not sent to another host by default. Name the variable that holds the key '
                      'for that host in "api_key_env".')


# --------------------------------------------------------------------------
# OpenAI-compatible chat completions
# --------------------------------------------------------------------------

def _openai_validate(raw):
    routes.take(raw, {'route', 'preset', 'base_url', 'model', 'api_key_env', 'structured_output', 'token_limit_field',
                      'max_output_tokens', 'temperature', 'seed', 'allow_insecure_http', 'allow_reported_model_mismatch',
                      'accept_reported_models', 'extra_body', 'max_calls', 'timeout_seconds', 'max_request_bytes',
                      'max_response_bytes'}, 'openai-compatible')
    preset = routes.choice_setting(raw, 'preset', tuple(PRESETS), 'custom')
    merged = {**PRESETS[preset], **raw}
    insecure = routes.flag_setting(merged, 'allow_insecure_http')
    if 'base_url' not in merged:
        routes.reject('The "openai-compatible" route needs "base_url", for example http://127.0.0.1:11434/v1.')
    base_url = routes.url_setting(merged, 'base_url', allow_insecure=insecure)
    if 'api_key_env' in PRESETS[preset]:
        _foreign_key_default(raw, base_url, PRESETS[preset]['base_url'], PRESETS[preset]['api_key_env'],
                             f'The preset "{preset}"')
    return {'preset': preset, 'base_url': base_url,
            'model': routes.text_setting(merged, 'model', 200, pattern=routes.MODEL_NAME),
            'api_key_env': routes.key_env_setting(merged),
            'structured_output': routes.choice_setting(merged, 'structured_output', ('json_schema', 'json_object', 'prompt'), 'json_schema'),
            'token_limit_field': routes.choice_setting(merged, 'token_limit_field', ('max_tokens', 'max_completion_tokens'), 'max_tokens'),
            'max_output_tokens': routes.number_setting(merged, 'max_output_tokens', 16, 200_000, LOCAL_OUTPUT_TOKENS),
            'temperature': routes.number_setting(merged, 'temperature', 0, 2, None, integer=False),
            'seed': routes.number_setting(merged, 'seed', 0, 2 ** 31 - 1, None),
            'allow_insecure_http': insecure or None,
            'allow_reported_model_mismatch': routes.flag_setting(merged, 'allow_reported_model_mismatch') or None,
            'accept_reported_models': routes.accepted_models_setting(merged),
            'extra_body': routes.extra_body_setting(merged, _OPENAI_RESERVED) or None,
            **routes.common_limits(merged)}


def _openai_headers(api_key):
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json', 'User-Agent': USER_AGENT}
    if api_key:
        headers['Authorization'] = 'Bearer ' + api_key
    return headers


def _openai_failure(status, raw, config):
    """Name a failed chat request. The status code decides first, then the words of the provider."""
    message, kind = _provider_message(_json_object(raw))
    words = (message + ' ' + kind).lower()
    mode, model, said = config['structured_output'], config['model'], _quoted(message)
    if status == 200:   # some servers report an error in an answer with status 200
        return RouteError('provider_error', 'The endpoint answered HTTP 200 with an error object in place of a reply.' + said,
                          'Read the provider message. If the model is still loading, wait and try again.')
    if 300 <= status < 400:
        return RouteError('unexpected_reply', f'The endpoint answered HTTP {status}, which is not a reply to a chat request.')
    if status in (400, 422):
        if any(word in words for word in ('response_format', 'json_schema', 'json_object', 'structured output', 'json mode')):
            others = [value for value in ('json_schema', 'json_object', 'prompt') if value != mode]
            return RouteError('structured_output_unsupported',
                              f'The endpoint did not accept "structured_output": "{mode}" (HTTP {status}).' + said,
                              f'Set "structured_output" to "{others[0]}" or "{others[1]}" in the route file and run the check.')
        limit_named = 'max_tokens' in words or 'max_completion_tokens' in words
        if limit_named and any(word in words for word in ('unsupported', 'unrecognized', 'unknown', 'not supported',
                                                           'not allowed', 'unexpected', 'extra')):
            other = 'max_tokens' if config['token_limit_field'] == 'max_completion_tokens' else 'max_completion_tokens'
            return RouteError('bad_request', f'The endpoint did not accept the output-limit field (HTTP {status}).' + said,
                              f'Set "token_limit_field" to "{other}" in the route file.')
        if limit_named or 'context length' in words or 'context_length' in words or 'context window' in words:
            return RouteError('bad_request', f'The endpoint did not accept the output limit or the size of the request (HTTP {status}).' + said,
                              'Lower "max_output_tokens" in the route file to a value that the model supports, '
                              'or choose a smaller evidence scope.')
        if 'temperature' in words or 'seed' in words:
            return RouteError('bad_request', f'The endpoint did not accept "temperature" or "seed" (HTTP {status}).' + said,
                              'Remove "temperature" and "seed" from the route file.')
        return RouteError('bad_request', f'The endpoint rejected the request (HTTP {status}).' + said)
    if status == 401:
        name = config.get('api_key_env')
        return RouteError('authentication', 'The provider rejected the API key (HTTP 401).',
                          f'Check the key in the environment variable {name}, then start again.' if name else
                          'This endpoint needs a key. Add "api_key_env" to the route file and set that variable.')
    if status == 402 or (status in (403, 429) and any(word in words for word in _BILLING_WORDS)):
        return RouteError('billing', f'The provider reports a billing, quota or usage-limit problem (HTTP {status}).' + said)
    if status == 403:
        return RouteError('permission', 'The provider refused this request for this account or network (HTTP 403).' + said)
    if status == 404:
        action = 'Run the check to list the model names. Check that "base_url" ends with /v1.'
        if config['preset'] == 'ollama':
            action = f'Run "ollama pull {model}" or correct "model". Check that "base_url" ends with /v1.'
        return RouteError('model_not_found', f'The endpoint did not find the model "{model}" or the address (HTTP 404).'
                          + said, action)
    if status in (408, 504):
        return RouteError('timeout', f'The endpoint reported a timeout (HTTP {status}).')
    if status == 429:
        return RouteError('rate_limited', 'The provider limits the request rate (HTTP 429).' + said)
    if status in (503, 529):
        return RouteError('provider_overloaded', f'The endpoint is overloaded or not ready (HTTP {status}).' + said)
    if status >= 500:
        return RouteError('provider_error', f'The endpoint had an internal error (HTTP {status}).' + said)
    return RouteError('bad_request', f'The endpoint rejected the request (HTTP {status}).' + said)


def _openai_build(config, *, api_key=None, record_dir=None, relay_dir=None):
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
        status, response_headers, raw = _send(config, request, receipt)
        _end(recorder, ordinal, receipt, status, response_headers, raw)
        if status != 200:
            raise _openai_failure(status, raw, config)
        envelope = _json_object(raw)
        choices = envelope.get('choices') if envelope else None
        if not isinstance(choices, list) or not choices:
            if envelope and envelope.get('error'):
                raise _openai_failure(200, raw, config)
            raise RouteError('unexpected_reply', 'The endpoint did not return a chat completion object.')
        if len(choices) != 1 or not isinstance(choices[0], dict):
            # One reply is asked for. With several, the route would have to choose, and it never chooses.
            raise RouteError('unexpected_reply', f'The endpoint returned {len(choices)} choices; one is expected.')
        if isinstance(envelope.get('model'), str):
            receipt['reported_model'] = routes.page_text(envelope['model'], 200)
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
        receipt['model_match_rule'] = routes.require_model(model, envelope.get('model'),
                                                           config.get('allow_reported_model_mismatch'),
                                                           config.get('accept_reported_models'))
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


def _listed(model, names, accepted):
    """``(listed name, rule)`` for the listed name that stands for the requested model, or ``None``."""
    for wanted in ('equal', 'default_tag', 'dated_snapshot', 'accepted_by_setting'):
        for name in names:
            if routes.model_rule(model, name, accepted) == wanted:
                return name, wanted
    for name in names:
        if routes.model_rule(name, model) in ('default_tag', 'dated_snapshot'):
            return name, 'requested_name_is_a_dated_form_of_the_listed_name'
    return None


def _report_models(status, names, complete, config, step, how, failure):
    """Turn a model list into the ``endpoint`` step. Return whether the check may go on."""
    model = config['model']
    if status in (404, 405, 501) or (status == 200 and names is None):
        step('endpoint', True, f'The endpoint answered (HTTP {status}) but gave no model list. The test call decides.')
        return True
    if status != 200:
        error = failure(status)
        step('endpoint', False, error.message, error.action)
        return False
    shown = ', '.join(names[:20]) or 'none'
    found = _listed(model, names, config.get('accept_reported_models'))
    if found and found[1] == 'equal':
        step('endpoint', True, f'The endpoint answered and lists the model "{model}" ({len(names)} models listed).')
        return True
    if found:
        step('endpoint', True, f'The endpoint answered. It lists "{found[0]}", which stands for the requested "{model}" '
                               f'by the rule "{found[1]}" ({len(names)} models listed). The test call decides.')
        return True
    if not complete:
        step('endpoint', True, f'The endpoint answered. "{model}" is not among the first {len(names)} listed models; '
                               'the test call decides.')
        return True
    step('endpoint', False, f'The endpoint answered, but it does not list the model "{model}". Listed: {shown}.', how)
    return False


def _openai_check(config, *, api_key=None, step):
    status, names, complete = _list_models(config['base_url'] + '/models', _openai_headers(api_key),
                                           config['timeout_seconds'], config['max_response_bytes'])
    how = 'Put one of the listed names in "model".'
    if config['preset'] == 'ollama':
        how = f'Run "ollama pull {config["model"]}", or put one of the listed names in "model".'
    return _report_models(status, names, complete, config, step, how,
                          lambda code: _openai_failure(code, b'', config))


def _openai_describe(config):
    lines = [f'Endpoint: {config["base_url"]}/chat/completions' + (f' (preset {config["preset"]})' if config['preset'] != 'custom' else ''),
             f'Model: {config["model"]}',
             f'Structured output: {config["structured_output"]}; output limit {config["max_output_tokens"]} tokens '
             f'({config["token_limit_field"]}); {config["timeout_seconds"]:g} s for one call']
    if config.get('temperature') is not None or config.get('seed') is not None:
        lines.append(f'Sampling: temperature {config.get("temperature", "not sent")}, seed {config.get("seed", "not sent")}')
    if config.get('accept_reported_models'):
        lines.append('Reported model names that are accepted: ' + ', '.join(config['accept_reported_models']))
    if config.get('extra_body'):
        lines.append('Further request fields (extra_body): ' + ', '.join(sorted(config['extra_body'])))
    return lines


# --------------------------------------------------------------------------
# Anthropic Messages API
# --------------------------------------------------------------------------

def _anthropic_validate(raw):
    routes.take(raw, {'route', 'base_url', 'model', 'api_key_env', 'anthropic_version', 'auth_header',
                      'anthropic_workspace_id', 'structured_output', 'max_output_tokens', 'effort', 'allow_insecure_http',
                      'allow_reported_model_mismatch', 'accept_reported_models', 'extra_body', 'max_calls',
                      'timeout_seconds', 'max_request_bytes', 'max_response_bytes'}, 'anthropic')
    insecure = routes.flag_setting(raw, 'allow_insecure_http')
    base_url = routes.url_setting(raw, 'base_url', default=ANTHROPIC_URL, allow_insecure=insecure)
    _foreign_key_default(raw, base_url, ANTHROPIC_URL, 'ANTHROPIC_API_KEY', 'The default key variable of this route')
    return {'base_url': base_url,
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
            'accept_reported_models': routes.accepted_models_setting(raw),
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


def _anthropic_failure(status, raw, config):
    """Name a failed Messages request. Each message names the status code that came."""
    body = _json_object(raw)
    message, kind = _provider_message(body)
    kind = kind.split(' ')[0] if kind else ''
    name, said = config['api_key_env'], _quoted(message)
    if status == 200:
        return RouteError('provider_error', 'The API answered HTTP 200 with an error object in place of a message.' + said)
    if 300 <= status < 400:
        return RouteError('unexpected_reply', f'The API answered HTTP {status}, which is not a reply to a message request.')
    if kind == 'authentication_error' or status == 401:
        return RouteError('authentication', f'The provider rejected the API key (HTTP {status}).',
                          f'Check the key in the environment variable {name}, then start again.')
    if kind == 'not_found_error' or status == 404:
        return RouteError('model_not_found', f'The API did not find the model "{config["model"]}" (HTTP {status}).' + said)
    if kind == 'request_too_large' or status == 413:
        return RouteError('bad_request', f'The request is larger than the API accepts (HTTP {status}).',
                          'Choose a smaller evidence scope.')
    if kind == 'invalid_request_error' or status == 400:
        words = message.lower()
        if config['structured_output'] == 'json_schema' and any(
                word in words for word in ('output_config', 'output_format', 'structured output', 'json_schema')):
            return RouteError('structured_output_unsupported',
                              f'The API did not accept the structured-output request (HTTP {status}).' + said,
                              'Set "structured_output" to "prompt" in the route file and run the check.')
        if any(word in words for word in ('spend', 'credit')) or ('usage' in words and 'limit' in words):
            return RouteError('billing', f'The API reports a spend or usage limit (HTTP {status}).' + said)
        if 'max_tokens' in words:
            return RouteError('bad_request', f'The API did not accept the output limit (HTTP {status}).' + said,
                              'Lower "max_output_tokens" in the route file to a value that the model supports.')
        return RouteError('bad_request', f'The API rejected the request (HTTP {status}).' + said)
    category = _ANTHROPIC_TYPES.get(kind)
    if category is None:
        category = ('provider_overloaded' if status == 529 else 'rate_limited' if status == 429 else
                    'billing' if status == 402 else 'permission' if status == 403 else
                    'timeout' if status == 504 else 'provider_error' if status >= 500 else 'bad_request')
    sentence = routes.CATEGORIES[category][0][:-1] + f' (HTTP {status}).'
    return RouteError(category, sentence + (said if category != 'authentication' else ''))


def _anthropic_build(config, *, api_key=None, record_dir=None, relay_dir=None):
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
        status, response_headers, raw = _send(config, request, receipt)
        _end(recorder, ordinal, receipt, status, response_headers, raw)
        if status != 200:
            raise _anthropic_failure(status, raw, config)
        envelope = _json_object(raw)
        if envelope and envelope.get('type') == 'error':
            raise _anthropic_failure(200, raw, config)
        if not envelope or envelope.get('type') != 'message' or not isinstance(envelope.get('content'), list):
            raise RouteError('unexpected_reply', 'The API did not return a message object.')
        if isinstance(envelope.get('model'), str):
            receipt['reported_model'] = routes.page_text(envelope['model'], 200)
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
        receipt['model_match_rule'] = routes.require_model(model, envelope.get('model'),
                                                           config.get('allow_reported_model_mismatch'),
                                                           config.get('accept_reported_models'))
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
    headers = {name: value for name, value in _anthropic_headers(config, api_key).items() if name != 'Content-Type'}
    status, names, complete = _list_models(config['base_url'] + '/v1/models?limit=1000', headers,
                                           config['timeout_seconds'], config['max_response_bytes'])
    return _report_models(status, names, complete, config, step, 'Put one of the listed names in "model".',
                          lambda code: _anthropic_failure(code, b'', config))


def _anthropic_describe(config):
    lines = [f'Endpoint: {config["base_url"]}/v1/messages (API version {config["anthropic_version"]})',
             f'Model: {config["model"]}',
             f'Structured output: {config["structured_output"]}; output limit {config["max_output_tokens"]} tokens; '
             f'{config["timeout_seconds"]:g} s for one call']
    if config.get('effort'):
        lines.append(f'Effort: {config["effort"]}')
    if config.get('anthropic_workspace_id'):
        lines.append(f'Workspace: {config["anthropic_workspace_id"]}')
    if config.get('accept_reported_models'):
        lines.append('Reported model names that are accepted: ' + ', '.join(config['accept_reported_models']))
    if config.get('extra_body'):
        lines.append('Further request fields (extra_body): ' + ', '.join(sorted(config['extra_body'])))
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
