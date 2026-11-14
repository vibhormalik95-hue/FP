"""The two HTTP routes against stand-in servers on 127.0.0.1.

The stand-ins implement the request and response shapes that the official
pages document. They are not models and not the real services: these tests
show that a route sends the documented request, applies the reply rule and
names each failure. They do not show that a real provider accepts the request.
"""
import http.server
import json
from pathlib import Path
import shutil
import socket
import ssl
import subprocess
import sys
import threading

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))

from feedctrl import model_routes, route_http  # noqa: E402
from feedctrl.model_routes import RouteError  # noqa: E402
from standins import anthropic_server, common, openai_compatible_server  # noqa: E402
from standins.route_state import fresh_route_state  # noqa: E402,F401  (autouse)

KEY = 'sk-test-0123456789abcdefSECRET'
MODEL = common.DEFAULT_MODEL
PAYLOAD = dict(model_routes.TEST_PAYLOAD)
SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['ok'],
          'properties': {'ok': {'type': 'boolean'}}}


def openai_config(server, **settings):
    return {'route': 'openai-compatible', 'base_url': server.url + '/v1', 'model': MODEL, **settings}


def anthropic_config(server, **settings):
    return {'route': 'anthropic', 'base_url': server.url, 'model': MODEL, 'api_key_env': 'ANTHROPIC_API_KEY', **settings}


def call(config, *, api_key=None, record_dir=None, payload=PAYLOAD, schema=SCHEMA):
    infer, identity, receipts = model_routes.build_route(config, api_key=api_key, record_dir=record_dir)
    try:
        return infer(dict(payload), dict(schema)), identity, receipts, None
    except RouteError as error:
        return None, identity, receipts, error


def free_port():
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        return probe.getsockname()[1]


# ---------------------------------------------------------------- OpenAI-compatible: the request

def test_the_chat_request_has_the_documented_shape_and_no_key_without_a_key():
    with openai_compatible_server.make_server() as server:
        result, identity, receipts, error = call(openai_config(server))
        sent = server.requests[-1]
    assert error is None and result == {'ok': True}
    assert sent['method'] == 'POST' and sent['path'] == '/v1/chat/completions'
    assert 'authorization' not in sent['headers'] and sent['headers']['content-type'] == 'application/json'
    assert sent['headers']['user-agent'].startswith('feed-control-lab')
    body = sent['body']
    assert set(body) == {'model', 'stream', 'max_tokens', 'messages', 'response_format'}
    assert body['model'] == MODEL and body['stream'] is False and body['max_tokens'] == 4096
    assert [message['role'] for message in body['messages']] == ['system', 'user']
    assert body['messages'][0]['content'].startswith(PAYLOAD['system']) and model_routes.OUTPUT_MARKER in body['messages'][0]['content']
    assert json.loads(body['messages'][1]['content']) == {'test': 'connection'}
    assert body['response_format'] == {'type': 'json_schema', 'json_schema': {'name': 'feed_control_reply', 'strict': True,
                                                                             'schema': SCHEMA}}
    assert identity['backend'] == 'openai-compatible-chat' and identity['model'] == MODEL and identity['live_model'] is True
    assert len(identity['digest']) == 64 and identity['route']['base_url'] == server.url + '/v1'
    receipt = receipts[0]
    assert receipt['outcome'] == 'parsed_transport_only' and receipt['http_status'] == 200
    assert receipt['requested_model'] == receipt['reported_model'] == MODEL and receipt['provider_request_id'] == 'standin-1'
    assert receipt['usage']['total_tokens'] > 0 and receipt['finish_reason'] == 'stop' and receipt['ordinal'] == 1
    assert receipt['started_utc'] <= receipt['finished_utc'] and receipt['elapsed_seconds'] >= 0


@pytest.mark.parametrize('mode,expected', [('json_object', {'type': 'json_object'}), ('prompt', None)])
def test_the_structured_output_setting_decides_the_response_format_field(mode, expected):
    with openai_compatible_server.make_server() as server:
        result, _, receipts, error = call(openai_config(server, structured_output=mode))
        body = server.requests[-1]['body']
    assert error is None and result == {'ok': True} and body.get('response_format') == expected
    assert receipts[0]['structured_output'] == mode and model_routes.OUTPUT_MARKER in body['messages'][0]['content']


