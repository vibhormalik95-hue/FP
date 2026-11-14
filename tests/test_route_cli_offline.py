"""The CLI routes against stand-in programs.

The stand-in for the Claude Code CLI prints the kind of result object that the
CLI documentation describes. It is not the CLI and not a model. These tests show
which arguments and which environment a route gives to the program, and how it
reads the result. They do not show that the real CLI accepts the arguments.
"""
import json
import os
from pathlib import Path
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))

from feedctrl import model_routes, route_cli  # noqa: E402
from feedctrl.model_routes import RouteError  # noqa: E402
from standins import common  # noqa: E402
from standins.route_state import fresh_route_state  # noqa: E402,F401  (autouse)

MODEL = 'claude-standin-not-a-model'
PAYLOAD = dict(model_routes.TEST_PAYLOAD)
SCHEMA = dict(model_routes.TEST_SCHEMA)
PASSED = ['STANDIN_REPLIES', 'STANDIN_FAIL', 'STANDIN_UNKNOWN', 'STANDIN_LOG', 'STANDIN_DELAY']
pytestmark = pytest.mark.skipif(os.name == 'nt', reason='the launcher of these tests is a POSIX shell file')


@pytest.fixture
def claude(tmp_path, monkeypatch):
    """A launcher for the stand-in CLI, its log file and a function that sets its behaviour."""
    launcher = common.write_launcher(tmp_path / 'bin', ROOT / 'tests' / 'standins' / 'cli_claude_code.py')
    log = tmp_path / 'cli-log.jsonl'
    monkeypatch.setenv('STANDIN_REPLIES', 'echo-ok')
    monkeypatch.setenv('STANDIN_LOG', str(log))
    for name in ('STANDIN_FAIL', 'STANDIN_UNKNOWN'):
        monkeypatch.delenv(name, raising=False)

    def config(**settings):
        return {'route': 'cli', 'profile': 'claude-code', 'command': launcher, 'model': MODEL,
                'pass_environment': PASSED, **settings}

    config.calls = lambda: [json.loads(line) for line in log.read_text(encoding='utf-8').splitlines()]
    config.fail = lambda mode: monkeypatch.setenv('STANDIN_FAIL', mode)
    config.setenv = monkeypatch.setenv
    return config


def call(config, *, record_dir=None, payload=PAYLOAD, schema=SCHEMA):
    infer, identity, receipts = model_routes.build_route(config, record_dir=record_dir)
    try:
        return infer(dict(payload), dict(schema)), identity, receipts, None
    except RouteError as error:
        return None, identity, receipts, error


def receipt_model_rule(receipts):
    return receipts[-1].get('model_match_rule')


def generic(*arguments, **settings):
    return {'route': 'cli', 'profile': 'generic', 'model': 'declared-model-name',
            'argv': [sys.executable, str(ROOT / 'tests' / 'standins' / 'cli_generic.py'), '--replies', 'echo-ok', *arguments],
            **settings}


# ---------------------------------------------------------------- Claude Code profile

