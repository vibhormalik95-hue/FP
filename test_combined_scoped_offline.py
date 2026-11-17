"""Actual configured adapter and combined app routes; authored fake backend only."""
import csv,hashlib,inspect,json,sys,threading,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
import test_two_stage_app_offline as fx
from diagnostic import app_binding,qualification as q,diagnostic_transport as transport,flow_guard
from feedctrl import windows_job_runner as windows,combined_grounding as grounding
from feedctrl.semantic_controls import load_topic_index
from feedctrl.semantic_review import SemanticApply,SemanticHistory,scoped_index
from feedctrl.indirect_grounding import _catalogue
from feedctrl.vocabulary_routes import VocabularyPreview
from feedctrl.api import Request
from fastapi import HTTPException
REQUEST='Show more music and remove food.'
REPLY={'status':'propose','reason':'Authored fake response.','negation_resolved':True,'alternatives':[],
 'controls':[{'control':'boost/standard','intent_span':'Show more music','relation':'Existing music label.',
  'evidence':[{'item_id':2,'field':'first_level_category_name','quote':'Music'}]},
 {'control':'exclude/none','intent_span':'remove food','relation':'Caption and tag.',
  'evidence':[{'item_id':1,'field':'caption','quote':'sandwich'},{'item_id':3,'field':'topic_tag','quote':'food'}]}]}
class Backend:
 def __init__(self,mode='success'):self.mode=mode;self.calls=[];self.runs=[];self.on_poll=None
 def launch(self,argv,input_bytes,env,cwd,maximum,deadline):
  self.calls.append((list(argv),json.loads(input_bytes)));answer=REPLY if self.mode!='invalid' else {'unexpected':'bad'}
  run=fx.FakeRun(fx.stream(answer,self.mode=='refusal'),self.mode=='cleanup');self.runs.append(run)
  if self.on_poll:
   poll=run.poll;fired=[False]
   def wrap(limit):
    value=poll(limit)
    if not fired[0]:fired[0]=True;self.on_poll()
    return value
   run.poll=wrap
  return run
