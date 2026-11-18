"""R6 finding C8a: a route trial never states "each case ran one time, nothing was applied" when that is not
true, and compare never accepts an unusable trial or counts two errors as the same outcome.

The model end is the same stand-in server as in test_route_trial_offline.py (a test double, no model).
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))

from test_route_trial_offline import TAGS, fresh_route_state, route, route_trial, run_trial  # noqa: E402,F401

CLAIM = 'Each case ran one time. Nothing was approved and nothing was applied.'


def test_an_interrupted_trial_does_not_claim_that_every_case_ran(capsys, tmp_path, monkeypatch, route):
    run_one, seen = route_trial.run_case, []

    def interrupt_at_the_third(client, case, user, label, receipts):
        seen.append(case['case'])
        if len(seen) == 3:
            raise KeyboardInterrupt
        return run_one(client, case, user, label, receipts)

    monkeypatch.setattr(route_trial, 'run_case', interrupt_at_the_third)
    code, record, output, _, out = run_trial(capsys, tmp_path, '--scenario', 'tags', '--route-file', route)
    assert code == 1 and record['interrupted'] is True
    assert CLAIM not in record['statements'] and CLAIM not in output
    assert CLAIM not in (out / 'trial.md').read_text(encoding='utf-8')
    assert route_trial.UNUSABLE_STATEMENTS['interrupted'] in record['statements']


def test_a_changed_state_does_not_claim_that_nothing_was_applied(capsys, tmp_path, monkeypatch, route):
    read, reads = route_trial.applied_state, []

    def changed_after_the_request(client, headers, user):
        state = read(client, headers, user)
        reads.append(1)
        return {**state, 'groups': [{'label': 'applied by a defect'}]} if len(reads) % 2 == 0 else state

    monkeypatch.setattr(route_trial, 'applied_state', changed_after_the_request)
    code, record, output, _, _ = run_trial(capsys, tmp_path, '--scenario', 'hunger', '--route-file', route)
    assert code == 1 and record['totals']['state_changed'] is True
    assert CLAIM not in record['statements'] and route_trial.UNUSABLE_STATEMENTS['changed'] in record['statements']


def test_statements_of_a_clean_trial_are_unchanged():
    assert route_trial.trial_statements(False, True, False) == list(route_trial.STATEMENTS)
    assert CLAIM not in route_trial.trial_statements(False, False, False)


@pytest.mark.parametrize('damage', [
    {'interrupted': True}, {'totals': {'state_changed': True}}, {'totals': {'nothing_applied': False}},
    {'exit_code': 1}, {'interrupted': None}])
def test_compare_refuses_a_trial_that_cannot_be_used(capsys, tmp_path, route, damage):
    _, first, _, _, a = run_trial(capsys, tmp_path, '--scenario', 'tags', '--route-file', route, name='a')
    bad = dict(first)
    for key, value in damage.items():
        bad[key] = {**first[key], **value} if isinstance(value, dict) else value
    folder = tmp_path / 'bad'
    folder.mkdir()
    (folder / 'trial.json').write_text(json.dumps(bad), encoding='utf-8')
    assert route_trial.main(['compare', str(a), str(folder)]) == 1
    assert 'not compared' in capsys.readouterr().err
    assert route_trial.main(['compare', str(a), str(a)]) == 0


def test_two_errors_are_not_the_same_outcome(capsys, tmp_path, route):
    _, first, _, _, _ = run_trial(capsys, tmp_path, '--scenario', 'tags', '--route-file', route, name='a')
    left, right = json.loads(json.dumps(first)), json.loads(json.dumps(first))
    left['cases'][0]['outcome'] = right['cases'][0]['outcome'] = 'error'
    rows = {row[0]: row for row in route_trial.comparison(left, right)}
    assert rows['vocabulary'][3] == 'error in a trial'
    summary = route_trial.comparison_summary(route_trial.comparison(left, right))
    assert f'Same outcome: {len(TAGS) - 1}.' in summary and 'error in at least one trial' in summary
