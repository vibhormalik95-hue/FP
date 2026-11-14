"""The route layer, offline: configuration, the reply rule, key handling, the check and the wizard.

No model, no provider and no network beyond 127.0.0.1 are used. The servers in
these tests are stand-ins that answer with fixed or hand-written replies.
"""
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))

from feedctrl import model_routes  # noqa: E402
from feedctrl.controls import ParserOperationalError  # noqa: E402
from feedctrl.model_routes import RouteError  # noqa: E402
import model_route  # noqa: E402
from standins import common, openai_compatible_server  # noqa: E402
from standins.route_state import fresh_route_state  # noqa: E402,F401  (autouse)

KEY = 'sk-test-0123456789abcdefSECRET'
SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['status', 'label'],
          'properties': {'status': {'type': 'string', 'enum': ['propose', 'clarify']},
                         'label': {'type': 'string', 'maxLength': 20}}}
GOOD = '{"status": "propose", "label": "Repair"}'
OLLAMA = {'route': 'openai-compatible', 'preset': 'ollama', 'model': 'llama3.1:8b'}


def category(function, *args, **kwargs):
    with pytest.raises(RouteError) as caught:
        function(*args, **kwargs)
    return caught.value.category


# ---------------------------------------------------------------- configuration

def test_every_built_in_route_validates_and_fills_its_defaults():
    ollama = model_routes.validate_config(OLLAMA)
    assert ollama['base_url'] == 'http://127.0.0.1:11434/v1' and ollama['token_limit_field'] == 'max_tokens'
    assert ollama['temperature'] == 0 and ollama['seed'] == 42 and ollama['max_calls'] == 40
    assert 'api_key_env' not in ollama and model_routes.needs_api_key(ollama) is None
    openai = model_routes.validate_config({'route': 'openai-compatible', 'preset': 'openai', 'model': 'some-model'})
    assert openai['api_key_env'] == 'OPENAI_API_KEY' and openai['token_limit_field'] == 'max_completion_tokens'
    assert 'temperature' not in openai
    anthropic = model_routes.validate_config({'route': 'anthropic', 'model': 'some-model'})
    assert anthropic['anthropic_version'] == '2026-10-21' and anthropic['api_key_env'] == 'ANTHROPIC_API_KEY'
    cli = model_routes.validate_config({'route': 'cli', 'profile': 'claude-code', 'model': 'claude-some-model'})
    assert cli['command'] == 'claude' and cli['structured_output'] == 'prompt' and cli['timeout_seconds'] == 600
    assert (ollama['max_output_tokens'], openai['max_output_tokens'], anthropic['max_output_tokens']) == (4096, 16384, 16384)
    assert ollama['timeout_seconds'] == anthropic['timeout_seconds'] == 600
    relay = model_routes.validate_config({'route': 'relay', 'declared_model': 'x', 'transport_note': 'by hand'})
    assert relay['max_calls'] == 10
    for name in ('llama3.1:8b', 'qwen/qwen3-4b', 'hf.co/user/repo:Q4_K_M', 'claude-some-model[1m]', 'provider/model@2026-01-01'):
        assert model_routes.validate_config({**OLLAMA, 'model': name})['model'] == name
    # Validation is stable: a normalised configuration validates to itself.
    for config in (ollama, openai, anthropic, cli, relay):
        assert model_routes.validate_config(config) == config
    assert set(model_routes.ROUTE_KINDS) == {'openai-compatible', 'anthropic', 'cli', 'relay'}


@pytest.mark.parametrize('raw', [
    [], {}, {'route': 'telepathy'}, {**OLLAMA, 'modle': 'x'}, {**OLLAMA, 'model': ''}, {**OLLAMA, 'model': 'a b'},
    {**OLLAMA, 'max_calls': 0}, {**OLLAMA, 'max_calls': 501}, {**OLLAMA, 'max_calls': True}, {**OLLAMA, 'timeout_seconds': 0},
    {**OLLAMA, 'structured_output': 'xml'}, {**OLLAMA, 'temperature': 3}, {**OLLAMA, 'allow_insecure_http': 'yes'},
    {**OLLAMA, 'base_url': 'ftp://127.0.0.1/v1'}, {**OLLAMA, 'base_url': 'http://user:pw@127.0.0.1:11434/v1'},
    {**OLLAMA, 'base_url': 'http://127.0.0.1:11434/v1?x=1'}, {**OLLAMA, 'extra_body': {'model': 'other'}},
    {**OLLAMA, 'extra_body': []}, {'route': 'openai-compatible', 'model': 'm'},
    {'route': 'anthropic', 'model': 'm', 'anthropic_version': '2020-01-01'},
    {'route': 'anthropic', 'model': 'm', 'temperature': 0},
    {'route': 'cli', 'model': 'm'}, {'route': 'cli', 'profile': 'generic', 'model': 'm'},
    {'route': 'cli', 'profile': 'generic', 'model': 'm', 'argv': []},
    {'route': 'cli', 'profile': 'generic', 'model': 'm', 'argv': ['x'], 'effort': 'high'},
    {'route': 'cli', 'profile': 'claude-code', 'model': 'm', 'omit_flags': ['-p']},
    {'route': 'cli', 'profile': 'claude-code', 'model': 'm', 'effort': 'extreme'},
    {'route': 'cli', 'profile': 'claude-code', 'model': 'm', 'pass_environment': ['NOT A NAME']},
    {'route': 'relay', 'declared_model': 'x'}, {'route': 'relay', 'declared_model': 'x', 'transport_note': 'y', 'max_calls': 11},
])
def test_a_wrong_route_file_is_refused_with_a_configuration_error(raw):
    assert category(model_routes.validate_config, raw) == 'configuration'


def test_http_to_another_computer_needs_an_explicit_setting():
    remote = {'route': 'openai-compatible', 'base_url': 'http://192.0.2.10:11434/v1', 'model': 'm'}
    with pytest.raises(RouteError, match='allow_insecure_http'):
        model_routes.validate_config(remote)
    assert model_routes.validate_config({**remote, 'allow_insecure_http': True})['allow_insecure_http'] is True
    assert model_routes.validate_config({**remote, 'base_url': 'https://192.0.2.10/v1'})['base_url'] == 'https://192.0.2.10/v1'
    for local in ('http://localhost:1234/v1/', 'http://127.0.0.1:1234/v1', 'http://[::1]:1234/v1'):
        assert model_routes.validate_config({**remote, 'base_url': local})['base_url'].endswith('/v1')


