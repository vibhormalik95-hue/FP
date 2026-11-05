"""Staged review/state contracts; response doubles are not model-quality evidence."""
from copy import deepcopy
import pytest
from feedctrl import induction_integration as ii
from feedctrl import staged_induction as si
from feedctrl import semantic_review as sr
from test_semantic_review import client,headers,apply,saved


def definition(payload):
    row=next(r for r in payload['catalogue'] if r['item_id']==3)
    return {'status':'propose','label':'Bread preparation scenes','definition':'Videos describing bread preparation.',
        'rationale':'Synthetic response double.','alternatives':[],
        'evidence':[{'item_id':3,'field':'caption','quote':row['fields']['caption'],'reason':'Synthetic supporting evidence.'}]}


def memberships(payload):
    return {'memberships':[{'item_id':r['item_id'],'verdict':'match' if r['item_id'] in (3,4) else 'not_match',
        'field':'caption','evidence_quote':r['fields']['caption'],'reason':'Synthetic test disposition.'} for r in payload['catalogue']]}


def model(monkeypatch,first=definition,second=memberships,hook=None,digest='fixture-model'):
    calls=[]
    def make(*args,**kwargs):
        local=[]
        def infer(payload,schema):
            stage='definition' if 'evidence' in schema['required'] else 'membership'
            if hook: hook(stage)
            raw=(first if stage=='definition' else second)(deepcopy(payload))
            local.append({'raw_http_response':deepcopy(raw)})
            calls.append(stage)
            return raw
        return infer,{'backend':'test-double','model_id':'fixture','model_revision':digest},local
    monkeypatch.setattr(ii,'make_induction_infer',make)
    return calls


def preview(c,h,**kwargs):
    return c.post('/api/semantic/definition/preview',headers=h,json={
        'user_id':1,'candidate_ids':list(range(1,9)),'objective':'Find preparation scenes.',
        'operation':'exclude','strength':'none',**kwargs})


def classify(c,h,p,**kwargs):
    return c.post('/api/semantic/definition/classify',headers=h,json={
        'user_id':1,'plan_id':p['definition_plan_id'],'evidence_reviewed':True,**kwargs})


def test_two_distinct_approvals_apply_only_complete_reviewed_ids(client,monkeypatch):
    h=headers(client);calls=model(monkeypatch)
    original=client.get('/api/compare?user_id=1',headers=h).json()
    p=preview(client,h).json()
    assert p['definition_ready'] and not p['applied'] and calls==['definition']
    assert saved(client,h).json()['groups']==[]
    m=classify(client,h,p).json()
    assert m['ready'] and m['definition_approved'] and not m['applied']
    assert calls==['definition','membership'] and saved(client,h).json()['groups']==[]
    g=m['groups'][0]
    assert g['proposal']['item_ids']==[3,4]
    assert len(g['proposal']['induction']['envelope']['field_evidence'])==8
    assert len(g['proposal']['induction']['definition_model_calls'])==1
    assert apply(client,h,m).json()['feed']['available_items']==34
    assert client.get('/api/compare?user_id=1',headers=h).json()==original
    assert classify(client,h,p).status_code==409
    clear=client.post('/api/semantic/history/preview',headers=h,json={'user_id':1,'action':'clear'}).json()
    apply(client,h,clear)
    undo=client.post('/api/semantic/history/preview',headers=h,json={'user_id':1,'action':'undo'}).json()
    assert apply(client,h,undo).json()['groups']==m['groups']


@pytest.mark.parametrize('approval',[False,1,'true',None])
def test_definition_requires_strict_affirmative_review(client,monkeypatch,approval):
    h=headers(client);calls=model(monkeypatch);p=preview(client,h).json()
    assert classify(client,h,p,evidence_reviewed=approval).status_code==422
    assert calls==['definition'] and saved(client,h).json()['groups']==[]


