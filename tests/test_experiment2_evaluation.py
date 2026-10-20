"""Synthetic Experiment 2 checks; no reserved language cases are read here."""
from __future__ import annotations

import copy
import csv
import json
from pathlib import Path

import pytest

from feedctrl import experiment2_evaluation as e2


def directive(operation="boost", category="category_1", strength="slight", *, floor=0,
              condition_category=None):
    return {"operation": operation, "category": category, "strength": strength,
            "floor": floor, "condition_category": condition_category}


def command(*directives):
    return {"operation": "set", "directives": list(directives)}


def catalogue():
    return {**{i: ["category_1"] for i in range(10)},
            **{i: ["category_2"] for i in range(10, 20)},
            **{i: ["category_1", "category_2"] for i in range(20, 30)},
            **{i: ["category_3"] for i in range(30, 50)}}


def ranking(x=0, y=0, both=0, size=10):
    return (list(range(x)) + list(range(10, 10 + y)) +
            list(range(20, 20 + both)) + list(range(30, 30 + size - x - y - both)))


def metrics(gold, after, before):
    return e2.evaluate_ranking(after, before, gold, catalogue(), next_item=49)


class ForbiddenTestLabels(dict):
    """Fail even if assignment reads labels but happens not to use their values."""

    def __getitem__(self, key):
        if key == "test":
            raise AssertionError("case assignment accessed held-out outcomes")
        return super().__getitem__(key)

    def get(self, key, default=None):
        if key == "test":
            raise AssertionError("case assignment accessed held-out outcomes")
        return super().get(key, default)


def synthetic_data():
    return {"metadata": {"status": "synthetic_unit_test"},
            "items": [{"item_id": i, "categories": cats} for i, cats in catalogue().items()],
            "users": [{"user_id": u, "train": [0, 10, 20],
                       "request_history": [1, 11], "test": [49 - u]} for u in (0, 1)]}


def cases():
    return [
        {"id": "synthetic-compound", "class": "compound",
         "text": "Boost category_1 and reduce category_2",
         "gold": command(directive(strength="moderate"),
                         directive("reduce", "category_2", "moderate"))},
        {"id": "synthetic-slight", "class": "graded",
         "text": "Slightly boost category_1", "gold": command(directive())},
    ]


def test_assignment_is_deterministic_and_does_not_access_test_labels():
    data = synthetic_data()
    expected = e2.assign_requests(data, cases(), request_seed=2026)
    changed = copy.deepcopy(data)
    changed["users"] = [ForbiddenTestLabels(user) for user in reversed(changed["users"])]
    for user in changed["users"]:
        user["test"] = [987654321]
    assert e2.assign_requests(changed, cases(), request_seed=2026) == expected
    assert e2.assign_requests(data, cases(), request_seed=2026) == expected
    assert e2.assign_requests(data, list(reversed(cases())), request_seed=2026) == expected
    requests, _ = expected
    assert requests
    assert len({r["request_id"] for r in requests}) == len(requests)
    for request in requests:
        user = next(u for u in data["users"] if u["user_id"] == request["user_id"])
        assert request["exemplar_item"] in user["train"] + user["request_history"]


def test_assignment_records_ineligible_user_classes_instead_of_inventing_support():
    fixture = cases() + [{"id": "synthetic-unseen-condition", "class": "conditional",
                         "text": "Boost category_1 only when also category_3",
                         "gold": command(directive(strength="moderate", condition_category="category_3"))}]
    requests, exclusions = e2.assign_requests(synthetic_data(), fixture)
    assert all(r["class"] != "conditional" for r in requests)
    assert {(r["user_id"], r["class"]) for r in exclusions} == {(0, "conditional"), (1, "conditional")}


@pytest.mark.parametrize("count,expected", [(1, False), (2, True), (4, True), (5, False)])
def test_slight_boost_band_has_inclusive_two_and_four_boundaries(count, expected):
    result = metrics(command(directive()), ranking(x=count), ranking(x=0))
    assert bool(result["full"])
    assert bool(result["band_satisfied"]) is expected
    assert bool(result["induced_success"]) is expected


def test_band_attainment_without_strict_movement_is_not_induced_success():
    gold = command(directive())
    result = metrics(gold, ranking(x=2), ranking(x=2))
    assert result["band_satisfied"]
    assert result["baseline_already_satisfies"]
    assert not result["intended_movement"]
    assert not result["induced_success"]
    changed = metrics(gold, ranking(x=3), ranking(x=2))
    assert changed["baseline_already_satisfies"]
    assert changed["intended_movement"]
    assert changed["induced_success"]


def test_compound_success_requires_both_bands_and_both_movements():
    gold = command(directive(strength="moderate"),
                   directive("reduce", "category_2", "strong"))
    before = ranking(x=1, y=3)
    assert metrics(gold, ranking(x=2, y=1), before)["induced_success"]
    assert not metrics(gold, ranking(x=1, y=1), before)["band_satisfied"]
    assert not metrics(gold, ranking(x=2, y=2), before)["band_satisfied"]
    # The result is in-band, but the boost target did not move.
    result = metrics(gold, ranking(x=2, y=1), ranking(x=2, y=3))
    assert result["band_satisfied"]
    assert not result["intended_movement"]
    assert not result["induced_success"]


@pytest.mark.parametrize("count,expected", [(0, True), (1, True), (2, False)])
def test_strong_reduction_band_is_at_most_one(count, expected):
    result = metrics(command(directive("reduce", strength="strong")),
                     ranking(x=count), ranking(x=4))
    assert bool(result["band_satisfied"]) is expected


def test_none_exclusion_is_distinct_from_reduction():
    gold = command(directive("exclude", strength="none"))
    assert metrics(gold, ranking(), ranking(x=2))["induced_success"]
    assert not metrics(gold, ranking(x=1), ranking(x=2))["band_satisfied"]
    assert not metrics(gold, ranking(), ranking())["induced_success"]


@pytest.mark.parametrize("count,band,violation", [(0, False, True), (1, True, False),
                                                (2, True, False), (3, False, False)])
def test_nonzero_floor_band_and_violation(count, band, violation):
    result = metrics(command(directive("reduce", floor=1)), ranking(x=count), ranking(x=4))
    assert bool(result["band_satisfied"]) is band
    assert bool(result["floor_violation"]) is violation


def test_conditional_control_checks_intersection_and_leakage_against_baseline():
    gold = command(directive(strength="moderate", condition_category="category_2"))
    before = ranking(x=1, both=1)
    assert metrics(gold, ranking(x=1, both=2), before)["induced_success"]
    leaked = metrics(gold, ranking(x=2, both=2), before)
    assert not leaked["band_satisfied"]
    assert not leaked["induced_success"]
    unchanged = metrics(gold, ranking(x=1, both=2), ranking(x=1, both=2))
    assert unchanged["band_satisfied"]
    assert not unchanged["intended_movement"]


def test_conditional_movement_penalizes_extra_rank_exposure_without_count_leakage():
    gold = command(directive(strength="moderate", condition_category="category_2"))
    before = list(range(30, 37)) + [0, 20, 21]
    after = [0, 20, 21] + list(range(30, 37))
    result = metrics(gold, after, before)
    assert result["band_satisfied"]  # Counts stayed at two intersection and one X-only.
    assert result["intended_movement"] < 0  # The leakage penalty exceeds the gain.
    assert not result["induced_success"]


def test_floor_violation_zeroes_movement_credit():
    result = metrics(command(directive("reduce", floor=1)), ranking(), ranking(x=4))
    assert result["floor_violation"]
    assert result["intended_movement"] == 0
    assert not result["induced_success"]


def test_underfilled_feed_cannot_pass_even_when_counts_are_in_band():
    gold = command(directive())
    result = metrics(gold, ranking(x=2, size=9), ranking(x=0))
    assert not result["full"]
    assert not result["induced_success"]
    empty = metrics(command(directive("exclude", strength="none")), [], ranking(x=2))
    assert not empty["full"]
    assert not empty["induced_success"]


def test_metrics_use_saved_rank_order_for_quality_and_reject_invalid_items():
    result = e2.evaluate_ranking(ranking(x=2), ranking(), command(directive()),
                                 catalogue(), next_item=1)
    assert result["hr1"] == 0
    assert result["ndcg_at_10"] == pytest.approx(1 / 1.584962500721156)
    with pytest.raises(ValueError):
        metrics(command(directive()), [0, 0] + ranking(size=8), ranking())
    with pytest.raises(ValueError):
        metrics(command(directive()), [9999] + ranking(size=9), ranking())


def test_parser_errors_stay_in_accuracy_denominator_and_do_not_count_as_clarify():
    fixture = cases()
    outcomes = [
        {"id": fixture[0]["id"], "backend": "rule_compound", "command": fixture[0]["gold"], "error": None},
        {"id": fixture[1]["id"], "backend": "rule_compound", "command": None, "error": "offline"},
        {"id": fixture[0]["id"], "backend": "ollama_compound", "command": fixture[0]["gold"], "error": None},
        {"id": fixture[1]["id"], "backend": "ollama_compound", "command": fixture[1]["gold"], "error": None},
    ]
    result = e2.summarize_parser(outcomes, fixture)["rule_compound"]
    assert result["total"] == 2
    assert result["correct"] == 1
    assert result["accuracy"] == .5
    assert result["operational_errors"] == 1
    assert result["clarifications"] == 0
    assert result["by_class"]["graded"]["total"] == 1
    assert result["by_class"]["graded"]["accuracy"] == 0
    with pytest.raises(ValueError, match="every case"):
        e2.summarize_parser(outcomes[:-1], fixture)
    with pytest.raises(ValueError, match="every case"):
        e2.summarize_parser(outcomes + outcomes[:1], fixture)


