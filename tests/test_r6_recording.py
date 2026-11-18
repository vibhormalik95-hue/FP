"""Regression tests for r6 findings D5, D6a, D6b, D7a, D7b and D7c (tools/recording). Windows-only modules."""
import sys
from pathlib import Path

import pytest

pytest.importorskip("winsound")
pytest.importorskip("pyautogui")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "recording"))
import check_take  # noqa: E402
import demo_script  # noqa: E402
import record_demo  # noqa: E402


# D7a: ordered alignment, not word presence anywhere
def test_reordered_narration_is_not_aligned_although_every_word_is_present():
    timeline = [{"at": 0.0, "text": "alpha bravo charlie delta echo"}, {"at": 5.0, "text": "foxtrot golf hotel india juliet"}]
    swapped = [{"start": 0.0, "end": 4.0, "text": "foxtrot golf hotel india juliet"},
               {"start": 5.0, "end": 9.0, "text": "alpha bravo charlie delta echo"}]
    a = check_take.ordered_alignment(timeline, swapped)
    assert a["aligned"] < 2                         # one order only: one sentence cannot align


def test_numbers_are_normalised_on_both_sides():
    assert check_take.words("Claude Sonnet five point five 17 of 20") == check_take.words("Claude Sonnet 5.517 of 20")
    assert check_take.words("eighty-five percent") == check_take.words("85%")


def test_word_timestamps_give_sync_offsets():
    timeline = [{"at": 10.0, "text": "hello there world"}]
    tr = [{"start": 9.0, "end": 14.0, "text": "hello there world",
           "words": [{"w": " hello", "start": 10.4}, {"w": " there", "start": 10.8}, {"w": " world", "start": 11.1}]}]
    a = check_take.ordered_alignment(timeline, tr)
    assert a["timing"] == "word" and a["max_abs_offset_s"] == pytest.approx(0.4)


# D7c: unknown cost is never turned into a number
def test_unknown_cost_stays_unknown():
    assert demo_script.money(None) == "cost not known"
    assert demo_script.money(0) == "no API charge"
    assert "unknown cost" in demo_script.calls_line({"calls": [{"latency_s": 1, "cost_usd": 0.001}, {"latency_s": 1, "cost_usd": None}]})
    assert "cost not known" in demo_script.calls_line({"calls": [{"latency_s": 1, "cost_usd": None}]})


# D7b: the model line states only measured facts
def test_model_line_is_attributable():
    summary = {"summaries": {"a": {"nl_exact": 3, "nl_cases": 4, "nc_member_f1": 0.5},
                             "b": {"nl_exact": 2, "nl_cases": 4, "nc_member_f1": 0.9}}}
    assert "highest" in demo_script.model_line("b", "B", summary)
    assert "highest" not in demo_script.model_line("a", "A", summary)
    assert "no claim" in demo_script.model_line("z", "Z", summary)
    assert "best" not in demo_script.model_line("a", "A", summary) and "inexpensive" not in demo_script.model_line("a", "A", summary)


# D5: one key variable per provider
def test_provider_key_variables():
    assert record_demo.KEY_ENV == {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}


# D6a: the requested reading dwell is kept up to the silence limit
def test_hold_keeps_the_requested_dwell(monkeypatch):
    slept = []
    d = record_demo.Director.__new__(record_demo.Director)
    d.check_cjk = lambda *_: None
    d.wait_speech = lambda: None
    monkeypatch.setattr(record_demo.time, "sleep", slept.append)
    d.hold(3.0)
    d.hold(9.0)
    assert slept == [3.0, record_demo.Director.MAX_SILENT_HOLD] and record_demo.Director.MAX_SILENT_HOLD < 5


# D6b: an occupied port is detected before anything starts
def test_port_free_detects_a_listener():
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen()
        assert record_demo.port_free(s.getsockname()[1]) is False
