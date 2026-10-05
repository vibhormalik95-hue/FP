from __future__ import annotations

import copy
import json
from unittest.mock import patch

import pytest

from feedctrl.evaluation import (analyze_rows, bh_adjust, generate_requests, load_metric_rows,
                                paired_bootstrap, paired_randomization_p, paired_wilcoxon_p,
                                ranking_metrics, run_evaluation)


def dataset():
    return {"metadata": {"status": "test_fixture"},
            "items": [{"item_id": i, "categories": ["category_1"] if i < 5 else ["category_2", "category_3"]} for i in range(12)],
            "users": [{"user_id": u, "train": [0, 1, 6], "request_history": [7, 2], "test": [u + 3, 4]} for u in range(3)]}


class FrozenModel:
    def __init__(self):
        self.histories = []

    def score(self, history, item_ids):
        self.histories.append(list(history))
        return [float(12 - i) for i in item_ids]


def test_requests_do_not_access_test_or_mutated_labels():
    first = dataset()
    second = copy.deepcopy(first)
    for user in second["users"]:
        del user["test"]
    assert generate_requests(first) == generate_requests(second)
    for request in generate_requests(first):
        user = first["users"][request["user_id"]]
        assert request["exemplar_item"] in user["train"] + user["request_history"]


def test_metrics_multilabel_fixed_denominator_and_fill_gate():
    categories = {1: ["a", "b", "a"], 2: ["b"], 3: ["a"]}
    metrics = ranking_metrics([1, 2, 3], "a", categories, next_item=1, k=4, operation="boost")
    assert metrics["target_proportion"] == .5
    assert metrics["conditional_exposure"] == pytest.approx(2 / 3)
    assert metrics["fill_rate"] == .75
    assert metrics["hr1"] == 1
    assert metrics["ndcg_at_k"] == 1
    assert metrics["compliant_filled_success"] == 0
    empty = ranking_metrics([], "a", categories, next_item=1, k=4, operation="mute")
    assert empty["target_proportion"] == 0
    assert empty["conditional_exposure"] is None
    assert empty["fill_rate"] == empty["compliant_filled_success"] == 0
    with pytest.raises(ValueError):
        ranking_metrics([1, 1], "a", categories, 1)


def test_bh_hand_calculation_and_noninferiority_boundary():
    assert bh_adjust([.01, .04, .03, .5]) == pytest.approx([.04, .0533333333, .0533333333, .5])
    assert paired_randomization_p([1, 1, 1]) == pytest.approx(.25)
    assert paired_wilcoxon_p([0, 0, 0]) == 1
    boundary = paired_bootstrap([-.1] * 40, n_resamples=100)
    assert not boundary["ni_exploratory_supported"]
    supported = paired_bootstrap([0.0] * 40, n_resamples=100)
    assert supported["ni_exploratory_supported"]
    assert supported["warning"] == "degenerate_empirical_distribution"
    values = [-1, 0, 0, 0, 0, 0, 0, 0, 1, 1] * 4
    stats = paired_bootstrap(values, n_resamples=1000)
    assert stats["simultaneous_lower"] <= stats["one_sided_lower95"]


def test_end_to_end_ranks_invariant_to_test_changes(tmp_path):
    data = dataset()
    model = FrozenModel()
    result = run_evaluation(data, model, tmp_path / "a", n_bootstrap=100)
    assert result["all_b_rank_invariant"]
    assert result["c_d_e_equal_request_fraction"] == 1
    assert result["parse_operational_errors"] == 0
    assert result["evidence_status"] == "rule_diagnostic"
    assert len(model.histories) == len(data["users"])
    assert all(h == [0, 1, 6, 7, 2] for h in model.histories)
    changed = copy.deepcopy(data)
    for user in changed["users"]:
        user["test"] = [11, 10, 9]
    run_evaluation(changed, FrozenModel(), tmp_path / "b", n_bootstrap=100)
    first = json.loads((tmp_path / "a" / "requests.json").read_text())
    second = json.loads((tmp_path / "b" / "requests.json").read_text())
    assert first == second
    rows = load_metric_rows([tmp_path / "a" / "request_metrics.csv"])
    for row in rows:
        if row["condition"] in ("C", "D", "E") and row["operation"] == "mute":
            assert float(row["target_proportion"]) == 0


def test_failures_are_retained_without_rule_fallback(tmp_path):
    with patch("feedctrl.controls.parse_control", side_effect=ConnectionError("offline")), patch("feedctrl.controls.parse_profile", side_effect=ConnectionError("offline")):
        summary = run_evaluation(dataset(), FrozenModel(), tmp_path, parser_backend="ollama", n_bootstrap=100)
    assert summary["evidence_status"] == "unavailable"
    assert summary["parse_operational_errors"] == 12
    assert summary["parse_clarifications"] == 0
    assert len(load_metric_rows([tmp_path / "request_metrics.csv"])) == 30


def test_failed_free_text_keeps_valid_profile_in_e(tmp_path):
    with patch("feedctrl.controls.parse_control", side_effect=ConnectionError("offline")):
        run_evaluation(dataset(), FrozenModel(), tmp_path, n_bootstrap=100)
    rows = load_metric_rows([tmp_path / "request_metrics.csv"])
    by_request = {}
    for row in rows:
        by_request.setdefault(row["request_id"], {})[row["condition"]] = row
    assert all(r["D"]["ranking_sha256"] == r["E"]["ranking_sha256"] for r in by_request.values())


def test_user_clusters_and_pairing_not_request_seed_pseudoreplication(tmp_path):
    run_evaluation(dataset(), FrozenModel(), tmp_path / "a", seed=1, n_bootstrap=100)
    run_evaluation(dataset(), FrozenModel(), tmp_path / "b", seed=2, n_bootstrap=100)
    rows = load_metric_rows([tmp_path / "a" / "request_metrics.csv", tmp_path / "b" / "request_metrics.csv"])
    combined = analyze_rows(rows, n_bootstrap=100)
    assert combined["user_count"] == 3
    assert combined["seed_count"] == 2
    assert all(c["n_users"] == 3 for c in combined["primary_contrasts"])
    assert len(combined["primary_contrasts"]) == 6
    with pytest.raises(ValueError, match="Incomplete"):
        analyze_rows(rows[1:], n_bootstrap=100)
    with pytest.raises(ValueError, match="Duplicate"):
        analyze_rows(rows + rows[:1], n_bootstrap=100)


def test_wrong_training_cohort_or_seed_rejected_before_scores(tmp_path):
    model = FrozenModel()
    model.metadata = {"train_sequence_sha256": "stale256-user-checkpoint"}
    with pytest.raises(ValueError, match="different data/user cohort"):
        run_evaluation(dataset(), model, tmp_path, n_bootstrap=100)
    assert model.histories == []
    model.metadata = {"seed": 999}
    with pytest.raises(ValueError, match="does not match model"):
        run_evaluation(dataset(), model, tmp_path, seed=42, n_bootstrap=100)
    assert model.histories == []