def test_one_sided_signed_rank_direction_and_zero_differences():
    assert e2.paired_wilcoxon_greater([0, 0, 0]) == 1
    assert e2.paired_wilcoxon_greater([1] * 20) < .001
    assert e2.paired_wilcoxon_greater([-1] * 20) > .99


def analysis_rows():
    rows = []
    for user in range(3):
        for seed in (42, 43, 44):
            for label in ("compound", "graded", "floor", "conditional"):
                for condition in ("A", "rule", "llm", "recency"):
                    success = int(condition == "llm" and user == 0)
                    rows.append({"seed": seed, "request_id": f"u{user}-{label}",
                                 "user_id": user, "class": label, "condition": condition,
                                 "induced_success": success, "intended_movement": .3 * success,
                                 "hr1": 0, "ndcg_at_10": 0})
    return rows


def test_analysis_has_eleven_joint_tests_and_users_are_the_unit():
    result = e2.analyze_rows(analysis_rows(), n_bootstrap=100)
    tests = result["tests"]
    assert result["user_count"] == 3
    assert len(tests) == 11
    assert sum(t["hypothesis"] == "H1" for t in tests) == 10
    assert sum(t["hypothesis"] == "H2" for t in tests) == 1
    assert all(t["n_users"] == 3 and t["bh_family_size"] == 11 for t in tests)
    assert all(t["mean_difference"] == pytest.approx(1 / 3)
               for t in tests if t["hypothesis"] == "H1")
    assert next(t for t in tests if t["hypothesis"] == "H2")["mean_difference"] == pytest.approx(.1)
    assert {(t["class"], t["reference"]) for t in tests if t["hypothesis"] == "H1"} == {
        (label, reference) for label in ("compound", "graded", "floor", "conditional", "pooled")
        for reference in ("A", "rule")}


def test_bh_correction_uses_one_family_of_eleven(monkeypatch):
    # Increasing adjusted values are hand-calculable: p_i * 11 / rank_i.
    supplied = [.001, .004, .009, .016, .025, .036, .049, .064, .081, .1, .121]
    calls = iter(supplied)
    monkeypatch.setattr(e2, "paired_wilcoxon_greater", lambda _: next(calls))
    tests = e2.analyze_rows(analysis_rows(), n_bootstrap=100)["tests"]
    assert [t["p_one_sided"] for t in tests] == supplied
    assert [t["q_bh"] for t in tests] == pytest.approx([.011 * i for i in range(1, 12)])


def test_analysis_rejects_missing_conditions_seeds_and_changed_request_identity():
    rows = analysis_rows()
    with pytest.raises(ValueError, match="all four conditions and three seeds"):
        e2.analyze_rows(rows[1:], n_bootstrap=100)
    with pytest.raises(ValueError, match="Duplicate"):
        e2.analyze_rows(rows + rows[:1], n_bootstrap=100)
    changed = copy.deepcopy(rows)
    changed[0]["user_id"] = 999
    with pytest.raises(ValueError, match="stable identity"):
        e2.analyze_rows(changed, n_bootstrap=100)


def test_ranking_replay_is_invariant_to_heldout_labels_and_keeps_failed_requests(monkeypatch):
    data, fixture = synthetic_data(), cases()
    outcomes = [{"id": row["id"], "backend": backend, "command": row["gold"],
                 "error": "synthetic outage" if backend == "ollama_compound" and index == 0 else None}
                for backend in ("rule_compound", "ollama_compound") for index, row in enumerate(fixture)]

    class FrozenModel:
        def __init__(self, seed):
            self.metadata = {"seed": seed, "train_sequence_sha256": e2.fingerprint(
                [{"user_id": u["user_id"], "train": u["train"]} for u in data["users"]])}
            self.histories = []

        def score(self, history, item_ids):
            self.histories.append(list(history))
            return [float(50 - i) for i in item_ids]

    def forbidden_parser(*args, **kwargs):
        raise AssertionError("ranking replay must use preserved parser outcomes")

    monkeypatch.setattr("feedctrl.experiment2_controls.parse_control", forbidden_parser)
    models = {seed: FrozenModel(seed) for seed in (42, 43, 44)}
    first, summary, requests, _ = e2.run_rankings(data, fixture, outcomes, models, n_bootstrap=100)
    assert len(first) == len(requests) * 3 * 4
    assert sum(r["parser_error"] for r in first) == 6
    assert all(len(m.histories) == 2 for m in models.values())
    assert all(h == [0, 10, 20, 1, 11] for m in models.values() for h in m.histories)
    assert summary["request_count"] == 4
    changed = copy.deepcopy(data)
    for user in changed["users"]:
        user["test"] = [0]
    second, _, repeated_requests, _ = e2.run_rankings(changed, fixture, outcomes, models, n_bootstrap=100)
    assert repeated_requests == requests
    keys = ("seed", "request_id", "condition", "score_sha256", "ranking_sha256", "top_10", "induced_success")
    assert [{k: r[k] for k in keys} for r in first] == [{k: r[k] for k in keys} for r in second]


def dump_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")



def supported_class_gold(label):
    return {"compound": command(directive(strength="moderate"), directive("reduce", "category_2", "moderate")),
            "graded": command(directive()),
            "floor": command(directive("reduce", strength="moderate", floor=1)),
            "conditional": command(directive(strength="moderate", condition_category="category_2"))}[label]

def student_gate_fixture(tmp_path):
    """All names, annotations and receipts below are fabricated unit-test data."""
    from unittest.mock import patch
    fixture_dir = tmp_path / "synthetic-human-gate-fixture"
    fixture_dir.mkdir()
    ids = [f"synthetic-{i:03d}" for i in range(100)]
    gold = command(directive())
    manifest, id_map = fixture_dir / "manifest.json", fixture_dir / "id-map.json"
    annotations, adjudication = fixture_dir / "student.csv", fixture_dir / "adjudication.json"
    receipt, basic_receipt = fixture_dir / "receipt.json", fixture_dir / "student-only-receipt.json"
    sealed, dev, parser = fixture_dir / "test.sealed", fixture_dir / "dev.jsonl", fixture_dir / "parser.py"
    commitment = fixture_dir / "parser-commitment.json"
    original_cases = [{"id": case_id, "class": e2.CLASSES[i % 4], "text": f"Synthetic unit-test utterance {i}", "gold": supported_class_gold(e2.CLASSES[i % 4])} for i, case_id in enumerate(ids)]
    sealed.write_text("\n".join(json.dumps(row) for row in original_cases))
    dev.write_text("synthetic development bytes")
    parser.write_text("synthetic parser implementation")
    source_hash = e2.sha256_file(sealed)
    dump_json(manifest, {"case_ids": ids, "cases": [{"id": r["id"], "class": r["class"]} for r in original_cases], "sealed_sha256": source_hash})
    dump_json(id_map, {f"blind-{i:03d}": case_id for i, case_id in enumerate(ids)})
    with patch.object(e2, "utc_now", return_value="2026-01-01T00:00:00+00:00"):
        dump_json(commitment, e2.make_parser_commitment(parser, dev, sealed, ["category_1", "category_2"]))
    with annotations.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["annotation_id", "text", "operation", "directives_json", "annotator", "timestamp_utc"])
        writer.writeheader()
        for i in range(100):
            gold = original_cases[i]["gold"]
            writer.writerow({"annotation_id": f"blind-{i:03d}", "text": f"Synthetic unit-test utterance {i}",
                             "operation": gold["operation"], "directives_json": json.dumps(gold["directives"]),
                             "annotator": "Alex Morgan (synthetic fixture)", "timestamp_utc": "2026-01-02T03:04:05+00:00"})
    basic = {"annotator_identity": "Alex Morgan (synthetic fixture)", "annotated_utc": "2026-01-02T03:04:05+00:00",
             "student_attestation": True, "independent_annotation": True, "no_model_outputs_seen": True,
             "student_annotations_sha256": e2.sha256_file(annotations), "source_test_sha256": source_hash, "case_ids": ids}
    dump_json(basic_receipt, basic)
    comparison = fixture_dir / "comparison"
    with patch.object(e2, "utc_now", return_value="2026-01-02T03:30:00+00:00"):
        e2.compare_annotations(annotations, basic_receipt, manifest, id_map, sealed, commitment, parser, dev,
                               ["category_1", "category_2"], comparison)
    agreement = comparison / "agreement-before-adjudication.json"
    final = [{"id": row["id"], "gold": row["gold"], "reason": "Synthetic fixture agreement"} for row in original_cases]
    dump_json(adjudication, {"adjudicator_identity": "Sam Taylor (synthetic fixture)",
                            "completed_utc": "2026-01-02T04:05:06+00:00", "disagreements_resolved": True,
                            "blind_before_model_outputs": True, "original_annotations_preserved": True,
                            "source_test_sha256": source_hash, "student_annotations_sha256": e2.sha256_file(annotations), "final_gold": final})
    dump_json(receipt, {**basic, "adjudication_sha256": e2.sha256_file(adjudication),
                       "agreement_record_sha256": e2.sha256_file(agreement), "student_only_receipt_sha256": e2.sha256_file(basic_receipt),
                       "final_gold_sha256": e2.fingerprint([{"id": r["id"], "gold": r["gold"]} for r in final])})
    return {"annotations_path": annotations, "receipt_path": receipt, "adjudication_path": adjudication,
            "manifest_path": manifest, "id_map_path": id_map, "sealed_sha256": source_hash, "agreement_path": agreement}


