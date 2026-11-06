"""New exposed contract fixtures, offline test doubles only. No semantic scoring."""
from copy import deepcopy
import csv
import json

import pytest
from fastapi.testclient import TestClient

from feedctrl import controls, indirect_grounding as ig
from feedctrl.api import create_app
from feedctrl.semantic_controls import TEXT_FIELDS

REQUEST = 'Hide displays that interrupt a quiet rehearsal.'
ACTION = {'operation': 'exclude', 'strength': 'none',
          'intent_span': 'interrupt a quiet rehearsal'}
PROVENANCE = {'backend': 'offline-test-double', 'model': 'fixture-only', 'digest': 'not-live'}
INDEX = {'sha256': 'a'*64, 'items': {
    1: {'fields': {'caption': 'Display emits an audible status tone.'}},
    2: {'fields': {'caption': 'Display has a flashing status light.'}},
    3: {'fields': {'caption': 'Display is silent and has no flashing light.'}},
    4: {'fields': {'caption': 'Sound and light behavior are not stated.'}}}}

def ambiguous():
    return {'status': 'ambiguous', 'reason': 'Sound and flashing-light interruption are different targets.',
            'negation_resolved': True,
            'alternatives': ['displays with audible status tones', 'displays with flashing status lights'],
            'evidence': []}

@pytest.mark.parametrize('status,resolved', [('ambiguous', True), ('no_match', False), ('propose', False)])
def test_clarification_preserves_hypotheses_without_selecting_or_rescuing(status, resolved):
    raw=ambiguous(); raw.update(status=status, negation_resolved=resolved)
    calls=[]
    def infer(payload,schema):
        calls.append(deepcopy(payload)); return raw
    r=ig.propose_indirect(REQUEST,ACTION,INDEX,infer,model_provenance=PROVENANCE)
    assert r['status']=='clarify' and r['requires_review'] is True
    assert r['item_ids']==[] and r['evidence']==[] and r['action']==ACTION
    assert r['clarification']['alternatives']==raw['alternatives']
    assert r['clarification']['model_reason']==raw['reason'] and len(calls)==1
    digest=r['provenance']['response_sha256']
    assert digest==ig._digest(raw)
    raw['alternatives'][0]='changed after return'
    assert r['clarification']['alternatives'][0]=='displays with audible status tones'
    assert r['provenance']['response_sha256']==digest

@pytest.mark.parametrize('alternatives', [[''], ['x'*301], ['x']*7, ['tone\u0085light'], ['tone\u202elight']])
def test_clarification_is_bounded_and_has_no_obscuring_control_text(alternatives):
    raw=ambiguous();raw['alternatives']=alternatives
    r=ig.propose_indirect(REQUEST,ACTION,INDEX,lambda *_:raw,model_provenance=PROVENANCE)
    assert r['status']=='error' and r['item_ids']==[] and 'clarification' not in r

def test_model_reason_obscuring_format_character_fails_closed():
    raw=ambiguous();raw['reason']='Visible\u202ehidden'
    r=ig.propose_indirect(REQUEST,ACTION,INDEX,lambda *_:raw,model_provenance=PROVENANCE)
    assert r['status']=='error' and r['item_ids']==[]

@pytest.fixture
def app_client(tmp_path):
    path=tmp_path/'synthetic-rehearsal.csv'
    with path.open('w',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['video_id',*TEXT_FIELDS]);w.writeheader()
        for i in range(1,37):
            fields=INDEX['items'].get(i,{'fields':{'caption':'Unrelated synthetic calibration record.'}})['fields']
            w.writerow({'video_id':i,**fields})
    with TestClient(create_app(fixture=True,semantic_path=path)) as c:
        h={'X-Session-ID':c.post('/api/session',json={}).json()['session_id']}
        yield c,h

def body():
    return {'user_id':1,'text':REQUEST,'label':'Rehearsal interruptions','candidate_ids':[1,2,3,4]}

