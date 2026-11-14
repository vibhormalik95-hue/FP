"""Authored display/custody mechanics, not semantic accuracy or live acceptance."""
import ast
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from feedctrl import staged_induction as staged
import test_category_resolution_offline as fixtures


class DefinitionContextTests(unittest.TestCase):
    setUp=fixtures.CategoryResolutionTests.setUp
    build=fixtures.CategoryResolutionTests.build
    call=fixtures.CategoryResolutionTests.call
    preview=fixtures.CategoryResolutionTests.preview
    resolve=fixtures.CategoryResolutionTests.resolve
    classify=fixtures.CategoryResolutionTests.classify
    conflict=fixtures.CategoryResolutionTests.conflict

    def authored_sources(self, ordinary=False, *, repeats=150):
        texts={1:'No glue or powered equipment is used.\n"Bread preparation" is quoted, not asserted. 🧭 cafe\u0301 <script>alert(1)</script> & '+('distant context ' * repeats)+'Only an example.',
               3:'Bread preparation is described only with supervision.\nSeparate item, same field.'}
        for item,text in texts.items():self.demo.topic_index['items'][item]['fields']['caption']=text
        # An uncited field and an out-of-scope item must never appear in context.
        self.demo.topic_index['items'][1]['fields']['title']='Uncited title sentinel'
        self.demo.topic_index['items'][9]['fields']['caption']='Out of scope sentinel'
        def change(raw):
            raw['evidence'].append({'item_id':3,'field':'caption','quote':'Bread preparation','reason':'Authored second quote.'})
            if ordinary:raw['alternatives']=[]
        self.mutate=change
        return texts

    def assert_context(self,response,texts):
        rows=response['evidence_context']
        self.assertEqual([r['item_id'] for r in rows],[1,3])
        for row in rows:
            self.assertEqual(row['field'],'caption')
            self.assertEqual(row['quote'],'Bread preparation')
            self.assertEqual(row['supplied_field_text'],texts[row['item_id']])
            self.assertTrue(row['quote_present']);self.assertFalse(row['truncated'])
        self.assertNotIn('Uncited title sentinel',repr(rows))
        self.assertNotIn('Out of scope sentinel',repr(rows))

    def test_clarification_and_resolved_primary_keep_exact_complete_fields(self):
        texts=self.authored_sources();p=self.preview();self.assert_context(p,texts)
        stored=deepcopy(self.state['semantic_definition_pending']['definition'])
        self.assertNotIn('evidence_context',stored)
        r=self.resolve(p);self.assert_context(r,texts)
        self.assertEqual(r['definition']['original_clarification'],stored)
        self.assertEqual(self.calls,['definition'])
        self.assertFalse(r['applied']);self.assertEqual(self.state['semantic_groups'],[])

    def test_ordinary_preview_returns_same_read_only_context(self):
        texts=self.authored_sources(ordinary=True);p=self.preview()
        self.assertTrue(p['definition_ready']);self.assert_context(p,texts)
        self.assertNotIn('evidence_context',p['definition'])
        self.assertEqual(self.calls,['definition']);self.assertFalse(p['applied'])

    def test_long_context_within_budget_is_returned_in_full(self):
        texts=self.authored_sources(ordinary=True);sizes=[];original=staged._budget
        def measure(payload):
            sizes.append(len(json.dumps(payload,ensure_ascii=False,allow_nan=False).encode('utf-8')))
            return original(payload)
        with patch.object(staged,'_budget',side_effect=measure):p=self.preview()
        self.assertTrue(p['definition_ready']);self.assertEqual(len(sizes),1)
        self.assertLessEqual(sizes[0],7000);self.assertGreater(len(texts[1].encode('utf-8')),2000)
        self.assert_context(p,texts);self.assertTrue(p['evidence_context'][0]['supplied_field_text'].endswith('Only an example.'))
        self.assertEqual(self.calls,['definition']);self.assertFalse(p['applied'])

    def test_over_budget_context_is_rejected_before_inference(self):
        self.authored_sources(ordinary=True,repeats=200);sizes=[];original=staged._budget
        def measure(payload):
            sizes.append(len(json.dumps(payload,ensure_ascii=False,allow_nan=False).encode('utf-8')))
            return original(payload)
        with patch.object(staged,'_budget',side_effect=measure):p=self.preview()
        self.assertEqual(len(sizes),1);self.assertGreater(sizes[0],7000)
        self.assertEqual(p['status'],'error');self.assertEqual(p['reason'],'Evidence budget exceeded; narrow the declared scope')
        self.assertFalse(p['definition_ready']);self.assertFalse(p['applied']);self.assertEqual(self.calls,[])
        self.assertIsNone(self.state['semantic_definition_pending']);self.assertEqual(self.state['semantic_groups'],[])

    def test_context_is_not_an_approval_or_persistent_mutable_source(self):
        texts=self.authored_sources();p=self.preview()
        p['evidence_context'][0]['supplied_field_text']='Forged display'
        r=self.resolve(p);self.assert_context(r,texts)
        self.assertEqual(self.demo.topic_index['items'][1]['fields']['caption'],texts[1])

    def test_changed_source_rejects_resolve_and_ordinary_classification(self):
        for ordinary in (False,True):
            with self.subTest(ordinary=ordinary):
                self.build();self.authored_sources(ordinary);p=self.preview()
                self.demo.topic_index['items'][1]['fields']['caption']+=' New qualifier.'
                self.conflict(lambda:self.classify(p) if ordinary else self.resolve(p))
                self.assertEqual(self.calls,['definition'])

    def test_other_user_and_session_cannot_retrieve_resolution_context(self):
        self.authored_sources();p=self.preview()
        self.conflict(lambda:self.resolve(p,user=2))
        self.conflict(lambda:self.resolve(p,session=self.demo.create_session()))
        self.assertEqual(self.calls,['definition'])

    def test_source_mutation_during_preview_returns_no_context(self):
        self.authored_sources()
        def change(stage):
            if stage=='definition':self.demo.topic_index['items'][1]['fields']['caption']+=' changed in flight'
        self.hook=change;p=self.preview()
        self.assertFalse(p['definition_ready']);self.assertNotIn('evidence_context',p)
        self.assertIsNone(self.state['semantic_definition_pending'])

    def test_missing_context_uses_only_explicit_scope_without_cross_item_fallback(self):
        path=Path(__file__).resolve().parents[1]/'feedctrl/semantic_review.py'
        tree=ast.parse(path.read_text())
        install=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='install_semantic_routes')
        fn=next(n for n in install.body if isinstance(n,ast.FunctionDef) and n.name=='evidence_context')
        namespace={'demo':SimpleNamespace(topic_index={'items':{2:{'fields':{'caption':'outside scope'}}}})}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),str(path),'exec'),namespace)
        scope={'items':{1:{'fields':{'caption':'item one'}},3:{'fields':{'caption':None}}}}
        proposal={'evidence':[{'item_id':i,'field':field,'quote':'item'} for i,field in [(1,'caption'),(2,'caption'),(3,'caption'),(1,'title')]]}
        before=deepcopy((proposal,scope));rows=namespace['evidence_context'](proposal,scope)
        self.assertEqual([r['supplied_field_text'] for r in rows],['item one',None,None,None])
        self.assertEqual([r['quote_present'] for r in rows],[True,False,False,False])
        self.assertEqual((proposal,scope),before)
        self.assertIsNone(namespace['evidence_context'](proposal,{'items':{}})[0]['supplied_field_text'])