def test_student_gate_requires_complete_preserved_independent_human_evidence(tmp_path):
    fixture = student_gate_fixture(tmp_path)
    gate = e2.validate_student_gate(**fixture)
    assert gate["status"] == "verified_human_attestations"
    assert len(gate["student_annotations"]) == len(gate["final_gold"]) == 100
    fixture["annotations_path"].unlink()
    with pytest.raises(ValueError, match="completed independent student annotations"):
        e2.validate_student_gate(**fixture)


@pytest.mark.parametrize("field,value", [("annotator_identity", "student"),
                                         ("independent_annotation", False),
                                         ("no_model_outputs_seen", False),
                                         ("student_annotations_sha256", "b" * 64),
                                         ("source_test_sha256", "b" * 64),
                                         ("case_ids", [])])
def test_student_gate_rejects_missing_attestations_placeholders_and_hashes(tmp_path, field, value):
    fixture = student_gate_fixture(tmp_path)
    receipt = json.loads(fixture["receipt_path"].read_text())
    receipt[field] = value
    dump_json(fixture["receipt_path"], receipt)
    with pytest.raises(ValueError):
        e2.validate_student_gate(**fixture)


def test_student_gate_rejects_invalid_annotation_command_even_with_matching_hashes(tmp_path):
    fixture = student_gate_fixture(tmp_path)
    annotation_path = fixture["annotations_path"]
    annotation_path.write_text(annotation_path.read_text().replace(",set,", ",invented,", 1))
    adjudication = json.loads(fixture["adjudication_path"].read_text())
    adjudication["student_annotations_sha256"] = e2.sha256_file(annotation_path)
    dump_json(fixture["adjudication_path"], adjudication)
    receipt = json.loads(fixture["receipt_path"].read_text())
    receipt["student_annotations_sha256"] = e2.sha256_file(annotation_path)
    receipt["adjudication_sha256"] = e2.sha256_file(fixture["adjudication_path"])
    dump_json(fixture["receipt_path"], receipt)
    with pytest.raises(ValueError):
        e2.validate_student_gate(**fixture)


def freeze_fixture(tmp_path):
    fixture = student_gate_fixture(tmp_path)
    gate = e2.validate_student_gate(**fixture)
    base = fixture["annotations_path"].parent
    artifacts = {}
    original_paths = {"parser_commitment": base / "parser-commitment.json", "parser_module": base / "parser.py",
                      "test_commitment": base / "test.sealed", "dev": base / "dev.jsonl", "agreement_record": fixture["agreement_path"],
                      "annotation_commit_record": fixture["agreement_path"].with_name("annotation-commit.json"),
                      "student_annotations": fixture["annotations_path"], "student_receipt": fixture["receipt_path"],
                      "adjudication": fixture["adjudication_path"], "language_manifest": fixture["manifest_path"], "annotation_id_map": fixture["id_map_path"]}
    for label in e2.REQUIRED_ARTIFACTS:
        path = original_paths.get(label, tmp_path / f"synthetic-{label}.txt")
        if label not in original_paths:
            path.write_text(f"synthetic fixture for {label}")
        artifacts[label] = path
    options = {"model": "synthetic-fixture-model", "timeout": 1}
    categories = ["category_1", "category_2"]
    receipt = e2.make_freeze_receipt(artifacts, categories, gate, options, {"model": "synthetic-fixture-model", "digest": "fixture"})
    return artifacts, categories, options, receipt, gate


def test_freeze_requires_student_gate_and_all_artifacts(tmp_path):
    artifacts, categories, options, _, gate = freeze_fixture(tmp_path)
    with pytest.raises(ValueError, match="independent student annotation"):
        e2.make_freeze_receipt(artifacts, categories, {}, options, {})
    with pytest.raises(ValueError, match="artifact labels"):
        e2.make_freeze_receipt({k: v for k, v in artifacts.items() if k != "dev"},
                               categories, gate, options, {})


def test_freeze_detects_changed_inputs_and_parser_options(tmp_path):
    artifacts, categories, options, receipt, _ = freeze_fixture(tmp_path)
    e2.verify_freeze_receipt(receipt, artifacts, categories, options)
    with pytest.raises(ValueError, match="parser options"):
        e2.verify_freeze_receipt(receipt, artifacts, categories, {**options, "model": "other"})
    artifacts["protocol"].write_text("changed synthetic protocol")
    with pytest.raises(ValueError, match="Frozen artifact changed: protocol"):
        e2.verify_freeze_receipt(receipt, artifacts, categories, options)


@pytest.mark.parametrize("field,value", [("seeds", [42]), ("k", 9), ("bootstrap_resamples", 100),
                                         ("request_seed", 2027)])
def test_freeze_rejects_changed_prespecified_constants(tmp_path, field, value):
    artifacts, categories, options, receipt, _ = freeze_fixture(tmp_path)
    receipt[field] = value
    with pytest.raises(ValueError, match="analysis constants"):
        e2.verify_freeze_receipt(receipt, artifacts, categories, options)


def test_evidence_writer_is_exclusive_even_for_identical_rewrites(tmp_path):
    path = tmp_path / "synthetic-freeze.json"
    e2.write_new_json(path, {"status": "fixture"})
    original = path.read_bytes()
    with pytest.raises(FileExistsError):
        e2.write_new_json(path, {"status": "fixture"})
    with pytest.raises(FileExistsError):
        e2.write_new_json(path, {"status": "changed"})
    assert path.read_bytes() == original


def test_reserved_opening_is_once_only_and_hash_gate_precedes_opening(tmp_path):
    sealed = tmp_path / "synthetic-reserved.jsonl"
    sealed.write_text("".join(json.dumps({**cases()[1], "id": f"synthetic-{i:03d}"}) + "\n"
                              for i in range(100)))
    opening, freeze = tmp_path / "opening.json", tmp_path / "freeze.json"
    e2.write_new_json(freeze, {"synthetic_fixture_only": True})
    with pytest.raises(ValueError, match="commitment changed"):
        e2.open_reserved_once(sealed, opening, freeze, tmp_path, "b" * 64)
    assert not opening.exists()
    assert len(e2.open_reserved_once(sealed, opening, freeze, tmp_path, e2.sha256_file(sealed))) == 100
    original = opening.read_bytes()
    with pytest.raises(ValueError, match="already opened"):
        e2.open_reserved_once(sealed, opening, freeze, tmp_path, e2.sha256_file(sealed))
    assert opening.read_bytes() == original


def test_parse_cache_replay_preserves_errors_and_never_calls_parser(tmp_path, monkeypatch):
    fixture = cases()
    calls = []

    def parser(text, categories, backend, **kwargs):
        calls.append((text, backend))
        if backend == "ollama_compound" and text == fixture[1]["text"]:
            raise ConnectionError("synthetic offline parser")
        return next(row["gold"] for row in fixture if row["text"] == text)

    first = e2.parse_cases(fixture, ["category_1", "category_2"], tmp_path, {}, parser=parser)
    assert len(calls) == 4
    assert sum(bool(row["error"]) for row in first) == 1
    original = {p.name: p.read_bytes() for p in (tmp_path / "parse_cache").glob("*.json")}

    def forbidden_parser(*args, **kwargs):
        raise AssertionError("immutable replay must not perform inference")

    monkeypatch.setattr("feedctrl.experiment2_controls.parse_control", forbidden_parser)
    replay = e2.load_immutable_parse_cache(tmp_path, fixture)
    assert sorted(replay, key=lambda r: (r["id"], r["backend"])) == sorted(
        first, key=lambda r: (r["id"], r["backend"]))
    assert {p.name: p.read_bytes() for p in (tmp_path / "parse_cache").glob("*.json")} == original
    assert e2.summarize_parser(replay, fixture)["ollama_compound"]["accuracy"] == .5
    with pytest.raises(ValueError, match="no repeated inference"):
        e2.parse_cases(fixture, ["category_1", "category_2"], tmp_path, {}, parser=parser)
    assert len(calls) == 4
    assert {p.name: p.read_bytes() for p in (tmp_path / "parse_cache").glob("*.json")} == original