@pytest.mark.parametrize('raw', [
    {**OLLAMA, 'api_key': KEY}, {**OLLAMA, 'token': 'abc'}, {**OLLAMA, 'Authorization': 'x'},
    {**OLLAMA, 'api_key_env': KEY}, {**OLLAMA, 'api_key_env': 'a1b2c3d4e5f6a7b8c9d0e1f2a3b4'},
    {**OLLAMA, 'extra_body': {'api_key': 'x'}}, {**OLLAMA, 'extra_body': {'metadata': {'password': 'x'}}},
    {**OLLAMA, 'extra_body': {'note': 'Bearer abcdefgh12345678'}}, {**OLLAMA, 'extra_body': {'note': KEY}},
    {'route': 'relay', 'declared_model': 'x', 'transport_note': KEY},
])
def test_a_credential_in_the_route_file_is_refused(raw, tmp_path):
    with pytest.raises(RouteError) as caught:
        model_routes.validate_config(raw)
    assert caught.value.category == 'configuration' and KEY not in str(caught.value)
    with pytest.raises(RouteError):
        model_routes.save_config(tmp_path / 'route.json', raw)
    assert not (tmp_path / 'route.json').exists()


def test_settings_that_only_look_like_secret_names_are_accepted():
    config = model_routes.validate_config({**OLLAMA, 'max_output_tokens': 2000, 'token_limit_field': 'max_tokens',
                                           'extra_body': {'thinking': {'budget_tokens': 100}, 'reasoning_effort': 'low'}})
    assert config['extra_body']['thinking'] == {'budget_tokens': 100}


def test_save_and_load_keep_the_normalised_file_and_refuse_a_broken_one(tmp_path):
    path = tmp_path / 'model-route.json'
    model_routes.save_config(path, OLLAMA)
    saved = json.loads(path.read_text(encoding='utf-8'))
    assert saved == model_routes.validate_config(OLLAMA) and path.read_bytes().isascii()
    assert model_routes.load_config(path) == saved
    assert category(model_routes.load_config, tmp_path / 'missing.json') == 'configuration'
    path.write_text('{"route": "relay", "route": "cli"}', encoding='utf-8')   # a repeated key
    assert category(model_routes.load_config, path) == 'configuration'
    path.write_bytes(b'\xef\xbb\xbf' + json.dumps(OLLAMA).encode())            # a byte-order mark from Notepad
    assert model_routes.load_config(path)['model'] == 'llama3.1:8b'


def test_describe_is_ascii_and_never_holds_a_key():
    for raw in (OLLAMA, {'route': 'anthropic', 'model': 'm'}, {'route': 'cli', 'profile': 'claude-code', 'model': 'm'},
                {'route': 'cli', 'profile': 'generic', 'model': 'm', 'argv': ['prog', 'run']},
                {'route': 'relay', 'declared_model': 'modèle', 'transport_note': 'by hand'}):
        lines = model_routes.describe(raw)
        assert lines[0].startswith('Route: ') and all(line.isascii() for line in lines)
        assert any('not a billing limit' in line for line in lines)


# ---------------------------------------------------------------- the key

def test_the_key_comes_from_the_named_variable_or_from_a_hidden_prompt():
    config = {'route': 'anthropic', 'model': 'm', 'api_key_env': 'MY_KEY'}
    assert model_routes.needs_api_key(config) == 'MY_KEY'
    assert model_routes.resolve_api_key(config, environ={'MY_KEY': '  ' + KEY + '\n'}) == KEY
    asked = []
    assert model_routes.resolve_api_key(config, environ={}, ask=lambda prompt: asked.append(prompt) or KEY) == KEY
    assert 'MY_KEY' in asked[0] and 'hidden' in asked[0] and KEY not in asked[0]
    with pytest.raises(RouteError) as caught:
        model_routes.resolve_api_key(config, environ={})
    assert caught.value.category == 'authentication' and 'MY_KEY' in str(caught.value)
    assert category(model_routes.resolve_api_key, config, environ={'MY_KEY': 'two words'}) == 'authentication'
    assert model_routes.resolve_api_key(OLLAMA, environ={}) is None


def test_build_refuses_a_missing_key_and_a_key_inside_the_file():
    assert category(model_routes.build_route, {'route': 'anthropic', 'model': 'm'}) == 'authentication'
    with_key = {'route': 'openai-compatible', 'base_url': 'http://127.0.0.1:9/v1', 'model': 'm', 'api_key_env': 'MY_KEY',
                'extra_body': {'comment': 'x' + 'plainvalue1234abcd'}}
    assert category(model_routes.build_route, with_key, api_key='plainvalue1234abcd') == 'configuration'
    assert category(model_routes.build_route, with_key, api_key='has space') == 'authentication'


def test_a_placeholder_key_that_is_a_word_of_the_file_is_accepted():
    # F09: a local server accepts any key; its documentation uses words such as "lm-studio".
    for key, config in (('lm-studio', {'route': 'openai-compatible', 'preset': 'lm-studio', 'model': 'qwen/qwen3-4b',
                                       'api_key_env': 'LM_KEY'}),
                        ('ollama', {'route': 'openai-compatible', 'preset': 'ollama', 'model': 'llama3.1:8b',
                                    'api_key_env': 'OLLAMA_API_KEY'}),
                        ('1234', {'route': 'openai-compatible', 'preset': 'lm-studio', 'model': 'm', 'api_key_env': 'K'})):
        infer, identity, receipts = model_routes.build_route(config, api_key=key)
        assert callable(infer) and receipts == []


def test_the_scrubber_removes_the_key_and_key_shaped_text():
    clean = model_routes.scrubber(KEY)
    text = clean(f'The key {KEY} failed. Authorization: Bearer abcdefgh12345678. Also sk-proj-****abcd1234.')
    assert KEY not in text and 'abcdefgh12345678' not in text and 'abcd1234' not in text
    assert text.count('[credential removed]') == 3


# ---------------------------------------------------------------- the reply rule

def test_exactly_one_json_object_that_matches_the_schema_is_accepted():
    assert model_routes.parse_reply(GOOD, SCHEMA) == {'status': 'propose', 'label': 'Repair'}
    assert model_routes.parse_reply('\n  ' + GOOD + ' \n', SCHEMA)['label'] == 'Repair'


@pytest.mark.parametrize('text,expected', [
    ('```json\n' + GOOD + '\n```', 'reply_not_json'), ('Here it is: ' + GOOD, 'reply_not_json'),
    (GOOD + ' Done.', 'reply_not_json'), (GOOD + GOOD, 'reply_not_json'), ('', 'reply_not_json'), ('   ', 'reply_not_json'),
    ('[1, 2]', 'reply_not_json'), ('"text"', 'reply_not_json'), ('{"status": "propose", "status": "clarify", "label": "x"}', 'reply_not_json'),
    ('{"status": "propose", "label": NaN}', 'reply_not_json'), ('{"status": "maybe", "label": "x"}', 'reply_schema_mismatch'),
    ('{"status": "propose"}', 'reply_schema_mismatch'), ('{"status": "propose", "label": "x", "extra": 1}', 'reply_schema_mismatch'),
    ('{"status": "propose", "label": "' + 'x' * 21 + '"}', 'reply_schema_mismatch'), (None, 'reply_not_json'),
])
def test_any_other_reply_is_refused_and_never_repaired(text, expected):
    with pytest.raises(RouteError) as caught:
        model_routes.parse_reply(text, SCHEMA)
    assert caught.value.category == expected and str(caught.value).isascii()
    assert isinstance(caught.value, ParserOperationalError)


