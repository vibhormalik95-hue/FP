"""Authored rehearsal data regressions, not model accuracy or browser proof."""
import csv
import importlib.util
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('replies',ROOT/'scripts/demo_scripted_replies.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
class RehearsalGrounding(unittest.TestCase):
    def test_dispositions(self):
        self.assertEqual({i:v[0] for i,v in r._CATEGORY_MEMBERSHIP.items()},dict.fromkeys([41001,41002,41003],'match')|{41004:'not_match'}|dict.fromkeys([41005,41006,41007,41008],'unknown'))
    def test_missing_conditions_not_negatives(self):
        for i in (41005,41006):
            self.assertEqual(r._CATEGORY_MEMBERSHIP[i][:2],('unknown',''))
            self.assertEqual(r._CATEGORY_AUDIT[i][:2],('not_stated',''))
            self.assertIn('not stated',r._CATEGORY_MEMBERSHIP[i][2])
    def test_quotes_are_literal(self):
        with (ROOT/'tools/hosted_validation_current/inputs/01-category-discovery/metadata.csv').open(encoding='utf-8-sig',newline='') as f:
            captions={int(row['video_id']):row['caption'] for row in csv.DictReader(f)}
        for table in (r._CATEGORY_MEMBERSHIP,r._CATEGORY_AUDIT):
            for i,(_,quote,reason) in table.items():
                if quote:self.assertIn(quote,captions[i])
    def test_retention_quote_and_modality(self):
        self.assertIn('The same bag is kept.',r._CATEGORY_AUDIT[41002][1])
        self.assertIn('so it can carry books again.',r._CATEGORY_AUDIT[41002][1])
    def test_diagram_description_not_overclaimed(self):
        self.assertEqual(r._CATEGORY_AUDIT[41007][2],'No completed activity or finished object is described.')
    def test_positive_set_unchanged(self):
        self.assertEqual([i for i,v in r._CATEGORY_MEMBERSHIP.items() if v[0]=='match'],[41001,41002,41003])
    def test_rehearsal_labels_retained(self):
        self.assertIn('authored rehearsal',r._CATEGORY_DEFINITION['label'])
        payload={'catalogue':[{'item_id':i} for i in r._CATEGORY_IDS],'reviewed_definition':r._CATEGORY_DEFINITION}
        response=r.lookup(payload,{'required':['memberships']})
        self.assertTrue(all(row['reason'].startswith('Authored rehearsal reply, not model output.') for row in response['memberships']))
if __name__=='__main__':unittest.main()
