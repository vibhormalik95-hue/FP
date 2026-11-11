"""Authored callable fixtures prove wiring/provenance, not model accuracy.

The lamp's purpose/capability does not prove actual illumination. Retention is
explicit, so a retention OR use condition differs from an actual-use condition.
No semantic classifier is implemented or tested by these authored replies.
"""
from copy import deepcopy
import unittest
from unittest.mock import patch
from pydantic import ValidationError
from feedctrl import staged_induction as staged
from feedctrl.staged_routes import DefinitionApproval
import test_category_resolution_offline as fixture

AMENDMENT = "Preserve the source's modality and tense in every rationale and evidence reason. A stated purpose, intention, possibility or capability does not establish that an action or outcome actually occurred. Explain only what the quotation establishes, using the exact definition's conditions and alternatives; do not claim an additional condition or outcome merely because it would be plausible."
QUOTE = 'A lamp was repaired so it can illuminate a desk. The same lamp is retained.'
REASON = 'The quotation proves the lamp was repaired and actually illuminated the desk.'

class ModalityTests(unittest.TestCase):
    setUp = fixture.CategoryResolutionTests.setUp
    build = fixture.CategoryResolutionTests.build
    call = fixture.CategoryResolutionTests.call
    preview = fixture.CategoryResolutionTests.preview
    resolve = fixture.CategoryResolutionTests.resolve

    def test_real_definition_payload_contains_only_generic_amendment(self):
        captures=[]
        original=staged._budget
        def capture(payload):
            captures.append(deepcopy(payload));return original(payload)
        with patch.object(staged,'_budget',side_effect=capture):
            self.preview()
        self.assertEqual(len(captures),1)
        prompt=captures[0]['instructions']
        self.assertEqual(prompt,staged.DEFINITION_PROMPT)
        self.assertEqual(prompt.count(AMENDMENT),1)
        self.assertIn('WHOLE definition.\n'+AMENDMENT+'\nNever infer',prompt)
        self.assertEqual(captures[0]['objective'],fixture.OBJECTIVE)
        for forbidden in (QUOTE,REASON,'lamp','satchel','41002','Repaired and kept in use','Bread preparation scenes','target set'):
            self.assertNotIn(forbidden,prompt)
        self.assertEqual(self.calls,['definition'])

    def test_overstated_reason_is_not_repaired_or_automatically_approved(self):
        for definition in ('Objects repaired and actually used afterward.',
                           'Objects repaired and either retained or used afterward.'):
            with self.subTest(definition=definition):
                self.build()
                self.demo.topic_index['items'][1]['fields']['caption']=QUOTE
                def authored(raw):
                    raw.update(label='Authored lamp proposal',definition=definition,
                               rationale=REASON,alternatives=['Objects acquired without repair.'])
                    raw['evidence']=[{'item_id':1,'field':'caption','quote':QUOTE,'reason':REASON}]
                self.mutate=authored
                saved=fixture.endpoint(self.app,'/api/semantic/groups')
                before_feed=deepcopy(saved(1,self.session)['feed'])
                p=self.preview();r=self.resolve(p)
                candidate=p['clarification']['candidate']
                self.assertEqual(candidate['rationale'],REASON)
                self.assertEqual(candidate['evidence'][0]['reason'],REASON)
                self.assertEqual(r['definition']['proposal'],candidate)
                self.assertEqual(r['definition']['original_clarification']['clarification'],p['clarification'])
                self.assertEqual(r['model_calls'],p['model_calls'])
                self.assertEqual(p['model_calls'][0]['raw_response'],self.raws[0])
                # The authored reviewer declines; strict false cannot start classification.
                with self.assertRaises(ValidationError):
                    DefinitionApproval(user_id=1,plan_id=r['definition_plan_id'],evidence_reviewed=False)
                self.assertEqual(self.calls,['definition'])
                self.assertFalse(r['applied'])
                self.assertEqual(self.state['semantic_groups'],[])
                self.assertEqual(self.state['semantic_history'],[])
                self.assertEqual(self.state['semantic_revision'],0)
                self.assertEqual(saved(1,self.session)['feed'],before_feed)
