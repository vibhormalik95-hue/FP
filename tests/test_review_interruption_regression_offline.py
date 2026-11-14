"""Synthetic concurrent review regressions; no HTTP, process or model."""
from copy import deepcopy
import threading,unittest
from fastapi import HTTPException
from feedctrl.api import Request
from feedctrl.semantic_review import SemanticHistory,SemanticPreview
import test_category_resolution_offline as fixture

class Interruptions(unittest.TestCase):
 setUp=fixture.CategoryResolutionTests.setUp
 build=fixture.CategoryResolutionTests.build
 call=fixture.CategoryResolutionTests.call
 preview=fixture.CategoryResolutionTests.preview
 resolve=fixture.CategoryResolutionTests.resolve
 classify=fixture.CategoryResolutionTests.classify
 apply=fixture.CategoryResolutionTests.apply
 conflict=fixture.CategoryResolutionTests.conflict
 def blocked_classify(self,plan,stage):
  entered=threading.Event();release=threading.Event();result={}
  def hook(current):
   if current==stage:
    entered.set()
    if not release.wait(5):raise AssertionError('synthetic stage wait expired')
  self.hook=hook
  def worker():
   try:result['value']=self.classify(plan)
   except BaseException as exc:result['error']=exc
  thread=threading.Thread(target=worker);thread.start()
  if not entered.wait(5):release.set();thread.join(5);self.fail('synthetic stage not reached')
  return thread,release,result
 def finish(self,thread,release,result):
  release.set();thread.join(5);self.assertFalse(thread.is_alive());self.assertNotIn('error',result);return result['value']
 def test_simultaneous_duplicate_classify_is_rejected_before_another_provider_call(self):
  plan=self.resolve(self.preview());thread,release,result=self.blocked_classify(plan,'membership')
  try:
   self.conflict(lambda:self.classify(plan));self.assertEqual(self.calls,['definition','membership'])
  finally:value=self.finish(thread,release,result)
  self.assertTrue(value['ready']);self.assertEqual(self.calls,['definition','membership','evidence_audit']);self.assertEqual(self.state['semantic_groups'],[])
 def test_old_clarification_cancel_does_not_claim_to_cancel_inflight_classify(self):
  clarification=self.preview();plan=self.resolve(clarification);thread,release,result=self.blocked_classify(plan,'membership')
  try:self.conflict(lambda:self.resolve(clarification,'cancel'))
  finally:value=self.finish(thread,release,result)
  self.assertTrue(value['ready']);self.assertEqual(self.calls,['definition','membership','evidence_audit'])
 def test_newer_manual_preview_supersedes_classify_during_either_stage(self):
  for stage in ('membership','evidence_audit'):
   with self.subTest(stage=stage):
    self.build();plan=self.resolve(self.preview());thread,release,result=self.blocked_classify(plan,stage)
    try:
     category=self.demo.items[1][0];newer=self.call('semantic/preview',SemanticPreview(user_id=1,label='Synthetic newer review',candidate_ids=list(range(1,9)),backend='manual_category',category=category,operation='exclude',strength='none'))
     self.assertTrue(newer['ready']);pending=deepcopy(self.state['semantic_pending'])
    finally:value=self.finish(thread,release,result)
    self.assertFalse(value['ready']);self.assertFalse(value['applied']);self.assertEqual(self.state['semantic_pending'],pending);self.assertEqual(self.state['semantic_groups'],[])
    self.assertEqual(self.calls,['definition','membership']+(['evidence_audit'] if stage=='evidence_audit' else []))
 def test_reset_cancels_inflight_classify_during_either_stage(self):
  for stage in ('membership','evidence_audit'):
   with self.subTest(stage=stage):
    self.build();plan=self.resolve(self.preview());thread,release,result=self.blocked_classify(plan,stage)
    try:self.call('reset',Request(user_id=1))
    finally:value=self.finish(thread,release,result)
    self.assertFalse(value['ready']);self.assertFalse(value['applied']);self.assertIsNone(self.state.get('semantic_pending'));self.assertEqual(self.state.get('semantic_groups',[]),[])
    self.assertEqual(self.calls,['definition','membership']+(['evidence_audit'] if stage=='evidence_audit' else []))
 def test_inventory_content_change_with_same_ids_invalidates_inflight_stage(self):
  for stage in ('membership','evidence_audit'):
   with self.subTest(stage=stage):
    self.build();plan=self.resolve(self.preview());thread,release,result=self.blocked_classify(plan,stage)
    try:
     before_ids=sorted(self.demo.items);self.demo.items[1]=['changed-synthetic-category'];self.assertEqual(sorted(self.demo.items),before_ids)
    finally:value=self.finish(thread,release,result)
    self.assertFalse(value['ready']);self.assertFalse(value['applied']);self.assertIsNone(self.state.get('semantic_pending'));self.assertEqual(self.state['semantic_groups'],[])
    self.assertEqual(self.calls,['definition','membership']+(['evidence_audit'] if stage=='evidence_audit' else []))
 def test_empty_undo_or_clear_plan_rejects_source_or_inventory_drift(self):
  for action in ('undo','clear'):
   for change in ('caption','source_digest','missing_digest','inventory'):
    with self.subTest(action=action,change=change):
     self.build();definition=self.resolve(self.preview());proposal=self.classify(definition);self.assertTrue(proposal['ready']);self.apply(proposal)
     plan=self.call('semantic/history/preview',SemanticHistory(user_id=1,action=action));self.assertTrue(plan['ready']);self.assertEqual(plan['groups'],[])
     if change=='caption':self.demo.topic_index['items'][1]['fields']['caption']='synthetic edited caption'
     elif change=='source_digest':self.demo.topic_index['sha256']='0'*64
     elif change=='missing_digest':del self.demo.topic_index['sha256']
     else:self.demo.items[1]=['changed-synthetic-category']
     before=deepcopy(self.state);self.conflict(lambda:self.apply(plan));self.assertEqual(self.state,before)
 def test_in_scope_preview_rejects_out_of_scope_inventory_edit(self):
  definition=self.resolve(self.preview());plan=self.classify(definition);self.assertTrue(plan['ready']);ids=sorted(self.demo.items);self.demo.items[20]=['changed-outside-scope'];self.assertEqual(sorted(self.demo.items),ids);before=deepcopy(self.state);self.conflict(lambda:self.apply(plan));self.assertEqual(self.state,before)
 def test_in_scope_preview_rejects_out_of_scope_metadata_edit(self):
  definition=self.resolve(self.preview());plan=self.classify(definition);self.assertTrue(plan['ready']);self.demo.topic_index['items'][20]['fields']['caption']='changed-outside-scope';before=deepcopy(self.state);self.conflict(lambda:self.apply(plan));self.assertEqual(self.state,before)
 def test_review_rejects_nonce_drift_before_apply(self):
  definition=self.resolve(self.preview());plan=self.classify(definition);self.assertTrue(plan['ready']);self.state['semantic_preview_nonce']='changed-synthetic-nonce';before=deepcopy(self.state);self.conflict(lambda:self.apply(plan));self.assertEqual(self.state,before)
 def test_other_session_and_revision_drift_reject_apply(self):
  definition=self.resolve(self.preview());plan=self.classify(definition);other=self.demo.create_session();before=deepcopy(self.state)
  self.conflict(lambda:self.call('semantic/apply',fixture.SemanticApply(user_id=1,plan_id=plan['plan_id']),session=other));self.assertEqual(self.state,before)
  self.state['semantic_revision']+=1;before=deepcopy(self.state);self.conflict(lambda:self.apply(plan));self.assertEqual(self.state,before)
 def test_newer_review_invalidates_previous_apply_token(self):
  definition=self.resolve(self.preview());old=self.classify(definition);category=self.demo.items[1][0]
  newer=self.call('semantic/preview',SemanticPreview(user_id=1,label='Newer synthetic review',candidate_ids=list(range(1,9)),backend='manual_category',category=category,operation='exclude',strength='none'));self.assertTrue(newer['ready']);before=deepcopy(self.state)
  self.conflict(lambda:self.apply(old));self.assertEqual(self.state,before);self.assertEqual(self.state['semantic_groups'],[])
 def test_unchanged_reviewed_undo_restores_exact_baseline(self):
  groups=fixture.endpoint(self.app,'/api/semantic/groups');baseline=groups(1,self.session)['feed'];definition=self.resolve(self.preview());plan=self.classify(definition);applied=self.apply(plan);self.assertNotEqual(applied['feed'],baseline)
  undo=self.call('semantic/history/preview',SemanticHistory(user_id=1,action='undo'));restored=self.apply(undo);self.assertEqual(restored['feed'],baseline)
 def test_new_clear_after_prior_drift_remains_available(self):
  definition=self.resolve(self.preview());plan=self.classify(definition);self.apply(plan);self.demo.items[1]=['changed-synthetic-category'];clear=self.call('semantic/history/preview',SemanticHistory(user_id=1,action='clear'));self.assertTrue(clear['ready']);self.assertTrue(self.apply(clear)['applied']);self.assertEqual(self.state['semantic_groups'],[])
if __name__=='__main__':unittest.main(verbosity=2)