def test_one_print_mode_call_with_the_request_on_standard_input_and_a_small_flag_set(claude, monkeypatch, tmp_path):
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'sk-must-not-reach-the-program')
    monkeypatch.setenv('OPENAI_API_KEY', 'sk-must-not-reach-the-program-2')
    result, identity, receipts, error = call(claude(), record_dir=tmp_path / 'record')
    assert error is None and result == {'ok': True}
    seen = claude.calls()
    assert len(seen) == 1                                               # one process for one call
    assert seen[0]['argv'] == ['-p', route_cli.QUERY, '--output-format', 'json', '--model', MODEL, '--max-turns', '1',
                               '--safe-mode', '--no-session-persistence', '--permission-mode', 'dontAsk', '--no-chrome',
                               '--tools', '', '--disallowedTools', 'mcp__*']
    assert PAYLOAD['system'] not in ' '.join(seen[0]['argv'])            # the request is not on the command line
    names = set(seen[0]['environment_names'])
    assert 'ANTHROPIC_API_KEY' not in names and 'OPENAI_API_KEY' not in names and 'STANDIN_REPLIES' in names
    # The shell of the launcher file adds a few names of its own.
    assert 'PATH' in names and names <= (set(route_cli.ENV_ALLOW) | set(route_cli.ENV_SET) | set(PASSED)
                                         | {'PWD', 'OLDPWD', 'SHLVL', '_'})
    assert {'PYTHONUTF8', 'PYTHONIOENCODING'} <= names                    # N5: a Python program reads UTF-8
    assert receipt_model_rule(receipts) == 'equal'
    assert seen[0]['cwd_entries'] == [] and Path(seen[0]['cwd']).resolve() != ROOT and not Path(seen[0]['cwd']).exists()
    assert identity['backend'] == 'local-cli-claude-code' and identity['model'] == MODEL and identity['live_model'] is True
    receipt = receipts[0]
    assert receipt['outcome'] == 'parsed_transport_only' and receipt['exit_code'] == 0 and receipt['program'] == 'claude'
    assert receipt['reported_models'] == [MODEL] and receipt['reported_model'] == MODEL and receipt['requested_model'] == MODEL
    assert receipt['cli_result']['subtype'] == 'success' and receipt['cli_result']['is_error'] is False
    assert receipt['usage']['input_tokens'] > 0 and receipt['estimated_cost_note'] == 'estimate of the CLI, not a bill'
    assert 'ANTHROPIC_API_KEY' not in receipt['passed_environment_names']
    assert sorted(path.name for path in (tmp_path / 'record').iterdir()) == [
        'call-0001-receipt.json', 'call-0001-stderr.txt', 'call-0001-stdin.txt', 'call-0001-stdout.txt']
    stdin = (tmp_path / 'record' / 'call-0001-stdin.txt').read_text(encoding='utf-8')
    assert common.from_prompt(stdin) == (PAYLOAD, SCHEMA)
    assert 'sk-must-not-reach' not in json.dumps([identity, receipts]) + stdin


def test_settings_add_and_remove_flags(claude):
    config = claude(effort='high', max_budget_usd=1.5, omit_flags=['--no-chrome', '--safe-mode'],
                    extra_args=['--verbose'])
    assert call(config)[3] is None
    argv = claude.calls()[-1]['argv']
    assert argv[-5:] == ['--effort', 'high', '--max-budget-usd', '1.5', '--verbose']
    assert '--no-chrome' not in argv and '--safe-mode' not in argv and '--no-session-persistence' in argv


def test_the_schema_flag_is_used_only_when_the_file_asks_for_it(claude):
    result, _, receipts, error = call(claude(structured_output='json_schema'))
    argv = claude.calls()[-1]['argv']
    assert error is None and result == {'ok': True}
    assert json.loads(argv[argv.index('--json-schema') + 1]) == SCHEMA and argv[argv.index('--max-turns') + 1] == '3'
    assert '<schema>' in receipts[0]['arguments'] and json.dumps(SCHEMA) not in json.dumps(receipts[0]['arguments'])
    claude.fail('no_structured')
    assert call(claude(structured_output='json_schema'))[3].category == 'reply_not_json'
    claude.fail('wrong_schema')
    assert call(claude(structured_output='json_schema'))[3].category == 'reply_schema_mismatch'


@pytest.mark.parametrize('fail,expected,words', [
    ('not_signed_in', 'cli_not_signed_in', 'claude auth login'), ('max_turns', 'cli_failed', 'turn limit'),
    ('budget', 'cli_failed', 'max_budget_usd'), ('exit_code', 'cli_failed', 'exit code 7'),
    ('no_envelope', 'unexpected_reply', 'JSON result object'), ('other_model', 'model_mismatch', 'another-model'),
    ('no_model_usage', 'model_mismatch', 'no model name'), ('fenced', 'reply_not_json', 'code fence'),
    ('prose', 'reply_not_json', ''), ('duplicate_key', 'reply_not_json', ''), ('not_json', 'reply_not_json', ''),
    ('empty', 'reply_not_json', ''), ('wrong_schema', 'reply_schema_mismatch', ''),
])
def test_each_failure_of_the_cli_gets_its_category_and_an_action(claude, fail, expected, words):
    claude.fail(fail)
    result, _, receipts, error = call(claude())
    assert result is None and error.category == expected and error.action and str(error).isascii()
    assert words in str(error) and receipts[0]['error_category'] == expected and len(claude.calls()) == 1


