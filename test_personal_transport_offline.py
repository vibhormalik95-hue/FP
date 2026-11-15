"""Offline adapter/stream/owned-loop composition with deterministic fake backends."""
import copy,hashlib,importlib.util,json,os,pathlib,sys,unittest
from unittest.mock import patch

ROOT=pathlib.Path(__file__).resolve().parent
CANDIDATE=ROOT
PINS={
 'feedctrl/claude_personal.py':'00805c05c96f7e18472496133101abfb30b912aca8f1e7faa348744db8ffd3eb',
 'feedctrl/windows_job_runner.py':'693931dbf1b02e121a38dab0e150857b589071b347fc7f763dfa5c831d9b41b4',
 'diagnostic/diagnostic_transport.py':'46f8e2ad315678a492472135ac4b0246e64eb964b9e0380de9270bd0953555e3',
 'diagnostic/rejection_observer.py':'30f6c19924fac26ceea934ca03d79039f52ed042b4d99a641659f670ed5a1440',
 'diagnostic/stream_projection.py':'e527bf52da8d819a0963afa02159d6b5b95908e371bc305f487f966e3256f7b6',
}
for name,pin in PINS.items():
 if hashlib.sha256((CANDIDATE/name).read_bytes()).hexdigest()!=pin:raise RuntimeError('Pinned source changed')
BLOCKED=[]
def guard(event,args):
 if (event.startswith('socket.') or event in {'subprocess.Popen','os.system','os.spawn','os.posix_spawn','os.exec','os.fork','os.forkpty','ctypes.dlopen'}
     or (event=='import' and args and (str(args[0]).split('.')[0] in {'anthropic','openai','ollama','torch','transformers'} or str(args[0])=='feedctrl.windows_job_native'))):
  BLOCKED.append(event);raise RuntimeError('Blocked offline operation')
sys.addaudithook(guard)
sys.path[:0]=[str(CANDIDATE),str(CANDIDATE/'diagnostic')]
from feedctrl import claude_personal as adapter
from feedctrl import windows_job_runner as windows
from feedctrl.model_adapters import HostedRunBudget
from diagnostic import diagnostic_transport as transport

MODEL='claude-offline-test'
CANARY='PRIVATE_SYNTHETIC_REFUSAL_CANARY'
SCHEMA={'type':'object','additionalProperties':False,'required':['title'],'properties':{'title':{'type':'string'}}}
PAYLOAD={'system':'Synthetic test only','brief':'Imaginary garden'}

def terminal():
 return {'type':'result','subtype':'success','is_error':False,'num_turns':1,'stop_reason':'end_turn',
         'permission_denials':[],'usage':{'input_tokens':1,'output_tokens':1},
         'modelUsage':{MODEL:{}},'total_cost_usd':0,'result':'{"title":"Imaginary garden"}'}
def stream(*frames):
 return b'\n'.join(json.dumps(frame,separators=(',',':')).encode() for frame in frames)+b'\n'

class Clock:
 def __init__(self):self.value=0.0
 def now(self):return self.value
 def sleep(self,amount):self.value+=amount

class FakeRun:
 def __init__(self,data,mode):
  self.data=data;self.mode=mode;self.events=[]
 def poll(self,limit):
  self.events.append('poll')
  if self.mode=='timeout':return b'',False,False,None,1
  return self.data,True,True,0,0
 def terminate(self):self.events.append('terminate')
 def cleanup_complete(self):
  self.events.append('cleanup_complete')
  return self.mode!='cleanup_uncertain'
 def finish_io(self,deadline):self.events.append('finish_io');return True
 def check_io(self):self.events.append('check_io')
 def close(self):self.events.append('close')

class FakeBackend:
 def __init__(self,data,mode='success'):
  self.data=data;self.mode=mode;self.launches=[];self.run=None
 def launch(self,argv,input_bytes,env,cwd,maximum,deadline):
  self.launches.append((copy.deepcopy(argv),bytes(input_bytes),copy.deepcopy(env),cwd,maximum,deadline))
  self.run=FakeRun(self.data,self.mode)
  return self.run

