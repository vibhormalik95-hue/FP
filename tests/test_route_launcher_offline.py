"""The launcher with a model route, offline.

The app is built by scripts/run_demo.py with ``--provider route`` and driven
through its own API. The model end of each route is a stand-in that answers
with the hand-written rehearsal replies. This shows that a route carries the
complete flows of the app; it is not evidence about any model or provider.
"""
import argparse
import json
import os
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(ROOT / 'tests'))

from feedctrl import model_routes  # noqa: E402
import quickstart  # noqa: E402
import run_demo  # noqa: E402
from standins import anthropic_server, common, openai_compatible_server  # noqa: E402
from standins.route_state import fresh_route_state  # noqa: E402,F401  (autouse)

KEY = 'sk-test-0123456789abcdefSECRET'
MODEL = common.DEFAULT_MODEL


def options(**values):
    base = dict(provider='route', scenario=None, port=None, reviewed_config=None, report=None, relay_dir=None,
                declared_model=None, transport_note=None, relay_timeout=600, max_calls=None, route_file=None,
                record_dir=None)
    base.update(values)
    return argparse.Namespace(**base)


def route_file(tmp_path, config):
    path = tmp_path / 'model-route.json'
    model_routes.save_config(path, config)
    return str(path)


def session(client):
    return {'X-Session-ID': client.post('/api/session', json={}).json()['session_id']}


def complete_flow(client, scenario):
    """Preview, Apply and Undo of the bundled request, exactly as the page does them."""
    headers = session(client)
    body = json.loads((run_demo.SCENARIOS[scenario] / 'app-preview.json').read_text())
    before = client.get('/api/semantic/groups?user_id=1', headers=headers).json()
    if scenario == 'category':
        definition = client.post('/api/semantic/definition/preview', headers=headers, json=body).json()
        assert definition['definition_ready'], definition
        review = client.post('/api/semantic/definition/classify', headers=headers, json={
            'user_id': 1, 'plan_id': definition['definition_plan_id'], 'evidence_reviewed': True}).json()
    else:
        review = client.post('/api/semantic/preview', headers=headers, json=body).json()
    assert review['ready'] and review['applied'] is False, review
    assert client.get('/api/semantic/groups?user_id=1', headers=headers).json()['feed'] == before['feed']
    applied = client.post('/api/semantic/apply', headers=headers, json={'user_id': 1, 'plan_id': review['plan_id']}).json()
    assert applied['feed']['available_items'] == 5
    undo = client.post('/api/semantic/history/preview', headers=headers, json={'user_id': 1, 'action': 'undo'}).json()
    restored = client.post('/api/semantic/apply', headers=headers, json={'user_id': 1, 'plan_id': undo['plan_id']}).json()
    assert restored['feed'] == before['feed'] and restored['groups'] == []
    return review


def test_an_openai_compatible_route_carries_the_indirect_request_flow(tmp_path, capsys):
    record = tmp_path / 'record'
    with openai_compatible_server.make_server(replies='scripted') as server:
        path = route_file(tmp_path, {'route': 'openai-compatible', 'base_url': server.url + '/v1', 'model': MODEL})
        app, port, summary, _ = run_demo.build_app(options(scenario='hunger', route_file=path, record_dir=str(record)))
        with TestClient(app) as client:
            status = client.get('/api/status').json()
            assert status['provider'] == {'backend': 'openai-compatible-chat', 'model': MODEL,
                                          'live_model': 'declared_by_adapter'}
            review = complete_flow(client, 'hunger')
        chat = [request for request in server.requests if request['path'] == '/v1/chat/completions']
    assert port == 8765 and len(chat) == 2                              # action, then evidence; no other request
    assert review['groups'][0]['proposal']['provenance']['model']['backend'] == 'openai-compatible-chat'
    assert summary['provider'] == 'route' and summary['route'][0] == 'Route: openai-compatible'
    assert summary['identity']['route']['model'] == MODEL and summary['record_dir'] == str(record.resolve())
    assert sorted(path.name for path in record.iterdir()) == [
        f'call-000{n}-{part}' for n in (1, 2) for part in ('receipt.json', 'request.json', 'response.txt')]
    assert [receipt['outcome'] for receipt in app.state.provider_receipts] == ['parsed_transport_only'] * 2


