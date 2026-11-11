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


class ResolutionTests(unittest.TestCase):
    setUp = ScenarioTests.setUp
    config = ScenarioTests.config
    setup_app = ScenarioTests.setup_app
    execute = ScenarioTests.execute
    """Authored protocol cases, not a model-quality test or endorsed category."""
    def runner(self,*args):
        code,raw=ScenarioTests.runner(self,*args)
        envelope_data=json.loads(raw)
        result=json.loads(envelope_data['result'])
        if 'definition' in result and self.variant in ('alternatives','invalid_primary','no_primary'):
            result['alternatives']=['Making new things from offcuts', 'Manual techniques without powered equipment']
            result['rationale']='Authored competing concepts; not semantic approval.'
            if self.variant=='invalid_primary':result['evidence'][0]['quote']='invented quotation'
            if self.variant=='no_primary':result.update(status='ambiguous',label='',definition='',evidence=[])
            envelope_data['result']=json.dumps(result)
        return code,json.dumps(envelope_data).encode()
    def test_explicit_resolution_then_distinct_evidence_apply_undo_reviews(self):
        self.variant='alternatives';seen=[]
        def review(label,context):
            seen.append((label,json.loads(json.dumps(context)),len(self.calls)))
            return 'review_primary' if label.startswith('choose unchanged') else True
        _,budget,bundle,report,_=self.execute('category',review)
        self.assertEqual(budget.attempted,3)
        self.assertEqual([v[2] for v in seen],[1,1,3,3])
        original=report['semantic_evidence']['definition_result']
        resolved=report['semantic_evidence']['resolution_result']
        self.assertEqual(seen[0][1]['actual_proposal'],original)
        self.assertEqual(len(original['clarification']['alternatives']),2)
        self.assertEqual(resolved['definition']['proposal'],original['clarification']['candidate'])
        self.assertEqual(resolved['definition']['original_clarification']['clarification'],original['clarification'])
        self.assertNotEqual(original['resolution_plan_id'],resolved['definition_plan_id'])
        self.assertEqual(report['operator_decisions'][0]['evidence_approved'],False)
        self.assertTrue(report['mechanics']['undo_applied'])
        for _,context,_ in seen:self.assertEqual(context['all_scoped_metadata'],bundle['rows'])
        for args in self.calls:self.assertNotIn('operator_only',args[1].decode())
    def test_cancel_is_zero_inference_consumes_resolution_and_never_classifies(self):
        self.variant='alternatives';_,budget,_,report,_=self.execute('category',lambda *_:'cancel')
        self.assertEqual(budget.attempted,1);self.assertEqual(len(self.calls),1)
        self.assertEqual(report['status'],'operator_cancelled_resolution_no_apply')
        self.assertEqual([s['path'] for s in report['steps']],['/api/semantic/definition/preview','/api/semantic/definition/resolve'])
        self.assertFalse(report['mechanics']['applied'])
    def test_primary_choice_does_not_approve_evidence(self):
        self.variant='alternatives';seen=[]
        def review(label,context):
            seen.append(label);return 'review_primary' if len(seen)==1 else False
        _,budget,_,report,_=self.execute('category',review)
        self.assertEqual(budget.attempted,1);self.assertEqual(len(seen),2)
        self.assertEqual(report['status'],'operator_declined_no_apply')
        self.assertFalse(report['mechanics']['applied'])
    def test_non_explicit_choice_fails_closed(self):
        for choice in (True,False,None,'APPROVE','',{'choice':'review_primary'}):
            with self.subTest(choice=choice):
                self.variant='alternatives';app,budget,bundle,report=self.setup_app('category')
                with self.assertRaisesRegex(ValueError,'Explicit review_primary or cancel'):
                    driver.run(app,'category',lambda *_:choice,report,bundle)
                self.assertEqual(budget.attempted,1)
                self.assertEqual(len(report['steps']),1)
                self.assertFalse(report['mechanics']['applied'])
    def test_invalid_or_absent_primary_remains_terminal(self):
        for variant in ('invalid_primary','no_primary'):
            with self.subTest(variant=variant):
                self.variant=variant;seen=[]
                _,budget,_,report,_=self.execute('category',lambda *args:seen.append(args))
                self.assertEqual(budget.attempted,1);self.assertEqual(seen,[])
                self.assertEqual(report['status'],'terminal_without_apply')
    def test_operator_context_mutation_cannot_rewrite_candidate(self):
        self.variant='alternatives'
        def review(label,context):
            if label.startswith('choose unchanged'):
                context['actual_proposal']['clarification']['candidate']['definition']='Operator rewrite must not be submitted'
                context['actual_proposal']['clarification']['alternatives'].clear()
                context['all_scoped_metadata'].clear()
                return 'review_primary'
            return False
        _,budget,bundle,report,_=self.execute('category',review)
        original=report['semantic_evidence']['definition_result']['clarification']
        resolved=report['semantic_evidence']['resolution_result']['definition']
        self.assertEqual(resolved['proposal'],original['candidate'])
        self.assertEqual(len(original['alternatives']),2);self.assertEqual(len(bundle['rows']),8)
        self.assertEqual(budget.attempted,1)
    def test_historical_payload_rejected_before_runner(self):
        self.variant='alternatives';app,budget,bundle,report=self.setup_app('category')
        historical=Path(driver.__file__).parent.parent/'hosted_validation/inputs/01-category-discovery/first-model-input.json'
        bundle['first']=json.loads(historical.read_text())
        driver.run(app,'category',lambda *_:True,report,bundle)
        self.assertEqual(len(self.calls),0);self.assertEqual(report['status'],'terminal_without_apply')
    def test_current_input_delta_is_only_system_prompt(self):
        from feedctrl.staged_induction import DEFINITION_PROMPT
        current=Path(driver.__file__).parent/'inputs';old=current.parent.parent/'hosted_validation/inputs'
        historic=json.loads((old/'01-category-discovery/first-model-input.json').read_text())
        now=json.loads((current/'01-category-discovery/first-model-input.json').read_text())
        self.assertNotEqual(now['payload']['system'],historic['payload']['system'])
        self.assertEqual(now['payload']['system'],DEFINITION_PROMPT)
        now['payload']['system']=historic['payload']['system'];self.assertEqual(now,historic)
        for name in ('app-preview.json','metadata.csv','metadata.json','app-data.json','existing-inventory.json'):
            self.assertEqual((current/'01-category-discovery'/name).read_bytes(),(old/'01-category-discovery'/name).read_bytes())
    def test_operator_note_preserves_repair_retention_but_not_observed_carrying(self):
        current=Path(driver.__file__).parent/'inputs/01-category-discovery'
        rows=json.loads((current/'metadata.json').read_text())
        row=next(r for r in rows if r['item_id']==41002)
        self.assertEqual(row['fields']['caption'],
            'A torn canvas satchel is mended with a needle and spare thread so it can carry books again. The same bag is kept.')
        notes=(current/'REVIEW-NOTES.md').read_text(encoding='utf-8')
        fact_row=next(line for line in notes.splitlines() if line.startswith('| 41002 |'))
        self.assertIn('so it can carry books again; the same bag is kept.',fact_row)
        self.assertIn('Whether carrying books actually resumes',fact_row)
        self.assertNotIn('same bag carries books again',notes)
        self.assertIn('41002 does not establish that condition',notes)
        self.assertIn('missing fact must remain unknown, not match or not_match',notes)
        self.assertIn('not a prescribed category or gold membership set',notes)

    def test_templates_false_gated_and_pins_current(self):
        root=Path(driver.__file__).resolve().parents[2]
        for name in ('reviewed-config.TEMPLATE.json','reviewed-indirect-config.TEMPLATE.json'):
            c=json.loads((Path(driver.__file__).parent/name).read_text())
            self.assertTrue(all(c[g] is False for g in driver.GATES))
            self.assertIsNone(c['estimated_per_invocation_usd']);self.assertIsNone(c['executable'])
            self.assertEqual(c['driver_sha256'],driver.digest(driver.__file__))
            self.assertEqual(c['input_manifest_sha256'],driver.INPUT_MANIFEST_SHA256)
            with self.assertRaisesRegex(ValueError,'Six explicit reviewed assertions'):driver.validate(c,root)
            c['profile_id']='historical'
            with self.assertRaisesRegex(ValueError,'Current profile identifier'):driver.validate(c,root)


    def test_consumed_resolution_cannot_replay_for_either_choice(self):
        from feedctrl.staged_routes import DefinitionResolution
        for choice in ('cancel','review_primary'):
            with self.subTest(choice=choice):
                self.variant='alternatives';app,budget,bundle,report=self.setup_app('category')
                route=next(r for r in app.routes if getattr(r,'path',None)=='/api/session')
                session=route.endpoint()['session_id'];route.endpoint=lambda:{'session_id':session}
                def review(label,context):return choice if label.startswith('choose unchanged') else False
                driver.run(app,'category',review,report,bundle)
                token=report['semantic_evidence']['definition_result']['resolution_plan_id']
                resolve=next(r.endpoint for r in app.routes if getattr(r,'path',None)=='/api/semantic/definition/resolve')
                with self.assertRaises(HTTPException) as caught:
                    resolve(DefinitionResolution(user_id=bundle['body']['user_id'],plan_id=token,choice=choice),session)
                self.assertEqual(caught.exception.status_code,409);self.assertEqual(budget.attempted,1)
                self.assertFalse(report['mechanics']['applied'])
    def test_expired_operator_review_fails_without_retry_or_membership(self):
        import time
        self.variant='alternatives';app,budget,bundle,report=self.setup_app('category')
        patches=[]
        def review(label,context):
            p=patch('feedctrl.staged_routes.time.monotonic',return_value=time.monotonic()+301)
            patches.append(p);p.start();return 'review_primary'
        try:
            with self.assertRaises(HTTPException) as caught:driver.run(app,'category',review,report,bundle)
            self.assertEqual(caught.exception.status_code,409)
        finally:
            for p in patches:p.stop()
        self.assertEqual(budget.attempted,1);self.assertEqual(len(self.calls),1)
        self.assertEqual(report['steps'][-1]['http_status'],409)
        self.assertFalse(report['mechanics']['applied'])

if __name__=='__main__':unittest.main(verbosity=2)