def test_immutable_replay_refuses_missing_modified_or_reworded_records(tmp_path):
    fixture = cases()
    e2.parse_cases(fixture, ["category_1", "category_2"], tmp_path, {},
                   parser=lambda text, *_args, **_kwargs: next(r["gold"] for r in fixture if r["text"] == text))
    path = next((tmp_path / "parse_cache").glob("*.json"))
    original = path.read_bytes()
    path.unlink()
    with pytest.raises(ValueError, match="complete immutable parse cache"):
        e2.load_immutable_parse_cache(tmp_path, fixture)
    path.write_bytes(original)
    changed = json.loads(original)
    changed["command"] = {"operation": "clarify", "directives": []}
    dump_json(path, changed)
    with pytest.raises(ValueError, match="record or exact wording changed"):
        e2.load_immutable_parse_cache(tmp_path, fixture)
    path.write_bytes(original)
    reworded = copy.deepcopy(fixture)
    reworded[0]["text"] += " changed"
    with pytest.raises(ValueError, match="record or exact wording changed"):
        e2.load_immutable_parse_cache(tmp_path, reworded)


def test_runner_replay_reads_only_immutable_evidence_and_rejects_inventory_changes(tmp_path, monkeypatch):
    from scripts.run_experiment2 import inventory, replay

    artifacts, categories, _, receipt, _ = freeze_fixture(tmp_path)
    fixture = cases()
    source = tmp_path / "synthetic-original-run"
    source.mkdir()
    e2.write_new_json(source / "opened_cases.json", fixture)
    e2.parse_cases(fixture, categories, source, {},
                   parser=lambda text, *_args, **_kwargs: next(r["gold"] for r in fixture if r["text"] == text))
    e2.write_new_json(source / "request_metrics.json", analysis_rows())
    e2.write_new_json(source / "manifest.json", {"stage": "test", "status": "synthetic_fixture",
                                                "freeze_receipt_sha256": e2.fingerprint(receipt),
                                                "files": inventory(source)})
    original = inventory(source)

    def forbidden(*args, **kwargs):
        raise AssertionError("replay must not generate new parser or ranking outcomes")

    monkeypatch.setattr(e2, "parse_cases", forbidden)
    monkeypatch.setattr(e2, "run_rankings", forbidden)
    monkeypatch.setattr("feedctrl.experiment2_controls.parse_control", forbidden)
    output = tmp_path / "synthetic-replay"
    result = replay(source, output, receipt, artifacts, categories)
    assert result["status"] == "replayed"
    assert json.loads((output / "request_metrics.json").read_text()) == analysis_rows()
    assert inventory(source) == original
    (source / "uncommitted-file.txt").write_text("synthetic tampering")
    with pytest.raises(ValueError, match="inventory changed"):
        replay(source, tmp_path / "rejected-replay", receipt, artifacts, categories)


def test_empty_analysis_is_not_assessed_not_a_negative_study():
    result = e2.analyze_rows([])
    assert result["status"] == "not_run"
    assert result["H1_passed"] is None and result["H2_passed"] is None
    assert result["H1_status"] == result["H2_status"] == "not_assessed"


def test_freeze_allows_exact_artifact_relocation_and_rejects_changed_bytes(tmp_path):
    import shutil
    artifacts, categories, options, receipt, _ = freeze_fixture(tmp_path)
    relocated = tmp_path / "isolated path with spaces"
    relocated.mkdir()
    copies = {}
    for label, original in artifacts.items():
        copies[label] = relocated / original.name
        shutil.copyfile(original, copies[label])
    e2.verify_freeze_receipt(receipt, copies, categories, options)
    copies["evaluator"].write_text("modified frozen evaluator")
    with pytest.raises(ValueError, match="Frozen artifact changed"):
        e2.verify_freeze_receipt(receipt, copies, categories, options)


def test_development_replay_cli_uses_recorded_commands_without_model_or_student_gate(tmp_path, monkeypatch):
    from scripts import run_experiment2 as runner
    root = tmp_path / "isolated project with spaces"
    (root / "feedctrl").mkdir(parents=True)
    (root / "docs").mkdir()
    for path in (root / "feedctrl/experiment2_controls.py", root / "feedctrl/experiment2_evaluation.py", root / "docs/experiment2-protocol.md"):
        path.write_text("Synthetic copied implementation marker; not a study artifact")
    data_path = root / "data.json"
    dump_json(data_path, {"items": [{"item_id": i, "categories": cs} for i, cs in catalogue().items()], "users": []})
    fixture = [{"id": f"synthetic-dev-{i:03d}", "class": e2.CLASSES[i % 4],
                "text": f"Synthetic fixture wording {i}: more category_1",
                "gold": command(directive())} for i in range(48)]
    dev_path = root / "dev.jsonl"
    dev_path.write_text("\n".join(json.dumps(row) for row in fixture))
    source = root / "results/experiment2/source"
    source.mkdir(parents=True)
    e2.write_new_json(source / "development_cases.json", fixture)
    e2.write_new_json(source / "execution_snapshot.json", {"status": "synthetic_fixture_only"})
    e2.parse_cases(fixture, ["category_1", "category_2"], source, {}, parser=lambda *args, **kwargs: command(directive()))
    e2.write_new_json(source / "manifest.json", {"stage": "dev", "status": "synthetic_fixture_only", "files": runner.inventory(source)})

    def forbidden(*args, **kwargs):
        raise AssertionError("Development replay cannot call a model, parser, or student gate")

    monkeypatch.setattr(runner, "ROOT", root)
    monkeypatch.setattr(runner, "gate", forbidden)
    monkeypatch.setattr(runner, "ollama_provenance", forbidden)
    monkeypatch.setattr(e2, "parse_cases", forbidden)
    monkeypatch.setattr(e2, "run_rankings", forbidden)
    output = root / "results/experiment2/replay"
    assert runner.main(["--stage", "replay", "--cache-run", str(source), "--output", str(output),
                        "--data", str(data_path), "--dev", str(dev_path), "--protocol", str(root / "docs/experiment2-protocol.md")]) == 0
    manifest = e2.read_json(output / "manifest.json")
    assert manifest["status"] == "development_replayed"
    assert manifest["ranking_status"] == "not_run"
    assert manifest["H1_status"] == manifest["H2_status"] == "not_assessed"
    accuracy = e2.read_json(output / "parser_accuracy.json")
    assert accuracy["ollama_compound"]["total"] == 48
    assert not list(root.rglob("test.opened.json"))
    with pytest.raises(AssertionError):
        forbidden()


@pytest.mark.parametrize("field", ["category", "condition_category"])
def test_freeze_rejects_final_gold_outside_frozen_catalogue(tmp_path, field):
    artifacts, categories, options, _, gate = freeze_fixture(tmp_path)
    gate = copy.deepcopy(gate)
    first = next(iter(gate["final_gold"].values()))
    first["directives"][0][field] = "category_999"
    with pytest.raises(ValueError, match="Final gold references categories outside"):
        e2.make_freeze_receipt(artifacts, categories, gate, options, {})


@pytest.mark.parametrize("timestamp_source", ["receipt", "rows"])
def test_student_timestamps_cannot_follow_adjudication_even_with_valid_hashes(tmp_path, timestamp_source):
    fixture = student_gate_fixture(tmp_path)
    receipt = e2.read_json(fixture["receipt_path"])
    adjudication = e2.read_json(fixture["adjudication_path"])
    if timestamp_source == "receipt":
        receipt["annotated_utc"] = "2026-01-03T03:04:05+00:00"
    else:
        path = fixture["annotations_path"]
        path.write_text(path.read_text().replace("2026-01-02T03:04:05+00:00", "2026-01-03T03:04:05+00:00"))
        receipt["student_annotations_sha256"] = e2.sha256_file(path)
        adjudication["student_annotations_sha256"] = e2.sha256_file(path)
        dump_json(fixture["adjudication_path"], adjudication)
        receipt["adjudication_sha256"] = e2.sha256_file(fixture["adjudication_path"])
    dump_json(fixture["receipt_path"], receipt)
    with pytest.raises(ValueError, match="Student annotation timestamps"):
        e2.validate_student_gate(**fixture)


def test_future_adjudication_cannot_satisfy_full_freeze(tmp_path):
    artifacts, categories, options, _, gate = freeze_fixture(tmp_path)
    gate = copy.deepcopy(gate)
    gate["adjudicated_utc"] = "2099-01-01T00:00:00+00:00"
    with pytest.raises(ValueError, match="Required time order"):
        e2.make_freeze_receipt(artifacts, categories, gate, options, {})


def test_full_freeze_requires_existing_parser_only_commitment(tmp_path):
    artifacts, categories, options, _, gate = freeze_fixture(tmp_path)
    artifacts["parser_commitment"].unlink()
    with pytest.raises(ValueError, match="Parser commitment is required"):
        e2.make_freeze_receipt(artifacts, categories, gate, options, {})


@pytest.mark.parametrize("field", ["parser_sha256", "policy", "test_sha256", "development_sha256"])
def test_full_freeze_rejects_mismatched_parser_commitment(tmp_path, field):
    artifacts, categories, options, _, gate = freeze_fixture(tmp_path)
    record = e2.read_json(artifacts["parser_commitment"])
    record[field] = {} if field == "policy" else "0" * 64
    dump_json(artifacts["parser_commitment"], record)
    with pytest.raises(ValueError, match="Parser commitment.*mismatch"):
        e2.make_freeze_receipt(artifacts, categories, gate, options, {})


