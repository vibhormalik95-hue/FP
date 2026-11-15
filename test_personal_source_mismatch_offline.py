"""Runtime identity checks in a temporary copy, without provider access."""
import json,shutil,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT));BLOCKED=[]
def guard(event,args):
 if event.startswith('socket.') or event in {'subprocess.Popen','os.system','os.spawn','os.exec','os.fork','ctypes.dlopen'}:
  BLOCKED.append(event);raise RuntimeError('offline_blocked')
sys.addaudithook(guard)
from diagnostic import qualification as q
class Checks(unittest.TestCase):
 def test_docs_changes_do_not_affect_identity_but_source_and_fixture_changes_do(self):
  with tempfile.TemporaryDirectory() as tmp:
   target=Path(tmp).absolute();manifest=json.loads((ROOT/'diagnostic'/'source-pins.json').read_bytes())
   names=set(manifest['files'])|set(q.PINS)
   for name in names:
    dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,dest)
   (target/'README.md').write_text('different documentation',encoding='utf-8')
   (target/'CURRENT-SOURCE-SHA256.txt').write_text('different documentation manifest',encoding='utf-8')
   with patch.object(q,'ROOT',target):
    q.verify_package()
    app=target/'feedctrl'/'api.py';original=app.read_bytes();app.write_bytes(original+b'\n# changed\n')
    with self.assertRaises(q.QualificationError):q.verify_package()
    app.write_bytes(original)
    fixture=target/'scenarios'/'categories-and-tags'/'metadata.csv';original=fixture.read_bytes();fixture.write_bytes(original+b'\n')
    with self.assertRaises(q.QualificationError):q.verify_package()
    fixture.write_bytes(original)
    (target/'feedctrl'/'unexpected.py').write_text('pass',encoding='utf-8')
    with self.assertRaises(q.QualificationError):q.verify_package()
  self.assertEqual(BLOCKED,[])
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks));print('GUARD_EVENTS:',BLOCKED,flush=True);sys.exit(0 if result.wasSuccessful() and not BLOCKED else 1)
