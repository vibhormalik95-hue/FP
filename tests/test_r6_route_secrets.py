"""R6 findings E3b and E4: passed credentials never reach a record file, and a check says "the route
works" only after a real model answer. Stand-in programs only; no model, no network, no key."""
import json
import os
from pathlib import Path
import sys
import urllib.parse

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
sys.path.insert(0, str(ROOT / 'scripts'))

from feedctrl import model_routes, route_cli  # noqa: E402
from feedctrl.model_routes import RouteError  # noqa: E402
from standins.route_state import fresh_route_state  # noqa: E402,F401  (autouse)
import model_route  # noqa: E402

# A made-up value, not a key of any service. It holds "/", "+", '"' and "=" so that its
# URL-encoded and JSON-escaped forms differ from it.
SENTINEL = 'r6/SENTINEL+"never-a-real-key"=Value0123456789'
UNREGISTERED = ('sk-ant-api03-' + 'R6sentinelUnregistered' + 'x' * 12, 'Bearer R6sentinel0123456789token',
                'sk-' + 'R6sentinelProj' + '9' * 20)
ECHO = r'''
import json, os, sys, urllib.parse
value = os.environ["R6_SERVICE_TOKEN"]
forms = [value, json.dumps(value)[1:-1], json.dumps(value)[1:-1].replace("/", "\\/"), urllib.parse.quote(value, safe="")]
sys.stdin.read()
sys.stderr.write("auth echo: " + " | ".join(forms) + " | " + " | ".join(UNREGISTERED) + chr(10))
sys.stdout.write(json.dumps({"ok": True, "echo": forms}))
'''


def forms(value):
    escaped = json.dumps(value)[1:-1]
    return {value, escaped, escaped.replace('/', '\\/'), urllib.parse.quote(value, safe='')}


def test_e3b_a_passed_credential_and_key_shaped_text_never_reach_the_record_files(tmp_path, monkeypatch):
    script = tmp_path / 'echo_auth.py'
    # The unregistered key shapes are in the program itself, never in the route file (which refuses them).
    script.write_text(f'UNREGISTERED = {list(UNREGISTERED)!r}' + chr(10) + ECHO, encoding='utf-8')
    monkeypatch.setenv('R6_SERVICE_TOKEN', SENTINEL)
    config = {'route': 'cli', 'profile': 'generic', 'model': 'declared',
              'argv': [sys.executable, str(script)],
              'pass_environment': ['R6_SERVICE_TOKEN']}
    infer, _, receipts = model_routes.build_route(config, record_dir=tmp_path / 'records')
    try:
        infer(dict(model_routes.TEST_PAYLOAD), dict(model_routes.TEST_SCHEMA))
    except RouteError as error:          # the extra "echo" field is refused; the records are written first
        message = str(error)
    else:
        message = ''
    files = sorted((tmp_path / 'records').iterdir())
    assert {'call-0001-stderr.txt', 'call-0001-stdin.txt', 'call-0001-stdout.txt'} <= {path.name for path in files}
    stdout = (tmp_path / 'records' / 'call-0001-stdout.txt').read_bytes()
    stderr = (tmp_path / 'records' / 'call-0001-stderr.txt').read_bytes()
    assert b'auth echo' in stderr and model_routes.REMOVED.encode() in stdout   # the program really ran
    persisted = b''.join(path.read_bytes() for path in files).decode('utf-8')
    persisted += json.dumps(receipts) + message
    for form in forms(SENTINEL):
        assert form not in persisted, form
    for key in UNREGISTERED:
        assert key.split()[-1] not in persisted, key
    assert 'R6sentinel' not in persisted


def test_e3b_only_sensitive_passed_values_are_remembered(monkeypatch):
    monkeypatch.setenv('R6_SERVICE_TOKEN', 'short1')       # credential-like name: remembered even when short
    monkeypatch.setenv('R6_LOCALE', 'en')                 # neither a credential name nor a key shape
    route_cli.environment({'pass_environment': ['R6_SERVICE_TOKEN', 'R6_LOCALE']})
    assert model_routes.scrub('token short1 here') == f'token {model_routes.REMOVED} here'
    assert model_routes.scrub('locale en here') == 'locale en here'


# ---------------------------------------------------------------- E4
def _fake_cli(monkeypatch, auth):
    monkeypatch.setattr(route_cli, '_claude_program', lambda config: str(ROOT / 'claude-stand-in'))

    def run_program(argv, *args, **kwargs):
        if argv[1:] == ['--version']:
            return 0, b'9.9.9 (stand-in)\n', b''
        if argv[1:] == ['auth', 'status']:
            if auth == 'unreadable':
                raise RouteError('unexpected_reply', 'no such command')
            return 2, b'', b'unknown command\n'
        raise AssertionError('no model call may be made')
    monkeypatch.setattr(route_cli, 'run_program', run_program)


@pytest.mark.parametrize('auth', ['unreadable', 'unreported'])
def test_e4_an_unknown_sign_in_state_is_unverified_not_signed_in(monkeypatch, auth):
    _fake_cli(monkeypatch, auth)
    lines = []
    config = {'route': 'cli', 'profile': 'claude-code', 'command': 'claude', 'model': 'm'}
    result = model_routes.check_route(config, test_call=False, out=lines.append)
    sign_in = [step for step in result['steps'] if step['name'] == 'sign-in'][0]
    assert sign_in['status'] == 'unverified' and 'not verified' in sign_in['detail']
    assert 'signed in' not in sign_in['detail'].replace('sign-in', '')
    assert result['unverified'] == ['sign-in'] and result['model_response'] is False
    assert result['test_call'] == 'skipped' and any(line.startswith('NOT VERIFIED  sign-in') for line in lines)


@pytest.mark.parametrize('result, works', [
    ({'ok': True, 'model_response': False, 'test_call': 'skipped', 'unverified': ['sign-in'], 'steps': []}, False),
    ({'ok': True, 'model_response': False, 'test_call': 'not_run', 'unverified': [], 'steps': []}, False),
    ({'ok': True, 'model_response': True, 'test_call': 'passed', 'unverified': ['sign-in'], 'steps': []}, True),
    ({'ok': False, 'model_response': False, 'test_call': 'failed', 'unverified': [], 'steps': []}, False),
])
def test_e4_the_route_works_only_after_a_real_model_answer(monkeypatch, tmp_path, result, works):
    path = tmp_path / 'model-route.json'
    model_routes.save_config(path, {'route': 'openai-compatible', 'base_url': 'http://127.0.0.1:9/v1', 'model': 'm'})
    monkeypatch.setattr(model_route, 'run_check', lambda config, **kwargs: result)
    lines = []
    code = model_route.check(type('A', (), {'file': str(path), 'no_test_call': True})(), out=lines.append)
    said = '\n'.join(lines)
    assert ('the route works' in said) is works
    assert code == (0 if result['ok'] else 1)
    if result['ok'] and not works:
        assert 'not proven to work' in said and 'no model answer was checked' in said
