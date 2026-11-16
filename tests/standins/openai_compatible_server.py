"""A stand-in for an OpenAI-compatible chat server. It is not a model.

    python tests/standins/openai_compatible_server.py --port 8801 --replies scripted

It implements ``GET /v1/models`` and ``POST /v1/chat/completions`` in the form
that the official pages document (see docs/model-routes.md). With ``--replies
scripted`` it answers the bundled scenario requests with the fixed test
replies of authored_replies.py (a test double) and refuses every other request. ``--fail MODE`` makes every
chat request fail in one named way, to test how a route reports that failure.
"""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common  # noqa: E402

HTTP_FAULTS = {
    'unauthorized': (401, 'Incorrect API key provided.', 'invalid_request_error', 'invalid_api_key'),
    'forbidden': (403, 'Country, region, or territory not supported.', 'request_forbidden', 'unsupported_country'),
    'model_not_found': (404, 'The model does not exist or you do not have access to it.', 'invalid_request_error', 'model_not_found'),
    'bad_request': (400, 'Invalid value for a request field.', 'invalid_request_error', 'invalid_value'),
    'rate_limited': (429, 'Rate limit reached for requests.', 'rate_limit_error', 'rate_limit_exceeded'),
    'quota': (429, 'You exceeded your current quota, please check your plan and billing details.', 'insufficient_quota', 'insufficient_quota'),
    'server_error': (500, 'The server had an error while processing your request.', 'server_error', 'server_error'),
    'overloaded': (503, 'The model is temporarily overloaded.', 'server_error', 'server_is_overloaded'),
}
FAULTS = (*HTTP_FAULTS, 'echo_key', 'no_structured_output', 'no_max_completion_tokens', 'redirect', 'slow', 'drop',
          'garbage_envelope', 'huge', 'truncated', 'refused', 'content_filter', 'tool_call', 'other_model', 'no_model',
          'snapshot_model', 'no_models_endpoint', *common.REPLY_FAULTS)


def error(status, message, kind, code):
    return status, {}, {'error': {'message': message, 'type': kind, 'param': None, 'code': code}}


def make_server(*, model=common.DEFAULT_MODEL, replies='scripted', fail=None, port=0, delay=0.0):
    if fail is not None and fail not in FAULTS:
        raise ValueError('Unknown fault ' + str(fail))

    def respond(record, number):
        path = record['path'].split('?')[0]
        if fail == 'unauthorized':
            return error(*HTTP_FAULTS['unauthorized'])
        if record['method'] == 'GET' and path == '/v1/models':
            if fail == 'no_models_endpoint':
                return 404, {}, {'error': 'not found'}
            return 200, {}, {'object': 'list', 'data': [{'id': model, 'object': 'model', 'created': 0,
                                                         'owned_by': 'stand-in-not-a-model'}]}
        if record['method'] != 'POST' or path != '/v1/chat/completions':
            return 404, {}, {'error': {'message': 'Unknown path ' + path, 'type': 'invalid_request_error', 'code': None}}
        body = record['body'] if isinstance(record['body'], dict) else {}
        if fail in HTTP_FAULTS:
            return error(*HTTP_FAULTS[fail])
        if fail == 'echo_key':   # a provider that repeats the credential in its message
            return error(403, 'The key ' + record['headers'].get('authorization', '') + ' may not use this model.',
                         'permission_error', 'forbidden')
        if fail == 'no_structured_output' and 'response_format' in body:
            return error(400, "'response_format' of type '" + str(body['response_format'].get('type'))
                         + "' is not supported by this model.", 'invalid_request_error', 'unsupported_value')
        if fail == 'no_max_completion_tokens' and 'max_completion_tokens' in body:
            return error(400, "Unsupported parameter: 'max_completion_tokens'.", 'invalid_request_error', 'unsupported_parameter')
        if fail == 'redirect':
            return 302, {'Location': 'http://127.0.0.1:9/elsewhere'}, {'moved': True}
        if fail == 'slow':
            time.sleep(delay)
        if fail == 'drop':
            return None
        if fail == 'garbage_envelope':
            return 200, {}, b'this is not JSON'
        if fail == 'huge':
            return 200, {}, b'{"padding": "' + b'x' * 3_000_000 + b'"}'
        try:
            messages = body['messages']
            payload, schema = common.from_messages(messages[0]['content'], messages[1]['content'])
        except (KeyError, IndexError, TypeError, ValueError):
            return error(400, 'The request does not have the form that the routes of this project send.',
                         'invalid_request_error', 'stand_in_form')
        reply = common.reply_for(payload, schema, replies)
        if reply is None:
            return error(422, common.NO_REPLY, 'stand_in', 'no_authored_reply')
        text = common.faulty(json.dumps(reply, ensure_ascii=False), fail)
        message = {'role': 'assistant', 'content': text, 'refusal': None}
        reason = 'stop'
        if fail == 'truncated':
            message['content'], reason = text[:max(1, len(text) // 2)], 'length'
        elif fail == 'refused':
            message.update(content=None, refusal='I cannot help with that request.')
        elif fail == 'content_filter':
            message['content'], reason = '', 'content_filter'
        elif fail == 'tool_call':
            message.update(content=None, tool_calls=[{'id': 'call_1', 'type': 'function',
                                                      'function': {'name': 'x', 'arguments': '{}'}}])
            reason = 'tool_calls'
        answer = {'id': f'chatcmpl-standin-{number}', 'object': 'chat.completion', 'created': 0,
                  'model': 'another-model' if fail == 'other_model' else model + '-2026-01-01' if fail == 'snapshot_model' else model,
                  'system_fingerprint': 'stand-in-not-a-model',
                  'choices': [{'index': 0, 'message': message, 'finish_reason': reason}],
                  'usage': {'prompt_tokens': len(json.dumps(body)) // 4, 'completion_tokens': len(text) // 4,
                            'total_tokens': (len(json.dumps(body)) + len(text)) // 4}}
        if fail == 'no_model':
            del answer['model']
        return 200, {'x-request-id': f'standin-{number}'}, answer

    return common.StandInServer(respond, port=port)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--port', type=int, default=8801)
    parser.add_argument('--model', default=common.DEFAULT_MODEL)
    parser.add_argument('--replies', choices=('scripted', 'echo-ok'), default='scripted')
    parser.add_argument('--fail', choices=FAULTS)
    parser.add_argument('--delay', type=float, default=5.0, help='seconds to wait with --fail slow')
    args = parser.parse_args(argv)
    server = make_server(model=args.model, replies=args.replies, fail=args.fail, port=args.port, delay=args.delay)
    common.serve_forever(server, f'OpenAI-compatible stand-in; model name "{args.model}"; replies: {args.replies}'
                         + (f'; every chat request fails as: {args.fail}' if args.fail else '')
                         + f'. Route file: "base_url": "http://127.0.0.1:{server.port}/v1"')


if __name__ == '__main__':
    main()
