"""Actual API/ranker contracts with synthetic response doubles, not model accuracy."""
from copy import deepcopy
import json
import pytest
from feedctrl import induction_integration as ii
from feedctrl import semantic_review as sr
from feedctrl.semantic_induction import rerank_membership
from test_semantic_review import client, headers, apply, saved


def raw(payload):
    return {'status': 'propose', 'label': 'Baked preparations',
        'definition': 'Videos with bread being prepared.', 'rationale': 'Synthetic response double, not live evidence.',
        'alternatives': [], 'memberships': [
            {'item_id': r['item_id'], 'verdict': 'match' if r['item_id'] in (3, 4) else 'not_match',
             'field': 'caption', 'evidence_quote': r['fields']['caption'],
             'reason': 'Bread preparation.' if r['item_id'] in (3, 4) else 'Cycling, not baking.'}
            for r in payload['catalogue']]}


def mock_model(monkeypatch, response=None, hook=None):
    calls = []
    def infer(payload, schema):
        if hook: hook()
        out = response(payload) if response else raw(payload)
        calls.append({'raw_http_response': {'model': 'mock', 'message': {'content': json.dumps(out)}}})
        return deepcopy(out)
    monkeypatch.setattr(ii, 'make_induction_infer', lambda *a, **k:
        (infer, {'backend': 'test-double', 'model_id': 'mock', 'model_revision': 'test-only'}, calls))
    return calls


def preview(c, h, **kw):
    return c.post('/api/semantic/induction/preview', headers=h, json={
        'user_id': 1, 'objective': 'Discover a useful preparation category.',
        'candidate_ids': list(range(1, 9)), 'operation': 'exclude', 'strength': 'none', **kw})


def test_generated_category_review_apply_undo_and_ae_isolation(client, monkeypatch):
    h = headers(client); mock_model(monkeypatch)
    ae = client.get('/api/compare?user_id=1', headers=h).json()
    neutral = saved(client, h).json()['feed']
    p = preview(client, h).json()
    assert p['ready'] and not p['applied'] and p['action_source'] == 'manual'
    assert saved(client, h).json()['groups'] == []
    g = p['groups'][0]
    assert g['label'] == 'Baked preparations' and g['proposal']['item_ids'] == [3, 4]
    # Coverage by the old inventory is compatible with a distinct derived set.
    inventory = g['proposal']['induction']['inventory']
    assert set().union(*(set(c['member_ids']) for c in inventory)) == set(range(1, 9))
    assert all(set(c['member_ids']) != {3, 4} for c in inventory)
    assert g['proposal']['induction']['envelope']['overlaps']
    assert len(g['proposal']['induction']['envelope']['field_evidence']) == 8
    assert g['proposal']['induction']['validated_category']['semantic_entailment_verified'] is False
    r = apply(client, h, p).json()
    assert r['applied'] and r['feed']['available_items'] == 34
    assert not {3, 4} & {x['item_id'] for x in r['feed']['items']}
    assert client.get('/api/compare?user_id=1', headers=h).json() == ae
    assert client.get('/api/steering?user_id=1', headers=h).json()['commands'] == []
    undo = client.post('/api/semantic/history/preview', headers=h, json={'user_id': 1, 'action': 'undo'}).json()
    assert saved(client, h).json()['groups']
    assert apply(client, h, undo).json()['feed'] == neutral


@pytest.mark.parametrize('operation,strength', [('boost','light'),('boost','strong'),('reduce','light'),('reduce','strong'),('exclude','none')])
def test_one_cached_score_vector_matches_explicit_membership_comparator(client, monkeypatch, operation, strength):
    h = headers(client); mock_model(monkeypatch)
    p = preview(client, h, operation=operation, strength=strength).json()
    assert p['ready']
    ids = list(range(1, 37)); scores = [float(i) for i in ids]
    grouped = sr.rank_groups(ids, scores, p['groups'], client.app.state.demo.topic_index, limit=36)
    manual = rerank_membership(ids, scores, [3, 4], operation, strength, limit=36)
    assert [(i['item_id'], i['score']) for i in grouped['items']] == [(i['item_id'], i['score']) for i in manual['items']]
    assert grouped['available_items'] == (34 if operation == 'exclude' else 36)


@pytest.mark.parametrize('mutation', ['definition','disposition','quote','members','model','objective','raw'])
def test_full_definition_disposition_and_provenance_are_sealed(client, monkeypatch, mutation):
    h = headers(client); mock_model(monkeypatch)
    p = preview(client, h).json()
    state = client.app.state.demo.user_state(h['X-Session-ID'], 1)
    control = state['semantic_pending']['groups'][0]['proposal']
    rec = control['induction']
    if mutation == 'definition': rec['envelope']['proposal']['definition'] = 'Changed meaning'
    elif mutation == 'disposition': rec['envelope']['proposal']['memberships'][0]['verdict'] = 'unknown'
    elif mutation == 'quote': rec['envelope']['field_evidence'][0]['evidence_quote'] = 'Fabricated text'
    elif mutation == 'members': control['item_ids'] = [999]
    elif mutation == 'model': rec['envelope']['provenance']['model_revision'] = 'different'
    elif mutation == 'objective': rec['objective'] = 'Different goal'
    else: rec['model_calls'][0]['raw_http_response']['message']['content'] = 'Changed raw response'
    assert apply(client, h, p).status_code == 409
    assert saved(client, h).json()['groups'] == []