def test_the_key_goes_only_into_the_authorization_header_and_settings_shape_the_body():
    with openai_compatible_server.make_server() as server:
        config = openai_config(server, api_key_env='MY_KEY', token_limit_field='max_completion_tokens', max_output_tokens=1000,
                               temperature=0, seed=42, extra_body={'reasoning_effort': 'low'})
        result, identity, receipts, error = call(config, api_key=KEY)
        sent = server.requests[-1]
    assert error is None and sent['headers']['authorization'] == 'Bearer ' + KEY
    assert sent['body']['max_completion_tokens'] == 1000 and 'max_tokens' not in sent['body']
    assert sent['body']['temperature'] == 0 and sent['body']['seed'] == 42 and sent['body']['reasoning_effort'] == 'low'
    assert KEY not in json.dumps(sent['body']) and KEY not in json.dumps([identity, receipts])


def test_a_schema_keyword_that_a_provider_can_reject_is_left_out_of_the_provider_copy_only():
    schema = {'type': 'object', 'additionalProperties': False, 'required': ['ok', 'notes'], 'properties': {
        'ok': {'type': 'boolean'}, 'notes': {'type': 'array', 'maxItems': 0, 'items': {'type': 'string', 'maxLength': 5}}}}
    with openai_compatible_server.make_server() as server:
        infer, _, _ = model_routes.build_route(openai_config(server))
        # The stand-in answers {"ok": true} for the connection test only, so ask it through the reply rule directly.
        sent_schema = route_http.provider_schema(schema)
    assert sent_schema['properties']['notes'] == {'type': 'array', 'items': {'type': 'string'}}
    assert schema['properties']['notes']['maxItems'] == 0                     # the app's own schema is untouched
    with pytest.raises(RouteError) as caught:                               # and the full schema still decides locally
        model_routes.parse_reply('{"ok": true, "notes": ["much too long"]}', schema)
    assert caught.value.category == 'reply_schema_mismatch'
    assert route_http.is_strict(schema) and not route_http.is_strict({'type': 'object', 'properties': {'a': {'type': 'string'}}})
    assert infer is not None


def test_the_provider_copy_of_every_schema_of_the_app_fits_the_documented_subsets():
    from feedctrl import category_induction_producer, evidence_audit, indirect_grounding, semantic_review, staged_induction
    from feedctrl import synthetic_drafts
    schemas = [semantic_review.ACTION_SCHEMA, indirect_grounding.SCHEMA, staged_induction.DEFINITION_SCHEMA,
               staged_induction.MEMBERSHIP_SCHEMA, evidence_audit.SCHEMA, category_induction_producer.SCHEMA,
               synthetic_drafts.SCHEMA]
    for schema in schemas:
        before = json.dumps(schema, sort_keys=True)
        closed = route_http.provider_schema(schema, close_objects=True)
        assert anthropic_server.schema_problem(closed) is None
        assert not set(route_http._RELAXED) & set(json.dumps(route_http.provider_schema(schema)).replace('"', ' ').split())
        assert isinstance(route_http.is_strict(schema), bool) and json.dumps(schema, sort_keys=True) == before


# ---------------------------------------------------------------- OpenAI-compatible: failures

@pytest.mark.parametrize('fail,expected', [
    ('unauthorized', 'authentication'), ('forbidden', 'permission'), ('model_not_found', 'model_not_found'),
    ('bad_request', 'bad_request'), ('rate_limited', 'rate_limited'), ('quota', 'billing'), ('server_error', 'provider_error'),
    ('overloaded', 'provider_overloaded'), ('echo_key', 'permission'), ('no_structured_output', 'structured_output_unsupported'),
    ('redirect', 'redirect_refused'), ('drop', 'not_reachable'), ('garbage_envelope', 'unexpected_reply'),
    ('huge', 'reply_too_large'), ('truncated', 'reply_truncated'), ('refused', 'reply_refused'),
    ('content_filter', 'reply_refused'), ('tool_call', 'unexpected_reply'), ('other_model', 'model_mismatch'),
    ('no_model', 'model_mismatch'), ('fenced', 'reply_not_json'), ('prose', 'reply_not_json'),
    ('duplicate_key', 'reply_not_json'), ('wrong_schema', 'reply_schema_mismatch'), ('not_json', 'reply_not_json'),
    ('empty', 'reply_not_json'),
])
def test_each_failure_of_a_chat_endpoint_gets_its_category_an_action_and_no_key(fail, expected, tmp_path):
    with openai_compatible_server.make_server(fail=fail) as server:
        result, identity, receipts, error = call(openai_config(server, api_key_env='MY_KEY'), api_key=KEY,
                                                 record_dir=tmp_path / 'record')
        assert len(server.requests) == 1                                    # one request, never a second one
    assert result is None and error.category == expected and error.action and str(error).isascii()
    assert receipts[0]['outcome'] == 'error' and receipts[0]['error_category'] == expected
    files = {path.name: path.read_bytes() for path in (tmp_path / 'record').iterdir()}
    assert 'call-0001-request.json' in files and 'call-0001-receipt.json' in files
    everything = str(error) + error.message + error.action + json.dumps([identity, receipts]) + repr(files)
    assert KEY not in everything and 'Bearer ' + KEY[:10] not in everything
    assert receipts[0].get('response_record_scrubbed') is (True if fail == 'echo_key' else None)