def test_parser_commitment_must_precede_earliest_student_row_not_only_receipt(tmp_path):
    artifacts, categories, options, _, gate = freeze_fixture(tmp_path)
    gate["earliest_student_utc"] = "2025-12-31T23:59:59+00:00"
    with pytest.raises(ValueError, match="must precede every student row"):
        e2.make_freeze_receipt(artifacts, categories, gate, options, {})
    gate["earliest_student_utc"] = gate["annotated_utc"]
    record = e2.read_json(artifacts["parser_commitment"])
    record["created_utc"] = "2026-01-02T03:04:06+00:00"
    dump_json(artifacts["parser_commitment"], record)
    with pytest.raises(ValueError, match="must precede every student row"):
        e2.make_freeze_receipt(artifacts, categories, gate, options, {})


def test_valid_parser_commitment_survives_complete_relocation(tmp_path):
    import shutil
    artifacts, categories, options, receipt, gate = freeze_fixture(tmp_path)
    destination = tmp_path / "moved commitment and artifacts"
    destination.mkdir()
    moved = {}
    for label, path in artifacts.items():
        moved[label] = destination / path.name
        shutil.copyfile(path, moved[label])
    state_dir = artifacts["test_commitment"].parent
    for name in ("annotation.opened.json", "annotation.completed.json"):
        shutil.copyfile(state_dir / name, destination / name)
    shutil.copytree(state_dir / "annotation-attempts", destination / "annotation-attempts")
    original = moved["parser_commitment"].read_bytes()
    e2.verify_freeze_receipt(receipt, moved, categories, options)
    new_full_receipt = e2.make_freeze_receipt(moved, categories, gate, options, {})
    assert new_full_receipt["artifacts"]["parser_commitment"]["sha256"] == e2.sha256_file(moved["parser_commitment"])
    assert moved["parser_commitment"].read_bytes() == original


def test_parser_freeze_cli_needs_no_human_or_ollama_and_refuses_opened_test(tmp_path, monkeypatch):
    from scripts import run_experiment2 as runner
    root = tmp_path / "synthetic parser commitment CLI"
    (root / "feedctrl").mkdir(parents=True)
    (root / "docs").mkdir()
    for path in (root / "feedctrl/experiment2_controls.py", root / "feedctrl/experiment2_evaluation.py", root / "docs/experiment2-protocol.md"):
        path.write_text("Synthetic implementation marker only")
    data = root / "data.json"
    dump_json(data, {"items": [{"item_id": 1, "categories": ["category_1"]}], "users": []})
    dev, sealed = root / "synthetic-dev.jsonl", root / "synthetic-reserved.sealed"
    dev.write_text("Synthetic development bytes only")
    sealed.write_text("Synthetic reserved bytes deliberately not parseable as cases")
    original_sealed = sealed.read_bytes()

    def forbidden(*args, **kwargs):
        raise AssertionError("Parser-only freeze cannot call a parser, human gate, or Ollama")

    monkeypatch.setattr(runner, "ROOT", root)
    monkeypatch.setattr(runner, "gate", forbidden)
    monkeypatch.setattr(runner, "ollama_provenance", forbidden)
    monkeypatch.setattr(e2, "load_cases", forbidden)
    monkeypatch.setattr(e2, "parse_cases", forbidden)
    output = root / "results/experiment2/parser-only"
    common = ["--stage", "parser-freeze", "--data", str(data), "--dev", str(dev), "--test", str(sealed),
              "--protocol", str(root / "docs/experiment2-protocol.md")]
    assert runner.main([*common, "--output", str(output)]) == 0
    commitment = e2.read_json(output / "parser-commitment.json")
    assert commitment["parser_sha256"] == e2.sha256_file(root / "feedctrl/experiment2_controls.py")
    assert commitment["test_sha256"] == e2.sha256_file(sealed)
    assert commitment["reserved_test_opened_for_evaluation"] is False
    assert sealed.read_bytes() == original_sealed
    assert not sealed.with_name("test.opened.json").exists()
    sealed.with_name("test.opened.json").write_text("synthetic prior opening marker")
    rejected = root / "results/experiment2/rejected-parser-only"
    assert runner.main([*common, "--output", str(rejected)]) == 2
    assert not (rejected / "parser-commitment.json").exists()
    assert e2.read_json(rejected / "manifest.json")["status"] == "blocked"


def test_annotation_field_agreement_aligns_targets_and_counts_missing_directives():
    import hashlib
    fixture = [{"id": "synthetic-target-mismatch", "text": "Synthetic target identity fixture",
                "gold": command(directive(category="category_0"))}]
    gate = {"student_annotations": {fixture[0]["id"]: {
        "gold": command(directive(category="category_1")),
        "text_sha256": hashlib.sha256(fixture[0]["text"].encode()).hexdigest()}}}
    result = e2.annotation_agreement(fixture, gate)
    assert result["field_comparison_count"] == 2
    assert all(value == 0 for value in result["field_agreement"].values())
    assert result["target_category_set_agreement"] == 0
    assert result["request_operation_agreement"] == 1
    assert result["full_command_exact_agreement"] == 0
    fixture[0]["gold"] = command(directive(category="category_0"), directive(category="category_1"))
    partial = e2.annotation_agreement(fixture, gate)
    assert partial["field_comparison_count"] == 2
    assert all(value == .5 for value in partial["field_agreement"].values())
    assert partial["target_category_set_agreement"] == 0


def test_annotation_field_agreement_is_order_invariant_and_reports_empty_fields_undefined():
    import hashlib
    text = "Synthetic order and empty agreement fixture"
    gold = command(directive(category="category_1"), directive("reduce", "category_2", "strong"))
    fixture = [{"id": "synthetic-order", "text": text, "gold": gold}]
    gate = {"student_annotations": {"synthetic-order": {"gold": {"operation": "set", "directives": list(reversed(gold["directives"]))},
                                                         "text_sha256": hashlib.sha256(text.encode()).hexdigest()}}}
    assert all(value == 1 for value in e2.annotation_agreement(fixture, gate)["field_agreement"].values())
    fixture[0]["gold"] = {"operation": "clarify", "directives": []}
    gate["student_annotations"]["synthetic-order"]["gold"] = fixture[0]["gold"]
    result = e2.annotation_agreement(fixture, gate)
    assert result["field_comparison_count"] == 0
    assert all(value is None for value in result["field_agreement"].values())
    assert result["cohens_kappa"] is None


def test_analysis_reports_separate_satisfaction_user_aggregates_and_h3_nonzero_counts():
    rows = analysis_rows()
    for row in rows:
        row["band_satisfied"] = row["user_id"] <= 1
        row["baseline_already_satisfies"] = row["user_id"] == 1
        if row["condition"] == "llm" and row["user_id"] == 0:
            row["hr1"] = 1
    result = e2.analyze_rows(rows, n_bootstrap=100)
    for label in (*e2.CLASSES, "pooled"):
        table = result["satisfaction_descriptive"]["llm"][label]
        assert table["band_satisfied"]["user_mean"] == pytest.approx(2 / 3)
        assert table["baseline_already_satisfies"]["user_mean"] == pytest.approx(1 / 3)
        assert table["induced_success"]["user_mean"] == pytest.approx(1 / 3)
        assert table["band_satisfied"]["n_users"] == 3
        assert len(table["band_satisfied"]["user_aggregates"]) == 3
        assert table["band_satisfied"]["n_requests"] == (12 if label == "pooled" else 3)
        assert table["band_satisfied"]["n_request_seed_rows"] == (36 if label == "pooled" else 9)
    assert all("n_nonzero_users" in record for record in result["H3"])
    contrast = next(r for r in result["H3"] if r["condition"] == "llm" and r["reference"] == "A" and r["metric"] == "hr1")
    assert contrast["n_nonzero_users"] == 1


def test_full_human_gate_rejects_missing_comparison_record(tmp_path):
    fixture = student_gate_fixture(tmp_path)
    fixture["agreement_path"].unlink()
    with pytest.raises(ValueError, match="Agreement record computed before adjudication"):
        e2.validate_student_gate(**fixture)


@pytest.mark.parametrize("change", ["post_adjudication", "author_bytes", "student_bytes", "computed_IAA", "student_only_receipt"])
def test_full_human_gate_recomputes_prior_agreement_and_source_hashes(tmp_path, change):
    fixture = student_gate_fixture(tmp_path)
    path = fixture["agreement_path"]
    record = e2.read_json(path)
    if change == "post_adjudication":
        record["created_utc"] = "2026-01-02T04:05:07+00:00"
    elif change == "author_bytes":
        record["source_test_text"] += " "
    elif change == "student_bytes":
        record["student_annotations_text"] += " "
    elif change == "computed_IAA":
        record["agreement"]["full_command_exact_agreement"] = 0
    else:
        record["student_only_receipt_text"] += " "
    dump_json(path, record)
    receipt = e2.read_json(fixture["receipt_path"])
    receipt["agreement_record_sha256"] = e2.sha256_file(path)
    dump_json(fixture["receipt_path"], receipt)
    with pytest.raises(ValueError):
        e2.validate_student_gate(**fixture)