def durable(client,headers):
    state=client.app.state.demo.user_state(headers['X-Session-ID'],1)
    return deepcopy({k:state.get(k) for k in ('semantic_groups','semantic_history','semantic_revision')}),client.get('/api/compare?user_id=1',headers=headers).json()

def test_api_clarification_preserves_all_durable_state_and_has_no_apply_token(app_client,monkeypatch):
    c,h=app_client
    c.get('/api/semantic/groups?user_id=1',headers=h)
    before=durable(c,h); calls=[]
    def infer(payload,schema):
        calls.append(deepcopy(payload))
        if 'needs_clarification' in schema['required']:
            return {'needs_clarification':False,'question':'','control':'exclude/none','intent_span':ACTION['intent_span']}
        return ambiguous()
    monkeypatch.setattr('feedctrl.semantic_review.make_local_ollama_infer',lambda *a,**k:(infer,PROVENANCE))
    r=c.post('/api/semantic/preview',headers=h,json=body())
    assert r.status_code==200
    v=r.json();assert v['status']=='clarify' and not v['ready'] and not v['applied']
    assert 'plan_id' not in v and v['item_ids']==[] and len(v['model_calls'])==2 and len(calls)==2
    assert v['clarification']['alternatives']==ambiguous()['alternatives']
    assert durable(c,h)==before
    stale=c.post('/api/semantic/apply',headers=h,json={'user_id':1,'plan_id':'not-created'})
    assert stale.status_code==409 and durable(c,h)==before

def envelope(content):
    return {'model':'installed:development','done':True,'done_reason':'stop','message':{'content':content}}

BAD_RESPONSES=[None, [], {'done':True,'model':'installed:development'},
    {'done':True,'model':'installed:development','message':None},
    envelope(None),envelope([]),envelope(''),envelope('not JSON'),envelope('[]'),
    envelope('{"needs_clarification":false,"needs_clarification":true}'),envelope('{"x":NaN}')]

@pytest.mark.parametrize('raw',BAD_RESPONSES)
def test_malformed_local_envelope_is_handled_by_api_without_state_change(app_client,monkeypatch,raw):
    c,h=app_client
    c.get('/api/semantic/groups?user_id=1',headers=h)
    before=durable(c,h);calls=[]
    monkeypatch.setenv('FEEDCTRL_STEERING_MODEL','installed:development')
    monkeypatch.setattr(controls,'ollama_provenance',lambda *a:{'digest':'offline-fixture','ollama_version':'test-only'})
    def request(*args):calls.append(args);return deepcopy(raw)
    monkeypatch.setattr(controls,'_request',request)
    r=c.post('/api/semantic/preview',headers=h,json=body())
    assert r.status_code==200
    v=r.json();assert v['status']=='error' and not v['ready'] and not v['applied']
    assert 'plan_id' not in v and len(calls)==1
    assert durable(c,h)==before

def test_strict_local_transport_accepts_one_object_and_rechecks_identity(monkeypatch):
    checks=[]
    monkeypatch.setattr(controls,'ollama_provenance',lambda *a:(checks.append(a) or {'digest':'same','ollama_version':'test-only'}))
    monkeypatch.setattr(controls,'_request',lambda *a:envelope(json.dumps({'fixture':'accepted'})))
    infer,p=ig.make_local_ollama_infer('installed:development',timeout=12)
    assert infer({'system':'offline contract only','request':'fixture'}, {'type':'object'})=={'fixture':'accepted'}
    assert len(checks)==2 and p['backend']=='ollama-loopback'

def test_strict_local_transport_rejects_overflow_to_infinity(monkeypatch):
    monkeypatch.setattr(controls,'ollama_provenance',lambda *a:{'digest':'same','ollama_version':'test-only'})
    monkeypatch.setattr(controls,'_request',lambda *a:envelope('{"value":1e309}'))
    infer,_=ig.make_local_ollama_infer('installed:development',timeout=12)
    with pytest.raises(ValueError):
        infer({'system':'offline contract only','request':'fixture'},{'type':'object'})
