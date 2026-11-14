"""Static validator-to-prompt consistency; no app or provider invocation."""
import ast,copy,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'feedctrl';events=[]
def guard(e,a):
 if e.startswith('socket.') or e in {'subprocess.Popen','os.system','os.spawn','os.exec','os.startfile','ctypes.dlopen'}:events.append(e);raise RuntimeError('blocked')
sys.addaudithook(guard)
def tree(p):return ast.parse(p.read_bytes())
def assigned(t,name):return next(x for x in t.body if isinstance(x,ast.Assign) and any(isinstance(y,ast.Name) and y.id==name for y in x.targets))
def function(t,name):return next(x for x in t.body if isinstance(x,(ast.FunctionDef,ast.AsyncFunctionDef)) and x.name==name)
def text_limits(f):
 out=[]
 for n in ast.walk(f):
  if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='_text':
   out.append((ast.unparse(n.args[0]),ast.literal_eval(n.args[1]) if len(n.args)>1 and isinstance(n.args[1],ast.Constant) else None))
 return out
class Contract(unittest.TestCase):
 def test_validator_bounds_match_prompt(self):
  st=tree(BASE/'staged_induction.py');audit=tree(BASE/'evidence_audit.py');producer=tree(BASE/'category_induction_producer.py');fn=function(producer,'_text');self.assertEqual(ast.literal_eval(fn.args.defaults[0]),2000)
  d=assigned(tree(BASE/'staged_induction.py'),'DEFINITION_PROMPT').value.value;member=assigned(tree(BASE/'staged_induction.py'),'MEMBERSHIP_PROMPT').value.value;ap=assigned(tree(BASE/'evidence_audit.py'),'PROMPT').value.value
  for v in ('80 Unicode code points','1000','2000','at most 10 alternatives and 24 evidence records','field name must be at most 100','reason at most 1000','U+0000-U+001F','without line breaks'):self.assertIn(v,d)
  for v in ('100 Unicode code points','2000','reason at most 1000'):self.assertIn(v,member)
  for v in ('100 Unicode code points','2000','reason at most 800'):self.assertIn(v,ap)
  self.assertIn(("raw['label']",80),text_limits(function(st,'_validate_candidate')));self.assertIn(("raw['definition']",1000),text_limits(function(st,'_validate_candidate')))
  code=ast.unparse(function(st,'propose_definition'));self.assertIn("len(raw['alternatives']) > 10",code);self.assertIn("len(raw['evidence']) > 24",code);self.assertIn("('rationale', 2000)",code)
  check=ast.unparse(function(st,'_validate_candidate'));self.assertIn('is_printable_label',check);self.assertIn('ord(c) < 32',check)
  self.assertIn(("row['field']",100),text_limits(function(st,'_validate_candidate')));self.assertIn(("row['quote']",None),text_limits(function(st,'_validate_candidate')));self.assertIn(("row['reason']",1000),text_limits(function(st,'_validate_candidate')))
  self.assertIn(("row['field']",100),text_limits(function(st,'classify_rows')));self.assertIn(("row['evidence_quote']",None),text_limits(function(st,'classify_rows')));self.assertIn(("row['reason']",1000),text_limits(function(st,'classify_rows')))
  self.assertIn(("row['field']",100),text_limits(function(audit,'_checked_rows')));self.assertIn(("row['quote']",None),text_limits(function(audit,'_checked_rows')));self.assertIn(("row['reason']",800),text_limits(function(audit,'_checked_rows')))
 def test_preserve_numbers_modality_and_exact_quotes(self):
  d=assigned(tree(BASE/'staged_induction.py'),'DEFINITION_PROMPT').value.value;a=assigned(tree(BASE/'evidence_audit.py'),'PROMPT').value.value
  for phrase in ('unnumbered prose','Restate each condition in words','do not omit or alter meaningful numbers','Copy quotations exactly','Do not truncate meaning or quotations'):self.assertIn(phrase,d)
  for phrase in ('does not establish that an\naction happened','may support a definition that asks\nfor that stated state','preserve its tense and modality','not ground truth'):self.assertIn(phrase,a)
 def test_guard_events(self):self.assertEqual(events,[])
if __name__=='__main__':
 r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Contract));print('Guard events:',events);sys.exit(not r.wasSuccessful() or bool(events))
