"""Actual direct app routes, authored responses and fake Windows backend only."""
import csv,hashlib,importlib.util,json,os,sys,tempfile,unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent
ACT_VALUE=os.environ.get('COMP_OFFLINE_CURATED_ACTIVATOR')
if ACT_VALUE:
 ACT=Path(ACT_VALUE);assert hashlib.sha256(ACT.read_bytes()).hexdigest()=='e1ca525c4ea0743f9c7c1a3e964b3f719740c5e141d318dac3bf8d6f924fcaf3'
elif not (os.environ.get('COMP_OFFLINE_USE_STANDARD_SITE')=='1' and sys.flags.isolated and not sys.flags.no_site and sys.prefix!=sys.base_prefix):
 raise RuntimeError('explicit isolated venv or reviewed curated activator required')
BLOCKED=[]
def guard(event,args):
 if (event.startswith('socket.') or event in {'subprocess.Popen','os.system','os.spawn','os.exec','os.fork','ctypes.dlopen'} or (event=='import' and args and (str(args[0]).split('.')[0] in {'anthropic','openai','ollama','torch','transformers'} or args[0]=='feedctrl.windows_job_native'))):
  BLOCKED.append(event);raise RuntimeError('offline_blocked')
sys.addaudithook(guard)
if ACT_VALUE:
 spec=importlib.util.spec_from_file_location('curated_runtime',ACT);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);mod.activate()
sys.path.insert(0,str(ROOT))
from diagnostic import app_binding,qualification as q,diagnostic_transport as transport,flow_guard
from feedctrl import windows_job_runner as windows
from feedctrl.semantic_controls import load_topic_index
from feedctrl.semantic_review import SemanticPreview,SemanticApply,SemanticHistory,ProviderFailure,scoped_index,rank_groups
from feedctrl.indirect_grounding import _catalogue
MODEL='claude-offline-test';REQUEST="I'm not hungry, remove all the stuff that makes me hungry."
ACTION={'needs_clarification':False,'question':'','control':'exclude/none','intent_span':'the stuff that makes me hungry'}
PROPOSAL={'status':'propose','reason':'Authored fake evidence.','negation_resolved':True,'alternatives':[],
          'evidence':[{'item_id':92001,'field':'caption','quote':'bowl of noodles'}, {'item_id':92003,'field':'caption','quote':'sliced bread'}]}
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def stream(response,refusal=False):
 terminal={'type':'result','subtype':'success','is_error':False,'num_turns':1,'stop_reason':'end_turn','permission_denials':[],
           'usage':{'input_tokens':1,'output_tokens':1},'modelUsage':{MODEL:{}},'total_cost_usd':0,'result':json.dumps(response)}
 frames=([{'type':'assistant','message':{'role':'assistant','content':[{'type':'refusal','refusal':'synthetic'}]}}] if refusal else [])+[terminal]
 return b'\n'.join(json.dumps(f,separators=(',',':')).encode() for f in frames)+b'\n'
class Clock:
 def __init__(self):self.t=0
 def now(self):return self.t
 def sleep(self,n):self.t+=n
class FakeRun:
 def __init__(self,data,uncertain):self.data=data;self.uncertain=uncertain;self.events=[]
 def poll(self,n):self.events.append('poll');return self.data,True,True,0,0
 def terminate(self):self.events.append('terminate')
 def cleanup_complete(self):self.events.append('cleanup_complete');return not self.uncertain
 def finish_io(self,d):self.events.append('finish_io');return True
 def check_io(self):self.events.append('check_io')
 def close(self):self.events.append('close')
class FakeBackend:
 def __init__(self,mode):self.mode=mode;self.calls=[];self.runs=[]
 def launch(self,argv,input_bytes,env,cwd,maximum,deadline):
  self.calls.append(json.loads(input_bytes));stage=len(self.calls)
  refusal=(self.mode=='first_refusal' and stage==1) or (self.mode=='second_refusal' and stage==2)
  response=({'unexpected':'invalid'} if self.mode=='invalid_action' and stage==1 else ACTION if stage==1 else PROPOSAL)
  r=FakeRun(stream(response,refusal),self.mode=='cleanup' and stage==1);self.runs.append(r);return r
