"""Offline checks for the local adapter's runtime/model provenance boundary."""
import json
import pytest
from feedctrl import controls
from feedctrl.indirect_grounding import make_local_ollama_infer


@pytest.mark.parametrize('case', ['success', 'wrong_model', 'changed_digest', 'incomplete'])
def test_actual_response_identity_and_digest_are_rechecked(monkeypatch, case):
    count = 0
    def provenance(*args):
        nonlocal count
        count += 1
        return {'digest': 'changed' if case == 'changed_digest' and count == 2 else 'original',
                'ollama_version': 'test-only'}
    def request(base, path, payload, timeout):
        assert base == 'http://127.0.0.1:11434' and path == '/api/chat'
        assert payload['options']['temperature'] == 0 and timeout == 12
        return {'model': 'different' if case == 'wrong_model' else 'installed:test',
                'done': case != 'incomplete', 'done_reason': 'stop',
                'message': {'content': json.dumps({'status': 'mock'})}}
    monkeypatch.setattr(controls, 'ollama_provenance', provenance)
    monkeypatch.setattr(controls, '_request', request)
    infer, p = make_local_ollama_infer('installed:test', timeout=12)
    assert p['digest'] == 'original' and p['ollama_version'] == 'test-only'
    if case == 'success':
        assert infer({'system': 'test', 'request': 'test'}, {}) == {'status': 'mock'}
        assert count == 2
    else:
        with pytest.raises(ValueError):
            infer({'system': 'test', 'request': 'test'}, {})
