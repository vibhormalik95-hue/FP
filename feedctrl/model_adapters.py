"""Explicit, bounded model transports for the reviewed semantic workflow.

The inference contract is infer(payload, schema) -> JSON object. Transport does
not choose membership, repair responses or approve changes. Hosted inference is
disabled unless an operator supplies a separately authorized run configuration.
"""
from __future__ import annotations

import base64
from copy import deepcopy
import hashlib
import json
import re
import threading
import time
import urllib.error
import urllib.request

from feedctrl.controls import ParserOperationalError

ENDPOINT = 'https://api.openai.com/v1/responses'


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def _hash(value):
    return hashlib.sha256(_json(value)).hexdigest()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def _decode(raw):
    return json.loads(raw, object_pairs_hook=_unique_object,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ParserOperationalError('Hosted model redirect rejected')


def make_openai_responses_infer(*, api_key, model, reasoning_effort,
                               authorized=False, max_calls=2,
                               max_output_tokens=4096, timeout=90,
                               max_request_bytes=20000):
    """Return (infer, provenance, receipts), with zero constructor network calls.

    authorized is an operational gate, not proof of user consent. The caller must
    establish destination/data/spend authority and lock the run before setting it.
    No key is read from disk or environment; no alias is silently substituted.
    A failed/timeout attempt consumes a call. There are no retries or tools.
    """
    if authorized is not True:
        raise ValueError('Hosted generation requires separate data and spend authorization')
    if not isinstance(api_key, str) or not api_key.strip() or any(c.isspace() for c in api_key):
        raise ValueError('Explicit valid API credential required')
    if not isinstance(model, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,150}', model):
        raise ValueError('Explicit provider model identifier required')
    if reasoning_effort not in ('low', 'medium', 'high', 'xhigh', 'max'):
        raise ValueError('Explicit supported reasoning effort required')
    for value, lower, upper in ((max_calls, 1, 10), (max_output_tokens, 1, 5000),
                                (max_request_bytes, 1, 50000)):
        if type(value) is not int or not lower <= value <= upper:
            raise ValueError('Invalid hosted run budget')
    if type(timeout) not in (int, float) or not 0 < timeout <= 300:
        raise ValueError('Invalid hosted timeout')
    config = {'backend': 'openai-responses', 'endpoint': ENDPOINT, 'model': model,
              'reasoning_effort': reasoning_effort, 'max_calls': max_calls,
              'max_output_tokens': max_output_tokens, 'timeout_seconds': timeout,
              'max_request_bytes': max_request_bytes, 'store': False,
              'retries': 0, 'tools': []}
    provenance = {**config, 'digest': _hash(config),
                  'digest_kind': 'configuration_sha256_not_model_weights',
                  'identity_limit': 'Requested API identifier; each returned model is checked. No weight attestation.'}
    receipts, lock, attempted = [], threading.Lock(), 0
    opener = urllib.request.build_opener(_NoRedirect())

    def infer(payload, schema):
        nonlocal attempted
        owned, owned_schema = deepcopy(payload), deepcopy(schema)
        if not isinstance(owned, dict) or not isinstance(owned.get('system'), str):
            raise ValueError('Explicit system prompt required')
        if not isinstance(owned_schema, dict) or owned_schema.get('type') != 'object':
            raise ValueError('Object response schema required')
        body = {'model': model, 'store': False, 'stream': False,
                'reasoning': {'effort': reasoning_effort},
                'max_output_tokens': max_output_tokens,
                'input': [{'role': 'system', 'content': owned['system']},
                          {'role': 'user', 'content': _json({k: v for k, v in owned.items()
                                                            if k != 'system'}).decode('utf-8')}],
                'text': {'format': {'type': 'json_schema', 'name': 'feed_control',
                                    'strict': True, 'schema': owned_schema}}}
        request_bytes = _json(body)
        if len(request_bytes) > max_request_bytes:
            raise ValueError('Hosted request exceeds locked evidence budget; no truncation')
        with lock:
            if attempted >= max_calls:
                raise ParserOperationalError('Hosted run call budget exhausted')
            attempted += 1
            receipt = {'call_id': attempted, 'representation': 'actual_hosted_attempt',
                       'request': deepcopy(body), 'request_sha256': hashlib.sha256(request_bytes).hexdigest(),
                       'schema_sha256': _hash(owned_schema), 'outcome': 'started',
                       'started_unix': time.time()}
            receipts.append(receipt)
        started = time.monotonic()
        try:
            request = urllib.request.Request(ENDPOINT, data=request_bytes, method='POST',
                headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + api_key})
            with opener.open(request, timeout=timeout) as response:
                receipt['http_status'] = response.status
                receipt['provider_request_id'] = response.headers.get('x-request-id')
                raw_bytes = response.read(2_000_001)
            # Preserve original response bytes before envelope/semantic validation.
            receipt['response_base64'] = base64.b64encode(raw_bytes).decode('ascii')
            receipt['response_sha256'] = hashlib.sha256(raw_bytes).hexdigest()
            receipt['response_capture_truncated'] = len(raw_bytes) > 2_000_000
            if len(raw_bytes) > 2_000_000:
                raise ValueError('Hosted response exceeded byte budget')
            raw = _decode(raw_bytes)
            receipt['raw_response'] = deepcopy(raw)
            if (not isinstance(raw, dict) or raw.get('status') != 'completed'
                    or raw.get('error') is not None or raw.get('incomplete_details') is not None):
                raise ValueError('Hosted response not completed')
            if raw.get('model') != model:
                raise ValueError('Returned model differs from locked requested identity')
            receipt['returned_model'] = raw['model']
            receipt['usage'] = deepcopy(raw.get('usage'))
            output = raw.get('output')
            if not isinstance(output, list):
                raise ValueError('Missing hosted output envelope')
            texts = []
            for item in output:
                if not isinstance(item, dict):
                    raise ValueError('Malformed hosted output item')
                if item.get('type') == 'reasoning':
                    continue
                if item.get('type') != 'message' or item.get('role') != 'assistant' or item.get('status') != 'completed':
                    raise ValueError('Unexpected hosted output item')
                content = item.get('content')
                if not isinstance(content, list):
                    raise ValueError('Missing hosted message content')
                for part in content:
                    if not isinstance(part, dict) or part.get('type') != 'output_text' or not isinstance(part.get('text'), str):
                        raise ValueError('Hosted refusal or unsupported content')
                    texts.append(part['text'])
            if len(texts) != 1:
                raise ValueError('Expected one complete JSON text; no concatenation or repair')
            parsed = _decode(texts[0])
            if not isinstance(parsed, dict):
                raise ValueError('Hosted response is not a JSON object')
            receipt['outcome'] = 'parsed_transport_only'
            return deepcopy(parsed)
        except (ValueError, TypeError, KeyError, urllib.error.URLError, OSError, ParserOperationalError) as exc:
            receipt['outcome'] = 'error'
            receipt['error_type'] = type(exc).__name__
            if isinstance(exc, urllib.error.HTTPError):
                receipt['http_status'] = exc.code
                receipt['provider_request_id'] = exc.headers.get('x-request-id') if exc.headers else None
                raw_bytes = exc.read(2_000_001)
                receipt['response_base64'] = base64.b64encode(raw_bytes).decode('ascii')
                receipt['response_sha256'] = hashlib.sha256(raw_bytes).hexdigest()
                receipt['response_capture_truncated'] = len(raw_bytes) > 2_000_000
            # Do not echo a provider error body or credential in a user-facing error.
            raise ParserOperationalError('Hosted model attempt failed: ' + type(exc).__name__) from exc
        finally:
            receipt['elapsed_seconds'] = time.monotonic() - started

    return infer, deepcopy(provenance), receipts
