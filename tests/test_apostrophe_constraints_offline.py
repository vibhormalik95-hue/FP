"""Conservative quote-state checks, not semantic accuracy evidence."""
import unittest
from feedctrl.source_constraints import literal_requirements
class ApostropheConstraints(unittest.TestCase):
 def terms(self,text):return literal_requirements('',text)['terms']
 def test_contraction_and_possessive_inside_quote_keep_digits(self):
  for intro in ('of','conditions'):
   for opening,apostrophe,closing in [("'","'","'"),('‘','’','’'),('"',"'",'"'),('“','’','”')]:
    text=f'Require {opening}it{apostrophe}s all two {intro}: (1) the item exists; (2) the owners{apostrophe} item remains{closing}.'
    with self.subTest(text=text):self.assertEqual(self.terms(text),['1','2'])
 def test_contractions_outside_quote_keep_structural_exception(self):
  for apostrophe in ("'",'’'):
   for intro in ('of','conditions'):
    text=f'All two {intro}: (1) the item{apostrophe}s condition isn{apostrophe}t missing; (2) its rating is IP68.'
    self.assertEqual(self.terms(text),['ip68'])
 def test_ambiguous_trailing_apostrophes_fail_closed(self):
  for apostrophe in ("'",'’'):
   for intro in ('of','conditions'):
    for body in [f'the owners{apostrophe} item exists',f'the James{apostrophe} item exists',f'the text is {apostrophe}ready{apostrophe}']:
     self.assertEqual(self.terms(f'All two {intro}: (1) {body}; (2) the rating is IP68.'),['1','2','ip68'])
 def test_mixed_outer_list_and_quoted_list_preserve_facts(self):
  for intro in ('of','conditions'):
   for quote in ('"','“'):
    closing='”' if quote=='“' else quote
    text=f'All two {intro}: (1) the text is {quote}it\'s all two {intro}: (1) the owners\' item exists; (2) the item remains{closing}; (2) the rating is IP68.'
    self.assertEqual(self.terms(text),['1','2','ip68'])
 def test_single_quote_ambiguity_retains_outer_labels_too(self):
  self.assertEqual(self.terms("All two conditions: (1) the text is 'ready'; (2) the rating is IP68."),['1','2','ip68'])
 def test_malformed_lists_and_unmatched_quotes_stay_literal(self):
  for text in ["All two conditions: (1) the item's state exists; (3) the owners' item remains.","All two of: (1) the item's state exists; (2) the item remains; extra", "Require 'it's all two of: (1) the item exists; (2) the item remains"]:
   self.assertEqual(self.terms(text),self.terms(text.replace('all two','any two').replace('All two','Any two')))
 def test_escaped_quotes_do_not_change_quote_state(self):
  self.assertEqual(self.terms(r'''Require 'it\'s all two conditions: (1) the item exists; (2) the owners\' item remains'.'''),['1','2'])