def test_a_fenced_reply_gets_a_message_that_names_the_fence():
    with pytest.raises(RouteError, match='code fence'):
        model_routes.parse_reply('```json\n' + GOOD + '\n```', SCHEMA)


@pytest.mark.parametrize('requested,reported,ok', [
    ('gpt-x', 'gpt-x', True), ('gpt-x', 'gpt-x-2026-08-06', True), ('claude-haiku-4-5', 'claude-haiku-4-5-20251001', True),
    ('llama3.1', 'llama3.1:latest', True), ('gpt-x', 'gpt-x-mini', False), ('gpt-x', 'gpt-x-mini-2026-01-01', False),
    ('gpt-x', 'another', False), ('gpt-x', None, False), ('gpt-x', '', False), ('gpt-x-2026-08-06', 'gpt-x', False),
])
def test_a_reported_model_matches_only_the_same_name_or_its_dated_snapshot(requested, reported, ok):
    assert model_routes.model_matches(requested, reported) is ok
    if ok:
        model_routes.require_model(requested, reported, False)
    else:
        assert category(model_routes.require_model, requested, reported, False) == 'model_mismatch'
        model_routes.require_model(requested, reported, True)


def test_every_error_category_has_a_sentence_and_an_action_in_ascii():
    assert len(model_routes.CATEGORIES) >= 20
    for name, (sentence, action) in model_routes.CATEGORIES.items():
        error = RouteError(name)
        assert error.category == name and sentence in str(error) and action in str(error) and str(error).isascii()
    with pytest.raises(ValueError):
        RouteError('not-a-category')


def test_the_rendered_texts_hold_the_instruction_the_schema_and_the_input_unchanged():
    payload = {'system': 'Choose a label.\nBe exact.', 'catalogue': [{'item_id': 1, 'text': 'café "quoted"'}], 'request': 'x'}
    system, user = model_routes.render_messages(payload, SCHEMA)
    assert system.startswith(payload['system']) and model_routes.OUTPUT_MARKER in system
    assert json.loads(user) == {'catalogue': payload['catalogue'], 'request': 'x'}
    assert common.from_messages(system, user) == (payload, SCHEMA)
    assert common.from_prompt(model_routes.render_prompt(payload, SCHEMA)) == (payload, SCHEMA)
    for bad in ({}, {'system': ''}, {'system': 5}, 'text'):
        with pytest.raises(ValueError):
            model_routes.render_messages(bad, SCHEMA)


# ---------------------------------------------------------------- the check

def test_the_check_reports_each_step_in_ascii_and_passes_against_a_stand_in():
    lines = []
    with openai_compatible_server.make_server(replies='echo-ok') as server:
        config = {'route': 'openai-compatible', 'base_url': server.url + '/v1', 'model': common.DEFAULT_MODEL}
        result = model_routes.check_route(config, out=lines.append)
        assert [request['path'] for request in server.requests] == ['/v1/models', '/v1/chat/completions']
    assert result['ok'] and [step['name'] for step in result['steps']] == ['configuration', 'endpoint', 'test call']
    assert all(step['ok'] and step['action'] == '' for step in result['steps'])
    assert all(line.isascii() for line in lines) and any(line.startswith('OK ') for line in lines)
    assert any('one very small request' in line and 'few tokens' in line for line in lines)


def test_the_check_without_a_test_call_sends_nothing_to_the_model():
    lines = []
    with openai_compatible_server.make_server(replies='echo-ok') as server:
        config = {'route': 'openai-compatible', 'base_url': server.url + '/v1', 'model': common.DEFAULT_MODEL}
        result = model_routes.check_route(config, test_call=False, out=lines.append)
        assert [request['path'] for request in server.requests] == ['/v1/models']
    assert result['ok'] and [step['name'] for step in result['steps']] == ['configuration', 'endpoint']
    assert any('No request was sent to the model' in line for line in lines)


def test_the_check_stops_at_the_first_failed_step_and_says_what_to_do():
    lines = []
    result = model_routes.check_route({'route': 'anthropic', 'model': 'm'}, out=lines.append)
    assert not result['ok'] and [step['name'] for step in result['steps']] == ['configuration', 'credential']
    assert 'ANTHROPIC_API_KEY' in result['steps'][-1]['action'] and any(line.startswith('FAILED') for line in lines)
    result = model_routes.check_route({'route': 'nothing'}, out=lines.append)
    assert not result['ok'] and result['steps'][0]['name'] == 'configuration'
    refused = model_routes.check_route({'route': 'openai-compatible', 'base_url': 'http://127.0.0.1:9/v1', 'model': 'm'},
                                       out=lines.append)
    assert not refused['ok'] and refused['steps'][-1]['name'] == 'endpoint'
    assert 'Nothing listens' in refused['steps'][-1]['detail'] and 'ollama serve' in refused['steps'][-1]['action']
    with openai_compatible_server.make_server(replies='echo-ok') as server:
        other = model_routes.check_route({'route': 'openai-compatible', 'base_url': server.url + '/v1', 'model': 'not-installed'},
                                         out=lines.append)
    assert not other['ok'] and common.DEFAULT_MODEL in other['steps'][-1]['detail']
    assert all(line.isascii() for line in lines)


def test_the_check_of_a_relay_route_makes_no_connection():
    lines = []
    result = model_routes.check_route({'route': 'relay', 'declared_model': 'x', 'transport_note': 'by hand'}, out=lines.append)
    assert result['ok'] and [step['name'] for step in result['steps']] == ['configuration', 'relay']


def test_the_check_never_prints_the_key(capsys):
    lines = []
    with openai_compatible_server.make_server(fail='echo_key') as server:
        config = {'route': 'openai-compatible', 'base_url': server.url + '/v1', 'model': common.DEFAULT_MODEL,
                  'api_key_env': 'MY_KEY'}
        result = model_routes.check_route(config, api_key=KEY, out=lines.append)
    assert not result['ok'] and result['steps'][-1]['name'] == 'test call'
    everything = '\n'.join(lines) + json.dumps(result) + ''.join(capsys.readouterr())
    assert KEY not in everything and 'credential removed' in everything