def test_failure_messages_say_what_to_change():
    with openai_compatible_server.make_server(fail='unauthorized') as server:
        error = call(openai_config(server, api_key_env='MY_KEY'), api_key=KEY)[3]
    assert 'HTTP 401' in error.message and 'MY_KEY' in error.action and 'Provider message' not in str(error)
    with openai_compatible_server.make_server(fail='no_structured_output') as server:
        error = call(openai_config(server))[3]
        assert '"json_object"' in error.action and '"prompt"' in error.action
        assert call(openai_config(server, structured_output='prompt'))[0] == {'ok': True}   # the named setting works
    with openai_compatible_server.make_server(fail='no_max_completion_tokens') as server:
        error = call(openai_config(server, token_limit_field='max_completion_tokens'))[3]
        assert error.category == 'bad_request' and '"token_limit_field" to "max_tokens"' in error.action
        assert call(openai_config(server))[0] == {'ok': True}
    with openai_compatible_server.make_server(fail='model_not_found') as server:
        error = call(openai_config(server, preset='ollama'))[3]
    assert f'ollama pull {MODEL}' in error.action and '/v1' in error.action
    with openai_compatible_server.make_server(fail='truncated') as server:
        assert 'max_output_tokens' in call(openai_config(server))[3].action
    with openai_compatible_server.make_server(replies='echo-ok') as server:
        error = call(openai_config(server), payload={'system': 'Another request.', 'x': 1},
                     schema={'type': 'object', 'required': ['a'], 'properties': {'a': {'type': 'string'}}})[3]
    assert error.category == 'bad_request' and 'STAND-IN, NOT A MODEL' in error.message


def test_nothing_listening_and_a_slow_server_are_reported_as_such():
    config = {'route': 'openai-compatible', 'base_url': f'http://127.0.0.1:{free_port()}/v1', 'model': MODEL}
    error = call(config)[3]
    assert error.category == 'not_reachable' and 'Nothing listens' in error.message and 'ollama serve' in error.action
    with openai_compatible_server.make_server(fail='slow', delay=3) as server:
        error = call(openai_config(server, timeout_seconds=1))[3]
    assert error.category == 'timeout' and 'timeout_seconds' in error.action


def test_the_reported_model_must_match_unless_the_file_allows_a_difference():
    with openai_compatible_server.make_server(fail='snapshot_model') as server:
        result, _, receipts, error = call(openai_config(server))
    assert error is None and result == {'ok': True} and receipts[0]['reported_model'] == MODEL + '-2026-01-01'
    with openai_compatible_server.make_server(fail='other_model') as server:
        refused = call(openai_config(server))
        allowed = call(openai_config(server, allow_reported_model_mismatch=True))
    assert refused[3].category == 'model_mismatch' and 'another-model' in refused[3].message
    assert 'allow_reported_model_mismatch' in refused[3].action
    assert allowed[3] is None and allowed[2][0]['requested_model'] == MODEL and allowed[2][0]['reported_model'] == 'another-model'


def test_the_call_allowance_stops_further_calls_before_anything_is_sent():
    with openai_compatible_server.make_server() as server:
        infer, _, receipts = model_routes.build_route(openai_config(server, max_calls=2))
        assert infer(dict(PAYLOAD), dict(SCHEMA)) == infer(dict(PAYLOAD), dict(SCHEMA)) == {'ok': True}
        with pytest.raises(RouteError) as caught:
            infer(dict(PAYLOAD), dict(SCHEMA))
        assert len(server.requests) == 2
    assert caught.value.category == 'allowance_exhausted' and 'max_calls' in caught.value.action and len(receipts) == 2


def test_an_oversized_request_is_refused_whole_and_a_bad_input_is_a_programming_error():
    with openai_compatible_server.make_server() as server:
        infer, _, receipts = model_routes.build_route(openai_config(server, max_request_bytes=1000))
        with pytest.raises(RouteError) as caught:
            infer({'system': 'x', 'catalogue': ['y' * 2000]}, dict(SCHEMA))
        assert caught.value.category == 'bad_request' and 'Nothing was sent' in caught.value.message
        for payload, schema in (({'catalogue': []}, SCHEMA), (PAYLOAD, {'type': 'array'}), (PAYLOAD, {'type': 'object', 'required': 5})):
            with pytest.raises(Exception) as bad:
                infer(payload, schema)
            assert not isinstance(bad.value, RouteError)
        assert server.requests == [] and len(receipts) == 1