def test_comparison_cli_before_adjudication_uses_no_parser_model_or_evaluation_opening(tmp_path, monkeypatch):
    import shutil
    from scripts import run_experiment2 as runner
    fixture = student_gate_fixture(tmp_path)
    original = fixture["annotations_path"].parent
    root = tmp_path / "isolated comparison CLI"
    (root / "feedctrl").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "feedctrl/experiment2_evaluation.py").write_text("synthetic evaluation marker")
    (root / "docs/experiment2-protocol.md").write_text("synthetic protocol marker")
    shutil.copyfile(original / "parser.py", root / "feedctrl/experiment2_controls.py")
    for name in ("test.sealed", "dev.jsonl", "manifest.json", "id-map.json", "student.csv", "student-only-receipt.json", "parser-commitment.json"):
        shutil.copyfile(original / name, root / name)
    dump_json(root / "data.json", {"items": [{"item_id": 1, "categories": ["category_1", "category_2"]}], "users": []})

    def forbidden(*args, **kwargs):
        raise AssertionError("Annotation comparison cannot infer, score, adjudicate or open evaluation")

    monkeypatch.setattr(runner, "ROOT", root)
    monkeypatch.setattr(runner, "gate", forbidden)
    monkeypatch.setattr(runner, "ollama_provenance", forbidden)
    monkeypatch.setattr(e2, "parse_cases", forbidden)
    monkeypatch.setattr(e2, "run_rankings", forbidden)
    monkeypatch.setattr(e2, "open_reserved_once", forbidden)
    monkeypatch.setattr(e2, "utc_now", lambda: "2026-01-02T03:30:00+00:00")
    output = root / "results/experiment2/comparison"
    args = ["--stage", "compare-annotations", "--output", str(output), "--data", str(root / "data.json"),
            "--dev", str(root / "dev.jsonl"), "--test", str(root / "test.sealed"),
            "--protocol", str(root / "docs/experiment2-protocol.md"), "--language-manifest", str(root / "manifest.json"),
            "--annotation-id-map", str(root / "id-map.json"), "--parser-commitment", str(root / "parser-commitment.json"),
            "--student-annotations", str(root / "student.csv"), "--student-receipt", str(root / "student-only-receipt.json")]
    assert runner.main(args) == 0
    record = e2.read_json(output / "agreement-before-adjudication.json")
    assert record["agreement"]["full_command_exact_agreement"] == 1
    assert len(record["author_cases"]) == len(record["student_annotations"]) == 100
    assert (root / "annotation.opened.json").exists()
    assert not (root / "test.opened.json").exists()
    assert e2.read_json(output / "manifest.json")["ranking_status"] == "not_run"
    assert not (output / "parse_cache").exists()
    # A downstream final receipt must not authorize a retrospective comparison.
    shutil.copyfile(fixture["receipt_path"], root / "final-receipt.json")
    new_output = root / "results/experiment2/rejected-comparison"
    changed = [str(new_output) if value == str(output) else str(root / "final-receipt.json") if value == str(root / "student-only-receipt.json") else value for value in args]
    assert runner.main(changed) == 2
    assert not (new_output / "agreement-before-adjudication.json").exists()


@pytest.mark.parametrize("label,gold", [
    ("compound", supported_class_gold("compound")),
    ("compound", command(*reversed(supported_class_gold("compound")["directives"]))),
    ("graded", command(directive())),
    ("graded", command(directive("reduce", strength="strong"))),
    ("graded", command(directive("exclude", strength="none"))),
    ("floor", supported_class_gold("floor")),
    ("conditional", supported_class_gold("conditional")),
])
def test_all_prespecified_final_class_forms_are_supported_without_rewriting(label, gold):
    case = {"id": "synthetic-valid-form", "class": label, "gold": gold}
    original = copy.deepcopy(case)
    assert e2.ranking_shape_issues([case]) == []
    e2.validate_ranking_cases([case])
    assert case == original


@pytest.mark.parametrize("label,gold", [
    ("unknown", supported_class_gold("graded")),
    (None, supported_class_gold("graded")),
    *[(label, {"operation": "clarify", "directives": []}) for label in e2.CLASSES],
    *[(label, supported_class_gold(other)) for label in e2.CLASSES for other in e2.CLASSES if label != other],
    ("compound", command(directive(strength="strong"), directive("reduce", "category_2", "moderate"))),
    ("compound", command(directive(strength="moderate"), directive("reduce", "category_2", "strong"))),
    ("compound", command(directive(strength="moderate"), directive("exclude", "category_2", "none"))),
    ("compound", command(directive(strength="moderate"), directive("boost", "category_2", "moderate"))),
    ("compound", command(directive(strength="moderate"), directive("reduce", "category_2", "moderate", floor=1))),
    ("compound", command(directive(strength="moderate", condition_category="category_2"), directive("reduce", "category_2", "moderate"))),
    ("graded", command(directive(strength="moderate"))),
    ("graded", command(directive(strength="strong"))),
    ("graded", command(directive("reduce", strength="slight"))),
    ("graded", command(directive("reduce", strength="moderate"))),
    ("floor", command(directive("reduce", strength="slight", floor=1))),
    ("floor", command(directive("reduce", strength="strong", floor=1))),
    ("conditional", command(directive(strength="slight", condition_category="category_2"))),
    ("conditional", command(directive(strength="strong", condition_category="category_2"))),
    ("conditional", command(directive(strength="moderate", condition_category="category_2"), directive("reduce", "category_2", "moderate"))),
])
def test_final_class_mismatch_is_explicit_and_never_relabelled(label, gold):
    case = {"id": "synthetic-invalid-form", "class": label, "gold": gold}
    original = copy.deepcopy(case)
    with pytest.raises(e2.UnsupportedRankingGold) as caught:
        e2.validate_ranking_cases([case])
    assert caught.value.issues[0]["id"] == case["id"]
    assert caught.value.issues[0]["class"] == label
    assert caught.value.issues[0]["reason"]
    assert case == original


def test_clarify_only_class_blocks_assignment_with_all_ids_before_history_access():
    fixture = [{"id": f"synthetic-clarify-{i}", "class": "floor", "gold": {"operation": "clarify", "directives": []}}
               for i in range(25)]
    class ForbiddenData(dict):
        def __getitem__(self, key):
            raise AssertionError("Unsupported final gold must block before history, scoring or reassignment")
    with pytest.raises(e2.UnsupportedRankingGold) as caught:
        e2.assign_requests(ForbiddenData(), fixture)
    assert {r["id"] for r in caught.value.issues} == {r["id"] for r in fixture}
    assert all(r["reason"] == "clarify_has_no_prespecified_ranking_metric" for r in caught.value.issues)


def test_full_freeze_rechecks_final_forms_against_committed_public_classes(tmp_path):
    artifacts, categories, options, _, gate = freeze_fixture(tmp_path)
    altered = copy.deepcopy(gate)
    first_id = sorted(altered["final_gold"])[0]
    altered["final_gold"][first_id] = {"operation": "clarify", "directives": []}
    original_hashes = {label: e2.sha256_file(path) for label, path in artifacts.items()}
    with pytest.raises(e2.UnsupportedRankingGold) as caught:
        e2.make_freeze_receipt(artifacts, categories, altered, options, {})
    assert caught.value.issues[0]["id"] == first_id
    assert original_hashes == {label: e2.sha256_file(path) for label, path in artifacts.items()}


