"""Evidence-audit software contracts only. Doubles do not establish semantic accuracy."""
from copy import deepcopy
import pytest
from feedctrl import evidence_audit as ea,staged_induction as si,induction_integration as ii
from test_staged_induction import client,headers,preview,classify,saved,apply,model as staged_model

MODEL={'backend':'fixture','model_id':'fixture','model_revision':'fixed'}

def inputs():
    index={'sha256':'a'*64,'items':{
        1:{'fields':{'caption':'A stated 18-month service plan.'}},
        2:{'fields':{'caption':'Caption says no 18-month service plan.'}},
        3:{'fields':{'caption':'Term not stated.'}}}}
    inventory=[{'category_id':'A','label':'A','member_ids':[1,3]},
               {'category_id':'B','label':'B','member_ids':[2]}]
    objective='An explicitly stated current 18-month service plan.'
    def definition(payload,schema):return {'status':'propose','label':'Stated plan','definition':objective,
        'rationale':'Synthetic proposal double.','alternatives':[],
        'evidence':[{'item_id':1,'field':'caption','quote':index['items'][1]['fields']['caption'],'reason':'Synthetic supporting quote.'}]}
    d=si.propose_definition(objective,index,inventory,definition,MODEL)
    def memberships(payload,schema):return {'memberships':[{'item_id':i,
        'verdict':'match' if i in (1,2) else 'unknown','field':'caption',
        'evidence_quote':index['items'][i]['fields']['caption'],'reason':'Adversarial test proposal, not semantic gold.'} for i in (1,2,3)]}
    primary=si.classify_definition(d,objective,index,inventory,memberships,MODEL)
    return objective,index,inventory,primary

def assessment(index,kinds=('supported','contradicted','not_stated')):
    return {'assessments':[{'item_id':i,'assessment':kind,'field':'caption',
        'quote':index['items'][i]['fields']['caption'],'reason':'Synthetic assessment double.'}
        for i,kind in zip((1,2,3),kinds)]}

def test_blind_assessment_intersection_revalidates_and_retains_primary():
    obj,index,inventory,primary=inputs();before=deepcopy(primary);seen=[]
    def infer(payload,schema):seen.append(payload);return assessment(index)
    result=ea.audit_membership_envelope(primary,obj,index,inventory,infer,MODEL)
    assert set(seen[0])=={'instructions','reviewed_definition','catalogue'}
    assert 'memberships' not in seen[0] and 'primary' not in seen[0]
    assert primary==before and result['status']=='review'
    assert [r['item_id'] for r in result['field_evidence'] if r['verdict']=='match']==[1]
    assert result['unknown_ids']==[2,3]
    assert result['evidence_audit']['primary_envelope']==before
    assert result['evidence_audit']['semantic_truth_verified'] is False
    si.revalidate_membership_envelope(result,obj,index,inventory)
    checked=ii.checked_category(result,obj,index,inventory)
    assert checked['member_ids']==[1] and checked['semantic_entailment_verified'] is False

@pytest.mark.parametrize('kind',['contradicted','not_stated','ambiguous'])
def test_no_audit_support_means_no_reviewable_positive(kind):
    obj,index,inventory,primary=inputs()
    r=ea.audit_membership_envelope(primary,obj,index,inventory,lambda *a:assessment(index,(kind,kind,kind)),MODEL)
    assert r['status']=='clarify' and r['proposal'] is None and r['unknown_ids']==[1,2,3]

def test_audit_cannot_upgrade_primary_unknown_or_negative():
    obj,index,inventory,primary=inputs()
    primary['field_evidence'][1]['verdict']='not_match'
    primary['proposal']['memberships'][1]['verdict']='not_match'
    primary=si.sealed(primary,'staged_revision')
    r=ea.audit_membership_envelope(primary,obj,index,inventory,lambda *a:assessment(index,('supported',)*3),MODEL)
    assert [x['item_id'] for x in r['field_evidence'] if x['verdict']=='match']==[1]
    assert r['unknown_ids']==[2,3]

