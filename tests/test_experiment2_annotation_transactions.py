"""Synthetic journal/metadata regressions. Never reads the real reserved bank."""
import pytest

from feedctrl import experiment2_evaluation as e2
from test_experiment2_evaluation import dump_json, freeze_fixture, retry_comparison_fixture, supported_class_gold


def corrected_inputs(root, args, csv_bytes, receipt_bytes):
    (root / "corrected.csv").write_bytes(csv_bytes)
    (root / "corrected-receipt.json").write_bytes(receipt_bytes)
    return {**args, "annotations_path": root / "corrected.csv", "receipt_path": root / "corrected-receipt.json",
            "output": root / "corrected-output"}


def failed_records(root):
    return sorted((root / "annotation-attempts").glob("*-finished.json"),
                  key=lambda path: e2.read_json(path)["started_record"]["attempt_index"])


def test_retry_requires_actual_latest_failure_and_preserves_all_earlier_attempts(tmp_path, monkeypatch):
    root, args, csv_bytes, receipt_bytes = retry_comparison_fixture(tmp_path)
    monkeypatch.setattr(e2, "utc_now", lambda: "2026-01-02T03:30:00+00:00")
    with pytest.raises(e2.AnnotationWordingMismatch):
        e2.compare_annotations(**args)
    first = failed_records(root)[0]
    with pytest.raises(e2.AnnotationWordingMismatch):
        e2.compare_annotations(**{**args, "output": root / "second-failure"}, retry_attempt_path=first,
                               correction_reason="Synthetic correction remained incomplete; labels unchanged")
    second = failed_records(root)[-1]
    original = {path: path.read_bytes() for path in (root / "annotation-attempts").iterdir()}
    opening = (root / "annotation.opened.json").read_bytes()
    corrected = corrected_inputs(root, args, csv_bytes, receipt_bytes)
    with pytest.raises(ValueError, match="actual latest"):
        e2.compare_annotations(**corrected, retry_attempt_path=first, correction_reason="Cannot skip a newer failure")
    record = e2.compare_annotations(**corrected, retry_attempt_path=second, correction_reason="Restore exact wording with unchanged labels")
    assert record["annotation_attempt"]["attempt_index"] == 3
    assert record["agreement"]["full_command_exact_agreement"] == 1
    assert all(path.read_bytes() == contents for path, contents in original.items())
    assert (root / "annotation.opened.json").read_bytes() == opening
    assert not (root / "test.opened.json").exists()


@pytest.mark.parametrize("interruption", ["nonretryable", "unfinished"])
def test_older_retry_cannot_bypass_intervening_nonretryable_or_unfinished_attempt(tmp_path, monkeypatch, interruption):
    root, args, csv_bytes, receipt_bytes = retry_comparison_fixture(tmp_path)
    monkeypatch.setattr(e2, "utc_now", lambda: "2026-01-02T03:30:00+00:00")
    with pytest.raises(e2.AnnotationWordingMismatch):
        e2.compare_annotations(**args)
    first = failed_records(root)[0]
    corrected = corrected_inputs(root, args, csv_bytes, receipt_bytes)
    if interruption == "nonretryable":
        output = root / "synthetic-unwritable-output"
        output.write_text("A regular file cannot contain agreement outputs")
        with pytest.raises(OSError):
            e2.compare_annotations(**{**corrected, "output": output}, retry_attempt_path=first,
                                   correction_reason="Same labels, legitimate wording correction")
        assert e2.read_json(failed_records(root)[-1])["status"] == "failed_nonretryable"
    else:
        def interrupt_comparison(*args, **kwargs):
            raise KeyboardInterrupt("Synthetic interrupted comparison")
        with monkeypatch.context() as local:
            local.setattr(e2, "annotation_agreement", interrupt_comparison)
            with pytest.raises(KeyboardInterrupt):
                e2.compare_annotations(**corrected, retry_attempt_path=first,
                                       correction_reason="Same labels, legitimate wording correction")
        assert len(list((root / "annotation-attempts").glob("*-started.json"))) == 2
        assert len(failed_records(root)) == 1
    before = {path: path.read_bytes() for path in (root / "annotation-attempts").iterdir()}
    with pytest.raises(ValueError, match="nonretryable|unfinished"):
        e2.compare_annotations(**{**corrected, "output": root / "forbidden-bypass"}, retry_attempt_path=first,
                               correction_reason="An older failure must not bypass the journal")
    assert all(path.read_bytes() == contents for path, contents in before.items())
    assert len(list((root / "annotation-attempts").iterdir())) == len(before)
    assert not (root / "annotation.completed.json").exists()
    assert not (root / "test.opened.json").exists()


