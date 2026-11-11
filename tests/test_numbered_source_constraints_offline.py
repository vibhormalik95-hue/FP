"""Offline syntax/audit contracts, not new inference or semantic ground truth.

REAL_DEFINITION and REAL_CAPTIONS are verbatim text from the retained review copy
FABLE-TWO-SCENARIO-REVIEW-COPY.json (SHA-256
c205c9171f1aa1296de41ddc772c6cfb23cd552d9c21d91768c0de10f778741c).
Its real run stopped for alternatives before classification; no replay is claimed.
All audit responses below are separately authored software fixtures.
"""
from copy import deepcopy
import unittest

from feedctrl.source_constraints import literal_requirements, source_witnesses
from feedctrl import evidence_audit as audit, staged_induction as staged

REAL_DEFINITION = 'An item belongs if its caption states all three of: (1) an already-existing object has a stated defect or damage (e.g. bent, torn, leaking); (2) that defect is fixed by a described repair action; and (3) the same object is kept or returned to use rather than discarded or replaced. Items are excluded if the object is replaced by a new one, if a new object is made from raw material or offcuts, or if no completed activity or subject is described.'
REAL_CAPTIONS = ['A bent metal bookmark is straightened with pliers and used again. The existing piece is kept.', 'A torn canvas satchel is mended with a needle and spare thread so it can carry books again. The same bag is kept.', 'A leaking clay jug is sealed and returned to watering plants. The same jug remains in use.', 'A broken desk organizer is put in recycling and a newly purchased organizer is unpacked in its place.', 'Paper offcuts are folded into a new tray. No glue or powered equipment is used.', 'A raw wooden blank is shaped with an electric lathe into a new knob.', 'A page of knot diagrams is shown. No completed activity or finished object is described.', 'The only notes are a blue background and a 20-second duration. The subject is not described.']
class NumberedRequirementsTests(unittest.TestCase):
    def terms(self, text, objective=''):
        return literal_requirements(objective, text)['terms']

    def test_exact_retained_real_definition_has_no_factual_digits(self):
        requirements = literal_requirements('', REAL_DEFINITION)
        self.assertEqual(requirements['terms'], [])
        self.assertTrue(requirements['necessary_only'])
        self.assertFalse(requirements['semantic_truth_verified'])
        for caption in REAL_CAPTIONS:
            self.assertEqual(source_witnesses(requirements, {'caption': caption})['missing'], [])
        # The original extractor required all three absent label digits.
        original = {'terms': ['1', '2', '3']}
        for caption in REAL_CAPTIONS:
            self.assertEqual(source_witnesses(original, {'caption': caption})['missing'], ['1', '2', '3'])

    def test_complete_counted_lists_in_either_input(self):
        examples = [
            'All two of: (1) the item is repaired; (2) the item is retained.',
            'All three of:\n(1) an object is repaired;\n(2) that object is retained;\nand (3) it is used.',
            'ALL TWO OF: （１） the item is repaired; and （２） its use continues.',
            'All ten of: ' + '; '.join(f'({i}) the condition is stated' for i in range(1, 11)),
            'All two of: (1) each item is repaired; and (2) every item is retained.',
        ]
        for example in examples:
            with self.subTest(example=example):
                self.assertEqual(self.terms(example), [])
                self.assertEqual(self.terms('', example), [])

    def test_mixed_numbers_are_not_removed_by_value(self):
        definition = ('All three of: (1) the item carries IP68 and a 90-point rating; '
                      '(2) a version 5.4 product has an 18-month plan and ID AB-123; '
                      'and (3) the record dated 2026-11-11 states 1 kg, 2 units and 3 uses.')
        self.assertEqual(self.terms(definition),
                         ['1', '18-month', '2', '2026-11-11', '3', '5.4', '90-point', 'ab-123', 'ip68'])
        self.assertEqual(self.terms(definition, 'Exactly 1 item with ID 001.'),
                         ['001', '1', '18-month', '2', '2026-11-11', '3', '5.4', '90-point', 'ab-123', 'ip68'])

    def test_parenthesized_factual_numbers_inside_and_outside_list_survive(self):
        definition = ('Exactly (1) unit; all two of: (1) the rating is (2); '
                      'and (2) the identifier is (3). Version (5.4), ISO-9001 and 0.5 kg apply.')
        self.assertEqual(self.terms(definition), ['0.5', '1', '2', '3', '5.4', 'iso-9001'])

    def test_ambiguous_or_malformed_numbering_stays_fail_closed(self):
        cases = [
            ('The rating is (1).', ['1']),
            ('(1) the item is repaired; (2) the item is retained.', ['1', '2']),
            ('Ratings: (1) star; (2) stars.', ['1', '2']),
            ('All two of: (1) kg of paint; (2) kg of putty.', ['1', '2']),
            ('All two of: (1) year of service; (2) years of support.', ['1', '2']),
            ('All two of: (1) the item is repaired.', ['1']),
            ('All three of: (1) the item is repaired; (3) the item is retained.', ['1', '3']),
            ('All two of: (2) the item is repaired; (3) the item is retained.', ['2', '3']),
            ('All two of: (1) the item is repaired; (1) the item is retained.', ['1']),
            ('All two of: (01) the item is repaired; (02) the item is retained.', ['01', '02']),
            ('All two of: (1.0) the item is repaired; (2.0) the item is retained.', ['1.0', '2.0']),
            ('All two of: (1A) the item is repaired; (2B) the item is retained.', ['1a', '2b']),
            ('All two of: (1) the item is repaired, (2) the item is retained.', ['1', '2']),
            ('All two of: (1) the item is repaired; (2) the item is retained; (3) the item is used.', ['1', '2', '3']),
            ('All two of: (1) the item is repaired; (2) the item is retained; or (3) the item is used.', ['1', '2', '3']),
            ('All two of: (1) the item is repaired; and (2)', ['1', '2']),
            ('All 2 of: (1) the item is repaired; (2) the item is retained.', ['1', '2']),
            ('All two of: (1) 90 points; (2) 5.4 volts.', ['1', '2', '5.4', '90']),
        ]
        for definition, expected in cases:
            with self.subTest(definition=definition):
                self.assertEqual(self.terms(definition), expected)

    def test_independent_lists_do_not_merge_across_objective_and_definition(self):
        self.assertEqual(self.terms('All two of: (2) the object is kept.',
                                   'All two of: (1) the object is repaired.'), ['1', '2'])
        self.assertEqual(self.terms('All two of: (1) the object is repaired; (2) the object is kept. '
                                   'All two of: (1) a plan exists; (2) its term is 18 months.'), ['18'])

    def test_negated_and_quoted_presence_does_not_prove_truth(self):
        requirements = literal_requirements('', 'All two of: (1) the rating is IP68; (2) the score is 90.')
        self.assertEqual(requirements['terms'], ['90', 'ip68'])
        self.assertFalse(requirements['semantic_truth_verified'])
        for caption in ('No IP68 rating or 90 points is claimed.', "A viewer asks 'IP68 and 90 points?'"):
            self.assertEqual(source_witnesses(requirements, {'caption': caption})['missing'], [])
        self.assertEqual(source_witnesses(requirements, {'caption': 'IP680 and 190 points.'})['missing'], ['90', 'ip68'])

    def test_numeric_witness_boundaries_and_equivalent_values_are_unchanged(self):
        requirements = literal_requirements('',
            'All two of: (1) the volume is 1.5 litres; and (2) the version is 5.4.')
        self.assertEqual(requirements['terms'], ['1.5', '5.4'])
        self.assertEqual(source_witnesses(requirements,
            {'caption': '15 litres with version 5.40.'})['missing'], ['1.5', '5.4'])
        self.assertEqual(source_witnesses(requirements,
            {'caption': '1.50 litres with version 5.4.1.'})['missing'], ['1.5', '5.4'])
        self.assertEqual(source_witnesses(requirements,
            {'caption': '1.5 litres with version 5.4.'})['missing'], [])


