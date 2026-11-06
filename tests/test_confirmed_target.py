"""New synthetic contract fixtures; no model accuracy or hunger-case rerun."""
from copy import deepcopy
import csv

import pytest
from fastapi.testclient import TestClient
from feedctrl import semantic_review as sr
from feedctrl.api import create_app
from feedctrl.semantic_controls import TEXT_FIELDS

ORIGINAL='I want an undisturbed afternoon. Remove the disruptive equipment.'
TARGET='Equipment whose supplied caption explicitly states it emits a beeping alarm.'
PROVENANCE={'backend':'offline-test-double','model':'not-live','digest':'no-model-weights'}

@pytest.fixture
def setup(tmp_path):
    path=tmp_path/'synthetic-equipment.csv'
    with path.open('w',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['video_id',*TEXT_FIELDS]);w.writeheader()
        for i in range(1,37):
            caption='This equipment emits a beeping alarm.' if i in (3,4) else ('Sound behavior is not stated.' if i==5 else 'This equipment has no audible alarm.')
            w.writerow({'video_id':i,'caption':caption})
    return path

def request(**kw):
    return {'user_id':1,'text':ORIGINAL,'label':'Confirmed alarm equipment',
        'candidate_ids':list(range(1,9)),'action_source':'confirmed',
        'confirmed_target':TARGET,'target_confirmed':True,'operation':'exclude',
        'strength':'none','mode':'replace',**kw}

def session(c):return {'X-Session-ID':c.post('/api/session',json={}).json()['session_id']}
def groups(c,h):return c.get('/api/semantic/groups?user_id=1',headers=h).json()
def model(calls,status='propose'):
    def infer(payload,schema):
        calls.append(deepcopy(payload))
        assert payload['request']==TARGET and payload['action']['intent_span']==TARGET
        assert 'needs_clarification' not in schema['required']
        return {'status':status,'reason':'Synthetic contract response, not model quality.',
            'negation_resolved':status!='ambiguous','alternatives':[],
            'evidence':[{'item_id':i,'field':'caption','quote':'emits a beeping alarm'} for i in (3,4)] if status=='propose' else []}
    return infer

@pytest.mark.parametrize('backend',['ollama','configured_model'])
def test_confirmed_target_review_apply_reset_and_source_isolation(setup,monkeypatch,backend):
    calls=[];infer=model(calls)
    monkeypatch.setattr(sr,'make_local_ollama_infer',lambda *a,**k:(infer,PROVENANCE))
    with TestClient(create_app(fixture=True,semantic_path=setup,
        semantic_infer_factory=lambda:(infer,PROVENANCE))) as c:
        c.app.state.demo.topic_index['source']='synthetic://confirmed-target/equipment'
        h=session(c);original_source=deepcopy(c.app.state.demo.topic_index)
        baseline=c.get('/api/compare?user_id=1',headers=h).json()
        preview=c.post('/api/semantic/preview',headers=h,json=request(backend=backend)).json()
        assert preview['ready'] and not preview['applied'] and len(calls)==1
        p=preview['proposal'];context=p['target_confirmation']
        assert p['item_ids']==[3,4] and p['action_source']=='user_confirmed_target'
        assert context['original_request']==ORIGINAL and context['original_request_sha256']==sr._digest(ORIGINAL)
        assert context['target']==TARGET and context['target_sha256']==p['provenance']['request_sha256']==sr._digest(TARGET)
        assert preview['groups'][0]['request']==TARGET and groups(c,h)['groups']==[]
        result=c.post('/api/semantic/apply',headers=h,json={'user_id':1,'plan_id':preview['plan_id']}).json()
        assert result['applied'] and result['feed']['available_items']==34
        assert c.get('/api/compare?user_id=1',headers=h).json()==baseline
        assert c.app.state.demo.topic_index==original_source
        c.post('/api/reset',headers=h,json={'user_id':1})
        assert groups(c,h)['groups']==[] and c.get('/api/compare?user_id=1',headers=h).json()==baseline