def test_a_second_reported_model_is_recorded_and_a_difference_can_be_accepted(claude):
    claude.fail('extra_model')
    result, _, receipts, error = call(claude())
    assert error is None and receipts[0]['reported_models'] == ['a-small-helper-model', MODEL]
    claude.fail('other_model')
    result, _, receipts, error = call(claude(allow_reported_model_mismatch=True))
    assert error is None and result == {'ok': True} and receipts[0]['reported_models'] == ['another-model']
    assert receipts[0]['reported_model'] is None and receipts[0]['requested_model'] == MODEL


def test_an_option_that_the_cli_does_not_know_is_named_with_the_setting_that_removes_it(claude):
    claude.setenv('STANDIN_UNKNOWN', '--safe-mode')
    error = call(claude())[3]
    assert error.category == 'cli_failed' and '--safe-mode' in error.message
    assert '"--safe-mode" to "omit_flags"' in error.action
    assert call(claude(omit_flags=['--safe-mode']))[0] == {'ok': True}
    claude.setenv('STANDIN_UNKNOWN', '--verbose')
    error = call(claude(extra_args=['--verbose']))[3]
    assert '--verbose' in error.message and 'extra_args' in error.action


def test_a_program_that_does_not_finish_is_stopped_at_the_time_limit(claude):
    claude.fail('slow')
    claude.setenv('STANDIN_DELAY', '30')
    started = time.monotonic()
    error = call(claude(timeout_seconds=1))[3]
    assert error.category == 'timeout' and 'stopped' in error.message and time.monotonic() - started < 15


def test_a_timeout_also_stops_what_the_program_started(tmp_path):
    marker = tmp_path / 'child.pid'
    script = tmp_path / 'parent.py'
    script.write_text('import subprocess, sys, time\n'
                      'child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])\n'
                      f'open({str(marker)!r}, "w").write(str(child.pid))\n'
                      'time.sleep(60)\n', encoding='utf-8')
    config = {'route': 'cli', 'profile': 'generic', 'model': 'declared', 'argv': [sys.executable, str(script)],
              'timeout_seconds': 2}
    assert call(config)[3].category == 'timeout'
    child = int(marker.read_text())
    for _ in range(50):
        try:
            os.kill(child, 0)
        except ProcessLookupError:
            break
        time.sleep(0.1)
    else:
        pytest.fail('the child of the stopped program is still running')


def test_a_missing_program_is_reported_before_any_call(tmp_path):
    for config in ({'route': 'cli', 'profile': 'claude-code', 'command': str(tmp_path / 'no-such-claude'), 'model': MODEL},
                   {'route': 'cli', 'profile': 'claude-code', 'command': 'no-such-claude-on-path', 'model': MODEL},
                   {'route': 'cli', 'profile': 'generic', 'argv': ['no-such-program-on-path'], 'model': MODEL}):
        with pytest.raises(RouteError) as caught:
            model_routes.build_route(config)
        assert caught.value.category == 'cli_not_found' and 'full path' in caught.value.action
        result = model_routes.check_route(config, out=lambda line: None)
        assert not result['ok'] and result['steps'][-1]['name'] == 'program'


