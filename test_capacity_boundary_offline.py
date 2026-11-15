"""Focused offline capacity boundary and unchanged acceptance checks."""
import contextlib,hashlib,io,json,os,pathlib,sys,tempfile,types,unittest
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parent
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
import test_personal_transport_offline as fx
def capacity_harness(*args,**kwargs):
 kwargs['max_output_tokens']=32768
 return fx.Harness(*args,**kwargs)
from diagnostic import qualification as q,build_context as builder
from feedctrl import claude_personal as adapter
class Checks(unittest.TestCase):
 def test_source_identity(self):
  q.verify_package()
 def test_fake_success_uses_32768_and_owned_cleanup(self):
  h=capacity_harness('reviewed_hooks',max_calls=1);self.assertEqual(h.invoke(),{'title':'Imaginary garden'})
  self.assertEqual(h.backend.launches[0][2]['CLAUDE_CODE_MAX_OUTPUT_TOKENS'],'32768')
  self.assertTrue(all(x in h.backend.run.events for x in ('terminate','cleanup_complete','finish_io','check_io','close')))
  with self.assertRaises(Exception):h.invoke()
  self.assertEqual(len(h.backend.launches),1)
 def test_transport_boundary_and_cleanup_uncertainty(self):
  h=capacity_harness('reviewed_hooks');h.invoke();argv,data,env,cwd,maximum,deadline=h.backend.launches[0]
  argv=list(argv);index=argv.index('--output-format');argv[index+1]='json';argv.remove('--verbose');argv.remove('--include-partial-messages')
  self.assertIsNone(fx.transport._validate(argv,data,env,cwd,0.05,maximum,'reviewed_hooks'))
  env=dict(env);env['CLAUDE_CODE_MAX_OUTPUT_TOKENS']='32769'
  self.assertEqual(fx.transport._validate(argv,data,env,cwd,0.05,maximum,'reviewed_hooks'),'invalid_environment')
  h=capacity_harness('reviewed_hooks',backend_mode='cleanup_uncertain')
  with self.assertRaises(adapter.PersonalCliMessage):h.invoke()
  with self.assertRaises(adapter.PersonalCliMessage):h.invoke()
  self.assertEqual(len(h.backend.launches),1)
 def test_multi_turn_and_refusal_still_rejected(self):
  multi=fx.terminal();multi['num_turns']=2
  refusal={'type':'assistant','message':{'role':'assistant','content':[{'type':'refusal','refusal':'private synthetic'}]}}
  for frames in ([multi],[refusal,fx.terminal()]):
   with self.subTest(frames=len(frames)):
    h=capacity_harness('reviewed_hooks',frames)
    with self.assertRaises(adapter.PersonalCliMessage):h.invoke()
    self.assertEqual(len(h.backend.launches),1)
    self.assertTrue(all(x in h.backend.run.events for x in ('terminate','cleanup_complete','finish_io','close')))
 def test_above_bound_rejected_before_dispatch(self):
  original=adapter.make_claude_personal_infer
  def above(**kwargs):kwargs['max_output_tokens']=32769;return original(**kwargs)
  with patch.object(adapter,'make_claude_personal_infer',side_effect=above):
   with self.assertRaises(ValueError):capacity_harness('reviewed_hooks')
 def test_fake_context_builder_and_qualification_boundary(self):
  with tempfile.TemporaryDirectory(prefix='comp-capacity-test-') as d:
   p=pathlib.Path(d);home=p/'home';plugin=p/'plugin';out=p/'context.json';home.mkdir();(home/'.claude').mkdir();(home/'.claude'/'settings.json').write_text('{}')
   (plugin/'.claude-plugin').mkdir(parents=True);(plugin/'hooks').mkdir();(plugin/'skills'/'caveman').mkdir(parents=True)
   manifest={'hooks':{k:[{'hooks':[{'command':'node fixture.js'}]}] for k in ('SessionStart','UserPromptSubmit')}}
   (plugin/'.claude-plugin'/'plugin.json').write_text(json.dumps(manifest));(plugin/'skills'/'caveman'/'SKILL.md').write_text('synthetic')
   for x in ('caveman-activate.js','caveman-mode-tracker.js','caveman-config.js'):(plugin/'hooks'/x).write_text('synthetic')
   cli=p/'claude.exe';node=p/'node.exe';cli.write_bytes(b'fake-cli');node.write_bytes(b'fake-node')
   args=['build_context','--cli',str(cli),'--home',str(home),'--plugin',str(plugin),'--node',str(node),'--output',str(out),'--tokens','32768']
   with patch.object(sys,'argv',args),contextlib.redirect_stdout(io.StringIO()):builder.main()
   value=q._load_context(out,h(out));self.assertEqual(value['max_output_tokens'],'32768')
   value['max_output_tokens']='32769';bad=p/'bad.json';bad.write_text(json.dumps(value))
   with self.assertRaises(q.QualificationError):q._load_context(bad,h(bad))
   with patch.object(sys,'argv',args[:-1]+['32769']),contextlib.redirect_stderr(io.StringIO()):
    with self.assertRaises(SystemExit):builder.main()
 def test_telemetry_helper_unchanged(self):
  self.assertEqual(h(ROOT/'diagnostic/transport_evidence.py'),'49db92370df26afd324867e8bfd078c4be94e8970ae40f689864e63e1caaf262')
  self.assertEqual(fx.BLOCKED,[])
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
 print('GUARD_EVENTS:',fx.BLOCKED,flush=True);sys.exit(0 if result.wasSuccessful() and not fx.BLOCKED else 1)
