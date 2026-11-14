"""The relay helpers and the Claude Code CLI operator, with a stand-in for the CLI.

No model, no network and no real CLI are used. The stand-in program prints the
kind of JSON result that the CLI prints in print mode with --output-format json.
"""
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import textwrap

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import relay_claude_cli  # noqa: E402
import relay_tools  # noqa: E402

SCHEMA = {'type': 'object', 'additionalProperties': False, 'required': ['status', 'label'],
          'properties': {'status': {'enum': ['propose', 'clarify']}, 'label': {'type': 'string', 'maxLength': 20}}}
GOOD = {'status': 'propose', 'label': 'Repair'}
MODEL = 'claude-fable-5-2'

FAKE = textwrap.dedent('''
    import json, sys
    from pathlib import Path
    here = Path(__file__).resolve().parent
    mode = (here / 'mode.txt').read_text().strip()
    stdin = sys.stdin.buffer.read().decode('utf-8')
    calls = here / 'calls.json'
    seen = json.loads(calls.read_text()) if calls.exists() else []
    seen.append({'argv': sys.argv[1:], 'stdin': stdin})
    calls.write_text(json.dumps(seen))
    if mode == 'exit3':
        sys.stderr.write('unknown option --safe-mode\\n'); sys.exit(3)
    good = json.dumps({'status': 'propose', 'label': 'Repair'})
    text = {'ok': good, 'fence': '```json\\n' + good + '\\n```', 'schema': json.dumps({'status': 'maybe', 'label': 'x'}),
            'error': good, 'othermodel': good}[mode]
    models = {'claude-other-1': {}} if mode == 'othermodel' else {'claude-fable-5-2': {'outputTokens': 5}}
    print(json.dumps({'type': 'result', 'subtype': 'success', 'is_error': mode == 'error', 'num_turns': 1,
                      'stop_reason': 'end_turn', 'duration_ms': 12, 'total_cost_usd': 0.01, 'result': text,
                      'usage': {'input_tokens': 3, 'output_tokens': 5}, 'modelUsage': models}))
''')


@pytest.fixture
def relay(tmp_path):
    spool = tmp_path / 'relay'
    spool.mkdir()
    request = {'ordinal': 1, 'created_utc': '2026-01-01T00:00:00+00:00', 'system': 'Choose a label.',
               'payload': {'items': [1, 2]}, 'schema': SCHEMA}
    request['request_sha256'] = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
    (spool / 'request-0001.json').write_text(json.dumps(request), encoding='utf-8')
    return spool


@pytest.fixture
def fake_cli(tmp_path):
    folder = tmp_path / 'cli'
    folder.mkdir()
    (folder / 'fake.py').write_text(FAKE, encoding='utf-8')
    (folder / 'mode.txt').write_text('ok')
    if os.name == 'nt':
        launcher = folder / 'claude.cmd'
        launcher.write_text(f'@"{sys.executable}" "{folder / "fake.py"}" %*\r\n')
    else:
        launcher = folder / 'claude'
        launcher.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{folder / "fake.py"}" "$@"\n')
        launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR)
    return launcher


def operate(relay, fake_cli, *extra):
    relay_claude_cli.main([str(relay), '--calls', '1', '--claude', str(fake_cli), '--wait', '5', '--timeout', '60', *extra])


# ---- relay_tools: a refused file does not spend the call --------------------------------------

def test_deliver_refuses_what_the_app_would_reject_and_delivers_nothing(relay, tmp_path):
    answer = tmp_path / 'answer.json'
    for content, expected in [(b'```json\n{"status":"propose","label":"Repair"}\n```', 'not one JSON object'),
                              (b'Here it is: {"status":"propose","label":"Repair"}', 'not one JSON object'),
                              ('{"status":"propose","label":"Repair"}'.encode('utf-16'), 'not UTF-8'),
                              (b'[1, 2]', 'not an object'),
                              (b'{"status":"maybe","label":"Repair"}', 'does not match the schema'),
                              (b'{"status":"propose","label":"Repair","extra":1}', 'does not match the schema')]:
        answer.write_bytes(content)
        with pytest.raises(SystemExit) as stopped:
            relay_tools.deliver(relay, 1, answer)
        assert 'NOT DELIVERED' in str(stopped.value) and expected in str(stopped.value)
        assert not (relay / 'response-0001.json').exists()
        with pytest.raises(SystemExit):
            relay_tools.check(relay, 1, answer)


