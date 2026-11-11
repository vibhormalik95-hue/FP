"""Authored offline contract fixtures, not semantic gold or live model evidence.

Direct in-process API functions and strict request models, no HTTP or scorer.
Run with verification/run_guarded.py to prohibit model, process and network use.
"""
from copy import deepcopy
import csv
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError
from feedctrl.api import create_app, Request
from feedctrl.category_induction_producer import _digest
from feedctrl.semantic_controls import TEXT_FIELDS
from feedctrl.semantic_review import InductionPreview, SemanticApply, SemanticHistory
from feedctrl.staged_routes import DefinitionResolution, DefinitionApproval
from feedctrl import staged_induction as staged

MODEL={'backend':'offline-authored','model_id':'fixture-only','model_revision':'not-live-evidence'}
OBJECTIVE='Find a preparation category, keeping missing substantive facts unknown.'
DEFINITION='Scenes explicitly describing bread preparation. Missing preparation facts stay unknown.'
ALTERNATIVES=['Serving prepared bread rather than preparing it.','Preparing any food rather than bread specifically.']

def endpoint(app,path):
    return next(r.endpoint for r in app.routes if getattr(r,'path',None)==path)


class CategoryResolutionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.source=Path(self.temp.name)/'authored.csv'
        with self.source.open('w',encoding='utf8',newline='') as handle:
            writer=csv.DictWriter(handle,fieldnames=['video_id',*TEXT_FIELDS]);writer.writeheader()
            for i in range(1,37):
                writer.writerow({'video_id':i,'caption':'Bread preparation' if i in (1,3) else 'Activity unspecified' if i==8 else 'Bicycle commuting'})
        self.build()

    def build(self):
        self.calls=[];self.raws=[];self.hook=None;self.mutate=None;self.member_mutate=None;self.factory_calls=0
        def factory():
            self.factory_calls+=1
            def infer(payload,schema):
                stage='definition' if 'evidence' in schema['required'] else 'evidence_audit' if 'assessments' in schema['required'] else 'membership'
                self.calls.append(stage)
                if self.hook:self.hook(stage)
                if stage=='definition':
                    raw={'status':'propose','label':'Bread preparation scenes','definition':DEFINITION,
                        'rationale':'Authored candidate rationale only.','alternatives':deepcopy(ALTERNATIVES),
                        'evidence':[{'item_id':1,'field':'caption','quote':'Bread preparation','reason':'Authored source quotation.'}]}
                    if self.mutate:self.mutate(raw)
                elif stage=='membership':
                    self.assertEqual(payload['reviewed_definition'],{'label':'Bread preparation scenes','definition':DEFINITION})
                    raw={'memberships':[{'item_id':r['item_id'],
                        'verdict':'match' if r['item_id'] in (1,3) else 'unknown' if r['item_id']==8 else 'not_match',
                        'field':'' if r['item_id']==8 else 'caption',
                        'evidence_quote':'' if r['item_id']==8 else r['fields']['caption'],
                        'reason':'Authored disposition.'} for r in payload['catalogue']]}
                    if self.member_mutate:self.member_mutate(raw)
                else:
                    self.assertNotIn('memberships',payload)
                    self.assertNotIn('decisions',payload)
                    raw={'assessments':[{'item_id':r['item_id'],'assessment':'supported' if r['item_id'] in (1,3,8) else 'contradicted',
                        'field':'caption','quote':r['fields']['caption'],'reason':'Authored blind assessment.'} for r in payload['catalogue']]}
                self.raws.append(deepcopy(raw));return raw
            return infer,deepcopy(MODEL)
        self.app=create_app(fixture=True,semantic_path=self.source,category_infer_factory=factory,
                            allow_local_models=False,allow_local_recommender=False)
        self.demo=self.app.state.demo;self.session=self.demo.create_session()
        self.state=self.demo.user_state(self.session,1)

    def call(self,path,body,session=None):
        return endpoint(self.app,'/api/'+path)(body,self.session if session is None else session)

    def preview(self):
        return self.call('semantic/definition/preview',InductionPreview(user_id=1,objective=OBJECTIVE,
            candidate_ids=list(range(1,9)),operation='exclude',strength='none'))

    def resolve(self,p,choice='review_primary',session=None,user=1):
        return self.call('semantic/definition/resolve',DefinitionResolution(user_id=user,
            plan_id=p['resolution_plan_id'],choice=choice),session)

    def classify(self,p,**kw):
        return self.call('semantic/definition/classify',DefinitionApproval(user_id=1,
            plan_id=p['definition_plan_id'],evidence_reviewed=True,**kw))

    def apply(self,p):
        return self.call('semantic/apply',SemanticApply(user_id=1,plan_id=p['plan_id']))

    def conflict(self,fn):
        with self.assertRaises(HTTPException) as caught:fn()
        self.assertEqual(caught.exception.status_code,409)

    def test_definition_prompt_preserves_existing_unknown_rule_without_changing_schema(self):
        for phrase in ['match needs affirmative evidence', 'for every substantive condition',
                       'not_match needs affirmative evidence that a condition is false',
                       'missing information remains unknown',
                       'Do not make absent evidence an exclusion condition',
                       'no_match means no supported category proposal, not negative item membership']:
            self.assertIn(phrase,staged.DEFINITION_PROMPT)
        self.assertEqual(staged.DEFINITION_SCHEMA['required'],
            ['status','label','definition','rationale','alternatives','evidence'])
        self.assertEqual(staged.DEFINITION_SCHEMA['properties']['status']['enum'],['propose','no_match','ambiguous'])
        p=self.preview()
        self.assertEqual(p['objective'],OBJECTIVE)
        self.assertEqual(p['audit']['prompt_sha256'],_digest(staged.DEFINITION_PROMPT))
        self.assertEqual(p['audit']['schema_sha256'],_digest(staged.DEFINITION_SCHEMA))
        self.assertEqual(self.calls,['definition'])

    def test_elapsed_ttl_rejects_unchanged_token_without_inference(self):
        p=self.preview();created=self.state['semantic_definition_pending']['created']
        with patch('feedctrl.staged_routes.time.monotonic',return_value=created+301):
            self.conflict(lambda:self.resolve(p))
        self.assertEqual(self.calls,['definition'])

    def test_display_retains_validated_primary_without_approval_or_extra_inference(self):
        p=self.preview();self.assertEqual(p['status'],'clarify');self.assertTrue(p['resolution_ready'])
        self.assertFalse(p['definition_ready']);self.assertFalse(p['applied']);self.assertIsNone(p['proposal'])
        self.assertEqual(p['clarification']['candidate']['definition'],DEFINITION)
        self.assertEqual(p['clarification']['alternatives'],ALTERNATIVES)
        self.assertEqual(p['clarification']['candidate']['rationale'],self.raws[0]['rationale'])
        self.assertEqual(p['model_calls'][0]['raw_response'],self.raws[0])
        self.assertEqual(p['audit']['response_sha256'],_digest(self.raws[0]))
        self.assertNotIn('definition_plan_id',p);self.assertNotIn('plan_id',p)
        self.conflict(lambda:self.classify({'definition_plan_id':p['resolution_plan_id']}))
        self.conflict(lambda:self.apply({'plan_id':p['resolution_plan_id']}))
        self.assertEqual(self.calls,['definition']);self.assertEqual(self.factory_calls,1)
        self.assertEqual(self.state['semantic_groups'],[]);self.assertEqual(self.state['semantic_history'],[])
        self.assertEqual(self.state['semantic_revision'],0)

    def test_resolution_preserves_original_and_is_separate_from_definition_approval(self):
        p=self.preview();original=deepcopy(self.state['semantic_definition_pending']['definition'])
        before=deepcopy(p);r=self.resolve(p)
        self.assertEqual(p,before);self.assertTrue(r['definition_ready']);self.assertFalse(r['applied'])
        self.assertNotEqual(r['definition_plan_id'],p['resolution_plan_id'])
        self.assertEqual(r['definition']['original_clarification'],original)
        self.assertEqual(original['status'],'clarify');self.assertIsNone(original['proposal'])
        staged.check_seal(original,'definition_revision')
        self.assertEqual(r['definition']['proposal'],p['clarification']['candidate'])
        self.assertEqual(r['definition']['operator_resolution']['choice'],'review_primary')
        for key in ('objective','audit','provenance','source_constraints'):
            self.assertEqual(r['definition'][key],p[key])
        self.assertEqual(r['model_calls'],p['model_calls'])
        self.assertEqual(self.calls,['definition']);self.assertEqual(self.factory_calls,1)
        for approval in [False,None,1,'true']:
            with self.subTest(approval=approval),self.assertRaises(ValidationError):
                DefinitionApproval(user_id=1,plan_id=r['definition_plan_id'],evidence_reviewed=approval)
        self.conflict(lambda:self.resolve(p));self.conflict(lambda:self.apply({'plan_id':r['definition_plan_id']}))
        self.assertEqual(self.calls,['definition'])

    def test_strict_resolution_input_cannot_post_candidate_status_or_arbitrary_choice(self):
        for extra in ({'choice':None},{'choice':True},{'choice':1},{'choice':'alternative_0'},
                      {'choice':'approve'},{'choice':''},{'choice':'review_primary','candidate':{}},
                      {'choice':'review_primary','status':'definition_review'},
                      {'choice':'review_primary','evidence_reviewed':True},{}):
            with self.subTest(extra=extra),self.assertRaises(ValidationError):
                DefinitionResolution(user_id=1,plan_id='test-token',**extra)

    def test_explicit_cancel_consumes_token_without_inference(self):
        p=self.preview();old=self.state['semantic_definition_pending'];r=self.resolve(p,'cancel')
        self.assertEqual(r['status'],'cancelled');self.assertTrue(old['used'])
        self.assertIsNone(self.state['semantic_definition_pending'])
        self.conflict(lambda:self.resolve(p));self.conflict(lambda:self.resolve(p,'cancel'))
        self.assertEqual(self.calls,['definition']);self.assertEqual(self.state['semantic_groups'],[])

    def test_invalid_primary_is_terminal_without_resolution_token(self):
        mutations=[lambda r:r.update(label=''),lambda r:r.update(label='Invisible\u200b'),
            lambda r:r.update(definition=''),lambda r:r.update(evidence=[]),
            lambda r:r['evidence'][0].update(quote='Invented quote'),
            lambda r:r['evidence'][0].update(item_id=999),lambda r:r['evidence'][0].update(item_id=True),
            lambda r:r['evidence'][0].update(field='missing'),lambda r:r['evidence'][0].update(extra='not allowed')]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                self.build();self.mutate=mutate;p=self.preview()
                self.assertEqual(p['status'],'error');self.assertFalse(p['definition_ready'])
                self.assertNotIn('resolution_plan_id',p);self.assertIsNone(self.state['semantic_definition_pending'])
                self.assertEqual(self.calls,['definition']);self.assertEqual(p['model_calls'][0]['raw_response'],self.raws[0])

    def test_no_match_and_ambiguous_without_valid_primary_stay_terminal(self):
        for status in ['no_match','ambiguous']:
            for alternatives in [[],ALTERNATIVES]:
                with self.subTest(status=status,alternatives=alternatives):
                    self.build();self.mutate=lambda r:r.update(status=status,evidence=[],alternatives=alternatives)
                    p=self.preview();self.assertFalse(p['definition_ready']);self.assertNotIn('resolution_plan_id',p)
                    self.assertIsNone(self.state['semantic_definition_pending']);self.assertEqual(self.calls,['definition'])

    def test_stale_tampered_cross_session_and_reset_tokens_rejected(self):
        for change in ['candidate','alternatives','raw','body','objective','source','inventory','eligible',
                       'expiry','revision','nonce','session','user','transplanted_session','reset','new_preview','history']:
            with self.subTest(change=change):
                self.build();p=self.preview();pending=self.state['semantic_definition_pending'];session=self.session;user=1
                if change=='candidate':pending['definition']['clarification']['candidate']['definition']='Altered'
                elif change=='alternatives':pending['definition']['clarification']['alternatives'].clear()
                elif change=='raw':pending['definition_model_calls'][0]['raw_response']['definition']='Altered'
                elif change=='body':pending['body']['operation']='boost'
                elif change=='objective':pending['body']['objective']='Changed request'
                elif change=='source':self.demo.topic_index['items'][1]['fields']['caption']='Altered'
                elif change=='inventory':self.demo.items[1]=['new-inventory']
                elif change=='eligible':self.demo.items.pop(36)
                elif change=='expiry':pending['created']-=301
                elif change=='revision':self.state['semantic_revision']+=1
                elif change=='nonce':self.state['semantic_preview_nonce']='new'
                elif change=='session':session=self.demo.create_session()
                elif change=='user':user=2
                elif change=='transplanted_session':
                    session=self.demo.create_session();self.demo.user_state(session,1).update(deepcopy(self.state))
                elif change=='reset':self.call('reset',Request(user_id=1))
                elif change=='new_preview':self.preview()
                elif change=='history':self.call('semantic/history/preview',SemanticHistory(user_id=1,action='clear'))
                before=deepcopy(self.state);calls=deepcopy(self.calls)
                self.conflict(lambda:self.resolve(p,session=session,user=user))
                self.assertEqual(self.calls,calls);self.assertEqual(self.state,before)

    def test_response_mutation_does_not_modify_server_held_candidate(self):
        p=self.preview();clean=deepcopy(p);p['clarification']['candidate']['definition']='Client rewrite'
        p['clarification']['alternatives'].clear();p['audit']['response_sha256']='wrong'
        r=self.resolve(p);self.assertEqual(r['definition']['proposal'],clean['clarification']['candidate'])
        self.assertEqual(r['definition']['original_clarification']['clarification']['alternatives'],ALTERNATIVES)

    def test_delayed_preview_cannot_restore_reset_or_superseded_clarification(self):
        for change in ['reset','history']:
            with self.subTest(change=change):
                self.build()
                def hook(stage):
                    if stage=='definition':
                        self.hook=None
                        if change=='reset':self.call('reset',Request(user_id=1))
                        else:self.call('semantic/history/preview',SemanticHistory(user_id=1,action='clear'))
                self.hook=hook;p=self.preview()
                self.assertEqual(p['status'],'error');self.assertNotIn('resolution_plan_id',p)
                if change=='reset':self.assertIsNone(self.state['semantic_definition_pending'])
                else:self.assertIsNone(self.state['semantic_definition_pending'])

    def test_full_authored_continuation_keeps_membership_audit_apply_and_undo_gates(self):
        p=self.preview();r=self.resolve(p);self.assertEqual(self.calls,['definition'])
        m=self.classify(r);self.assertTrue(m['ready']);self.assertTrue(m['definition_approved'])
        self.assertFalse(m['applied']);self.assertEqual(self.calls,['definition','membership','evidence_audit'])
        self.assertEqual(self.state['semantic_groups'],[]);self.assertEqual(m['groups'][0]['proposal']['item_ids'],[1,3])
        envelope=m['groups'][0]['proposal']['induction']['envelope']
        self.assertEqual(len(envelope['field_evidence']),8);self.assertIn(8,envelope['unknown_ids'])
        self.assertEqual(envelope['staged_definition']['original_clarification']['audit'],p['audit'])
        self.assertEqual(envelope['staged_definition']['proposal']['definition'],DEFINITION)
        self.conflict(lambda:self.classify(r));self.conflict(lambda:self.resolve(p))
        applied=self.apply(m);self.assertTrue(applied['applied']);self.assertEqual(applied['feed']['available_items'],34)
        self.conflict(lambda:self.apply(m))
        clear=self.call('semantic/history/preview',SemanticHistory(user_id=1,action='clear'))
        self.assertEqual(len(self.state['semantic_groups']),1);self.apply(clear)
        undo=self.call('semantic/history/preview',SemanticHistory(user_id=1,action='undo'))
        self.assertEqual(self.state['semantic_groups'],[])
        self.assertEqual(self.apply(undo)['groups'],applied['groups'])
        self.assertEqual(self.calls,['definition','membership','evidence_audit'])

    def test_resolved_definition_stale_or_mutated_before_classify_still_blocks_inference(self):
        for change in ['definition','original','source','reset','expiry']:
            with self.subTest(change=change):
                self.build();r=self.resolve(self.preview());pending=self.state['semantic_definition_pending']
                if change=='definition':pending['definition']['proposal']['definition']='Changed'
                elif change=='original':pending['definition']['original_clarification']['clarification']['alternatives']=[]
                elif change=='source':self.demo.topic_index['items'][1]['fields']['caption']='Changed'
                elif change=='reset':self.call('reset',Request(user_id=1))
                else:pending['created']-=301
                self.conflict(lambda:self.classify(r));self.assertEqual(self.calls,['definition'])

    def test_resolved_plan_consumed_before_inference_prevents_nested_replay(self):
        r=self.resolve(self.preview());seen=[]
        def hook(stage):
            if stage=='membership':
                self.conflict(lambda:self.classify(r));seen.append('blocked')
        self.hook=hook
        self.assertTrue(self.classify(r)['ready']);self.assertEqual(seen,['blocked'])
        self.assertEqual(self.calls,['definition','membership','evidence_audit'])

    def test_reset_during_membership_or_audit_cannot_create_apply_review(self):
        for interrupted in ['membership','evidence_audit']:
            with self.subTest(interrupted=interrupted):
                self.build();r=self.resolve(self.preview())
                def hook(stage):
                    if stage==interrupted:self.call('reset',Request(user_id=1))
                self.hook=hook;m=self.classify(r)
                self.assertFalse(m['ready']);self.assertEqual(m['status'],'error')
                self.assertIsNone(self.state['semantic_pending']);self.assertEqual(self.state['semantic_groups'],[])
                expected=['definition','membership']+(['evidence_audit'] if interrupted=='evidence_audit' else [])
                self.assertEqual(self.calls,expected)

    def test_duplicate_primary_cannot_enter_resolution(self):
        self.mutate=lambda r:r.update(label='category_1')
        p=self.preview();self.assertEqual(p['status'],'duplicate')
        self.assertNotIn('resolution_plan_id',p);self.assertIsNone(self.state['semantic_definition_pending'])
        self.assertEqual(self.calls,['definition'])

    def test_invalid_or_incomplete_membership_after_resolution_cannot_apply(self):
        for mutate in [lambda r:r['memberships'].pop(),lambda r:r['memberships'][0].update(item_id=999),
                       lambda r:r['memberships'][0].update(evidence_quote='Invented')]:
            with self.subTest(mutate=mutate):
                self.build();r=self.resolve(self.preview());self.member_mutate=mutate;m=self.classify(r)
                self.assertEqual(m['status'],'error');self.assertFalse(m['ready'])
                self.assertEqual(self.calls,['definition','membership']);self.assertEqual(self.state['semantic_groups'],[])


if __name__=='__main__':unittest.main(verbosity=2)