def test_a_windows_command_shim_gets_only_arguments_that_cmd_passes_unchanged(tmp_path):
    shim = tmp_path / 'claude.cmd'
    shim.write_text('@echo off\r\n', encoding='ascii')
    base = {'route': 'cli', 'profile': 'claude-code', 'command': str(shim), 'model': MODEL}
    args = route_cli.claude_arguments(model_routes.validate_config(base), str(shim))
    assert '--tools' not in args and args[args.index('--disallowedTools') + 1] == '*' and '' not in args
    assert not set(''.join(args)) & set('&|<>^%!"')
    for risky in ({**base, 'structured_output': 'json_schema'}, {**base, 'extra_args': ['--settings', '{"a": 1}']},
                  {**base, 'extra_args': ['a&b']}):
        with pytest.raises(RouteError) as caught:
            model_routes.build_route(risky)
        assert caught.value.category == 'configuration'
    assert route_cli.is_shim('C:\\Users\\x\\AppData\\Roaming\\npm\\claude.CMD') and not route_cli.is_shim('/usr/bin/claude')


def test_the_check_of_the_cli_reads_the_version_and_the_sign_in_state_then_makes_one_call(claude):
    lines = []
    good = model_routes.check_route(claude(), out=lines.append)
    assert good['ok'] and [step['name'] for step in good['steps']] == ['configuration', 'program', 'sign-in', 'test call']
    assert 'stand-in for the Claude Code CLI' in good['steps'][1]['detail']
    assert [entry['argv'][:2] for entry in claude.calls()] == [['--version'], ['auth', 'status'], ['-p', route_cli.QUERY]]
    claude.fail('not_signed_in')
    bad = model_routes.check_route(claude(), out=lines.append)
    assert not bad['ok'] and bad['steps'][-1]['name'] == 'sign-in' and 'claude auth login' in bad['steps'][-1]['action']
    assert all(line.isascii() for line in lines)


def test_the_cli_allowance_and_the_request_limit_hold(claude):
    infer, _, receipts = model_routes.build_route(claude(max_calls=1, max_request_bytes=2000))
    with pytest.raises(RouteError) as caught:
        infer({'system': 'x', 'catalogue': ['y' * 4000]}, dict(SCHEMA))
    assert caught.value.category == 'bad_request' and 'Nothing was sent' in caught.value.message
    with pytest.raises(RouteError) as caught:
        infer(dict(PAYLOAD), dict(SCHEMA))
    assert caught.value.category == 'allowance_exhausted' and not Path(os.environ['STANDIN_LOG']).exists()


# ---------------------------------------------------------------- any program

def test_a_program_that_reads_standard_input_answers_through_the_generic_profile(tmp_path):
    result, identity, receipts, error = call(generic(), record_dir=tmp_path / 'record')
    assert error is None and result == {'ok': True}
    assert identity['backend'] == 'local-cli-generic' and identity['model'] == 'declared-model-name'
    assert 'declared' in identity['identity_limit'] and receipts[0]['reported_model'] is None and receipts[0]['exit_code'] == 0
    assert common.from_prompt((tmp_path / 'record' / 'call-0001-stdin.txt').read_text(encoding='utf-8')) == (PAYLOAD, SCHEMA)


@pytest.mark.parametrize('fail,expected', [
    ('exit_code', 'cli_failed'), ('not_utf8', 'reply_not_json'), ('fenced', 'reply_not_json'), ('prose', 'reply_not_json'),
    ('duplicate_key', 'reply_not_json'), ('wrong_schema', 'reply_schema_mismatch'), ('not_json', 'reply_not_json'),
    ('empty', 'reply_not_json'),
])
def test_each_failure_of_a_generic_program_gets_its_category(fail, expected):
    error = call(generic('--fail', fail))[3]
    assert error.category == expected and str(error).isascii()
    if fail == 'exit_code':
        assert 'exit code 7' in error.message and 'boom' in error.message


def test_a_generic_program_without_a_reply_for_the_request_fails_and_says_it_is_a_stand_in():
    arguments = [sys.executable, str(ROOT / 'tests' / 'standins' / 'cli_generic.py'), '--replies', 'scripted']
    config = {'route': 'cli', 'profile': 'generic', 'model': 'declared', 'argv': arguments}
    error = call(config, payload={'system': 'Another request.', 'x': 1},
                 schema={'type': 'object', 'required': ['a'], 'properties': {'a': {'type': 'string'}}})[3]
    assert error.category == 'cli_failed' and 'STAND-IN, NOT A MODEL' in error.message
