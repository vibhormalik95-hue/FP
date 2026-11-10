"""Authored, in-process fixtures only: no transport, model or network execution."""
from copy import deepcopy
from unittest.mock import patch
import unittest
import io
import json
from fastapi import HTTPException
from feedctrl.api import Request
from feedctrl.api import create_app
from feedctrl.claude_personal_app import shared_personal_factories, create_claude_personal_app
from feedctrl.hosted_app import shared_factories, create_openai_hosted_app
from feedctrl.model_adapters import HostedRunBudget, make_openai_responses_infer
from feedctrl.controls import ParserOperationalError
from feedctrl import synthetic_drafts as sd

IDENTITY={'backend':'openai-responses','model':'offline-model','digest':'offline-config'}
PERSONAL={**IDENTITY,'backend':'claude-code-personal-cli'}
RAW={'title':'Imagined harbor','description':'A fictional harbor under a violet sky.','category_label':'Imaginary places'}
BRIEF='Imagine a fictional harbor.'

class Response:
    def __init__(self, value=None, status=200): self.value, self.status_code=value,status
    def json(self): return deepcopy(self.value)

class DirectClient:
    """Invoke application routes in process; no ASGI server, socket, or browser."""
    def __init__(self, app): self.app=app
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def endpoint(self,path): return next(r.endpoint for r in self.app.routes if getattr(r,'path',None)==path)
    def get(self,path,headers):
        name=path.split('?')[0]; token=headers['X-Session-ID']
        if name=='/api/compare': return Response(self.endpoint(name)(1,10,token))
        return Response(self.endpoint(name)(1,token))
    def post(self,path,headers=None,json=None):
        try:
            if path=='/api/session': return Response(self.endpoint(path)(),201)
            cls={'/api/synthetic/preview':sd.DraftRequest,'/api/synthetic/admit':sd.Admission,
                 '/api/synthetic/remove':sd.Removal,'/api/synthetic/restore/preview':sd.User,
                 '/api/reset':Request}[path]
            return Response(self.endpoint(path)(cls(**json),headers['X-Session-ID']))
        except HTTPException as e: return Response({'detail':e.detail},e.status_code)

def client(factory=None):
    return DirectClient(create_app(fixture=True, allow_local_models=False, synthetic_infer_factory=factory))

def setup(c): return {'X-Session-ID': c.post('/api/session',json={}).json()['session_id']}
def post(c,h,path,**body): return c.post('/api/'+path,headers=h,json={'user_id':1,**body})
def items(c,h): return c.get('/api/synthetic/items?user_id=1',headers=h).json()
def preview(c,h): return post(c,h,'synthetic/preview',brief=BRIEF,synthetic_acknowledged=True)
def admit(c,h,p): return post(c,h,'synthetic/admit',plan_id=p['plan_id'])

def lifecycle(binding,identity):
    seen=[]
    def infer(payload,schema):
        seen.append(deepcopy((payload,schema))); return deepcopy(RAW)
    sem,cat=binding(infer,identity)
    with patch('feedctrl.synthetic_drafts.make_draft_infer',side_effect=AssertionError('No local fallback')), client(sem) as c:
        h=setup(c); before=c.get('/api/compare?user_id=1',headers=h).json()
        src=deepcopy((c.app.state.demo.items,c.app.state.demo.categories,c.app.state.demo.topic_index))
        state=items(c,h); assert state['generation_available'] and state['configured_model']==identity['model'] and state['generation_provider']==identity['backend']
        p=preview(c,h).json(); assert p['ready'] and not p['admitted']
        assert items(c,h)['items']==[] and c.get('/api/compare?user_id=1',headers=h).json()==before
        assert seen==[({'system':sd.PROMPT,'brief':BRIEF},sd.SCHEMA)]
        assert p['draft']['provenance']['raw_output']==RAW and p['draft']['provenance']['model']==identity
        assert p['model_calls'][0]['raw_output']==RAW
        a=admit(c,h,p).json(); record=a['items'][0]
        assert a['admitted'] and a['feed']['items'][0]['score']==0 and not a['feed']['uses_trained_scorer']
        assert (c.app.state.demo.items,c.app.state.demo.categories,c.app.state.demo.topic_index)==src
        assert c.get('/api/compare?user_id=1',headers=h).json()==before
        assert post(c,h,'synthetic/remove',item_id=record['item_id']).json()['items']==[]
        restore=post(c,h,'synthetic/restore/preview').json()
        assert restore['ready'] and restore['replayed_removed_record'] and restore['model_calls']==[] and items(c,h)['items']==[]
        restored=admit(c,h,restore).json()['items'][0]
        assert restored['item_id']==record['item_id'] and restored['provenance']==record['provenance'] and len(seen)==1
        assert post(c,h,'reset').status_code==200 and items(c,h)['items']==[]

