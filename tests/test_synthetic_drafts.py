"""Offline doubles exercise fictional metadata contracts, not live model quality."""
from copy import deepcopy
import pytest
from fastapi.testclient import TestClient
from feedctrl.api import create_app
from feedctrl import synthetic_drafts as sd

RAW={'title':'Cloud reading nook','description':'An explicitly fictional reading nook floating in an imagined cloud garden.','category_label':'Imaginary reading spaces'}

@pytest.fixture
def client():
    with TestClient(create_app(fixture=True)) as c:yield c

def session(c):return {'X-Session-ID':c.post('/api/session',json={}).json()['session_id']}
def listing(c,h,user=1):return c.get(f'/api/synthetic/items?user_id={user}',headers=h)
def preview(c,h,**kw):return c.post('/api/synthetic/preview',headers=h,json={'user_id':1,'brief':'Invent a fictional reading nook.','synthetic_acknowledged':True,**kw})
def admit(c,h,p,user=1):return c.post('/api/synthetic/admit',headers=h,json={'user_id':user,'plan_id':p['plan_id']})
def mock(monkeypatch,raw=None,hook=None):
    count=[];model={'model':'fixture','digest':'not-live','ollama_version':'test-double'}
    def make(*a,**kw):
        calls=[]
        def infer(brief):
            count.append(brief)
            if hook:hook(model)
            value=RAW if raw is None else raw
            calls.append({'kind':'offline-test-double','raw':deepcopy(value)})
            return value
        return infer,model,calls
    monkeypatch.setattr(sd,'make_draft_infer',make)
    return count,model

def test_review_admit_neutral_feed_remove_reset_and_observed_source_isolation(client,monkeypatch):
    h=session(client);calls,_=mock(monkeypatch);demo=client.app.state.demo
    base=client.get('/api/compare?user_id=1',headers=h).json();source=deepcopy(demo.items);data=deepcopy(demo.data)
    assert listing(client,h).json()['items']==[]
    p=preview(client,h).json();assert p['ready'] and not p['admitted']
    assert listing(client,h).json()['items']==[]
    a=admit(client,h,p).json();r=a['items'][0]
    assert a['admitted'] and r['origin']==sd.ORIGIN and r['is_synthetic'] is True and r['media_asset'] is None
    assert r['item_id'].startswith('synthetic-') and a['feed']['items'][0]['score']==0
    assert not a['feed']['uses_trained_scorer'] and a['feed']['isolated_from_observed_catalogue']
    assert client.get('/api/compare?user_id=1',headers=h).json()==base
    assert demo.items==source and demo.data==data and len(calls)==1
    assert admit(client,h,p).status_code==409
    removed=client.post('/api/synthetic/remove',headers=h,json={'user_id':1,'item_id':r['item_id']}).json()
    assert removed['removed'] and removed['items']==[]
    p=preview(client,h).json();admit(client,h,p)
    assert client.post('/api/reset',headers=h,json={'user_id':1}).status_code==200
    assert listing(client,h).json()['items']==[] and client.get('/api/compare?user_id=1',headers=h).json()==base

@pytest.mark.parametrize('ack',[False,1,'true',None])
def test_strict_opt_in_precedes_any_inference(client,monkeypatch,ack):
    h=session(client);calls,_=mock(monkeypatch)
    assert preview(client,h,synthetic_acknowledged=ack).status_code==422 and calls==[]

@pytest.mark.parametrize('brief',[' ','x'*2001,'bad\x00brief','https://real.example/private','bad\ud800'])
def test_invalid_briefs_never_infer(client,monkeypatch,brief):
    h=session(client);calls,_=mock(monkeypatch)
    if '\ud800' in brief:
        # JSON encoding can reject an unpaired surrogate before API transport.
        with pytest.raises(ValueError):sd._text(brief,2000)
    else:assert preview(client,h,brief=brief).status_code==422
    assert calls==[]

@pytest.mark.parametrize('raw',[{},[],{'title':'x','description':'y','category_label':'z','item_id':1},
    {'title':None,'description':'y','category_label':'z'},
    {'title':'x','description':'https://video.example/real','category_label':'z'},
    {'title':'x','description':'','category_label':'z'},
    {'title':'x'*121,'description':'y','category_label':'z'},
    {'title':'x','description':'y','category_label':'z\nother'}])
