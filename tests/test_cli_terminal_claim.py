import importlib.util,json,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
relay=types.ModuleType('relay_tools')
relay.wait_for_request=lambda *a: {'request_sha256':'abc'}
relay.render=lambda r:'synthetic offline request'
relay.problem=lambda *a:None
relay.deliver=lambda *a:None
spec=importlib.util.spec_from_file_location('candidate',Path(__file__).resolve().parents[1] / 'scripts' / 'relay_claude_cli.py')
m=importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {'relay_tools': relay}):
 spec.loader.exec_module(m)
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.spool=Path(self.tmp.name)
  self.args=types.SimpleNamespace(wait=1,model='test-model',effort='low',max_budget_usd=1,timeout=1,allow_other_models=False)
 def envelope(self,**kw):
  e=dict(type='result',subtype='success',is_error=False,stop_reason='end_turn',num_turns=1,result='{}',modelUsage={'test-model':{}});e.update(kw);return e
 def run_call(self,e):
  done=types.SimpleNamespace(returncode=0,stdout=json.dumps(e).encode(),stderr=b'')
  with patch.object(m.subprocess,'run',return_value=done) as run,patch.object(relay,'deliver') as deliver:
   try:m.one_call(self.spool,1,'fake.exe',self.args)
   except SystemExit:pass
   return run.call_count,deliver.call_count
 def test_strict_envelope_decode(self):
  bad = ('{"stop_reason":"refusal","stop_reason":"end_turn"}',
         '{"usage":{"n":1,"n":2}}', '{"n":NaN}', '{"n":Infinity}', '{"n":-Infinity}', '{"n":1e999}', '{"n":-1e999}')
  for raw in bad:
   with self.subTest(raw=raw):
    with self.assertRaises(ValueError):m.strict_result_json(raw)
 def test_duplicate_refusal_not_delivered_or_retried(self):
  raw=json.dumps(self.envelope()).replace('"stop_reason": "end_turn"','"stop_reason": "refusal", "stop_reason": "end_turn"')
  done=types.SimpleNamespace(returncode=0,stdout=raw.encode(),stderr=b'')
  with patch.object(m.subprocess,'run',return_value=done) as run,patch.object(relay,'deliver') as deliver:
   with self.assertRaises(SystemExit):m.one_call(self.spool,1,'fake.exe',self.args)
   self.assertEqual(run.call_count,1);deliver.assert_not_called()
  before={p.name:p.read_bytes() for p in self.spool.iterdir()}
  self.assertEqual(self.run_call(self.envelope()),(0,0))
  self.assertEqual(before,{p.name:p.read_bytes() for p in self.spool.iterdir()})
 def test_normal_success(self):
  self.assertEqual(self.run_call(self.envelope()),(1,1))
 def test_refusal_rejected_and_no_repeat(self):
  self.assertEqual(self.run_call(self.envelope(stop_reason='refusal')),(1,0))
  before={p.name:p.read_bytes() for p in self.spool.iterdir()}
  self.assertEqual(self.run_call(self.envelope()),(0,0))
  self.assertEqual(before,{p.name:p.read_bytes() for p in self.spool.iterdir()})
 def test_envelope_matrix(self):
  for n in (None,0,2,3,True,1.0,'1'):
   self.assertIsNotNone(m.terminal_result_problem(self.envelope(num_turns=n)))
  for stop in (None,'refusal','max_tokens','tool_use','unknown'):
   self.assertIsNotNone(m.terminal_result_problem(self.envelope(stop_reason=stop)))
  for kw in ({'is_error':True},{'is_error':0},{'subtype':'error'},{'type':'message'}):
   self.assertIsNotNone(m.terminal_result_problem(self.envelope(**kw)))
 def test_legacy_receipt_blocks(self):
  p=self.spool/'cli-call-0001.json';p.write_bytes(b'legacy')
  self.assertEqual(self.run_call(self.envelope()),(0,0));self.assertEqual(p.read_bytes(),b'legacy')
 def test_response_blocks_direct_entry(self):
  (self.spool/'response-0001.json').write_text('{}')
  self.assertEqual(self.run_call(self.envelope()),(0,0))
 def test_incomplete_marker_blocks(self):
  (self.spool/'cli-attempt-0001.json').write_bytes(b'')
  self.assertEqual(self.run_call(self.envelope()),(0,0))
 def test_concurrent_claim(self):
  def attempt(_):
   try:m.claim_attempt(self.spool,1,'abc');return True
   except SystemExit:return False
  with ThreadPoolExecutor(max_workers=8) as pool:self.assertEqual(sum(pool.map(attempt,range(8))),1)
 def test_changed_hash_blocks(self):
  m.claim_attempt(self.spool,1,'abc')
  with self.assertRaises(SystemExit):m.claim_attempt(self.spool,1,'changed')
 def test_interrupt_leaves_claim(self):
  with patch.object(m.subprocess,'run',side_effect=KeyboardInterrupt):
   with self.assertRaises(KeyboardInterrupt):m.one_call(self.spool,1,'fake.exe',self.args)
  self.assertEqual(self.run_call(self.envelope()),(0,0))
 def test_timeout_leaves_claim(self):
  with patch.object(m.subprocess,'run',side_effect=m.subprocess.TimeoutExpired('fake',1)):
   with self.assertRaises(SystemExit):m.one_call(self.spool,1,'fake.exe',self.args)
  self.assertEqual(self.run_call(self.envelope()),(0,0))
 def test_delivery_failure_blocks_restart(self):
  done=types.SimpleNamespace(returncode=0,stdout=json.dumps(self.envelope()).encode(),stderr=b'')
  with patch.object(m.subprocess,'run',return_value=done),patch.object(relay,'deliver',side_effect=OSError('offline injected')):
   with self.assertRaises(OSError):m.one_call(self.spool,1,'fake.exe',self.args)
  self.assertEqual(self.run_call(self.envelope()),(0,0))
 def test_next_ordinal_allowed(self):
  m.claim_attempt(self.spool,1,'abc');m.claim_attempt(self.spool,2,'def')
if __name__=='__main__':unittest.main(verbosity=2)