def test_an_anthropic_route_carries_the_new_category_flow_and_the_key_stays_out_of_every_output(tmp_path, monkeypatch):
    monkeypatch.setenv('ANTHROPIC_API_KEY', KEY)
    record = tmp_path / 'record'
    with anthropic_server.make_server(replies='scripted') as server:
        path = route_file(tmp_path, {'route': 'anthropic', 'base_url': server.url, 'model': MODEL,
                                     'api_key_env': 'ANTHROPIC_API_KEY'})
        app, _, summary, _ = run_demo.build_app(options(scenario='category', route_file=path, record_dir=str(record)))
        with TestClient(app) as client:
            status = client.get('/api/status').json()
            review = complete_flow(client, 'category')
        messages = [request for request in server.requests if request['path'] == '/v1/messages']
    assert len(messages) == 3                                           # definition, membership, evidence assessment
    assert all(request['headers']['authorization'] == 'Bearer ' + KEY for request in messages)
    assert status['provider']['backend'] == 'anthropic-messages'
    recorded = b''.join(path.read_bytes() for path in record.iterdir())
    outputs = json.dumps([summary, status, review, app.state.provider_receipts], default=str) + Path(path).read_text()
    assert KEY not in outputs and KEY.encode() not in recorded


@pytest.mark.skipif(os.name == 'nt', reason='the launcher of this test is a POSIX shell file')
def test_a_cli_route_carries_the_indirect_request_flow(tmp_path, monkeypatch):
    launcher = common.write_launcher(tmp_path / 'bin', ROOT / 'tests' / 'standins' / 'cli_claude_code.py')
    monkeypatch.setenv('STANDIN_REPLIES', 'scripted')
    path = route_file(tmp_path, {'route': 'cli', 'profile': 'claude-code', 'command': launcher, 'model': MODEL,
                                 'pass_environment': ['STANDIN_REPLIES']})
    app, _, summary, _ = run_demo.build_app(options(scenario='hunger', route_file=path, record_dir='none'))
    with TestClient(app) as client:
        assert client.get('/api/status').json()['provider']['backend'] == 'local-cli-claude-code'
        complete_flow(client, 'hunger')
    assert 'record_dir' not in summary and len(app.state.provider_receipts) == 2


def test_a_relay_route_gets_a_new_relay_folder(tmp_path):
    path = route_file(tmp_path, {'route': 'relay', 'declared_model': 'declared chat model', 'transport_note': 'by hand'})
    relay = tmp_path / 'relay'
    app, _, summary, _ = run_demo.build_app(options(scenario='hunger', route_file=path, relay_dir=str(relay)))
    assert summary['relay_dir'] == str(relay.resolve()) and relay.is_dir() and 'record_dir' not in summary
    with TestClient(app) as client:
        assert client.get('/api/status').json()['provider'] == {
            'backend': 'operator-relay-file-queue', 'model': 'declared chat model', 'live_model': 'operator_declared'}


def test_start_problems_are_one_plain_message_and_not_a_trace(tmp_path, monkeypatch):
    monkeypatch.delenv('ANTHROPIC_API_KEY', raising=False)
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False, raising=False)
    with pytest.raises(SystemExit) as stopped:
        run_demo.build_app(options(scenario='hunger', route_file=str(tmp_path / 'missing.json')))
    assert 'does not exist' in str(stopped.value) and 'model_route.py setup' in str(stopped.value)
    path = route_file(tmp_path, {'route': 'anthropic', 'model': MODEL})
    with pytest.raises(SystemExit) as stopped:
        run_demo.build_app(options(scenario='hunger', route_file=path))
    assert 'ANTHROPIC_API_KEY is not set' in str(stopped.value) and str(stopped.value).isascii()
    (tmp_path / 'full').mkdir()
    (tmp_path / 'full' / 'old.txt').write_text('x')
    local = route_file(tmp_path, {'route': 'openai-compatible', 'base_url': 'http://127.0.0.1:9/v1', 'model': MODEL})
    with pytest.raises(SystemExit) as stopped:
        run_demo.build_app(options(scenario='hunger', route_file=local, record_dir=str(tmp_path / 'full')))
    assert 'not empty' in str(stopped.value)


