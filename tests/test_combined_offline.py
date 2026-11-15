"""Authored offline replies, not model-quality evidence."""
from copy import deepcopy
import csv
import tempfile
import unittest
from pathlib import Path
from fastapi.testclient import TestClient
from feedctrl.api import create_app
from feedctrl.semantic_controls import TEXT_FIELDS
from feedctrl.combined_grounding import propose_combined

IDENTITY={'backend':'authored-test','model':'standin','digest':'not-live'}
REQUEST='Show more music and remove food.'
FIELDS={1:{'caption':'Eating a sandwich','first_level_category_name':'Daily life'},
 2:{'caption':'A concert','first_level_category_name':'Music'},
 3:{'caption':'Vegetable soup','topic_tag':'food'},4:{'caption':'Walking a dog'}}
INDEX={'sha256':'a'*64,'items':{i:{'fields':FIELDS.get(i,{'caption':f'Neutral {i}'})} for i in range(1,9)}}
def reply():
 return {'status':'propose','reason':'two preferences','negation_resolved':True,'alternatives':[],
 'controls':[{'control':'boost/standard','intent_span':'Show more music','relation':'Music category',
 'evidence':[{'item_id':2,'field':'first_level_category_name','quote':'Music'}]},
 {'control':'exclude/none','intent_span':'remove food','relation':'caption and tag',
 'evidence':[{'item_id':1,'field':'caption','quote':'sandwich'}, {'item_id':3,'field':'topic_tag','quote':'food'}]}]}

class Grounding(unittest.TestCase):
 def run_reply(self,r,request=REQUEST,index=INDEX):
  self.calls=[]
  def infer(payload,schema): self.calls.append(payload); return r
  return propose_combined(request,index,infer,model_provenance=IDENTITY)
 def test_all_fields_and_mixed(self):
  result=self.run_reply(reply());self.assertEqual(result['status'],'review');self.assertEqual(len(self.calls),1)
  self.assertEqual(self.calls[0]['catalogue'][0]['fields']['caption'],'Eating a sandwich')
  self.assertEqual(result['controls'][1]['item_ids'],[1,3])
 def test_bad_quote_fails_whole_plan(self):
  r=reply();r['controls'][1]['evidence'][0]['quote']='not here';result=self.run_reply(r)
  self.assertEqual(result['status'],'error');self.assertEqual(result['controls'],[])
 def test_unknown_id(self):
  r=reply();r['controls'][0]['evidence'][0]['item_id']=99;self.assertEqual(self.run_reply(r)['status'],'error')
 def test_overlap_no_silent_priority(self):
  r=reply();r['controls'][0]['evidence']=[{'item_id':1,'field':'caption','quote':'sandwich'}]
  self.assertEqual(self.run_reply(r)['status'],'clarify')
 def test_overlapping_spans(self):
  r=reply();r['controls'][1]['intent_span']='more music';self.assertEqual(self.run_reply(r)['status'],'error')
 def test_no_partial_abstention(self):
  r=reply();r['status']='unsupported';self.assertEqual(self.run_reply(r)['status'],'error')
 def test_guard_before_call(self):
  result=self.run_reply(reply(),'Do not remove food');self.assertEqual(result['status'],'clarify');self.assertEqual(self.calls,[])
 def test_budget_before_call(self):
  index=deepcopy(INDEX);index['items'][1]['fields']['caption']='x'*20000
  self.assertEqual(self.run_reply(reply(),index=index)['status'],'clarify');self.assertEqual(self.calls,[])
 def test_breadth(self):
  r=reply();r['controls'][1]['evidence']=[{'item_id':i,'field':'caption','quote':INDEX['items'][i]['fields']['caption']} for i in [1,4,5,6,7]]
  self.assertEqual(self.run_reply(r)['status'],'clarify')
 def test_provider_failure(self):
  def fail(*args):raise RuntimeError('private message')
  r=propose_combined(REQUEST,INDEX,fail,model_provenance=IDENTITY)
  self.assertEqual(r['status'],'error');self.assertNotIn('private message',str(r))