def test_deliver_copies_an_acceptable_answer_byte_for_byte(relay, tmp_path, capsys):
    answer = tmp_path / 'answer.json'
    raw = b'\xef\xbb\xbf{ "status": "propose",\r\n  "label": "Repair" }\r\n'  # Notepad: BOM and CRLF
    answer.write_bytes(raw)
    relay_tools.check(relay, 1, answer)
    relay_tools.deliver(relay, 1, answer)
    assert (relay / 'response-0001.json').read_bytes() == raw
    assert json.loads(capsys.readouterr().out.splitlines()[-1])['answer_sha256'] == hashlib.sha256(raw).hexdigest()
    with pytest.raises(SystemExit, match='already delivered'):
        relay_tools.deliver(relay, 1, answer)


def test_force_records_a_model_reply_that_is_not_a_valid_answer(relay, tmp_path, capsys):
    answer = tmp_path / 'answer.json'
    answer.write_bytes(b'I cannot answer that.')
    relay_tools.deliver(relay, 1, answer, force=True)
    assert (relay / 'response-0001.json').read_bytes() == b'I cannot answer that.'
    assert 'forced_despite' in json.loads(capsys.readouterr().out.splitlines()[-1])


# ---- the CLI operator --------------------------------------------------------------------------

def test_operator_makes_one_call_and_delivers_the_reply_unchanged(relay, fake_cli):
    operate(relay, fake_cli)
    calls = json.loads((fake_cli.parent / 'calls.json').read_text())
    assert len(calls) == 1
    request = json.loads((relay / 'request-0001.json').read_text())
    assert calls[0]['stdin'] == relay_tools.render(request)          # the whole request text, on standard input
    argv = calls[0]['argv']
    assert argv[0] == '-p' and '--output-format' in argv and argv[argv.index('--model') + 1] == MODEL
    assert argv[argv.index('--max-turns') + 1] == '1' and argv[argv.index('--effort') + 1] == 'max'
    assert 'Choose a label.' not in ' '.join(argv)                    # no request text in a flag
    assert json.loads((relay / 'response-0001.json').read_text()) == GOOD
    record = json.loads((relay / 'cli-call-0001.json').read_text())
    assert record['delivered'] is True and record['reported_models'] == [MODEL] and record['exit_code'] == 0
    assert record['usage'] == {'input_tokens': 3, 'output_tokens': 5}
    assert 'Choose a label.' not in json.dumps(record)               # the record holds no request text


@pytest.mark.parametrize('mode, reason, reply_kept', [
    ('fence', 'not one JSON object', True),
    ('schema', 'does not match the schema', True),
    ('error', 'did not report a successful result', True),
    ('othermodel', 'reported the models', True),
    ('exit3', 'exit code 3', False),
])
def test_operator_stops_without_delivery_and_without_a_second_call(relay, fake_cli, mode, reason, reply_kept):
    (fake_cli.parent / 'mode.txt').write_text(mode)
    with pytest.raises(SystemExit) as stopped:
        operate(relay, fake_cli)
    assert 'NOT delivered' in str(stopped.value) and reason in str(stopped.value)
    assert not (relay / 'response-0001.json').exists()               # the request is still open
    assert len(json.loads((fake_cli.parent / 'calls.json').read_text())) == 1
    record = json.loads((relay / 'cli-call-0001.json').read_text())
    assert record['delivered'] is False and reason in record['not_delivered_because']
    assert (relay / 'cli-reply-0001.not-delivered.txt').exists() is reply_kept


def test_operator_can_accept_another_reported_model_when_told_to(relay, fake_cli):
    (fake_cli.parent / 'mode.txt').write_text('othermodel')
    operate(relay, fake_cli, '--allow-other-models')
    assert json.loads((relay / 'cli-call-0001.json').read_text())['reported_models'] == ['claude-other-1']
    assert (relay / 'response-0001.json').exists()


def test_operator_skips_a_request_that_already_has_a_reply(relay, fake_cli):
    (relay / 'response-0001.json').write_text(json.dumps(GOOD))
    operate(relay, fake_cli)
    assert not (fake_cli.parent / 'calls.json').exists()


def test_operator_does_not_pass_api_keys_to_the_cli(relay, fake_cli, monkeypatch):
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'OFFLINE-DUMMY-NOT-A-CREDENTIAL')
    seen = {}
    real_run = relay_claude_cli.subprocess.run

    def spy(argv, **kwargs):
        seen.update(kwargs['env'])
        return real_run(argv, **kwargs)

    monkeypatch.setattr(relay_claude_cli.subprocess, 'run', spy)
    operate(relay, fake_cli)
    assert 'ANTHROPIC_API_KEY' not in seen and seen['CLAUDE_CODE_MAX_RETRIES'] == '0'


def test_an_empty_argument_is_left_out_for_a_windows_command_shim():
    assert '' in relay_claude_cli.cli_arguments('C:/x/claude.exe', MODEL, 'max', 2)
    assert '' not in relay_claude_cli.cli_arguments('C:/x/claude.cmd', MODEL, 'max', 2)