def test_the_terminal_line_of_each_call_keeps_the_whole_error_and_never_the_key():
    lines = []
    with openai_compatible_server.make_server(replies='echo-ok') as server:
        config = {'route': 'openai-compatible', 'base_url': server.url + '/v1', 'model': common.DEFAULT_MODEL}
        infer, _, _ = model_routes.build_route(config, log=lines.append)
        assert infer(dict(model_routes.TEST_PAYLOAD), dict(model_routes.TEST_SCHEMA)) == {'ok': True}
    with openai_compatible_server.make_server(fail='echo_key') as server:
        config = {'route': 'openai-compatible', 'base_url': server.url + '/v1', 'model': common.DEFAULT_MODEL,
                  'api_key_env': 'MY_KEY'}
        infer, _, _ = model_routes.build_route(config, api_key=KEY, log=lines.append)
        with pytest.raises(RouteError):
            infer(dict(model_routes.TEST_PAYLOAD), dict(model_routes.TEST_SCHEMA))
    assert lines[0].startswith('[model route] call 1 answered in ') and 'passed the format checks' in lines[0]
    assert lines[1].startswith('[model route] call 1 FAILED after ') and 'permission:' in lines[1] and 'What to do:' in lines[1]
    assert KEY not in '\n'.join(lines) and all(line.isascii() for line in lines)


# ---------------------------------------------------------------- another adapter

def test_another_adapter_needs_one_registration_and_no_change_elsewhere():
    receipts = []

    def build(config, *, api_key=None, record_dir=None, relay_dir=None):
        def infer(payload, schema):
            receipts.append({'ordinal': len(receipts) + 1})
            return model_routes.parse_reply('{"ok": true}', schema)
        return infer, model_routes.identity_for(config, 'fixed-test-adapter', 'A fixed object; not a model.'), receipts

    def validate(raw):
        model_routes.take(raw, {'route', 'model', 'max_calls'}, 'fixed-test')
        return {'model': model_routes.text_setting(raw, 'model', 50), 'max_calls': model_routes.number_setting(raw, 'max_calls', 1, 5, 1)}

    model_routes.register_route('fixed-test', model_routes.RouteAdapter(
        validate, build, lambda config, *, api_key=None, step: step('endpoint', True, 'nothing to reach') or True,
        lambda config: ['Model: ' + config['model']], lambda config: None))
    try:
        config = model_routes.validate_config({'route': 'fixed-test', 'model': 'none'})
        infer, identity, _ = model_routes.build_route(config)
        assert infer(dict(model_routes.TEST_PAYLOAD), dict(model_routes.TEST_SCHEMA)) == {'ok': True}
        assert identity['backend'] == 'fixed-test-adapter' and identity['route'] == config
        assert model_routes.check_route(config, out=lambda line: None)['ok']
        assert model_routes.describe(config)[:2] == ['Route: fixed-test', 'Model: none']
    finally:
        model_routes._REGISTRY.pop('fixed-test')
    with pytest.raises(ValueError):
        model_routes.register_route('Bad Name', None)


# ---------------------------------------------------------------- the command-line tool

def answers(*values):
    queue = list(values)
    return lambda prompt='': queue.pop(0) if queue else ''


def test_the_wizard_builds_each_kind_of_route_from_numbered_choices():
    quiet = lambda line='': None
    no_models = lambda config, key=None: []
    local = model_route.wizard(answers('3', '1', 'llama3.1:8b'), quiet, {}, no_models)
    assert model_routes.validate_config(local)['base_url'] == 'http://127.0.0.1:11434/v1' and local['model'] == 'llama3.1:8b'
    listed = model_route.wizard(answers('3', '2', '2'), quiet, {}, lambda config, key=None: ['first-model', 'second-model'])
    assert listed == {'route': 'openai-compatible', 'preset': 'lm-studio', 'base_url': 'http://127.0.0.1:1234/v1',
                      'model': 'second-model'}
    hosted = model_route.wizard(answers('2', '2', '', 'claude-some-model'), quiet, {}, no_models)
    assert hosted == {'route': 'anthropic', 'api_key_env': 'ANTHROPIC_API_KEY', 'model': 'claude-some-model'}
    openai = model_route.wizard(answers('2', '1', 'MY_OPENAI_KEY', 'y', '1'), quiet, {'MY_OPENAI_KEY': KEY},
                                lambda config, key=None: ['listed-with-key'] if key == KEY else [])
    assert openai == {'route': 'openai-compatible', 'preset': 'openai', 'api_key_env': 'MY_OPENAI_KEY', 'model': 'listed-with-key'}
    claude = model_route.wizard(answers('1', '1', '', 'claude-some-model', 'high'), quiet, {}, no_models)
    assert claude == {'route': 'cli', 'profile': 'claude-code', 'command': 'claude', 'model': 'claude-some-model', 'effort': 'high'}
    program = model_route.wizard(answers('1', '2', 'ollama run "llama3.1:8b" --format json', 'llama3.1:8b'), quiet, {}, no_models)
    assert program['argv'] == ['ollama', 'run', 'llama3.1:8b', '--format', 'json']
    relay = model_route.wizard(answers('9', '4', 'some chat model', ''), quiet, {}, no_models)
    assert relay == {'route': 'relay', 'declared_model': 'some chat model', 'transport_note': 'copied by hand into a chat application'}
    for config in (local, listed, hosted, openai, claude, program, relay):
        model_routes.validate_config(config)


def test_setup_with_flags_writes_the_file_without_a_question_and_without_a_key(tmp_path, capsys, monkeypatch):
    path = tmp_path / 'model-route.json'
    monkeypatch.setenv('OPENAI_API_KEY', KEY)
    code = model_route.main(['setup', '--file', str(path), '--no-check', '--route', 'openai-compatible', '--preset', 'openai',
                             '--model', 'some-model', '--max-calls', '12', '--set', 'max_output_tokens=2000',
                             '--set', 'allow_reported_model_mismatch=true'])
    output = capsys.readouterr().out
    saved = json.loads(path.read_text(encoding='utf-8'))
    assert code == 0 and saved['max_calls'] == 12 and saved['max_output_tokens'] == 2000
    assert saved['allow_reported_model_mismatch'] is True and saved['api_key_env'] == 'OPENAI_API_KEY'
    assert KEY not in path.read_text(encoding='utf-8') and KEY not in output and output.isascii()
    assert '$env:OPENAI_API_KEY' in output and 'export OPENAI_API_KEY' in output
    with pytest.raises(SystemExit, match='was not changed'):
        model_route.main(['setup', '--file', str(path), '--no-check', '--route', 'relay', '--declared-model', 'x',
                          '--transport-note', 'y'])
    assert json.loads(path.read_text(encoding='utf-8')) == saved
    with pytest.raises(SystemExit, match='credential'):
        model_route.main(['setup', '--file', str(path), '--yes', '--no-check', '--route', 'anthropic', '--model', 'm',
                          '--set', 'api_key=' + KEY])
    assert KEY not in path.read_text(encoding='utf-8')