def failure_case(case):
    called=[]; holder={}
    def infer(payload,schema):
        called.append(True)
        if case=='provider_error': raise ParserOperationalError('returned wrong model')
        if case=='malformed': return {'title':'bad'}
        if case=='oversize': return {**RAW,'title':'x'*121}
        if case=='stale': holder['client'].app.state.demo.items[1]=['changed']
        return RAW
    identity={**IDENTITY,'backend':'untrusted-provider' if case=='wrong_provider' else IDENTITY['backend']}
    factory=None if case=='absent' else lambda:(infer,identity)
    with patch('feedctrl.synthetic_drafts.make_draft_infer',side_effect=AssertionError('No local fallback')), client(factory) as c:
        holder['client']=c; h=setup(c); result=preview(c,h)
        if case in ('absent','stale'): assert result.status_code in (403,409)
        else: assert result.status_code==200 and not result.json()['ready']
        assert items(c,h)['items']==[]
        assert len(called)==(0 if case in ('absent','wrong_provider') else 1)
        assert post(c,h,'synthetic/admit',plan_id='not-a-plan').status_code==409

def shared_budget(binding,identity):
    budget=HostedRunBudget(3); calls=[]
    def infer(payload,schema):
        budget.reserve(); calls.append(deepcopy(payload)); return RAW
    sem,cat=binding(infer,identity)
    sem()[0]({'system':'indirect'}, {'type':'object'})
    cat()[0]({'instructions':'category'}, {'type':'object'})
    with client(sem) as c:
        h=setup(c); assert preview(c,h).json()['ready']
        assert not preview(c,h).json()['ready']
        assert budget.attempted==3 and len(calls)==3 and items(c,h)['items']==[]
        assert calls[-1]=={'system':sd.PROMPT,'brief':BRIEF}

def constructors():
    for kind in ('openai','personal'):
        identity=IDENTITY if kind=='openai' else PERSONAL
        transport='feedctrl.hosted_app.make_openai_responses_infer' if kind=='openai' else 'feedctrl.claude_personal_app.make_claude_personal_infer'
        with patch(transport,return_value=(lambda payload,schema:deepcopy(RAW),identity,[])), patch('feedctrl.synthetic_drafts.make_draft_infer',side_effect=AssertionError('No local fallback')):
            if kind=='openai':
                app=create_openai_hosted_app(api_key='placeholder',model='offline',reasoning_effort='medium',run_budget=HostedRunBudget(1),spend_guard=object(),fixture=True)
            else:
                app=create_claude_personal_app(operator_token='a'*32,allowed_origin='http://127.0.0.1:8000',fixture=True)
            # Call route directly to avoid bypassing or changing personal boundary policy.
            def route(path):return next(r.endpoint for r in app.routes if getattr(r,'path',None)==path)
            sid=route('/api/session')()['session_id']
            p=route('/api/synthetic/preview')(sd.DraftRequest(user_id=1,brief=BRIEF,synthetic_acknowledged=True),sid)
            assert p['ready'] and p['draft']['provenance']['model']==identity

def wrong_model_transport():
    """Run the real adapter against an in-memory fake response, never a socket."""
    sent=[]
    envelope={'model':'wrong-model','status':'completed','error':None,'incomplete_details':None,
              'output':[{'type':'message','role':'assistant','status':'completed',
                         'content':[{'type':'output_text','text':json.dumps(RAW)}]}]}
    class FakeResponse(io.BytesIO):
        status=200
        headers={'x-request-id':'offline-fixture'}
        def __enter__(self): return self
        def __exit__(self,*args): self.close()
    class FakeOpener:
        def open(self,request,**kwargs):
            sent.append(json.loads(request.data))
            return FakeResponse(json.dumps(envelope).encode())
    with patch('feedctrl.model_adapters.urllib.request.build_opener',return_value=FakeOpener()):
        infer,identity,receipts=make_openai_responses_infer(
            api_key='offline-placeholder',model='offline-model',reasoning_effort='medium',
            run_budget=HostedRunBudget(1),authorized=True)
        factory,_=shared_factories(infer,identity)
        with patch('feedctrl.synthetic_drafts.make_draft_infer',side_effect=AssertionError('No fallback')), client(factory) as c:
            h=setup(c); p=preview(c,h).json()
            assert not p['ready'] and items(c,h)['items']==[]
            assert post(c,h,'synthetic/admit',plan_id='not-a-plan').status_code==409
        assert len(sent)==len(receipts)==1 and receipts[0]['outcome']=='error'
        assert receipts[0]['raw_response']==envelope
        assert sent[0]['input']==[{'role':'system','content':sd.PROMPT},
                                  {'role':'user','content':json.dumps({'brief':BRIEF},separators=(',',':'),ensure_ascii=False)}]
        assert sent[0]['text']['format']['schema']==sd.SCHEMA

class HostedSyntheticOfflineTests(unittest.TestCase):
    def test_openai_lifecycle(self): lifecycle(shared_factories,IDENTITY)
    def test_personal_lifecycle(self): lifecycle(shared_personal_factories,PERSONAL)
    def test_failure_cases(self):
        for case in ('absent','provider_error','malformed','oversize','wrong_provider','stale'):
            with self.subTest(case=case): failure_case(case)
    def test_openai_shared_budget(self): shared_budget(shared_factories,IDENTITY)
    def test_personal_shared_budget(self): shared_budget(shared_personal_factories,PERSONAL)
    def test_constructors(self): constructors()
    def test_wrong_model_real_adapter(self): wrong_model_transport()

if __name__ == '__main__': unittest.main(verbosity=2)
