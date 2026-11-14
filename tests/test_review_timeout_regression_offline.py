"""Guarded synthetic timeout and review-window tests; no native or model calls."""
import sys,unittest,types,threading,contextlib,math
from pathlib import Path
from unittest import mock
events=[]
def guard(event,args):
 if event.startswith('socket.') or event in {'subprocess.Popen','os.system','os.spawn','os.exec','os.startfile','ctypes.dlopen'} or (event=='import' and args and (str(args[0]).split('.')[0] in {'anthropic','openai','ollama','torch','transformers','uvicorn'} or str(args[0])=='feedctrl.windows_job_native')):
  events.append(event);raise RuntimeError('blocked offline operation')
sys.addaudithook(guard)
from feedctrl import windows_job_runner as runner,staged_routes as routes,claude_personal as personal
class Clock:
 def __init__(self,value=0):self.value=value
 def now(self):return self.value
 def sleep(self,seconds):self.value+=max(seconds,100)
class FakeRun:
 def __init__(self,clock,finish_at):self.clock=clock;self.finish_at=finish_at;self.calls=[]
 def poll(self,remaining):
  self.calls.append('poll')
  return (b'',True,True,0,0) if self.clock.value>=self.finish_at else (b'',True,False,None,1)
 def terminate(self):self.calls.append('terminate')
 def cleanup_complete(self):self.calls.append('cleanup');return True
 def finish_io(self,deadline):self.calls.append('finish_io');return True
 def check_io(self):self.calls.append('check_io')
 def close(self):self.calls.append('close')
class Backend:
 def __init__(self,clock,finish_at):self.run=FakeRun(clock,finish_at);self.calls=0
 def launch(self,*args):self.calls+=1;return self.run
class FakeApp:
 def __init__(self):self.endpoints={}
 def post(self,path):
  def register(fn):self.endpoints[path]=fn;return fn
  return register
class Provider:
 def __init__(self):self.calls=[]
 def require_available(self):pass
 def stage(self,name,model,**kwargs):self.calls.append(name);return (lambda *_:None),{'model_id':'synthetic'},[]
class RouteHarness:
 def __init__(self,age=0,member_seconds=600,audit_seconds=600,mutate=None):
  self.clock=Clock(1000);self.provider=Provider();self.demo=types.SimpleNamespace(lock=threading.RLock(),items={1:{},2:{}},topic_index={});self.audit_calls=0;self.member_seconds=member_seconds;self.audit_seconds=audit_seconds;self.mutate=mutate
  body={'user_id':1,'candidate_ids':[1,2],'objective':'synthetic','operation':'exclude','strength':'none','mode':'merge'}
  pending={'id':'synthetic-plan','created':1000-age,'revision':0,'nonce':'synthetic-nonce','session_id':'synthetic-session','body':body,'definition':{'provenance':{'model_id':'synthetic'}},'eligible_sha256':routes._digest([1,2]),'definition_model_calls':[],'used':False}
  pending['binding_sha256']=routes._digest({k:pending[k] for k in ('id','created','revision','nonce','body','definition','eligible_sha256','definition_model_calls','session_id')})
  self.state={'semantic_definition_pending':pending,'semantic_revision':0,'semantic_preview_nonce':'synthetic-nonce','semantic_groups':[]};self.app=FakeApp()
 def run(self):
  state=self.state;clock=self.clock
  def classify(*_args):
   clock.value+=self.member_seconds
   if self.mutate=='revision':state['semantic_revision']+=1
   if self.mutate=='nonce':state['semantic_preview_nonce']='superseded'
   return {'status':'review'}
  def audit_model(*_args):self.audit_calls+=1;clock.value+=self.audit_seconds;return {'status':'review','proposal':{'label':'synthetic'}}
  def review(_state,_user,_groups,**_kwargs):state['semantic_pending']={};return {'ready':True}
  fake_time=types.SimpleNamespace(monotonic=clock.now,time=lambda:0)
  with contextlib.ExitStack() as stack:
   for obj,name,value in [(routes,'time',fake_time),(routes,'scoped_index',lambda *_:{'items':{1:{},2:{}}}),(routes.ii,'projected_inventory',lambda *_:[]),(routes.staged,'revalidate_definition',lambda *_:None),(routes.staged,'classify_definition',classify),(routes.evidence_audit,'audit_membership_envelope',audit_model),(routes.staged,'revalidate_membership_envelope',lambda *_:None),(routes.ii,'category_as_control',lambda *_:{'induction':{}}),(routes,'seal_group',lambda *_:{'label':'synthetic'})]:stack.enter_context(mock.patch.object(obj,name,value))
   routes.install_staged_routes(self.app,self.demo,lambda *_:state,review,evidence_context=lambda *_:None,category_provider=self.provider)
   return self.app.endpoints['/api/semantic/definition/classify'](routes.DefinitionApproval(user_id=1,plan_id='synthetic-plan',evidence_reviewed=True),'synthetic-session')
