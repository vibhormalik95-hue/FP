"""Historical input binding is explicit; no provider or process is invoked."""
import ast,hashlib,importlib.util,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];TOOL=ROOT/'tools/hosted_validation_current';events=[]
def guard(event,args):
 if event.startswith('socket.') or event in {'subprocess.Popen','os.system','os.spawn','os.exec','os.startfile','ctypes.dlopen'}:
  events.append(event);raise RuntimeError('blocked offline operation')
sys.addaudithook(guard)
spec=importlib.util.spec_from_file_location('historical_driver',TOOL/'driver.py');driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
from feedctrl.model_adapters import _json
first=json.loads((TOOL/'inputs/01-category-discovery/first-model-input.json').read_bytes());tree=ast.parse((ROOT/'feedctrl/staged_induction.py').read_bytes());current=next(n.value.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='DEFINITION_PROMPT' for x in n.targets))
def rendered(system):return system+'\n\nReturn exactly one JSON object matching this schema. Do not use Markdown, prose, or additional text. Schema: '+_json(first['schema']).decode('utf8')
def body():return _json({k:v for k,v in first['payload'].items() if k!='system'})
class HistoricalBoundary(unittest.TestCase):
 def test_frozen_input_and_manifest_preserved(self):
  sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
  self.assertEqual(sha(TOOL/'inputs/01-category-discovery/first-model-input.json'),'c91994a1e52945315d625ab3df337eeffcd668b7ec9c301d8d40b2be60651c45')
  self.assertEqual(sha(TOOL/'inputs/MANIFEST.json'),'e4e36c14e3947324e1f34458f49df432130c7b5904aefda672953daabbb91655');self.assertEqual(driver.INPUT_MANIFEST_SHA256,'e4e36c14e3947324e1f34458f49df432130c7b5904aefda672953daabbb91655')
 def test_revised_prompt_fails_before_runner(self):
  self.assertNotEqual(current,first['payload']['system']);hits=[];report={'model_inputs':[]};checkpoints=[]
  wrapped=driver.capturing_runner(lambda *args:hits.append(True),{'first':first},report,lambda:checkpoints.append(True))
  with self.assertRaisesRegex(ValueError,'First logical payload/schema differs'):wrapped(['--system-prompt',rendered(current)],body(),{},'synthetic',1,1)
  self.assertEqual((hits,report['model_inputs'],checkpoints),([],[],[]))
 def test_matching_historical_input_reaches_only_fake_runner(self):
  hits=[];report={'model_inputs':[]};checkpoints=[]
  def fake(*args):hits.append(True);return 0,b'synthetic'
  wrapped=driver.capturing_runner(fake,{'first':first},report,lambda:checkpoints.append(True))
  self.assertEqual(wrapped(['--system-prompt',rendered(first['payload']['system'])],body(),{},'synthetic',1,1),(0,b'synthetic'))
  self.assertEqual(hits,[True]);self.assertEqual(report['model_inputs'][0]['status'],'runner_returned');self.assertEqual(len(checkpoints),2)
 def test_documented_boundary_and_links(self):
  s=(TOOL/'README.md').read_text(encoding='utf-8');self.assertIn('rejects the revised application',s);self.assertIn('not provide a current ready-to-run hosted',s);self.assertIn('historical profile',s.casefold());self.assertTrue((TOOL/'../../docs/app.md').resolve().is_file());self.assertTrue((TOOL/'../../docs/hosted-only-configuration.md').resolve().is_file());self.assertEqual(events,[])
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(HistoricalBoundary));print('Guard events:',events);sys.exit(not result.wasSuccessful() or bool(events))