@pytest.mark.parametrize('change',[{'target_confirmed':False},{'confirmed_target':None},
    {'confirmed_target':'   '},{'confirmed_target':'beep\u202ehidden'},
    {'operation':'exclude','strength':'strong'},{'operation':'boost','strength':'none'},
    {'backend':'manual_category'},{'text':''},
    {'action_source':'manual'},{'action_source':'model','backend':'configured_model'}])
def test_invalid_confirmation_never_constructs_adapter(setup,monkeypatch,change):
    def forbidden(*a,**k):pytest.fail('Invalid confirmation must fail before adapter construction')
    monkeypatch.setattr(sr,'make_local_ollama_infer',forbidden)
    with TestClient(create_app(fixture=True,semantic_path=setup,semantic_infer_factory=forbidden)) as c:
        h=session(c);before=groups(c,h)
        response=c.post('/api/semantic/preview',headers=h,json=request(**change))
        assert response.status_code in (200,422)
        if response.status_code==200:assert not response.json()['ready'] and not response.json()['applied']
        assert groups(c,h)==before

def test_confirmation_boolean_is_strict(setup):
    with TestClient(create_app(fixture=True,semantic_path=setup)) as c:
        h=session(c)
        assert c.post('/api/semantic/preview',headers=h,json=request(target_confirmed='yes')).status_code==422

@pytest.mark.parametrize('status',['ambiguous','no_match'])
def test_confirmation_never_overrides_model_abstention_or_retries(setup,monkeypatch,status):
    calls=[]
    monkeypatch.setattr(sr,'make_local_ollama_infer',lambda *a,**k:(model(calls,status),PROVENANCE))
    with TestClient(create_app(fixture=True,semantic_path=setup)) as c:
        h=session(c);before=groups(c,h)
        response=c.post('/api/semantic/preview',headers=h,json=request()).json()
        assert not response['ready'] and not response['applied'] and 'plan_id' not in response
        assert response['target_confirmation']['confirmed'] is True and len(calls)==1
        assert groups(c,h)==before

@pytest.mark.parametrize('change',['original','target','missing','source'])
def test_sealed_confirmation_revalidated_before_apply(setup,monkeypatch,change):
    monkeypatch.setattr(sr,'make_local_ollama_infer',lambda *a,**k:(model([]),PROVENANCE))
    with TestClient(create_app(fixture=True,semantic_path=setup)) as c:
        h=session(c);p=c.post('/api/semantic/preview',headers=h,json=request()).json()
        state=c.app.state.demo.user_state(h['X-Session-ID'],1)
        group=state['semantic_pending']['groups'][0]
        if change=='original':group['proposal']['target_confirmation']['original_request']='Changed original'
        elif change=='target':group['proposal']['target_confirmation']['target']='A different target'
        elif change=='missing':group['proposal'].pop('target_confirmation')
        else:c.app.state.demo.topic_index['items'][3]['fields']['caption']='Changed source'
        # Recomputing the outer digest cannot rescue inconsistent inner provenance.
        group['revision']=sr._digest({k:v for k,v in group.items() if k!='revision'})
        assert c.post('/api/semantic/apply',headers=h,json={'user_id':1,'plan_id':p['plan_id']}).status_code==409
        assert state['semantic_groups']==[] and state['semantic_history']==[]

def test_confirmed_plan_is_session_bound(setup,monkeypatch):
    monkeypatch.setattr(sr,'make_local_ollama_infer',lambda *a,**k:(model([]),PROVENANCE))
    with TestClient(create_app(fixture=True,semantic_path=setup)) as c:
        first,second=session(c),session(c)
        p=c.post('/api/semantic/preview',headers=first,json=request()).json()
        assert c.post('/api/semantic/apply',headers=second,json={'user_id':1,'plan_id':p['plan_id']}).status_code==409
        assert groups(c,second)['groups']==[]
