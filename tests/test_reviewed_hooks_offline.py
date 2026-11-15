"""Authored adapter checks only: no CLI, hooks, model, process, or network."""
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from feedctrl.claude_personal import make_claude_personal_infer
from feedctrl.controls import ParserOperationalError
from feedctrl.model_adapters import HostedRunBudget
from feedctrl.windows_job_runner import CleanupUncertain

MODEL = 'claude-offline-test'
CONTEXT = 'a' * 64
SCHEMA = {'type': 'object', 'additionalProperties': False,
          'required': ['title'], 'properties': {'title': {'type': 'string'}}}
PAYLOAD = {'system': 'Synthetic test only', 'brief': 'Imaginary garden'}
GATES = ('runtime_authorized', 'data_authorized', 'subscription_and_usage_authorized',
         'executable_reviewed', 'managed_runtime_reviewed', 'process_containment_reviewed')


def envelope():
    return {'type': 'result', 'subtype': 'success', 'is_error': False, 'num_turns': 1,
            'stop_reason': 'end_turn', 'usage': {'input_tokens': 1, 'output_tokens': 1},
            'modelUsage': {MODEL: {}}, 'total_cost_usd': 0, 'result': '{"title":"Imaginary garden"}'}


def options(runner):
    opts = dict(executable=str(Path.cwd() / 'offline-only-cli'),
                workdir=str(Path.cwd() / 'offline-only-directory'),
                model=MODEL, effort='max', run_budget=HostedRunBudget(1),
                estimated_per_invocation_usd=0.5, output_mode='plain_json',
                reviewed_cli_version='2.1.321', process_runner=runner)
    opts.update({name: True for name in GATES})
    return opts


def call(mode=None, response=None, context=CONTEXT):
    seen = []

    def fake(*args):
        seen.append(deepcopy(args))
        return 0, json.dumps(envelope() if response is None else response).encode()

    opts = options(fake)
    if mode is not None:
        opts['runtime_mode'] = mode
    if mode == 'reviewed_hooks':
        opts['reviewed_hooks_context_sha256'] = context
    infer, provenance, receipts = make_claude_personal_infer(**opts)
    with patch.object(Path, 'is_file', return_value=True), patch.object(Path, 'is_dir', return_value=True):
        result = infer(PAYLOAD, SCHEMA)
    return result, provenance, receipts, seen


class ReviewedHooksTests(unittest.TestCase):
    def test_default_and_explicit_safe_mode_are_identical(self):
        default, explicit = call(), call('safe_mode')
        self.assertEqual(default[0], explicit[0])
        self.assertEqual(default[1], explicit[1])
        self.assertEqual(default[3], explicit[3])
        self.assertTrue(default[1]['safe_mode'])
        self.assertIn('--safe-mode', default[3][0][0])

    def test_reviewed_mode_only_removes_safe_mode_from_arguments(self):
        safe, reviewed = call(), call('reviewed_hooks')
        old, new = safe[3][0][0], reviewed[3][0][0]
        self.assertEqual([argument for argument in old if argument != '--safe-mode'], new)
        self.assertEqual(safe[3][0][1:], reviewed[3][0][1:])
        self.assertFalse(reviewed[1]['safe_mode'])
        self.assertEqual(reviewed[1]['runtime_mode'], 'reviewed_hooks')
        self.assertEqual(reviewed[1]['reviewed_hooks_context_sha256'], CONTEXT)
        self.assertEqual(reviewed[1]['hook_context_review'], 'operator_asserted_not_attested')
        self.assertEqual(reviewed[1]['hook_execution'], 'not_verified')
        self.assertNotEqual(safe[1]['digest'], reviewed[1]['digest'])

    def test_context_changes_digest_not_arguments(self):
        first, second = call('reviewed_hooks'), call('reviewed_hooks', context='b' * 64)
        self.assertNotEqual(first[1]['digest'], second[1]['digest'])
        self.assertEqual(first[3], second[3])

    def test_mode_and_context_validation_fail_before_runner(self):
        for mode, context in [(None, None), ('', None), ('other', None), (False, None),
                              ('reviewed_hooks', None), ('reviewed_hooks', 'A' * 64),
                              ('reviewed_hooks', '0' * 63), ('safe_mode', CONTEXT)]:
            called = []
            opts = options(lambda *args: called.append(True))
            opts.update(runtime_mode=mode, reviewed_hooks_context_sha256=context)
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                make_claude_personal_infer(**opts)
            self.assertEqual(called, [])

    def test_all_review_gates_remain_required(self):
        for gate in GATES:
            called = []
            opts = options(lambda *args: called.append(True))
            opts.update(runtime_mode='reviewed_hooks', reviewed_hooks_context_sha256=CONTEXT)
            opts[gate] = False
            with self.subTest(gate=gate), self.assertRaises(ValueError):
                make_claude_personal_infer(**opts)
            self.assertEqual(called, [])

    def test_refusal_identity_turn_and_schema_rejections_do_not_retry(self):
        for field, value in [('stop_reason', 'refusal'), ('num_turns', 2),
                             ('modelUsage', {'wrong-model': {}}), ('is_error', True),
                             ('result', '{"wrong":"x"}')]:
            response, called = envelope(), []
            response[field] = value

            def fake(*args):
                called.append(True)
                return 0, json.dumps(response).encode()

            opts = options(fake)
            opts.update(runtime_mode='reviewed_hooks', reviewed_hooks_context_sha256=CONTEXT)
            infer, _, receipts = make_claude_personal_infer(**opts)
            with self.subTest(field=field), patch.object(Path, 'is_file', return_value=True), \
                    patch.object(Path, 'is_dir', return_value=True):
                with self.assertRaises(ParserOperationalError):
                    infer(PAYLOAD, SCHEMA)
                with self.assertRaises(ParserOperationalError):
                    infer(PAYLOAD, SCHEMA)
            self.assertEqual(called, [True])
            self.assertEqual(receipts[0]['outcome'], 'error')

    def test_uncertain_cleanup_blocks_later_call(self):
        called = []

        def fake(*args):
            called.append(True)
            raise CleanupUncertain('synthetic')

        opts = options(fake)
        opts['run_budget'] = HostedRunBudget(2)
        opts.update(runtime_mode='reviewed_hooks', reviewed_hooks_context_sha256=CONTEXT)
        infer, _, _ = make_claude_personal_infer(**opts)
        with patch.object(Path, 'is_file', return_value=True), patch.object(Path, 'is_dir', return_value=True):
            with self.assertRaises(ParserOperationalError):
                infer(PAYLOAD, SCHEMA)
            with self.assertRaises(ParserOperationalError):
                infer(PAYLOAD, SCHEMA)
        self.assertEqual(called, [True])


if __name__ == '__main__':
    unittest.main()
