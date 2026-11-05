"""Reviewed nonliteral sets: mocked inference is contract evidence, not accuracy."""
from copy import deepcopy
import csv
import pytest
from fastapi.testclient import TestClient
from feedctrl.api import create_app
from feedctrl import semantic_review as sr
from feedctrl.semantic_controls import TEXT_FIELDS


@pytest.fixture
def client(tmp_path):
    path = tmp_path / 'source.csv'
    with path.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['video_id', *TEXT_FIELDS])
        writer.writeheader()
        for i in range(1, 37):
            writer.writerow({'video_id': i, 'caption': 'Freshly baked bread' if i in (3, 4) else 'Bicycle commuting'})
    with TestClient(create_app(fixture=True, semantic_path=path)) as c:
        yield c


def headers(c):
    return {'X-Session-ID': c.post('/api/session', json={}).json()['session_id']}


def fake_model(monkeypatch, operation='exclude', strength='none', hook=None):
    def infer(payload, schema):
        if schema is sr.ACTION_SCHEMA or 'needs_clarification' in schema['required']:
            return {'needs_clarification': False, 'question': '', 'control': f'{operation}/{strength}',
                'intent_span': 'makes me hungry'}
        if hook:
            hook()
        return {'status': 'propose', 'reason': 'Bread may stimulate appetite; synthetic mock output',
            'negation_resolved': True, 'alternatives': [],
            'evidence': [{'item_id': 3, 'field': 'caption', 'quote': 'Freshly baked bread'}]}
    monkeypatch.setattr(sr, 'make_local_ollama_infer', lambda *a, **kw:
        (infer, {'backend': 'test-double', 'model': 'mock', 'digest': 'not-live'}))


def preview(c, h, **kw):
    return c.post('/api/semantic/preview', headers=h, json={'user_id': 1,
        'text': 'Hide what makes me hungry', 'label': 'Appetite cues',
        'candidate_ids': list(range(1, 9)), **kw})


def apply(c, h, p, user=1):
    return c.post('/api/semantic/apply', headers=h, json={'user_id': user, 'plan_id': p['plan_id']})


def saved(c, h, user=1):
    return c.get(f'/api/semantic/groups?user_id={user}', headers=h)


def test_nonliteral_proposal_review_apply_and_ae_isolation(client, monkeypatch):
    h = headers(client)
    before = client.get('/api/compare?user_id=1', headers=h).json()
    fake_model(monkeypatch)
    p = preview(client, h).json()
    assert p['ready'] and p['applied'] is False
    assert saved(client, h).json()['groups'] == []
    assert p['groups'][0]['proposal']['item_ids'] == [3]
    result = apply(client, h, p).json()
    assert result['applied'] and result['feed']['available_items'] == 35
    assert 3 not in [x['item_id'] for x in result['feed']['items']]
    assert client.get('/api/compare?user_id=1', headers=h).json() == before
    assert client.get('/api/steering?user_id=1', headers=h).json()['commands'] == []


def test_manual_category_uses_same_enforcement_without_model(client, monkeypatch):
    h = headers(client)
    def forbidden(*a, **kw):
        raise AssertionError('No model in manual baseline')
    monkeypatch.setattr(sr, 'make_local_ollama_infer', forbidden)
    p = preview(client, h, backend='manual_category', category='category_3',
        operation='exclude', strength='none').json()
    assert p['ready'] and p['groups'][0]['proposal']['item_ids'] == [3]
    assert apply(client, h, p).json()['feed']['available_items'] == 35


@pytest.mark.parametrize('change', ['text', 'source', 'candidates', 'action', 'membership'])
def test_apply_revalidates_authoritative_source_and_sealed_records(client, monkeypatch, change):
    h = headers(client); fake_model(monkeypatch)
    p = preview(client, h).json()
    demo = client.app.state.demo
    state = demo.user_state(h['X-Session-ID'], 1)
    if change == 'text':
        demo.topic_index['items'][3]['fields']['caption'] = 'Changed source text'
    elif change == 'source':
        demo.topic_index['sha256'] = '0' * 64
    elif change == 'candidates':
        demo.items.pop(36)
    elif change == 'action':
        state['semantic_pending']['groups'][0]['proposal']['action']['operation'] = 'boost'
    else:
        state['semantic_pending']['groups'][0]['proposal']['item_ids'] = [999]
    assert apply(client, h, p).status_code == 409
    assert state['semantic_groups'] == [] and state['semantic_history'] == []


def test_review_tokens_expire_supersede_and_bind_session_user(client, monkeypatch):
    h, other = headers(client), headers(client); fake_model(monkeypatch)
    p = preview(client, h).json()
    assert apply(client, other, p).status_code == 409
    assert apply(client, h, p, user=2).status_code == 409
    newer = preview(client, h).json()
    assert apply(client, h, p).status_code == 409
    client.app.state.demo.user_state(h['X-Session-ID'], 1)['semantic_pending']['created'] -= 301
    assert apply(client, h, newer).status_code == 409


