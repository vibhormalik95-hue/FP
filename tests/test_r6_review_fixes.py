"""Regression tests for the r6 code-review should-fix items (record-file redaction scope, ledger error text)."""
import pytest

from feedctrl import model_routes
from feedctrl.llm_providers import Ledger, reserved_call


def test_record_files_keep_long_ids_but_cut_prefixed_keys():
    long_id = b"Ab3" + b"x" * 20 + b"Y9z" * 7          # 44 mixed-case characters, not a key prefix
    key = b"sk-" + b"Q" * 30
    cleaned, changed = model_routes.scrub_bytes(b"id " + long_id + b" key " + key)
    assert long_id in cleaned and key not in cleaned and changed


class Boom:
    name, model, free, _secret = "openai", "gpt-5-mini", False, ""

    def estimate_usd(self, system, payload, max_output_tokens=None):
        return 0.001

    def complete(self, *a):
        raise RuntimeError("connect to https://user:SENTINELPASS@example.test/v1?token=SENTINELTOKEN failed")


def test_unexpected_failure_books_no_raw_exception_text():
    ledger = Ledger(budget_usd=1.0)
    with pytest.raises(Exception):
        reserved_call(Boom(), ledger, "t", "s", {}, {})
    text = repr(ledger.calls)
    assert "SENTINELPASS" not in text and "SENTINELTOKEN" not in text and "unexpected failure" in text