class Harness:
 def __init__(self,mode='safe_mode',frames=None,backend_mode='success',wrapper_mode=None,mutate=None,max_calls=2,max_output_tokens=4096):
  self.clock=Clock()
  self.backend=FakeBackend(stream(*(frames if frames is not None else [terminal()])),backend_mode)
  def loop(*args):
   return windows.run_with_backend(*args,backend=self.backend,now=self.clock.now,
                                   sleep=self.clock.sleep,cleanup_timeout=0.05)
  self.transport=transport.DiagnosticRunner(loop,runtime_mode=wrapper_mode or mode)
  def runner(argv,*args):
   if mutate is not None:argv=mutate(list(argv))
   return self.transport(argv,*args)
  opts=dict(executable=str(ROOT/'missing-cli'),workdir=str(ROOT/'missing-cwd'),model=MODEL,
            effort='max',run_budget=HostedRunBudget(max_calls),estimated_per_invocation_usd=0.5,
            output_mode='plain_json',runtime_authorized=True,data_authorized=True,
            subscription_and_usage_authorized=True,executable_reviewed=True,
            managed_runtime_reviewed=True,process_containment_reviewed=True,
            reviewed_cli_version='2.1.321',max_response_bytes=4096,timeout=0.05,max_output_tokens=max_output_tokens,
            process_runner=runner)
  if mode=='reviewed_hooks':
   opts.update(runtime_mode=mode,reviewed_hooks_context_sha256='a'*64)
  self.infer,self.provenance,self.receipts=adapter.make_claude_personal_infer(**opts)
 def invoke(self):
  with patch.dict(os.environ,{'SYSTEMROOT':r'C:\Windows','PATH':r'C:\Windows\System32'},clear=True), \
       patch.object(pathlib.Path,'is_file',return_value=True),patch.object(pathlib.Path,'is_dir',return_value=True):
   return self.infer(PAYLOAD,SCHEMA)

