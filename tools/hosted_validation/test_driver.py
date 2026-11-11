"""Authored fake-runner outcomes only; no model/network/native execution."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import driver
from fastapi import HTTPException
from feedctrl.windows_job_runner import CleanupUncertain
from feedctrl.semantic_review import SemanticPreview
from test_claude_personal_offline import options,envelope

class ScenarioTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.exe=self.root/'fake.exe';self.exe.touch()
        self.calls=[];self.variant='valid';self.checkpoints=[]
    def config(self,scenario):
        c=options();c.pop('run_budget');c.update(driver.BOUNDS)
        c.update(model=driver.EXPECTED_MODEL,effort='max',scenario=scenario,executable=str(self.exe),
                 workdir=str(self.root),output_mode='plain_json',operator_token='authored-test-only-token-12345678901')
        return c
    def runner(self,*args):
        self.calls.append(args)
        if self.variant=='cleanup':raise CleanupUncertain('Authored uncertainty')
        argv,data=args[:2];payload=json.loads(data);system=argv[argv.index('--system-prompt')+1]
        if '"intent_span"' in system:
            result={'needs_clarification':self.variant=='clarify','question':'What should be removed?' if self.variant=='clarify' else '',
                    'control':'boost/light' if self.variant=='boost' else 'exclude/none',
                    'intent_span':'the stuff that makes me hungry'}
        elif '"negation_resolved"' in system:
            result={'status':'propose','reason':'Authored food interpretation, not factual appetite prediction.',
                    'negation_resolved':True,'alternatives':[],
                    'evidence':[{'item_id':r['item_id'],'field':'caption','quote':r['fields']['caption']}
                                for r in payload['catalogue'] if r['item_id'] in (81001,81003,81006)]}
            if self.variant=='bad_quote':result['evidence'][0]['quote']='Not in any supplied source'
        elif '"assessments"' in system:
            result={'assessments':[{'item_id':r['item_id'],'assessment':
                    'supported' if r['item_id'] in (41001,41002,41003) else
                    'not_stated' if r['item_id'] in (41007,41008) else 'contradicted',
                    'field':'caption','quote':r['fields']['caption'],'reason':'Authored fixture assessment'}
                    for r in payload['catalogue']]}
        elif '"memberships"' in system:
            result={'memberships':[{'item_id':r['item_id'],'verdict':
                    'unknown' if self.variant=='all_unknown' else 'match' if r['item_id'] in (41001,41002,41003) else
                    'unknown' if r['item_id'] in (41007,41008) else 'not_match',
                    'field':'caption','evidence_quote':r['fields']['caption'],'reason':'Authored fixture disposition'}
                    for r in payload['catalogue']]}
        else:
            row=payload['catalogue'][0]
            result={'status':'propose','label':'Restore damaged objects','definition':'Restoring a damaged existing object to use while keeping the same object.',
                    'rationale':'Authored example, not a preselected runtime meaning.','alternatives':[],
                    'evidence':[{'item_id':row['item_id'],'field':'caption','quote':row['fields']['caption'],'reason':'Authored fixture evidence'}]}
            if self.variant=='no_match':result.update(status='no_match',label='',definition='',evidence=[])
        value=envelope();value.pop('structured_output');value['result']=json.dumps(result)
        value['modelUsage']={('claude-opus-5-5' if self.variant=='wrong_model' else driver.EXPECTED_MODEL):{'outputTokens':4}}
        if self.variant=='private_extras':
            value['usage']['diagnostic']='private@example.invalid'
            value['modelUsage'][driver.EXPECTED_MODEL]['location']='C:/Users/private/secret'
        return 0,json.dumps(value).encode()
    def setup_app(self,scenario):
        bundle=driver.load_inputs(Path(driver.__file__).parent/'inputs',scenario)
        report=driver.new_report(scenario,bundle)
        def checkpoint():self.checkpoints.append(json.loads(json.dumps(report)))
        app,budget=driver.build(self.config(scenario),self.root,bundle,self.runner,report,checkpoint)
        return app,budget,bundle,report
    def execute(self,scenario,review=None):
        app,budget,bundle,report=self.setup_app(scenario)
        reviews=[]
        def approve(label,value):reviews.append(value);return True
        driver.run(app,scenario,review or approve,report,bundle)
        return app,budget,bundle,report,reviews
    def test_staged_category_exact_initial_input_dynamic_effect_and_unknowns(self):
        app,budget,bundle,report,reviews=self.execute('category')
        self.assertEqual(budget.attempted,3);self.assertEqual(len(self.calls),3)
        self.assertEqual(report['mechanics'],{'baseline_available':8,'applied':True,'undo_applied':True,
                 'selected_ids':[41001,41002,41003],'after_apply_available':5,'after_undo_available':8})
        self.assertEqual(report['semantic_evidence']['proposal_result']['induction']['unknown_ids'],[41007,41008])
        self.assertEqual(len(report['source_evidence']['all_scoped_metadata']),8)
        self.assertTrue(all(len(r['all_scoped_metadata'])==8 and 'Not established' in r['operator_only_facts_unknowns_and_review_notes'] for r in reviews))
        self.assertEqual(report['model_inputs'][0]['status'],'runner_returned')
        self.assertEqual(self.checkpoints[0]['model_inputs'][0]['status'],'prepared_before_runner')
        for call in self.calls:self.assertNotIn('reviewer-only illustrations',call[1].decode())
        self.assertFalse(app.state.allow_local_models)
    def test_hunger_preserves_exact_request_and_source_unknowns(self):
        _,budget,bundle,report,reviews=self.execute('indirect')
        self.assertEqual(budget.attempted,2)
        self.assertEqual(report['mechanics']['after_apply_available'],5)
        self.assertEqual(report['mechanics']['after_undo_available'],8)
        self.assertEqual(bundle['body']['text'],"I'm not hungry, remove all the stuff that makes me hungry.")
        self.assertNotIn('expected_target_ids',report['semantic_evidence'])
        self.assertIn('What remains unknown',reviews[0]['operator_only_facts_unknowns_and_review_notes'])
    def test_clarification_terminal_no_apply_no_retry(self):
        self.variant='clarify';_,budget,_,report,reviews=self.execute('indirect')
        self.assertEqual(budget.attempted,1);self.assertEqual(len(self.calls),1)
        self.assertEqual(report['semantic_evidence']['terminal_result']['status'],'clarify')
        self.assertFalse(report['mechanics']['applied']);self.assertEqual(reviews,[])
    def test_definition_abstention_terminal_no_classify(self):
        self.variant='no_match';_,budget,_,report,_=self.execute('category')
        self.assertEqual(budget.attempted,1);self.assertFalse(report['mechanics']['applied'])
        self.assertEqual(report['semantic_evidence']['terminal_result']['status'],'no_match')
    def test_bad_quote_preserved_rejection_no_apply(self):
        self.variant='bad_quote';_,budget,_,report,_=self.execute('indirect')
        self.assertEqual(budget.attempted,2);self.assertFalse(report['mechanics']['applied'])
        self.assertEqual(report['status'],'terminal_without_apply')
    def test_wrong_model_no_retry(self):
        self.variant='wrong_model';_,budget,_,report,_=self.execute('category')
        self.assertEqual((budget.attempted,len(self.calls)),(1,1))
        self.assertEqual(report['semantic_evidence']['terminal_result']['status'],'error')
    def test_boost_result_preserved_not_rewritten_or_applied(self):
        self.variant='boost';_,budget,_,report,_=self.execute('indirect')
        self.assertEqual(budget.attempted,2)
        self.assertEqual(report['status'],'unsupported_action_preserved_no_apply')
        self.assertEqual(report['semantic_evidence']['returned_action']['operation'],'boost')
    def test_declining_definition_stops_after_one_call(self):
        _,budget,_,report,_=self.execute('category',lambda *_:False)
        self.assertEqual(budget.attempted,1);self.assertEqual(report['status'],'operator_declined_no_apply')
    def test_shared_cleanup_latch_stops_other_factory(self):
        self.variant='cleanup';app,budget,bundle,report=self.setup_app('category')
        driver.run(app,'category',lambda *_:True,report,bundle)
        endpoint=lambda path:next(r.endpoint for r in app.routes if getattr(r,'path',None)==path)
        session=endpoint('/api/session')()['session_id']
        with self.assertRaises(HTTPException) as caught:
            endpoint('/api/semantic/preview')(SemanticPreview(user_id=1,label='Authored latch check',
                text='Remove irrelevant items',candidate_ids=bundle['body']['candidate_ids'],backend='configured_model',action_source='model'),session)
        self.assertEqual(caught.exception.status_code,502);self.assertEqual((budget.attempted,len(self.calls)),(1,1))
    def test_shared_budget_cannot_renew_between_routes(self):
        app,budget,bundle,report,_=self.execute('category')
        endpoint=lambda path:next(r.endpoint for r in app.routes if getattr(r,'path',None)==path)
        session=endpoint('/api/session')()['session_id']
        with self.assertRaises(HTTPException) as caught:
            endpoint('/api/semantic/preview')(SemanticPreview(user_id=1,label='Budget check',text='Remove irrelevant items',
            candidate_ids=bundle['body']['candidate_ids'],backend='configured_model',action_source='model'),session)
        self.assertEqual(caught.exception.status_code,502);self.assertEqual((budget.attempted,len(self.calls)),(3,3))
    def test_receipt_projection_drops_private_provider_extras(self):
        self.variant='private_extras';app,_,_,report,_=self.execute('indirect')
        report['receipts']=app.state.hosted_model_receipts
        text=json.dumps(driver.redact(report,self.config('indirect')))
        self.assertNotIn('private@example.invalid',text);self.assertNotIn('C:/Users/private/secret',text)
    def test_all_unknown_membership_stops_before_audit_and_apply(self):
        self.variant='all_unknown';_,budget,_,report,_=self.execute('category')
        self.assertEqual(budget.attempted,2);self.assertEqual(len(self.calls),2)
        self.assertFalse(report['mechanics']['applied'])
        self.assertEqual(report['semantic_evidence']['terminal_result']['status'],'clarify')
    def test_report_write_failure_cannot_mask_cleanup_latch(self):
        self.variant='cleanup';bundle=driver.load_inputs(Path(driver.__file__).parent/'inputs','category')
        report=driver.new_report('category',bundle);writes=[]
        def checkpoint():
            writes.append(1)
            if len(writes)>1:raise OSError('Authored report persistence failure')
        app,budget=driver.build(self.config('category'),self.root,bundle,self.runner,report,checkpoint)
        driver.run(app,'category',lambda *_:True,report,bundle)
        endpoint=lambda path:next(r.endpoint for r in app.routes if getattr(r,'path',None)==path)
        session=endpoint('/api/session')()['session_id']
        with self.assertRaises(HTTPException) as caught:
            endpoint('/api/semantic/preview')(SemanticPreview(user_id=1,label='Latch after report failure',
                text='Remove irrelevant items',candidate_ids=bundle['body']['candidate_ids'],backend='configured_model',action_source='model'),session)
        self.assertIn('uncertain process cleanup',caught.exception.detail)
        self.assertEqual((budget.attempted,len(self.calls)),(1,1))
    def test_input_drift_rejected_without_any_runner(self):
        import shutil
        source=Path(driver.__file__).parent/'inputs';copy=self.root/'inputs';shutil.copytree(source,copy)
        (copy/'02-hunger-continuation'/'app-preview.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'Input drift'):driver.load_inputs(copy,'indirect')
        self.assertEqual(self.calls,[])
    def test_indirect_operational_error_is_recorded_without_apply(self):
        self.variant='wrong_model';app,budget,bundle,report=self.setup_app('indirect')
        with self.assertRaises(HTTPException):driver.run(app,'indirect',lambda *_:True,report,bundle)
        self.assertEqual(report['steps'][-1]['http_status'],502)
        self.assertIn('operational_failure',report['semantic_evidence'])
        self.assertFalse(report['mechanics']['applied']);self.assertEqual((budget.attempted,len(self.calls)),(1,1))
    def test_first_input_mismatch_stops_before_runner(self):
        app,budget,bundle,report=self.setup_app('category');bundle['first']['payload']['objective']='Changed objective'
        driver.run(app,'category',lambda *_:True,report,bundle)
        self.assertEqual(len(self.calls),0);self.assertEqual(budget.attempted,1)
        self.assertEqual(report['semantic_evidence']['terminal_result']['status'],'error')

if __name__=='__main__':unittest.main(verbosity=2)