def test_the_check_and_show_commands_use_the_file_and_set_the_exit_code(tmp_path, capsys):
    path = tmp_path / 'model-route.json'
    with openai_compatible_server.make_server(replies='echo-ok') as server:
        model_route.main(['setup', '--file', str(path), '--no-check', '--route', 'openai-compatible',
                          '--base-url', server.url + '/v1', '--model', common.DEFAULT_MODEL])
        assert model_route.main(['check', '--route-file', str(path)]) == 0
        assert model_route.main(['check', '--file', str(path), '--no-test-call']) == 0
    assert model_route.main(['check', '--file', str(path)]) == 1        # the stand-in is stopped
    assert model_route.main(['show', '--file', str(path)]) == 0
    assert model_route.main(['check', '--file', str(tmp_path / 'none.json')]) == 1
    output = capsys.readouterr().out
    assert output.isascii() and 'the route works' in output and 'does not work yet' in output


# ---------------------------------------------------------------- review findings F01 to F03
# PLAIN_KEY has no known key shape (no "sk-" prefix, separators): only the
# remembered value can find it, not the shape mask.
PLAIN_KEY = 'plainkeytestvalue-0123'


def test_f01_a_preset_key_variable_is_not_given_to_another_host():
    for raw in ({'route': 'openai-compatible', 'preset': 'openai', 'base_url': 'https://other-host.example/v1', 'model': 'm'},
                {'route': 'openai-compatible', 'preset': 'openai', 'base_url': 'http://127.0.0.1:8080/v1', 'model': 'm'},
                {'route': 'anthropic', 'base_url': 'https://other-host.example', 'model': 'm'}):
        with pytest.raises(RouteError) as caught:
            model_routes.validate_config(raw)
        assert caught.value.category == 'configuration' and 'api_key_env' in caught.value.action
        # With the variable named in the file, the route is accepted and uses that variable.
        named = model_routes.validate_config({**raw, 'api_key_env': 'OTHER_HOST_KEY'})
        assert model_routes.needs_api_key(named) == 'OTHER_HOST_KEY'
    assert model_routes.needs_api_key({'route': 'openai-compatible', 'preset': 'openai', 'model': 'm'}) == 'OPENAI_API_KEY'
    assert model_routes.needs_api_key({'route': 'anthropic', 'model': 'm'}) == 'ANTHROPIC_API_KEY'


def test_f01_the_wizard_sends_a_key_only_to_a_named_host_after_a_yes():
    lines = []
    with openai_compatible_server.make_server(model='other-provider-model', replies='echo-ok') as server:
        address = server.url + '/v1'
        environ = {'OPENAI_API_KEY': KEY}
        # Enter at the variable question gives no default for another provider: the question comes again.
        config = model_route.wizard(answers('2', '3', address, '', 'OPENAI_API_KEY', 'n', 'typed-model'), lines.append,
                                    environ, model_route.listed_models)
        assert server.requests == []                                     # "n": nothing was sent
        assert config['api_key_env'] == 'OPENAI_API_KEY' and config['model'] == 'typed-model'
        assert any('127.0.0.1' in line and 'OPENAI_API_KEY' in line for line in lines)
        config = model_route.wizard(answers('2', '3', address, 'OPENAI_API_KEY', 'y', '1'), lines.append,
                                    environ, model_route.listed_models)
        assert [request['headers'].get('authorization') for request in server.requests] == ['Bearer ' + KEY]
        assert config['model'] == 'other-provider-model'
    assert all(KEY not in line for line in lines)


@pytest.mark.parametrize('requested, reported, rule', [
    ('claude-opus-5', 'claude-opus-5-5', None), ('claude-sonnet-5', 'claude-sonnet-5-5', None),
    ('claude-opus-4', 'claude-opus-4-8', None), ('gpt-5', 'gpt-5-1-2025-11-13', None), ('gpt-4o', 'gpt-4o-mini', None),
    ('gpt-4', 'gpt-4-0613', None), ('m', 'M', None), ('m', '', None), ('m', None, None),
    ('m', 'm', 'equal'), ('llama3.1', 'llama3.1:latest', 'default_tag'),
    ('claude-sonnet-4-5', 'claude-sonnet-4-5-20250929', 'dated_snapshot'),
    ('gpt-4o', 'gpt-4o-2024-08-06', 'dated_snapshot'), ('gpt-4o', 'gpt-4o-2024-13-06', None)])
def test_f02_the_model_identity_rule(requested, reported, rule):
    assert model_routes.model_rule(requested, reported) == rule
    assert model_routes.model_matches(requested, reported) is (rule is not None)


def test_f02_another_model_needs_an_exact_name_in_the_route_file():
    assert model_routes.model_rule('gpt-4', 'gpt-4-0613', ['gpt-4-0613']) == 'accepted_by_setting'
    assert model_routes.model_rule('gpt-4', 'gpt-4-0613-x', ['gpt-4-0613']) is None
    with pytest.raises(RouteError) as caught:
        model_routes.require_model('claude-opus-5', 'claude-opus-5-5')
    assert caught.value.category == 'model_mismatch' and 'accept_reported_models' in caught.value.action
    assert model_routes.validate_config({**OLLAMA, 'accept_reported_models': ['b', 'a', 'a']})['accept_reported_models'] == ['a', 'b']
    with pytest.raises(RouteError):
        model_routes.validate_config({**OLLAMA, 'accept_reported_models': ['-starts-with-a-hyphen']})


def test_f02_the_check_fails_when_the_endpoint_serves_another_model():
    lines = []
    with openai_compatible_server.make_server(model='claude-opus-5-5', replies='echo-ok') as server:
        base = {'route': 'openai-compatible', 'base_url': server.url + '/v1', 'model': 'claude-opus-5'}
        result = model_routes.check_route(base, out=lines.append)
        assert not result['ok'] and result['steps'][-1]['name'] == 'endpoint' and 'claude-opus-5-5' in result['steps'][-1]['detail']
        accepted = model_routes.check_route({**base, 'accept_reported_models': ['claude-opus-5-5']}, out=lines.append)
        assert accepted['ok'], accepted
        endpoint = [step for step in accepted['steps'] if step['name'] == 'endpoint'][0]
        assert '"claude-opus-5-5"' in endpoint['detail'] and 'accepted_by_setting' in endpoint['detail']
        assert 'accepted_by_setting' in accepted['steps'][-1]['detail']
    with openai_compatible_server.make_server(model='claude-opus-5-5', replies='echo-ok', fail='no_models_endpoint') as server:
        result = model_routes.check_route({'route': 'openai-compatible', 'base_url': server.url + '/v1',
                                           'model': 'claude-opus-5'}, out=lines.append)
        assert not result['ok'] and result['steps'][-1]['name'] == 'test call'
        assert 'claude-opus-5-5' in result['steps'][-1]['detail']
    with openai_compatible_server.make_server(model='llama3.1:latest', replies='echo-ok') as server:
        result = model_routes.check_route({'route': 'openai-compatible', 'base_url': server.url + '/v1',
                                           'model': 'llama3.1'}, out=lines.append)
        endpoint = [step for step in result['steps'] if step['name'] == 'endpoint'][0]
        assert result['ok'] and '"llama3.1:latest"' in endpoint['detail'] and 'default_tag' in endpoint['detail']