class HooksTransportTests(unittest.TestCase):
 def test_both_modes_accept_valid_stream_and_preserve_cleanup(self):
  for mode in ('safe_mode','reviewed_hooks'):
   with self.subTest(mode=mode):
    h=Harness(mode);self.assertEqual(h.invoke(),{'title':'Imaginary garden'})
    self.assertEqual(len(h.backend.launches),1);argv=h.backend.launches[0][0]
    self.assertEqual('--safe-mode' in argv,mode=='safe_mode')
    self.assertEqual(argv[argv.index('--output-format')+1],'stream-json')
    self.assertIn('--verbose',argv);self.assertIn('--include-partial-messages',argv)
    self.assertEqual(h.transport.records[0]['projection']['ok'],True)
    self.assertTrue(all(x in h.backend.run.events for x in ('terminate','cleanup_complete','finish_io','check_io','close')))
    self.assertEqual(h.receipts[0]['outcome'],'parsed_transport_only')
 def test_refusal_content_followed_by_success_is_rejected_in_both_modes(self):
  refusal={'type':'assistant','message':{'role':'assistant','content':[{'type':'refusal','refusal':CANARY}]}}
  for mode in ('safe_mode','reviewed_hooks'):
   with self.subTest(mode=mode):
    h=Harness(mode,[refusal,terminal()])
    with self.assertRaises(adapter.PersonalCliMessage):h.invoke()
    self.assertEqual(len(h.backend.launches),1)
    self.assertEqual(h.transport.records[0]['projection']['error'],'assistant_operational_failure')
    self.assertNotIn(CANARY,json.dumps(h.transport.records))
 def test_refusal_delta_followed_by_success_is_rejected(self):
  frames=[{'type':'stream_event','event':{'type':'message_start','message':{'type':'message','role':'assistant','content':[]}}},
          {'type':'stream_event','event':{'type':'message_delta','delta':{'stop_reason':'refusal'}}},
          {'type':'stream_event','event':{'type':'message_stop'}},terminal()]
  h=Harness('reviewed_hooks',frames)
  with self.assertRaises(adapter.PersonalCliMessage):h.invoke()
  self.assertEqual(h.transport.records[0]['projection']['error'],'assistant_operational_failure')
  self.assertEqual(len(h.backend.launches),1)
 def test_timeout_stops_and_confirms_fake_cleanup(self):
  h=Harness('reviewed_hooks',backend_mode='timeout')
  with self.assertRaises(adapter.PersonalCliMessage) as caught:h.invoke()
  self.assertIsInstance(caught.exception.__cause__,TimeoutError)
  self.assertFalse(h.transport.records[0]['runner_returned'])
  self.assertTrue(all(x in h.backend.run.events for x in ('terminate','cleanup_complete','finish_io','close')))
  self.assertEqual(len(h.backend.launches),1)
 def test_uncertain_cleanup_latches_and_prevents_next_call(self):
  h=Harness('reviewed_hooks',backend_mode='cleanup_uncertain')
  with self.assertRaises(adapter.PersonalCliMessage) as caught:h.invoke()
  self.assertIsInstance(caught.exception.__cause__,windows.CleanupUncertain)
  with self.assertRaises(adapter.PersonalCliMessage):h.invoke()
  self.assertEqual(len(h.backend.launches),1);self.assertEqual(len(h.transport.records),1)
  self.assertIn('terminate',h.backend.run.events);self.assertIn('finish_io',h.backend.run.events)
  self.assertIn('close',h.backend.run.events)
 def test_oversized_output_is_rejected_and_fake_cleanup_runs(self):
  h=Harness('reviewed_hooks')
  h.backend.data=b'x'*4097
  with self.assertRaises(adapter.PersonalCliMessage) as caught:h.invoke()
  self.assertIsInstance(caught.exception.__cause__,windows.WindowsRunnerError)
  self.assertFalse(h.transport.records[0]['runner_returned'])
  self.assertTrue(all(x in h.backend.run.events for x in ('terminate','finish_io','close')))
  self.assertEqual(len(h.backend.launches),1)
 def test_unexpected_arguments_rejected_before_backend_in_both_modes(self):
  for mode in ('safe_mode','reviewed_hooks'):
   def mutate(argv):
    argv[argv.index('--permission-mode')+1]='unexpected-mode'
    return argv
   with self.subTest(mode=mode):
    h=Harness(mode,mutate=mutate)
    with self.assertRaises(adapter.PersonalCliMessage) as caught:h.invoke()
    self.assertIsInstance(caught.exception.__cause__,transport.DiagnosticTransportError)
    self.assertEqual(h.backend.launches,[]);self.assertEqual(h.transport.records,[])
 def test_mismatched_mode_layouts_are_rejected_before_backend(self):
  for adapter_mode,wrapper_mode in (('safe_mode','reviewed_hooks'),('reviewed_hooks','safe_mode')):
   with self.subTest(adapter_mode=adapter_mode):
    h=Harness(adapter_mode,wrapper_mode=wrapper_mode)
    with self.assertRaises(adapter.PersonalCliMessage):h.invoke()
    self.assertEqual(h.backend.launches,[]);self.assertEqual(h.transport.records,[])
 def test_invalid_mode_is_rejected_before_runner(self):
  for mode in (None,False,'','other'):
   with self.subTest(mode=mode),self.assertRaises(transport.DiagnosticTransportError):
    transport.DiagnosticRunner(lambda *a:None,runtime_mode=mode)
 def test_max_tokens_and_multi_turn_never_accepted(self):
  truncated=terminal();truncated['stop_reason']='max_tokens'
  multiple=terminal();multiple['num_turns']=2
  truncated_then_multiple=[
   {'type':'stream_event','event':{'type':'message_start','message':{'type':'message','role':'assistant','content':[]}}},
   {'type':'stream_event','event':{'type':'message_delta','delta':{'stop_reason':'max_tokens'}}},
   {'type':'stream_event','event':{'type':'message_stop'}},multiple]
  for frames in ([truncated],[multiple],truncated_then_multiple):
   with self.subTest(frames=frames):
    h=Harness('reviewed_hooks',frames)
    with self.assertRaises(adapter.PersonalCliMessage):h.invoke()
    self.assertEqual(len(h.backend.launches),1)
 def test_explicit_one_call_budget_blocks_second_dispatch(self):
  h=Harness('reviewed_hooks',max_calls=1)
  self.assertEqual(h.invoke(),{'title':'Imaginary garden'})
  with self.assertRaises(Exception):h.invoke()
  self.assertEqual(len(h.backend.launches),1)
 def test_guard_events_remain_empty(self):self.assertEqual(BLOCKED,[])

if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(HooksTransportTests))
 print('GUARD_EVENTS:',BLOCKED,flush=True)
 sys.exit(0 if result.wasSuccessful() and not BLOCKED else 1)