def routes(app):return {r.path:r.endpoint for r in app.routes if getattr(r,'path',None) in {'/api/semantic/groups','/api/semantic/preview','/api/semantic/apply','/api/semantic/history/preview'}}
def full_feed(app,session):
 demo=app.state.demo;state=demo.user_state(session,1);ids=sorted(demo.items);history=demo.users[1]['train']+demo.users[1]['request_history']
 counts=Counter(c for i in history for c in demo.items.get(i,[]));scores=[sum(counts[c] for c in demo.items[i])+((i*17+7)%19)/100 for i in ids]
 return rank_groups(ids,scores,state.get('semantic_groups',[]),demo.topic_index,limit=len(ids),original_categories=demo.items)
class Checks(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).absolute();self.work=self.root/'work';self.work.mkdir();self.cli=self.root/'cli.exe';self.cli.write_bytes(b'fake')
  self.data=self.root/'data.json';self.sidecar=self.root/'captions.csv';self.marker=self.root/'marker';self.ids=[92001,92002,92003,92004]
  self.data.write_text(json.dumps({'metadata':{'kind':'synthetic_fixture','is_fixture':True},'items':[{'item_id':i,'categories':['Recipe' if i in (92001,92003) else 'Repair']} for i in self.ids],'users':[{'user_id':1,'train':[92002],'request_history':[],'test':[]}]}),encoding='utf-8')
  with self.sidecar.open('w',encoding='utf-8',newline='') as f:
   w=csv.writer(f);w.writerow(['video_id','manual_cover_text','caption','topic_tag','first_level_category_name','second_level_category_name','third_level_category_name'])
   for i,c in zip(self.ids,['A bowl of noodles on a table.','A bicycle wheel is repaired.','Fresh sliced bread on a plate.','A lamp is repaired.']):w.writerow([i,'',c,'', '','',''])
  self.context={'context_file':self.root/'context','context_sha256':'a'*64,'cli':self.cli,'workdir':self.work,'home':self.root}
  self.files={str(self.data):digest(self.data),str(self.sidecar):digest(self.sidecar)}
  index=load_topic_index(self.sidecar,set(self.ids));self.catalogue_sha=flow_guard._digest(_catalogue(scoped_index(index,self.ids)))
  self.env={'PATH':str(self.root),'USERPROFILE':str(self.root),'HOME':str(self.root),'SYSTEMROOT':str(self.root)}
  self.patchenv=patch.dict(os.environ,self.env,clear=True);self.patchenv.start()
  expected=q._expected_child_environment({'max_output_tokens':'4096'},self.root)
  self.reviewed={'max_output_tokens':'4096','child_env_sha256':q._environment_digest(expected)}
  self.patches=[patch.object(q,'_require_bootstrap'),patch.object(q,'preflight'),patch.object(q,'_load_context',return_value=self.reviewed),patch.object(app_binding.bootstrap,'_load',return_value=q)]
  for x in self.patches:x.start()
 def tearDown(self):
  for x in reversed(self.patches):x.stop()
  self.patchenv.stop();self.tmp.cleanup()
 def build(self,mode):
  backend=FakeBackend(mode);clock=Clock()
  def loop(*args):return windows.run_with_backend(*args,backend=backend,now=clock.now,sleep=clock.sleep,cleanup_timeout=.05)
  wrapped=transport.DiagnosticRunner(loop,runtime_mode='reviewed_hooks');bound=q._BoundCalls(wrapped,self.context,self.marker,2)
  approvals={k:True for k in app_binding._APPROVALS}
  with patch.object(app_binding.bootstrap,'bind_once',return_value=(bound,[])):
   app,_=app_binding.construct(enable_live=True,context=self.context,marker=self.marker,allowed_origin='http://127.0.0.1:8000',model=MODEL,effort='max',estimated_per_invocation_usd=5,output_mode='plain_json',reviewed_cli_version='2.1.321',approvals=approvals,reviewed_files=self.files,max_calls=2,request=REQUEST,catalogue_sha256=self.catalogue_sha,fixture=False,data_path=self.data,semantic_path=self.sidecar)
  return app,backend
 def preview(self,app):
  session=app.state.demo.create_session();route=routes(app);before=full_feed(app,session)
  body=SemanticPreview(user_id=1,text=REQUEST,label='Authored test',candidate_ids=self.ids,backend='configured_model',action_source='model')
  try:result=route['/api/semantic/preview'](body,x_session_id=session)
  except ProviderFailure as exc:result=exc.body
  self.assertEqual(full_feed(app,session),before)
  return session,route,before,result
 def test_two_stage_preview_ai_review_apply_undo(self):
  app,backend=self.build('success');session,route,before,result=self.preview(app)
  self.assertTrue(result['ready']);self.assertEqual(len(backend.calls),2);self.assertFalse(result['applied'])
  reviews=[]
  def ai_review(payload):reviews.append(payload);return True
  self.assertTrue(ai_review(result));self.assertEqual(set(result['proposal']['item_ids']),{92001,92003})
  applied=route['/api/semantic/apply'](SemanticApply(user_id=1,plan_id=result['plan_id']),x_session_id=session);self.assertTrue(applied['applied'])
  changed=full_feed(app,session);self.assertNotEqual(changed,before);self.assertEqual({x['item_id'] for x in before['items']}-{x['item_id'] for x in changed['items']},{92001,92003});self.assertNotIn(session,json.dumps(backend.calls))
  undo=route['/api/semantic/history/preview'](SemanticHistory(user_id=1,action='undo'),x_session_id=session)
  self.assertTrue(undo['ready']);self.assertEqual(full_feed(app,session),changed);self.assertTrue(ai_review(undo))
  restored=route['/api/semantic/apply'](SemanticApply(user_id=1,plan_id=undo['plan_id']),x_session_id=session)
  self.assertTrue(restored['applied']);self.assertEqual(full_feed(app,session),before);self.assertEqual(len(reviews),2)
  self.assertTrue(self.marker.exists());self.assertTrue(self.marker.with_name('marker.2').exists())
  self.assertTrue(all('close' in x.events and 'terminate' in x.events for x in backend.runs))
 def test_first_and_second_refusal_stop_without_apply(self):
  for mode,expected in [('first_refusal',1),('invalid_action',1),('second_refusal',2)]:
   with self.subTest(mode=mode):
    if self.marker.exists():self.marker.unlink()
    if self.marker.with_name('marker.2').exists():self.marker.with_name('marker.2').unlink()
    app,backend=self.build(mode);session,route,before,result=self.preview(app)
    self.assertFalse(result['ready']);self.assertEqual(len(backend.calls),expected);self.assertEqual(full_feed(app,session),before)
    self.assertEqual(self.marker.with_name('marker.2').exists(),expected==2)
    with self.assertRaises(Exception) as caught:self.preview(app)
    self.assertEqual(getattr(caught.exception,'status_code',None),409);self.assertEqual(len(backend.calls),expected)
 def test_changed_fixture_stops_before_dispatch(self):
  app,backend=self.build('success');self.sidecar.write_text('changed',encoding='utf-8')
  session,route,before,result=self.preview(app)
  self.assertFalse(result['ready']);self.assertEqual(backend.calls,[]);self.assertFalse(self.marker.exists())
  self.assertEqual(full_feed(app,session),before)
 def test_fake_cleanup_uncertainty_stops_second_call(self):
  app,backend=self.build('cleanup');session,route,before,result=self.preview(app)
  self.assertFalse(result['ready']);self.assertEqual(len(backend.calls),1);self.assertFalse(self.marker.with_name('marker.2').exists())
  self.assertEqual(full_feed(app,session),before)
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks));print('GUARD_EVENTS:',BLOCKED,flush=True);sys.exit(0 if result.wasSuccessful() and not BLOCKED else 1)