def test_f02_the_receipt_names_the_rule_that_matched():
    with openai_compatible_server.make_server(replies='echo-ok', fail='snapshot_model') as server:
        infer, _, receipts = model_routes.build_route({'route': 'openai-compatible', 'base_url': server.url + '/v1',
                                                       'model': common.DEFAULT_MODEL})
        assert infer(dict(model_routes.TEST_PAYLOAD), dict(model_routes.TEST_SCHEMA)) == {'ok': True}
    assert receipts[0]['model_match_rule'] == 'dated_snapshot'
    assert receipts[0]['reported_model'] == common.DEFAULT_MODEL + '-2026-01-01'


@pytest.mark.parametrize('raw', [
    {'route': 'cli', 'profile': 'generic', 'model': 'm', 'argv': ['tool', '--api-key=' + PLAIN_KEY, '--json']},
    {'route': 'cli', 'profile': 'generic', 'model': 'm', 'argv': ['tool', '--token', PLAIN_KEY]},
    {'route': 'cli', 'profile': 'generic', 'model': 'm', 'argv': ['tool', '-H', 'Authorization: Bearer ' + PLAIN_KEY]},
    {'route': 'cli', 'profile': 'generic', 'model': 'm', 'argv': ['tool', '--json', 'sk-proj-REALKEY0123456789abcdef']},
    {'route': 'cli', 'profile': 'generic', 'model': 'm', 'argv': ['tool', '{"auth": {"api_key": "' + PLAIN_KEY + '"}}']},
    {'route': 'cli', 'profile': 'claude-code', 'model': 'm', 'extra_args': ['--verbose', '--api-key', PLAIN_KEY]},
    {'route': 'cli', 'profile': 'claude-code', 'model': 'm', 'extra_args': ['{"token": "' + PLAIN_KEY + '"}']},
    {'route': 'openai-compatible', 'base_url': 'https://example.invalid/sk-proj-REALKEY0123456789abcdef/v1', 'model': 'm',
     'api_key_env': 'K'},
    {**OLLAMA, 'extra_body': {'user': 'gsk_0123456789abcdefghijKLMNOPQRSTUVWXYZabcdefghijklmnop'}},
    {**OLLAMA, 'extra_body': {'metadata': {'note': 'x-api-key: ' + PLAIN_KEY}}},
    {**OLLAMA, 'extra_body': {'metadata': '{"client_secret": "' + PLAIN_KEY + '"}'}},
    {**OLLAMA, 'model': 'x' + 'Ab1' * 14},
])
def test_f03_a_credential_is_refused_anywhere_in_a_setting(raw):
    with pytest.raises(RouteError) as caught:
        model_routes.validate_config(raw)
    assert caught.value.category == 'configuration' and PLAIN_KEY not in str(caught.value)


def test_f03_ordinary_settings_are_not_taken_for_credentials():
    model_routes.validate_config({**OLLAMA, 'extra_body': {'prompt_cache_key': 'study-1', 'top_k': 40}})
    model_routes.validate_config({**OLLAMA, 'api_key_env': 'OPENAI_API_KEY_comp9500_professor'})
    model_routes.validate_config({'route': 'cli', 'profile': 'generic', 'model': 'm',
                                  'argv': ['ollama', 'run', 'llama3.1:8b', '--format', 'json', '--keepalive', '5m']})
    with pytest.raises(RouteError) as caught:   # F19: a typing error gets the message of an unknown setting
        model_routes.validate_config({**OLLAMA, 'max_output_token': 100})
    assert 'does not know' in caught.value.message and 'max_output_tokens' in caught.value.action


def test_f03_the_identity_holds_a_hash_of_the_program_settings_and_the_terminal_shows_them():
    config = {'route': 'cli', 'profile': 'generic', 'model': 'declared-model',
              'argv': [sys.executable, '-c', 'print(1)', '--private-path', '/home/someone/notes']}
    infer, identity, _ = model_routes.build_route(config)
    shown = json.dumps(identity)
    assert '/home/someone/notes' not in shown and sys.executable not in shown
    assert identity['route']['settings_shown_as_sha256']['argv'] == model_routes._hash(config['argv'])
    assert any('/home/someone/notes' in line for line in model_routes.describe(config))
    claude = {'route': 'cli', 'profile': 'claude-code', 'model': 'm', 'command': '/opt/private/claude', 'extra_args': ['--verbose']}
    identity = model_routes.identity_for(model_routes.validate_config(claude), 'local-cli-claude-code', 'x')
    assert '/opt/private' not in json.dumps(identity) and '--verbose' not in json.dumps(identity)
    assert set(identity['route']['settings_shown_as_sha256']) == {'command', 'extra_args'}
    body = {**OLLAMA, 'extra_body': {'top_k': 40}}
    identity = model_routes.identity_for(model_routes.validate_config(body), 'openai-compatible-chat', 'x')
    assert 'top_k' not in json.dumps(identity) and 'extra_body' in identity['route']['settings_shown_as_sha256']


# ---------------------------------------------------------------- lead decisions 6 and 7 (page_safe, N1)

def test_every_route_error_text_is_page_safe_at_construction():
    model_routes.remember_secret(PLAIN_KEY)
    assert RouteError.page_safe is True
    for name in model_routes.CATEGORIES:
        error = RouteError(name, f'Text with the key {PLAIN_KEY}, an escape \x1b[2K, a bell \x07, a line\nbreak and '
                                 'sk-proj-ABCDEFGH12345678 ' + 'long ' * 400, f'Do this \x1b[8m{PLAIN_KEY}')
        text = str(error)
        assert error.page_safe is True and isinstance(error, ParserOperationalError)
        assert PLAIN_KEY not in text and 'ABCDEFGH12345678' not in text
        assert text.isascii() and not any(ord(char) < 32 or ord(char) == 127 for char in text)
        assert len(error.message) <= 600 and len(error.action) <= 600
        default = RouteError(name)
        assert str(default) == f'{model_routes.CATEGORIES[name][0]} {model_routes.CATEGORIES[name][1]}'
    with pytest.raises(ValueError):
        RouteError('not_a_category')


@pytest.mark.parametrize('text', [' ' + GOOD, '\x0c' + GOOD, ' ' + GOOD, GOOD + ' ', '\x0b' + GOOD])
def test_n1_only_json_white_space_may_stand_around_the_reply(text):
    with pytest.raises(RouteError) as caught:
        model_routes.parse_reply(text, SCHEMA)
    assert caught.value.category == 'reply_not_json'


def test_n1_space_tab_cr_and_lf_around_the_reply_are_accepted():
    assert model_routes.parse_reply(' \t\r\n' + GOOD + '\r\n \t', SCHEMA) == {'status': 'propose', 'label': 'Repair'}