def test_independent_student_clarify_still_receives_honest_comparison(tmp_path, monkeypatch):
    import shutil
    fixture = student_gate_fixture(tmp_path)
    original = fixture["annotations_path"].parent
    current = tmp_path / "independent clarification pass"
    current.mkdir()
    for name in ("test.sealed", "dev.jsonl", "parser.py", "parser-commitment.json", "manifest.json", "id-map.json", "student.csv", "student-only-receipt.json"):
        shutil.copyfile(original / name, current / name)
    with (current / "student.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row["operation"], row["directives_json"] = "clarify", "[]"
    with (current / "student.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    receipt = e2.read_json(current / "student-only-receipt.json")
    receipt["student_annotations_sha256"] = e2.sha256_file(current / "student.csv")
    dump_json(current / "student-only-receipt.json", receipt)
    def forbidden(*args, **kwargs):
        raise AssertionError("Independent annotation comparison cannot call a parser")
    monkeypatch.setattr("feedctrl.experiment2_controls.parse_control", forbidden)
    monkeypatch.setattr(e2, "utc_now", lambda: "2026-01-02T03:30:00+00:00")
    record = e2.compare_annotations(current / "student.csv", current / "student-only-receipt.json", current / "manifest.json",
                                    current / "id-map.json", current / "test.sealed", current / "parser-commitment.json",
                                    current / "parser.py", current / "dev.jsonl", ["category_1", "category_2"], current / "comparison")
    assert record["agreement"]["n"] == 100
    assert record["agreement"]["full_command_exact_agreement"] == 0
    assert len(record["disagreements"]) == 100
    assert all(row["gold"]["operation"] == "clarify" for row in record["student_annotations"].values())
    assert not (current / "test.opened.json").exists()


def test_unsupported_final_consensus_blocks_test_cli_before_any_inference(tmp_path, monkeypatch):
    import shutil
    from scripts import run_experiment2 as runner
    fixture = student_gate_fixture(tmp_path)
    base = fixture["annotations_path"].parent
    adjudication = e2.read_json(fixture["adjudication_path"])
    changed_id = adjudication["final_gold"][0]["id"]
    adjudication["final_gold"][0]["gold"] = {"operation": "clarify", "directives": []}
    adjudication["final_gold"][0]["reason"] = "Synthetic genuine-unresolved-consensus scenario"
    dump_json(fixture["adjudication_path"], adjudication)
    receipt = e2.read_json(fixture["receipt_path"])
    receipt["adjudication_sha256"] = e2.sha256_file(fixture["adjudication_path"])
    receipt["final_gold_sha256"] = e2.fingerprint([{ "id": r["id"], "gold": e2.canonical(r["gold"])} for r in sorted(adjudication["final_gold"], key=lambda r:r["id"])])
    dump_json(fixture["receipt_path"], receipt)
    root = tmp_path / "blocked final consensus CLI"
    (root / "feedctrl").mkdir(parents=True)
    (root / "docs").mkdir()
    shutil.copyfile(base / "parser.py", root / "feedctrl/experiment2_controls.py")
    (root / "feedctrl/experiment2_evaluation.py").write_text("Synthetic evaluator marker")
    (root / "docs/protocol.md").write_text("Synthetic protocol marker")
    dump_json(root / "data.json", {"items": [{"item_id": 1, "categories": ["category_1", "category_2"]}], "users": []})
    def forbidden(*args, **kwargs):
        raise AssertionError("Unsupported final consensus must block before inference or evaluation opening")
    monkeypatch.setattr(runner, "ROOT", root)
    monkeypatch.setattr(runner, "ollama_provenance", forbidden)
    monkeypatch.setattr(e2, "parse_cases", forbidden)
    monkeypatch.setattr(e2, "run_rankings", forbidden)
    monkeypatch.setattr(e2, "open_reserved_once", forbidden)
    output = root / "results/experiment2/blocked"
    assert runner.main(["--stage", "test", "--output", str(output), "--data", str(root / "data.json"),
                        "--protocol", str(root / "docs/protocol.md"), "--dev", str(base / "dev.jsonl"), "--test", str(base / "test.sealed"),
                        "--language-manifest", str(fixture["manifest_path"]), "--annotation-id-map", str(fixture["id_map_path"]),
                        "--student-annotations", str(fixture["annotations_path"]), "--student-receipt", str(fixture["receipt_path"]),
                        "--adjudication", str(fixture["adjudication_path"]), "--agreement-record", str(fixture["agreement_path"])]) == 2
    manifest = e2.read_json(output / "manifest.json")
    assert manifest["status"] == "blocked"
    assert changed_id in manifest["error"]
    assert "clarify_has_no_prespecified_ranking_metric" in manifest["error"]
    assert not (base / "test.opened.json").exists()
    assert not (output / "parse_cache").exists()


def test_IAA_reports_full_command_and_directive_count_numerators_denominators_and_kappa():
    import hashlib
    source = [command(directive()), supported_class_gold("compound"), {"operation": "clarify", "directives": []}]
    targets = [source[0], command(directive()), source[2]]
    cases_ = [{"id": f"synthetic-count-{i}", "text": f"Synthetic directive count fixture {i}", "gold": gold} for i, gold in enumerate(source)]
    student = {"student_annotations": {row["id"]: {"gold": gold, "text_sha256": hashlib.sha256(row["text"].encode()).hexdigest()}
                                       for row, gold in zip(cases_, targets)}}
    result = e2.annotation_agreement(cases_, student)
    assert result["full_command_exact_agreement_numerator"] == 2
    assert result["full_command_exact_agreement_denominator"] == 3
    assert result["directive_count_agreement_numerator"] == 2
    assert result["directive_count_agreement_denominator"] == 3
    assert result["directive_count_agreement"] == pytest.approx(2 / 3)
    assert result["directive_count_cohens_kappa"] == pytest.approx(.5)
    one = e2.annotation_agreement(cases_[:1], {"student_annotations": {cases_[0]["id"]: student["student_annotations"][cases_[0]["id"]]}})
    assert one["directive_count_agreement"] == 1
    assert one["directive_count_cohens_kappa"] is None
    assert one["directive_count_kappa_undefined_reason"] == "expected agreement is one"


def retry_comparison_fixture(tmp_path):
    import shutil
    fixture = student_gate_fixture(tmp_path)
    original = fixture["annotations_path"].parent
    root = tmp_path / "wording retry fixture"
    root.mkdir()
    for name in ("test.sealed", "dev.jsonl", "parser.py", "parser-commitment.json", "manifest.json", "id-map.json", "student.csv", "student-only-receipt.json"):
        shutil.copyfile(original / name, root / name)
    correct_csv = (root / "student.csv").read_bytes()
    correct_receipt = (root / "student-only-receipt.json").read_bytes()
    (root / "student.csv").write_bytes(correct_csv.replace(b"Synthetic unit-test utterance 0", b"Worksheet transport mismatch 0", 1))
    receipt = e2.read_json(root / "student-only-receipt.json")
    receipt["student_annotations_sha256"] = e2.sha256_file(root / "student.csv")
    dump_json(root / "student-only-receipt.json", receipt)
    kwargs = {"annotations_path": root / "student.csv", "receipt_path": root / "student-only-receipt.json",
              "manifest_path": root / "manifest.json", "id_map_path": root / "id-map.json", "sealed_path": root / "test.sealed",
              "parser_commitment_path": root / "parser-commitment.json", "parser_module": root / "parser.py", "dev_path": root / "dev.jsonl",
              "categories": ["category_1", "category_2"], "output": root / "failed-output"}
    return root, kwargs, correct_csv, correct_receipt


def test_failed_wording_access_can_retry_with_same_labels_and_cannot_repeat_success(tmp_path, monkeypatch):
    root, args, correct_csv, correct_receipt = retry_comparison_fixture(tmp_path)
    monkeypatch.setattr(e2, "utc_now", lambda: "2026-01-02T03:20:00+00:00")
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Annotation retry cannot make inference or evaluation calls")
    monkeypatch.setattr("feedctrl.experiment2_controls.parse_control", forbidden)
    monkeypatch.setattr(e2, "open_reserved_once", forbidden)
    monkeypatch.setattr(e2, "run_rankings", forbidden)
    with pytest.raises(e2.AnnotationWordingMismatch):
        e2.compare_annotations(**args)
    opening_bytes = (root / "annotation.opened.json").read_bytes()
    failed = next((root / "annotation-attempts").glob("*-finished.json"))
    failed_bytes = failed.read_bytes()
    first = e2.read_json(failed)
    assert first["status"] == "failed_validation" and first["retryable"]
    assert "Worksheet transport mismatch 0" in first["started_record"]["student_annotations_text"]
    assert not (root / "annotation.completed.json").exists()
    assert not (root / "annotation.in-progress.json").exists()
    assert not (args["output"] / "agreement-before-adjudication.json").exists()
    (root / "corrected-student.csv").write_bytes(correct_csv)
    (root / "corrected-receipt.json").write_bytes(correct_receipt)
    corrected = {**args, "annotations_path": root / "corrected-student.csv", "receipt_path": root / "corrected-receipt.json",
                 "output": root / "corrected-output"}
    with pytest.raises(ValueError, match="retry requires"):
        e2.compare_annotations(**corrected)
    monkeypatch.setattr(e2, "utc_now", lambda: "2026-01-02T03:30:00+00:00")
    record = e2.compare_annotations(**corrected, retry_attempt_path=failed, correction_reason="Restore exact worksheet wording after a transport error; labels are unchanged.")
    assert record["agreement"]["full_command_exact_agreement"] == 1
    assert record["first_annotation_access"]["created_utc"] == "2026-01-02T03:20:00+00:00"
    assert (root / "annotation.opened.json").read_bytes() == opening_bytes
    assert failed.read_bytes() == failed_bytes
    assert (root / "annotation.completed.json").exists()
    assert not (root / "test.opened.json").exists()
    assert record["annotation_attempt"]["prior_failed_attempt"] == first
    student = e2.validate_student_annotation_pass(corrected["annotations_path"], corrected["receipt_path"], args["manifest_path"], args["id_map_path"], e2.sha256_file(args["sealed_path"]))
    e2.verify_agreement_record(corrected["output"] / "agreement-before-adjudication.json", student,
                               e2.sha256_file(args["sealed_path"]), "2026-01-02T04:05:06+00:00")
    attempts = {p.name: p.read_bytes() for p in (root / "annotation-attempts").iterdir()}
    with pytest.raises(ValueError, match="already completed"):
        e2.compare_annotations(**{**corrected, "output": root / "forbidden-rerun"}, retry_attempt_path=failed, correction_reason="Repeated comparison is forbidden")
    assert {p.name: p.read_bytes() for p in (root / "annotation-attempts").iterdir()} == attempts


@pytest.mark.parametrize("change", ["labels", "parser_commitment", "evaluation_opening", "tampered_failed_evidence"])
def test_annotation_retry_rejects_label_parser_changes_and_evaluation_access(tmp_path, monkeypatch, change):
    root, args, correct_csv, correct_receipt = retry_comparison_fixture(tmp_path)
    monkeypatch.setattr(e2, "utc_now", lambda: "2026-01-02T03:20:00+00:00")
    with pytest.raises(e2.AnnotationWordingMismatch):
        e2.compare_annotations(**args)
    failed = next((root / "annotation-attempts").glob("*-finished.json"))
    evidence = {p.name: p.read_bytes() for p in (root / "annotation-attempts").iterdir()}
    opening_bytes = (root / "annotation.opened.json").read_bytes()
    (root / "corrected-student.csv").write_bytes(correct_csv)
    (root / "corrected-receipt.json").write_bytes(correct_receipt)
    corrected = {**args, "annotations_path": root / "corrected-student.csv", "receipt_path": root / "corrected-receipt.json", "output": root / "rejected-output"}
    if change == "labels":
        with corrected["annotations_path"].open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        rows[0]["operation"], rows[0]["directives_json"] = "clarify", "[]"
        with corrected["annotations_path"].open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
        receipt = e2.read_json(corrected["receipt_path"])
        receipt["student_annotations_sha256"] = e2.sha256_file(corrected["annotations_path"])
        dump_json(corrected["receipt_path"], receipt)
    elif change == "tampered_failed_evidence":
        record = e2.read_json(failed)
        record["started_record"]["student_receipt_text"] += " "
        dump_json(failed, record)
        evidence = {p.name: p.read_bytes() for p in (root / "annotation-attempts").iterdir()}
    elif change == "parser_commitment":
        record = e2.read_json(args["parser_commitment_path"])
        record["scope"] = "Changed synthetic commitment despite same parser bytes"
        changed = root / "changed-commitment.json"
        dump_json(changed, record)
        corrected["parser_commitment_path"] = changed
    else:
        (root / "test.opened.json").write_text("synthetic prior evaluation opening")
    with pytest.raises(ValueError):
        e2.compare_annotations(**corrected, retry_attempt_path=failed, correction_reason="This attempted change must be rejected")
    assert (root / "annotation.opened.json").read_bytes() == opening_bytes
    assert {p.name: p.read_bytes() for p in (root / "annotation-attempts").iterdir()} == evidence
    assert not (root / "annotation.completed.json").exists()


@pytest.mark.parametrize("failure", ["completion_marker", "successful_finish", "commit_before_write", "commit_after_write"])
def test_partial_annotation_transaction_never_satisfies_downstream_human_gate(tmp_path, monkeypatch, failure):
    root, args, correct_csv, correct_receipt = retry_comparison_fixture(tmp_path)
    args["annotations_path"].write_bytes(correct_csv)
    args["receipt_path"].write_bytes(correct_receipt)
    monkeypatch.setattr(e2, "utc_now", lambda: "2026-01-02T03:30:00+00:00")
    original_writer = e2.write_new_json
    injected = []

    def fail_transaction_write(path, value):
        path = Path(path)
        selected = ((failure == "completion_marker" and path.name == "annotation.completed.json") or
                    (failure == "successful_finish" and path.name.endswith("-finished.json") and value.get("status") == "completed") or
                    (failure.startswith("commit_") and path.name == "annotation-commit.json"))
        if selected and not injected:
            injected.append(path)
            if failure == "commit_after_write":
                original_writer(path, value)
            raise OSError("Synthetic transaction write failure")
        original_writer(path, value)

    monkeypatch.setattr(e2, "write_new_json", fail_transaction_write)
    with pytest.raises(OSError, match="Synthetic transaction write failure"):
        e2.compare_annotations(**args)
    assert injected
    agreement_path = args["output"] / "agreement-before-adjudication.json"
    assert agreement_path.is_file()  # A plausible-looking result alone is insufficient.
    original_fixture = tmp_path / "synthetic-human-gate-fixture"
    final_receipt = e2.read_json(original_fixture / "receipt.json")
    final_receipt["agreement_record_sha256"] = e2.sha256_file(agreement_path)
    dump_json(root / "final-receipt.json", final_receipt)
    with pytest.raises(ValueError, match="transaction|marker|nonretryable|failed-commit"):
        e2.validate_student_gate(args["annotations_path"], root / "final-receipt.json", original_fixture / "adjudication.json",
                                 args["manifest_path"], args["id_map_path"], e2.sha256_file(args["sealed_path"]), agreement_path)
    assert (root / "annotation.opened.json").is_file()
    assert list((root / "annotation-attempts").glob("*-finished.json"))
    assert not (root / "test.opened.json").exists()
    assert not (root / "annotation.in-progress.json").exists()
    assert not (args["output"] / "parse_cache").exists()


def test_successful_annotation_gate_relocates_markers_journal_and_commit_by_current_paths(tmp_path):
    import shutil
    fixture = student_gate_fixture(tmp_path)
    original = fixture["annotations_path"].parent
    destination = tmp_path / "relocated complete human evidence with spaces"
    shutil.copytree(original, destination)
    moved = {key: destination / value.relative_to(original) if isinstance(value, Path) else value for key, value in fixture.items()}
    agreement_bytes = moved["agreement_path"].read_bytes()
    shutil.rmtree(original)
    gate = e2.validate_student_gate(**moved)
    assert gate["status"] == "verified_human_attestations"
    assert moved["agreement_path"].read_bytes() == agreement_bytes
    marker = destination / "annotation.completed.json"
    marker.write_bytes(marker.read_bytes() + b" ")
    with pytest.raises(ValueError, match="transaction proof"):
        e2.validate_student_gate(**moved)


def test_embedded_first_access_timestamp_cannot_replace_actual_immutable_marker(tmp_path):
    fixture = student_gate_fixture(tmp_path)
    opening = fixture["annotations_path"].parent / "annotation.opened.json"
    original_opening = opening.read_bytes()
    record = e2.read_json(fixture["agreement_path"])
    record["first_annotation_access"]["created_utc"] = "1999-01-01T00:00:00+00:00"
    dump_json(fixture["agreement_path"], record)
    receipt = e2.read_json(fixture["receipt_path"])
    receipt["agreement_record_sha256"] = e2.sha256_file(fixture["agreement_path"])
    dump_json(fixture["receipt_path"], receipt)
    with pytest.raises(ValueError, match="first annotation access"):
        e2.validate_student_gate(**fixture)
    assert opening.read_bytes() == original_opening


def test_failed_annotation_lock_cleanup_blocks_human_gate_and_full_freeze(tmp_path, monkeypatch):
    import shutil
    artifacts, categories, options, _, original_gate = freeze_fixture(tmp_path)
    original_bank = artifacts["test_commitment"].parent
    current_bank = tmp_path / "current bank with surviving process lock"
    current_bank.mkdir()
    for name in ("test.sealed", "dev.jsonl", "parser.py", "parser-commitment.json", "manifest.json", "id-map.json",
                 "student.csv", "student-only-receipt.json", "adjudication.json", "receipt.json"):
        shutil.copyfile(original_bank / name, current_bank / name)
    output = current_bank / "comparison"
    lock = current_bank / "annotation.in-progress.json"
    original_unlink = Path.unlink

    def failed_lock_cleanup(path, *args, **kwargs):
        if path == lock:
            raise PermissionError("Synthetic annotation lock cleanup failure")
        return original_unlink(path, *args, **kwargs)

    with monkeypatch.context() as injected:
        injected.setattr(e2, "utc_now", lambda: "2026-01-02T03:30:00+00:00")
        injected.setattr(Path, "unlink", failed_lock_cleanup)
        with pytest.raises(PermissionError, match="Synthetic annotation lock cleanup failure"):
            e2.compare_annotations(current_bank / "student.csv", current_bank / "student-only-receipt.json",
                                   current_bank / "manifest.json", current_bank / "id-map.json", current_bank / "test.sealed",
                                   current_bank / "parser-commitment.json", current_bank / "parser.py", current_bank / "dev.jsonl",
                                   categories, output)
    agreement = output / "agreement-before-adjudication.json"
    commit = output / "annotation-commit.json"
    assert lock.exists() and agreement.exists() and commit.exists()
    assert (current_bank / "annotation.completed.json").exists()
    assert e2.read_json(next((current_bank / "annotation-attempts").glob("*-finished.json")))["status"] == "completed"
    receipt = e2.read_json(current_bank / "receipt.json")
    receipt["agreement_record_sha256"] = e2.sha256_file(agreement)
    dump_json(current_bank / "receipt.json", receipt)
    evidence = {path: path.read_bytes() for path in current_bank.rglob("*") if path.is_file()}
    with pytest.raises(ValueError, match="surviving process lock"):
        e2.validate_student_gate(current_bank / "student.csv", current_bank / "receipt.json", current_bank / "adjudication.json",
                                 current_bank / "manifest.json", current_bank / "id-map.json", e2.sha256_file(current_bank / "test.sealed"), agreement)
    # Even a previously verified gate cannot bypass the current bank's lock.
    moved = {label: current_bank / path.name if path.parent == original_bank else path for label, path in artifacts.items()}
    moved.update(agreement_record=agreement, annotation_commit_record=commit)
    cached_gate = {**original_gate, "agreement_record_sha256": e2.sha256_file(agreement),
                   "annotation_commit_sha256": e2.sha256_file(commit), "receipt_sha256": e2.sha256_file(current_bank / "receipt.json")}
    with pytest.raises(ValueError, match="surviving process lock"):
        e2.make_freeze_receipt(moved, categories, cached_gate, options, {})
    assert all(path.read_bytes() == contents for path, contents in evidence.items())
    assert not (current_bank / "test.opened.json").exists()
    assert not (output / "parse_cache").exists()
