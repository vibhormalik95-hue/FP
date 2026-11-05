import copy
import unittest
from feedctrl.category_induction_producer import propose_category, validate_current_source


def index():
    # Deliberately synthetic fixture records, not observed COMP catalogue items.
    return {'sha256': 'a'*64, 'items': {
        11: {'fields': {'caption': 'A bicycle trip through the city.'}},
        22: {'fields': {'caption': 'A tram trip through the city.'}},
        33: {'fields': {'caption': 'A cake in an oven.'}},
        44: {'fields': {}}}}


def raw():
    return {'status': 'propose', 'label': 'Low-emission city journeys',
        'definition': 'City journeys by bicycle or tram.', 'rationale': 'Synthetic inference double only.',
        'alternatives': [], 'memberships': [
            {'item_id': 11, 'verdict': 'match', 'field': 'caption', 'evidence_quote': 'bicycle trip', 'reason': 'Bicycle travel.'},
            {'item_id': 22, 'verdict': 'match', 'field': 'caption', 'evidence_quote': 'tram trip', 'reason': 'Tram travel.'},
            {'item_id': 33, 'verdict': 'not_match', 'field': 'caption', 'evidence_quote': 'cake in an oven', 'reason': 'Baking, not a journey.'},
            {'item_id': 44, 'verdict': 'unknown', 'field': '', 'evidence_quote': '', 'reason': 'No metadata.'}]}

MODEL = {'backend': 'offline-test-double', 'model_id': 'fixture-only', 'model_revision': 'v1'}
OBJ = 'Discover a useful travel category from existing metadata.'