def test_the_record_folder_holds_the_exact_request_and_reply_and_is_never_reused(tmp_path):
    record = tmp_path / 'record'
    with openai_compatible_server.make_server() as server:
        result, _, receipts, error = call(openai_config(server, api_key_env='MY_KEY'), api_key=KEY, record_dir=record)
        sent = server.requests[-1]['body']
    assert error is None and sorted(path.name for path in record.iterdir()) == [
        'call-0001-receipt.json', 'call-0001-request.json', 'call-0001-response.txt']
    assert json.loads((record / 'call-0001-request.json').read_text(encoding='utf-8')) == sent
    reply = json.loads((record / 'call-0001-response.txt').read_text(encoding='utf-8'))
    assert json.loads(reply['choices'][0]['message']['content']) == result
    assert json.loads((record / 'call-0001-receipt.json').read_text())['request_body_sha256'] == receipts[0]['request_body_sha256']
    assert all(KEY.encode() not in path.read_bytes() for path in record.iterdir())
    with pytest.raises(RouteError) as caught:
        model_routes.build_route({'route': 'openai-compatible', 'base_url': 'http://127.0.0.1:9/v1', 'model': MODEL},
                                 record_dir=record)
    assert caught.value.category == 'configuration' and 'not empty' in caught.value.message


# ---------------------------------------------------------------- Anthropic Messages

def test_the_messages_request_has_the_documented_shape():
    with anthropic_server.make_server() as server:
        result, identity, receipts, error = call(anthropic_config(server), api_key=KEY)
        sent = server.requests[-1]
    assert error is None and result == {'ok': True}
    assert sent['method'] == 'POST' and sent['path'] == '/v1/messages'
    assert sent['headers']['anthropic-version'] == '2026-10-21' and sent['headers']['authorization'] == 'Bearer ' + KEY
    assert 'x-api-key' not in sent['headers'] and 'anthropic-workspace-id' not in sent['headers']
    body = sent['body']
    assert set(body) == {'model', 'max_tokens', 'system', 'messages', 'output_config'}
    assert body['max_tokens'] == 16384 and body['system'].startswith(PAYLOAD['system'])
    assert body['messages'] == [{'role': 'user', 'content': '{"test":"connection"}'}]
    assert body['output_config'] == {'format': {'type': 'json_schema', 'schema': SCHEMA}}
    assert identity['backend'] == 'anthropic-messages' and KEY not in json.dumps([identity, receipts, body])
    assert receipts[0]['provider_request_id'] == 'req_standin_1' and receipts[0]['stop_reason'] == 'end_turn'
    assert set(receipts[0]['usage']) == {'input_tokens', 'output_tokens'} and receipts[0]['usage']['input_tokens'] > 0


def test_the_messages_settings_select_the_headers_the_mode_and_the_effort():
    with anthropic_server.make_server() as server:
        config = anthropic_config(server, auth_header='x-api-key', anthropic_workspace_id='wrkspc_01ABC', effort='high',
                                  structured_output='prompt', anthropic_version='2023-06-01', max_output_tokens=900)
        result, _, _, error = call(config, api_key=KEY)
        sent = server.requests[-1]
    assert error is None and result == {'ok': True}
    assert sent['headers']['x-api-key'] == KEY and 'authorization' not in sent['headers']
    assert sent['headers']['anthropic-workspace-id'] == 'wrkspc_01ABC' and sent['headers']['anthropic-version'] == '2023-06-01'
    assert sent['body']['output_config'] == {'effort': 'high'} and sent['body']['max_tokens'] == 900
    assert not {'temperature', 'top_p', 'top_k'} & set(sent['body'])


def test_the_structured_output_copy_passes_the_documented_schema_limits():
    # An open object and a count keyword: both are outside the documented subset, and the stand-in refuses them.
    schema = {'type': 'object', 'required': ['ok'], 'minProperties': 1, 'properties': {'ok': {'type': 'boolean'}}}
    assert anthropic_server.schema_problem(schema) is not None
    with anthropic_server.make_server() as server:
        result, _, _, error = call(anthropic_config(server), api_key=KEY, schema=schema)
        sent = server.requests[-1]['body']['output_config']['format']['schema']
    assert error is None and result == {'ok': True}
    assert sent == {'type': 'object', 'required': ['ok'], 'properties': {'ok': {'type': 'boolean'}},
                    'additionalProperties': False}
    assert 'additionalProperties' not in schema                         # the app's own schema is untouched