def routes(app):return {r.path:r.endpoint for r in app.routes if getattr(r,'path',None) in {'/api/semantic/groups','/api/semantic/combined/preview','/api/semantic/preview','/api/semantic/apply','/api/semantic/history/preview','/api/reset'}}
class Checks(fx.Checks):
 def setUp(self):
  super().setUp();self.ids=list(range(1,9))
  self.data.write_text(json.dumps({'metadata':{'kind':'synthetic_fixture','is_fixture':True},'items':[{'item_id':i,'categories':['Music' if i==2 else 'General']} for i in self.ids],'users':[{'user_id':1,'train':[4],'request_history':[],'test':[]}]}),encoding='utf-8')
  fields=['video_id','manual_cover_text','caption','topic_tag','first_level_category_name','second_level_category_name','third_level_category_name']
  with self.sidecar.open('w',encoding='utf-8',newline='') as f:
   w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
   for i in self.ids:
    row={'video_id':i,'caption':{1:'Eating a sandwich',2:'A concert',3:'Vegetable soup'}.get(i,f'Neutral {i}')}
    if i==2:row['first_level_category_name']='Music'
    if i==3:row['topic_tag']='food'
    w.writerow(row)
  self.files={str(self.data):fx.digest(self.data),str(self.sidecar):fx.digest(self.sidecar)}
  self.index=load_topic_index(self.sidecar,set(self.ids));self.catsha=flow_guard._digest(_catalogue(scoped_index(self.index,self.ids)))
 def build_combined(self,mode='success',flow='combined-v1',**overrides):
  backend=Backend(mode);clock=fx.Clock()
  def loop(*args):return windows.run_with_backend(*args,backend=backend,now=clock.now,sleep=clock.sleep,cleanup_timeout=.05)
  wrapped=transport.DiagnosticRunner(loop,runtime_mode='reviewed_hooks');bound=q._BoundCalls(wrapped,self.context,self.marker,1)
  args=dict(enable_live=True,context=self.context,marker=self.marker,allowed_origin='http://127.0.0.1:8000',model=fx.MODEL,effort='max',estimated_per_invocation_usd=5,output_mode='plain_json',reviewed_cli_version='2.1.321',approvals={k:True for k in app_binding._APPROVALS},reviewed_files=self.files,max_calls=1,request=REQUEST,catalogue_sha256=self.catsha,flow_mode=flow,source_sha256=fx.digest(self.sidecar),candidate_ids=self.ids,fixture=False,data_path=self.data,semantic_path=self.sidecar)
  args.update(overrides)
  with patch.object(app_binding.bootstrap,'bind_once',return_value=(bound,[])):
   app,_=app_binding.construct(**args)
  return app,backend
 def guard_of(self,app):
  endpoint=routes(app)['/api/semantic/combined/preview'];return dict(zip(endpoint.__code__.co_freevars,(c.cell_contents for c in endpoint.__closure__)))['scope_guard']
 def call(self,app,session,text=REQUEST,ids=None):
  return routes(app)['/api/semantic/combined/preview'](VocabularyPreview(user_id=1,text=text,candidate_ids=self.ids if ids is None else ids),x_session_id=session)
 def test_configured_one_call_atomic_review_apply_and_exact_undo(self):
  app,backend=self.build_combined();session=app.state.demo.create_session();r=routes(app);before=r['/api/semantic/groups'](user_id=1,x_session_id=session)
  preview=self.call(app,session);self.assertTrue(preview['ready']);self.assertEqual(r['/api/semantic/groups'](user_id=1,x_session_id=session),before)
  self.assertEqual(len(backend.calls),1);self.assertNotIn(session,json.dumps(backend.calls));self.assertEqual(len(preview['groups']),2)
  reviews=[]
  def ai_review(value):reviews.append(value);return True
  self.assertTrue(ai_review(preview));applied=r['/api/semantic/apply'](SemanticApply(user_id=1,plan_id=preview['plan_id']),x_session_id=session);self.assertTrue(applied['applied'])
  self.assertEqual(applied['feed']['available_items'],6);ids={x['item_id'] for x in applied['feed']['items']};self.assertNotIn(1,ids);self.assertNotIn(3,ids);self.assertIn(2,ids)
  original=next(x for x in before['feed']['items'] if x['item_id']==2);boosted=next(x for x in applied['feed']['items'] if x['item_id']==2);self.assertAlmostEqual(boosted['score']-original['score'],.25)
  with self.assertRaises(HTTPException) as dup:r['/api/semantic/apply'](SemanticApply(user_id=1,plan_id=preview['plan_id']),x_session_id=session)
  self.assertEqual(dup.exception.status_code,409)
  undo=r['/api/semantic/history/preview'](SemanticHistory(user_id=1,action='undo'),x_session_id=session);self.assertTrue(undo['ready']);self.assertTrue(ai_review(undo))
  restored=r['/api/semantic/apply'](SemanticApply(user_id=1,plan_id=undo['plan_id']),x_session_id=session);self.assertEqual(restored['feed'],before['feed']);self.assertEqual(restored['groups'],before['groups'])
  self.assertEqual(len(reviews),2);self.assertEqual(len(backend.calls),1);self.assertTrue(self.marker.exists());self.assertFalse(self.marker.with_name('marker.2').exists())
  with self.assertRaises(HTTPException):self.call(app,session)
  self.assertEqual(len(backend.calls),1)
 def test_refusal_invalid_and_cleanup_close_no_reuse(self):
  for mode in ('refusal','invalid','cleanup'):
   with self.subTest(mode=mode):
    if self.marker.exists():self.marker.unlink()
    app,backend=self.build_combined(mode);session=app.state.demo.create_session();result=self.call(app,session)
    self.assertFalse(result['ready']);self.assertEqual(len(backend.calls),1);self.assertTrue(self.marker.exists())
    with self.assertRaises(HTTPException):self.call(app,session)
    self.assertEqual(len(backend.calls),1)
 def test_mode_request_scope_source_catalogue_and_model_mismatches_zero_dispatch(self):
  for kind in ('mode','request','scope','source','catalogue','model'):
   with self.subTest(kind=kind):
    if self.marker.exists():self.marker.unlink()
    app,backend=self.build_combined(flow=None if kind=='mode' else 'combined-v1');session=app.state.demo.create_session()
    if kind=='source':app.state.demo.topic_index['sha256']='0'*64
    if kind=='catalogue':app.state.demo.topic_index['items'][1]['fields']['caption']='changed'
    if kind=='model':self.guard_of(app).model='claude-different'
    with self.assertRaises(HTTPException):self.call(app,session,text='Different request' if kind=='request' else REQUEST,ids=self.ids[:-1] if kind=='scope' else None)
    self.assertEqual(backend.calls,[]);self.assertFalse(self.marker.exists())
 def test_wrong_prompt_and_schema_stop_before_transport(self):
  for kind in ('prompt','schema'):
   with self.subTest(kind=kind):
    if self.marker.exists():self.marker.unlink()
    app,backend=self.build_combined();session=app.state.demo.create_session()
    def wrong(request,index,infer,*,model_provenance):
     payload={'system':grounding.PROMPT,'request':request,'catalogue':_catalogue(index)};schema=grounding.SCHEMA
     if kind=='prompt':payload['system']='different'
     else:schema={'type':'object'}
     infer(payload,schema);raise AssertionError('must fail')
    with patch.object(grounding,'propose_combined',side_effect=wrong):result=self.call(app,session)
    self.assertFalse(result['ready']);self.assertEqual(backend.calls,[]);self.assertFalse(self.marker.exists())
 def test_expired_scope_and_wrong_model_argv_are_zero_transport(self):
  app,backend=self.build_combined();session=app.state.demo.create_session();scope=self.guard_of(app);ticks=iter([0,301]);scope._clock=lambda:next(ticks)
  result=self.call(app,session);self.assertFalse(result['ready']);self.assertEqual(backend.calls,[]);self.assertFalse(self.marker.exists())
  calls=[];r=app_binding._ModelPinnedRunner(lambda *args:calls.append(1),'claude-reviewed')
  with self.assertRaises(ValueError):r(['fake','--model','claude-other'],b'',{},'',1,1)
  self.assertEqual(calls,[])
 def test_supersession_before_reservation_and_during_provider(self):
  for stage in ('before','during'):
   with self.subTest(stage=stage):
    if self.marker.exists():self.marker.unlink()
    app,backend=self.build_combined();session=app.state.demo.create_session();route=routes(app);original=grounding.propose_combined
    def supersede():
     with app.state.demo.lock:app.state.demo.user_state(session,1)['semantic_preview_nonce']='newer'
    def changed(request,index,infer,*,model_provenance):supersede();return original(request,index,infer,model_provenance=model_provenance)
    if stage=='before':
     with patch.object(grounding,'propose_combined',side_effect=changed):result=self.call(app,session)
     self.assertFalse(result['ready']);self.assertEqual(backend.calls,[]);self.assertFalse(self.marker.exists())
    else:
     backend.on_poll=supersede
     with self.assertRaises(HTTPException) as exc:self.call(app,session)
     self.assertEqual(exc.exception.status_code,409);self.assertEqual(len(backend.calls),1);self.assertTrue(self.marker.exists())
    with self.assertRaises(HTTPException):self.call(app,session)
    self.assertEqual(len(backend.calls),0 if stage=='before' else 1)
 def test_overlapping_preview_is_denied_without_second_transport(self):
  app,backend=self.build_combined();session=app.state.demo.create_session();entered=threading.Event();release=threading.Event();out=[]
  def wait():
   entered.set()
   if not release.wait(3):raise RuntimeError('bounded timeout')
  backend.on_poll=wait
  def first():
   try:out.append(self.call(app,session).get('ready'))
   except HTTPException as exc:out.append(exc.status_code)
  t=threading.Thread(target=first,daemon=True);t.start()
  try:
   self.assertTrue(entered.wait(3))
   with self.assertRaises(HTTPException) as exc:self.call(app,session)
   self.assertEqual(exc.exception.status_code,409)
  finally:release.set();t.join(3)
  self.assertFalse(t.is_alive());self.assertEqual(out,[False]);self.assertEqual(len(backend.calls),1)
 def test_reviewed_source_file_change_stops_before_dispatch(self):
  app,backend=self.build_combined();session=app.state.demo.create_session()
  self.sidecar.write_bytes(b'changed')
  result=self.call(app,session);self.assertFalse(result['ready'])
  self.assertEqual(backend.calls,[]);self.assertFalse(self.marker.exists())
  with self.assertRaises(HTTPException):self.call(app,session)
 def test_unwrapped_combined_route_remains_reusable(self):
  from feedctrl.api import create_app
  calls=[]
  def factory():
   def infer(payload,schema):calls.append((payload,schema));return REPLY
   return infer,{'backend':'authored-fake','model':'fixture','digest':'fixture-only'}
  app=create_app(data_path=self.data,semantic_path=self.sidecar,fixture=False,semantic_infer_factory=factory,allow_local_models=False,allow_local_recommender=False)
  session=app.state.demo.create_session();first=self.call(app,session);second=self.call(app,session)
  self.assertTrue(first['ready']);self.assertTrue(second['ready']);self.assertEqual(len(calls),2)
  with self.assertRaises(HTTPException):routes(app)['/api/semantic/apply'](SemanticApply(user_id=1,plan_id=first['plan_id']),x_session_id=session)
  self.assertTrue(routes(app)['/api/semantic/apply'](SemanticApply(user_id=1,plan_id=second['plan_id']),x_session_id=session)['applied'])
if __name__=='__main__':
 names=('test_configured_one_call_atomic_review_apply_and_exact_undo','test_refusal_invalid_and_cleanup_close_no_reuse','test_mode_request_scope_source_catalogue_and_model_mismatches_zero_dispatch','test_wrong_prompt_and_schema_stop_before_transport','test_expired_scope_and_wrong_model_argv_are_zero_transport','test_supersession_before_reservation_and_during_provider','test_overlapping_preview_is_denied_without_second_transport','test_reviewed_source_file_change_stops_before_dispatch','test_unwrapped_combined_route_remains_reusable')
 r=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(Checks(n) for n in names));print('GUARD_EVENTS:',fx.BLOCKED,flush=True);sys.exit(0 if r.wasSuccessful() and not fx.BLOCKED else 1)
