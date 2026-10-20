import json

import pytest
from fastapi.testclient import TestClient

from feedctrl.api import create_app


@pytest.fixture
def client():
    with TestClient(create_app(fixture=True)) as client:
        yield client


def session(client):
    r = client.post('/api/session', json={})
    assert r.status_code == 201
    return {'X-Session-ID': r.json()['session_id']}


def feed(client, headers, condition='E', user=1):
    r = client.get(f'/api/feed?user_id={user}&condition={condition}', headers=headers)
    assert r.status_code == 200, r.text
    return r.json()


def test_status_explicit_fixture_and_rule(client):
    s = client.get('/api/status').json()
    assert s['data_mode'] == 'fixture'
    assert 'diagnostic' in s['model_mode']
    assert s['default_parser'] == 'rule'
    assert 'no original video' in s['asset_note']


def test_missing_and_unknown_sessions_rejected(client):
    assert client.get('/api/feed?user_id=1').status_code == 401
    assert client.get('/api/feed?user_id=1', headers={'X-Session-ID':'invented'}).status_code == 401


def test_bounds_and_unknown_ids(client):
    h = session(client)
    assert client.get('/api/feed?user_id=999', headers=h).status_code == 404
    assert client.get('/api/feed?user_id=1&limit=100', headers=h).status_code == 422
    assert client.post('/api/control', headers=h, json={'user_id':1,'text':'x'*501}).status_code == 422
    assert client.post('/api/control', headers=h, json={'user_id':1,'text':'Mute category_0','backend':'remote'}).status_code == 422
    assert client.put('/api/profile', headers=h, json={'user_id':1,'profile':{'category_0':2}}).status_code == 422
    assert client.put('/api/profile', headers=h, json={'user_id':1,'profile':{'category_999':1}}).status_code == 422
    assert client.post('/api/feedback', headers=h, json={'user_id':1,'item_id':999,'direction':'like'}).status_code == 422


def test_controls_and_profiles_are_session_and_user_isolated(client):
    a, b = session(client), session(client)
    baseline_b = feed(client, b)
    baseline_u2 = feed(client, a, user=2)
    r = client.post('/api/control', headers=a, json={'user_id':1,'text':'Mute category_0'})
    assert r.status_code == 200 and r.json()['applied']
    assert all('category_0' not in i['categories'] for i in feed(client, a)['items'])
    assert feed(client, b) == baseline_b
    assert feed(client, a, user=2) == baseline_u2


def test_ab_rank_invariance_and_explanations(client):
    h = session(client)
    result = client.get('/api/compare?user_id=1', headers=h).json()
    assert [i['item_id'] for i in result['A']['items']] == [i['item_id'] for i in result['B']['items']]
    assert all(not i['explanation'] for i in result['A']['items'])
    assert all(i['explanation'] for i in result['B']['items'])


def test_feedback_is_item_only_and_limited_to_a_b(client):
    h = session(client)
    before_c = feed(client, h, 'C')['items']
    item = feed(client, h, 'A')['items'][0]['item_id']
    assert client.post('/api/feedback', headers=h, json={'user_id':1,'item_id':item,'direction':'dislike'}).status_code == 200
    assert item not in [i['item_id'] for i in feed(client, h, 'A')['items']]
    assert item not in [i['item_id'] for i in feed(client, h, 'B')['items']]
    assert feed(client, h, 'C')['items'] == before_c


def test_natural_language_profile_and_d_condition(client):
    h = session(client)
    before_c = feed(client, h, 'C')['items']
    r = client.post('/api/profile/text', headers=h, json={'user_id':1,'text':'Show me more category_1. Mute category_0.'})
    assert r.status_code == 200 and r.json()['applied'], r.text
    f = feed(client, h, 'D')
    assert f['profile'] == {'category_1':.25,'category_0':-1}
    assert all('category_0' not in i['categories'] for i in f['items'])
    assert feed(client, h, 'C')['items'] == before_c


def test_profile_word_limit(client):
    h = session(client)
    assert client.post('/api/profile/text', headers=h, json={'user_id':1,'text':'x '*201}).status_code == 422


def test_ambiguity_preserves_previous_control(client):
    h = session(client)
    client.post('/api/control', headers=h, json={'user_id':1,'text':'Mute category_0'})
    before = feed(client,h)
    r = client.post('/api/control', headers=h, json={'user_id':1,'text':'Perhaps something interesting'})
    assert not r.json()['applied']
    assert feed(client,h) == before


def test_ollama_failure_visible_preserves_state(client, monkeypatch):
    h = session(client)
    before = feed(client,h)
    def fail(*args, **kwargs):
        raise RuntimeError('Unavailable')
    monkeypatch.setattr('feedctrl.api.parse_control', fail)
    r = client.post('/api/control', headers=h, json={'user_id':1,'text':'Mute category_0','backend':'ollama'})
    assert r.status_code == 502
    assert 'previous state is preserved' in r.json()['detail']
    assert feed(client,h) == before


def test_hard_mutes_allow_empty_feed_and_reset_restores(client):
    h = session(client)
    baseline = feed(client,h)
    cats = client.get('/api/categories').json()['categories']
    client.put('/api/profile', headers=h, json={'user_id':1,'profile':{c:-1 for c in cats}})
    assert feed(client,h)['items'] == []
    assert feed(client,h)['fill_rate'] == 0
    client.post('/api/reset', headers=h, json={'user_id':1})
    assert feed(client,h) == baseline


def test_held_out_labels_do_not_affect_api(client):
    h = session(client)
    before = feed(client,h)
    client.app.state.demo.users[1]['test'] = [999,998,997]
    assert feed(client,h) == before
    public = json.dumps(client.get('/api/users').json()) + json.dumps(feed(client,h))
    assert '999' not in public and 'test' not in public


def test_model_fixture_metadata_kind_is_recognized(tmp_path):
    from feedctrl.data import make_fixture
    p = tmp_path / 'fixture.json'
    p.write_text(json.dumps(make_fixture()))
    with TestClient(create_app(data_path=p,model_path=tmp_path/'missing')) as client:
        assert client.get('/api/status').json()['data_mode'] == 'fixture'


def test_reset_control_then_new_profile_works(client):
    h = session(client)
    client.post('/api/control', headers=h, json={'user_id':1,'text':'Reset all preferences'})
    client.put('/api/profile', headers=h, json={'user_id':1,'profile':{'category_0':-1}})
    assert all('category_0' not in i['categories'] for i in feed(client,h)['items'])


def test_profile_initial_history_is_grounded_and_text_is_preserved(client):
    h = session(client)
    initial = feed(client,h)
    assert '6 items' in initial['profile_text']
    assert not initial['profile']
    text = initial['profile_text'] + '\nMute category_0.'
    r = client.post('/api/profile/text', headers=h, json={'user_id':1,'text':text})
    assert r.status_code == 200 and r.json()['applied']
    assert feed(client,h)['profile_text'] == text
    assert feed(client,h,user=2)['profile_text'] != text
    client.post('/api/reset', headers=h, json={'user_id':1})
    assert feed(client,h)['profile_text'] == initial['profile_text']


def test_parsed_global_reset_clears_item_feedback(client):
    h=session(client)
    before=feed(client,h,'A')['items']
    item=before[0]['item_id']
    client.post('/api/feedback',headers=h,json={'user_id':1,'item_id':item,'direction':'dislike'})
    result=client.post('/api/control',headers=h,json={'user_id':1,'text':'Reset my feed'}).json()
    assert result['applied']
    assert feed(client,h,'A')['items']==before