@pytest.mark.parametrize('change',['definition','action','mode','source','original_inventory','eligible','expiry','session','user','reset'])
def test_stale_or_changed_definition_never_starts_classification(client,monkeypatch,change):
    h=headers(client);calls=model(monkeypatch);p=preview(client,h).json();demo=client.app.state.demo
    state=demo.user_state(h['X-Session-ID'],1);pending=state['semantic_definition_pending']
    used_h=h;user=1
    if change=='definition':pending['definition']['proposal']['definition']='Changed'
    elif change=='action':pending['body']['operation']='boost'
    elif change=='mode':pending['body']['mode']='replace'
    elif change=='source':demo.topic_index['items'][3]['fields']['caption']='Changed'
    elif change=='original_inventory':demo.items[3]=['changed']
    elif change=='eligible':demo.items.pop(36)
    elif change=='expiry':pending['created']-=301
    elif change=='session':used_h=headers(client)
    elif change=='user':user=2
    else:client.post('/api/reset',headers=h,json={'user_id':1})
    before=deepcopy(state)
    assert classify(client,used_h,p,user_id=user).status_code==409
    assert state==before and calls==['definition']


def test_consumed_token_cannot_duplicate_in_flight_model_call(client,monkeypatch):
    h=headers(client);p_holder={};nested=[]
    def hook(stage):
        if stage=='membership':nested.append(classify(client,h,p_holder['p']).status_code)
    calls=model(monkeypatch,hook=hook);p_holder['p']=preview(client,h).json()
    assert classify(client,h,p_holder['p']).json()['ready']
    assert nested==[409] and calls==['definition','membership']


@pytest.mark.parametrize('stage',['definition','membership'])
def test_newer_review_race_prevents_stale_stage_result(client,monkeypatch,stage):
    h=headers(client)
    def hook(current):
        if current==stage:client.post('/api/semantic/history/preview',headers=h,json={'user_id':1,'action':'clear'})
    model(monkeypatch,hook=hook)
    p=preview(client,h).json()
    result=p if stage=='definition' else classify(client,h,p).json()
    assert not result.get('definition_ready') and not result.get('ready') and not result['applied']
    assert saved(client,h).json()['groups']==[]


def test_unsupported_definition_abstains_without_membership_or_profile_write(client,monkeypatch):
    h=headers(client)
    def unsupported(payload):
        return {'status':'no_match','label':'','definition':'','rationale':'No evidence for this property.',
            'alternatives':[],'evidence':[]}
    calls=model(monkeypatch,first=unsupported)
    p=preview(client,h,objective='Verified certification absent from the supplied metadata').json()
    assert p['status']=='no_match' and not p['definition_ready'] and not p['applied']
    assert calls==['definition'] and saved(client,h).json()['groups']==[]


def test_all_unknown_memberships_preserve_abstention_after_definition_review(client,monkeypatch):
    h=headers(client)
    def unknown(payload):
        return {'memberships':[{'item_id':r['item_id'],'verdict':'unknown','field':'',
            'evidence_quote':'','reason':'Required property is not stated.'} for r in payload['catalogue']]}
    model(monkeypatch,second=unknown);p=preview(client,h).json();m=classify(client,h,p).json()
    assert not m['ready'] and not m['applied'] and m['status']=='clarify'
    assert len(m['unknown_ids'])==8 and saved(client,h).json()['groups']==[]


@pytest.mark.parametrize('fault',['missing','duplicate','invented_id','quote','definition_drift'])
def test_invalid_membership_never_receives_apply_token(client,monkeypatch,fault):
    h=headers(client)
    def invalid(payload):
        raw=memberships(payload)
        if fault=='missing':raw['memberships'].pop()
        elif fault=='duplicate':raw['memberships'][-1]=deepcopy(raw['memberships'][0])
        elif fault=='invented_id':raw['memberships'][0]['item_id']=999
        elif fault=='quote':raw['memberships'][0]['evidence_quote']='Invented'
        else:raw['definition']='A changed meaning'
        return raw
    model(monkeypatch,second=invalid);p=preview(client,h).json();m=classify(client,h,p).json()
    assert m['status']=='error' and not m['ready'] and not m['applied']
    assert saved(client,h).json()['groups']==[]