def test_a_route_failure_reaches_the_page_as_a_message_that_says_what_to_do(tmp_path, monkeypatch):
    monkeypatch.setenv('MY_KEY', KEY)
    with openai_compatible_server.make_server(fail='unauthorized') as server:
        path = route_file(tmp_path, {'route': 'openai-compatible', 'base_url': server.url + '/v1', 'model': MODEL,
                                     'api_key_env': 'MY_KEY'})
        for scenario, url in (('hunger', '/api/semantic/preview'), ('category', '/api/semantic/definition/preview')):
            app, _, _, _ = run_demo.build_app(options(scenario=scenario, route_file=path, record_dir='none'))
            with TestClient(app) as client:
                headers = session(client)
                body = json.loads((run_demo.SCENARIOS[scenario] / 'app-preview.json').read_text())
                before = client.get('/api/semantic/groups?user_id=1', headers=headers).json()['feed']
                response = client.post(url, headers=headers, json=body)
                text = json.dumps(response.json())
                assert response.status_code == (502 if scenario == 'hunger' else 200)
                assert 'HTTP 401' in text and 'MY_KEY' in text and KEY not in text
                assert client.get('/api/semantic/groups?user_id=1', headers=headers).json()['feed'] == before


def test_the_launcher_accepts_the_route_options_on_its_command_line(tmp_path, monkeypatch, capsys):
    seen = {}
    monkeypatch.setattr(run_demo, 'build_app', lambda args: seen.update(vars(args)) or (_ for _ in ()).throw(SystemExit('stop')))
    with pytest.raises(SystemExit, match='stop'):
        run_demo.main(['--scenario', 'hunger', '--provider', 'route', '--route-file', 'x.json', '--record-dir', 'none'])
    assert seen['provider'] == 'route' and seen['route_file'] == 'x.json' and seen['record_dir'] == 'none'


def test_quickstart_start_hands_the_key_to_the_server_in_its_environment_only(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('MY_KEY', KEY)
    path = route_file(tmp_path, {'route': 'openai-compatible', 'base_url': 'http://127.0.0.1:9/v1', 'model': MODEL,
                                 'api_key_env': 'MY_KEY'})
    started = {}

    class Server:
        def poll(self):
            return 0

    monkeypatch.setattr(quickstart, 'run_demo', lambda *arguments, env=None: started.update(arguments=arguments, env=env) or Server())
    monkeypatch.setattr(quickstart, 'wait_until_served', lambda port, server: None)
    monkeypatch.setattr(quickstart, 'keep_serving', lambda server: None)
    quickstart.main(['start', '--scenario', 'hunger', '--route-file', path, '--port', '8805', '--record-dir', 'none'])
    output = capsys.readouterr().out
    assert started['arguments'] == ('--scenario', 'hunger', '--provider', 'route', '--route-file', path, '--port', '8805',
                                    '--record-dir', 'none')
    assert started['env']['MY_KEY'] == KEY and KEY not in ' '.join(started['arguments']) and KEY not in output
    assert 'Route: openai-compatible' in output and 'http://127.0.0.1:8805' in output and output.isascii()
    monkeypatch.delenv('MY_KEY')
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False, raising=False)
    with pytest.raises(SystemExit) as stopped:
        quickstart.main(['start', '--scenario', 'hunger', '--route-file', path])
    # F11: the real cause, and no advice to run the setup again (the file is good).
    assert 'MY_KEY is not set' in str(stopped.value) and 'quickstart.py setup' not in str(stopped.value)


def test_quickstart_start_prints_the_relay_commands_for_a_relay_route(tmp_path, monkeypatch, capsys):
    path = route_file(tmp_path, {'route': 'relay', 'declared_model': 'declared chat model', 'transport_note': 'by hand'})
    started = {}

    class Server:
        def poll(self):
            return 0

    monkeypatch.setattr(quickstart, 'run_demo', lambda *arguments, env=None: started.update(arguments=arguments, env=env) or Server())
    monkeypatch.setattr(quickstart, 'wait_until_served', lambda port, server: None)
    monkeypatch.setattr(quickstart, 'keep_serving', lambda server: None)
    quickstart.main(['start', '--scenario', 'category', '--route-file', path])
    output = capsys.readouterr().out
    relay = started['arguments'][started['arguments'].index('--relay-dir') + 1]
    assert 'relay-category-' in relay and started['env'] is None
    assert 'relay_tools.py show' in output and 'relay_tools.py deliver' in output and relay in output


def test_quickstart_setup_and_doctor_are_the_route_tool(tmp_path, capsys):
    path = tmp_path / 'model-route.json'
    with pytest.raises(SystemExit) as done:
        quickstart.main(['setup', '--file', str(path), '--no-check', '--route', 'relay', '--declared-model', 'x',
                         '--transport-note', 'by hand'])
    assert done.value.code == 0 and json.loads(path.read_text())['route'] == 'relay'
    with pytest.raises(SystemExit) as done:
        quickstart.main(['doctor', '--file', str(path)])
    assert done.value.code == 0
    with pytest.raises(SystemExit) as done:
        quickstart.main(['doctor', '--file', str(tmp_path / 'none.json')])
    assert done.value.code == 1
    assert 'the route works' in capsys.readouterr().out