def test_undo_clear_replace_and_global_reset_are_reviewed(client, monkeypatch):
    h = headers(client); fake_model(monkeypatch)
    first = apply(client, h, preview(client, h).json()).json()
    second = apply(client, h, preview(client, h, label='Different name', mode='replace').json()).json()
    assert [g['label'] for g in second['groups']] == ['Different name']
    p = client.post('/api/semantic/history/preview', headers=h, json={'user_id': 1, 'action': 'undo'}).json()
    assert saved(client, h).json()['groups'] == second['groups']
    assert apply(client, h, p).json()['groups'] == first['groups']
    p = client.post('/api/semantic/history/preview', headers=h, json={'user_id': 1, 'action': 'clear'}).json()
    assert apply(client, h, p).json()['groups'] == []
    p = preview(client, h).json()
    client.post('/api/reset', headers=h, json={'user_id': 1})
    assert apply(client, h, p).status_code == 409
    assert saved(client, h).json()['groups'] == []


def test_inference_race_does_not_overwrite_a_newer_review(client, monkeypatch):
    h = headers(client)
    fake_model(monkeypatch, hook=lambda: client.post('/api/semantic/history/preview',
        headers=h, json={'user_id': 1, 'action': 'clear'}))
    assert preview(client, h).status_code == 409
    assert saved(client, h).json()['groups'] == []


def test_no_match_invalid_model_and_oversize_never_apply(client, monkeypatch):
    h = headers(client)
    for kind in ['no_match', 'invalid', 'oversized']:
        def infer(payload, schema):
            if 'needs_clarification' in schema['required']:
                return {'needs_clarification': False, 'question': '', 'control': 'exclude/none',
                    'intent_span': 'makes me hungry'}
            return {'status': 'no_match', 'reason': 'No evidence', 'negation_resolved': True,
                'alternatives': [], 'evidence': []} if kind == 'no_match' else {'bad': 'schema'}
        monkeypatch.setattr(sr, 'make_local_ollama_infer', lambda *a, **kw:
            (infer, {'backend': 'test', 'model': 'mock', 'digest': 'mock'}))
        if kind == 'oversized':
            client.app.state.demo.topic_index['items'][3]['fields']['caption'] = 'x' * 20000
        p = preview(client, h).json()
        assert not p['ready'] and p['applied'] is False
        assert saved(client, h).json()['groups'] == []


def test_candidate_and_model_action_types_are_strict(client):
    h = headers(client)
    assert preview(client, h, candidate_ids=[True, 2]).status_code == 422
    assert preview(client, h, candidate_ids=[1, 1]).status_code == 422
    assert preview(client, h, candidate_ids=[1, 999]).status_code == 422
    for bad in [[], {}, 'missing']:
        with pytest.raises(ValueError):
            sr.interpret_action('Hide food', lambda *a: {'needs_clarification': False, 'question': '',
                'control': bad, 'intent_span': 'food'})


def test_explicit_manual_action_ablation_never_calls_the_action_parser(client, monkeypatch):
    h = headers(client); fake_model(monkeypatch)
    def forbidden(*a):
        raise AssertionError('Explicit manual action must not be reported as model-parsed')
    monkeypatch.setattr(sr, 'interpret_action', forbidden)
    p = preview(client, h, action_source='manual', operation='exclude', strength='none').json()
    assert p['ready'] and len(p['model_calls']) == 1
    assert p['proposal']['action_source'] == 'manual'
    assert p['proposal']['action']['operation'] == 'exclude'


def test_invalid_model_action_retains_its_raw_response_without_applying(client, monkeypatch):
    h = headers(client)
    raw = {'needs_clarification': False, 'question': '', 'control': 'exclude/none',
           'intent_span': 'invented subject absent from request'}
    monkeypatch.setattr(sr, 'make_local_ollama_infer', lambda *a, **kw:
        (lambda *a: deepcopy(raw), {'backend': 'test', 'model': 'mock', 'digest': 'mock'}))
    p = preview(client, h).json()
    assert not p['ready'] and p['status'] == 'error' and not p['applied']
    assert p['model_calls'][0]['raw_response'] == raw
    assert saved(client, h).json()['groups'] == []


def test_overlap_exclusion_wins_and_numeric_ties(client):
    h = headers(client)
    boost = preview(client, h, backend='manual_category', category='category_3', strength='strong').json()
    apply(client, h, boost)
    p = preview(client, h, backend='manual_category', category='category_3', operation='exclude',
        strength='none', label='Exclude same').json()
    assert p['feed']['available_items'] == 35
    assert 3 not in [x['item_id'] for x in p['feed']['items']]
    index = client.app.state.demo.topic_index
    assert [x['item_id'] for x in sr.rank_groups([10, 2, 3], [0, 0, 0], [], index)['items']] == [2, 3, 10]