@pytest.mark.parametrize('fail,expected', [
    ('unauthorized', 'authentication'), ('billing', 'billing'), ('forbidden', 'permission'),
    ('model_not_found', 'model_not_found'), ('too_large', 'bad_request'), ('rate_limited', 'rate_limited'),
    ('server_error', 'provider_error'), ('timeout', 'timeout'), ('overloaded', 'provider_overloaded'),
    ('bad_request', 'bad_request'), ('no_structured_output', 'structured_output_unsupported'),
    ('redirect', 'redirect_refused'), ('truncated', 'reply_truncated'), ('refused', 'reply_refused'),
    ('context_full', 'reply_truncated'), ('tool_use', 'unexpected_reply'), ('two_blocks', 'reply_not_json'),
    ('other_model', 'model_mismatch'), ('fenced', 'reply_not_json'), ('prose', 'reply_not_json'),
    ('duplicate_key', 'reply_not_json'), ('wrong_schema', 'reply_schema_mismatch'), ('not_json', 'reply_not_json'),
    ('empty', 'reply_not_json'),
])
def test_each_failure_of_the_messages_api_gets_its_category_an_action_and_no_key(fail, expected, tmp_path):
    with anthropic_server.make_server(fail=fail) as server:
        result, identity, receipts, error = call(anthropic_config(server), api_key=KEY, record_dir=tmp_path / 'record')
        assert len(server.requests) == 1
    assert result is None and error.category == expected and error.action and str(error).isascii()
    files = repr({path.name: path.read_bytes() for path in (tmp_path / 'record').iterdir()})
    assert KEY not in str(error) + json.dumps([identity, receipts]) + files
    assert receipts[0]['error_category'] == expected


def test_messages_replies_with_a_thinking_block_or_a_dated_model_name_are_accepted():
    for fail in ('thinking_block', 'snapshot_model'):
        with anthropic_server.make_server(fail=fail) as server:
            result, _, receipts, error = call(anthropic_config(server), api_key=KEY)
        assert error is None and result == {'ok': True}
    assert receipts[0]['reported_model'] == MODEL + '-20260101'


def test_messages_failures_say_what_to_change():
    with anthropic_server.make_server(fail='unauthorized') as server:
        error = call(anthropic_config(server, api_key_env='MY_ANTHROPIC'), api_key=KEY)[3]
    assert 'MY_ANTHROPIC' in error.action and 'Provider message' not in str(error)
    with anthropic_server.make_server(fail='no_structured_output') as server:
        error = call(anthropic_config(server), api_key=KEY)[3]
        assert '"structured_output" to "prompt"' in error.action
        assert call(anthropic_config(server, structured_output='prompt'), api_key=KEY)[0] == {'ok': True}
    with anthropic_server.make_server(fail='context_full') as server:
        assert 'smaller evidence scope' in call(anthropic_config(server), api_key=KEY)[3].action


def test_the_anthropic_check_lists_models_with_the_key_and_reports_a_rejected_key():
    lines = []
    with anthropic_server.make_server(replies='echo-ok') as server:
        good = model_routes.check_route(anthropic_config(server), api_key=KEY, out=lines.append)
        assert server.requests[0]['path'] == '/v1/models?limit=1000' and server.requests[0]['method'] == 'GET'
        assert server.requests[0]['headers']['anthropic-version'] == '2026-10-21'
    with anthropic_server.make_server(fail='unauthorized') as server:
        bad = model_routes.check_route(anthropic_config(server), api_key=KEY, out=lines.append)
    assert good['ok'] and [step['name'] for step in good['steps']] == ['configuration', 'credential', 'endpoint', 'test call']
    assert not bad['ok'] and bad['steps'][-1]['name'] == 'endpoint' and 'ANTHROPIC_API_KEY' in bad['steps'][-1]['action']
    assert KEY not in '\n'.join(lines) + json.dumps([good, bad]) and all(line.isascii() for line in lines)


def test_an_endpoint_without_a_model_list_still_reaches_the_test_call():
    lines = []
    with openai_compatible_server.make_server(replies='echo-ok', fail='no_models_endpoint') as server:
        result = model_routes.check_route(openai_config(server), out=lines.append)
    assert result['ok'] and 'no model list' in result['steps'][1]['detail']


@pytest.mark.skipif(shutil.which('openssl') is None, reason='openssl is needed to make a test certificate')
def test_a_certificate_that_this_computer_does_not_trust_is_a_tls_failure(tmp_path):
    key, certificate = tmp_path / 'key.pem', tmp_path / 'cert.pem'
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-keyout', str(key), '-out', str(certificate),
                    '-days', '1', '-subj', '/CN=127.0.0.1', '-addext', 'subjectAltName=IP:127.0.0.1'],
                   check=True, capture_output=True)
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), http.server.BaseHTTPRequestHandler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(str(certificate), str(key))
    server.socket = context.wrap_socket(server.socket, server_side=True)
    server.handle_error = lambda *args: None
    threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.05}, daemon=True).start()
    try:
        config = {'route': 'openai-compatible', 'base_url': f'https://127.0.0.1:{server.server_port}/v1', 'model': MODEL,
                  'api_key_env': 'MY_KEY'}
        error = call(config, api_key=KEY)[3]
    finally:
        server.shutdown()
        server.server_close()
    assert error.category == 'tls' and 'certificate' in error.action.lower() and KEY not in str(error)


