"""Check the supplemental analysis against analytic values and leakage invariants."""
from copy import deepcopy
import math

import pytest

from scripts.benchmark_revision import assess, popularity_scores, rank_candidates, uniform_expectation


def test_baseline_ranks_ignore_test_labels_and_catalogue_order():
    data = {'items': [{'item_id': i} for i in (30, 10, 20)],
            'users': [{'user_id': 1, 'train': [10, 20], 'request_history': [30, 20], 'test': [10]}]}
    ids = [i['item_id'] for i in data['items']]
    expected = rank_candidates(ids, popularity_scores(data, 'request_history', ids))
    changed = deepcopy(data)
    changed['users'][0]['test'] = [30]
    reordered = list(reversed(ids))
    assert rank_candidates(reordered, popularity_scores(changed, 'request_history', reordered)) == expected == [20, 30, 10]
    with pytest.raises(ValueError, match='pre-test'):
        popularity_scores(data, 'test', ids)


def test_single_target_ndcg_and_uniform_expectation_by_enumeration():
    data = {'items': [{'item_id': i} for i in range(10)],
            'users': [{'user_id': i, 'train': [], 'request_history': [], 'test': [i]} for i in range(10)]}
    observed = assess(data, lambda history, ids: [-i for i in ids])
    expected = uniform_expectation(10)
    assert observed['hr1'] == expected['hr1'] == .1
    assert observed['hr10'] == expected['hr10'] == 1
    assert observed['ndcg10'] == pytest.approx(expected['ndcg10'])
    assert expected['ndcg10'] == pytest.approx(sum(1 / math.log2(i + 2) for i in range(10)) / 10)