# ---------------------------------------------------------------- minor findings of the review, and the mutation table

def test_f06_the_scrubber_removes_a_remembered_key_of_any_shape_and_length():
    clean = model_routes.scrubber(PLAIN_KEY, 'abc')
    text = clean(f'One {PLAIN_KEY} two "{PLAIN_KEY}" abc and abcdef, url {PLAIN_KEY.replace("-", "%2D")}')
    assert PLAIN_KEY not in text and ' abc ' not in text and 'abcdef' in text
    assert model_routes.scrub_bytes(b'x ' + PLAIN_KEY.encode() + b' y') == (b'x [credential removed] y', True)


def test_n9_a_plain_word_after_bearer_is_not_taken_for_a_key():
    text = model_routes.scrub('This endpoint needs Bearer authentication in the Authorization header.')
    assert text == 'This endpoint needs Bearer authentication in the Authorization header.'
    assert 'abcdefgh1234' not in model_routes.scrub('Authorization: Bearer abcdefgh1234')


def test_f08_control_characters_of_untrusted_text_become_escapes():
    assert model_routes.ascii_text('\x1b[1A\x07\x7f\u00e9') == '\\x1b[1A\\x07\\x7f\\xe9'
    with openai_compatible_server.make_server(replies='echo-ok', fail='prose') as server:
        lines = []
        model_routes.check_route({'route': 'openai-compatible', 'base_url': server.url + '/v1',
                                  'model': common.DEFAULT_MODEL}, out=lines.append)
    assert all(line.isascii() and not any(ord(char) < 32 or ord(char) == 127 for char in line) for line in lines)


def test_f10_usual_mistakes_end_in_one_message_and_not_in_a_trace(tmp_path, monkeypatch, capsys):
    cases = [['setup', '--file', str(tmp_path / 'a.json'), '--no-check', '--route', 'openai-compatible',
              '--base-url', 'http://[::1:1234/v1', '--model', 'm'],
             ['setup', '--file', str(tmp_path / 'no-folder' / 'b.json'), '--no-check', '--route', 'relay',
              '--declared-model', 'x', '--transport-note', 'y'],
             ['setup', '--file', str(tmp_path / 'c.json'), '--no-check', '--route', 'cli', '--profile', 'generic',
              '--model', 'm', '--program', 'tool "unclosed']]
    for argv in cases:
        with pytest.raises(SystemExit) as stopped:
            model_route.main(argv)
        assert isinstance(stopped.value.code, str) and stopped.value.code.isascii()
    import io

    class Interrupted(io.StringIO):
        def readline(self, *args):
            raise KeyboardInterrupt

    monkeypatch.setattr(sys, 'stdin', io.StringIO(''))          # no terminal: the first question meets the end of input
    with pytest.raises(SystemExit) as stopped:
        model_route.main(['setup', '--file', str(tmp_path / 'd.json')])
    assert 'no terminal' in stopped.value.code
    monkeypatch.setattr(sys, 'stdin', Interrupted())              # Ctrl+C at a question
    with pytest.raises(SystemExit) as stopped:
        model_route.main(['setup', '--file', str(tmp_path / 'e.json')])
    assert stopped.value.code == 'Stopped.'
    with pytest.raises(RouteError) as caught:   # a zero-width space in the key
        model_routes.resolve_api_key({**OLLAMA, 'api_key_env': 'MY_KEY'}, environ={'MY_KEY': 'abcd\u200befgh1234'})
    assert caught.value.category == 'authentication' and 'printable' in caught.value.message
    file = tmp_path / 'a-file'
    file.write_text('x')
    with pytest.raises(RouteError) as caught:
        model_routes.build_route(OLLAMA, record_dir=file)
    assert caught.value.category == 'record_failed'


def test_f11_the_check_shows_the_real_cause_of_a_key_that_cannot_be_used(tmp_path, capsys, monkeypatch):
    path = tmp_path / 'route.json'
    model_routes.save_config(path, {'route': 'openai-compatible', 'base_url': 'http://127.0.0.1:9/v1', 'model': 'm',
                                    'api_key_env': 'MY_KEY'})
    monkeypatch.setenv('MY_KEY', 'Bearer abcdefgh12345678')
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False, raising=False)
    assert model_route.main(['check', '--file', str(path)]) == 1
    output = capsys.readouterr().out
    assert 'holds a space or a line break' in output and 'is not set' not in output and 'abcdefgh12345678' not in output


def test_f12_the_wizard_asks_again_and_never_repeats_a_pasted_key():
    lines = []
    pasted = 'sk-proj-PASTEDKEY0123456789abcdefXYZ'
    config = model_route.wizard(answers('2', '3', 'https://example.invalid/v1', pasted, '$MY_KEY', 'some-model'),
                                lines.append, {}, lambda config, key=None: [])
    assert config['api_key_env'] == 'MY_KEY' and pasted not in '\n'.join(lines)
    # A number outside the list is asked again; it never becomes the model name.
    config = model_route.wizard(answers('3', '1', '7', '2'), lines.append, {}, lambda config, key=None: ['a', 'b'])
    assert config['model'] == 'b' and any('from 1 to 2' in line for line in lines)
    # An effort outside the list is asked again; the message offers no "None".
    config = model_route.wizard(answers('1', '1', '', 'claude-x-1', 'very high', 'max'), lines.append, {},
                                lambda config, key=None: [])
    assert config['effort'] == 'max' and not any('None' in line for line in lines)
    # A server on another computer: http is accepted only after a yes.
    config = model_route.wizard(answers('3', '3', 'http://192.168.1.20:11434/v1', 'n', 'http://192.168.1.20:11434/v1', 'y',
                                        'llama3.1:8b'), lines.append, {}, lambda config, key=None: [])
    assert config['allow_insecure_http'] is True and model_routes.validate_config(config)['base_url'].startswith('http://192')
    with pytest.raises(SystemExit) as stopped:
        model_route.wizard(answers('3', '1'), lines.append, {}, lambda config, key=None: [])
    assert 'No usable answer' in stopped.value.code


def test_f16_a_record_folder_that_cannot_be_written_stops_the_run_with_its_own_message(tmp_path):
    import shutil
    with openai_compatible_server.make_server(replies='echo-ok') as server:
        config = {'route': 'openai-compatible', 'base_url': server.url + '/v1', 'model': common.DEFAULT_MODEL, 'max_calls': 3}
        infer, _, receipts = model_routes.build_route(config, record_dir=tmp_path / 'gone')
        shutil.rmtree(tmp_path / 'gone')
        for _ in range(2):
            with pytest.raises(RouteError) as caught:
                infer(dict(model_routes.TEST_PAYLOAD), dict(model_routes.TEST_SCHEMA))
            assert caught.value.category == 'record_failed' and 'provider' not in caught.value.message
        assert server.requests == [] and receipts == []
        # The folder goes away after the request was sent: the paid reply is kept and the run stops after it.
        folder = tmp_path / 'late'
        infer, _, receipts = model_routes.build_route(config, record_dir=folder)
        original = model_routes.Recorder.write

        def write(self, ordinal, name, data):
            if name == 'response.txt':
                shutil.rmtree(folder)
            return original(self, ordinal, name, data)

        model_routes.Recorder.write = write
        try:
            assert infer(dict(model_routes.TEST_PAYLOAD), dict(model_routes.TEST_SCHEMA)) == {'ok': True}
        finally:
            model_routes.Recorder.write = original
        assert receipts[0]['record_incomplete'] is True and receipts[0]['receipt_file_written'] is False
        with pytest.raises(RouteError) as caught:
            infer(dict(model_routes.TEST_PAYLOAD), dict(model_routes.TEST_SCHEMA))
        assert caught.value.category == 'record_failed' and len(server.requests) == 1