def test_the_model_names_of_an_endpoint_can_be_listed_for_the_setup_questions():
    with openai_compatible_server.make_server() as server:
        config = model_routes.validate_config(openai_config(server))
        assert route_http.model_names(config) == [MODEL]
    with anthropic_server.make_server() as server:
        config = model_routes.validate_config(anthropic_config(server))
        assert route_http.model_names(config, KEY) == [MODEL]


# ---------------------------------------------------------------- review finding F05

def run_in_thread(infer):
    box = {}

    def run():
        try:
            box['result'] = infer(dict(PAYLOAD), dict(SCHEMA))
        except RouteError as error:
            box['error'] = error

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    return worker, box


@pytest.mark.parametrize('make, config', [(openai_compatible_server.make_server, openai_config),
                                          (anthropic_server.make_server, anthropic_config)])
def test_f05_a_stop_request_ends_a_running_call_and_refuses_the_next(make, config):
    import time
    with make(replies='echo-ok', fail='slow', delay=30) as server:
        infer, _, receipts = model_routes.build_route(config(server), api_key=KEY)
        worker, box = run_in_thread(infer)
        for _ in range(100):
            if server.requests:
                break
            time.sleep(0.05)
        started = time.monotonic()
        model_routes.request_stop()
        worker.join(10)
        assert not worker.is_alive() and time.monotonic() - started < 3
        assert box['error'].category == 'stopped' and receipts[0]['error_category'] == 'stopped'
        with pytest.raises(RouteError) as caught:
            infer(dict(PAYLOAD), dict(SCHEMA))
        assert caught.value.category == 'stopped' and len(server.requests) == 1 and len(receipts) == 1


def test_n1_a_reply_with_several_choices_is_refused():
    import json as json_module

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers.get('Content-Length') or 0))
            body = json_module.dumps({'id': 'x', 'object': 'chat.completion', 'model': MODEL, 'choices': [
                {'index': 1, 'message': {'role': 'assistant', 'content': '{"ok": false}'}, 'finish_reason': 'stop'},
                {'index': 0, 'message': {'role': 'assistant', 'content': '{"ok": true}'}, 'finish_reason': 'stop'}]}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        _, _, _, error = call({'route': 'openai-compatible', 'base_url': f'http://127.0.0.1:{server.server_port}/v1',
                               'model': MODEL})
    finally:
        server.shutdown()
        server.server_close()
    assert error.category == 'unexpected_reply' and '2 choices' in error.message


# ---------------------------------------------------------------- minor findings: a raw server that answers one fixed way

PLAIN_KEY = 'plainkeytestvalue-0123'     # no known key shape


class RawServer:
    """A loopback server whose answer is a function of the request head. Not a model."""

    def __init__(self, answer):
        self.answer, self.count = answer, 0
        self.sock = socket.socket()
        self.sock.bind(('127.0.0.1', 0))
        self.sock.listen(8)
        self.url = f'http://127.0.0.1:{self.sock.getsockname()[1]}'
        self.thread = threading.Thread(target=self._loop, daemon=True)

    def _loop(self):
        while True:
            try:
                connection, _ = self.sock.accept()
            except OSError:
                return
            threading.Thread(target=self._one, args=(connection,), daemon=True).start()

    def _one(self, connection):
        with connection:
            data = b''
            while b'\r\n\r\n' not in data:
                block = connection.recv(65536)
                if not block:
                    return
                data += block
            head, _, rest = data.partition(b'\r\n\r\n')
            length = 0
            for line in head.split(b'\r\n'):
                if line.lower().startswith(b'content-length:'):
                    length = int(line.split(b':', 1)[1])
            while len(rest) < length:
                rest += connection.recv(65536)
            self.count += 1
            try:
                self.answer(connection, head.decode('latin-1'))
            except OSError:
                pass

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.sock.close()


def header(head, name):
    for line in head.split('\r\n'):
        if line.lower().startswith(name.lower() + ':'):
            return line.split(':', 1)[1].strip()
    return ''


def respond(connection, status, body, headers=None):
    data = body if isinstance(body, bytes) else json.dumps(body).encode()
    lines = [f'HTTP/1.1 {status} X', 'Content-Type: application/json', f'Content-Length: {len(data)}', 'Connection: close',
             *[f'{name}: {value}' for name, value in (headers or {}).items()]]
    connection.sendall(('\r\n'.join(lines) + '\r\n\r\n').encode('latin-1') + data)


def chat(content='{"ok": true}', model=MODEL):
    return {'id': 'x', 'object': 'chat.completion', 'model': model,
            'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': content}, 'finish_reason': 'stop'}]}