def test_the_earlier_quick_start_steps_still_parse():
    parser_error = None
    try:
        quickstart.main(['rehearse', '--scenario', 'not-a-scenario'])
    except SystemExit as stopped:
        parser_error = stopped.code
    assert parser_error == 2
    assert sorted(run_demo.SCENARIOS) == sorted(set(run_demo.SCENARIOS)) and 'category' in run_demo.SCENARIOS


# ---------------------------------------------------------------- review findings F04 and F05

def test_f04_quickstart_start_hands_absolute_paths_to_the_server(tmp_path, monkeypatch, capsys):
    mine = tmp_path / 'my-folder'
    mine.mkdir()
    monkeypatch.chdir(mine)
    model_routes.save_config(mine / 'model-route.json', {'route': 'openai-compatible', 'base_url': 'http://127.0.0.1:9/v1',
                                                          'model': 'model-of-the-file-in-my-folder'})
    started = {}

    class Server:
        def poll(self):
            return 0

    monkeypatch.setattr(quickstart, 'run_demo', lambda *arguments, env=None: started.update(arguments=arguments) or Server())
    monkeypatch.setattr(quickstart, 'wait_until_served', lambda port, server: None)
    monkeypatch.setattr(quickstart, 'keep_serving', lambda server: None)
    monkeypatch.setattr(quickstart, 'require_free_port', lambda port: None)
    quickstart.main(['start', '--scenario', 'hunger', '--route-file', 'model-route.json', '--record-dir', 'myrecords'])
    arguments = started['arguments']
    served = arguments[arguments.index('--route-file') + 1]
    records = arguments[arguments.index('--record-dir') + 1]
    assert served == str(mine / 'model-route.json') and Path(served).is_absolute()
    assert records == str(mine / 'myrecords') and Path(records).is_absolute()
    output = capsys.readouterr().out
    assert 'model-of-the-file-in-my-folder' in output and str(mine / 'model-route.json') in output


def _local_get(url, data=None, headers=None, timeout=5):
    import urllib.request
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request = urllib.request.Request(url, data=data, headers=headers or {}, method='POST' if data is not None else 'GET')
    with opener.open(request, timeout=timeout) as response:
        return response.status, response.read()


