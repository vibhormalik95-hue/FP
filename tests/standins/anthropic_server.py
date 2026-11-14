"""A stand-in for the Anthropic Messages API. It is not a model.

    python tests/standins/anthropic_server.py --port 8802 --replies scripted

It implements ``GET /v1/models`` and ``POST /v1/messages`` in the form that the
official pages document (see docs/model-routes.md). It also refuses what the
documentation says the API refuses: a request without ``anthropic-version``,
the sampling parameters that API version 2026-10-21 removed, and a
structured-output schema with a keyword outside the documented subset. A route
that sent such a request to the real API would get the same kind of error.
"""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

HTTP_FAULTS = {
    'unauthorized': (401, 'authentication_error', 'invalid x-api-key'),
    'billing': (402, 'billing_error', 'Your credit balance is too low to access the API.'),
    'forbidden': (403, 'permission_error', 'Your API key does not have permission to use the specified resource.'),
    'model_not_found': (404, 'not_found_error', 'model: the requested model was not found.'),
    'too_large': (413, 'request_too_large', 'Request exceeds the maximum allowed number of bytes.'),
    'rate_limited': (429, 'rate_limit_error', 'This request would exceed your rate limit.'),
    'server_error': (500, 'api_error', 'An unexpected error has occurred.'),
    'timeout': (504, 'timeout_error', 'The request timed out while processing.'),
    'overloaded': (529, 'overloaded_error', 'Overloaded'),
    'bad_request': (400, 'invalid_request_error', 'messages: field required'),
}
FAULTS = (*HTTP_FAULTS, 'no_structured_output', 'redirect', 'slow', 'truncated', 'refused', 'context_full', 'tool_use',
          'two_blocks', 'thinking_block', 'other_model', 'snapshot_model', *common.REPLY_FAULTS)
_UNSUPPORTED = ('minLength', 'maxLength', 'maxItems', 'minimum', 'maximum', 'multipleOf', 'pattern', 'format')


def error(status, kind, message, number=0):
    return status, {'request-id': f'req_standin_{number}'}, {'type': 'error', 'error': {'type': kind, 'message': message},
                                                             'request_id': f'req_standin_{number}'}


def schema_problem(schema, path='schema'):
    """The first place where a schema leaves the documented structured-output subset, or ``None``."""
    if isinstance(schema, list):
        return next((found for index, item in enumerate(schema)
                     if (found := schema_problem(item, f'{path}[{index}]'))), None)
    if not isinstance(schema, dict):
        return None
    for name in _UNSUPPORTED:
        if name in schema:
            return f'{path}: the keyword {name} is not supported'
    if schema.get('minItems', 0) not in (0, 1):
        return f'{path}: minItems supports only 0 and 1'
    if schema.get('type') == 'object' and schema.get('additionalProperties') is not False:
        return f'{path}: additionalProperties must be false for an object'
    for name, value in schema.items():
        if name in ('enum', 'const', 'required'):
            continue
        children = value.items() if name == 'properties' and isinstance(value, dict) else [(name, value)]
        for key, child in children:
            found = schema_problem(child, f'{path}.{key}')
            if found:
                return found
    return None