def test_n4_a_record_folder_with_only_file_browser_entries_counts_as_empty(tmp_path):
    (tmp_path / 'rec').mkdir()
    (tmp_path / 'rec' / '.DS_Store').write_bytes(b'x')
    model_routes.build_route(OLLAMA, record_dir=tmp_path / 'rec')


def test_mutation_a_record_file_is_never_overwritten(tmp_path):
    recorder = model_routes.Recorder(tmp_path / 'rec')
    recorder.write(1, 'response.txt', b'first')
    with pytest.raises(RouteError) as caught:
        recorder.write(1, 'response.txt', b'second')
    assert caught.value.category == 'record_failed' and (tmp_path / 'rec' / 'call-0001-response.txt').read_bytes() == b'first'


@pytest.mark.parametrize('raw', [
    {**OLLAMA, 'model': '-starts-with-a-hyphen'},
    {**OLLAMA, 'model': '--settings'},
    {'route': 'openai-compatible', 'base_url': 'https://' + PLAIN_KEY + '@example.invalid/v1', 'model': 'm', 'api_key_env': 'K'},
    {'route': 'openai-compatible', 'base_url': 'https://user:pass@example.invalid/v1', 'model': 'm', 'api_key_env': 'K'},
    {**OLLAMA, 'api_key_env': 'MY KEY'}, {**OLLAMA, 'api_key_env': 'MY-KEY'}, {**OLLAMA, 'api_key_env': '1KEY'},
    {'route': 'relay', 'declared_model': 'x', 'transport_note': 'by hand\x07'},
    {'route': 'relay', 'declared_model': 'x\x1b[2K', 'transport_note': 'by hand'},
])
def test_mutation_settings_that_the_route_refuses(raw):
    with pytest.raises(RouteError) as caught:
        model_routes.validate_config(raw)
    assert caught.value.category == 'configuration'


def test_mutation_the_terminal_line_of_a_failed_call_passes_the_scrubber():
    model_routes.remember_secret(PLAIN_KEY)
    lines = []

    def broken(payload, schema):
        raise ValueError('a defect that shows ' + PLAIN_KEY)

    with pytest.raises(ValueError):
        model_routes._logged(broken, lines.append)({}, {})
    assert PLAIN_KEY not in lines[0] and '[credential removed]' in lines[0]


def test_mutation_the_check_cleans_every_text_that_an_adapter_gives_it():
    def check(config, *, api_key=None, step):
        step('endpoint', True, 'The endpoint answered with ' + api_key + ' \x1b[2K')
        return False

    model_routes.register_route('echo-test', model_routes.RouteAdapter(
        lambda raw: {'model': 'm', 'max_calls': 1}, lambda *args, **kwargs: None, check,
        lambda config: [], lambda config: 'ECHO_KEY'))
    try:
        lines = []
        result = model_routes.check_route({'route': 'echo-test'}, api_key=PLAIN_KEY, out=lines.append)
    finally:
        model_routes._REGISTRY.pop('echo-test')
    assert PLAIN_KEY not in json.dumps(result) + '\n'.join(lines) and '\x1b' not in '\n'.join(lines)


def test_mutation_the_allowance_counter_is_locked():
    allowance = model_routes.CallAllowance(2)
    entered = []

    class Recording:
        def __enter__(self):
            entered.append(True)

        def __exit__(self, *args):
            return False

    allowance._lock = Recording()
    assert allowance.reserve() == 1 and entered == [True]


def test_w4_a_windows_command_line_is_split_by_the_rules_of_windows():
    split = model_route.split_command
    assert split(r'"C:\Program Files\Ollama\ollama.exe" run m', os_name='nt') == [
        r'C:\Program Files\Ollama\ollama.exe', 'run', 'm']
    assert split('tool --opt="a b" c', os_name='nt') == ['tool', '--opt=a b', 'c']
    assert split(r'tool C:\path\ "x\"y"', os_name='nt') == ['tool', 'C:\\path\\', 'x"y']
    with pytest.raises(RouteError):
        split('tool "unclosed', os_name='nt')
    assert split("tool 'a b'", os_name='posix') == ['tool', 'a b']


def test_w1_a_windows_path_without_an_extension_is_completed_to_its_program_file():
    from feedctrl import route_cli
    seen = {}

    def which(name, path=None):
        seen.update(name=name, path=path)
        return path + '\\claude.CMD' if name == 'claude' else None

    found = route_cli.resolve_program(r'C:\Users\x\AppData\Roaming\npm\claude', os_name='nt', which=which)
    assert seen == {'name': 'claude', 'path': r'C:\Users\x\AppData\Roaming\npm'} and found.endswith('claude.CMD')
    assert route_cli.resolve_program('no-such-tool', os_name='nt', which=lambda name, path=None: None) is None


def test_w2_the_program_environment_keeps_the_windows_names_that_the_cli_needs():
    from feedctrl import route_cli
    assert {'CLAUDE_CODE_GIT_BASH_PATH', 'PROGRAMFILES', 'APPDATA', 'LOCALAPPDATA', 'USERPROFILE', 'PATHEXT',
            'SYSTEMROOT'} <= set(route_cli.ENV_ALLOW)
    assert not {'ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'CLAUDE_CODE_OAUTH_TOKEN', 'ANTHROPIC_AUTH_TOKEN'} & set(route_cli.ENV_ALLOW)
    assert 'pass_environment' in route_cli._SIGN_IN_ADVICE


@pytest.mark.parametrize('text, words', [('{"status": "propose", "label": "x", "n": 1e999}', 'not finite'),
                                         ('{"status": "propose", "label": "x", "d": ' + '[' * 70 + ']' * 70 + '}',
                                          'nested deeper than 64 levels')])
def test_mutation_the_reply_passes_the_fixed_size_depth_and_number_limits(text, words):
    open_schema = {**SCHEMA, 'additionalProperties': True}
    with pytest.raises(RouteError) as caught:
        model_routes.parse_reply(text, open_schema)
    assert caught.value.category == 'reply_not_json' and words in caught.value.message