@pytest.mark.parametrize('fault',['missing','duplicate','invented','bool','quote','field','kind','extra','long_reason'])
def test_invalid_evidence_assessment_fails_closed(fault):
    obj,index,inventory,primary=inputs();raw=assessment(index)
    if fault=='missing':raw['assessments'].pop()
    elif fault=='duplicate':raw['assessments'][2]=deepcopy(raw['assessments'][0])
    elif fault=='invented':raw['assessments'][0]['item_id']=999
    elif fault=='bool':raw['assessments'][0]['item_id']=True
    elif fault=='quote':raw['assessments'][0]['quote']='Invented affirmative statement'
    elif fault=='field':raw['assessments'][0]['field']='invented'
    elif fault=='kind':raw['assessments'][0]['assessment']='maybe'
    elif fault=='long_reason':raw['assessments'][0]['reason']='x'*801
    else:raw['definitions']='Replace the reviewed definition'
    before=deepcopy(primary)
    with pytest.raises(ValueError):ea.audit_membership_envelope(primary,obj,index,inventory,lambda *a:raw,MODEL)
    assert primary==before

def test_callback_payload_mutation_cannot_rewrite_evidence_and_outputs_are_owned():
    obj,index,inventory,primary=inputs();raw=assessment(index);owned=deepcopy(index)
    def infer(payload,schema):
        payload['catalogue'][0]['fields']['caption']='Fabricated'
        index['items'][1]['fields']['caption']='Caller mutation'
        MODEL['model_revision']='Caller mutation'
        return raw
    model=deepcopy(MODEL)
    try:r=ea.audit_membership_envelope(primary,obj,index,inventory,infer,model)
    finally:MODEL['model_revision']='fixed'
    raw['assessments'][0]['item_id']=999
    si.revalidate_membership_envelope(r,obj,owned,inventory)
    assert r['evidence_audit']['assessment']['assessments'][0]['item_id']==1

def test_mutated_audit_or_current_source_cannot_be_applied(client,monkeypatch):
    h=headers(client);staged_model(monkeypatch);d=preview(client,h).json();m=classify(client,h,d).json()
    assert m['ready'] and len(m['evidence_audit_model_calls'])==1
    state=client.app.state.demo.user_state(h['X-Session-ID'],1)
    state['semantic_pending']['groups'][0]['proposal']['induction']['envelope']['evidence_audit']['assessment']['assessments'][0]['assessment']='supported'
    before=deepcopy(state)
    assert apply(client,h,m).status_code==409 and state==before

def test_assessment_runtime_failure_preserves_profile_and_ae(client,monkeypatch):
    h=headers(client);staged_model(monkeypatch)
    original=ii.make_induction_infer
    def make(*args,**kw):
        infer,provenance,calls=original(*args,**kw)
        def fail(payload,schema):
            if 'assessments' in schema['required']:raise ValueError('Synthetic assessment failure')
            return infer(payload,schema)
        return fail,provenance,calls
    monkeypatch.setattr(ii,'make_induction_infer',make)
    ae=client.get('/api/compare?user_id=1',headers=h).json()
    d=preview(client,h).json();r=classify(client,h,d).json()
    assert r['status']=='error' and not r['applied'] and not r['ready']
    assert saved(client,h).json()['groups']==[] and client.get('/api/compare?user_id=1',headers=h).json()==ae


def test_two_model_calls_can_agree_wrongly_and_are_not_marked_truth():
    obj,index,inventory,primary=inputs()
    r=ea.audit_membership_envelope(primary,obj,index,inventory,lambda *a:assessment(index,('supported',)*3),MODEL)
    # This deliberately wrong double cites real negative text for item 2. The
    # custody/consensus contract cannot prove entailment and must say so.
    assert r['status']=='review' and r['proposal']['memberships'][1]['verdict']=='match'
    assert r['evidence_audit']['semantic_truth_verified'] is False
    assert r['requires_review'] is True


def test_all_unsupported_audit_rows_receive_no_apply_token(client,monkeypatch):
    h=headers(client);staged_model(monkeypatch);original=ii.make_induction_infer
    def make(*args,**kw):
        infer,provenance,calls=original(*args,**kw)
        def unsupported(payload,schema):
            if 'assessments' not in schema['required']:return infer(payload,schema)
            raw={'assessments':[{'item_id':r['item_id'],'assessment':'not_stated',
                'field':'','quote':'','reason':'Required attribute absent.'} for r in payload['catalogue']]}
            calls.append({'raw_http_response':deepcopy(raw)});return raw
        return unsupported,provenance,calls
    monkeypatch.setattr(ii,'make_induction_infer',make)
    d=preview(client,h).json();r=classify(client,h,d).json()
    assert r['status']=='clarify' and not r['ready'] and not r['applied'] and 'plan_id' not in r
    assert len(r['unknown_ids'])==8 and saved(client,h).json()['groups']==[]