class ProducerTests(unittest.TestCase):
    def produce(self, response=None, idx=None, **kwargs):
        return propose_category(OBJ, idx or index(), lambda p, s: copy.deepcopy(response if response is not None else raw()), model_provenance=MODEL, **kwargs)

    def test_contract_and_field_provenance(self):
        r = self.produce()
        self.assertEqual(r['status'], 'review')
        self.assertIs(r['requires_review'], True)
        self.assertEqual(r['unknown_ids'], [44])
        self.assertEqual(set(r['proposal']), {'label','definition','memberships'})
        self.assertEqual(set(r['proposal']['memberships'][0]), {'item_id','verdict','evidence_quote','reason'})
        self.assertEqual(r['field_evidence'][0]['field'], 'caption')
        self.assertEqual(r['audit']['candidate_ids'], [11,22,33,44])
        self.assertEqual(r['audit']['novelty_scope'], 'inventory unavailable')

    def test_unknown_item(self):
        r=raw();r['memberships'][0]['item_id']=999
        self.assertEqual(self.produce(r)['status'],'error')

    def test_boolean_item(self):
        r=raw();r['memberships'][0]['item_id']=True
        self.assertEqual(self.produce(r)['status'],'error')

    def test_duplicate_item(self):
        r=raw();r['memberships'][1]=copy.deepcopy(r['memberships'][0])
        self.assertEqual(self.produce(r)['status'],'error')

    def test_missing_candidate(self):
        r=raw();r['memberships'].pop()
        self.assertEqual(self.produce(r)['status'],'error')

    def test_fabricated_quote(self):
        r=raw();r['memberships'][0]['evidence_quote']='flying bicycle'
        self.assertEqual(self.produce(r)['status'],'error')

    def test_wrong_field(self):
        r=raw();r['memberships'][0]['field']='topic_tag'
        self.assertEqual(self.produce(r)['status'],'error')

    def test_no_quote_for_positive(self):
        r=raw();r['memberships'][0]['evidence_quote']=''
        self.assertEqual(self.produce(r)['status'],'error')

    def test_no_quote_for_negative(self):
        r=raw();r['memberships'][2]['evidence_quote']=''
        self.assertEqual(self.produce(r)['status'],'error')

    def test_unknown_with_fabricated_quote(self):
        r=raw();r['memberships'][3].update(field='caption', evidence_quote='fiction')
        self.assertEqual(self.produce(r)['status'],'error')

    def test_all_unknown_remains_visible_and_cannot_apply(self):
        r=raw()
        for m in r['memberships']:m.update(verdict='unknown',field='',evidence_quote='')
        out=self.produce(r)
        self.assertEqual(out['status'],'clarify')
        self.assertEqual(out['unknown_ids'],[11,22,33,44])
        self.assertEqual(len(out['field_evidence']),4)
        self.assertIsNone(out['proposal'])

    def test_all_known_negative_is_no_match(self):
        r=raw();r['memberships'].pop();idx=index();del idx['items'][44]
        for m in r['memberships']:m['verdict']='not_match'
        out=self.produce(r,idx=idx)
        self.assertEqual(out['status'],'no_match');self.assertEqual(out['unknown_ids'],[])
        self.assertIsNone(out['proposal'])

    def test_alternatives(self):
        r=raw();r['alternatives']=['All city scenes']
        self.assertEqual(self.produce(r)['status'],'clarify')
        self.assertIsNone(self.produce(r)['proposal'])

    def test_empty_abstention(self):
        r=raw();r.update(status='no_match',memberships=[],label='',definition='')
        self.assertEqual(self.produce(r)['status'],'no_match')

    def test_ambiguous_abstention(self):
        r=raw();r.update(status='ambiguous',memberships=[])
        self.assertEqual(self.produce(r)['status'],'clarify')

    def test_abstention_cannot_leak_members(self):
        r=raw();r['status']='no_match'
        self.assertEqual(self.produce(r)['status'],'error')

    def test_empty_catalogue_skips_inference(self):
        def infer(*a):raise AssertionError('Must not call')
        r=propose_category(OBJ,{'sha256':'a'*64,'items':{}},infer,model_provenance=MODEL)
        self.assertEqual(r['status'],'no_match')

    def test_oversize_skips_inference(self):
        def infer(*a):raise AssertionError('Must not call')
        for args in ({'max_items':1},{'max_bytes':1}):
            r=propose_category(OBJ,index(),infer,model_provenance=MODEL,**args)
            self.assertEqual(r['status'],'blocked')

    def test_invalid_budgets(self):
        for val in (True,0,-1,10001):
            with self.assertRaises(ValueError):self.produce(max_items=val)

    def test_model_failure(self):
        def infer(*a):raise RuntimeError('backend unavailable')
        self.assertEqual(propose_category(OBJ,index(),infer,model_provenance=MODEL)['status'],'error')

    def test_malformed_output(self):
        for r in ({},[],None,{'categories':[]}):
            out=propose_category(OBJ,index(),lambda *a:r,model_provenance=MODEL)
            self.assertEqual(out['status'],'error')

    def test_invalid_verdict(self):
        r=raw();r['memberships'][0]['verdict']='yes'
        self.assertEqual(self.produce(r)['status'],'error')

    def test_duplicate_label(self):
        cats=[{'category_id':'c','label':raw()['label'].upper(),'member_ids':[33]}]
        self.assertEqual(self.produce(existing_categories=cats)['status'],'duplicate')

    def test_duplicate_membership(self):
        cats=[{'category_id':'c','label':'Travel','member_ids':[11,22]}]
        self.assertEqual(self.produce(existing_categories=cats)['status'],'duplicate')

    def test_partial_overlap_preserved(self):
        cats=[{'category_id':'c','label':'City','member_ids':[11,33]}]
        r=self.produce(existing_categories=cats)
        self.assertEqual(r['status'],'review')
        self.assertEqual(r['overlaps'],[{'category_id':'c','member_ids':[11],'exact_set':False}])

    def test_callback_mutation_does_not_rewrite_source(self):
        idx=index();before=copy.deepcopy(idx)
        def infer(p,s):
            p['catalogue'][0]['fields']['caption']='flying bicycle'
            s['required'].clear()
            r=raw();r['memberships'][0]['evidence_quote']='flying bicycle'
            return r
        r=propose_category(OBJ,idx,infer,model_provenance=MODEL)
        self.assertEqual(r['status'],'error');self.assertEqual(idx,before)

    def test_response_and_model_aliasing(self):
        response=raw();model=copy.deepcopy(MODEL)
        r=propose_category(OBJ,index(),lambda *a:response,model_provenance=model)
        response['memberships'][0]['item_id']=999;model['model_id']='changed'
        self.assertEqual(r['proposal']['memberships'][0]['item_id'],11)
        self.assertEqual(r['provenance']['model_id'],'fixture-only')

    def test_revalidation(self):
        r=self.produce();proposal,provenance=validate_current_source(r,OBJ,index())
        self.assertEqual(proposal,r['proposal']);self.assertEqual(provenance,r['provenance'])

    def test_stale_metadata_same_source_digest(self):
        r=self.produce();idx=index();idx['items'][11]['fields']['caption']='Changed'
        with self.assertRaises(ValueError):validate_current_source(r,OBJ,idx)

    def test_stale_source_digest(self):
        r=self.produce();idx=index();idx['sha256']='b'*64
        with self.assertRaises(ValueError):validate_current_source(r,OBJ,idx)

    def test_stale_objective(self):
        with self.assertRaises(ValueError):validate_current_source(self.produce(),'different',index())

    def test_stale_inventory(self):
        with self.assertRaises(ValueError):validate_current_source(self.produce(),OBJ,index(),[{'category_id':'c','label':'City','member_ids':[11]}])

    def test_invalid_source(self):
        idx=index();idx['items'][True]={'fields':{}}
        with self.assertRaises(ValueError):self.produce(idx=idx)

    def test_owner_label_and_definition_bounds(self):
        for key, value in (('label', 'x'*81), ('definition', 'x'*1001), ('label', 'bad\nlabel')):
            r=raw();r[key]=value
            self.assertEqual(self.produce(r)['status'],'error')

    def test_unhashable_verdict(self):
        r=raw();r['memberships'][0]['verdict']={'match':True}
        self.assertEqual(self.produce(r)['status'],'error')

    def test_negative_item_ids(self):
        idx=index();idx['items'][-1]={'fields':{}}
        with self.assertRaises(ValueError):self.produce(idx=idx)

    def test_response_budget(self):
        r=raw();r['rationale']='x'*1000001
        self.assertEqual(self.produce(r)['status'],'error')

    def test_unknown_with_real_field_quote(self):
        r=raw();r['memberships'][2]['verdict']='unknown'
        out=self.produce(r)
        self.assertEqual(out['status'],'review');self.assertEqual(out['unknown_ids'],[33,44])

    def test_unicode_byte_budget(self):
        idx=index();idx['items'][44]['fields']['caption']='景'*6000
        r=self.produce(idx=idx,max_bytes=10000)
        self.assertEqual(r['status'],'blocked')

    def test_inventory_ids_must_be_within_candidate_pool(self):
        for ids in ([11,22,999],[-1],[True],[11,11]):
            cats=[{'category_id':'old','label':'Old travel','member_ids':ids}]
            with self.assertRaisesRegex(ValueError,'supplied candidate IDs'):
                self.produce(existing_categories=cats)

    def test_surrogate_source_is_deliberate_validation_error_before_inference(self):
        idx=index();idx['items'][11]['fields']['caption']='\ud800'
        calls=[]
        with self.assertRaisesRegex(ValueError,'UTF-8'):
            propose_category(OBJ,idx,lambda *args:calls.append(args),model_provenance=MODEL)
        self.assertEqual(calls,[])

    def test_surrogate_objective_is_deliberate_validation_error(self):
        with self.assertRaisesRegex(ValueError,'UTF-8'):
            propose_category('\ud800',index(),lambda *args:raw(),model_provenance=MODEL)

    def test_surrogate_model_output_fails_closed(self):
        r=raw();r['definition']='\ud800'
        out=self.produce(r)
        self.assertEqual(out['status'],'error');self.assertIsNone(out['proposal'])

    def test_no_auto_approval_or_ranker(self):
        r=self.produce()
        self.assertNotIn('approved',r);self.assertNotIn('scores',r);self.assertNotIn('filter',r)

if __name__=='__main__': unittest.main()
