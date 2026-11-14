"""The demonstration launcher, offline. No listener, no process, no model.

The personal-cli path is exercised with an authored runner that returns CLI
envelopes built from the hand-written rehearsal replies. That checks wiring,
the operator-token boundary and the provider report; it is not evidence about
the Windows process runner, the real CLI or any model.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import demo_scripted_replies  # noqa: E402
import run_demo  # noqa: E402

MODEL = 'claude-fable-5-2'
TOKEN = 'offline-test-operator-token-0123456789abcdef'


def options(**values):
    base = dict(provider='manual', scenario=None, port=None, reviewed_config=None, report=None,
                relay_dir=None, declared_model=None, transport_note=None, relay_timeout=600, max_calls=None)
    base.update(values)
    return argparse.Namespace(**base)


def session(client, headers=None):
    headers = dict(headers or {})
    headers['X-Session-ID'] = client.post('/api/session', json={}, headers=headers).json()['session_id']
    return headers


def test_built_interface_check_names_a_missing_asset(tmp_path, monkeypatch):
    dist = tmp_path / 'web' / 'dist'
    dist.mkdir(parents=True)
    (dist / 'index.html').write_text('<script src="/assets/app.js"></script><link href="/assets/app.css">')
    monkeypatch.setattr(run_demo, 'ROOT', tmp_path)
    with pytest.raises(SystemExit, match='assets/app.js'):
        run_demo.require_built_interface()
    (dist / 'assets').mkdir()
    (dist / 'assets' / 'app.js').write_text('')
    with pytest.raises(SystemExit, match='assets/app.css'):
        run_demo.require_built_interface()
    (dist / 'assets' / 'app.css').write_text('')
    run_demo.require_built_interface()


def test_repository_interface_is_complete():
    run_demo.require_built_interface()


def test_manual_provider_offers_no_model_and_only_the_manual_control():
    app, port, summary, _ = run_demo.build_app(options())
    assert port == 8765 and summary == {'scenario': 'category', 'provider': 'manual'}
    with TestClient(app) as client:
        status = client.get('/api/status').json()
        assert status['provider'] is None and status['local_models_allowed'] is False
        assert status['data_mode'] == 'fixture' and status['items'] == 8
        headers = session(client)
        saved = client.get('/api/semantic/groups?user_id=1', headers=headers).json()
        assert saved['category_adapter_available'] is False and saved['external_adapter_available'] is False
        body = json.loads((run_demo.SCENARIOS['category'] / 'app-preview.json').read_text())
        assert client.post('/api/semantic/definition/preview', headers=headers, json=body).status_code == 503


@pytest.mark.parametrize('scenario,key', [('category', 'staged'), ('hunger', 'configured_model')])
def test_scripted_provider_is_labelled_and_serves_the_exact_bundled_request(scenario, key):
    app, _, summary, _ = run_demo.build_app(options(provider='scripted', scenario=scenario))
    assert summary['identity']['live_model'] is False
    with TestClient(app) as client:
        status = client.get('/api/status').json()
        assert status['provider'] == {'backend': 'scripted-authored-replies',
                                      'model': 'none (replies written by hand)', 'live_model': False}
        body = json.loads((run_demo.SCENARIOS[scenario] / 'app-preview.json').read_text())
        assert status['scenario_requests'][key] == body.get('objective', body.get('text'))
        headers = session(client)
        before = client.get('/api/semantic/groups?user_id=1', headers=headers).json()
        if scenario == 'category':
            definition = client.post('/api/semantic/definition/preview', headers=headers, json=body).json()
            assert definition['definition_ready'], definition
            review = client.post('/api/semantic/definition/classify', headers=headers, json={
                'user_id': 1, 'plan_id': definition['definition_plan_id'], 'evidence_reviewed': True}).json()
        else:
            review = client.post('/api/semantic/preview', headers=headers, json=body).json()
        assert review['ready'] and review['applied'] is False and review['history_action'] == 'none'
        assert [row['item_id'] for row in review['scope_items']] == sorted(body['candidate_ids'])
        assert all(row['source_text'] for row in review['scope_items'])
        assert client.get('/api/semantic/groups?user_id=1', headers=headers).json()['feed'] == before['feed']
        applied = client.post('/api/semantic/apply', headers=headers, json={'user_id': 1, 'plan_id': review['plan_id']}).json()
        assert applied['feed']['available_items'] == 5
        undo = client.post('/api/semantic/history/preview', headers=headers, json={'user_id': 1, 'action': 'undo'}).json()
        assert undo['history_action'] == 'undo'
        restored = client.post('/api/semantic/apply', headers=headers, json={'user_id': 1, 'plan_id': undo['plan_id']}).json()
        assert restored['feed'] == before['feed'] and restored['groups'] == []


def test_scripted_provider_refuses_any_other_request():
    app, _, _, _ = run_demo.build_app(options(provider='scripted', scenario='category'))
    with TestClient(app) as client:
        headers = session(client)
        body = json.loads((run_demo.SCENARIOS['category'] / 'app-preview.json').read_text())
        body['objective'] += ' Please.'
        reply = client.post('/api/semantic/definition/preview', headers=headers, json=body).json()
        assert reply['definition_ready'] is False and reply['status'] == 'error'


def test_relay_needs_its_declarations():
    with pytest.raises(SystemExit, match='relay needs'):
        run_demo.build_app(options(provider='relay', scenario='category'))


# ---------------------------------------------------------------- personal-cli

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@pytest.fixture
def personal(tmp_path, monkeypatch):
    """A reviewed-configuration double and an authored runner. Nothing is launched."""
    import feedctrl.windows_job_runner as runner_module
    # Test-only current contract. Historical production inputs and driver stay frozen.
    fixture = ROOT / 'tests' / 'fixtures' / 'personal_cli_current'
    inputs = tmp_path / 'current-test-inputs'
    shutil.copytree(run_demo.INPUTS, inputs)
    for relative in ('MANIFEST.json', '01-category-discovery/first-model-input.json'):
        shutil.copyfile(fixture / relative, inputs / relative)
    # Git checkouts may use CRLF; canonicalize only the temporary test copy.
    for path in inputs.rglob('*'):
        if path.is_file():
            path.write_bytes(path.read_bytes().replace(b'\r\n', b'\n'))
    test_pin = '7273bdc69e1390be6c9d265314998c2483d5c6eaef298a48f7c330afca205626'
    assert sha(inputs / 'MANIFEST.json') == test_pin
    monkeypatch.setattr(run_demo, 'INPUTS', inputs)
    original_util = run_demo.importlib.util

    def test_spec(name, path):
        spec = original_util.spec_from_file_location(name, path)
        original_loader = spec.loader

        class TestPinLoader:
            def create_module(self, spec):
                return original_loader.create_module(spec)

            def exec_module(self, module):
                original_loader.exec_module(module)
                module.INPUT_MANIFEST_SHA256 = test_pin

        spec.loader = TestPinLoader()
        return spec

    # Patch only run_demo's reference, not the shared importlib module.
    monkeypatch.setattr(run_demo, 'importlib', SimpleNamespace(util=SimpleNamespace(
        spec_from_file_location=test_spec,
        module_from_spec=original_util.module_from_spec)))
    calls = []

    def authored_runner(argv, data, env, cwd, timeout, maximum):
        system = argv[argv.index('--system-prompt') + 1]
        schema = json.loads(system.split('Schema: ', 1)[1])
        reply = demo_scripted_replies.lookup(json.loads(data), schema)
        calls.append(sorted(schema['required']))
        envelope = {'type': 'result', 'subtype': 'success', 'is_error': False, 'num_turns': 1,
                    'result': json.dumps(reply), 'usage': {'input_tokens': 1, 'output_tokens': 4},
                    'modelUsage': {MODEL: {'outputTokens': 4}}, 'total_cost_usd': 0.01}
        return 0, json.dumps(envelope).encode()

    monkeypatch.setattr(runner_module, 'run_windows_job', authored_runner)
    monkeypatch.setattr(run_demo, 'require_free_port', lambda port: None)

    def make(scenario='category', name='config.json'):
        template = 'reviewed-config.TEMPLATE.json' if scenario == 'category' else 'reviewed-indirect-config.TEMPLATE.json'
        config = json.loads((ROOT / 'tools' / 'hosted_validation_current' / template).read_text())
        config['input_manifest_sha256'] = test_pin
        config['driver_sha256'] = sha(ROOT / 'tools' / 'hosted_validation_current' / 'driver.py')
        config['source_sha256'] = {p.relative_to(ROOT).as_posix(): sha(p)
                                   for p in (ROOT / 'feedctrl').glob('*.py')}
        executable = tmp_path / 'not-a-program.bin'
        executable.write_bytes(b'not a program')
        workdir = tmp_path / 'work'
        workdir.mkdir(exist_ok=True)
        config.update(executable=str(executable), executable_sha256=sha(executable), workdir=str(workdir),
                      estimated_per_invocation_usd=0.1, operator_token=TOKEN,
                      reviewer_reference='offline test double, not a review')
        for gate in ('runtime_authorized', 'data_authorized', 'subscription_and_usage_authorized',
                     'executable_reviewed', 'managed_runtime_reviewed', 'process_containment_reviewed'):
            config[gate] = True  # a double for the authored runner only
        for key in config['review_receipts']:
            path = tmp_path / f'receipt-{key}.json'
            path.write_text(json.dumps(config['identity_basis']) if key == 'model_identity' else '{"double": true}')
            config['review_receipts'][key] = {'path': str(path), 'sha256': sha(path)}
        path = tmp_path / name
        path.write_text(json.dumps(config))
        return path
    return make, calls, tmp_path


def personal_client(app):
    return TestClient(app, base_url='http://127.0.0.1:8765', client=('127.0.0.1', 50000))


def test_scoped_configuration_pins_current_source_and_test_inputs(personal):
    make, _, tmp = personal
    run_demo.build_app(options(provider='personal-cli', reviewed_config=str(make()), report=str(tmp / 'r.json')))


def test_personal_cli_served_flow_token_boundary_and_final_report(personal):
    make, calls, tmp = personal
    config, report_path = make(), tmp / 'report.json'
    app, port, summary, finish = run_demo.build_app(options(
        provider='personal-cli', reviewed_config=str(config), report=str(report_path)))
    assert port == 8765 and summary['scenario'] == 'category' and TOKEN not in json.dumps(summary)
    assert Path(str(config) + '.consumed').exists()
    token = {'X-Personal-Operator-Token': TOKEN}
    body = json.loads((run_demo.SCENARIOS['category'] / 'app-preview.json').read_text())
    with personal_client(app) as client:
        assert client.get('/api/status').status_code == 403
        assert client.get('/api/status', headers={'X-Personal-Operator-Token': 'wrong' * 8}).status_code == 403
        status = client.get('/api/status', headers=token).json()
        assert status['provider']['backend'] == 'claude-code-personal-cli' and status['provider']['model'] == MODEL
        assert status['scenario_requests'] == {'staged': body['objective']}
        headers = session(client, token)
        before = client.get('/api/semantic/groups?user_id=1', headers=headers).json()
        definition = client.post('/api/semantic/definition/preview', headers=headers, json=body).json()
        review = client.post('/api/semantic/definition/classify', headers=headers, json={
            'user_id': 1, 'plan_id': definition['definition_plan_id'], 'evidence_reviewed': True}).json()
        assert review['ready'] and len(calls) == 3
        applied = client.post('/api/semantic/apply', headers=headers, json={'user_id': 1, 'plan_id': review['plan_id']}).json()
        assert applied['feed']['available_items'] == 5
        undo = client.post('/api/semantic/history/preview', headers=headers, json={'user_id': 1, 'action': 'undo'}).json()
        restored = client.post('/api/semantic/apply', headers=headers, json={'user_id': 1, 'plan_id': undo['plan_id']}).json()
        assert restored['feed'] == before['feed']
    finish()
    text = report_path.read_text()
    report = json.loads(text)
    assert TOKEN not in text and str(tmp) not in text
    assert report['status'] == 'server_stopped' and report['attempted'] == 3
    assert [r['outcome'] for r in report['receipts']] == ['parsed_transport_only'] * 3
    assert all('response_sha256' in r and r['reported_model'] == MODEL for r in report['receipts'])
    assert report['mechanics'] == {'recorded_here': False, 'note': report['steps']}
    assert len(report['model_inputs']) == 3 and report['model_inputs'][0]['status'] == 'runner_returned'


def test_personal_cli_refuses_a_used_configuration_a_wrong_scenario_and_another_port(personal):
    make, _, tmp = personal
    config = make()
    with pytest.raises(SystemExit, match='always serves on port 8765'):
        run_demo.build_app(options(provider='personal-cli', reviewed_config=str(config), report=str(tmp / 'a.json'), port=9999))
    with pytest.raises(SystemExit, match='does not match the reviewed configuration'):
        run_demo.build_app(options(provider='personal-cli', reviewed_config=str(config), report=str(tmp / 'a.json'), scenario='hunger'))
    assert not Path(str(config) + '.consumed').exists()  # neither refusal spent the configuration
    run_demo.build_app(options(provider='personal-cli', reviewed_config=str(config), report=str(tmp / 'a.json')))
    with pytest.raises(FileExistsError):
        run_demo.build_app(options(provider='personal-cli', reviewed_config=str(config), report=str(tmp / 'b.json')))


def test_personal_cli_busy_port_does_not_spend_the_configuration(personal, monkeypatch):
    make, _, tmp = personal
    config = make()

    def busy(port):
        raise SystemExit('Port 8765 on 127.0.0.1 is in use; stop the other server first')
    monkeypatch.setattr(run_demo, 'require_free_port', busy)
    with pytest.raises(SystemExit, match='in use'):
        run_demo.build_app(options(provider='personal-cli', reviewed_config=str(config), report=str(tmp / 'a.json')))
    assert not Path(str(config) + '.consumed').exists() and not (tmp / 'a.json').exists()


def test_personal_cli_indirect_scenario_serves_the_hunger_fixture(personal):
    make, calls, tmp = personal
    app, _, summary, finish = run_demo.build_app(options(
        provider='personal-cli', reviewed_config=str(make('indirect')), report=str(tmp / 'i.json')))
    assert summary['scenario'] == 'hunger' and summary['max_calls'] == 2
    token = {'X-Personal-Operator-Token': TOKEN}
    body = json.loads((run_demo.SCENARIOS['hunger'] / 'app-preview.json').read_text())
    with personal_client(app) as client:
        headers = session(client, token)
        review = client.post('/api/semantic/preview', headers=headers, json=body).json()
        assert review['ready'] and len(calls) == 2
        assert review['groups'][0]['proposal']['item_ids'] == [81001, 81003, 81006]
    finish()
    assert json.loads((tmp / 'i.json').read_text())['attempted'] == 2


def test_source_fingerprint_is_stable_and_changes_with_served_source(tmp_path):
    first = run_demo.source_fingerprint()
    assert len(first) == 64 and first == run_demo.source_fingerprint()
    copy = tmp_path / 'copy'
    for folder in ('feedctrl', 'web/dist', 'tools/hosted_validation_current/inputs'):
        shutil.copytree(ROOT / folder, copy / folder)
    (copy / 'scripts').mkdir()
    for name in ('run_demo.py', 'demo_scripted_replies.py'):
        shutil.copy(ROOT / 'scripts' / name, copy / 'scripts' / name)
    assert run_demo.source_fingerprint(copy) == first
    with open(copy / 'feedctrl' / 'staged_routes.py', 'ab') as handle:
        handle.write(b'\n# changed\n')
    assert run_demo.source_fingerprint(copy) != first


def test_source_fingerprint_is_the_same_on_every_operating_system(tmp_path):
    """The order and the line-ending rule are fixed here, not left to the platform.

    Windows compares paths without case, so REVIEW-NOTES.md would sort after
    app-data.json there if the order came from the paths themselves.
    """
    import hashlib
    inputs = 'tools/hosted_validation_current/inputs'
    content = {
        'feedctrl/a.py': b'x = 1\ny = 2\n',
        'scripts/demo_scripted_replies.py': b'TABLE = {}\n',
        'scripts/run_demo.py': b'print(1)\n',
        f'{inputs}/REVIEW-NOTES.md': b'notes\n',
        f'{inputs}/app-data.json': b'{}\n',
        'web/dist/index.html': b'<html>\n</html>\n',
    }
    for name, data in content.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_bytes(data)
    expected = hashlib.sha256()
    for name in ('feedctrl/a.py', 'scripts/demo_scripted_replies.py', 'scripts/run_demo.py',
                 f'{inputs}/REVIEW-NOTES.md', f'{inputs}/app-data.json', 'web/dist/index.html'):
        expected.update(name.encode('utf-8') + b'\0')
        expected.update(hashlib.sha256(content[name]).digest())
    assert run_demo.source_fingerprint(tmp_path) == expected.hexdigest()
    # A Windows checkout can give Python files CRLF line endings: the value stays the same.
    (tmp_path / 'feedctrl/a.py').write_bytes(b'x = 1\r\ny = 2\r\n')
    assert run_demo.source_fingerprint(tmp_path) == expected.hexdigest()
    # Every other file counts as bytes on disk.
    (tmp_path / 'web/dist/index.html').write_bytes(b'<html>\r\n</html>\r\n')
    assert run_demo.source_fingerprint(tmp_path) != expected.hexdigest()


def test_status_reports_the_fingerprint_only_when_the_launcher_sets_it():
    app, _, _, _ = run_demo.build_app(options(provider='scripted', scenario='category'))
    with TestClient(app) as client:
        assert client.get('/api/status').json()['source_fingerprint'] is None
        app.state.source_fingerprint = 'a' * 64
        assert client.get('/api/status').json()['source_fingerprint'] == 'a' * 64
        app.state.source_fingerprint = '<script>'
        assert client.get('/api/status').json()['source_fingerprint'] is None

@pytest.mark.parametrize('field', ['system', 'objective'])
def test_offline_input_drift_stops_before_authored_runner(personal, field):
    make, calls, tmp = personal
    path = run_demo.INPUTS / '01-category-discovery' / 'first-model-input.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    data['payload'][field] = str(data['payload'].get(field, '')) + ' changed'
    path.write_text(json.dumps(data), encoding='utf-8')
    with pytest.raises(ValueError, match='Input drift'):
        run_demo.build_app(options(provider='personal-cli', reviewed_config=str(make()),
                                   report=str(tmp / 'drift-report.json')))
    assert calls == []


def test_production_driver_and_frozen_input_pin_are_unchanged():
    import importlib.util
    path = ROOT / 'tools' / 'hosted_validation_current' / 'driver.py'
    spec = importlib.util.spec_from_file_location('unmodified_production_driver', path)
    driver = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(driver)
    original = 'e4e36c14e3947324e1f34458f49df432130c7b5904aefda672953daabbb91655'
    assert driver.INPUT_MANIFEST_SHA256 == original
    manifest = ROOT / 'tools' / 'hosted_validation_current' / 'inputs' / 'MANIFEST.json'
    assert hashlib.sha256(manifest.read_bytes().replace(b'\r\n', b'\n')).hexdigest() == original