def test_staged_definition_seal_and_current_inventory_survive_history_boundaries(client,monkeypatch):
    h=headers(client);model(monkeypatch);p=preview(client,h).json();m=classify(client,h,p).json()
    apply(client,h,m)
    clear=client.post('/api/semantic/history/preview',headers=h,json={'user_id':1,'action':'clear'}).json()
    apply(client,h,clear)
    restore=client.post('/api/semantic/history/preview',headers=h,json={'user_id':1,'action':'undo'}).json()
    client.app.state.demo.items[3]=['changed']
    state=client.app.state.demo.user_state(h['X-Session-ID'],1);before=deepcopy(state)
    assert apply(client,h,restore).status_code==409 and state==before


def test_snapshot_mutation_and_returned_raw_aliases_are_not_authoritative(client):
    index=sr.scoped_index(client.app.state.demo.topic_index,list(range(1,9)))
    inventory=ii.projected_inventory(index,client.app.state.demo.items,[])
    actual=deepcopy(index);raw_holder={}
    def mutate(payload,schema):
        raw=definition(payload);raw_holder['raw']=raw
        payload['catalogue'][2]['fields']['caption']='Invented'
        index['items'][3]['fields']['caption']='Caller changed'
        return raw
    model={'backend':'fixture','model_id':'fixture','model_revision':'fixture'}
    d=si.propose_definition('Preparation',index,inventory,mutate,model)
    raw_holder['raw']['definition']='Changed after return'
    si.revalidate_definition(d,'Preparation',actual,inventory)
    assert d['proposal']['definition']=='Videos describing bread preparation.'


def test_changed_runtime_digest_never_starts_membership(client,monkeypatch):
    h=headers(client);model(monkeypatch);p=preview(client,h).json()
    calls=model(monkeypatch,digest='different-installed-model')
    result=classify(client,h,p).json()
    assert result['status']=='error' and not result['applied'] and calls==[]
    assert saved(client,h).json()['groups']==[]


def test_nested_membership_definition_mutation_rejected_at_apply(client,monkeypatch):
    h=headers(client);model(monkeypatch);p=preview(client,h).json();m=classify(client,h,p).json()
    state=client.app.state.demo.user_state(h['X-Session-ID'],1)
    state['semantic_pending']['groups'][0]['proposal']['induction']['envelope']['staged_definition']['proposal']['definition']='Changed'
    before=deepcopy(state)
    assert apply(client,h,m).status_code==409 and state==before


def test_definition_without_support_never_reaches_review(client,monkeypatch):
    h=headers(client)
    def empty(payload):
        raw=definition(payload);raw['evidence']=[];return raw
    calls=model(monkeypatch,first=empty);p=preview(client,h).json()
    assert p['status']=='error' and not p['definition_ready'] and not p['applied']
    assert calls==['definition'] and saved(client,h).json()['groups']==[]


def test_uncited_unknown_canonicalization_preserves_verdict_and_raw_output(client):
    index=sr.scoped_index(client.app.state.demo.topic_index,[3,4])
    raw={'memberships':[{'item_id':i,'verdict':'unknown','field':'caption','evidence_quote':'',
        'reason':'No evidence for the required property.'} for i in (3,4)]}
    before=deepcopy(raw)
    result=si.classify_rows({'label':'Unstated property','definition':'An unstated property.'},index,lambda *a:raw)
    assert raw==before
    assert [r['verdict'] for r in result['memberships']]==['unknown','unknown']
    assert all(r['field']==r['evidence_quote']=='' for r in result['memberships'])
    assert [r['item_id'] for r in result['normalizations']]==[3,4]
    assert result['audit']['response_sha256']==ii._digest(before)


@pytest.mark.parametrize('verdict,field,quote',[
    ('match','caption',''),('not_match','caption',''),
    ('unknown','invented_field',''),('unknown','caption','invented quote')])
def test_unknown_normalization_does_not_allow_false_evidence(client,verdict,field,quote):
    index=sr.scoped_index(client.app.state.demo.topic_index,[3,4])
    raw={'memberships':[{'item_id':i,'verdict':verdict,'field':field,'evidence_quote':quote,
        'reason':'Synthetic invalid output.'} for i in (3,4)]}
    with pytest.raises(ValueError):
        si.classify_rows({'label':'A property','definition':'A property.'},index,lambda *a:raw)
