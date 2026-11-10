"""Truncated-response regressions using authored bytes and an in-memory opener.

No sockets, provider/model calls, local inference, or Windows processes run.
The optional ledger uses synthetic proof and prices, not verified live billing.
Run with PYTHONPATH=.:tests python -m unittest -v test_transport_errors_offline.
"""
from copy import deepcopy
import csv
import hashlib
import http.client
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import urllib.error

from feedctrl import model_adapters as ma
from feedctrl.controls import ParserOperationalError
from feedctrl.hosted_spend_guard import DurableHostedSpendGuard, canonical


SCHEMA = {"type": "object", "required": ["ok"], "additionalProperties": False,
          "properties": {"ok": {"type": "boolean"}}}
PAYLOAD = {"system": "Offline transport test only.", "request": "Authored fixture"}
KEY = "OFFLINE-DUMMY-NOT-A-CREDENTIAL"


def request_body():
    return {"model": "gpt-6.1-sol", "store": False, "stream": False,
            "service_tier": "default", "reasoning": {"effort": "medium"},
            "max_output_tokens": 4096,
            "input": [{"role": "system", "content": PAYLOAD["system"]},
                      {"role": "user", "content": canonical({"request": PAYLOAD["request"]}).decode()}],
            "text": {"format": {"type": "json_schema", "name": "feed_control",
                                "strict": True, "schema": SCHEMA}}}


def synthetic_policy():
    return {"run_id": "offline-truncated-response", "model": "gpt-6.1-sol",
            "reasoning_effort": "medium",
            "allowed_request_sha256": [hashlib.sha256(canonical(request_body())).hexdigest()],
            "max_input_tokens": 16000, "max_output_tokens": 4096,
            "input_usd_per_million": "5", "output_usd_per_million": "10",
            "counter_upper_micro_usd": 1000, "other_upper_micro_usd": 1000,
            "price_evidence_sha256": "a" * 64, "counter_evidence_sha256": "b" * 64,
            "account_evidence_sha256": "c" * 64}


class IncompleteResponse:
    status = 200
    headers = {"x-request-id": "offline-incomplete-response"}

    def __init__(self):
        self.error = http.client.IncompleteRead(b'{"private":"' + KEY.encode(), 100)
        self.read_sizes = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        self.closed = True

    def read(self, size):
        self.read_sizes.append(size)
        raise self.error