def make_server(*, model=common.DEFAULT_MODEL, replies='scripted', fail=None, port=0, delay=0.0):
    if fail is not None and fail not in FAULTS:
        raise ValueError('Unknown fault ' + str(fail))

    def respond(record, number):
        path, headers = record['path'].split('?')[0], record['headers']
        if 'anthropic-version' not in headers and record['method'] == 'POST':
            return error(400, 'invalid_request_error', 'anthropic-version: header is required', number)
        if not headers.get('x-api-key') and not headers.get('authorization', '').startswith('Bearer ') or fail == 'unauthorized':
            return error(*HTTP_FAULTS['unauthorized'], number)
        if record['method'] == 'GET' and path == '/v1/models':
            return 200, {}, {'data': [{'type': 'model', 'id': model, 'display_name': 'Stand-in, not a model',
                                       'created_at': '1970-01-01T00:00:00Z', 'lifecycle': 'active'}],
                             'has_more': False, 'first_id': model, 'last_id': model}
        if record['method'] != 'POST' or path != '/v1/messages':
            return error(404, 'not_found_error', 'Unknown path ' + path, number)
        body = record['body'] if isinstance(record['body'], dict) else {}
        if fail in HTTP_FAULTS:
            return error(*HTTP_FAULTS[fail], number)
        if headers['anthropic-version'] == '2026-10-21' and {'temperature', 'top_p', 'top_k'} & set(body):
            return error(400, 'invalid_request_error', 'temperature: this parameter was removed in API version 2026-10-21', number)
        form = (body.get('output_config') or {}).get('format')
        if form is not None:
            if fail == 'no_structured_output':
                return error(400, 'invalid_request_error', 'output_config.format: structured outputs are not available', number)
            problem = None if form.get('type') == 'json_schema' else 'output_config.format.type must be json_schema'
            problem = problem or schema_problem(form.get('schema'))
            if problem:
                return error(400, 'invalid_request_error', 'output_config.format.' + problem, number)
        if fail == 'redirect':
            return 307, {'Location': 'http://127.0.0.1:9/elsewhere'}, {'moved': True}
        if fail == 'slow':
            time.sleep(delay)
        try:
            messages = body['messages']
            if not isinstance(body['max_tokens'], int) or not isinstance(body['model'], str):
                raise ValueError
            payload, schema = common.from_messages(body['system'], messages[0]['content'])
        except (KeyError, IndexError, TypeError, ValueError):
            return error(400, 'invalid_request_error', 'The request does not have the form that the routes of this '
                                                       'project send.', number)
        reply = common.reply_for(payload, schema, replies)
        if reply is None:
            return error(400, 'invalid_request_error', common.NO_REPLY, number)
        text = common.faulty(json.dumps(reply, ensure_ascii=False), fail)
        content, reason = [{'type': 'text', 'text': text}], 'end_turn'
        if fail == 'truncated':
            content, reason = [{'type': 'text', 'text': text[:max(1, len(text) // 2)]}], 'max_tokens'
        elif fail == 'refused':
            content, reason = [{'type': 'text', 'text': 'I cannot help with that request.'}], 'refusal'
        elif fail == 'context_full':
            content, reason = [{'type': 'text', 'text': text[:5]}], 'model_context_window_exceeded'
        elif fail == 'tool_use':
            content, reason = [{'type': 'tool_use', 'id': 'toolu_1', 'name': 'x', 'input': {}}], 'tool_use'
        elif fail == 'two_blocks':
            half = max(1, len(text) // 2)
            content = [{'type': 'text', 'text': text[:half]}, {'type': 'text', 'text': text[half:]}]
        elif fail == 'thinking_block':
            content = [{'type': 'thinking', 'thinking': 'stand-in thinking text', 'signature': 'none'}, content[0]]
        answer = {'id': f'msg_standin_{number}', 'type': 'message', 'role': 'assistant',
                  'model': 'another-model' if fail == 'other_model' else model + '-20260101' if fail == 'snapshot_model' else model,
                  'content': content, 'stop_reason': reason, 'stop_sequence': None,
                  'usage': {'input_tokens': len(json.dumps(body)) // 4, 'output_tokens': len(text) // 4}}
        return 200, {'request-id': f'req_standin_{number}'}, answer

    return common.StandInServer(respond, port=port)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--port', type=int, default=8802)
    parser.add_argument('--model', default=common.DEFAULT_MODEL)
    parser.add_argument('--replies', choices=('scripted', 'echo-ok'), default='scripted')
    parser.add_argument('--fail', choices=FAULTS)
    parser.add_argument('--delay', type=float, default=5.0, help='seconds to wait with --fail slow')
    args = parser.parse_args(argv)
    server = make_server(model=args.model, replies=args.replies, fail=args.fail, port=args.port, delay=args.delay)
    common.serve_forever(server, f'Anthropic Messages stand-in; model name "{args.model}"; replies: {args.replies}'
                         + (f'; every message request fails as: {args.fail}' if args.fail else '')
                         + f'. Route file: "base_url": "http://127.0.0.1:{server.port}"')


if __name__ == '__main__':
    main()
