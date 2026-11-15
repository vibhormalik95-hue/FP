"""Owned fake-only preview lifetime, invalidation and ordering checks."""
import json,sys,threading,unittest
from unittest.mock import patch
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
import test_two_stage_app_offline as fx
from diagnostic.flow_guard import FlowGuard,FlowGuardError,_digest,_PreviewScope
from feedctrl.semantic_review import SemanticPreview,SemanticApply,SemanticHistory,ACTION_SCHEMA,ACTION_PROMPT
from feedctrl.indirect_grounding import SCHEMA,PROMPT
from feedctrl.api import Request
from fastapi import HTTPException

def body(ids):return SemanticPreview(user_id=1,text=fx.REQUEST,label='Original',candidate_ids=ids,backend='configured_model',action_source='model')
def manual(ids,label='Manual'):
 return SemanticPreview(user_id=1,label=label,candidate_ids=ids,backend='manual_category',action_source='manual',category='Repair',operation='boost',strength='standard')
def intercept(backend,callback):
 launch=backend.launch
 def replacement(*args):
  run=launch(*args)
  if len(backend.calls)==1:
   poll=run.poll;fired=[False]
   def wrapped(limit):
    result=poll(limit)
    if not fired[0]:fired[0]=True;callback()
    return result
   run.poll=wrapped
  return run
 backend.launch=replacement