@pytest.mark.parametrize('mutation', ['caption','sidecar_digest','original_inventory','eligible_ids'])
def test_current_source_and_inventory_revalidated_before_apply(client, monkeypatch, mutation):
    h = headers(client); mock_model(monkeypatch)
    p = preview(client, h).json(); demo = client.app.state.demo
    if mutation == 'caption': demo.topic_index['items'][3]['fields']['caption'] = 'Different caption'
    elif mutation == 'sidecar_digest': demo.topic_index['sha256'] = '0' * 64
    elif mutation == 'original_inventory': demo.items[3] = ['category_changed']
    else: demo.items.pop(36)
    assert apply(client, h, p).status_code == 409
    assert demo.user_state(h['X-Session-ID'], 1)['semantic_groups'] == []


def test_live_source_changes_during_inference_cannot_create_pending_review(client, monkeypatch):
    h = headers(client)
    def mutate(): client.app.state.demo.topic_index['items'][3]['fields']['caption'] = 'Changed'
    mock_model(monkeypatch, hook=mutate)
    r = preview(client, h).json()
    assert not r['ready'] and r['status'] == 'error'
    assert saved(client, h).json()['groups'] == []


def test_newer_request_invalidates_in_flight_induction(client, monkeypatch):
    h = headers(client)
    mock_model(monkeypatch, hook=lambda: client.post('/api/semantic/history/preview',headers=h,
                                                    json={'user_id': 1,'action':'clear'}))
    assert preview(client, h).status_code == 409


def test_budget_and_nonreview_outputs_do_not_apply(client, monkeypatch):
    h = headers(client)
    calls = mock_model(monkeypatch)
    client.app.state.demo.topic_index['items'][3]['fields']['caption'] = 'x' * 15000
    r = preview(client, h).json()
    assert not r['ready'] and r['status'] == 'blocked' and not calls
    client.app.state.demo.topic_index['items'][3]['fields']['caption'] = 'Freshly baked bread'
    mock_model(monkeypatch, response=lambda p: {'status':'no_match','label':'','definition':'',
        'rationale':'No supported category','alternatives':[],'memberships':[]})
    r = preview(client, h).json()
    assert not r['ready'] and r['status'] == 'no_match'
    assert saved(client, h).json()['groups'] == []


def test_client_cannot_send_an_approved_category_or_unknown_ids(client, monkeypatch):
    h = headers(client); mock_model(monkeypatch)
    assert preview(client, h, approved=True).status_code == 422
    assert preview(client, h, candidate_ids=[True,2]).status_code == 422
    assert preview(client, h, candidate_ids=[1,999]).status_code == 422
    assert preview(client, h, operation='exclude',strength='light').status_code == 422


def test_session_user_expiry_and_global_reset(client, monkeypatch):
    h, other = headers(client), headers(client); mock_model(monkeypatch)
    p = preview(client, h).json()
    assert apply(client, other, p).status_code == 409
    assert apply(client, h, p, user=2).status_code == 409
    state = client.app.state.demo.user_state(h['X-Session-ID'],1)
    state['semantic_pending']['created'] -= 301
    assert apply(client, h, p).status_code == 409
    p = preview(client, h).json(); apply(client, h, p)
    client.post('/api/reset',headers=h,json={'user_id':1})
    assert saved(client,h).json()['groups'] == []
    assert apply(client,h,p).status_code == 409


@pytest.mark.parametrize('case', ['ok','wrong_model','changed_digest','invalid_json','budget','wire_budget','retry'])
def test_real_local_adapter_contract_and_failed_raw_retention(monkeypatch, case):
    reads = 0
    def provenance(*args):
        nonlocal reads
        reads += 1
        return {'digest':'changed' if case == 'changed_digest' and reads == 2 else 'original', 'ollama_version':'test-runtime'}
    sent = []
    def request(base, path, payload, timeout):
        sent.append(payload)
        assert payload['messages'][0] == {'role':'system','content':'test instructions'}
        assert 'instructions' not in json.loads(payload['messages'][1]['content'])
        return {'model':'wrong' if case == 'wrong_model' else 'installed:test', 'done':True,
            'message':{'content':'bad json' if case == 'invalid_json' else '{"value":1}'}}
    monkeypatch.setattr(ii,'ollama_provenance',provenance);monkeypatch.setattr(ii,'_request',request)
    infer, model, calls = ii.make_induction_infer('installed:test')
    assert model == {'backend':'ollama-loopback','model_id':'installed:test','model_revision':'original'}
    objective = 'x'*20000 if case == 'budget' else '\u00e9'*3000 if case == 'wire_budget' else 'test'
    payload = {'instructions':'test instructions','objective':objective}
    if case in ('ok','retry'):
        assert infer(payload,{}) == {'value':1}
        if case == 'retry':
            with pytest.raises(ValueError,match='One inference'): infer(payload,{})
        assert len(sent) == 1
    else:
        with pytest.raises(ValueError): infer(payload,{})
        if case in ('budget','wire_budget'): assert not sent and not calls
        else: assert calls[0]['raw_http_response'] and calls[0]['status'] == 'error'
