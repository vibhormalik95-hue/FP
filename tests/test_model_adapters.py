"""Offline provider contracts. Every network response here is a test double."""
import base64
from copy import deepcopy
import io
import json
import urllib.error
import pytest

from feedctrl import model_adapters as ma
from feedctrl import semantic_review as sr
from feedctrl.api import create_app
from feedctrl.controls import ParserOperationalError
from fastapi.testclient import TestClient
from test_semantic_review import client, headers, saved

SCHEMA = {'type':'object','required':['ok'],'additionalProperties':False,
          'properties':{'ok':{'type':'boolean'}}}
PAYLOAD = {'system':'Return the schema only.', 'request':'Synthetic transport check'}


def envelope(text='{"ok":true}', **kw):
    return {'model':'gpt-6.1-sol','status':'completed','error':None,'incomplete_details':None,
        'usage':{'input_tokens':42,'output_tokens':9},'output':[
        {'type':'reasoning','summary':[]}, {'type':'message','role':'assistant','status':'completed',
         'content':[{'type':'output_text','text':text}]}], **kw}


class Response(io.BytesIO):
    status = 200
    headers = {'x-request-id':'synthetic-provider-request'}
    def __enter__(self):return self
    def __exit__(self,*args):self.close()


def adapter(monkeypatch, result=None, *, error=None, **kw):
    sent=[]
    class Opener:
        def open(self, request, **options):
            sent.append((request, options))
            if error:raise error
            raw = json.dumps(result if result is not None else envelope()).encode()
            return Response(raw)
    monkeypatch.setattr(ma.urllib.request,'build_opener',lambda *a:Opener())
    infer,provenance,receipts=ma.make_openai_responses_infer(api_key='dummy-offline-secret',
        model='gpt-6.1-sol',reasoning_effort='medium',authorized=True,**kw)
    return infer,provenance,receipts,sent


def test_constructor_requires_authorization_before_network_or_key_use(monkeypatch):
    monkeypatch.setattr(ma.urllib.request,'build_opener',lambda *a:pytest.fail('No constructor networking'))
    with pytest.raises(ValueError,match='authorization'):
        ma.make_openai_responses_infer(api_key='dummy',model='gpt-6.1-sol',reasoning_effort='medium')


def test_exact_request_identity_no_tools_no_storage_no_secret_receipt(monkeypatch):
    infer,p,r,sent=adapter(monkeypatch)
    before=deepcopy((PAYLOAD,SCHEMA))
    assert sent==[] and infer(PAYLOAD,SCHEMA)=={'ok':True}
    req,options=sent[0];body=json.loads(req.data)
    assert req.full_url==ma.ENDPOINT and options=={'timeout':90}
    assert req.get_header('Authorization')=='Bearer dummy-offline-secret'
    assert body['model']=='gpt-6.1-sol' and body['store'] is False and body['stream'] is False
    assert 'tools' not in body and body['reasoning']=={'effort':'medium'}
    assert body['text']['format']=={'type':'json_schema','name':'feed_control','strict':True,'schema':SCHEMA}
    assert [m['role'] for m in body['input']]==['system','user']
    assert (PAYLOAD,SCHEMA)==before
    assert 'dummy-offline-secret' not in json.dumps((p,r))
    assert p['digest_kind']=='configuration_sha256_not_model_weights'
    assert r[0]['usage']=={'input_tokens':42,'output_tokens':9}
    assert r[0]['provider_request_id']=='synthetic-provider-request'
    assert json.loads(base64.b64decode(r[0]['response_base64']))==envelope()


@pytest.mark.parametrize('change',[
    lambda r:r.update(status='incomplete'),lambda r:r.update(model='different-model'),
    lambda r:r.update(output=None),lambda r:r.update(error={'message':'failed'}),
    lambda r:r['output'][1].update(status='in_progress'),
    lambda r:r['output'][1].update(content=[{'type':'refusal','refusal':'No'}]),
    lambda r:r['output'].append(deepcopy(r['output'][1])),
    lambda r:r['output'][1]['content'][0].update(text='{"ok":true,"ok":false}'),
    lambda r:r['output'][1]['content'][0].update(text='{"ok":NaN}'),
    lambda r:r['output'][1]['content'][0].update(text='```json\n{"ok":true}\n```'),
    lambda r:r['output'][1]['content'][0].update(text='[]'),
])
def test_bad_outputs_retained_without_repair_retry_or_success(monkeypatch,change):
    result=envelope();change(result)
    infer,p,r,sent=adapter(monkeypatch,result)
    with pytest.raises(ParserOperationalError):infer(PAYLOAD,SCHEMA)
    assert len(sent)==len(r)==1 and r[0]['outcome']=='error'
    assert r[0]['raw_response']==result


