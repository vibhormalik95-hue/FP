"""Protect the supplemental audit's estimand, NI decisions, and frozen artifacts."""
from __future__ import annotations

import copy
import math

import pytest

from scripts.analyze_revision import aggregate_rows, analyze_backend, ni_interpretation, stable_write


def fixture():
    data = {"users": [{"user_id": u} for u in range(40)],
            "items": [{"item_id": i, "categories": ["a" if i < 2 else "b"]} for i in range(4)]}
    rows = []
    for user in range(40):
        for seed in (1, 2):
            for operation in ("boost", "mute"):
                for condition in "ABCDE":
                    reference = condition in "AB"
                    hit = int(reference and user == 0)
                    rows.append({"user_id": user, "seed": seed, "condition": condition, "operation": operation,
                                 "request_id": f"u{user}-{operation}", "category": "a", "parser_backend": "rule",
                                 "hr1": hit, "ndcg_at_k": hit, "fill_rate": 1,
                                 "target_proportion": int(reference), "top_k": [0, 1] if reference else [2, 3]})
    return rows, data


def test_total_baseline_loss_passes_absolute_margin_but_fails_relative():
    rows, data = fixture()
    result = analyze_backend(rows, data, n_bootstrap=1000)
    ni = result["hr1_noninferiority_sensitivity"][0]
    assert ni["n_users"] == 40  # Not 160 request-seed observations.
    assert ni["baseline_hr1"] == pytest.approx(.025)
    assert ni["mean_difference"] == pytest.approx(-.025)
    assert ni["informative_users_nonzero_paired_difference"] == 1
    absolute = ni["absolute_10_percentage_points"]
    relative = ni["relative_10_percent_of_observed_reference"]
    assert absolute["statistical_criterion_passed"]
    assert absolute["margin_exceeds_baseline"]
    assert not absolute["informative_statistical_support"]
    assert relative["margin_absolute"] == pytest.approx(.0025)
    assert not relative["statistical_criterion_passed"]
    assert not relative["informative_statistical_support"]
    ndcg = result["boost_ndcg_tradeoff"]
    assert ndcg["mean_difference"] == pytest.approx(-.025)
    assert ndcg["relative_change"] == -1
    assert ndcg["informative_users_nonzero_paired_difference"] == 1


def test_relative_margin_uses_same_both_operation_estimand_as_difference():
    rows, data = fixture()
    # Two extra A/B hits in mute only; operation means must both contribute.
    for row in rows:
        if row["condition"] in "AB" and row["operation"] == "mute" and row["user_id"] in (1, 2):
            row["hr1"] = 1
    ni = analyze_backend(rows, data, n_bootstrap=100)["hr1_noninferiority_sensitivity"][0]
    assert ni["baseline_hr1_by_operation"] == pytest.approx({"boost": .025, "mute": .075})
    assert ni["baseline_hr1"] == pytest.approx(.05)
    assert ni["relative_10_percent_of_observed_reference"]["margin_absolute"] == pytest.approx(.005)


def test_decision_boundary_and_zero_baseline_remain_noninformative():
    boundary = {"n_users": 40, "simultaneous_lower": -.1}
    assert not ni_interpretation(boundary, .5, .1, 5)["statistical_criterion_passed"]
    zero = ni_interpretation({"n_users": 40, "simultaneous_lower": 0}, 0, .1, 0)
    assert zero["statistical_criterion_passed"]
    assert not zero["informative_statistical_support"]
    assert not ni_interpretation({"n_users": 29, "simultaneous_lower": 0}, .5, .1, 5)["statistical_criterion_passed"]
    for invalid in (-.1, math.nan, math.inf, 2):
        with pytest.raises(ValueError):
            ni_interpretation(boundary, .5, invalid, 5)


def test_missing_pairs_duplicates_and_changed_request_identity_are_rejected():
    rows, _ = fixture()
    with pytest.raises(ValueError, match="Incomplete"):
        aggregate_rows(rows[1:])
    with pytest.raises(ValueError, match="Duplicate"):
        aggregate_rows(rows + rows[:1])
    changed = copy.deepcopy(rows)
    changed[0]["category"] = "b"
    with pytest.raises(ValueError, match="identity"):
        aggregate_rows(changed)
    changed = copy.deepcopy(rows)
    changed[0]["hr1"] = .5
    with pytest.raises(ValueError, match="binary"):
        aggregate_rows(changed)


def test_saturation_validates_saved_top_k_against_catalogue():
    rows, data = fixture()
    result = analyze_backend(rows, data, n_bootstrap=100)["policy_saturation"]
    assert result["assigned_category_min_items"] == 2
    assert result["boost_users_saturated_tcp_one_all_seeds"]["A"] == 40
    assert result["boost_users_saturated_tcp_one_all_seeds"]["C"] == 0
    assert result["item_only_boost_max_tcp_change_from_uncontrolled"] == .5
    rows[0]["top_k"] = [2, 3]
    with pytest.raises(ValueError, match="Saved TCP"):
        analyze_backend(rows, data, n_bootstrap=100)


def test_versioned_artifacts_cannot_overwrite_a_different_record(tmp_path):
    path = tmp_path / "analysis-v1.json"
    stable_write(path, b"original")
    stable_write(path, b"original")
    with pytest.raises(ValueError, match="increment --version"):
        stable_write(path, b"changed")
    assert path.read_bytes() == b"original"