def raw_call(answer, key, tmp_path, **settings):
    lines = []
    with RawServer(answer) as server:
        config = {'route': 'openai-compatible', 'base_url': server.url + '/v1', 'model': MODEL, **settings}
        if key:
            config['api_key_env'] = 'MY_KEY'
        infer, _, receipts = model_routes.build_route(config, api_key=key, record_dir=tmp_path / 'record', log=lines.append)
        try:
            result, error = infer(dict(PAYLOAD), dict(SCHEMA)), None
        except RouteError as caught:
            result, error = None, caught
    files = {path.name: path.read_bytes() for path in (tmp_path / 'record').iterdir()}
    return result, error, receipts, files, lines


@pytest.mark.parametrize('where', ['model', 'request_id', 'reply_start', 'reply_value', 'error_type'])
def test_f06_a_key_that_the_endpoint_repeats_is_removed_at_every_sink(where, tmp_path):
    def answer(connection, head):
        bearer = header(head, 'Authorization')
        if where == 'model':
            respond(connection, 200, chat(model=bearer.split(' ', 1)[1]))
        elif where == 'request_id':
            respond(connection, 200, chat(), {'x-request-id': bearer})
        elif where == 'reply_start':
            respond(connection, 200, chat('Invalid header ' + bearer))
        elif where == 'reply_value':
            respond(connection, 200, chat(json.dumps({'ok': bearer})))
        else:
            respond(connection, 400, {'error': {'message': 'bad', 'type': bearer, 'code': bearer}})
    result, error, receipts, files, lines = raw_call(answer, PLAIN_KEY, tmp_path)
    text = json.dumps([str(error), error and error.action, receipts, lines])
    assert PLAIN_KEY not in text
    assert all(PLAIN_KEY.encode() not in data for data in files.values())
    if where == 'request_id':
        assert result == {'ok': True} and receipts[0]['provider_request_id'] == 'Bearer [credential removed]'


def test_f06_a_json_escaped_or_a_short_key_is_removed_from_the_record_and_the_message(tmp_path):
    slash_key = 'AbCd/EfGh+IjKl/MnOp'

    def escaped(connection, head):
        text = json.dumps({'error': {'message': 'The key ' + header(head, 'Authorization') + ' may not use this model.'}})
        respond(connection, 403, text.replace('/', '\\/').encode())
    _, error, _, files, _ = raw_call(escaped, slash_key, tmp_path / 'a')
    assert slash_key not in str(error) and slash_key.replace('/', '\\/').encode() not in files['call-0001-response.txt']
    assert b'[credential removed]' in files['call-0001-response.txt']
    model_routes.forget_secrets()

    def short(connection, head):
        respond(connection, 403, {'error': {'message': 'The key ' + header(head, 'Authorization') + ' may not use this model.'}})
    _, error, _, _, lines = raw_call(short, 'abc', tmp_path / 'b')
    assert ' abc ' not in str(error) and ' abc ' not in lines[-1] and '[credential removed]' in str(error)


def test_f07_the_time_limit_holds_for_the_whole_call(tmp_path):
    import time
    body = json.dumps(chat()).encode()

    def drip(connection, head):
        connection.sendall(b'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: %d\r\n'
                           b'Connection: close\r\n\r\n' % len(body))
        for index in range(len(body)):
            connection.sendall(body[index:index + 1])
            time.sleep(0.3)
    started = time.monotonic()
    _, error, receipts, _, _ = raw_call(drip, None, tmp_path, timeout_seconds=2)
    assert error.category == 'timeout' and time.monotonic() - started < 5 and receipts[0]['error_category'] == 'timeout'


@pytest.mark.parametrize('status, body, expected, words', [
    (400, {'error': {'message': 'max_tokens is too large: 16384. This model supports at most 4096 completion tokens.',
                     'type': 'invalid_request_error'}}, 'bad_request', 'Lower "max_output_tokens"'),
    (400, {'error': {'message': "Unsupported parameter: 'max_tokens'.", 'type': 'invalid_request_error'}},
     'bad_request', '"token_limit_field" to "max_completion_tokens"'),
    (429, {'error': {'message': 'Organization usage limit reached.', 'type': 'usage_limit_reached'}}, 'billing', 'credit'),
    (429, {'error': {'message': 'Rate limit reached for requests.', 'type': 'rate_limit_error'}}, 'rate_limited', 'Wait'),
    (200, {'error': {'message': 'model is still loading'}}, 'provider_error', 'loading'),
    (304, b'', 'unexpected_reply', 'route kind'),
    (400, {'error': {'message': 'temperature is not supported'}}, 'bad_request', 'Remove "temperature"'),
])
def test_f17_a_failure_message_names_the_status_that_came_and_the_right_action(status, body, expected, words, tmp_path):
    _, error, receipts, _, _ = raw_call(lambda connection, head: respond(connection, status, body), None, tmp_path)
    assert error.category == expected and words in str(error)
    if status != 200:
        assert f'HTTP {status}' in error.message and receipts[0]['http_status'] == status