def _gone(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    return False


@pytest.mark.skipif(os.name == 'nt', reason='SIGINT to another process and the POSIX launcher file; not run on Windows')
def test_f05_ctrl_c_stops_the_server_and_the_running_cli_program(tmp_path):
    import signal
    import socket
    import subprocess
    import threading
    import time
    launcher = common.write_launcher(tmp_path / 'bin', ROOT / 'tests' / 'standins' / 'cli_claude_code.py')
    log = tmp_path / 'cli-log.jsonl'
    path = route_file(tmp_path, {'route': 'cli', 'profile': 'claude-code', 'command': launcher, 'model': MODEL,
                                 'pass_environment': ['STANDIN_REPLIES', 'STANDIN_FAIL', 'STANDIN_DELAY', 'STANDIN_LOG']})
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    env = {**os.environ, 'STANDIN_REPLIES': 'scripted', 'STANDIN_FAIL': 'slow', 'STANDIN_DELAY': '60',
           'STANDIN_LOG': str(log), 'PYTHONUNBUFFERED': '1'}
    server = subprocess.Popen([sys.executable, str(ROOT / 'scripts' / 'run_demo.py'), '--scenario', 'hunger',
                               '--provider', 'route', '--route-file', path, '--record-dir', 'none', '--port', str(port)],
                              cwd=str(ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        base = f'http://127.0.0.1:{port}'
        for _ in range(80):
            try:
                if _local_get(base + '/')[0] == 200:
                    break
            except OSError:
                time.sleep(0.25)
        session = json.loads(_local_get(base + '/api/session', b'{}', {'Content-Type': 'application/json'})[1])['session_id']
        body = (run_demo.SCENARIOS['hunger'] / 'app-preview.json').read_bytes()
        answer = {}

        def preview():
            try:
                answer['status'] = _local_get(base + '/api/semantic/preview', body,
                                              {'Content-Type': 'application/json', 'X-Session-ID': session}, timeout=90)[0]
            except Exception as error:   # noqa: BLE001  (an error answer or a closed connection are both acceptable)
                answer['error'] = type(error).__name__

        threading.Thread(target=preview, daemon=True).start()
        for _ in range(80):
            if log.exists() and log.read_text().strip():
                break
            time.sleep(0.25)
        program = json.loads(log.read_text().splitlines()[-1])
        assert not _gone(program['pid'])
        started = time.monotonic()
        server.send_signal(signal.SIGINT)
        code = server.wait(timeout=30)
        seconds = time.monotonic() - started
        output = server.stdout.read().decode('utf-8', 'replace')
        assert seconds < 15, output
        assert _gone(program['pid']) and not Path(program['cwd']).exists(), output
        assert code == 0 and 'Traceback' not in output, output
        assert 'call 1 FAILED' in output and 'stopping' in output, output
        assert len(log.read_text().splitlines()) == 1                    # no second call after the stop
    finally:
        if server.poll() is None:
            server.kill()
            server.wait()


# ---------------------------------------------------------------- minor findings: launcher options, proxy, busy port, Windows stop

def test_n4_the_launcher_options_of_a_route_do_what_they_say(tmp_path, monkeypatch):
    path = route_file(tmp_path, {'route': 'openai-compatible', 'base_url': 'http://127.0.0.1:9/v1', 'model': MODEL})
    app, _, summary, _ = run_demo.build_app(options(scenario='hunger', route_file=path, record_dir='None', max_calls=1))
    assert 'record_dir' not in summary and summary['identity']['route']['max_calls'] == 1
    assert any('Call allowance for one run: 1 ' in line for line in summary['route'])
    for name, value in (('declared_model', 'x'), ('transport_note', 'y'), ('relay_timeout_given', 30.0)):
        with pytest.raises(SystemExit) as stopped:
            run_demo.build_app(options(scenario='hunger', route_file=path, record_dir='none', **{name: value}))
        assert 'belong to --provider relay' in str(stopped.value)
    monkeypatch.setattr(run_demo, 'ROOT', tmp_path)
    _, _, summary, _ = run_demo.build_app(options(scenario='hunger', route_file=path))
    assert Path(summary['record_dir']).name.startswith('route-hunger-') and summary['record_dir'].endswith('Z')


def test_f20_the_readiness_probe_never_uses_a_proxy(monkeypatch):
    import http.server
    import threading

    class Page(http.server.BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Length', '0')
            self.end_headers()

    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Page)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    for name in ('http_proxy', 'HTTP_PROXY'):
        monkeypatch.setenv(name, 'http://127.0.0.1:9')
    for name in ('no_proxy', 'NO_PROXY'):
        monkeypatch.setenv(name, '')

    class Running:
        def poll(self):
            return None

    try:
        quickstart.wait_until_served(server.server_port, Running(), seconds=5)
    finally:
        server.shutdown()
        server.server_close()


def test_lead_11_rehearse_on_a_busy_port_fails_with_a_clear_message():
    import socket
    import subprocess
    with socket.socket() as busy:
        busy.bind(('127.0.0.1', 0))
        busy.listen(1)
        port = busy.getsockname()[1]
        done = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'quickstart.py'), 'rehearse', '--port', str(port)],
                              capture_output=True, text=True, timeout=60, cwd=str(ROOT))
    assert done.returncode != 0 and f'Port {port}' in done.stderr and 'in use' in done.stderr
    assert 'keeps running' not in done.stdout


def test_lead_11_a_server_that_ends_with_an_error_ends_the_launcher_with_its_code():
    class Failed:
        returncode = 1

        def wait(self, timeout=None):
            return 1

        def poll(self):
            return 1

    with pytest.raises(SystemExit) as stopped:
        quickstart.serve_until_stopped(Failed())
    assert stopped.value.code == 1


def test_w3_on_windows_the_launcher_asks_the_server_to_stop_with_ctrl_break(monkeypatch):
    import signal
    import subprocess
    monkeypatch.setattr(quickstart, 'WINDOWS', True)
    monkeypatch.setattr(signal, 'CTRL_BREAK_EVENT', 1, raising=False)
    monkeypatch.setattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0x200, raising=False)
    sent = []

    class Server:
        def __init__(self):
            self.code = None

        def poll(self):
            return self.code

        def send_signal(self, value):
            sent.append(value)
            self.code = 0

        def wait(self, timeout=None):
            return self.code

        def terminate(self):
            sent.append('terminate')

        kill = terminate

    assert quickstart.stop_server(Server()) == 0 and sent == [1]
    started = {}
    monkeypatch.setattr(subprocess, 'Popen', lambda *args, **kwargs: started.update(kwargs) or Server())
    quickstart.run_demo('--scenario', 'tags')
    assert started['creationflags'] == 0x200
