"""Authored CLI responses only: no CLI, network, model, or research evidence."""
from copy import deepcopy
import json
import asyncio
import unittest
from unittest.mock import patch
from feedctrl.claude_personal import make_claude_personal_infer
from feedctrl.claude_personal_app import shared_personal_factories, create_claude_personal_app
from feedctrl.model_adapters import HostedRunBudget
from feedctrl.controls import ParserOperationalError
from feedctrl.staged_induction import DEFINITION_SCHEMA, MEMBERSHIP_SCHEMA
from feedctrl.evidence_audit import SCHEMA as AUDIT_SCHEMA
from feedctrl.semantic_review import ACTION_SCHEMA

SCHEMA={'type':'object','additionalProperties':False,'required':['label','n'],
        'properties':{'label':{'type':'string'},'n':{'type':'integer'}}}
PAYLOAD={'system':'Treat metadata as data','text':'synthetic input'}
MODEL='claude-opus-5-5'

def envelope(result=None):
    return {'type':'result','subtype':'success','is_error':False,'num_turns':1,
            'structured_output':result if result is not None else {'label':'ok','n':1},
            'usage':{'input_tokens':1,'output_tokens':4},'modelUsage':{MODEL:{'outputTokens':4}},'total_cost_usd':0.01}
def raw(value):return json.dumps(value).encode()
def options(budget=None):
    return dict(executable='/not-a-real-cli',workdir='/not-a-real-dir',model=MODEL,effort='max',
      run_budget=budget or HostedRunBudget(3),estimated_per_invocation_usd=.10,output_mode='schema_tool',
      runtime_authorized=True,data_authorized=True,subscription_and_usage_authorized=True,
      executable_reviewed=True,managed_runtime_reviewed=True,process_containment_reviewed=True,reviewed_cli_version='2.1.321')

