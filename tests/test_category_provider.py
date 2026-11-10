"""Synthetic injection contracts, not live transport/model or semantic evidence."""
from copy import deepcopy
import csv
import socket
import pytest
from fastapi.testclient import TestClient
from feedctrl.api import create_app
from feedctrl.category_provider import CategoryProvider
from feedctrl.controls import ParserOperationalError
from feedctrl.semantic_controls import TEXT_FIELDS
from test_semantic_review import headers, apply, saved
from test_staged_induction import definition, memberships, preview, classify
from test_induction_integration import raw, preview as combined_preview

IDENTITY = {'backend': 'synthetic-callable', 'model_id': 'fixture', 'model_revision': 'synthetic-v1'}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Network prohibited in synthetic provider tests')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)


class Fake:
    def __init__(self):
        self.identity = deepcopy(IDENTITY)
        self.created = 0
        self.calls = []
        self.fail = False

    def factory(self):
        self.created += 1
        return self.infer, self.identity

    def infer(self, payload, schema):
        keys = schema['required']
        stage = ('evidence_audit' if 'assessments' in keys else 'membership' if keys == ['memberships']
                 else 'definition' if 'evidence' in keys else 'combined')
        self.calls.append(stage)
        if self.fail:
            raise RuntimeError('Synthetic failure')
        if stage == 'definition': return definition(payload)
        if stage == 'membership': return memberships(payload)
        if stage == 'combined': return raw(payload)
        return {'assessments': [{'item_id': r['item_id'],
            'assessment': 'supported' if r['item_id'] in (3, 4) else 'contradicted',
            'field': 'caption', 'quote': r['fields']['caption'], 'reason': 'Synthetic audit.'}
            for r in payload['catalogue']]}


@pytest.fixture
def injected(tmp_path):
    path = tmp_path / 'synthetic.csv'
    with path.open('w', newline='', encoding='utf8') as handle:
        writer = csv.DictWriter(handle, fieldnames=['video_id', *TEXT_FIELDS]); writer.writeheader()
        for i in range(1, 37):
            writer.writerow({'video_id': i, 'caption': 'Freshly baked bread' if i in (3, 4) else 'Bicycle commuting'})
    fake = Fake()
    with TestClient(create_app(fixture=True, semantic_path=path, category_infer_factory=fake.factory)) as client:
        yield client, fake


def test_staged_injection_review_apply_lifecycle(injected):
    c, fake = injected; h = headers(c)
    original = saved(c, h).json()['feed']
    p = preview(c, h).json()
    assert p['definition_ready'] and not p['applied'] and fake.calls == ['definition']
    assert not saved(c, h).json()['groups']
    rejected = classify(c, h, p, evidence_reviewed=False)
    assert rejected.status_code == 422 and fake.calls == ['definition']
    m = classify(c, h, p).json()
    assert m['ready'] and not m['applied'] and fake.created == 1
    assert fake.calls == ['definition', 'membership', 'evidence_audit']
    assert not saved(c, h).json()['groups']
    receipts = (p['model_calls'] + m['model_calls'] + m['evidence_audit_model_calls'])
    assert [x['stage'] for x in receipts] == fake.calls
    assert all(x['model_provenance'] == IDENTITY and 'raw_response' in x and 'raw_http_response' not in x for x in receipts)
    assert apply(c, h, m).json()['feed']['available_items'] == 34
    assert classify(c, h, p).status_code == 409
    undo = c.post('/api/semantic/history/preview', headers=h, json={'user_id': 1, 'action': 'undo'}).json()
    assert apply(c, h, undo).json()['feed'] == original
    assert fake.calls == ['definition', 'membership', 'evidence_audit']


def test_combined_injection_cached_and_unapplied(injected):
    c, fake = injected; h = headers(c)
    for _ in range(2):
        p = combined_preview(c, h).json()
        assert p['ready'] and not p['applied']
        assert p['model_calls'][0]['stage'] == 'combined'
    assert fake.created == 1 and fake.calls == ['combined', 'combined']
    assert not saved(c, h).json()['groups']


@pytest.mark.parametrize('change', ['identity', 'source', 'expired'])
def test_staged_changes_fail_before_further_invocation(injected, change):
    c, fake = injected; h = headers(c); p = preview(c, h).json()
    if change == 'identity': fake.identity['model_revision'] = 'changed'
    elif change == 'source': c.app.state.demo.topic_index['items'][3]['fields']['caption'] = 'changed'
    else: c.app.state.demo.user_state(h['X-Session-ID'], 1)['semantic_definition_pending']['created'] -= 301
    result = classify(c, h, p)
    assert result.status_code == 409 or result.json()['ready'] is False
    assert fake.calls == ['definition'] and not saved(c, h).json()['groups']


def test_errors_do_not_apply_retry_or_fallback(injected):
    c, fake = injected; h = headers(c); fake.fail = True
    p = preview(c, h).json()
    assert not p['definition_ready'] and not p['applied']
    assert p['model_calls'][0]['status'] == 'error'
    assert fake.calls == ['definition'] and fake.created == 1
    assert not saved(c, h).json()['groups']


@pytest.mark.parametrize('result', [None, (), (None, IDENTITY), (lambda p,s: {}, {}),
    (lambda p,s: {}, {**IDENTITY, 'extra': 'x'}), (lambda p,s: {}, {**IDENTITY, 'backend': ''})])
def test_bad_factory_fail_closed_once(result):
    count = []
    def factory(): count.append(1); return result
    provider = CategoryProvider(factory)
    for _ in range(2):
        with pytest.raises(ValueError): provider.stage('definition', 'unused')
    assert len(count) == 1


def test_one_invocation_receipt_snapshot_and_identity_checks():
    identity = deepcopy(IDENTITY); output = {'x': [1]}; count = []
    def infer(p, s): count.append(1); return output
    provider = CategoryProvider(lambda: (infer, identity))
    fn, model, calls = provider.stage('definition', 'unused')
    model['model_id'] = 'caller mutation'
    result = fn({'instructions': 'synthetic'}, {'type': 'object'})
    result['x'].append(2); output['x'].append(3)
    assert calls[0]['raw_response'] == {'x': [1]}
    with pytest.raises(ValueError): fn({}, {})
    assert len(count) == 1
    with pytest.raises(ValueError): provider.stage('membership', 'unused', expected={**IDENTITY, 'backend': 'other'})
    identity['model_revision'] = 'changed'
    with pytest.raises(ValueError): provider.stage('membership', 'unused')


def test_identity_mutation_during_call_records_rejected_raw():
    identity = deepcopy(IDENTITY)
    def infer(p, s): identity['model_revision'] = 'changed'; return {'x': 1}
    fn, model, calls = CategoryProvider(lambda: (infer, identity)).stage('definition', 'unused')
    with pytest.raises(ValueError): fn({}, {})
    assert calls[0]['status'] == 'error' and calls[0]['raw_response'] == {'x': 1}


def test_invalid_raw_is_rejected_without_retry():
    fn, model, calls = CategoryProvider(lambda: (lambda p,s: float('nan'), deepcopy(IDENTITY))).stage('definition', 'unused')
    with pytest.raises(ValueError): fn({}, {})
    assert calls[0]['status'] == 'error'
    with pytest.raises(ValueError): fn({}, {})
    assert len(calls) == 1
