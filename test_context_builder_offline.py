"""Synthetic context generation and qualification; no hook or CLI is run."""
import contextlib,hashlib,io,json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT));BLOCKED=[]
def guard(event,args):
 if event.startswith('socket.') or event in {'subprocess.Popen','os.system','os.spawn','os.exec','os.fork','ctypes.dlopen'}:BLOCKED.append(event);raise RuntimeError('offline_blocked')
sys.addaudithook(guard)
from diagnostic import build_context as build,qualification as q
class Checks(unittest.TestCase):
 def test_builder_and_qualifier_agree_and_never_overwrite(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp).absolute();home=root/'home';plugin=home/'.claude'/'plugins'/'cache'/'fake';work=root/'work';work.mkdir()
   cli=root/'cli';node=root/'node';cli.write_bytes(b'fake cli');node.write_bytes(b'fake node')
   def put(path,data):path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
   def js(v):return json.dumps(v,separators=(',',':')).encode()
   hooks={k:[{'hooks':[{'command':'synthetic-'+k}]}] for k in ('SessionStart','UserPromptSubmit')}
   put(plugin/'.claude-plugin'/'plugin.json',js({'hooks':hooks}));put(plugin/'skills'/'caveman'/'SKILL.md',b'fake skill')
   for name in ('caveman-activate.js','caveman-mode-tracker.js','caveman-config.js'):put(plugin/'hooks'/name,b'fake hook')
   put(home/'.claude'/'settings.json',js({'enabledPlugins':{'fake':True}}))
   put(home/'.claude'/'plugins'/'installed_plugins.json',js({'plugins':{'fake':[{'installPath':str(plugin)}]}}))
   output=root/'context.json';env={'PATH':'synthetic-path','HOME':str(home),'USERPROFILE':str(home),'HOMEDRIVE':home.drive,'HOMEPATH':str(home)[len(home.drive):]}
   argv=['builder','--cli',str(cli),'--home',str(home),'--plugin',str(plugin),'--node',str(node),'--output',str(output),'--tokens','4096']
   with patch.dict(os.environ,env,clear=True),patch.object(sys,'argv',argv),patch.object(q.shutil,'which',return_value=str(node)),contextlib.redirect_stdout(io.StringIO()):
    build.main();context_sha=hashlib.sha256(output.read_bytes()).hexdigest()
    result=q.preflight(context_file=output,context_sha256=context_sha,cli=cli,workdir=work,home=home)
    self.assertTrue(result['qualified']);self.assertFalse(result['authorization_established']);self.assertEqual(result['live_calls'],0)
    reviewed=json.loads(output.read_bytes());child=q._expected_child_environment(reviewed,home)
    context={'context_file':output,'context_sha256':context_sha,'cli':cli,'workdir':work,'home':home};marker=root/'marker';calls=[]
    with patch.object(q,'_require_bootstrap'):
     runner=q._BoundCalls(lambda *args:calls.append(1) or 'fake',context,marker,2)
     args=([str(cli)],b'{}',child,str(work),1,100)
     self.assertEqual(runner(*args),'fake')
     (home/'.claude'/'settings.json').write_bytes(b'{}')
     with self.assertRaises(q.QualificationError):runner(*args)
    self.assertEqual(calls,[1]);self.assertTrue(marker.exists());self.assertFalse(marker.with_name('marker.2').exists())
    old=output.read_bytes()
    with self.assertRaises(ValueError):build.main()
    self.assertEqual(output.read_bytes(),old)
  self.assertEqual(BLOCKED,[])
if __name__=='__main__':
 r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks));print('GUARD_EVENTS:',BLOCKED,flush=True);sys.exit(0 if r.wasSuccessful() and not BLOCKED else 1)
