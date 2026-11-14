"""Offline failure-receipt tests. No executable or provider is invoked."""
import hashlib
import json
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from test_cli_terminal_claim import m, relay

class FailureEvidenceTests(unittest.TestCase):
    def test_nonzero_structured_stdout_and_private_stderr(self):
        stdout = json.dumps(dict(type='result', subtype='error_max_turns', is_error=True,
                                 stop_reason='refusal', num_turns=2, result='PRIVATE-OUTPUT')).encode()
        self.check_failure(types.SimpleNamespace(returncode=1, stdout=stdout,
                           stderr=b'Authorization: Bearer PRIVATE-SECRET'), stdout)

    def test_timeout_retains_partial_output_metadata(self):
        stdout = b'{"type":"result","subtype":"error_during_execution","is_error":true}'
        self.check_failure(m.subprocess.TimeoutExpired('fake', 1, output=stdout,
                           stderr=b'PRIVATE-SECRET'), stdout)

    def check_failure(self, outcome, stdout):
        args=types.SimpleNamespace(wait=1,model='test-model',effort='low',max_budget_usd=1,
                                  timeout=1,allow_other_models=False)
        with tempfile.TemporaryDirectory() as directory:
            spool=Path(directory)
            kwargs = {'side_effect':outcome} if isinstance(outcome,Exception) else {'return_value':outcome}
            with patch.object(m.subprocess,'run',**kwargs) as run, patch.object(relay,'deliver') as deliver:
                with self.assertRaises(SystemExit) as stopped:
                    m.one_call(spool,1,'fake.exe',args)
                run.assert_called_once(); deliver.assert_not_called()
                text=(spool/'cli-call-0001.json').read_text()
                self.assertNotIn('PRIVATE-',text+str(stopped.exception))
                record=json.loads(text)
                self.assertFalse(record['delivered'])
                self.assertEqual(record['failure_output']['stdout']['sha256'],hashlib.sha256(stdout).hexdigest())
                self.assertEqual(record['failure_output']['stdout']['bytes'],len(stdout))
                self.assertTrue(record['failure_output']['stdout']['terminal']['is_error'])
                before={p.name:p.read_bytes() for p in spool.iterdir()}
                with self.assertRaises(SystemExit):m.one_call(spool,1,'fake.exe',args)
                run.assert_called_once(); deliver.assert_not_called()
                self.assertEqual(before,{p.name:p.read_bytes() for p in spool.iterdir()})
                self.assertEqual(set(before),{'cli-attempt-0001.json','cli-call-0001.json'})

    def test_untrusted_fields_not_retained(self):
        raw=json.dumps(dict(type='SECRET',subtype='PRIVATE',stop_reason='TOKEN',
                            num_turns=True,is_error='PASSWORD',errors=['PRIVATE'])).encode()
        result=m.failure_output_summary(raw,None)
        self.assertEqual(result['stdout']['terminal'],dict(type='unrecognized',subtype='unrecognized',stop_reason='unrecognized'))
        self.assertEqual(result['stderr'],{'available':False})

    def test_parse_bound_and_invalid_bytes(self):
        for raw,status in ((b'x'*65537,'over_limit'),(b'\xff','invalid'),(b'[]','not_object'),
                           (b'{"type":"result","type":"secret"}','invalid'),(b'{"n":NaN}','invalid'),
                           (b'['*1000,'invalid')):
            with self.subTest(status=status):
                result=m.failure_output_summary(raw,b'')['stdout']
                self.assertEqual(result['json_status'],status)
                self.assertNotIn('terminal',result)

    def test_text_timeout_and_missing_outputs(self):
        result=m.failure_output_summary('private partial text',None)
        self.assertEqual(result['stdout']['bytes'],20)
        self.assertNotIn('private',json.dumps(result))

if __name__=='__main__':unittest.main()