@pytest.mark.parametrize("label", ["language_manifest", "annotation_id_map"])
def test_changed_public_metadata_bytes_block_human_gate_and_cached_gate_full_freeze(tmp_path, label):
    artifacts, categories, options, _, gate = freeze_fixture(tmp_path)
    artifacts[label].write_bytes(artifacts[label].read_bytes() + b"\n ")
    with pytest.raises(ValueError, match="current public metadata"):
        e2.validate_student_gate(artifacts["student_annotations"], artifacts["student_receipt"], artifacts["adjudication"],
                                 artifacts["language_manifest"], artifacts["annotation_id_map"],
                                 e2.sha256_file(artifacts["test_commitment"]), artifacts["agreement_record"])
    with pytest.raises(ValueError, match="current full-freeze artifact"):
        e2.make_freeze_receipt(artifacts, categories, gate, options, {})
    assert not artifacts["test_commitment"].with_name("test.opened.json").exists()


def test_changed_class_manifest_and_corresponding_final_gold_cannot_reach_freeze(tmp_path):
    artifacts, categories, options, _, gate = freeze_fixture(tmp_path)
    manifest = e2.read_json(artifacts["language_manifest"])
    changed_id = manifest["cases"][0]["id"]
    manifest["cases"][0]["class"] = "graded"
    dump_json(artifacts["language_manifest"], manifest)
    adjudication = e2.read_json(artifacts["adjudication"])
    for row in adjudication["final_gold"]:
        if row["id"] == changed_id:
            row["gold"] = supported_class_gold("graded")
    dump_json(artifacts["adjudication"], adjudication)
    receipt = e2.read_json(artifacts["student_receipt"])
    receipt["adjudication_sha256"] = e2.sha256_file(artifacts["adjudication"])
    receipt["final_gold_sha256"] = e2.fingerprint([{"id": row["id"], "gold": e2.canonical(row["gold"])}
                                                 for row in sorted(adjudication["final_gold"], key=lambda row: row["id"])])
    dump_json(artifacts["student_receipt"], receipt)
    with pytest.raises(ValueError, match="current public metadata"):
        e2.validate_student_gate(artifacts["student_annotations"], artifacts["student_receipt"], artifacts["adjudication"],
                                 artifacts["language_manifest"], artifacts["annotation_id_map"],
                                 e2.sha256_file(artifacts["test_commitment"]), artifacts["agreement_record"])
    gate["final_gold"][changed_id] = supported_class_gold("graded")
    with pytest.raises(ValueError, match="current full-freeze artifact"):
        e2.make_freeze_receipt(artifacts, categories, gate, options, {})
    assert not artifacts["test_commitment"].with_name("test.opened.json").exists()


@pytest.mark.parametrize("mismatch", ["class", "id"])
def test_comparison_rejects_source_ids_or_classes_that_differ_from_public_manifest(tmp_path, monkeypatch, mismatch):
    root, args, csv_bytes, receipt_bytes = retry_comparison_fixture(tmp_path)
    args = corrected_inputs(root, args, csv_bytes, receipt_bytes)
    manifest = e2.read_json(args["manifest_path"])
    if mismatch == "class":
        manifest["cases"][0]["class"] = "graded"
    else:
        old_id = manifest["cases"][0]["id"]
        manifest["cases"][0]["id"] = "synthetic-other-id"
        mapping = e2.read_json(args["id_map_path"])
        mapping["blind-000"] = "synthetic-other-id"
        dump_json(args["id_map_path"], mapping)
        receipt = e2.read_json(args["receipt_path"])
        receipt["case_ids"] = ["synthetic-other-id" if value == old_id else value for value in receipt["case_ids"]]
        dump_json(args["receipt_path"], receipt)
    dump_json(args["manifest_path"], manifest)
    monkeypatch.setattr(e2, "utc_now", lambda: "2026-01-02T03:30:00+00:00")
    with pytest.raises(ValueError, match="Original author case IDs/classes"):
        e2.compare_annotations(**args)
    assert e2.read_json(failed_records(root)[0])["status"] == "failed_nonretryable"
    assert not (args["output"] / "agreement-before-adjudication.json").exists()
    assert not (root / "test.opened.json").exists()