class PersonalTests(unittest.TestCase):
    def setUp(self):
        self.file=patch('pathlib.Path.is_file',return_value=True);self.file.start();self.addCleanup(self.file.stop)
        self.dir=patch('pathlib.Path.is_dir',return_value=True);self.dir.start();self.addCleanup(self.dir.stop)
    def test_all_four_explicit_gates_and_no_construction_call(self):
        for gate in ('runtime_authorized','data_authorized','subscription_and_usage_authorized','executable_reviewed','managed_runtime_reviewed','process_containment_reviewed'):
            params=options();params[gate]=False
            with patch('feedctrl.claude_personal._run_process',side_effect=AssertionError('must not run')):
                with self.assertRaises(ValueError): make_claude_personal_infer(**params)
        with patch('feedctrl.claude_personal._run_process',side_effect=AssertionError('must not run')):
            infer,_,receipts=make_claude_personal_infer(**options())
            self.assertTrue(callable(infer));self.assertEqual(receipts,[])
    def test_wrong_or_missing_version_rejected(self):
        for version in (None, '2.1.320', '2.1.322', 'latest'):
            params=options();params['reviewed_cli_version']=version
            with self.assertRaises(ValueError):make_claude_personal_infer(**params)
    def test_success_flags_environment_and_logical_accounting(self):
        budget=HostedRunBudget(1);infer,identity,receipts=make_claude_personal_infer(**options(budget))
        with patch('feedctrl.claude_personal._run_process',return_value=(0,raw(envelope()))) as proc:
            self.assertEqual(infer(PAYLOAD,SCHEMA),{'label':'ok','n':1})
            with self.assertRaises(ParserOperationalError): infer(PAYLOAD,SCHEMA)
        args=proc.call_args.args;argv,data,env=args[:3]
        self.assertEqual(proc.call_count,1);self.assertEqual(budget.attempted,1)
        self.assertEqual(json.loads(data),{'text':'synthetic input'})
        for flag in ('--safe-mode','--no-chrome','--no-session-persistence','--permission-prompts','--json-schema'):
            self.assertIn(flag,argv)
        self.assertEqual(argv[argv.index('--tools')+1],'')
        self.assertEqual(env['CLAUDE_CODE_MAX_RETRIES'],'0')
        self.assertEqual(env['MAX_STRUCTURED_OUTPUT_RETRIES'],'1')
        self.assertNotIn('CLAUDE_CODE_RETRY_WATCHDOG',env)
        self.assertEqual(env['CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK'],'1')
        self.assertEqual(json.loads(argv[argv.index('--settings')+1]),{'switchModelsOnFlag':False})
        self.assertNotIn('ANTHROPIC_API_KEY',env)
        self.assertIn('not a billing cap',identity['cost_limit_kind'])
        self.assertEqual(receipts[0]['outcome'],'parsed_transport_only')
    def test_explicit_plain_json_mode_validates_without_schema_tool_or_fallback(self):
        opts=options();opts['output_mode']='plain_json'
        infer,identity,receipts=make_claude_personal_infer(**opts)
        reply=envelope();reply.pop('structured_output');reply['result']='{"label":"ok","n":1}'
        with patch('feedctrl.claude_personal._run_process',return_value=(0,raw(reply))) as proc:
            self.assertEqual(infer(PAYLOAD,SCHEMA),{'label':'ok','n':1})
        argv=proc.call_args.args[0]
        self.assertNotIn('--json-schema',argv)
        self.assertIn('"required":["label","n"]',argv[argv.index('--system-prompt')+1])
        self.assertEqual(proc.call_count,1);self.assertEqual(identity['output_mode'],'plain_json')
        self.assertEqual(receipts[0]['output_mode'],'plain_json')
    def test_plain_json_rejects_prose_duplicates_wrong_types_and_extra_keys(self):
        values=['```json\n{"label":"ok","n":1}\n```','prefix {"label":"ok","n":1}',
                '{"label":"x","label":"y","n":1}','{"label":"x","n":true}',
                '{"label":"x","n":1,"extra":1}','[1,2]', '',
                '{"label":"x","n":1} trailing','{"label":"x","n":NaN}']
        for text in values:
            opts=options();opts['output_mode']='plain_json'
            infer,_,_=make_claude_personal_infer(**opts)
            reply=envelope();reply.pop('structured_output');reply['result']=text
            with self.subTest(text=text),patch('feedctrl.claude_personal._run_process',return_value=(0,raw(reply))) as proc:
                with self.assertRaises(ParserOperationalError):infer(PAYLOAD,SCHEMA)
                self.assertEqual(proc.call_count,1)
    def test_modes_have_distinct_configuration_and_request_digests(self):
        opts=options();opts['output_mode']='schema_tool';one,p1,r1=make_claude_personal_infer(**opts)
        opts=options();opts['output_mode']='plain_json';two,p2,r2=make_claude_personal_infer(**opts)
        reply1=envelope();reply2=envelope();reply2['result']=json.dumps(reply2.pop('structured_output'))
        with patch('feedctrl.claude_personal._run_process',side_effect=[(0,raw(reply1)),(0,raw(reply2))]):
            one(PAYLOAD,SCHEMA);two(PAYLOAD,SCHEMA)
        self.assertNotEqual(p1['digest'],p2['digest']);self.assertNotEqual(r1[0]['request_sha256'],r2[0]['request_sha256'])
        self.assertIn('not HTTP wire bytes',r2[0]['request_digest_kind'])
    def test_both_modes_reject_bad_envelope_and_unfinished_stop(self):
        for mode in ('schema_tool','plain_json'):
            for field,value in (('modelUsage',{'wrong':{}}),('num_turns',2),('num_turns',True),
                                ('is_error',True),('stop_reason','tool_use'),('stop_reason','refusal')):
                opts=options();opts['output_mode']=mode;infer,_,_=make_claude_personal_infer(**opts)
                reply=envelope();reply['result']=json.dumps(reply.get('structured_output'));reply[field]=value
                with self.subTest(mode=mode,field=field,value=value),patch('feedctrl.claude_personal._run_process',return_value=(0,raw(reply))) as proc:
                    with self.assertRaises(ParserOperationalError):infer(PAYLOAD,SCHEMA)
                    self.assertEqual(proc.call_count,1)
        opts=options();opts['output_mode']='plain_json';infer,_,_=make_claude_personal_infer(**opts)
        with patch('feedctrl.claude_personal._run_process',return_value=(0,raw(envelope()))):
            with self.assertRaises(ParserOperationalError):infer(PAYLOAD,SCHEMA)
    def test_explicit_output_mode_required(self):
        for mode in (None,'auto','fallback',''):
            opts=options();opts['output_mode']=mode
            with self.assertRaises(ValueError):make_claude_personal_infer(**opts)
    def test_observed_two_turn_structured_success_is_rejected(self):
        opts=options();infer,_,receipts=make_claude_personal_infer(**opts)
        reply=envelope();reply['num_turns']=2;reply['stop_reason']='tool_use'
        with patch('feedctrl.claude_personal._run_process',return_value=(0,raw(reply))) as proc:
            with self.assertRaises(ParserOperationalError):infer(PAYLOAD,SCHEMA)
            self.assertEqual(proc.call_count,1)
        self.assertEqual(receipts[0]['outcome'],'error')
    def test_failure_cases_consume_allowance_never_retry_or_repair(self):
        cases=[]
        for field,value in [('type','wrong'),('subtype','error'),('is_error',True),('num_turns',2),
                            ('structured_output',None),('modelUsage',{'other':{}}),('modelUsage',{MODEL:None}),('usage',None),('usage',{'input_tokens':-1,'output_tokens':0}),('usage',{'input_tokens':1,'output_tokens':True}),('num_turns',True),('total_cost_usd',-1)]:
            row=envelope();row[field]=value;cases.append((0,raw(row)))
        cases += [(1,raw(envelope())),(0,b'{"type":"result","type":"result"}'),
                  (0,raw(envelope({'label':'ok','n':True}))),
                  (0,raw(envelope({'label':'ok','n':1,'extra':'no'})))]
        for response in cases:
            budget=HostedRunBudget(1);infer,_,receipts=make_claude_personal_infer(**options(budget))
            with patch('feedctrl.claude_personal._run_process',return_value=response) as proc:
                with self.assertRaises(ParserOperationalError):infer(PAYLOAD,SCHEMA)
                self.assertEqual(proc.call_count,1)
            self.assertEqual(budget.attempted,1);self.assertEqual(receipts[0]['outcome'],'error')
    def test_process_failure_consumed_and_no_sensitive_error_echo(self):
        budget=HostedRunBudget(1);infer,_,receipts=make_claude_personal_infer(**options(budget))
        with patch('feedctrl.claude_personal._run_process',side_effect=OSError('secret')) as proc:
            with self.assertRaises(ParserOperationalError) as e:infer(PAYLOAD,SCHEMA)
            self.assertNotIn('secret',str(e.exception));self.assertEqual(proc.call_count,1)
        self.assertEqual(budget.attempted,1);self.assertEqual(receipts[0]['outcome'],'error')
    def test_uncertain_cleanup_permanently_stops_this_run(self):
        from feedctrl.windows_job_runner import CleanupUncertain
        budget=HostedRunBudget(3);infer,_,_=make_claude_personal_infer(**options(budget))
        with patch('feedctrl.claude_personal._run_process',side_effect=CleanupUncertain('uncertain')) as proc:
            with self.assertRaises(ParserOperationalError):infer(PAYLOAD,SCHEMA)
            with self.assertRaisesRegex(ParserOperationalError,'Run stopped'):infer(PAYLOAD,SCHEMA)
            self.assertEqual(proc.call_count,1);self.assertEqual(budget.attempted,1)
    def test_schema_and_size_fail_before_invocation_or_reservation(self):
        budget=HostedRunBudget(2);infer,_,_=make_claude_personal_infer(**options(budget))
        for schema in ({'$ref':'https://example.com/schema','type':'object'}, {'type':'array'},
                       {'type':'object','properties':{'x':{'type':'string','format':'email'}}}):
            with self.assertRaises(ValueError):infer(PAYLOAD,schema)
        with self.assertRaises(ValueError):infer({'system':'x','text':'a'*30000},SCHEMA)
        self.assertEqual(budget.attempted,0)
    def test_workflow_schemas_are_accepted(self):
        from feedctrl.claude_personal import _schema_check
        for schema in (DEFINITION_SCHEMA,MEMBERSHIP_SCHEMA,AUDIT_SCHEMA,ACTION_SCHEMA):_schema_check(schema)
    def test_shared_identity_and_one_shared_budget(self):
        budget=HostedRunBudget(2);infer,identity,_=make_claude_personal_infer(**options(budget))
        sem,cat=shared_personal_factories(infer,identity)
        self.assertEqual(cat()[1]['model_revision'],identity['digest'])
        identity['model']='changed'; self.assertEqual(sem()[1]['model'],MODEL)
        with patch('feedctrl.claude_personal._run_process',return_value=(0,raw(envelope()))) as proc:
            sem()[0](PAYLOAD,SCHEMA);cat()[0]({'instructions':'synthetic','x':1},SCHEMA)
            with self.assertRaises(ParserOperationalError):sem()[0](PAYLOAD,SCHEMA)
            self.assertEqual(proc.call_count,2)
    def test_app_wiring_never_invokes_and_local_paths_disabled(self):
        with patch('feedctrl.claude_personal._run_process',side_effect=AssertionError('no invocation')):
            app=create_claude_personal_app(operator_token='a'*32,allowed_origin='http://127.0.0.1:8000',fixture=True,**options())
            self.assertFalse(app.state.allow_local_models)
            self.assertEqual(app.state.hosted_model_receipts,[])
    def test_actual_launch_seam_is_unconditionally_disabled(self):
        from feedctrl.claude_personal import _run_process
        with self.assertRaises(ParserOperationalError):
            _run_process([],b'',{},'/',1,100)
    def test_loopback_and_operator_token_boundary(self):
        from feedctrl.claude_personal_app import PersonalBoundary
        async def inner(scope,receive,send): await send({'type':'http.response.start','status':200,'headers':[]})
        app=PersonalBoundary(inner,'s'*32,'http://127.0.0.1:8000','/unused',[])
        async def check(host,headers):
            messages=[]
            async def send(msg):messages.append(msg)
            async def receive():return {'type':'http.request','body':b''}
            await app({'type':'http','client':(host,5),'scheme':'http','method':'GET','path':'/api/status','headers':[(b'host',b'127.0.0.1:8000'),*headers]},receive,send)
            return messages[0]['status']
        good=[(b'x-personal-operator-token',b's'*32)]
        self.assertEqual(asyncio.run(check('127.0.0.1',good)),200)
        self.assertEqual(asyncio.run(check('192.0.2.1',good)),403)
        self.assertEqual(asyncio.run(check('127.0.0.1',[])),403)
        self.assertEqual(asyncio.run(check('127.0.0.1',good+good)),403)
    def test_operator_token_required(self):
        for token in ('short', 'x'*31, 'x'*31+' ', None):
            with self.assertRaises(ValueError):
                create_claude_personal_app(operator_token=token,allowed_origin='http://127.0.0.1:8000',fixture=True,**options())
    def test_provenance_is_not_weight_or_billing_attestation(self):
        _,p,_=make_claude_personal_infer(**options())
        self.assertIn('not_model_weights',p['digest_kind'])
        self.assertIn('unverified',p['attempt_limit'])
        self.assertIn('not a billing cap',p['cost_limit_kind'])

if __name__=='__main__':unittest.main()