def test_invalid_model_output_never_admitted_or_changes_original_state(client,monkeypatch,raw):
    h=session(client);mock(monkeypatch,raw);before=client.get('/api/compare?user_id=1',headers=h).json()
    p=preview(client,h).json();assert not p['ready'] and not p['admitted'] and p['status']=='error'
    assert listing(client,h).json()['items']==[] and client.get('/api/compare?user_id=1',headers=h).json()==before

@pytest.mark.parametrize('change',['session','user','expiry','record','pending','source','reset','clear','nonce','revision'])
def test_stale_or_cross_boundary_admission_rejects_unchanged_store(client,monkeypatch,change):
    h=session(client);mock(monkeypatch);p=preview(client,h).json();demo=client.app.state.demo;s=demo.user_state(h['X-Session-ID'],1)
    other=h;user=1
    if change=='session':other=session(client)
    elif change=='user':user=2
    elif change=='expiry':s['synthetic_pending']['created']-=301
    elif change=='record':s['synthetic_pending']['record']['description']='Changed'
    elif change=='pending':s['synthetic_pending']['source_version']='changed'
    elif change=='source':demo.items[1]=['changed']
    elif change=='reset':client.post('/api/reset',headers=h,json={'user_id':1})
    elif change=='clear':client.post('/api/synthetic/clear',headers=h,json={'user_id':1})
    elif change=='nonce':s['synthetic_nonce']='changed'
    else:s['synthetic_revision']+=1
    before=deepcopy(s)
    assert admit(client,other,p,user).status_code==409 and s==before and s['synthetic_items']==[]

def test_duplicate_content_and_duplicate_ids_rejected(client,monkeypatch):
    h=session(client);mock(monkeypatch);p=preview(client,h).json();admit(client,h,p)
    assert preview(client,h).json()['status']=='error'
    s=client.app.state.demo.user_state(h['X-Session-ID'],1)
    s['synthetic_items'].append(deepcopy(s['synthetic_items'][0]))
    assert listing(client,h).status_code==409
    assert client.post('/api/synthetic/clear',headers=h,json={'user_id':1}).json()['items']==[]

def test_admission_rechecks_duplicate_id_even_with_other_content(client,monkeypatch):
    h=session(client);mock(monkeypatch);p=preview(client,h).json();admit(client,h,p)
    mock(monkeypatch,{**RAW,'title':'Other nook'});p=preview(client,h).json()
    s=client.app.state.demo.user_state(h['X-Session-ID'],1);pending=deepcopy(s['synthetic_pending'])
    pending['record']['item_id']=s['synthetic_items'][0]['item_id'];pending['record']=sd.sealed(pending['record']);s['synthetic_pending']=sd.sealed(pending)
    before=deepcopy(s);assert admit(client,h,p).status_code==409 and s==before

def test_saved_items_and_source_scopes_cannot_cross_sessions_or_original_ids(client,monkeypatch):
    h=session(client);other=session(client);mock(monkeypatch);p=preview(client,h).json();a=admit(client,h,p).json();item=a['items'][0]['item_id']
    assert listing(client,other).json()['items']==[] and listing(client,h,2).json()['items']==[]
    assert client.post('/api/synthetic/remove',headers=other,json={'user_id':1,'item_id':item}).status_code==404
    assert client.post('/api/feedback',headers=h,json={'user_id':1,'item_id':item,'direction':'like'}).status_code==422
    assert client.post('/api/semantic/preview',headers=h,json={'user_id':1,'label':'X','candidate_ids':[1,item]}).status_code==422

def test_admission_invalidates_pending_but_preserves_saved_observed_groups(client,monkeypatch):
    h=session(client);mock(monkeypatch);p=preview(client,h).json();s=client.app.state.demo.user_state(h['X-Session-ID'],1)
    saved=[{'synthetic_test_saved_group':'unchanged'}];s['semantic_groups']=deepcopy(saved)
    for k in ('semantic_pending','semantic_definition_pending','semantic_preview_nonce','steering_pending'):s[k]={'old':'context'}
    s['semantic_revision']=7;s['steering_revision']=8
    admit(client,h,p)
    assert s['semantic_groups']==saved
    assert all(s[k] is None for k in ('semantic_pending','semantic_definition_pending','semantic_preview_nonce','steering_pending'))
    assert s['semantic_revision']==8 and s['steering_revision']==9