MODEL = {'backend': 'authored-fixture', 'model_id': 'no-model-call', 'model_revision': 'offline-only'}
DEFINITION = 'All two of: (1) the item has an IP68 rating; and (2) the item is kept in use.'


def audit_fixture(definition=DEFINITION, verdicts=('match', 'match', 'unknown', 'not_match')):
    objective = 'Find a useful stated property.'
    captions = ['An IP68-rated item is kept in use.', 'An item is kept in use; its rating is unstated.',
                'No property is stated.', 'No IP68 rating is claimed for this item.']
    index = {'sha256': 'a' * 64, 'items': {
        i: {'fields': {'caption': caption}} for i, caption in enumerate(captions, 1)}}
    inventory = [{'category_id': 'A', 'label': 'Original A', 'member_ids': [1, 3]},
                 {'category_id': 'B', 'label': 'Original B', 'member_ids': [2, 4]}]
    raw = {'status': 'propose', 'label': 'Authored contract fixture', 'definition': definition,
           'rationale': 'Authored software fixture, not model evidence.', 'alternatives': [],
           'evidence': [{'item_id': 1, 'field': 'caption', 'quote': captions[0],
                         'reason': 'Authored test citation.'}]}
    proposal = staged.propose_definition(objective, index, inventory, lambda *args: raw, MODEL)
    memberships = {'memberships': [{'item_id': i, 'verdict': verdict, 'field': 'caption',
                    'evidence_quote': captions[i - 1], 'reason': 'Authored software-test disposition.'}
                   for i, verdict in enumerate(verdicts, 1)]}
    primary = staged.classify_definition(proposal, objective, index, inventory, lambda *args: memberships, MODEL)
    return objective, index, inventory, primary


