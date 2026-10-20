"""Run gated Experiment 2 stages. Reserved-test inference requires real student evidence."""
from __future__ import annotations
import argparse
import csv
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.output_safety import require_new_output
from feedctrl import experiment2_evaluation as e2
from feedctrl.controls import ollama_provenance


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, choices=("dev", "parser-freeze", "compare-annotations", "freeze", "test", "replay"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--data", type=Path, default=ROOT / "data/processed.json")
    parser.add_argument("--models", type=Path, default=ROOT / "results/models")
    parser.add_argument("--dev", type=Path, default=ROOT / "results/experiment2/language-v2/dev.jsonl")
    parser.add_argument("--test", type=Path, default=ROOT / "results/experiment2/language-v2/test.sealed")
    parser.add_argument("--language-manifest", type=Path, default=ROOT / "results/experiment2/language-v2/reserved-test-manifest.json")
    parser.add_argument("--annotation-id-map", type=Path, default=ROOT / "results/experiment2/language-v2/annotation-id-map.json")
    parser.add_argument("--protocol", type=Path, default=ROOT / "docs/experiment2-protocol.md")
    parser.add_argument("--student-annotations", type=Path)
    parser.add_argument("--student-receipt", type=Path)
    parser.add_argument("--adjudication", type=Path)
    parser.add_argument("--agreement-record", type=Path)
    parser.add_argument("--retry-annotation-attempt", type=Path, help="Immutable failed wording-validation attempt to correct, with unchanged labels")
    parser.add_argument("--annotation-correction-reason", help="Explicit reason for a same-label wording or transport correction")
    parser.add_argument("--freeze-receipt", type=Path)
    parser.add_argument("--parser-commitment", type=Path, default=ROOT / "results/experiment2/parser-freeze-v2.json")
    parser.add_argument("--cache-run", type=Path, help="Original dev or reserved-test run; replay never calls a parser or a model")
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--ollama-model", default="llama3.1:8b", choices=("llama3.1:8b",))
    parser.add_argument("--timeout", type=float, default=600)
    parser.add_argument("--num-thread", type=int, default=6)
    return parser.parse_args(argv)


def artifact_paths(args):
    return {"parser_module": ROOT / "feedctrl/experiment2_controls.py", "evaluator": ROOT / "feedctrl/experiment2_evaluation.py",
            "runner": Path(__file__).resolve(), "parser_commitment": args.parser_commitment, "legacy_controls": ROOT / "feedctrl/controls.py",
            "legacy_evaluation": ROOT / "feedctrl/evaluation.py", "legacy_model": ROOT / "feedctrl/model.py", "protocol": args.protocol, "dev": args.dev, "test_commitment": args.test,
            "data": args.data, "language_manifest": args.language_manifest, "annotation_id_map": args.annotation_id_map,
            "student_annotations": args.student_annotations, "student_receipt": args.student_receipt,
            "adjudication": args.adjudication, "agreement_record": args.agreement_record,
            "annotation_commit_record": args.agreement_record.with_name("annotation-commit.json") if args.agreement_record else None,
            **{f"{kind}_{seed}": args.models / f"seed_{seed}" / filename
            for seed in e2.SEEDS for kind, filename in (("checkpoint", "model.pt"), ("checkpoint_metadata", "metadata.json"))}}


def gate(args):
    if any(value is None for value in (args.student_annotations, args.student_receipt, args.adjudication, args.agreement_record)):
        raise ValueError("Blocked: provide --student-annotations, --student-receipt, --adjudication and --agreement-record from the completed independent student pass")
    return e2.validate_student_gate(args.student_annotations, args.student_receipt, args.adjudication,
                                    args.language_manifest, args.annotation_id_map, e2.sha256_file(args.test), agreement_path=args.agreement_record,
                                    annotation_state_dir=args.test.parent)


def inventory(output):
    return {str(p.relative_to(output)): {"sha256": e2.sha256_file(p), "bytes": p.stat().st_size}
            for p in sorted(output.rglob("*")) if p.is_file() and p.name != "manifest.json"}


def save_rows(output, rows):
    e2.write_new_json(output / "request_metrics.json", rows)
    if rows:
        with (output / "request_metrics.csv").open("x", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            for row in rows:
                writer.writerow({key: json.dumps(value, sort_keys=True) if isinstance(value, (dict, list)) else value for key, value in row.items()})


def replay(source, output, receipt, paths, categories):
    e2.verify_freeze_receipt(receipt, paths, categories)
    manifest = e2.read_json(source / "manifest.json")
    if manifest.get("stage") != "test":
        raise ValueError("Replay source must be an original reserved-test run")
    if manifest.get("freeze_receipt_sha256") != e2.fingerprint(receipt):
        raise ValueError("Replay source has a different freeze receipt")
    actual = inventory(source)
    if actual != manifest.get("files"):
        raise ValueError("Original run inventory changed; replay requires exact immutable files")
    cases = e2.read_json(source / "opened_cases.json")
    outcomes = e2.load_immutable_parse_cache(source, cases)
    accuracy = e2.summarize_parser(outcomes, cases)
    e2.write_new_json(output / "parser_accuracy.json", accuracy)
    print(json.dumps({"stage": "parser_accuracy_replayed", "accuracy": accuracy}), flush=True)
    if not (source / "request_metrics.json").is_file():
        return {"status": "incomplete_immutable_evidence", "ranking_status": "not_run", "H1_status": "not_assessed", "H2_status": "not_assessed", "reason": "No recorded ranking rows; replay cannot create missing test results"}
    rows = e2.read_json(source / "request_metrics.json")
    summary = e2.analyze_rows(rows)
    save_rows(output, rows)
    e2.write_new_json(output / "summary.json", summary)
    return {"status": "replayed", "ranking_status": summary["status"], "original_status": manifest["status"], "parser_error_count": sum(r["error"] is not None for r in outcomes)}



def replay_development(source, output):
    manifest = e2.read_json(source / "manifest.json")
    if manifest.get("stage") != "dev" or inventory(source) != manifest.get("files"):
        raise ValueError("Development replay requires the unchanged original dev-run inventory")
    cases = e2.read_json(source / "development_cases.json")
    if len(cases) != 48:
        raise ValueError("Development replay requires all 48 recorded cases")
    outcomes = e2.load_immutable_parse_cache(source, cases)
    accuracy = e2.summarize_parser(outcomes, cases)
    e2.write_new_json(output / "parser_accuracy.json", accuracy)
    summary = {"status": "development_replayed", "parser_accuracy": accuracy, "reserved_test_status": "not_opened", "ranking_status": "not_run",
               "source_manifest_sha256": e2.sha256_file(source / "manifest.json"),
               "original_execution_snapshot": e2.read_json(source / "execution_snapshot.json"),
               "scope": "Recomputed from immutable actual parser commands; no parser or ranking execution, no reserved-test evidence"}
    e2.write_new_json(output / "summary.json", summary)
    return {"status": "development_replayed", "reserved_test_status": "not_opened", "ranking_status": "not_run",
            "source_manifest_sha256": summary["source_manifest_sha256"], "parser_error_count": sum(bool(r["error"]) for r in outcomes)}

def main(argv=None):
    args = arguments(argv)
    started = time.monotonic()
    try:
        output = require_new_output(args.output, ROOT, directory=True)
    except ValueError as error:
        print(json.dumps({"status": "blocked", "error": str(error)}), file=sys.stderr)
        return 2
    if not output.is_relative_to((ROOT / "results/experiment2").resolve()):
        print(json.dumps({"status": "blocked", "error": "Experiment 2 output must be inside results/experiment2"}), file=sys.stderr)
        return 2
    output.mkdir(parents=True, exist_ok=True)
    options = {"model": args.ollama_model, "base_url": args.ollama_url, "timeout": args.timeout,
               "seed": 42, "num_thread": args.num_thread}
    manifest = {"schema_version": 1, "experiment": "experiment2", "stage": args.stage, "started_utc": e2.utc_now(),
                "status": "started", "ranking_status": "not_run", "H1_status": "not_assessed", "H2_status": "not_assessed",
                "parser_options": options}
    exit_code = 0
    try:
        manifest["data_sha256"] = e2.sha256_file(args.data)
        data = e2.read_json(args.data)
        categories = sorted({c for i in data["items"] for c in i["categories"]}, key=e2.category_key)
        # Snapshot pre-execution code and policy even for dev, which is allowed to evolve.
        snapshot = {"created_utc": e2.utc_now(), "policy": e2.policy_fingerprints(categories),
                    "source_sha256": {str(path.resolve()): e2.sha256_file(path) for path in
                        (ROOT / "feedctrl/experiment2_controls.py", ROOT / "feedctrl/experiment2_evaluation.py", Path(__file__).resolve(), args.protocol)},
                    "dev_sha256": e2.sha256_file(args.dev), "parser_options": options}
        e2.write_new_json(output / "execution_snapshot.json", snapshot)
        source_dir = output / "source_snapshot"
        source_dir.mkdir()
        for index, source in enumerate(snapshot["source_sha256"]):
            with (source_dir / f"{index:02d}-{Path(source).name}").open("xb") as handle:
                handle.write(Path(source).read_bytes())
        if args.stage == "parser-freeze":
            commitment = e2.make_parser_commitment(ROOT / "feedctrl/experiment2_controls.py", args.dev, args.test, categories)
            e2.write_new_json(output / "parser-commitment.json", commitment)
            manifest.update({"status": commitment["status"], "parser_commitment_sha256": e2.fingerprint(commitment), "reserved_test_status": "not_opened"})
        elif args.stage == "compare-annotations":
            if args.student_annotations is None or args.student_receipt is None:
                raise ValueError("--student-annotations and the original --student-receipt are required for annotation comparison")
            record = e2.compare_annotations(args.student_annotations, args.student_receipt, args.language_manifest,
                                             args.annotation_id_map, args.test, args.parser_commitment,
                                             ROOT / "feedctrl/experiment2_controls.py", args.dev, categories, output,
                                             retry_attempt_path=args.retry_annotation_attempt, correction_reason=args.annotation_correction_reason)
            manifest.update({"status": "compared_before_adjudication", "agreement_record_sha256": e2.sha256_file(output / "agreement-before-adjudication.json"),
                             "annotation_access_status": "opened_for_annotation_only", "reserved_test_status": "not_opened_for_evaluation"})
            print(json.dumps({"stage": "agreement_before_adjudication", "agreement": record["agreement"]}), flush=True)
        elif args.stage == "dev":
            # Startup failure stops both parser comparisons rather than producing a fallback run.
            provenance = ollama_provenance(base_url=args.ollama_url, model=args.ollama_model, timeout=min(args.timeout, 10))
            manifest["llm_provenance"] = provenance
            cases = e2.load_cases(args.dev, expected_count=48)
            e2.validate_case_bank(cases, categories, 48)
            e2.write_new_json(output / "development_cases.json", cases)
            outcomes = e2.parse_cases(cases, categories, output, {**options, "cache_dir": str(output / "raw_llm_cache")})
            accuracy = e2.summarize_parser(outcomes, cases)
            e2.write_new_json(output / "parser_accuracy.json", accuracy)
            e2.write_new_json(output / "summary.json", {"status": "development_only", "parser_accuracy": accuracy, "reserved_test_status": "not_opened", "ranking_status": "not_run"})
            manifest.update({"status": "development_only", "parser_error_count": sum(r["error"] is not None for r in outcomes), "reserved_test_status": "not_opened"})
            print(json.dumps({"stage": "development_parser_accuracy", "accuracy": accuracy}), flush=True)
            exit_code = 2 if manifest["parser_error_count"] else 0
        elif args.stage == "replay" and args.cache_run is not None and e2.read_json(args.cache_run / "manifest.json").get("stage") == "dev":
            manifest.update(replay_development(args.cache_run.resolve(), output))
        else:
            student = gate(args)
            paths = artifact_paths(args)
            if args.stage == "freeze":
                if args.test.with_name("test.opened.json").exists():
                    raise ValueError("Test already opened; cannot create a new freeze")
                provenance = ollama_provenance(base_url=args.ollama_url, model=args.ollama_model, timeout=min(args.timeout, 10))
                receipt = e2.make_freeze_receipt(paths, categories, student, options, provenance)
                e2.write_new_json(output / "freeze-receipt.json", receipt)
                manifest.update({"status": "frozen_before_test", "freeze_receipt_sha256": e2.fingerprint(receipt), "llm_provenance": provenance})
            else:
                if args.freeze_receipt is None:
                    raise ValueError("--freeze-receipt is required for test or replay")
                receipt = e2.read_json(args.freeze_receipt)
                e2.verify_freeze_receipt(receipt, paths, categories, options)
                manifest["freeze_receipt_sha256"] = e2.fingerprint(receipt)
                if args.stage == "replay":
                    if args.cache_run is None:
                        raise ValueError("--cache-run is required for replay")
                    manifest.update(replay(args.cache_run.resolve(), output, receipt, paths, categories))
                    exit_code = 0 if manifest["status"] == "replayed" else 2
                else:
                    provenance = ollama_provenance(base_url=args.ollama_url, model=args.ollama_model, timeout=min(args.timeout, 10))
                    if provenance != receipt["llm_provenance"]:
                        raise ValueError("Frozen Ollama version or model digest changed")
                    manifest["llm_provenance"] = provenance
                    cases = e2.open_reserved_once(args.test, args.test.with_name("test.opened.json"), args.freeze_receipt, output,
                                                  receipt["artifacts"]["test_commitment"]["sha256"])
                    e2.validate_case_bank(cases, categories, 100, e2.read_json(args.language_manifest))
                    # Preserve author labels and actual student disagreement before applying final gold.
                    e2.write_new_json(output / "annotation_agreement.json", e2.annotation_agreement(cases, student))
                    e2.write_new_json(output / "original_author_cases.json", cases)
                    cases = [{**row, "gold": student["final_gold"][row["id"]]} for row in cases]
                    e2.validate_case_bank(cases, categories, 100, e2.read_json(args.language_manifest))
                    e2.write_new_json(output / "opened_cases.json", cases)
                    outcomes = e2.parse_cases(cases, categories, output, {**options, "cache_dir": str(output / "raw_llm_cache")})
                    accuracy = e2.summarize_parser(outcomes, cases)
                    e2.write_new_json(output / "parser_accuracy.json", accuracy)
                    # This output precedes every scoring or ranking operation.
                    print(json.dumps({"stage": "reserved_test_parser_accuracy", "accuracy": accuracy}), flush=True)
                    from feedctrl.model import load_model
                    models = {seed: load_model(args.models / f"seed_{seed}") for seed in e2.SEEDS}
                    rows, summary, requests, exclusions = e2.run_rankings(data, cases, outcomes, models)
                    save_rows(output, rows)
                    e2.write_new_json(output / "requests.json", requests)
                    e2.write_new_json(output / "exclusions.json", exclusions)
                    e2.write_new_json(output / "summary.json", summary)
                    errors = sum(r["error"] is not None for r in outcomes)
                    manifest.update({"status": "executed_with_parser_errors" if errors else "executed", "ranking_status": summary["status"],
                                     "parser_error_count": errors, "H1_status": "not_assessed" if summary["status"] == "not_run" else "passed" if summary["H1_passed"] else "not_demonstrated",
                                     "H2_status": "not_assessed" if summary["status"] == "not_run" else "passed" if summary["H2_passed"] else "not_demonstrated"})
                    exit_code = 2 if errors else 0
    except Exception as error:
        manifest.update({"status": "blocked" if args.stage in ("parser-freeze", "compare-annotations", "freeze", "test", "replay") else "unavailable_or_failed",
                         "error": f"{type(error).__name__}: {error}"})
        exit_code = 2
        print(json.dumps({"stage": args.stage, "status": manifest["status"], "error": manifest["error"]}), file=sys.stderr, flush=True)
    finally:
        manifest.update({"completed_utc": e2.utc_now(), "wall_seconds": time.monotonic() - started, "files": inventory(output)})
        e2.write_new_json(output / "manifest.json", manifest)
    print(json.dumps({"stage": args.stage, "status": manifest["status"], "output": str(output), "wall_seconds": manifest["wall_seconds"]}), flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