class Lifecycle(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();path=Path(self.temp.name)/'source.csv'
  with path.open('w',newline='') as f:
   writer=csv.DictWriter(f,fieldnames=['video_id',*TEXT_FIELDS]);writer.writeheader()
   for i in range(1,37):writer.writerow({'video_id':i,**FIELDS.get(i,{'caption':f'Neutral {i}'})})
  self.answer=reply();self.calls=[];self.hook=None
  def infer(payload,schema):
   self.calls.append(payload)
   if self.hook:self.hook()
   return deepcopy(self.answer)
  self.app=create_app(fixture=True,semantic_path=path,semantic_infer_factory=lambda:(infer,IDENTITY),allow_local_models=False)
  self.client=TestClient(self.app);self.client.__enter__()
  self.h={'X-Session-ID':self.client.post('/api/session',json={}).json()['session_id']}
 def tearDown(self):self.client.__exit__(None,None,None);self.temp.cleanup()
 def saved(self):return self.client.get('/api/semantic/groups?user_id=1',headers=self.h).json()
 def preview(self):return self.client.post('/api/semantic/combined/preview',headers=self.h,json={'user_id':1,'text':REQUEST,'candidate_ids':list(range(1,9))})
 def apply(self,p,h=None):return self.client.post('/api/semantic/apply',headers=h or self.h,json={'user_id':1,'plan_id':p['plan_id']})
 def test_atomic_apply_exact_undo(self):
  before=self.saved();p=self.preview().json();self.assertTrue(p['ready'],p);self.assertEqual(self.saved(),before)
  self.assertEqual(len(p['groups']),2);self.assertEqual(p['calls_attempted'],1)
  a=self.apply(p);self.assertEqual(a.status_code,200,a.text);self.assertEqual(a.json()['feed']['available_items'],34)
  self.assertEqual(self.apply(p).status_code,409)
  undo=self.client.post('/api/semantic/history/preview',headers=self.h,json={'user_id':1,'action':'undo'}).json()
  after=self.apply(undo).json();self.assertEqual(after['feed'],before['feed']);self.assertEqual(after['groups'],[])
 def test_other_session_cannot_apply(self):
  p=self.preview().json();h={'X-Session-ID':self.client.post('/api/session',json={}).json()['session_id']}
  self.assertEqual(self.apply(p,h).status_code,409)
 def test_failed_second_control_leaves_state(self):
  before=self.saved();self.answer['controls'][1]['evidence'][0]['quote']='fake'
  p=self.preview().json();self.assertFalse(p['ready']);self.assertEqual(self.saved(),before);self.assertNotIn('plan_id',p)
 def test_new_preview_supersedes_old(self):
  a=self.preview().json();b=self.preview().json();self.assertEqual(self.apply(a).status_code,409);self.assertEqual(self.apply(b).status_code,200)
 def test_source_changed_during_inference_rejects_plan(self):
  before=self.saved()
  self.hook=lambda:self.app.state.demo.topic_index['items'][1]['fields'].update(caption='different source')
  p=self.preview().json();self.assertFalse(p['ready']);self.assertNotIn('plan_id',p)
  self.assertEqual(self.saved()['groups'],before['groups'])
 def test_source_changed_after_review_rejects_apply(self):
  p=self.preview().json()
  self.app.state.demo.topic_index['items'][1]['fields']['caption']='changed'
  self.assertEqual(self.apply(p).status_code,409)
  self.assertEqual(self.saved()['groups'],[])
 def test_timeout_expired_plan(self):
  p=self.preview().json()
  token=self.h['X-Session-ID']
  self.app.state.demo.sessions[token]['users'][1]['semantic_pending']['created']-=301
  self.assertEqual(self.apply(p).status_code,409)
  self.assertEqual(self.saved()['groups'],[])
 def test_authentication_before_model(self):
  r=self.client.post('/api/semantic/combined/preview',json={'user_id':1,'text':REQUEST,'candidate_ids':list(range(1,9))})
  self.assertEqual(r.status_code,401);self.assertEqual(self.calls,[])

if __name__=='__main__':unittest.main()
