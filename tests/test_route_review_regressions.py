"""Offline adversarial route regressions. No real provider or CLI."""
import argparse
import signal
import sys
import threading
import time
from pathlib import Path
import pytest
from feedctrl import model_routes as routes, route_cli

@pytest.fixture(autouse=True)
def clear_stop():
    routes.reset_stop()
    yield
    routes.reset_stop()

@pytest.mark.parametrize('base', ['https://other.example/v1', 'http://127.0.0.1:9999/v1'])
def test_foreign_host_cannot_inherit_provider_key(base):
    with pytest.raises(routes.RouteError, match='another host'):
        routes.validate_config({'route': 'openai-compatible', 'preset': 'openai', 'base_url': base, 'model': 'm'})

@pytest.mark.parametrize('requested,reported', [('claude-opus-5','claude-opus-5-5'), ('gpt-5','gpt-5-1-2025-11-13')])
def test_different_versions_are_not_snapshots(requested, reported):
    assert not routes.model_matches(requested, reported)
    assert routes.model_matches(requested, requested + '-2026-01-01')

def test_cli_fallback_does_not_claim_requested_model():
    _, model, _, problem = route_cli._answer_model(
        {'modelUsage': {'requested': {'outputTokens': 3}, 'fallback': {'outputTokens': 1300}}}, {'model': 'requested'})
    assert model is None and problem

@pytest.mark.parametrize('argument', ['--api-key=sk-proj-123456789ABCDEF', '--token', '--settings'])
def test_claude_credential_or_settings_arguments_rejected(argument):
    with pytest.raises(routes.RouteError):
        routes.validate_config({'route': 'cli', 'profile': 'claude-code', 'model': 'm', 'extra_args': [argument]})

def test_nested_credential_json_rejected():
    with pytest.raises(routes.RouteError):
        routes.validate_config({'route': 'openai-compatible', 'base_url': 'http://127.0.0.1:9999/v1', 'model': 'm',
                                'extra_body': {'comment': '{"env":{"ANTHROPIC_API_KEY":"ordinary-secret"}}'}})

def test_stop_ends_owned_cli_and_rejects_new_calls(tmp_path):
    outcome = []
    def run():
        try:
            route_cli.run_program([sys.executable, '-c', 'import time; time.sleep(30)'], b'', {}, str(tmp_path), 60, 1000)
        except routes.RouteError as exc:
            outcome.append(exc.category)
    worker = threading.Thread(target=run)
    worker.start()
    time.sleep(.2)
    routes.request_stop()
    worker.join(5)
    assert not worker.is_alive() and outcome == ['stopped']
    infer, _, _ = routes.build_route({'route': 'cli', 'profile': 'generic', 'model': 'm',
                                     'argv': [sys.executable, '-c', 'raise AssertionError("must not execute")']})
    with pytest.raises(routes.RouteError) as caught:
        infer(routes.TEST_PAYLOAD, routes.TEST_SCHEMA)
    assert caught.value.category == 'stopped'

def test_demo_signal_sets_stop_before_server_drain(monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
    import run_demo
    import uvicorn
    class App:
        state = argparse.Namespace()
    seen = []
    monkeypatch.setattr(run_demo, 'require_built_interface', lambda: None)
    monkeypatch.setattr(run_demo, 'source_fingerprint', lambda: 'offline')
    monkeypatch.setattr(run_demo, 'build_app', lambda args: (App(), 8765, {}, lambda: seen.append('finished')))
    def handle_exit(self, sig, frame):
        assert routes.stop_requested()
        seen.append('signal')
    monkeypatch.setattr(uvicorn.Server, 'handle_exit', handle_exit)
    monkeypatch.setattr(uvicorn.Server, 'run', lambda self: self.handle_exit(signal.SIGTERM, None))
    run_demo.main(['--provider', 'manual', '--scenario', 'category'])
    assert seen == ['signal', 'finished']


def test_receipt_mapping_keys_are_scrubbed():
    key = 'regression-secret-42'
    routes.remember_secret(key)
    assert key not in str(routes.scrub_value({'usage': {key: {'tokens': 1}}}))


def test_quickstart_resolves_user_paths_before_child_changes_directory(tmp_path, monkeypatch):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
    import quickstart
    routes.save_config(tmp_path / 'chosen.json', {'route': 'relay', 'declared_model': 'model', 'transport_note': 'manual'})
    monkeypatch.chdir(tmp_path)
    seen = {}
    class Server:
        returncode = 0
        def poll(self):
            return self.returncode
    monkeypatch.setattr(quickstart, 'run_demo', lambda *args, **kw: seen.update(args=args) or Server())
    monkeypatch.setattr(quickstart, 'require_free_port', lambda port: None)
    monkeypatch.setattr(quickstart, 'wait_until_served', lambda *a: None)
    monkeypatch.setattr(quickstart, 'keep_serving', lambda *a: None)
    quickstart.main(['start', '--scenario', 'category', '--route-file', 'chosen.json', '--record-dir', 'records'])
    args = seen['args']
    assert args[args.index('--route-file') + 1] == str(tmp_path / 'chosen.json')
    assert args[args.index('--record-dir') + 1] == str(tmp_path / 'records')
