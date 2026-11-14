"""Offline reference grammar and retained-definition regression checks."""
import hashlib,importlib.util,json,sys,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parents[1];ROOT=HERE
events=[]
def guard(event,args):
 if event.startswith('socket.') or event in {'subprocess.Popen','os.system','os.spawn','os.exec','os.startfile','ctypes.dlopen'}:
  events.append(event);raise RuntimeError('forbidden operation')
sys.addaudithook(guard);spec=importlib.util.spec_from_file_location('r5_candidate',HERE/'feedctrl/source_constraints.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
BASE='All three of the following: (1) an item is damaged; (2) the item is fixed; and (3) the item is kept.'
class References(unittest.TestCase):
 def terms(self,t,objective=''):return m.literal_requirements(objective,t)['terms']
 def test_long_subjects_and_reference_verbs(self):
  subjects=['A stated purpose or capability of future use does not by itself satisfy','A described consequence after the repair does not satisfy','The observed item must satisfy','The reported evidence can satisfy','A documented decision could meet','The stated outcome violates','The described result contradicts','The observed action fulfilled']
  for subject in subjects:
   for number in (1,2,3):
    for style in (str(number),'('+str(number)+')'):
     with self.subTest(subject=subject,style=style):self.assertEqual(self.terms(BASE+' '+subject+' condition '+style+'.'),[])
 def test_reference_is_occurrence_only(self):
  text=BASE+' The item has 3 bolts and 4.5 volts. A stated purpose does not satisfy condition 3.'
  self.assertEqual(self.terms(text,'A minimum of 2 days.'),['2','3','4.5'])
 def test_quoted_or_inscription_is_not_masked(self):
  cases=['The required inscription reads: it must satisfy condition 3.','The label is: it must satisfy condition 3.','The password is satisfy condition 3.','The text says "satisfy condition 3".','It must include `satisfy condition 3`.','The caption must display satisfy condition 3.','The stated text is satisfy condition 3.','The reported identifier is satisfy condition 3.','The stated key is satisfy condition 3.']
  for text in cases:
   with self.subTest(text=text):self.assertIn('3',self.terms(BASE+' '+text))
 def test_unbound_malformed_and_ambiguous_references_fail_closed(self):
  cases=[('A stated purpose cannot satisfy condition 4.','4'),('A stated purpose cannot satisfy condition 03.','03'),('A stated purpose cannot satisfy condition 3.5.','3.5'),('A stated purpose cannot satisfy condition 3-5.','3-5')]
  for text,n in cases:
   with self.subTest(text=text):self.assertIn(n,self.terms(BASE+' '+text))
  self.assertIn('3',self.terms('The outcome satisfies condition 3.'))
  self.assertIn('3',self.terms(BASE+' Both: (1) the item exists; (2) the item is kept. The outcome satisfies condition 3.'))
  self.assertIn('3',self.terms(BASE,'The outcome satisfies condition 3.'))
 def test_quoted_reference_in_objective_or_definition_remains(self):
  self.assertIn('3',self.terms(BASE+' The phrase "satisfy condition 3" is required.'))
  self.assertIn('3',self.terms(BASE,'The task is to say "satisfy condition 3".'))
 def test_other_numbers_are_never_erased(self):
  self.assertEqual(self.terms(BASE+' The item bears number 3. Its score is 9. The stated outcome satisfies condition 3.'),['3','9'])
 def test_invalid_or_extra_list_fails_closed(self):
  t='All three of: (1) the item is valid; (2) the item is ready; (4) the item is kept. The item satisfies condition 3.'
  self.assertIn('3',self.terms(t));self.assertIn('1',self.terms(t))
 def test_no_factual_truth_claim_or_guard_events(self):
  d=m.literal_requirements('',BASE+' The stated result satisfies condition 3.');self.assertFalse(d['semantic_truth_verified']);self.assertTrue(d['necessary_only']);self.assertEqual(events,[])
if __name__=='__main__':
 r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(References));print('Guard events:',events);sys.exit(not r.wasSuccessful() or bool(events))
