"""Synthetic-only two-call marker, context and failure-latch regressions."""
import os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT));BLOCKED=[]
def guard(event,args):
 if event.startswith('socket.') or event in {'subprocess.Popen','os.system','os.spawn','os.exec','os.fork','ctypes.dlopen'}:
  BLOCKED.append(event);raise RuntimeError('offline_blocked')
sys.addaudithook(guard)
from diagnostic import qualification as q
class Checks(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).absolute();self.work=self.root/'work';self.work.mkdir();self.cli=self.root/'cli';self.cli.write_bytes(b'fake')
  self.ctx={'cli':self.cli,'workdir':self.work,'home':self.root,'context_file':self.root/'context','context_sha256':'a'*64};self.env={'synthetic':'value'}
  self.patches=[patch.object(q,'_require_bootstrap'),patch.object(q,'preflight'),patch.object(q,'_load_context',return_value={'child_env_sha256':q._environment_digest(self.env)}),patch.object(q,'_expected_child_environment',return_value=self.env)]
  for x in self.patches:x.start()
  self.call=([str(self.cli)],b'{}',self.env,str(self.work),1,100)
 def tearDown(self):
  for x in reversed(self.patches):x.stop()
  self.tmp.cleanup()
 def test_two_calls_each_consumed_then_budget_exhausted(self):
  calls=[];marker=self.root/'marker';runner=q._BoundCalls(lambda *a:calls.append(1) or 'ok',self.ctx,marker,2)
  self.assertEqual(runner(*self.call),'ok');self.assertEqual(runner(*self.call),'ok')
  with self.assertRaises(q.QualificationError):runner(*self.call)
  self.assertEqual(calls,[1,1]);self.assertEqual(marker.read_bytes(),b'consumed\n');self.assertEqual(marker.with_name('marker.2').read_bytes(),b'consumed\n')
  self.assertEqual(q.preflight.call_count,2);self.assertEqual(q._require_bootstrap.call_count,2)
 def test_first_failure_and_cleanup_uncertainty_prevent_second(self):
  for exc in (RuntimeError('fake refusal'),RuntimeError('fake cleanup uncertain')):
   marker=self.root/('marker'+str(id(exc)));calls=[]
   def failed(*args):calls.append(1);raise exc
   runner=q._BoundCalls(failed,self.ctx,marker,2)
   with self.assertRaises(RuntimeError):runner(*self.call)
   with self.assertRaises(q.QualificationError):runner(*self.call)
   self.assertEqual(calls,[1]);self.assertTrue(marker.exists());self.assertFalse(marker.with_name(marker.name+'.2').exists())
 def test_context_changes_before_second_dispatch_stop_without_second_marker(self):
  calls=[];marker=self.root/'marker';runner=q._BoundCalls(lambda *a:calls.append(1) or 'ok',self.ctx,marker,2)
  self.assertEqual(runner(*self.call),'ok')
  with patch.object(q,'preflight',side_effect=q.QualificationError('changed')):
   with self.assertRaises(q.QualificationError):runner(*self.call)
  with self.assertRaises(q.QualificationError):runner(*self.call)
  self.assertEqual(calls,[1]);self.assertTrue(marker.exists());self.assertFalse(marker.with_name('marker.2').exists())
 def test_second_marker_collision_fails_closed(self):
  calls=[];marker=self.root/'marker';marker.with_name('marker.2').write_bytes(b'existing')
  runner=q._BoundCalls(lambda *a:calls.append(1) or 'ok',self.ctx,marker,2)
  self.assertEqual(runner(*self.call),'ok')
  with self.assertRaises(q.QualificationError):runner(*self.call)
  self.assertEqual(calls,[1])
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks));print('GUARD_EVENTS:',BLOCKED,flush=True);sys.exit(0 if result.wasSuccessful() and not BLOCKED else 1)