@pytest.mark.parametrize('error',[TimeoutError('timeout'),urllib.error.URLError('offline')])
def test_transport_failure_consumes_attempt_without_retry(monkeypatch,error):
    infer,p,r,sent=adapter(monkeypatch,error=error,max_calls=1)
    with pytest.raises(ParserOperationalError):infer(PAYLOAD,SCHEMA)
    with pytest.raises(ParserOperationalError,match='budget exhausted'):infer(PAYLOAD,SCHEMA)
    assert len(sent)==len(r)==1 and r[0]['outcome']=='error'


def test_http_error_bytes_retained_but_not_echoed(monkeypatch):
    raw=b'{"error":{"message":"test provider rejection"}}'
    error=urllib.error.HTTPError(ma.ENDPOINT,429,'limit',{'x-request-id':'synthetic-limit'},io.BytesIO(raw))
    infer,p,r,sent=adapter(monkeypatch,error=error)
    with pytest.raises(ParserOperationalError) as raised:infer(PAYLOAD,SCHEMA)
    assert 'test provider rejection' not in str(raised.value)
    assert r[0]['http_status']==429 and base64.b64decode(r[0]['response_base64'])==raw


def test_receipt_mutation_cannot_reopen_consumed_budget(monkeypatch):
    infer,p,r,sent=adapter(monkeypatch,max_calls=1)
    infer(PAYLOAD,SCHEMA);r.clear()
    with pytest.raises(ParserOperationalError,match='budget exhausted'):infer(PAYLOAD,SCHEMA)
    assert len(sent)==1


def test_oversized_request_fails_before_call_without_truncation(monkeypatch):
    infer,p,r,sent=adapter(monkeypatch,max_request_bytes=20)
    with pytest.raises(ValueError,match='budget'):infer(PAYLOAD,SCHEMA)
    assert not r and not sent


def test_redirect_handler_fails_closed():
    with pytest.raises(ParserOperationalError):ma._NoRedirect().redirect_request(None,None,302,'',{},'https://example.com')


def configured_request(c,h,**kw):
    return c.post('/api/semantic/preview',headers=h,json={'user_id':1,'text':'Hide what makes me hungry',
        'label':'Offline contract group','candidate_ids':list(range(1,9)),
        'backend':'configured_model','action_source':'model',**kw})


def test_unconfigured_provider_fails_closed_and_never_uses_ollama(client,monkeypatch):
    monkeypatch.setattr(sr,'make_local_ollama_infer',lambda *a,**k:pytest.fail('No fallback'))
    h=headers(client);before=saved(client,h).json()
    assert before['external_adapter_available'] is False
    result=configured_request(client,h)
    assert result.status_code==502 and 'No authorized configured' in result.json()['detail']
    assert saved(client,h).json()==before


def test_configured_provider_real_api_mechanics_with_offline_double(client):
    # New app instance, same unit-test metadata. No hosted or local inference runs.
    trace=[]
    def infer(payload,schema):
        trace.append(deepcopy((payload,schema)))
        if 'control' in schema['required']:
            return {'needs_clarification':False,'question':'','control':'exclude/none','intent_span':'makes me hungry'}
        return {'status':'propose','reason':'Synthetic test-double membership, no accuracy claim',
            'negation_resolved':True,'alternatives':[],
            'evidence':[{'item_id':3,'field':'caption','quote':'Freshly baked bread'}]}
    provenance={'backend':'offline-contract-double','model':'not-a-real-model','digest':'test-config',
                'digest_kind':'configuration_sha256_not_model_weights'}
    app=create_app(fixture=True,semantic_infer_factory=lambda:(infer,provenance))
    app.state.demo.topic_index=deepcopy(client.app.state.demo.topic_index)
    with TestClient(app) as c:
        h=headers(c);other=headers(c);before=saved(c,h).json()
        ae=c.get('/api/compare?user_id=1',headers=h).json()
        p=configured_request(c,h).json()
        assert len(trace)==2 and p['ready'] and not p['applied']
        assert p['proposal']['provenance']['model']==provenance
        assert saved(c,h).json()==before
        assert c.post('/api/semantic/apply',headers=other,json={'user_id':1,'plan_id':p['plan_id']}).status_code==409
        result=c.post('/api/semantic/apply',headers=h,json={'user_id':1,'plan_id':p['plan_id']}).json()
        assert result['applied'] and result['feed']['available_items']==35
        undo=c.post('/api/semantic/history/preview',headers=h,json={'user_id':1,'action':'undo'}).json()
        c.post('/api/semantic/apply',headers=h,json={'user_id':1,'plan_id':undo['plan_id']}).raise_for_status()
        assert saved(c,h).json()['groups']==[]
        assert c.get('/api/compare?user_id=1',headers=h).json()==ae


@pytest.mark.parametrize('backend,action_source',[('configured_model','manual'),('configured_model','ollama'),('ollama','model')])
def test_mislabelled_provider_action_rejected(client,backend,action_source):
    h=headers(client);before=saved(client,h).json()
    r=configured_request(client,h,backend=backend,action_source=action_source).json()
    assert r['status']=='error' and not r['ready']
    assert saved(client,h).json()==before