@pytest.mark.parametrize('kind',['reset','source','newer_preview'])
def test_inflight_race_cannot_install_stale_draft(client,monkeypatch,kind):
    h=session(client);called=[]
    def hook(model):
        if called:return
        called.append(True)
        if kind=='reset':client.post('/api/reset',headers=h,json={'user_id':1})
        elif kind=='source':client.app.state.demo.items[1]=['changed']
        else:
            mock(monkeypatch)
            assert preview(client,h).json()['ready']
    mock(monkeypatch,hook=hook)
    assert preview(client,h).status_code==409 and listing(client,h).json()['items']==[]

def test_source_drift_withholds_admitted_item_and_removal_still_works(client,monkeypatch):
    h=session(client);mock(monkeypatch);p=preview(client,h).json();a=admit(client,h,p).json();item=a['items'][0]['item_id']
    client.app.state.demo.items[1]=['changed']
    result=listing(client,h).json()
    assert result['items'][0]['source_snapshot_changed'] and result['feed']['items']==[]
    assert client.post('/api/synthetic/remove',headers=h,json={'user_id':1,'item_id':item}).json()['items']==[]

def test_reviewed_restore_reuses_exact_generated_record_without_inference(client,monkeypatch):
    h=session(client);count,_=mock(monkeypatch);p=preview(client,h).json();a=admit(client,h,p).json();record=a['items'][0]
    client.post('/api/synthetic/remove',headers=h,json={'user_id':1,'item_id':record['item_id']})
    assert listing(client,h).json()['can_restore_removed']
    restored=client.post('/api/synthetic/restore/preview',headers=h,json={'user_id':1}).json()
    assert restored['ready'] and restored['replayed_removed_record'] and restored['model_calls']==[]
    assert restored['draft']=={k:v for k,v in record.items() if k!='source_snapshot_changed'}
    assert listing(client,h).json()['items']==[]
    again=admit(client,h,restored).json()['items'][0]
    assert again['item_id']==record['item_id'] and again['provenance']==record['provenance'] and again['origin']==sd.ORIGIN
    assert len(count)==1 and not listing(client,h).json()['can_restore_removed']
    client.post('/api/reset',headers=h,json={'user_id':1})
    assert listing(client,h).json()['items']==[] and not listing(client,h).json()['can_restore_removed']

@pytest.mark.parametrize('change',['source','session','clear','reset'])
def test_restore_rejects_drift_and_has_no_cross_session_history(client,monkeypatch,change):
    h=session(client);count,_=mock(monkeypatch);p=preview(client,h).json();a=admit(client,h,p).json()
    client.post('/api/synthetic/remove',headers=h,json={'user_id':1,'item_id':a['items'][0]['item_id']})
    used=h
    if change=='source':client.app.state.demo.items[1]=['changed']
    elif change=='session':used=session(client)
    else:client.post('/api/'+('synthetic/clear' if change=='clear' else 'reset'),headers=h,json={'user_id':1})
    state=client.app.state.demo.user_state(h['X-Session-ID'],1);before=deepcopy(state)
    assert client.post('/api/synthetic/restore/preview',headers=used,json={'user_id':1}).status_code==409
    assert state==before and len(count)==1

def test_response_aliases_and_callback_model_mutation_do_not_change_record(client,monkeypatch):
    h=session(client);raw=deepcopy(RAW)
    calls,model=mock(monkeypatch,raw,lambda m:m.update(digest='changed-during-callback'))
    p=preview(client,h).json();assert p['draft']['provenance']['model']['digest']=='not-live'
    raw['description']='Changed after return';model['digest']='changed-after-return';p['draft']['title']='Client tamper'
    stored=client.app.state.demo.user_state(h['X-Session-ID'],1)['synthetic_pending']['record']
    assert stored['description']==RAW['description'] and stored['title']==RAW['title']
    assert stored['provenance']['model']['digest']=='not-live'

def test_local_adapter_one_attempt_bounded_options_raw_receipt_and_digest(monkeypatch):
    calls=[]
    monkeypatch.setattr(sd,'ollama_provenance',lambda *a:{'model':'fixture','digest':'D','ollama_version':'fixture'})
    def request(base,path,body,timeout):
        calls.append(deepcopy(body));return {'model':'fixture','done':True,'done_reason':'stop','message':{'content':__import__('json').dumps(RAW)}}
    monkeypatch.setattr(sd,'_request',request)
    infer,model,receipts=sd.make_draft_infer('fixture')
    assert infer('Fictional nook.')==RAW
    assert calls[0]['options']['num_predict']==1000 and calls[0]['messages'][1]['content']=='Fictional nook.'
    assert calls[0]['messages']==[{'role':'system','content':sd.PROMPT},{'role':'user','content':'Fictional nook.'}]
    assert set(calls[0])=={'model','messages','format','stream','keep_alive','options'}
    assert receipts[0]['raw_http_response']['done']
    with pytest.raises(ValueError):infer('No retry')
    assert len(calls)==1

