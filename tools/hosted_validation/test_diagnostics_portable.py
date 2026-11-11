"""Real adapter/helper, authored envelopes, injected callable; no native backend."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(sys.argv[1]).resolve()
CANDIDATE = ROOT.parent
ADAPTER = ROOT / 'feedctrl' / 'claude_personal.py'
DRIVER = ROOT / 'tools' / 'hosted_validation' / 'driver.py'
EXPECTED = {
    ADAPTER: '5971daefba03dd88fbf3b6b9b107fcb05371210cd660914d9022553e78af3113',
    DRIVER: '8d1cc561b4d466d93c780aa85223f47b82a087539c18f5f0cb371607fbc0d2f5',
}
for path, expected in EXPECTED.items():
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise RuntimeError('Frozen candidate identity differs')

# Deliberately strengthen, never replace, the unchanged original audit guard.
# Refuse ctypes itself, so Windows cannot initialize kernel32 as an import side effect.
FORBIDDEN = {'ctypes', '_ctypes', 'feedctrl.windows_job_native'}
if any(name in sys.modules for name in FORBIDDEN):
    raise RuntimeError('Native modules already loaded; fresh interpreter required')
def no_native_import(event, args):
    if event == 'import' and args and (
        args[0] in FORBIDDEN or str(args[0]).startswith('ctypes.')
    ):
        raise RuntimeError('Native module outside portable diagnostic scope: ' + args[0])
sys.addaudithook(no_native_import)

from feedctrl.claude_personal import make_claude_personal_infer
from feedctrl.controls import ParserOperationalError
from feedctrl.model_adapters import HostedRunBudget
from feedctrl.windows_job_runner import run_with_backend, CleanupUncertain
spec = importlib.util.spec_from_file_location('portable_diagnostic_driver', DRIVER)
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)
MODEL = 'claude-fable-5-2'
SCHEMA = {'type':'object','properties':{'label':{'type':'string'}},
          'required':['label'],'additionalProperties':False}

class Diagnostics(unittest.TestCase):
    def invoke(self, status, raw, success=False):
        calls = []
        def fake(*args):
            calls.append(args)
            return status, raw
        budget = HostedRunBudget(1)
        infer, _, receipts = make_claude_personal_infer(
            # Existing inert Python file, never launched. No Path or OS mocks.
            executable=str(ADAPTER), workdir=str(ROOT), model=MODEL, effort='max',
            run_budget=budget, estimated_per_invocation_usd=.1, output_mode='plain_json',
            runtime_authorized=True, data_authorized=True,
            subscription_and_usage_authorized=True, executable_reviewed=True,
            managed_runtime_reviewed=True, process_containment_reviewed=True,
            reviewed_cli_version='2.1.321', process_runner=fake)
        payload={'system':'Synthetic test only','text':'authored fixture'}
        if success:
            self.assertEqual(infer(payload, SCHEMA), {'label':'ok'})
        else:
            with self.assertRaises(ParserOperationalError): infer(payload, SCHEMA)
        self.assertEqual(len(calls),1)
        self.assertEqual(budget.attempted,1)
        with self.assertRaises(ParserOperationalError): infer(payload, SCHEMA)
        self.assertEqual(len(calls),1)
        self.assertEqual(receipts[0]['response_sha256'], hashlib.sha256(raw).hexdigest())
        projected=driver.receipt_projection(receipts, {'model':MODEL})[0]
        return receipts[0], projected

    def envelope(self):
        return {'type':'result','subtype':'success','is_error':False,'num_turns':1,
                'result':'{"label":"ok"}', 'usage':{'input_tokens':1,'output_tokens':4},
                'modelUsage':{MODEL:{'outputTokens':4}}, 'total_cost_usd':.01}

    def test_success_real_adapter_and_projection(self):
        receipt, projected=self.invoke(0,json.dumps(self.envelope()).encode(),True)
        self.assertEqual(receipt['outcome'],'parsed_transport_only')
        self.assertEqual(projected['reported_model'],MODEL)
        self.assertNotIn('failure_reason',projected)

    def test_nonzero_evidence_without_private_fields(self):
        value=self.envelope()
        value.update(subtype='error_during_execution',is_error=True,num_turns=0,
                     errors=['PRIVATE_CANARY quota access denied'], account='PRIVATE_CANARY')
        value['usage']['private']='PRIVATE_CANARY'
        receipt, projected=self.invoke(1,json.dumps(value).encode())
        self.assertEqual(projected['cli_status']['subtype'],'error_during_execution')
        self.assertEqual(projected['exit_code'],1)
        self.assertEqual(projected['reported_usage'],{'input_tokens':1,'output_tokens':4})
        self.assertNotIn('PRIVATE_CANARY',json.dumps([receipt,projected]))
        self.assertNotIn('quota',json.dumps(projected))

    def test_malformed_receipts_remain_minimal(self):
        for raw in (b'{oops', b'{"type":1,"type":2}', b'{"usage":NaN}'):
            with self.subTest(raw=raw):
                receipt, projected=self.invoke(1,raw)
                self.assertEqual(projected['failure_reason'],'malformed_envelope')
                self.assertNotIn('reported_usage',receipt)
                self.assertNotIn('cli_status',receipt)

    def test_invalid_model_metadata_preserves_status(self):
        value=self.envelope(); value['modelUsage']={'PRIVATE_CANARY':{'outputTokens':4}}
        _,projected=self.invoke(0,json.dumps(value).encode())
        self.assertEqual(projected['cli_status']['subtype'],'success')
        self.assertNotIn('reported_model',projected)
        self.assertNotIn('PRIVATE_CANARY',json.dumps(projected))

    def test_overflow_cost_does_not_discard_error_status(self):
        value=self.envelope(); value.update(is_error=True,subtype='error_max_turns',total_cost_usd=10**400)
        value['modelUsage'][MODEL]['costUSD']=10**400
        _,projected=self.invoke(1,json.dumps(value).encode())
        self.assertEqual(projected['cli_status']['subtype'],'error_max_turns')
        self.assertNotIn('estimated_cost_usd',projected)
        self.assertNotIn('costUSD',projected['reported_model_usage'][MODEL])

    def test_original_guard_denies_synthetic_events(self):
        # Audit event emission only. No socket, process, file or DLL operation.
        probes=[('subprocess.Popen',()), ('socket.connect',()),
                ('socket.getaddrinfo',()), ('ctypes.dlopen',('kernel32',)),
                ('import',('torch',)), ('open',('synthetic.gguf',))]
        for event,args in probes:
            with self.subTest(event=event),self.assertRaisesRegex(RuntimeError,'Blocked offline:'):
                sys.audit(event,*args)

    def test_native_modules_never_loaded(self):
        self.assertFalse(FORBIDDEN.intersection(sys.modules))
