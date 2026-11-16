"""Fake-binder test of actual app construction; never invokes a provider."""
import hashlib, importlib.util, os, sys, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent
ACT_VALUE=os.environ.get('COMP_OFFLINE_CURATED_ACTIVATOR')
if ACT_VALUE:
 ACTIVATOR=Path(ACT_VALUE);assert hashlib.sha256(ACTIVATOR.read_bytes()).hexdigest()=='e1ca525c4ea0743f9c7c1a3e964b3f719740c5e141d318dac3bf8d6f924fcaf3'
elif not (os.environ.get('COMP_OFFLINE_USE_STANDARD_SITE')=='1' and sys.flags.isolated and not sys.flags.no_site and sys.prefix!=sys.base_prefix):
 raise RuntimeError('explicit isolated venv or reviewed curated activator required')
BLOCKED=[]
def guard(event,args):
 if (event.startswith('socket.') or event in {'subprocess.Popen','os.system','os.spawn','os.exec','os.fork','ctypes.dlopen'} or (event=='import' and args and (str(args[0]).split('.')[0] in {'anthropic','openai','ollama','torch','transformers'} or args[0]=='feedctrl.windows_job_native'))):
  BLOCKED.append(event);raise RuntimeError('offline_blocked')
sys.addaudithook(guard)
if ACT_VALUE:
 spec=importlib.util.spec_from_file_location('curated_runtime',ACTIVATOR)
 runtime=importlib.util.module_from_spec(spec);spec.loader.exec_module(runtime);runtime.activate()
sys.path.insert(0,str(ROOT))
from diagnostic import app_binding
APPROVALS={k:True for k in app_binding._APPROVALS}
CTX={'context_file':ROOT/'fake-context','context_sha256':'a'*64,'cli':str(ROOT/'fake-cli'),'workdir':str(ROOT),'home':str(ROOT)}
ARGS=dict(context=CTX,marker=ROOT/'fake-marker',allowed_origin='http://127.0.0.1:8000',model='claude-offline-test',effort='max',estimated_per_invocation_usd=5,output_mode='plain_json',reviewed_cli_version='2.1.321',approvals=APPROVALS,reviewed_files={},fixture=True)
class Checks(unittest.TestCase):
 def test_default_and_incomplete_review_fail_before_binding(self):
  with patch.object(app_binding.bootstrap,'bind_once') as bind:
   with self.assertRaises(ValueError):app_binding.construct(**ARGS)
   with self.assertRaises(ValueError):app_binding.construct(enable_live=True,**dict(ARGS,approvals={}))
   bind.assert_not_called()
 def test_actual_fixture_app_constructs_with_fake_binder_only(self):
  calls=[]
  def fake_runner(*args):calls.append(args);raise AssertionError('unexpected dispatch')
  fake=SimpleNamespace(_load_context=lambda *a:{'max_output_tokens':'16384'},_hash_string=lambda x:len(x)==64,_digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest())
  with tempfile.TemporaryDirectory() as tmp:
   sidecar=Path(tmp)/'captions.csv';sidecar.write_text('video_id,manual_cover_text,caption,topic_tag,first_level_category_name,second_level_category_name,third_level_category_name\n'+''.join(f'{i},,An invented caption.,,,,\n' for i in range(1,37)),encoding='utf-8')
   args=dict(ARGS,semantic_path=sidecar,reviewed_files={str(sidecar):hashlib.sha256(sidecar.read_bytes()).hexdigest()})
   with patch.object(app_binding.bootstrap,'bind_once',return_value=(fake_runner,[])) as bind, patch.object(app_binding.bootstrap,'_load',return_value=fake):
    app,observations=app_binding.construct(enable_live=True,**args)
   self.assertIsNotNone(app);self.assertEqual(observations,[]);self.assertEqual(calls,[])
   self.assertTrue(bind.call_args.kwargs['enable_live']);self.assertEqual(BLOCKED,[])
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
 print('GUARD_EVENTS:',BLOCKED,flush=True);sys.exit(0 if result.wasSuccessful() and not BLOCKED else 1)