class TransportErrorTests(unittest.TestCase):
    def setUp(self):
        # Fail closed even if a future edit accidentally bypasses the fake opener.
        for target in ("socket.socket", "socket.create_connection"):
            mock = patch(target, side_effect=AssertionError("No network in offline tests"))
            mock.start()
            self.addCleanup(mock.stop)

    def adapter(self, guard=None, *, open_error=None):
        response = IncompleteResponse()
        opener = Mock()
        opener.open.side_effect = open_error
        opener.open.return_value = response
        budget = ma.HostedRunBudget(1)
        with patch.object(ma.urllib.request, "build_opener", return_value=opener):
            infer, provenance, receipts = ma.make_openai_responses_infer(
                api_key=KEY, model="gpt-6.1-sol", reasoning_effort="medium",
                run_budget=budget, authorized=True, spend_guard=guard)
        opener.open.assert_not_called()
        return infer, provenance, receipts, budget, opener, response

    def guard(self, path):
        calls = []

        def count(raw):
            calls.append(raw)
            return {"request_sha256": hashlib.sha256(raw).hexdigest(), "model": "gpt-6.1-sol",
                    "input_tokens": 42, "counter_receipt_sha256": "d" * 64}

        return DurableHostedSpendGuard.create_new(path, synthetic_policy(), count), calls

    def test_incomplete_read_finalizes_receipt_without_retry_or_budget_refund(self):
        infer, provenance, receipts, budget, opener, response = self.adapter()
        with self.assertRaisesRegex(ParserOperationalError, "Hosted model attempt failed: IncompleteRead") as caught:
            infer(PAYLOAD, SCHEMA)
        self.assertIs(caught.exception.__cause__, response.error)
        self.assertNotIn(KEY, str(caught.exception))
        self.assertTrue(response.closed)
        self.assertEqual(response.read_sizes, [2_000_001])
        self.assertEqual(len(receipts), 1)
        receipt = receipts[0]
        self.assertEqual(receipt["outcome"], "error")
        self.assertEqual(receipt["error_type"], "IncompleteRead")
        self.assertEqual(receipt["representation"], "actual_hosted_attempt")
        self.assertEqual(receipt["call_id"], 1)
        self.assertEqual(receipt["http_status"], 200)
        self.assertEqual(receipt["provider_request_id"], "offline-incomplete-response")
        self.assertGreaterEqual(receipt["elapsed_seconds"], 0)
        # Incomplete bytes are not misrepresented as a complete provider response.
        self.assertNotIn("response_base64", receipt)
        self.assertNotIn("raw_response", receipt)
        self.assertNotIn(KEY, json.dumps((provenance, receipts)))
        with self.assertRaisesRegex(ParserOperationalError, "budget exhausted"):
            infer(PAYLOAD, SCHEMA)
        self.assertEqual(budget.attempted, 1)
        self.assertEqual(opener.open.call_count, 1)
        self.assertEqual(len(receipts), 1)

    def test_incomplete_read_marks_durable_failure_and_keeps_reservation_consumed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.sqlite"
            guard, counter_calls = self.guard(path)
            infer, _, receipts, budget, opener, _ = self.adapter(guard)
            with self.assertRaises(ParserOperationalError):
                infer(PAYLOAD, SCHEMA)
            self.assertEqual(receipts[0]["outcome"], "error")
            snapshot = guard.snapshot()
            self.assertTrue(snapshot["blocked"])
            self.assertEqual(snapshot["reserved_micro_usd"], 250000)
            self.assertEqual(snapshot["attempts"][0]["state"], "failed")
            restarted = DurableHostedSpendGuard.open_existing(path, synthetic_policy(), guard.counter)
            self.assertEqual(restarted.snapshot(), snapshot)
            with self.assertRaises(ParserOperationalError):
                infer(PAYLOAD, SCHEMA)
            self.assertEqual(len(counter_calls), 1)
            self.assertEqual(opener.open.call_count, 1)
            self.assertEqual(budget.attempted, 1)
            self.assertEqual(receipts[-1]["representation"], "preflight_only")

    def test_secondary_ledger_failure_does_not_hide_incomplete_read_or_reopen_run(self):
        with tempfile.TemporaryDirectory() as directory:
            guard, counter_calls = self.guard(Path(directory) / "synthetic.sqlite")
            infer, _, receipts, budget, opener, response = self.adapter(guard)
            with patch.object(guard, "fail", side_effect=OSError("authored persistence failure")):
                with self.assertRaises(ParserOperationalError) as caught:
                    infer(PAYLOAD, SCHEMA)
            self.assertIs(caught.exception.__cause__, response.error)
            self.assertEqual(receipts[0]["outcome"], "error")
            self.assertEqual(receipts[0]["error_type"], "IncompleteRead")
            self.assertEqual(receipts[0]["guard_persistence_error_type"], "OSError")
            self.assertEqual(guard.snapshot()["attempts"][0]["state"], "counted")
            self.assertEqual(guard.snapshot()["reserved_micro_usd"], 250000)
            with self.assertRaises(ParserOperationalError):
                infer(PAYLOAD, SCHEMA)
            self.assertEqual(len(counter_calls), 1)
            self.assertEqual(opener.open.call_count, 1)
            self.assertEqual(budget.attempted, 1)

    def test_incomplete_http_error_capture_preserves_primary_failure(self):
        body = IncompleteResponse()
        error = urllib.error.HTTPError(ma.ENDPOINT, 503, "offline", body.headers, body)
        infer, _, receipts, budget, opener, _ = self.adapter(open_error=error)
        with self.assertRaises(ParserOperationalError) as caught:
            infer(PAYLOAD, SCHEMA)
        self.assertIs(caught.exception.__cause__, error)
        self.assertEqual(receipts[0]["outcome"], "error")
        self.assertEqual(receipts[0]["error_type"], "HTTPError")
        self.assertEqual(receipts[0]["http_status"], 503)
        self.assertEqual(receipts[0]["response_capture_error_type"], "IncompleteRead")
        self.assertEqual(opener.open.call_count, 1)
        self.assertEqual(budget.attempted, 1)

    def test_configured_indirect_preview_maps_incomplete_read_to_502_without_apply(self):
        # Direct endpoint call only: no HTTP server, browser or model execution.
        from fastapi import HTTPException
        from feedctrl.api import create_app
        from feedctrl.semantic_controls import TEXT_FIELDS
        from feedctrl.semantic_review import SemanticPreview

        def endpoint(app, path):
            return next(route.endpoint for route in app.routes if getattr(route, "path", None) == path)

        infer, provenance, receipts, budget, opener, _ = self.adapter()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "authored.csv"
            with path.open("w", newline="", encoding="utf8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["video_id", *TEXT_FIELDS])
                writer.writeheader()
                for item_id in range(1, 37):
                    writer.writerow({"video_id": item_id, "caption": "Freshly baked bread"})
            app = create_app(fixture=True, semantic_path=path, allow_local_models=False,
                             allow_local_recommender=False, semantic_infer_factory=lambda: (infer, provenance))
            session = endpoint(app, "/api/session")()["session_id"]
            groups = endpoint(app, "/api/semantic/groups")
            before = deepcopy(groups(1, session))
            request = SemanticPreview(user_id=1, text="Hide what makes me hungry", label="Authored fixture",
                                      candidate_ids=[3, 4], backend="configured_model", action_source="model")
            with self.assertRaises(HTTPException) as caught:
                endpoint(app, "/api/semantic/preview")(request, session)
            self.assertEqual(caught.exception.status_code, 502)
            self.assertIn("IncompleteRead", caught.exception.detail)
            self.assertNotIn(KEY, caught.exception.detail)
            self.assertEqual(groups(1, session), before)
            self.assertEqual(receipts[0]["outcome"], "error")
            self.assertEqual(opener.open.call_count, 1)
            self.assertEqual(budget.attempted, 1)


if __name__ == "__main__":
    unittest.main()
