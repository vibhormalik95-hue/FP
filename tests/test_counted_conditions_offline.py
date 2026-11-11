"""Exact hosted-text extraction regression plus authored syntax contracts.

Strings from SAFE-SEMANTIC-EXTRACT.json, SHA256
7ed6b8ce0f3f5d6da4099adf3c6186e16365cc335fcc320b04dc3a3f58585025.
Original report SHA256 b0280161fbeb837227c0fffb8612788d83f99033930519a418265469000ebc52.
Classification never ran: evidence review was declined. No accuracy claim.
"""
import unittest
from feedctrl.source_constraints import literal_requirements, source_witnesses
OBJECTIVE = 'Propose one useful new category from these eight descriptions. Decide the shared concept yourself from the stated facts, rather than taking an existing category code as its meaning. Give a precise definition supported by the descriptions; do not merely rename an existing category or invent missing facts.'
DEFINITION = 'An item matches when its description affirmatively states all three conditions: (1) an already-existing object has a stated defect or damage; (2) a corrective action is performed on that same object; and (3) that same object is kept or returned to use afterward. An item is not a match only when the description affirmatively shows a condition is false, for example the damaged object is discarded and a different one takes its place, or the stated outcome is a newly made object rather than the restoration of an existing one. If the description does not say whether damage, repair or retention occurred (for example, the subject or activity is not described), membership is unknown, not negative. Tool type, material, power source and the original K code are irrelevant to membership.'

class CountedConditionsTests(unittest.TestCase):
    def terms(self, text):
        return literal_requirements('', text)['terms']

    def test_exact_latest_definition(self):
        result = literal_requirements(OBJECTIVE, DEFINITION)
        self.assertEqual(result['terms'], [])
        self.assertTrue(result['necessary_only'])
        self.assertFalse(result['semantic_truth_verified'])

    def test_counts_and_existing_conjunction_positions(self):
        for count, word in enumerate(('two','three','four','five','six','seven','eight','nine','ten'),2):
            for placement in ('none','last','every'):
                clauses = [('and ' if i > 1 and (placement == 'every' or placement == 'last' and i == count) else '') + f'({i}) the item has rating {i}' for i in range(1,count+1)]
                text = f'All {word} conditions: ' + '; '.join(clauses)
                with self.subTest(count=count, placement=placement):
                    self.assertEqual(self.terms(text), sorted(str(i) for i in range(1,count+1)))
                    self.assertEqual(self.terms(text.replace(' has rating ', ' has code X')), sorted(f'x{i}' for i in range(1,count+1)))
                    self.assertEqual(literal_requirements(text, '')['terms'], self.terms(text))

    def test_factual_digits_and_witnesses_survive(self):
        text = 'All three conditions: (1) the rating is "1" and (2); (2) an ID is AB-123 with version 5.4; and (3) that item has [3] units and 0.5 kg.'
        terms = ['0.5','1','2','3','5.4','ab-123']
        self.assertEqual(self.terms(text), terms)
        self.assertEqual(source_witnesses(literal_requirements('',text), {'caption':'An item is retained.'})['missing'], terms)

    def test_quoted_or_nested_list_remains_literal(self):
        text = 'all two conditions: (1) the item exists; and (2) the item is kept'
        for left,right in [('"','"'),("'","'"),('“','”'),('`','`'),('(',')'),('[',']'),('{','}')]:
            with self.subTest(left=left):
                self.assertEqual(self.terms('Require '+left+text+right), ['1','2'])
        self.assertEqual(self.terms('all two conditions: (1) the quote is "'+text+'"; and (2) the value is (9).'), ['1','2','9'])

    def test_malformed_and_unsupported_conjunctions_stay_literal(self):
        base = 'all three conditions: (1) the object exists; (2) the object is fixed; and (3) the object is kept'
        cases = [base.replace('; and (3)', ' and (3)'), base.replace('; and (3)', '; or (3)'), base.replace('; (2)', '; and and (2)'), base.replace(': (1)', ': and (1)'), base.replace('(2)', '(4)'), base.replace('(2)', '(1)'), base.replace('(3)', '(03)'), base.replace('(3)', '(3.0)'), base.replace('three conditions', '3 conditions'), base.replace('three conditions', 'three criteria'), base.replace('three conditions', 'three condition'), base.replace('; (2)', '; ; (2)'), base+';', base+'; (4) the item is new', base+'; (4.5) the item is new', base+'; commentary', base+' "', base+' [', base.replace('(2)', '[(2)]'), base.replace('and (3)', 'and "(3) the extra;" (3)')]
        for text in cases:
            with self.subTest(text=text):
                # Compare to unchanged literal extraction by omitting the introduction.
                self.assertEqual(self.terms(text), self.terms(text.replace('all ', 'any ', 1)))

    def test_quoted_separator_does_not_complete_conditions(self):
        for text in ['all two conditions: (1) the text is "quoted; (2) the value is 8"', 'all two conditions: (1) the text is [nested; (2) the value is 8]', 'all two conditions: (1) the item is kept; (2) the value is 8; "extra"']:
            with self.subTest(text=text):
                self.assertEqual(self.terms(text), ['1','2','8'])

    def test_independent_inputs_and_nfkc(self):
        text = 'ALL TWO CONDITIONS: （１） the item is kept; AND （２） the item has ９ units.'
        self.assertEqual(self.terms(text), ['9'])
        self.assertEqual(literal_requirements('Require "1" and (2).',text)['terms'], ['1','2','9'])
        self.assertEqual(literal_requirements('all two conditions: (1) the item exists;', '(2) the item is kept')['terms'], ['1','2'])