class NumberedAuditTests(unittest.TestCase):
    def run_audit(self, kinds=('supported',) * 4, **fixture_args):
        objective, index, inventory, primary = audit_fixture(**fixture_args)
        before = deepcopy(primary)
        assessment = {'assessments': [{'item_id': i, 'assessment': kind, 'field': 'caption',
                       'quote': index['items'][i]['fields']['caption'], 'reason': 'Authored software-test assessment.'}
                      for i, kind in enumerate(kinds, 1)]}
        result = audit.audit_membership_envelope(primary, objective, index, inventory, lambda *args: assessment, MODEL)
        self.assertEqual(primary, before)
        self.assertFalse(result['evidence_audit']['semantic_truth_verified'])
        self.assertTrue(result['requires_review'])
        audit.revalidate_audited_envelope(result, objective, index, inventory)
        if result['status'] == 'review':
            staged.revalidate_membership_envelope(result, objective, index, inventory)
        return result

    def test_labels_do_not_block_agreement_but_missing_factual_rating_does(self):
        result = self.run_audit()
        self.assertEqual(result['status'], 'review')
        self.assertEqual([r['item_id'] for r in result['field_evidence'] if r['verdict'] == 'match'], [1])
        self.assertEqual(result['unknown_ids'], [2, 3, 4])
        self.assertEqual(result['evidence_audit']['literal_constraints']['terms'], ['ip68'])
        self.assertEqual(result['evidence_audit']['withheld'][0]['missing_literal_terms'], ['ip68'])

    def test_removing_labels_never_upgrades_unknown_or_negative(self):
        result = self.run_audit(definition='All two of: (1) the item is repaired; (2) the item is retained.')
        self.assertEqual([r['item_id'] for r in result['field_evidence'] if r['verdict'] == 'match'], [1, 2])
        self.assertEqual(result['unknown_ids'], [3, 4])

    def test_audit_disagreement_still_withholds_every_positive(self):
        result = self.run_audit(kinds=('not_stated', 'ambiguous', 'supported', 'contradicted'))
        self.assertEqual(result['status'], 'clarify')
        self.assertIsNone(result['proposal'])
        self.assertEqual(result['unknown_ids'], [1, 2, 3])
        self.assertEqual(result['field_evidence'][3]['verdict'], 'not_match')

    def test_wrong_agreement_on_negation_is_still_not_claimed_as_truth(self):
        result = self.run_audit(verdicts=('match', 'match', 'unknown', 'match'))
        self.assertEqual([r['item_id'] for r in result['field_evidence'] if r['verdict'] == 'match'], [1, 4])
        self.assertFalse(result['evidence_audit']['semantic_truth_verified'])