class Tests(unittest.TestCase):
 def test_timeout_600_completes_at_500_fake_seconds(self):
  clock=Clock();backend=Backend(clock,500);result=runner.run_with_backend(['fake'],b'',{},'fake',600,100,backend=backend,now=clock.now,sleep=clock.sleep);self.assertEqual(result,(0,b''));self.assertEqual(backend.calls,1);self.assertEqual(backend.run.calls[-4:],['cleanup','finish_io','check_io','close'])
 def test_timeout_cleans_up_without_retry(self):
  clock=Clock();backend=Backend(clock,999)
  with self.assertRaises(TimeoutError):runner.run_with_backend(['fake'],b'',{},'fake',600,100,backend=backend,now=clock.now,sleep=clock.sleep)
  self.assertEqual(backend.calls,1);self.assertEqual(backend.run.calls[-4:],['terminate','cleanup','finish_io','close'])
 def test_timeout_invalid_values_fail_before_launch(self):
  for t in [0,-1,600.01,True,float('nan'),float('inf')]:
   clock=Clock();b=Backend(clock,0)
   with self.subTest(timeout=t):
    with self.assertRaises(ValueError):runner.run_with_backend(['fake'],b'',{},'fake',t,100,backend=b,now=clock.now,sleep=clock.sleep)
    self.assertEqual(b.calls,0)
 def test_existing_freshness_window_and_fixed_inflight_bound(self):
  self.assertTrue(routes._within_review_window(1000,1300));self.assertFalse(routes._within_review_window(1000,1300.001));self.assertTrue(routes._within_review_window(1000,2200,inflight_deadline=2230));self.assertFalse(routes._within_review_window(1000,2230.001,inflight_deadline=2230))
 def test_inflight_membership_and_audit_do_not_expire_initial_review(self):
  h=RouteHarness();result=h.run();self.assertTrue(result['ready']);self.assertEqual(h.provider.calls,['membership','evidence_audit']);self.assertEqual(h.audit_calls,1)
 def test_initial_review_still_expires_before_calls(self):
  h=RouteHarness(age=301)
  with self.assertRaises(routes.HTTPException) as e:h.run()
  self.assertEqual(e.exception.status_code,409);self.assertEqual(h.provider.calls,[])
 def test_inflight_deadline_fails_before_audit(self):
  h=RouteHarness(member_seconds=1231);r=h.run();self.assertFalse(r['ready']);self.assertEqual(h.provider.calls,['membership']);self.assertEqual(h.audit_calls,0)
 def test_inflight_deadline_fails_after_audit_without_preview(self):
  h=RouteHarness(member_seconds=600,audit_seconds=631);r=h.run();self.assertFalse(r['ready']);self.assertEqual(h.provider.calls,['membership','evidence_audit']);self.assertEqual(h.audit_calls,1);self.assertNotIn('semantic_pending',h.state)
 def test_revision_and_nonce_drift_still_fail_before_audit(self):
  for field in ['revision','nonce']:
   with self.subTest(field=field):
    h=RouteHarness(mutate=field);r=h.run();self.assertFalse(r['ready']);self.assertEqual(h.provider.calls,['membership']);self.assertEqual(h.audit_calls,0)
 def test_personal_adapter_accepts_600_rejects_invalid_without_calling_runner(self):
  invoked=[]
  for value in [600,600.01,True,0,float('nan')]:
   cfg={'executable':str(Path.cwd()/'synthetic-cli'),'workdir':str(Path.cwd()),'model':'claude-fable-5-2','effort':'max','run_budget':personal.HostedRunBudget(3),'estimated_per_invocation_usd':5.0,'output_mode':'plain_json','runtime_authorized':True,'data_authorized':True,'subscription_and_usage_authorized':True,'executable_reviewed':True,'managed_runtime_reviewed':True,'process_containment_reviewed':True,'reviewed_cli_version':'2.1.321','max_output_tokens':16384,'timeout':value,'process_runner':lambda *_:invoked.append(True)}
   with self.subTest(timeout=value):
    if value==600 and type(value) is int:personal.make_claude_personal_infer(**cfg)
    else:
     with self.assertRaises(ValueError):personal.make_claude_personal_infer(**cfg)
  self.assertEqual(invoked,[])
 def test_no_guard_events(self):self.assertEqual(events,[])
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests));print('Guard events:',events);sys.exit(not result.wasSuccessful() or bool(events))