class Lifetime(fx.Checks):
 def test_real_route_supersession_variants_never_dispatch_grounding_or_reopen(self):
  for mode in ('model_preview','manual_preview','manual_apply','undo','clear','reset'):
   with self.subTest(mode=mode):
    for marker in (self.marker,self.marker.with_name('marker.2')):
     if marker.exists():marker.unlink()
    app,backend=self.build('success');session=app.state.demo.create_session();route=fx.routes(app)
    reset=next(r.endpoint for r in app.routes if getattr(r,'path',None)=='/api/reset')
    if mode=='undo':
     earlier=route['/api/semantic/preview'](manual(self.ids,'Earlier'),x_session_id=session)
     self.assertTrue(earlier['ready']);route['/api/semantic/apply'](SemanticApply(user_id=1,plan_id=earlier['plan_id']),x_session_id=session)
    observed=[]
    def change():
     if mode=='model_preview':
      try:route['/api/semantic/preview'](body(self.ids),x_session_id=session)
      except HTTPException as exc:observed.append(exc.status_code)
     elif mode in ('manual_preview','manual_apply'):
      newer=route['/api/semantic/preview'](manual(self.ids,'New manual'),x_session_id=session);observed.append(newer['ready'])
      if mode=='manual_apply':observed.append(route['/api/semantic/apply'](SemanticApply(user_id=1,plan_id=newer['plan_id']),x_session_id=session)['applied'])
     elif mode in ('undo','clear'):
      observed.append(route['/api/semantic/history/preview'](SemanticHistory(user_id=1,action=mode),x_session_id=session)['ready'])
     else:observed.append(reset(Request(user_id=1),x_session_id=session)['reset'])
    intercept(backend,change)
    with self.assertRaises(HTTPException) as stopped:route['/api/semantic/preview'](body(self.ids),x_session_id=session)
    self.assertEqual(stopped.exception.status_code,409);self.assertTrue(observed);self.assertEqual(len(backend.calls),1)
    self.assertTrue(self.marker.exists());self.assertFalse(self.marker.with_name('marker.2').exists())
    for retry_session in (session,app.state.demo.create_session()):
     with self.assertRaises(HTTPException) as retry:route['/api/semantic/preview'](body(self.ids),x_session_id=retry_session)
     self.assertEqual(retry.exception.status_code,409)
    self.assertEqual(len(backend.calls),1);self.assertNotIn(session,json.dumps(backend.calls));self.assertEqual(fx.BLOCKED,[])
 def test_early_ambiguity_and_invalid_scope_close_without_dispatch(self):
  for mode in ('ambiguity','invalid_ids'):
   with self.subTest(mode=mode):
    app,backend=self.build('success');session=app.state.demo.create_session();route=fx.routes(app)
    request=SemanticPreview(user_id=1,text="Don't remove repairs",label='Ambiguous',candidate_ids=self.ids,backend='configured_model',action_source='model') if mode=='ambiguity' else body([self.ids[0],999999])
    if mode=='ambiguity':self.assertFalse(route['/api/semantic/preview'](request,x_session_id=session)['ready'])
    else:
     with self.assertRaises(HTTPException):route['/api/semantic/preview'](request,x_session_id=session)
    with self.assertRaises(HTTPException) as retry:route['/api/semantic/preview'](body(self.ids),x_session_id=session)
    self.assertEqual(retry.exception.status_code,409);self.assertEqual(backend.calls,[]);self.assertFalse(self.marker.exists())
 def test_supersession_after_route_check_before_grounding_reservation_blocks_dispatch(self):
  from feedctrl import semantic_review
  app,backend=self.build('success');session=app.state.demo.create_session();route=fx.routes(app)
  original=semantic_review.propose_indirect
  def superseded(*args,**kwargs):
   with app.state.demo.lock:
    state=app.state.demo.user_state(session,1);state['semantic_preview_nonce']='superseding-nonce'
   return original(*args,**kwargs)
  with patch.object(semantic_review,'propose_indirect',side_effect=superseded):
   result=route['/api/semantic/preview'](body(self.ids),x_session_id=session)
  self.assertFalse(result['ready']);self.assertEqual(len(backend.calls),1)
  self.assertTrue(self.marker.exists());self.assertFalse(self.marker.with_name('marker.2').exists())
  with self.assertRaises(HTTPException) as retry:route['/api/semantic/preview'](body(self.ids),x_session_id=session)
  self.assertEqual(retry.exception.status_code,409);self.assertEqual(len(backend.calls),1)
 def test_expired_claim_is_irreversible(self):
  lock=threading.RLock();guard=FlowGuard(lambda *_:fx.ACTION,max_calls=2,request=fx.REQUEST,catalogue_sha256='a'*64,files={'input':'h'},file_digest=lambda p:'h')
  with self.assertRaises(FlowGuardError):guard.open_preview_scope(state_lock=lock,validate=lambda:False,identity=('fake',1,'nonce'))
  with self.assertRaises(FlowGuardError):guard.open_preview_scope(state_lock=lock,validate=lambda:True,identity=('fake',1,'new'))
 def test_application_exception_or_cancellation_closes_after_first_attempt(self):
  from feedctrl import semantic_review
  for error in (RuntimeError('synthetic application exception'),KeyboardInterrupt()):
   with self.subTest(error=type(error).__name__):
    for marker in (self.marker,self.marker.with_name('marker.2')):
     if marker.exists():marker.unlink()
    app,backend=self.build('success');session=app.state.demo.create_session();route=fx.routes(app)
    with patch.object(semantic_review,'propose_indirect',side_effect=error):
     with self.assertRaises(type(error)):route['/api/semantic/preview'](body(self.ids),x_session_id=session)
    self.assertEqual(len(backend.calls),1);self.assertTrue(self.marker.exists());self.assertFalse(self.marker.with_name('marker.2').exists())
    with self.assertRaises(HTTPException) as retry:route['/api/semantic/preview'](body(self.ids),x_session_id=session)
    self.assertEqual(retry.exception.status_code,409);self.assertEqual(len(backend.calls),1)
 def test_overlapping_scopes_finish_without_lock_inversion(self):
  app,backend=self.build('success');session=app.state.demo.create_session();route=fx.routes(app);entered=threading.Event();release=threading.Event();out=[]
  def wait_first():
   entered.set()
   if not release.wait(3):raise RuntimeError('bounded test timeout')
  intercept(backend,wait_first)
  def first():
   try:route['/api/semantic/preview'](body(self.ids),x_session_id=session);out.append('unexpected success')
   except HTTPException as exc:out.append(exc.status_code)
  thread=threading.Thread(target=first,daemon=True);thread.start()
  try:
   self.assertTrue(entered.wait(3))
   with self.assertRaises(HTTPException) as overlap:route['/api/semantic/preview'](body(self.ids),x_session_id=session)
   self.assertEqual(overlap.exception.status_code,409)
  finally:release.set();thread.join(3)
  self.assertFalse(thread.is_alive());self.assertEqual(out,[409]);self.assertEqual(len(backend.calls),1);self.assertFalse(self.marker.with_name('marker.2').exists())
 def test_unwrapped_provider_route_keeps_two_stage_behavior(self):
  from feedctrl.api import create_app
  calls=[]
  def infer(payload,schema):calls.append(1);return fx.ACTION if len(calls)==1 else fx.PROPOSAL
  def factory():return infer,{'backend':'authored-fake','model':'not-a-model','digest':'fixture-only'}
  app=create_app(data_path=self.data,semantic_path=self.sidecar,fixture=False,semantic_infer_factory=factory,allow_local_models=False,allow_local_recommender=False)
  session=app.state.demo.create_session();route=fx.routes(app);preview=route['/api/semantic/preview'](body(self.ids),x_session_id=session)
  self.assertTrue(preview['ready']);self.assertEqual(calls,[1,1])
 def test_reservation_order_and_bare_or_foreign_scope_fail_closed(self):
  state={'nonce':'first','revision':0};lock=threading.RLock();calls=[];catalogue=[{'item_id':1}]
  def current():return state=={'nonce':'first','revision':0}
  def inner(payload,schema):
   calls.append(1)
   acquired=[]
   def other():
    with lock:acquired.append(True)
   t=threading.Thread(target=other,daemon=True);t.start();t.join(2)
   self.assertFalse(t.is_alive());self.assertEqual(acquired,[True])
   if len(calls)==2:
    with lock:state['nonce']='later'
   return fx.ACTION if len(calls)==1 else fx.PROPOSAL
  bare=FlowGuard(inner,max_calls=2,request=fx.REQUEST,catalogue_sha256=_digest(catalogue),files={'input':'h'},file_digest=lambda p:'h')
  with self.assertRaises(FlowGuardError):bare({'system':ACTION_PROMPT,'request':fx.REQUEST},ACTION_SCHEMA)
  with self.assertRaises(FlowGuardError):bare.open_preview_scope(state_lock=lock,validate=current,identity=('fake-session',1,'first'))
  guard=FlowGuard(inner,max_calls=2,request=fx.REQUEST,catalogue_sha256=_digest(catalogue),files={'input':'h'},file_digest=lambda p:'h')
  scope=guard.open_preview_scope(state_lock=lock,validate=current,identity=('fake-session',1,'first'))
  self.assertEqual(scope({'system':ACTION_PROMPT,'request':fx.REQUEST},ACTION_SCHEMA),fx.ACTION)
  payload={'system':PROMPT,'request':fx.REQUEST,'action':guard.action,'catalogue':catalogue}
  self.assertEqual(scope(payload,SCHEMA),fx.PROPOSAL);self.assertEqual(calls,[1,1])
  scope.close();scope.close()
  with self.assertRaises(FlowGuardError):guard.open_preview_scope(state_lock=lock,validate=lambda:True,identity=('other',1,'later'))
  other=FlowGuard(lambda *_:fx.ACTION,max_calls=2,request=fx.REQUEST,catalogue_sha256=_digest(catalogue),files={'input':'h'},file_digest=lambda p:'h')
  real=other.open_preview_scope(state_lock=lock,validate=lambda:True,identity=('one',1,'nonce'))
  foreign=_PreviewScope(other,lock,lambda:True,('two',1,'nonce'))
  with self.assertRaises(FlowGuardError):foreign({'system':ACTION_PROMPT,'request':fx.REQUEST},ACTION_SCHEMA)
  with self.assertRaises(FlowGuardError):real({'system':ACTION_PROMPT,'request':fx.REQUEST},ACTION_SCHEMA)
  real.close()
 def test_scope_closed_while_call_inflight_cannot_be_resumed(self):
  lock=threading.RLock();entered=threading.Event();release=threading.Event();result=[]
  def inner(*_):
   entered.set()
   if not release.wait(3):raise RuntimeError('bounded test timeout')
   return fx.ACTION
  guard=FlowGuard(inner,max_calls=2,request=fx.REQUEST,catalogue_sha256='a'*64,files={'input':'h'},file_digest=lambda p:'h')
  scope=guard.open_preview_scope(state_lock=lock,validate=lambda:True,identity=('session',1,'nonce'))
  def worker():
   try:scope({'system':ACTION_PROMPT,'request':fx.REQUEST},ACTION_SCHEMA);result.append('unexpected')
   except FlowGuardError:result.append('closed')
  t=threading.Thread(target=worker,daemon=True);t.start()
  try:self.assertTrue(entered.wait(3));scope.close()
  finally:release.set();t.join(3)
  self.assertFalse(t.is_alive());self.assertEqual(result,['closed'])
  with self.assertRaises(FlowGuardError):guard.open_preview_scope(state_lock=lock,validate=lambda:True,identity=('other',1,'new'))
if __name__=='__main__':
 names=('test_real_route_supersession_variants_never_dispatch_grounding_or_reopen','test_early_ambiguity_and_invalid_scope_close_without_dispatch','test_supersession_after_route_check_before_grounding_reservation_blocks_dispatch','test_expired_claim_is_irreversible','test_application_exception_or_cancellation_closes_after_first_attempt','test_overlapping_scopes_finish_without_lock_inversion','test_unwrapped_provider_route_keeps_two_stage_behavior','test_reservation_order_and_bare_or_foreign_scope_fail_closed','test_scope_closed_while_call_inflight_cannot_be_resumed')
 suite=unittest.TestSuite(Lifetime(name) for name in names);r=unittest.TextTestRunner(verbosity=2).run(suite);print('GUARD_EVENTS:',fx.BLOCKED,flush=True);sys.exit(0 if r.wasSuccessful() and not fx.BLOCKED else 1)