def test_capacity_gate_stops_before_generation(client,monkeypatch):
    h=session(client);attempts=[]
    for n in range(sd.MAX_ITEMS):
        count,_=mock(monkeypatch,{**RAW,'title':f'Fictional nook {n}'})
        p=preview(client,h).json();assert p['ready'];assert admit(client,h,p).json()['admitted'];attempts+=count
    assert len(attempts)==sd.MAX_ITEMS
    count,_=mock(monkeypatch,{**RAW,'title':'No ninth item'})
    assert preview(client,h).status_code==409 and count==[]

@pytest.mark.parametrize('fault',['model','incomplete','length','invalid_json','duplicate_json','digest'])
def test_adapter_failures_keep_raw_receipt_and_never_retry(monkeypatch,fault):
    attempts=[];identities=[]
    def identity(*a):
        identities.append(True)
        return {'model':'fixture','digest':'changed' if fault=='digest' and len(identities)>1 else 'D'}
    monkeypatch.setattr(sd,'ollama_provenance',identity)
    def request(*args):
        attempts.append(True)
        return {'model':'wrong' if fault=='model' else 'fixture','done':fault!='incomplete',
                'done_reason':'length' if fault=='length' else 'stop',
                'message':{'content':'invalid' if fault=='invalid_json' else '{"title":"a","title":"b"}' if fault=='duplicate_json' else __import__('json').dumps(RAW)}}
    monkeypatch.setattr(sd,'_request',request)
    infer,model,receipts=sd.make_draft_infer('fixture')
    with pytest.raises(ValueError):infer('Fictional nook.')
    assert receipts[0]['status']=='error' and 'raw_http_response' in receipts[0]
    with pytest.raises(ValueError):infer('No retry')
    assert len(attempts)==1

@pytest.mark.parametrize('envelope',[
    {'model':'fixture','done':True,'done_reason':'stop'},
    {'model':'fixture','done':True,'message':None},
    {'model':'fixture','done':True,'message':{}},
    {'model':'fixture','done':True,'message':{'content':None}},
    {'model':'fixture','done':True,'message':{'content':123}},
    []])
def test_malformed_completed_envelope_is_handled_with_caller_receipt(client,monkeypatch,envelope):
    h=session(client);attempts=[]
    monkeypatch.setenv('FEEDCTRL_STEERING_MODEL','fixture')
    monkeypatch.setattr(sd,'ollama_provenance',lambda *a:{'model':'fixture','digest':'D'})
    def request(*args):attempts.append(True);return deepcopy(envelope)
    monkeypatch.setattr(sd,'_request',request)
    before=client.get('/api/compare?user_id=1',headers=h).json()
    result=preview(client,h)
    assert result.status_code==200
    body=result.json();assert body['status']=='error' and not body['ready'] and not body['admitted']
    assert 'Malformed draft response' in body['reason']
    assert body['model_calls'][0]['status']=='error' and body['model_calls'][0]['raw_http_response']==envelope
    assert len(attempts)==1 and listing(client,h).json()['items']==[]
    assert client.get('/api/compare?user_id=1',headers=h).json()==before

@pytest.mark.parametrize('character',['\u0085','\u202e','\u2066','\u200b','\ufeff','\u2028','\u2029'])
@pytest.mark.parametrize('field',['title','description','category_label'])
def test_unicode_review_obscuring_characters_rejected_without_admission(client,monkeypatch,character,field):
    h=session(client);mock(monkeypatch,{**RAW,field:RAW[field]+character+'hidden'})
    p=preview(client,h).json()
    assert p['status']=='error' and 'Unicode control' in p['reason'] and not p['ready']
    assert listing(client,h).json()['items']==[]

@pytest.mark.parametrize('character',['\u0085','\u202e'])
def test_unicode_obscured_user_brief_rejected_before_inference(client,monkeypatch,character):
    h=session(client);count,_=mock(monkeypatch)
    assert preview(client,h,brief='Fictional'+character+'brief').status_code==422 and count==[]

def test_ordinary_unicode_and_explicit_multiline_text_remain_valid():
    raw={'title':'Café 月','description':'Fictional café.\nA second imagined line.\tA detail.','category_label':'Imaginary café'}
    assert sd.validate_output(raw)==raw
