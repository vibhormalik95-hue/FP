"""Synthetic protocol fixtures only; not a semantic benchmark or real catalogue."""
import copy
import unittest
from feedctrl.indirect_grounding import propose_indirect

class GroundingTests(unittest.TestCase):
    def setUp(self):
        self.index = {'sha256': 'a' * 64, 'items': {
            1: {'fields': {'caption': '烹饪米饭和蔬菜', 'first_level_category_name': '美食'}},
            2: {'fields': {'caption': '修理自行车', 'first_level_category_name': '维修'}},
            3: {'fields': {'caption': '弹奏钢琴', 'first_level_category_name': '音乐'}},
            4: {'fields': {'caption': '登山旅行', 'first_level_category_name': '旅行'}}}}
        self.action = {'operation': 'exclude', 'strength': 'none', 'intent_span': 'makes me hungry'}
        self.request = 'I am not hungry, hide what makes me hungry'
        self.raw = {'status': 'propose', 'reason': 'Prepared meals may trigger appetite.',
            'negation_resolved': True, 'alternatives': [],
            'evidence': [{'item_id': 1, 'field': 'caption', 'quote': '烹饪米饭和蔬菜'}]}
        self.provenance = {'backend': 'test-double', 'model': 'synthetic-contract-fixture', 'digest': 'not-a-real-model'}
    def run_proposal(self, **kwargs):
        return propose_indirect(self.request, self.action, self.index,
            lambda p, s: copy.deepcopy(self.raw), model_provenance=self.provenance, **kwargs)
    def test_zero_overlap_only_review(self):
        result = self.run_proposal()
        self.assertEqual(result['status'], 'review')
        self.assertEqual(result['item_ids'], [1])
        self.assertTrue(result['requires_review'])
        self.assertEqual(result['action'], self.action)
    def test_general_contract_not_hunger_rule(self):
        self.request = 'Show more things that help me commute without petrol'
        self.action = {'operation': 'boost', 'strength': 'light', 'intent_span': 'commute without petrol'}
        self.raw['evidence'] = [{'item_id': 2, 'field': 'caption', 'quote': '修理自行车'}]
        self.raw['reason'] = 'Bicycle maintenance supports cycling.'
        self.assertEqual(self.run_proposal()['item_ids'], [2])
    def test_callback_cannot_fabricate_authoritative_evidence(self):
        def mutate(payload, schema):
            payload['catalogue'][0]['fields']['caption'] = 'Fabricated food evidence'
            self.raw['evidence'][0]['quote'] = 'Fabricated food evidence'
            return self.raw
        r = propose_indirect(self.request, self.action, self.index, mutate, model_provenance=self.provenance)
        self.assertEqual(r['status'], 'error')
    def test_response_not_aliased_after_return(self):
        r = propose_indirect(self.request, self.action, self.index, lambda *_: self.raw,
                             model_provenance=self.provenance)
        self.raw['evidence'][0]['item_id'] = 999
        self.assertEqual(r['evidence'][0]['item_id'], 1)
        self.assertEqual(r['item_ids'], [1])
    def test_callback_cannot_change_action_or_index(self):
        before = copy.deepcopy(self.action)
        def mutate(*_):
            self.action.update(operation='boost', strength='strong')
            self.index['items'].clear()
            return self.raw
        r = propose_indirect(self.request, self.action, self.index, mutate, model_provenance=self.provenance)
        self.assertEqual(r['status'], 'review')
        self.assertEqual(r['action'], before)
    def test_callback_cannot_change_schema(self):
        def mutate(payload, schema):
            schema['required'].clear()
            return self.raw
        r = propose_indirect(self.request, self.action, self.index, mutate, model_provenance=self.provenance)
        self.assertEqual(r['status'], 'review')
        self.assertEqual(self.run_proposal()['status'], 'review')
    def test_unresolved_no_match_clarifies(self):
        self.raw.update(status='no_match', negation_resolved=False, evidence=[])
        self.assertEqual(self.run_proposal()['status'], 'clarify')
        self.raw.update(negation_resolved=True, alternatives=['metaphorical meaning'])
        self.assertEqual(self.run_proposal()['status'], 'clarify')
    def test_mixed_id_types_rejected_cleanly(self):
        self.index['items']['five'] = {'fields': {'caption': 'x'}}
        with self.assertRaises(ValueError): self.run_proposal()
    def test_non_string_action_rejected_cleanly(self):
        self.action['operation'] = []
        with self.assertRaises(ValueError): self.run_proposal()
        self.action['operation'] = 'exclude'
        self.action['strength'] = []
        with self.assertRaises(ValueError): self.run_proposal()
    def test_curly_apostrophe_command_negation(self):
        self.request = 'Don’t hide what makes me hungry'
        self.assertEqual(self.run_proposal()['status'], 'clarify')
    def test_modified_command_negation(self):
        self.request = 'Do not ever hide what makes me hungry'
        self.assertEqual(self.run_proposal()['status'], 'clarify')
    def test_non_json_response(self):
        self.raw['reason'] = float('nan')
        self.assertEqual(self.run_proposal()['status'], 'error')
    def test_unhashable_status(self):
        self.raw['status'] = {}
        self.assertEqual(self.run_proposal()['status'], 'error')
    def test_absent_item(self):
        self.raw['evidence'][0]['item_id'] = 999
        self.assertEqual(self.run_proposal()['status'], 'error')
    def test_invented_quote(self):
        self.raw['evidence'][0]['quote'] = 'food never in catalogue'
        self.assertEqual(self.run_proposal()['status'], 'error')
    def test_wrong_field(self):
        self.raw['evidence'][0]['field'] = 'search_text'
        self.assertEqual(self.run_proposal()['status'], 'error')
    def test_duplicate_item(self):
        self.raw['evidence'] *= 2
        self.assertEqual(self.run_proposal()['status'], 'error')
    def test_boolean_id(self):
        self.raw['evidence'][0]['item_id'] = True
        self.assertEqual(self.run_proposal()['status'], 'error')
    def test_no_match(self):
        self.raw.update(status='no_match', evidence=[])
        self.assertEqual(self.run_proposal()['status'], 'no_match')
    def test_abstention_with_evidence(self):
        self.raw['status'] = 'ambiguous'
        self.assertEqual(self.run_proposal()['status'], 'error')
    def test_ambiguity(self):
        self.raw['alternatives'] = ['hunger for knowledge']
        self.assertEqual(self.run_proposal()['status'], 'clarify')
    def test_unresolved_negation(self):
        self.raw['negation_resolved'] = False
        self.assertEqual(self.run_proposal()['status'], 'clarify')
    def test_command_negation(self):
        self.request = "Don't hide what makes me hungry"
        self.assertEqual(self.run_proposal()['status'], 'clarify')
    def test_overbroad(self):
        self.raw['evidence'] = [{'item_id': i, 'field': 'caption', 'quote': x['fields']['caption']}
            for i, x in list(self.index['items'].items())[:3]]
        self.assertEqual(self.run_proposal()['status'], 'clarify')
    def test_no_silent_truncation(self):
        self.assertEqual(self.run_proposal(max_items=3)['status'], 'clarify')
        self.assertEqual(self.run_proposal(max_chars=100)['status'], 'clarify')
    def test_source_and_request_binding(self):
        a = self.run_proposal()['provenance']
        self.index['items'][1]['fields']['caption'] += '!'
        b = self.run_proposal()['provenance']
        self.assertNotEqual(a['catalogue_sha256'], b['catalogue_sha256'])
        self.request += '!'
        self.assertNotEqual(b['request_sha256'], self.run_proposal()['provenance']['request_sha256'])
    def test_no_mutation(self):
        before = copy.deepcopy((self.index, self.action, self.raw))
        self.run_proposal()
        self.assertEqual(before, (self.index, self.action, self.raw))
    def test_inference_failure(self):
        def fail(*_): raise TimeoutError()
        r = propose_indirect(self.request, self.action, self.index, fail, model_provenance=self.provenance)
        self.assertEqual(r['status'], 'error')
        self.assertEqual(r['item_ids'], [])
    def test_schema_rejects_operation_changes(self):
        self.raw['operation'] = 'boost'
        self.assertEqual(self.run_proposal()['status'], 'error')
    def test_intent_must_be_request_bound(self):
        self.action['intent_span'] = 'unmentioned meaning'
        with self.assertRaises(ValueError): self.run_proposal()
    def test_invalid_strength(self):
        self.action['strength'] = 'strong'
        with self.assertRaises(ValueError): self.run_proposal()
    def test_missing_source_provenance(self):
        del self.index['sha256']
        with self.assertRaises(ValueError): self.run_proposal()
    def test_empty_selection_abstains(self):
        self.raw['evidence'] = []
        self.assertEqual(self.run_proposal()['status'], 'no_match')

if __name__ == '__main__': unittest.main()
