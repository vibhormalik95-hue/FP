"""Authored envelopes only. Guards forbid process, network and native runner use."""
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from feedctrl.claude_personal import make_claude_personal_infer, _safe_cli_evidence
from feedctrl.controls import ParserOperationalError
from test_claude_personal_offline import options, envelope, raw, MODEL, PAYLOAD, SCHEMA

spec = importlib.util.spec_from_file_location('safe_evidence_driver', Path(__file__).resolve().parents[1]/'tools/hosted_validation/driver.py')
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)

class SafeEvidenceTests(unittest.TestCase):
    def setUp(self):
        for name in ('subprocess.Popen', 'os.system', 'socket.socket',
                     'feedctrl.claude_personal._run_process',
                     'feedctrl.windows_job_runner.run_windows_job'):
            p = patch(name, side_effect=AssertionError('Forbidden offline action'))
            p.start(); self.addCleanup(p.stop)
        for name in ('pathlib.Path.is_file', 'pathlib.Path.is_dir'):
            p = patch(name, return_value=True); p.start(); self.addCleanup(p.stop)

    def invoke(self, code, value, success=False):
        calls=[]
        def fake(*args):
            calls.append(1)
            return code, value
        infer, _, receipts = make_claude_personal_infer(**options(), process_runner=fake)
        if success:
            self.assertEqual(infer(PAYLOAD, SCHEMA), {'label':'ok','n':1})
        else:
            with self.assertRaises(ParserOperationalError) as cm:
                infer(PAYLOAD, SCHEMA)
            self.assertIsInstance(cm.exception.__cause__, ValueError)
        self.assertEqual(calls, [1])
        return receipts[0]

    def test_nonzero_error_usage_and_export(self):
        value=envelope();value.update(subtype='error_during_execution',is_error=True,num_turns=0)
        receipt=self.invoke(1,raw(value))
        self.assertEqual(receipt['cli_status'], {'type':'result','subtype':'error_during_execution','is_error':True,'num_turns':0})
        self.assertEqual(receipt['reported_usage'],value['usage'])
        self.assertEqual(receipt['estimated_cost_usd'],.01)
        projected=driver.receipt_projection([receipt],{'model':MODEL})[0]
        for key in ('cli_status','failure_reason','reported_usage','reported_model_usage','response_sha256','exit_code'):
            self.assertEqual(projected[key],receipt[key])
        self.assertNotIn('quota',json.dumps(projected))

    def test_explicit_budget_turn_status_not_guessed_from_text(self):
        for subtype in ('error_max_budget_usd','error_max_turns','error_max_structured_output_retries'):
            value=envelope();value.update(subtype=subtype,is_error=True)
            self.assertEqual(self.invoke(1,raw(value))['cli_status']['subtype'],subtype)
        receipt=self.invoke(1,raw({'errors':['quota exceeded; access denied'], 'subtype':'private@example.invalid'}))
        self.assertEqual(receipt['cli_status'],{})
        self.assertNotIn('reported_usage',receipt)
        self.assertNotIn('reported_model',receipt)

    def test_malformed_json_only_hash_exit_and_reason(self):
        for value in (b'{oops', b'{"type":"result","type":"result"}', b'{"usage":NaN}'):
            receipt=self.invoke(1,value)
            self.assertEqual(receipt['failure_reason'],'malformed_envelope')
            self.assertEqual(len(receipt['response_sha256']),64)
            self.assertEqual(receipt['exit_code'],1)
            self.assertNotIn('cli_status',receipt)
            self.assertNotIn('reported_usage',receipt)
        receipt=self.invoke(1,b'[]')
        self.assertEqual(receipt['failure_reason'],'invalid_envelope_type')

    def test_success_identity_mismatch_keeps_status_not_arbitrary_model(self):
        value=envelope();value['modelUsage']={'private@example.invalid':{'outputTokens':4}}
        receipt=self.invoke(0,raw(value))
        self.assertEqual(receipt['failure_reason'],'model_identity_validation_failed')
        self.assertEqual(receipt['cli_status']['subtype'],'success')
        self.assertNotIn('reported_model',receipt)
        self.assertNotIn('private',json.dumps(receipt))

    def test_success_and_failure_extra_metadata_are_never_copied(self):
        for success in (False,True):
            value=envelope();value['account']='secret@example.invalid'
            value['usage'].update(session='secret',path='secret',token='secret',nested={'secret':1})
            value['modelUsage'][MODEL]['provider_added']='secret'
            value['errors']=['secret']
            receipt=self.invoke(0 if success else 1,raw(value),success)
            self.assertNotIn('secret',json.dumps(receipt))
            self.assertNotIn('account',receipt)
            if success:self.assertNotIn('failure_reason',receipt)

    def test_numeric_bounds_and_unknown_fields(self):
        value={'usage':dict(input_tokens=True,output_tokens=-1,cache_read_input_tokens=2**54),
               'total_cost_usd':10**400, 'num_turns':True, 'is_error':'false', 'stop_reason':None}
        self.assertEqual(_safe_cli_evidence(value,MODEL),{'cli_status':{},'reported_usage':{}})
        for cost in (float('inf'),float('nan'),-1,True,'0.1'):
            self.assertNotIn('estimated_cost_usd',_safe_cli_evidence({'total_cost_usd':cost},MODEL))
        receipt=self.invoke(1,raw({'usage':{'input_tokens':7,'output_tokens':False},'modelUsage':{MODEL:{'costUSD':.1,'outputTokens':4,'token':'secret'}}}))
        self.assertEqual(receipt['reported_usage'],{'input_tokens':7})
        self.assertEqual(receipt['reported_model_usage'],{MODEL:{'costUSD':.1,'outputTokens':4}})

    def test_helper_rejects_unsafe_costs_without_losing_error_evidence(self):
        for cost in (10**400, float('nan'), float('inf'), -1, True, '0.1'):
            with self.subTest(cost_type=type(cost).__name__):
                receipt = {'estimated_cost_usd': cost,
                           'reported_model_usage': {MODEL: {'costUSD': cost, 'outputTokens': 4}},
                           'outcome': 'error', 'error_type': 'CleanupUncertain',
                           'response_sha256': 'a'*64, 'exit_code': 1}
                projected = driver.receipt_projection([receipt], {'model': MODEL})[0]
                self.assertNotIn('estimated_cost_usd', projected)
                self.assertEqual(projected['reported_model_usage'], {MODEL: {'outputTokens': 4}})
                self.assertEqual(projected['error_type'], 'CleanupUncertain')
                self.assertEqual(projected['outcome'], 'error')
                self.assertEqual(projected['response_sha256'], 'a'*64)
                self.assertEqual(projected['exit_code'], 1)
                # Projection remains serializable for report writing.
                self.assertEqual(json.loads(json.dumps(projected, allow_nan=False)), projected)

    def test_helper_does_not_trust_injected_projection(self):
        projected=driver.receipt_projection([{'cli_status':{'type':'secret','subtype':'secret','num_turns':True,'is_error':'secret','account':'secret'},'failure_reason':'secret'}],{'model':MODEL})[0]
        self.assertEqual(projected,{'cli_status':{}})

if __name__ == '__main__':unittest.main()
