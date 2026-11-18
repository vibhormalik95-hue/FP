"""R6 findings C4, C5a, C5b, C5c and E3a: honest spend accounting and a sanitized base URL.

No network and no paid call: providers are local fakes, and the OpenAI client is replaced by a stub
that raises the SDK's own connection error.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import openai
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from feedctrl import llm_providers as lp  # noqa: E402
from feedctrl.llm_providers import Ledger, Provider, ProviderError  # noqa: E402


class Failing(Provider):
    """A paid-looking provider whose every call fails after it may have used tokens."""
    name = "openai"

    def __init__(self, estimate=0.6):
        super().__init__("gpt-5-mini")
        self.estimate, self.calls = estimate, 0

    def estimate_usd(self, system, payload, max_output_tokens=None):
        return self.estimate

    def complete(self, task, system, payload, schema):
        self.calls += 1
        raise ProviderError("The reply was not valid JSON.")


class Translating(Failing):
    def complete(self, task, system, payload, schema):
        self.calls += 1
        return ({"translations": [{"id": t["id"], "en": "english " + t["id"]} for t in payload["texts"]]},
                {"task": task, "provider": self.name, "model": self.model, "cost_usd": 0.01, "latency_s": 0.1})


# ---------------------------------------------------------------------------------------------- C4

def test_c4_the_estimate_and_the_reservation_are_documented_as_advisory_not_an_upper_bound():
    estimate_doc = Provider.estimate_usd.__doc__.lower()
    reserve_doc = Ledger.reserve.__doc__.lower()
    assert "advisory" in estimate_doc and "not an upper bound" in estimate_doc
    assert "upper-bound cost" not in estimate_doc
    assert "cannot overspend" not in reserve_doc and "does not\n        prevent overspend" in Ledger.reserve.__doc__
    assert Provider.sdk_max_retries == 1          # the SDK retry is named, not hidden


def test_c4_a_failed_call_is_booked_with_an_unknown_actual_cost_never_as_a_bound_or_zero():
    ledger = Ledger(budget_usd=1.0)
    reservation = ledger.reserve(0.02)
    call = ledger.settle(reservation, {"task": "t", "error": "timeout", "cost_usd": None})
    assert call["cost_usd"] == 0.02 and ledger.total() == 0.02   # the budget still counts it (app behaviour kept)
    assert call["cost_known"] is False and "unknown" in call["cost_source"]
    assert "upper bound" not in call["cost_source"]
    assert ledger.unknown_cost_calls() == 1


# ---------------------------------------------------------------------------------------------- C5

def test_c5_reserved_call_refuses_a_call_that_does_not_fit_and_books_a_failure_as_unknown():
    provider, ledger = Failing(estimate=0.6), Ledger(budget_usd=1.0)
    with pytest.raises(ProviderError):
        lp.reserved_call(provider, ledger, "t", "s", {}, {})
    assert ledger.total() == 0.6 and ledger.calls[0]["cost_known"] is False and ledger.reserved() == 0
    with pytest.raises(lp.BudgetExhausted):                     # 0.6 + 0.6 > 1.0: not started
        lp.reserved_call(provider, ledger, "t", "s", {}, {})
    assert provider.calls == 1


def test_c5a_english_layer_translate_goes_through_the_reservation_and_never_books_zero():
    import build_kuairec_english as english
    provider, ledger = Failing(estimate=0.6), Ledger(budget_usd=1.0)
    assert english.translate(["a", "b"], provider, ledger, batch=1) == {}
    # Two batches, budget for one reservation: the second call is never started (old code: both ran, each 0.0).
    assert provider.calls == 1
    assert [c["cost_usd"] for c in ledger.calls] == [0.6] and ledger.calls[0]["cost_known"] is False


def test_c5b_english_eval_set_calls_through_the_reservation(tmp_path, monkeypatch):
    import build_english_eval_set as eval_set
    provider = Failing(estimate=0.6)
    monkeypatch.setattr(eval_set, "build_provider", lambda *a, **k: provider)
    with pytest.raises(SystemExit) as stopped:   # three attempts wanted; the budget of 1.0 admits one
        eval_set.main(["--out", str(tmp_path / "new")])
    assert "nothing written" in str(stopped.value)
    assert provider.calls == 1 and not (tmp_path / "new").exists()


def _gloss_inputs(tmp_path, monkeypatch, gloss):
    data = tmp_path / "processed.json"
    data.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(gloss, "read_caption_table", lambda path: ({}, {"sha256": "c" * 64}))
    monkeypatch.setattr(gloss, "build_catalog", lambda processed, rows: {
        1: {"cover_text": "x1", "caption": "", "tags": ["x2"], "kuairec_categories": []}})
    monkeypatch.setattr(gloss.time, "sleep", lambda s: None)
    return data


def test_c5c_gloss_retry_rechecks_the_budget_and_a_failure_is_not_booked_as_zero(tmp_path, monkeypatch):
    import build_kuairec_gloss as gloss
    data = _gloss_inputs(tmp_path, monkeypatch, gloss)
    provider = Failing(estimate=0.6)
    monkeypatch.setattr(gloss, "build_provider", lambda *a, **k: provider)
    out = tmp_path / "gloss.json"
    assert gloss.main(["--data", str(data), "--output", str(out), "--budget-usd", "1.0"]) == 2
    result = json.loads(out.read_text(encoding="utf-8"))
    assert provider.calls == 1                      # old code: retried without a budget check (2 calls)
    assert result["cost_usd"] == 0.6 and result["calls_with_unknown_cost"] == 1


def test_c5c_gloss_resume_refuses_strings_of_another_model(tmp_path, monkeypatch):
    import build_kuairec_gloss as gloss
    data = _gloss_inputs(tmp_path, monkeypatch, gloss)
    out = tmp_path / "gloss.json"
    out.write_text(json.dumps({"translator": {"provider": "openai", "model": "gpt-5"}, "strings": {"x1": "one"}}),
                   encoding="utf-8")
    monkeypatch.setattr(gloss, "build_provider", lambda *a, **k: pytest.fail("no call may start"))
    with pytest.raises(SystemExit) as stopped:
        gloss.main(["--data", str(data), "--output", str(out), "--model", "gpt-5-mini"])
    assert "gpt-5" in str(stopped.value) and json.loads(out.read_text())["translator"]["model"] == "gpt-5"
    # The same model resumes, and only the missing string is translated.
    provider = Translating()
    monkeypatch.setattr(gloss, "build_provider", lambda *a, **k: provider)
    assert gloss.main(["--data", str(data), "--output", str(out), "--model", "gpt-5"]) == 0
    result = json.loads(out.read_text(encoding="utf-8"))
    assert result["strings"] == {"x1": "one", "x2": "english 0"} and result["translator"]["model"] == "gpt-5"


# ---------------------------------------------------------------------------------------------- E3a

SENTINEL_PASSWORD = "R6SENTINELpassw0rd"
SENTINEL_QUERY = "R6SENTINELquerytoken"


def test_e3a_a_connection_error_names_the_sanitized_base_url_only():
    url = f"http://r6user:{SENTINEL_PASSWORD}@127.0.0.1:9/v1?token={SENTINEL_QUERY}"
    provider = lp.OpenAICompatibleProvider("", model="local-model", base_url=url)

    class Completions:
        def create(self, **kwargs):
            raise openai.APIConnectionError(message=f"Connection error to {url}",
                                            request=httpx.Request("POST", url))

    provider._client = type("Client", (), {"chat": type("Chat", (), {"completions": Completions()})()})()
    with pytest.raises(ProviderError) as caught:
        provider.complete("t", "s", {}, {"type": "object"})
    message = str(caught.value)
    assert "http://127.0.0.1:9/v1" in message
    for secret in (SENTINEL_PASSWORD, SENTINEL_QUERY, "r6user", url):
        assert secret not in message
    assert provider.describe()["base_url"] == "http://127.0.0.1:9/v1"
