"""Protected AI-reference custody; this module never runs a parser or inference.

CLI: python scripts/ai_e2_references.py {lock,compare,finalize} --root STUDY_ROOT
Run each stage once. A failed stage aborts this study version; outputs are exclusive.

Initial inputs: annotations/{tanishq,khushi}/{labels,receipt}.json. Labels are a
list of exactly {id, gold, rationale}. Receipt REQUIRED fields (additional
metadata is permitted):
  study_id, role, labels_sha256, source_sheet_sha256, finalized_utc,
  identity: {is_ai: true, agent_name, task_identity, fresh_context: true,
             model_id: "gpt-6.1-sol", reasoning_effort: "xhigh",
             model_metadata_source, exact_backend_weights: "unavailable"},
  exposure: {opened_inputs: [actual input paths/descriptions], declaration,
             parser_implementation_access: false, intent_plan_access: false,
             predictions_access: false, practice_or_development_access: false,
             other_initial_labels_access: false}.
Timestamps must be actual timezone-aware ISO 8601 finalization times, not human
annotation times. The source-sheet hash is annotations/ROLE/questions.json.

Only disputes are released in custody/disputes.json. A fresh adjudicator writes
custody/adjudication-decisions.json, a list of {id,gold,rationale}, and
custody/adjudication-receipt.json. Its receipt uses role="adjudicator", the same
identity/exposure fields, decisions_sha256 and source_packet_sha256 instead of
labels_sha256/source_sheet_sha256. For that role other_initial_labels_access
must be true, with initial_labels_scope="disputes_only". No adjudication input
or receipt is required when there are zero disputes.

The initial lock commits both original byte streams and both receipt byte
streams BEFORE reading label JSON. Originals are preserved as byte-identical
exclusive snapshots. Compare validates every label and receipt before computing
any agreement. Finalize checks final references against the LOCKED intent plan
only after adjudication; incompatibility/clarify aborts without coercion.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any

STUDY = "AIREF-E2-20261014-v1"
ROLES = ("tanishq", "khushi")
CATEGORIES = tuple(f"category_{n}" for n in range(31))
FIELDS = ("operation", "category", "strength", "floor", "condition_category")
REPO = Path(__file__).resolve().parents[1]
RUBRIC = REPO / "docs/ai-reference-e2-rubric-2026-10-14.md"
PROTOCOL = REPO / "docs/ai-reference-e2-protocol-2026-10-14.md"
PROMPTS = REPO / "docs/ai-reference-e2-role-prompts-2026-10-14.json"
CUSTODIAN = {
    "is_ai": True, "agent_name": "Vibhor", "task_identity": "/root/vibhor_custodian",
    "model_id": "gpt-6.1-sol", "reasoning_effort": "xhigh",
    "model_metadata_source": "inherited parent session model; no override",
    "exact_backend_weights": "unavailable",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def fingerprint(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def write_new_bytes(path: Path, blob: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(blob)
        handle.flush()
        os.fsync(handle.fileno())


def write_new(path: Path, value: Any) -> str:
    blob = (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    write_new_bytes(path, blob)
    return digest(blob)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def decode(blob: bytes) -> Any:
    def invalid_constant(value: str) -> None:
        raise ValueError(f"Invalid JSON constant: {value}")
    return json.loads(blob.decode("utf-8-sig"), object_pairs_hook=_unique_object,
                      parse_constant=invalid_constant)


def read_json(path: Path) -> Any:
    return decode(path.read_bytes())


def timestamp(value: Any, name: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{name}: ISO 8601 timestamp required")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name}: actual timezone-aware timestamp required")
    if parsed > datetime.now(timezone.utc):
        raise ValueError(f"{name}: finalization cannot be in the future")
    return parsed


def nonempty(value: Any, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name}: nonempty string required")


def canonical(command: Any, text: str) -> dict:
    """Strict frozen-rubric schema, without importing parser implementation."""
    if not isinstance(command, dict) or set(command) != {"operation", "directives"}:
        raise ValueError("gold must have exactly operation/directives")
    op, directives = command["operation"], command["directives"]
    if op not in ("set", "clarify") or not isinstance(directives, list):
        raise ValueError("Invalid request operation/directives")
    if (op == "clarify" and directives) or (op == "set" and not 1 <= len(directives) <= 2):
        raise ValueError("clarify requires zero directives; set requires one or two")
    mentioned = set(re.findall(r"\bcategory_\d+\b", text))
    cleaned = []
    targets = set()
    for directive in directives:
        if not isinstance(directive, dict) or set(directive) != set(FIELDS):
            raise ValueError("A directive must have exactly the five rubric fields")
        target, condition = directive["category"], directive["condition_category"]
        if not isinstance(target, str) or target not in CATEGORIES or target not in mentioned:
            raise ValueError("Target must be an allowed explicitly mentioned category")
        if target in targets:
            raise ValueError("Repeated directive target")
        targets.add(target)
        if condition is not None and (not isinstance(condition, str) or condition not in CATEGORIES
                                      or condition not in mentioned or condition == target):
            raise ValueError("Condition must be another allowed explicitly mentioned category")
        action, strength, floor = directive["operation"], directive["strength"], directive["floor"]
        if action not in ("boost", "reduce", "exclude"):
            raise ValueError("Invalid directive operation")
        if type(floor) is not int or floor not in (0, 1):
            raise ValueError("floor must be integer zero or one")
        if action == "exclude":
            if strength != "none" or floor != 0 or condition is not None:
                raise ValueError("exclude requires none/zero/null")
        else:
            if strength not in ("slight", "moderate", "strong"):
                raise ValueError("Invalid boost/reduce strength")
            if floor and action != "reduce":
                raise ValueError("Only reduction may have a floor")
            if condition is not None and action != "boost":
                raise ValueError("Only boost may have same-item condition")
        cleaned.append({field: directive[field] for field in FIELDS})
    return {"operation": op, "directives": sorted(cleaned, key=lambda row: int(row["category"][9:]))}


def validate_questions(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"categories", "questions"}:
        raise ValueError("Question sheet must contain only public categories/questions")
    if value["categories"] != list(CATEGORIES) or not isinstance(value["questions"], list):
        raise ValueError("Question sheet vocabulary/schema mismatch")
    questions = {}
    for row in value["questions"]:
        if not isinstance(row, dict) or set(row) != {"id", "text"}:
            raise ValueError("Question row must contain only id/text")
        case_id, text = row["id"], row["text"]
        if not isinstance(case_id, str) or not re.fullmatch(r"q_[0-9a-f]{12}", case_id) or case_id in questions:
            raise ValueError("Invalid/duplicate opaque ID")
        nonempty(text, "question text")
        questions[case_id] = text
    if len(questions) != 100:
        raise ValueError("Exactly all 100 question IDs required")
    return questions


def validate_rows(value: Any, questions: dict[str, str], expected_ids: set[str]) -> tuple[dict, dict]:
    if not isinstance(value, list):
        raise ValueError("Annotation/decision file must be a JSON list")
    originals, golds = {}, {}
    for row in value:
        if not isinstance(row, dict) or set(row) != {"id", "gold", "rationale"}:
            raise ValueError("Every annotation/decision needs exactly id/gold/rationale")
        case_id = row["id"]
        if not isinstance(case_id, str) or case_id not in expected_ids or case_id in originals:
            raise ValueError("Annotation/decision has an unexpected or duplicate ID")
        nonempty(row["rationale"], "rationale")
        golds[case_id] = canonical(row["gold"], questions[case_id])
        originals[case_id] = row
    if set(originals) != expected_ids:
        raise ValueError("Annotation/decision must cover exactly every assigned ID")
    return originals, golds


def validate_receipt(value: Any, role: str, label_hash: str, sheet_hash: str,
                     locked_utc: str | None = None) -> None:
    if not isinstance(value, dict) or value.get("study_id") != STUDY or value.get("role") != role:
        raise ValueError("Receipt study/role mismatch")
    label_key = "decisions_sha256" if role == "adjudicator" else "labels_sha256"
    sheet_key = "source_packet_sha256" if role == "adjudicator" else "source_sheet_sha256"
    if value.get(label_key) != label_hash or value.get(sheet_key) != sheet_hash:
        raise ValueError("Receipt label/source byte hash mismatch")
    finalized = timestamp(value.get("finalized_utc"), "receipt finalized_utc")
    if locked_utc is not None and finalized > timestamp(locked_utc, "initial locked_utc"):
        raise ValueError("Initial annotation receipt postdates the pre-comparison lock")
    identity = value.get("identity")
    if not isinstance(identity, dict) or identity.get("is_ai") is not True or identity.get("fresh_context") is not True:
        raise ValueError("Truthful AI/fresh-context identity required")
    for field in ("agent_name", "task_identity", "model_metadata_source"):
        nonempty(identity.get(field), f"identity.{field}")
    if identity["agent_name"].casefold() != role:
        raise ValueError("AI role identity mismatch")
    if (identity.get("model_id"), identity.get("reasoning_effort"), identity.get("exact_backend_weights")) != (
            "gpt-6.1-sol", "xhigh", "unavailable"):
        raise ValueError("Actual inherited model provenance must be recorded without invented weights")
    exposure = value.get("exposure")
    if not isinstance(exposure, dict):
        raise ValueError("Exposure declaration required")
    nonempty(exposure.get("declaration"), "exposure.declaration")
    opened = exposure.get("opened_inputs")
    if not isinstance(opened, list) or not opened or any(not isinstance(p, str) or not p.strip() for p in opened):
        raise ValueError("List actual opened inputs")
    for field in ("parser_implementation_access", "intent_plan_access", "predictions_access", "practice_or_development_access"):
        if exposure.get(field) is not False:
            raise ValueError(f"Role exposure violation or incomplete declaration: {field}")
    if role == "adjudicator":
        if exposure.get("other_initial_labels_access") is not True or exposure.get("initial_labels_scope") != "disputes_only":
            raise ValueError("Adjudicator must declare access only to disputed initial labels")
    elif exposure.get("other_initial_labels_access") is not False:
        raise ValueError("Initial labels must be independently authored without cross-label access")


def paths(root: Path) -> dict[str, Path]:
    result = {
        "protocol_freeze": root / "protocol/protocol-freeze.json",
        "protocol": PROTOCOL, "rubric": RUBRIC, "role_prompts": PROMPTS,
        "bank_code": REPO / "scripts/ai_e2_bank.py", "custodian_code": Path(__file__).resolve(),
        "bank_lock": root / "custody/bank-lock.json", "master": root / "custody/questions-master.json",
        "intent_plan": root / "custody/intent-plan.json",
    }
    for role in ROLES:
        for kind, filename in (("sheet", "questions"), ("labels", "labels"), ("receipt", "receipt")):
            result[f"{role}_{kind}"] = root / f"annotations/{role}/{filename}.json"
    return result


def lock(root: Path) -> dict:
    """Hash/copy both labels and receipts before any label JSON is decoded."""
    inputs = paths(root)
    blobs = {name: path.read_bytes() for name, path in inputs.items()}
    records = {name: {"path": str(path.resolve()), "sha256": digest(blobs[name]), "bytes": len(blobs[name])}
               for name, path in inputs.items()}
    for role in ROLES:
        for kind in ("labels", "receipt"):
            name = f"{role}_{kind}"
            snapshot = root / f"custody/initial-originals/{role}-{kind}.json"
            write_new_bytes(snapshot, blobs[name])
            records[name]["snapshot_path"] = str(snapshot.resolve())
    for name, path in inputs.items():
        if digest(path.read_bytes()) != records[name]["sha256"]:
            raise ValueError("An input changed while its initial hash lock was being written")
    record = {"study_id": STUDY, "locked_utc": now(), "status": "both_initial_AI_label_and_receipt_bytes_locked_before_comparison",
              "custodian": CUSTODIAN, "inputs": records}
    output_hash = write_new(root / "custody/initial-label-lock.json", record)
    return {"stage": "lock", "initial_label_files": 2, "initial_receipts": 2,
            "label_contents_compared": False, "initial_lock_sha256": output_hash}


def committed_inputs(root: Path) -> tuple[dict, dict[str, bytes]]:
    record = read_json(root / "custody/initial-label-lock.json")
    if record.get("study_id") != STUDY or set(record.get("inputs", {})) != set(paths(root)):
        raise ValueError("Incomplete initial input lock")
    blobs = {}
    for name, path in paths(root).items():
        item = record["inputs"][name]
        if item.get("path") != str(path.resolve()):
            raise ValueError("Initial input path changed")
        blob = path.read_bytes()
        if digest(blob) != item.get("sha256") or len(blob) != item.get("bytes"):
            raise ValueError(f"Locked input bytes changed: {name}")
        if "snapshot_path" in item and Path(item["snapshot_path"]).read_bytes() != blob:
            raise ValueError("Preserved initial annotation/receipt bytes changed")
        blobs[name] = blob
    return record, blobs


def validated_initial(root: Path) -> tuple[dict, dict[str, bytes], dict, dict, dict, dict]:
    record, blobs = committed_inputs(root)
    questions = validate_questions(decode(blobs["master"]))
    bank = decode(blobs["bank_lock"])
    if (bank.get("n") != 100 or bank.get("question_master_sha256") != digest(blobs["master"])
            or bank.get("intent_plan_sha256") != digest(blobs["intent_plan"])):
        raise ValueError("Bank lock/master/intent byte commitment mismatch")
    originals, labels, receipts = {}, {}, {}
    for role in ROLES:
        sheet = validate_questions(decode(blobs[f"{role}_sheet"]))
        if sheet != questions or bank.get("sheets", {}).get(role) != digest(blobs[f"{role}_sheet"]):
            raise ValueError("Annotator did not receive the locked exact question texts")
        receipts[role] = decode(blobs[f"{role}_receipt"])
        validate_receipt(receipts[role], role, digest(blobs[f"{role}_labels"]),
                         digest(blobs[f"{role}_sheet"]), record["locked_utc"])
        originals[role], labels[role] = validate_rows(decode(blobs[f"{role}_labels"]), questions, set(questions))
    if receipts[ROLES[0]]["identity"]["task_identity"] == receipts[ROLES[1]]["identity"]["task_identity"]:
        raise ValueError("Independent initial labels need distinct actual agent task identities")
    return record, blobs, questions, originals, labels, receipts


def kappa(left: list, right: list) -> tuple[float | None, float, str | None]:
    n = len(left)
    observed = sum(a == b for a, b in zip(left, right)) / n
    a_count, b_count = Counter(left), Counter(right)
    expected = sum(a_count[x] * b_count[x] for x in set(a_count) | set(b_count)) / (n * n)
    return ((observed - expected) / (1 - expected) if expected < 1 else None,
            expected, "expected agreement is one" if expected == 1 else None)


def agreement(left: dict, right: dict, receipts: dict) -> dict:
    ids = sorted(left)
    n = len(ids)
    full_left, full_right = [fingerprint(left[i]) for i in ids], [fingerprint(right[i]) for i in ids]
    full_n = sum(a == b for a, b in zip(full_left, full_right))
    full_kappa, full_expected, full_reason = kappa(full_left, full_right)
    counts_left, counts_right = [len(left[i]["directives"]) for i in ids], [len(right[i]["directives"]) for i in ids]
    count_n = sum(a == b for a, b in zip(counts_left, counts_right))
    count_kappa, count_expected, count_reason = kappa(counts_left, counts_right)
    fields = {field: 0 for field in FIELDS}
    denominator, same_targets, same_operations = 0, 0, 0
    for case_id in ids:
        a = {d["category"]: d for d in left[case_id]["directives"]}
        b = {d["category"]: d for d in right[case_id]["directives"]}
        same_targets += set(a) == set(b)
        same_operations += left[case_id]["operation"] == right[case_id]["operation"]
        denominator += len(set(a) | set(b))
        for target in set(a) & set(b):
            for field in FIELDS:
                fields[field] += a[target][field] == b[target][field]
    return {"study_id": STUDY, "computed_utc": now(), "status": "actual_independent_AI_context_reference_annotations",
            "provenance": {role: receipts[role]["identity"] for role in ROLES},
            "interpretation": "Descriptive rubric agreement among separate AI contexts sharing a model family; not human ground truth or independent model training.",
            "n": n, "full_command_exact_agreement": full_n / n,
            "full_command_exact_agreement_numerator": full_n, "full_command_exact_agreement_denominator": n,
            "cohens_kappa": full_kappa, "full_command_expected_chance_agreement": full_expected,
            "kappa_undefined_reason": full_reason,
            "directive_count_agreement": count_n / n, "directive_count_agreement_numerator": count_n,
            "directive_count_agreement_denominator": n, "directive_count_cohens_kappa": count_kappa,
            "directive_count_expected_chance_agreement": count_expected, "directive_count_kappa_undefined_reason": count_reason,
            "field_agreement": {f: fields[f] / denominator if denominator else None for f in FIELDS},
            "field_agreement_counts": fields, "field_comparison_count": denominator,
            "field_alignment": "union of target category IDs per case; a missing directive disagrees on every field",
            "category_field_interpretation": "Target-aligned category agreement is partly tautological, not semantic accuracy.",
            "request_operation_agreement": same_operations / n, "request_operation_agreement_numerator": same_operations,
            "request_operation_agreement_denominator": n, "target_category_set_agreement": same_targets / n,
            "target_category_set_agreement_numerator": same_targets, "target_category_set_agreement_denominator": n,
            "disagreement_ids": [i for i in ids if left[i] != right[i]], "acceptance_cutoff": None}


def packet_for(record: dict, questions: dict, originals: dict, disputed: list[str]) -> dict:
    return {"study_id": STUDY, "role": "fresh_AI_adjudicator", "created_utc": now(),
            "rubric": {"path": record["inputs"]["rubric"]["path"], "sha256": record["inputs"]["rubric"]["sha256"]},
            "locked_initial_labels_sha256": {r: record["inputs"][f"{r}_labels"]["sha256"] for r in ROLES},
            "dispute_count": len(disputed),
            "disputes": [{"id": i, "text": questions[i], "initial_AI_annotations": {r: originals[r][i] for r in ROLES}}
                         for i in disputed]}


def compare(root: Path) -> dict:
    record, _, questions, originals, labels, receipts = validated_initial(root)
    result = agreement(labels[ROLES[0]], labels[ROLES[1]], receipts)
    disputed = result["disagreement_ids"]
    agreement_hash = write_new(root / "custody/agreement.json", result)
    packet_hash = write_new(root / "custody/disputes.json", packet_for(record, questions, originals, disputed))
    comparison_lock = {"study_id": STUDY, "locked_utc": now(), "initial_lock_sha256": digest((root / "custody/initial-label-lock.json").read_bytes()),
                       "agreement_sha256": agreement_hash, "disputes_sha256": packet_hash,
                       "n": 100, "exact_agreements": 100 - len(disputed), "disputes": len(disputed)}
    comparison_hash = write_new(root / "custody/comparison-lock.json", comparison_lock)
    return {"stage": "compare", "n": 100, "exact_agreements": 100 - len(disputed), "disputes": len(disputed),
            "agreement_sha256": agreement_hash, "disputes_sha256": packet_hash, "comparison_lock_sha256": comparison_hash}


def expected_command(slot: dict, text: str) -> dict:
    target, secondary, subtype = slot["target"], slot["secondary"], slot["subtype"]
    def directive(operation: str, category: str, strength: str, floor: int = 0, condition: str | None = None) -> dict:
        return dict(zip(FIELDS, (operation, category, strength, floor, condition)))
    if slot["class"] == "compound" and subtype == "compound":
        directives = [directive("boost", target, "moderate"), directive("reduce", secondary, "moderate")]
    elif slot["class"] == "graded" and subtype in ("slight_boost", "strong_reduction", "exclusion"):
        operation, strength = {"slight_boost": ("boost", "slight"), "strong_reduction": ("reduce", "strong"), "exclusion": ("exclude", "none")}[subtype]
        directives = [directive(operation, target, strength)]
    elif slot["class"] == "floor" and subtype == "floor":
        directives = [directive("reduce", target, "moderate", 1)]
    elif slot["class"] == "conditional" and subtype == "conditional":
        directives = [directive("boost", target, "moderate", condition=secondary)]
    else:
        raise ValueError("Locked plan has an invalid class/subtype")
    return canonical({"operation": "set", "directives": directives}, text)


def validate_plan(value: Any, questions: dict) -> list[dict]:
    if not isinstance(value, dict) or value.get("study_id") != STUDY or value.get("seed") != 20261014:
        raise ValueError("Intent plan provenance mismatch")
    slots = value.get("slots")
    if not isinstance(slots, list) or len(slots) != 100:
        raise ValueError("Locked plan must have exactly 100 slots")
    ids = set()
    for index, slot in enumerate(slots, 1):
        if not isinstance(slot, dict) or set(slot) != {"slot", "id", "class", "target", "secondary", "subtype"}:
            raise ValueError("Locked intent slot schema mismatch")
        expected_id = "q_" + digest(f"{STUDY}:slot:{index}".encode())[:12]
        if slot["slot"] != index or slot["id"] != expected_id or slot["id"] in ids:
            raise ValueError("Locked intent slot/opaque ID mismatch")
        ids.add(slot["id"])
        if slot["target"] not in CATEGORIES or slot["class"] != ("compound", "graded", "floor", "conditional")[(index - 1) // 25]:
            raise ValueError("Locked intent class/target mismatch")
        if slot["class"] in ("compound", "conditional"):
            if slot["secondary"] not in CATEGORIES or slot["secondary"] == slot["target"]:
                raise ValueError("Locked secondary category mismatch")
        elif slot["secondary"] is not None:
            raise ValueError("Unexpected secondary category in locked plan")
    if ids != set(questions) or {s["target"] for s in slots} != set(CATEGORIES):
        raise ValueError("Plan IDs/target coverage mismatch")
    if Counter(s["subtype"] for s in slots if s["class"] == "graded") != Counter({"slight_boost": 9, "strong_reduction": 8, "exclusion": 8}):
        raise ValueError("Locked graded subtype counts mismatch")
    return slots


def finalize(root: Path) -> dict:
    record, blobs, questions, originals, labels, receipts = validated_initial(root)
    comparison = read_json(root / "custody/comparison-lock.json")
    if comparison.get("initial_lock_sha256") != digest((root / "custody/initial-label-lock.json").read_bytes()):
        raise ValueError("Initial/comparison lock mismatch")
    agreement_blob, packet_blob = (root / "custody/agreement.json").read_bytes(), (root / "custody/disputes.json").read_bytes()
    if digest(agreement_blob) != comparison.get("agreement_sha256") or digest(packet_blob) != comparison.get("disputes_sha256"):
        raise ValueError("Comparison/dispute packet bytes changed")
    saved_agreement = decode(agreement_blob)
    recomputed = agreement(labels[ROLES[0]], labels[ROLES[1]], receipts)
    recomputed["computed_utc"] = saved_agreement.get("computed_utc")
    if saved_agreement != recomputed:
        raise ValueError("Saved agreement is not reproducible from locked initial labels")
    disputed = recomputed["disagreement_ids"]
    packet, expected_packet = decode(packet_blob), packet_for(record, questions, originals, disputed)
    expected_packet["created_utc"] = packet.get("created_utc")
    if packet != expected_packet:
        raise ValueError("Adjudicator packet includes altered or unexpected material")
    decisions, adjudicated, adjudicator_receipt, adjudication_sources = {}, {}, None, {}
    decision_path, receipt_path = root / "custody/adjudication-decisions.json", root / "custody/adjudication-receipt.json"
    if disputed:
        decision_blob, receipt_blob = decision_path.read_bytes(), receipt_path.read_bytes()
        adjudicator_receipt = decode(receipt_blob)
        validate_receipt(adjudicator_receipt, "adjudicator", digest(decision_blob), digest(packet_blob))
        if adjudicator_receipt["identity"]["task_identity"] in {receipts[r]["identity"]["task_identity"] for r in ROLES} | {CUSTODIAN["task_identity"]}:
            raise ValueError("Adjudicator must have a fresh distinct actual task identity")
        if timestamp(adjudicator_receipt["finalized_utc"], "adjudication finalized_utc") < timestamp(comparison["locked_utc"], "comparison locked_utc"):
            raise ValueError("Adjudication receipt predates its dispute packet commitment")
        decisions, adjudicated = validate_rows(decode(decision_blob), questions, set(disputed))
        adjudication_sources = {"decisions": {"path": str(decision_path.resolve()), "sha256": digest(decision_blob)},
                                "receipt": {"path": str(receipt_path.resolve()), "sha256": digest(receipt_blob)}}
    elif decision_path.exists() or receipt_path.exists():
        raise ValueError("Zero-dispute bank requires no adjudication files; do not add unrelated decisions")
    final = {i: (adjudicated[i] if i in adjudicated else labels[ROLES[0]][i]) for i in questions}
    slots = validate_plan(decode(blobs["intent_plan"]), questions)
    incompatible = []
    for slot in slots:
        case_id = slot["id"]
        expected = expected_command(slot, questions[case_id])
        if final[case_id] != expected:
            incompatible.append({"id": case_id, "reason": "clarify" if final[case_id]["operation"] == "clarify" else "final_reference_does_not_exactly_match_locked_subtype_target_secondary_requirements"})
    if incompatible:
        write_new(root / "custody/reference-compatibility-failure.json", {"study_id": STUDY, "checked_utc": now(), "status": "aborted_before_inference_no_coercion",
                  "incompatible_count": len(incompatible), "issues": incompatible,
                  "required_disposition": "Separate pre-inference bank/protocol version and new independent annotation required; preserve all original evidence."})
        raise ValueError("Final reference compatibility failed for IDs: " + ",".join(row["id"] for row in incompatible))
    # Assign class only after the exact compatibility pass. The gold is always
    # the actual agreed/adjudicated annotation, never a substituted intent label.
    cases = [{"id": s["id"], "text": questions[s["id"]], "class": s["class"], "gold": final[s["id"]]} for s in slots]
    retained = []
    for case in cases:
        case_id = case["id"]
        resolution = "exact_initial_agreement"
        if case_id in adjudicated:
            resolution = ("clarify" if final[case_id]["operation"] == "clarify" else
                          "tanishq_label" if final[case_id] == labels["tanishq"][case_id] else
                          "khushi_label" if final[case_id] == labels["khushi"][case_id] else "corrected_rubric_label")
        retained.append({"id": case_id, "original_AI_annotations": {r: originals[r][case_id] for r in ROLES},
                         "adjudication": decisions.get(case_id), "resolution": resolution, "final_canonical_gold": final[case_id]})
    cases_hash = write_new(root / "custody/final-cases.json", cases)
    provenance_hash = write_new(root / "custody/final-reference-provenance.json", {
        "study_id": STUDY, "created_utc": now(), "custodian": CUSTODIAN, "initial_receipts": receipts,
        "adjudicator_receipt": adjudicator_receipt, "records": retained})
    source_hashes = {name: {"path": item["path"], "sha256": item["sha256"]} for name, item in record["inputs"].items()}
    source_hashes.update({"initial_lock": {"sha256": digest((root / "custody/initial-label-lock.json").read_bytes())},
                         "comparison_lock": {"sha256": digest((root / "custody/comparison-lock.json").read_bytes())},
                         "agreement": {"sha256": digest(agreement_blob)}, "disputes": {"sha256": digest(packet_blob)},
                         **{f"adjudication_{k}": v for k, v in adjudication_sources.items()}})
    frozen = {"study_id": STUDY, "frozen_utc": now(), "status": "final_AI_references_frozen_before_inference",
              "custodian": CUSTODIAN, "n": 100, "exact_initial_agreements": 100 - len(disputed), "adjudications": len(disputed),
              "initial_label_status": "both_hashes_locked_before_any_comparison_original_bytes_retained",
              "compatibility_status": "all_100_final_canonical_labels_exactly_match_locked_subtype_and_target_roles",
              "annotation_provenance": "AI references from separate contexts of a shared model family; no human annotation claim",
              "class_counts": dict(Counter(row["class"] for row in cases)), "source_hashes": source_hashes,
              "final_hashes": {"final_cases": {"path": str((root / "custody/final-cases.json").resolve()), "sha256": cases_hash},
                               "reference_provenance": {"path": str((root / "custody/final-reference-provenance.json").resolve()), "sha256": provenance_hash}}}
    freeze_hash = write_new(root / "custody/reference-freeze.json", frozen)
    return {"stage": "finalize", "n": 100, "exact_initial_agreements": 100 - len(disputed), "adjudications": len(disputed),
            "class_counts": frozen["class_counts"], "compatibility_failures": 0, "final_cases_sha256": cases_hash,
            "reference_freeze_sha256": freeze_hash}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("stage", choices=("lock", "compare", "finalize"))
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    aborted = root / "custody/references-aborted.json"
    if aborted.exists():
        raise ValueError("This reference version is aborted; preserve it and record a separately authorized new version")
    # Exclusive start markers prevent silently resuming a partial custody stage.
    marker = root / f"custody/reference-{args.stage}-started.json"
    write_new(marker, {"study_id": STUDY, "stage": args.stage, "started_utc": now(), "custodian": CUSTODIAN})
    try:
        result = {"lock": lock, "compare": compare, "finalize": finalize}[args.stage](root)
        result.update({"study_id": STUDY, "completed_utc": now(), "custodian": CUSTODIAN})
        write_new(root / f"custody/reference-{args.stage}-receipt.json", result)
    except Exception as error:
        write_new(aborted, {"study_id": STUDY, "stage": args.stage, "aborted_utc": now(), "error_type": type(error).__name__,
                           "error": str(error), "status": "aborted_before_further_comparison_or_inference_preserve_all_evidence"})
        raise
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
