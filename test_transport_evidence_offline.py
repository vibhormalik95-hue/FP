"""Focused fake-backed projection retention and unchanged acceptance checks."""
import ast,copy,hashlib,json,pathlib,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT))
import test_personal_transport_offline as fx
from diagnostic import qualification as q,transport_evidence as evidence
from feedctrl import claude_personal as adapter

CANARY='PRIVATE_FAKE_PROMPT_AND_RESPONSE_6ad7'

def stage(reason):
 return [{'type':'stream_event','event':{'type':'message_start','message':{'type':'message','role':'assistant','content':[]}}},
         {'type':'stream_event','event':{'type':'message_delta','delta':{'stop_reason':reason}}},
         {'type':'stream_event','event':{'type':'message_stop'}}]
class Observed:
 def records(self):return [{'lifecycle':'fake'}]
class Checks(unittest.TestCase):
 @classmethod
 def setUpClass(cls):q.verify_package()
 def save(self,h,status):
  obs=q._ObservationView(Observed(),h.transport,evidence)
  self.assertEqual(obs(),[{'lifecycle':'fake'}]);value={'status':status,'transport_metadata':obs.transport_metadata()}
  with tempfile.TemporaryDirectory(prefix='comp-transport-metadata-') as d:
   path=pathlib.Path(d)/'result.json';path.write_text(json.dumps(value));self.assertEqual(json.loads(path.read_bytes()),value)
  return value['transport_metadata']
 def test_one_turn_success_is_still_accepted_and_metadata_persists(self):
  end=fx.terminal();end['result']=json.dumps({'title':CANARY});h=fx.Harness('reviewed_hooks',stage('end_turn')+[end])
  self.assertEqual(h.invoke(),{'title':CANARY});m=self.save(h,'accepted');record=m['records'][0]
  self.assertEqual(m['capture_status'],'available');self.assertEqual(record['projection_status'],'accepted')
  self.assertEqual(record['ordered_stop_reasons'],['end_turn']);self.assertEqual(record['terminal']['num_turns'],1)
  self.assertEqual(record['terminal']['usage'],{'input_tokens':1,'output_tokens':1})
  self.assertEqual(record['refusal_presence'],'not_observed_in_recognized_projection');self.assertIsNone(record['per_message_usage'])
  self.assertNotIn(CANARY,json.dumps(m));self.assertNotIn('Synthetic test only',json.dumps(m))
 def test_two_turn_is_still_rejected_and_ordered_stops_persist(self):
  end=fx.terminal();end['num_turns']=2;h=fx.Harness('reviewed_hooks',stage('max_tokens')+stage('end_turn')+[end])
  with self.assertRaises(adapter.PersonalCliMessage):h.invoke()
  self.assertEqual(h.receipts[0]['failure_reason'],'incomplete_success');m=self.save(h,'rejected');record=m['records'][0]
  self.assertEqual(record['projection_status'],'accepted');self.assertEqual(record['terminal']['num_turns'],2)
  self.assertEqual(record['ordered_stop_reasons'],['max_tokens','end_turn']);self.assertEqual(record['stream_event_counts']['message_start'],2)
  self.assertIsNone(record['per_message_usage']);self.assertEqual(len(h.backend.launches),1)
 def test_refusal_followed_by_success_remains_rejected_and_count_persists(self):
  h=fx.Harness('reviewed_hooks',stage('refusal')+[fx.terminal()])
  with self.assertRaises(adapter.PersonalCliMessage):h.invoke()
  m=self.save(h,'rejected');record=m['records'][0]
  self.assertEqual(record['projection_status'],'rejected');self.assertEqual(record['projection_error'],'assistant_operational_failure')
  self.assertEqual(record['refusal_presence'],'observed_in_stop_reason');self.assertEqual(record['observed_stop_counts']['refusal'],1)
  self.assertIsNone(record['ordered_stop_reasons']);self.assertEqual(len(h.backend.launches),1)
 def test_refusal_block_cannot_be_misreported_as_absent(self):
  refusal={'type':'assistant','message':{'role':'assistant','content':[{'type':'refusal','refusal':CANARY}]}}
  h=fx.Harness('reviewed_hooks',[refusal,fx.terminal()])
  with self.assertRaises(adapter.PersonalCliMessage):h.invoke()
  m=self.save(h,'rejected');self.assertEqual(m['records'][0]['refusal_presence'],'unavailable');self.assertNotIn(CANARY,json.dumps(m))
 def test_timeout_is_still_rejected_and_absence_is_explicit(self):
  h=fx.Harness('reviewed_hooks',backend_mode='timeout')
  with self.assertRaises(adapter.PersonalCliMessage):h.invoke()
  record=self.save(h,'rejected')['records'][0]
  self.assertEqual(record['projection_status'],'unavailable');self.assertFalse(record['runner_returned']);self.assertIsNone(record['terminal'])
 def test_malicious_metadata_is_bounded_and_never_copied(self):
  bad={'runner_returned':True,'projection':{'ok':True,'intermediate_stop_reasons':[CANARY]*5000,
      'frame_counts':{'assistant':5000,'private':CANARY},'stream_event_counts':{'unknown':CANARY},
      'final_result':{'subtype':CANARY,'num_turns':1,'is_error':False,'stop_reason':'end_turn','usage':{'input_tokens':CANARY}}}}
  m=evidence.snapshot([bad]);record=m['records'][0]
  self.assertIsNone(record['ordered_stop_reasons']);self.assertIsNone(record['frame_counts']);self.assertIsNone(record['terminal'])
  self.assertNotIn(CANARY,json.dumps(m));self.assertLess(len(json.dumps(m)),2000)
  self.assertEqual(evidence.snapshot([bad]*4),{'capture_status':'unavailable','records':[]})
 def test_capture_failure_is_nonfatal_and_no_content_is_injected(self):
  class BadEvidence:
   @staticmethod
   def snapshot(records):raise RuntimeError(CANARY)
  obs=q._ObservationView(Observed(),type('FakeTransport',(),{'records':[]})(),BadEvidence())
  self.assertEqual(obs.transport_metadata(),{'capture_status':'unavailable','records':[]})
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
 print('GUARD_EVENTS:',fx.BLOCKED,flush=True);sys.exit(0 if result.wasSuccessful() and not fx.BLOCKED else 1)