class QuotedAndMalformedListTests(unittest.TestCase):
    """Corrected-revision cases, including every independent review failure."""
    def test_exact_independent_extraction_failures(self):
        cases = [
            ('The caption must contain the exact text "all two of: (1) a repair; (2) a reuse".', ['1', '2']),
            ('All two of: (1) the caption literally contains "ready; (2) a repair".', ['1', '2']),
            ('All two of: (1) the item is repaired; (2) the item is retained;; (3) the item is used.', ['1', '2', '3']),
            ('All two of: (1) the item is repaired; (2) the item is retained; (3.0) the item is used.', ['1', '2', '3.0']),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(literal_requirements('', text)['terms'], expected)
                self.assertEqual(literal_requirements(text, '')['terms'], expected)

    def test_quoted_required_digits_still_block_audit_positives(self):
        definition = 'The caption must contain the exact text "all two of: (1) a repair; (2) a reuse".'
        objective, index, inventory, primary = audit_fixture(definition=definition)
        assessment = {'assessments': [{'item_id': i, 'assessment': 'supported', 'field': 'caption',
            'quote': row['fields']['caption'], 'reason': 'Authored offline counterexample, not model output.'}
            for i, row in index['items'].items()]}
        result = audit.audit_membership_envelope(primary, objective, index, inventory, lambda *args: assessment, MODEL)
        audit.revalidate_audited_envelope(result, objective, index, inventory)
        self.assertEqual(result['status'], 'clarify')
        self.assertFalse(any(row['verdict'] == 'match' for row in result['field_evidence']))
        self.assertEqual(result['evidence_audit']['literal_constraints']['terms'], ['1', '2'])
        self.assertTrue(result['requires_review'])
        self.assertFalse(result['evidence_audit']['semantic_truth_verified'])

    def test_quotes_backticks_and_brackets_preserve_embedded_list_digits(self):
        embedded = 'all two of: (1) a repair; (2) a reuse'
        for opening, closing in [('"', '"'), ("'", "'"), ('“', '”'), ('‘', '’'),
                                 ('«', '»'), ('‹', '›'), ('`', '`'), ('``', '``'), ('```', '```'),
                                 ('(', ')'), ('[', ']'), ('{', '}')]:
            with self.subTest(delimiters=(opening, closing)):
                text = 'The exact field is ' + opening + embedded + closing + '.'
                self.assertEqual(literal_requirements('', text)['terms'], ['1', '2'])

    def test_quoted_and_bracketed_separators_do_not_complete_outer_list(self):
        for opening, closing in [('"', '"'), ("'", "'"), ('“', '”'), ('`', '`'),
                                 ('(', ')'), ('[', ']'), ('{', '}')]:
            with self.subTest(delimiters=(opening, closing)):
                text = 'All two of: (1) the field contains ' + opening + 'ready; (2) a repair' + closing + '.'
                self.assertEqual(literal_requirements('', text)['terms'], ['1', '2'])

    def test_quoted_body_facts_survive_but_real_outer_labels_do_not(self):
        text = 'All two of: (1) the caption contains "ready; (2) a repair"; and (2) the rating is "IP68; version 9.2".'
        self.assertEqual(literal_requirements('', text)['terms'], ['2', '9.2', 'ip68'])
        text = 'All two of: (1) the item\'s condition isn\'t missing; (2) its rating is IP68.'
        self.assertEqual(literal_requirements('', text)['terms'], ['ip68'])
        text = 'All two of: (1) the caption includes "say \\"ready; (2) a repair\\""; (2) its rating is IP68.'
        self.assertEqual(literal_requirements('', text)['terms'], ['2', 'ip68'])

    def test_any_trailing_top_level_semicolon_keeps_list_fail_closed(self):
        prefix = 'All two of: (1) the item is repaired; (2) the item is retained'
        for suffix, expected in [(';', ['1', '2']), ('; commentary.', ['1', '2']),
                                 (';;; (3) the item is used.', ['1', '2', '3']),
                                 ('; and (03) the item is used.', ['03', '1', '2']),
                                 ('; or [3] the item is used.', ['1', '2', '3'])]:
            with self.subTest(suffix=suffix):
                self.assertEqual(literal_requirements('', prefix + suffix)['terms'], expected)

    def test_unbalanced_or_mismatched_delimiters_disable_exception(self):
        text = 'All two of: (1) the item is repaired; (2) the item is retained.'
        for example in ['"' + text, '(' + text, '[' + text + ')', text + ' (unfinished',
                        text + ' "unfinished', text + ' ]']:
            with self.subTest(text=example):
                self.assertEqual(literal_requirements('', example)['terms'], ['1', '2'])


if __name__ == '__main__':
    unittest.main()
