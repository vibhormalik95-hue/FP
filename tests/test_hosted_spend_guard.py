"""Offline simulated prices/counter/provider only. Not verified live billing."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import io
import json
import shutil
import threading
import subprocess
import sys
from pathlib import Path
import pytest

from feedctrl import model_adapters as ma
from feedctrl.hosted_spend_guard import DurableHostedSpendGuard as Guard, canonical, validate_policy
from feedctrl.controls import ParserOperationalError

SCHEMA={'type':'object','required':['ok'],'properties':{'ok':{'type':'boolean'}},'additionalProperties':False}
def payload(n):return {'system':'Offline test only.','request':f'Synthetic budget fixture {n}'}
def body(n):
    p=payload(n)
    return {'model':'gpt-6.1-sol','store':False,'stream':False,'service_tier':'default',
        'reasoning':{'effort':'medium'},'max_output_tokens':4096,
        'input':[{'role':'system','content':p['system']},{'role':'user','content':canonical({'request':p['request']}).decode()}],
        'text':{'format':{'type':'json_schema','name':'feed_control','strict':True,'schema':SCHEMA}}}
def sha(b):return hashlib.sha256(b).hexdigest()
def policy():
    return {'run_id':'offline-contract-run','model':'gpt-6.1-sol','reasoning_effort':'medium',
        'allowed_request_sha256':[sha(canonical(body(1))),sha(canonical(body(2)))],
        'max_input_tokens':16000,'max_output_tokens':4096,
        'input_usd_per_million':'5','output_usd_per_million':'10',
        'counter_upper_micro_usd':1000,'other_upper_micro_usd':1000,
        'price_evidence_sha256':'a'*64,'counter_evidence_sha256':'b'*64,'account_evidence_sha256':'c'*64}
def counter(calls):
    def count(request):
        calls.append(request)
        return {'request_sha256':sha(request),'model':'gpt-6.1-sol','input_tokens':42,
                'counter_receipt_sha256':'d'*64}
    return count
def response(**kw):
    return {'model':'gpt-6.1-sol','service_tier':'default','status':'completed','error':None,
        'incomplete_details':None,'usage':{'input_tokens':42,'output_tokens':9},
        'output':[{'type':'message','role':'assistant','status':'completed',
                   'content':[{'type':'output_text','text':'{"ok":true}'}]}],**kw}
class FakeResponse(io.BytesIO):
    status=200;headers={}
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
def make_adapter(monkeypatch,guard,sent,result=None,error=None):
    class Opener:
        def open(self,request,**kw):
            sent.append(request.data)
            if error:raise error
            return FakeResponse(canonical(result if result is not None else response()))
    monkeypatch.setattr(ma.urllib.request,'build_opener',lambda *a:Opener())
    return ma.make_openai_responses_infer(api_key='OFFLINE-DUMMY-NOT-A-CREDENTIAL',
        model='gpt-6.1-sol',reasoning_effort='medium',run_budget=ma.HostedRunBudget(2),
        authorized=True,spend_guard=guard)

def test_reservation_commits_before_counter_and_uses_extra_durability(tmp_path):
    path=tmp_path/'run.sqlite';p=policy();observed=[]
    def count(request):
        reopened=Guard.open_existing(path,p,counter([]))
        snapshot=reopened.snapshot();assert snapshot['reserved_micro_usd']==250000
        assert snapshot['attempts'][0]['state']=='reserved'
        with reopened._connection() as db:
            assert db.execute('PRAGMA synchronous').fetchone()[0]==3
            assert db.execute('PRAGMA journal_mode').fetchone()[0]=='delete'
        observed.append(True);return counter([])(request)
    guard=Guard.create_new(path,p,count)
    ticket=guard.before_send(canonical(body(1)))
    assert observed==[True]
    assert ticket['upper_micro_usd']==42*5+4096*10+2000
    guard.complete(ticket,response())
    assert guard.snapshot()['reserved_micro_usd']==250000

def test_fixed_allowance_survives_new_adapters_and_restarts(tmp_path,monkeypatch):
    path=tmp_path/'run.sqlite';p=policy();count_calls=[];sent=[]
    first=Guard.create_new(path,p,counter(count_calls))
    infer,_,_=make_adapter(monkeypatch,first,sent)
    assert infer(payload(1),SCHEMA)=={'ok':True}
    second=Guard.open_existing(path,p,counter(count_calls))
    infer,_,_=make_adapter(monkeypatch,second,sent)
    assert infer(payload(2),SCHEMA)=={'ok':True}
    third=Guard.open_existing(path,p,counter(count_calls))
    infer,_,receipts=make_adapter(monkeypatch,third,sent)
    with pytest.raises(ParserOperationalError):infer(payload(1),SCHEMA)
    assert len(sent)==len(count_calls)==2
    assert third.snapshot()['reserved_micro_usd']==500000
    assert receipts[0]['representation']=='preflight_only'
    with pytest.raises(ValueError):Guard.create_new(path,p,counter([]))

def test_inflight_reservation_blocks_concurrent_counter_and_cannot_resume(tmp_path):
    path=tmp_path/'run.sqlite';p=policy();started=threading.Event();release=threading.Event();calls=[]
    def count(request):
        calls.append(request);started.set();assert release.wait(5)
        return counter([])(request)
    first=Guard.create_new(path,p,count);second=Guard.open_existing(path,p,counter(calls))
    with ThreadPoolExecutor(2) as pool:
        future=pool.submit(first.before_send,canonical(body(1)))
        assert started.wait(5)
        with pytest.raises(ParserOperationalError):second.before_send(canonical(body(2)))
        release.set();ticket=future.result()
    assert len(calls)==1
    restarted=Guard.open_existing(path,p,counter(calls))
    with pytest.raises(ParserOperationalError):restarted.before_send(canonical(body(2)))
    assert restarted.snapshot()['attempts'][0]['state']=='counted'
    first.complete(ticket,response())

@pytest.mark.parametrize('mutation',[lambda p:p.update(request_sha256='0'*64),
    lambda p:p.update(model='different'),lambda p:p.update(input_tokens=True),
    lambda p:p.update(input_tokens=0),lambda p:p.update(input_tokens=16001),
    lambda p:p.pop('counter_receipt_sha256')])
def test_invalid_counter_proof_burns_reservation_and_never_generates(tmp_path,monkeypatch,mutation):
    calls=[];sent=[]
    def count(request):
        proof=counter(calls)(request);mutation(proof);return proof
    guard=Guard.create_new(tmp_path/'run.sqlite',policy(),count)
    infer,_,_=make_adapter(monkeypatch,guard,sent)
    with pytest.raises(ParserOperationalError):infer(payload(1),SCHEMA)
    assert sent==[] and len(calls)==1
    assert guard.snapshot()['blocked'] and guard.snapshot()['reserved_micro_usd']==250000
    with pytest.raises(ParserOperationalError):infer(payload(2),SCHEMA)
    assert len(calls)==1 and sent==[]

def test_counter_failure_and_provider_timeout_never_refund(tmp_path,monkeypatch):
    def fail(_):raise TimeoutError('offline-counter-timeout')
    first=Guard.create_new(tmp_path/'count.sqlite',policy(),fail);sent=[]
    infer,_,_=make_adapter(monkeypatch,first,sent)
    with pytest.raises(ParserOperationalError):infer(payload(1),SCHEMA)
    assert first.snapshot()['blocked'] and first.snapshot()['reserved_micro_usd']==250000 and sent==[]
    second=Guard.create_new(tmp_path/'provider.sqlite',policy(),counter([]))
    infer,_,_=make_adapter(monkeypatch,second,sent,error=TimeoutError('offline-provider-timeout'))
    with pytest.raises(ParserOperationalError):infer(payload(1),SCHEMA)
    assert len(sent)==1 and second.snapshot()['blocked'] and second.snapshot()['reserved_micro_usd']==250000

@pytest.mark.parametrize('result',[response(service_tier='priority'),response(model='different'),
    response(usage={'input_tokens':43,'output_tokens':9}),
    response(usage={'input_tokens':42,'output_tokens':4097})])
def test_unexpected_paid_response_blocks_run_and_retains_slot(tmp_path,monkeypatch,result):
    guard=Guard.create_new(tmp_path/'run.sqlite',policy(),counter([]));sent=[]
    infer,_,_=make_adapter(monkeypatch,guard,sent,result=result)
    with pytest.raises(ParserOperationalError):infer(payload(1),SCHEMA)
    assert len(sent)==1 and guard.snapshot()['blocked']
    with pytest.raises(ParserOperationalError):infer(payload(2),SCHEMA)
    assert len(sent)==1

def test_missing_corrupt_partial_or_cloned_ledger_never_recreates(tmp_path):
    p=policy();path=tmp_path/'run.sqlite'
    with pytest.raises(ParserOperationalError):Guard.open_existing(path,p,counter([]))
    assert not path.exists()
    Guard.create_new(path,p,counter([]));clone=tmp_path/'clone.sqlite';shutil.copyfile(path,clone)
    with pytest.raises(ValueError):Guard.open_existing(clone,p,counter([]))
    path.write_bytes(b'corrupt retained test ledger')
    with pytest.raises(ParserOperationalError):Guard.open_existing(path,p,counter([]))
    with pytest.raises(ValueError):Guard.create_new(path,p,counter([]))
    partial=tmp_path/'partial.sqlite';partial.write_bytes(b'')
    with pytest.raises(ParserOperationalError):Guard.open_existing(partial,p,counter([]))

@pytest.mark.parametrize('change',[{'counter_upper_micro_usd':None},{'counter_upper_micro_usd':200000},
    {'other_upper_micro_usd':250000},{'input_usd_per_million':'1'},
    {'counter_evidence_sha256':''},{'model':'gpt-6-astra'},{'max_output_tokens':4097}])
def test_unproven_or_excessive_policy_is_rejected_before_file_creation(tmp_path,change):
    p=policy();p.update(change);path=tmp_path/'run.sqlite'
    with pytest.raises(ValueError):Guard.create_new(path,p,counter([]))
    assert not path.exists()

def test_request_change_rejected_before_counter_or_reservation(tmp_path):
    calls=[];guard=Guard.create_new(tmp_path/'run.sqlite',policy(),counter(calls))
    for change in ({'service_tier':'priority'},{'tools':[]},{'previous_response_id':'unapproved'},{'max_output_tokens':5000}):
        b=body(1);b.update(change)
        with pytest.raises(ValueError):guard.before_send(canonical(b))
    with pytest.raises(ValueError):guard.before_send(canonical(body(1))+b'\n')
    assert calls==[] and guard.snapshot()['reserved_micro_usd']==0

def test_policy_copies_cannot_change_locked_evidence(tmp_path):
    p=policy();guard=Guard.create_new(tmp_path/'run.sqlite',p,counter([]))
    p['model']='changed';exposed=guard.policy;exposed['model']='changed'
    assert guard.policy['model']=='gpt-6.1-sol'

def test_exact_rational_rounding_is_upward(tmp_path):
    p=policy();p.update(input_usd_per_million='11/2',output_usd_per_million='21/2',max_output_tokens=17)
    b=body(1);b['max_output_tokens']=17;p['allowed_request_sha256']=[sha(canonical(b))]
    def count(request):return {'request_sha256':sha(request),'model':p['model'],'input_tokens':2,'counter_receipt_sha256':'d'*64}
    guard=Guard.create_new(tmp_path/'run.sqlite',p,count)
    assert guard.before_send(canonical(b))['upper_micro_usd']==2190

def test_separate_processes_cannot_replenish_or_race_an_inflight_slot(tmp_path):
    path=tmp_path/'run.sqlite';p=policy()
    guard=Guard.create_new(path,p,counter([]))
    script='''import hashlib,json,sys
from feedctrl.hosted_spend_guard import DurableHostedSpendGuard,canonical
from feedctrl.controls import ParserOperationalError
path,policy,body=sys.argv[1:]
def counter(request):
 return {'request_sha256':hashlib.sha256(request).hexdigest(),'model':'gpt-6.1-sol','input_tokens':42,'counter_receipt_sha256':'d'*64}
guard=DurableHostedSpendGuard.open_existing(path,json.loads(policy),counter)
try:
 guard.before_send(canonical(json.loads(body)))
 print(json.dumps({'reserved':True}))
except ParserOperationalError:
 print(json.dumps({'reserved':False}))
'''
    processes=[subprocess.Popen([sys.executable,'-c',script,str(path),json.dumps(p),json.dumps(body(n))],
        cwd=Path(__file__).resolve().parents[1],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for n in (1,2)]
    outputs=[]
    for process in processes:
        out,err=process.communicate(timeout=15)
        assert process.returncode==0,err
        outputs.append(json.loads(out)['reserved'])
    assert sorted(outputs)==[False,True]
    assert guard.snapshot()['reserved_micro_usd']==250000
    assert len(guard.snapshot()['attempts'])==1
    with pytest.raises(ParserOperationalError):guard.before_send(canonical(body(2)))
