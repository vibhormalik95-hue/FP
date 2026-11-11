"""Explicit runner contract using authored responses only, with no processes or network."""
import csv
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from feedctrl.claude_personal import make_claude_personal_infer
from feedctrl.claude_personal_app import create_claude_personal_app
from feedctrl.controls import ParserOperationalError
from feedctrl.model_adapters import HostedRunBudget
from feedctrl.windows_job_runner import CleanupUncertain
from test_claude_personal_offline import MODEL, PAYLOAD, SCHEMA, envelope, raw, options
from test_hosted_synthetic_offline import DirectClient, setup, preview, RAW


class ExplicitRunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.exe = Path(self.tmp.name) / 'fake-cli'
        self.exe.touch()
        from feedctrl.semantic_controls import TEXT_FIELDS
        self.semantic_path = Path(self.tmp.name) / 'fixture.csv'
        with self.semantic_path.open('w', newline='', encoding='utf8') as handle:
            writer = csv.DictWriter(handle, fieldnames=['video_id', *TEXT_FIELDS])
            writer.writeheader()
            for item in range(1, 37):
                writer.writerow({'video_id': item, 'caption': 'Freshly baked bread' if item in (3, 4) else 'Bicycle commuting'})

    def opts(self, budget=None, **overrides):
        result = options(budget)
        result.update(executable=str(self.exe), workdir=self.tmp.name)
        result.update(overrides)
        return result

    def test_default_is_disabled_and_construction_does_not_execute(self):
        for extra in ({}, {'process_runner': None}):
            budget = HostedRunBudget(1)
            infer, identity, receipts = make_claude_personal_infer(**self.opts(budget, **extra))
            self.assertEqual(identity['process_runner_selection'], 'disabled_default')
            self.assertEqual(receipts, [])
            with self.assertRaises(ParserOperationalError) as cm:
                infer(PAYLOAD, SCHEMA)
            self.assertIn('CLI launch disabled', str(cm.exception.__cause__))
            self.assertEqual(budget.attempted, 1)

    def test_non_callable_and_all_review_gates_fail_before_execution(self):
        for runner in (False, 1, 'runner', object()):
            budget = HostedRunBudget(1)
            with self.assertRaisesRegex(ValueError, 'callable'):
                make_claude_personal_infer(**self.opts(budget, process_runner=runner))
            self.assertEqual(budget.attempted, 0)
        calls = []
        for gate in ('runtime_authorized', 'data_authorized', 'subscription_and_usage_authorized',
                     'executable_reviewed', 'managed_runtime_reviewed', 'process_containment_reviewed'):
            for value in (False, None):
                budget = HostedRunBudget(1)
                with self.assertRaises(ValueError):
                    make_claude_personal_infer(**self.opts(budget, process_runner=lambda *a: calls.append(a), **{gate: value}))
                self.assertEqual(budget.attempted, 0)
        self.assertEqual(calls, [])

    def test_explicit_runner_arguments_modes_and_provenance(self):
        for mode in ('schema_tool', 'plain_json'):
            calls = []
            response = envelope()
            if mode == 'plain_json':
                response['result'] = json.dumps(response.pop('structured_output'))
            def runner(*args):
                calls.append(args)
                return 0, raw(response)
            budget = HostedRunBudget(1)
            infer, identity, receipts = make_claude_personal_infer(**self.opts(budget, process_runner=runner, output_mode=mode, timeout=7, max_response_bytes=1234))
            self.assertEqual(calls, [])
            with patch.dict(os.environ, {'ANTHROPIC_API_KEY': 'secret', 'UNRELATED_SECRET': 'secret'}):
                self.assertEqual(infer(PAYLOAD, SCHEMA), {'label':'ok','n':1})
            self.assertEqual(len(calls), 1)
            argv, data, env, cwd, timeout, maximum = calls[0]
            self.assertEqual((cwd, timeout, maximum), (self.tmp.name, 7, 1234))
            self.assertEqual(json.loads(data), {'text':'synthetic input'})
            for flag in ('--safe-mode', '--no-chrome', '--no-session-persistence', '--permission-mode', '--permission-prompts', '--max-turns'):
                self.assertIn(flag, argv)
            self.assertEqual(argv[argv.index('--tools')+1], '')
            self.assertEqual(argv[argv.index('--disallowedTools')+1], 'mcp__*')
            self.assertEqual(argv[argv.index('--model')+1], MODEL)
            self.assertEqual('--json-schema' in argv, mode == 'schema_tool')
            self.assertNotIn('ANTHROPIC_API_KEY', env)
            self.assertNotIn('UNRELATED_SECRET', env)
            from feedctrl.claude_personal import _ENV_ALLOW
            self.assertLessEqual(set(env), set(_ENV_ALLOW) | {'CLAUDE_CODE_MAX_RETRIES','CLAUDE_CODE_NONSTREAMING_TIMEOUT_RETRIES','MAX_STRUCTURED_OUTPUT_RETRIES','CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK','CLAUDE_CODE_MAX_OUTPUT_TOKENS','DISABLE_AUTOUPDATER','CLAUDE_CODE_DISABLE_REFUSAL_FALLBACK'})
            self.assertEqual(identity['process_runner_selection'], 'explicit')
            self.assertIn('not_model_weights', identity['digest_kind'])
            self.assertEqual(receipts[0]['outcome'], 'parsed_transport_only')
            self.assertEqual(budget.attempted, 1)

    def test_bad_boundaries_fail_closed_and_consume_one_reservation(self):
        for response in (None, (True, b'{}'), ('0', b'{}'), (0, '{}'), (0, b'x'*1001), (1, raw(envelope()))):
            calls = []
            def runner(*args):
                calls.append(args)
                return response
            budget = HostedRunBudget(1)
            infer, _, receipts = make_claude_personal_infer(**self.opts(budget, process_runner=runner, max_response_bytes=1000))
            with self.subTest(response=repr(response)[:25]):
                with self.assertRaises(ParserOperationalError): infer(PAYLOAD, SCHEMA)
                self.assertEqual((len(calls), budget.attempted, len(receipts)), (1, 1, 1))
                self.assertEqual(receipts[0]['outcome'], 'error')
                if response != (1, raw(envelope())):
                    self.assertNotIn('response_sha256', receipts[0])

    def test_timeout_and_errors_redacted_no_retry(self):
        for failure in (TimeoutError('secret timeout'), OSError('secret failure')):
            calls = []
            def runner(*args):
                calls.append(args)
                raise failure
            budget = HostedRunBudget(1)
            infer, _, receipts = make_claude_personal_infer(**self.opts(budget, process_runner=runner))
            with self.assertRaises(ParserOperationalError) as cm: infer(PAYLOAD, SCHEMA)
            self.assertNotIn('secret', str(cm.exception))
            self.assertEqual((len(calls), budget.attempted, receipts[0]['outcome']), (1, 1, 'error'))

    def test_request_or_schema_rejected_before_reservation(self):
        calls = []
        budget = HostedRunBudget(2)
        infer, _, receipts = make_claude_personal_infer(**self.opts(budget, process_runner=lambda *a: calls.append(a)))
        for payload, schema in (({'system':'x','text':'x'*30000}, SCHEMA), (PAYLOAD, {'type':'object','$ref':'https://example.com'}), (PAYLOAD, {'type':'object','properties':{'x':{'type':'string','enum':['x'*30000]}}})):
            with self.assertRaises(ValueError): infer(payload, schema)
        self.assertEqual((calls, budget.attempted, receipts), ([], 0, []))

    def app_factories(self, runner, budget):
        import feedctrl.api as api
        real_create_app = api.create_app
        capture = {}
        def create(*args, **kwargs):
            capture.update(kwargs)
            return real_create_app(*args, **kwargs)
        with patch.object(api, 'create_app', side_effect=create):
            app = create_claude_personal_app(operator_token='a'*32, allowed_origin='http://127.0.0.1:8000', fixture=True, semantic_path=self.semantic_path, **self.opts(budget, process_runner=runner))
        return app, capture

    def test_actual_app_paths_share_budget_and_receipts(self):
        calls = []
        def runner(*args):
            calls.append(args)
            return 0, raw(envelope(RAW))
        budget = HostedRunBudget(1)
        app, factories = self.app_factories(runner, budget)
        self.assertEqual(calls, [])
        self.assertIs(factories['semantic_infer_factory'], factories['synthetic_infer_factory'])
        with DirectClient(app) as client:
            response = preview(client, setup(client)).json()
        self.assertTrue(response['ready'])
        self.assertEqual((len(calls), budget.attempted, len(app.state.hosted_model_receipts)), (1, 1, 1))
        from feedctrl.semantic_review import SemanticPreview, InductionPreview
        endpoint = lambda path: next(r.endpoint for r in app.routes if getattr(r, 'path', None) == path)
        session = endpoint('/api/session')()['session_id']
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as semantic_error:
            endpoint('/api/semantic/preview')(SemanticPreview(user_id=1, label='Fixture', candidate_ids=[1, 2], text='Hide bread', backend='configured_model', action_source='model'), session)
        self.assertEqual(semantic_error.exception.status_code, 502)
        category = endpoint('/api/semantic/induction/preview')(InductionPreview(user_id=1, candidate_ids=[1, 2], objective='Find bread'), session)
        self.assertFalse(category['ready'])
        self.assertEqual((len(calls), budget.attempted, len(app.state.hosted_model_receipts)), (1, 1, 1))

    def test_cleanup_uncertainty_latches_across_factories(self):
        calls = []
        error = CleanupUncertain('secret')
        def runner(*args):
            calls.append(args)
            raise error
        budget = HostedRunBudget(3)
        app, factories = self.app_factories(runner, budget)
        with self.assertRaises(ParserOperationalError) as cm:
            factories['category_infer_factory']()[0]({'instructions':'x'}, SCHEMA)
        self.assertIs(cm.exception.__cause__, error)
        self.assertNotIn('secret', str(cm.exception))
        with self.assertRaisesRegex(ParserOperationalError, 'Run stopped'):
            factories['semantic_infer_factory']()[0](PAYLOAD, SCHEMA)
        self.assertEqual((len(calls), budget.attempted, len(app.state.hosted_model_receipts)), (1, 1, 1))

if __name__ == '__main__': unittest.main()
