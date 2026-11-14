"""The review window bounds the reviewer's decision, not provider latency.

Response doubles only: these are state-contract checks, not model evidence.
"""
import time

import pytest

from test_semantic_review import client, headers, apply, saved
from test_staged_induction import classify, model, preview


@pytest.fixture
def clock(monkeypatch):
    """A monotonic clock that a test can advance without sleeping."""
    real, offset = time.monotonic, {'seconds': 0.0}
    monkeypatch.setattr(time, 'monotonic', lambda: real() + offset['seconds'])
    return offset


def slow_provider(clock, seconds, stages=('membership', 'evidence_audit')):
    def hook(stage):
        if stage in stages:
            clock['seconds'] += seconds
    return hook


def test_timely_approval_survives_slow_membership_and_audit_calls(client, monkeypatch, clock):
    # Each provider call takes 200 s: together they exceed the 300 s review window.
    calls = model(monkeypatch, hook=slow_provider(clock, 200))
    h = headers(client)
    p = preview(client, h).json()
    assert p['definition_ready']
    m = classify(client, h, p).json()
    assert calls == ['definition', 'membership', 'evidence_audit']
    assert m.get('ready') is True and m['applied'] is False, m.get('reason')
    assert saved(client, h).json()['groups'] == []
    assert apply(client, h, m).json()['feed']['available_items'] == 34


def test_late_approval_is_still_rejected_before_any_model_call(client, monkeypatch, clock):
    calls = model(monkeypatch)
    h = headers(client)
    p = preview(client, h).json()
    clock['seconds'] += 301
    assert classify(client, h, p).status_code == 409
    assert calls == ['definition'] and saved(client, h).json()['groups'] == []


@pytest.mark.parametrize('stage', ['membership', 'evidence_audit'])
def test_state_change_during_a_slow_call_still_withholds_the_result(client, monkeypatch, clock, stage):
    h = headers(client)

    def hook(current):
        if current == stage:
            clock['seconds'] += 200
            client.post('/api/semantic/history/preview', headers=h, json={'user_id': 1, 'action': 'clear'})
    model(monkeypatch, hook=hook)
    p = preview(client, h).json()
    m = classify(client, h, p).json()
    assert not m.get('ready') and m['applied'] is False
    assert saved(client, h).json()['groups'] == []


def test_final_review_window_starts_when_the_membership_review_is_issued(client, monkeypatch, clock):
    model(monkeypatch, hook=slow_provider(clock, 200))
    h = headers(client)
    m = classify(client, h, preview(client, h).json()).json()
    assert m['ready']
    clock['seconds'] += 301
    assert apply(client, h, m).status_code == 409
    assert saved(client, h).json()['groups'] == []