@pytest.mark.parametrize('status, kind, message, expected, shown', [
    (403, 'authentication_error', 'invalid bearer token', 'authentication', 'HTTP 403'),
    (400, 'invalid_request_error', 'messages.0.content: text content blocks must be non-empty; check the request format',
     'bad_request', 'HTTP 400'),
    (400, 'invalid_request_error', 'output_config.format: structured outputs are not available',
     'structured_output_unsupported', 'HTTP 400'),
    (429, 'rate_limit_error', 'slow down', 'rate_limited', 'HTTP 429'),
])
def test_f17_anthropic_messages_name_the_status_that_came(status, kind, message, expected, shown, tmp_path):
    def answer(connection, head):
        respond(connection, status, {'type': 'error', 'error': {'type': kind, 'message': message}})
    with RawServer(answer) as server:
        infer, _, _ = model_routes.build_route(anthropic_config(server), api_key=KEY)
        with pytest.raises(RouteError) as caught:
            infer(dict(PAYLOAD), dict(SCHEMA))
    assert caught.value.category == expected and shown in caught.value.message


def test_f18_extra_body_cannot_replace_temperature_or_seed():
    with pytest.raises(RouteError) as caught:
        model_routes.validate_config({'route': 'openai-compatible', 'preset': 'ollama', 'model': 'm',
                                      'extra_body': {'temperature': 1.9, 'seed': 7}})
    assert 'seed, temperature' in caught.value.message
    with pytest.raises(RouteError):
        model_routes.validate_config({'route': 'anthropic', 'model': 'm', 'extra_body': {'temperature': 1}})


def test_n3_a_refused_redirect_leaves_its_status_and_names_its_target():
    with openai_compatible_server.make_server(fail='redirect') as server:
        _, _, receipts, error = call(openai_config(server))
    assert error.category == 'redirect_refused' and 'http://127.0.0.1:9/elsewhere' in error.message
    assert receipts[0]['http_status'] == 302


def test_mutation_a_server_on_this_computer_is_never_reached_through_a_proxy(monkeypatch):
    for name in ('http_proxy', 'HTTP_PROXY', 'all_proxy', 'ALL_PROXY'):
        monkeypatch.setenv(name, 'http://127.0.0.1:9')
    for name in ('no_proxy', 'NO_PROXY'):
        monkeypatch.setenv(name, '')
    with openai_compatible_server.make_server(replies='echo-ok') as server:
        result, _, _, error = call(openai_config(server))
    assert error is None and result == {'ok': True}


def test_n7_the_provider_copy_keeps_names_maps_and_nullable_objects_apart():
    schema = {'type': 'object', 'additionalProperties': False, 'required': ['a', 'm'],
              '$defs': {'format': {'type': 'string', 'maxLength': 3}},
              'properties': {'a': {'$ref': '#/$defs/format'},
                             'm': {'type': 'object', 'additionalProperties': {'type': 'number'}},
                             'n': {'type': ['object', 'null'], 'properties': {}}}}
    copy = route_http.provider_schema(schema, close_objects=True)
    assert copy['$defs'] == {'format': {'type': 'string'}}                  # a name, not the keyword "format"
    assert copy['properties']['m']['additionalProperties'] == {'type': 'number'}   # a map stays open
    assert copy['properties']['n']['additionalProperties'] is False          # a nullable object is closed
    assert route_http.is_strict(schema) is False
    assert route_http.is_strict({'type': ['object', 'null'], 'properties': {'x': {'type': 'string'}},
                                 'required': ['x']}) is False


def test_n2_the_receipts_are_in_the_order_of_their_ordinals_under_threads():
    with openai_compatible_server.make_server(replies='echo-ok') as server:
        infer, _, receipts = model_routes.build_route(openai_config(server, max_calls=12))
        workers = [threading.Thread(target=lambda: infer(dict(PAYLOAD), dict(SCHEMA)), daemon=True) for _ in range(12)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(20)
    assert [receipt['ordinal'] for receipt in receipts] == list(range(1, 13))
