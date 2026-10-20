"""Independent post-commit AIREF E2 audit; no project imports or model calls.

Preparation of this file does not authorize its execution. Run only after the
200 predictions are immutable and protected scoring has completed. The required
manifest/prompt/schema hashes must come from the recorded commitments, not be
chosen by inspecting outcomes. This auditor evaluates saved rankings; it does
not independently train SASRec or reimplement the language-control ranker.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import sys
import traceback

STUDY = "AIREF-E2-20261014-v1"
CLASSES = ("compound", "graded", "floor", "conditional")
SEEDS = (42, 43, 44)
CONDITIONS = ("A", "rule", "llm", "recency")
BACKENDS = ("rule_compound", "ollama_compound")
FIELDS = ("operation", "category", "strength", "floor", "condition_category")
METRICS = ("induced_success", "intended_movement", "hr1", "ndcg_at_10",
           "band_satisfied", "baseline_already_satisfies")
CATEGORIES = [f"category_{i}" for i in range(31)]
OPTIONS = {"temperature": 0, "seed": 42, "num_ctx": 4096,
           "num_predict": 768, "num_thread": 6}
MODEL = {"model": "llama3.1:8b", "digest":
         "46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e",
         "ollama_version": "0.34.0"}
RELEASE_FIELDS = {"study_id", "status", "frozen_utc", "questions_sha256", "model",
                  "options", "worker_source_sha256", "denied_probe_paths",
                  "reference_freeze_sha256", "protocol_freeze_sha256", "timeout_seconds"}
SOURCE_PATHS = {"scripts/ai_e2_inference_worker.py", "feedctrl/__init__.py",
                "feedctrl/controls.py", "feedctrl/experiment2_controls.py"}


def stamp():
    return datetime.now(timezone.utc).isoformat()


def stable(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False)


def fingerprint(value):
    return hashlib.sha256(stable(value).encode("utf-8")).hexdigest()


def timestamp(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Naive evidence timestamp")
    return result


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def canonical(value, *, metadata=False):
    if not isinstance(value, dict):
        raise ValueError("Command must be an object")
    command = {k: v for k, v in value.items() if not (metadata and k == "source")}
    if set(command) != {"operation", "directives"}:
        raise ValueError("Unexpected command fields")
    operation, directives = command["operation"], command["directives"]
    if not isinstance(directives, list) or operation not in ("set", "clarify"):
        raise ValueError("Invalid request operation/directives")
    if (operation == "clarify" and directives) or (operation == "set" and len(directives) not in (1, 2)):
        raise ValueError("Invalid directive count")
    result, targets = [], set()
    for directive in directives:
        if not isinstance(directive, dict) or set(directive) != set(FIELDS):
            raise ValueError("Unexpected directive fields")
        d = dict(directive)
        op, category, strength, floor, condition = (d[k] for k in FIELDS)
        if category not in CATEGORIES or category in targets or type(floor) is not int or floor not in (0, 1):
            raise ValueError("Invalid target/floor")
        if condition is not None and (condition not in CATEGORIES or condition == category):
            raise ValueError("Invalid condition")
        if op == "exclude":
            if strength != "none" or floor != 0 or condition is not None:
                raise ValueError("Invalid exclusion")
        elif op not in ("boost", "reduce") or strength not in ("slight", "moderate", "strong"):
            raise ValueError("Invalid operation/strength")
        if (floor and op != "reduce") or (condition is not None and op != "boost"):
            raise ValueError("Invalid floor/condition combination")
        targets.add(category)
        result.append(d)
    return {"operation": operation, "directives": sorted(result, key=lambda d: int(d["category"].split("_")[-1]))}


class Audit:
    def __init__(self):
        self.checks = 0
        self.failure_count = 0
        self.failures = []
        self.inputs = {}

    def check(self, condition, message):
        self.checks += 1
        if not condition:
            self.failure_count += 1
            if len(self.failures) < 1000:
                self.failures.append(message)
        return bool(condition)

    def require(self, condition, message):
        if not self.check(condition, message):
            raise ValueError(message)

    def sha(self, path):
        path = Path(path).resolve()
        h = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                h.update(block)
        value = h.hexdigest()
        self.inputs[str(path)] = value
        return value

    def read(self, path):
        path = Path(path).resolve()
        blob = path.read_bytes()
        self.inputs[str(path)] = hashlib.sha256(blob).hexdigest()
        return json.loads(blob.decode("utf-8-sig"), object_pairs_hook=unique_object,
                          parse_constant=lambda x: (_ for _ in ()).throw(ValueError("Nonfinite JSON: " + x)))

    def same(self, actual, expected, label):
        if isinstance(expected, dict):
            self.check(isinstance(actual, dict), label + " object")
            if isinstance(actual, dict):
                for key, value in expected.items():
                    self.check(key in actual, label + " missing " + key)
                    if key in actual:
                        self.same(actual[key], value, label + "/" + key)
        elif isinstance(expected, (list, tuple)):
            self.check(isinstance(actual, (list, tuple)) and len(actual) == len(expected), label + " length")
            if isinstance(actual, (list, tuple)) and len(actual) == len(expected):
                for index, (a, b) in enumerate(zip(actual, expected)):
                    self.same(a, b, label + "/" + str(index))
        elif type(expected) is float:
            self.check(type(actual) in (int, float) and math.isfinite(actual)
                       and math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-12), label)
        else:
            self.check(actual == expected, label)

    def inventory(self, directory, manifest):
        directory = Path(directory).resolve()
        actual = {p.relative_to(directory).as_posix() for p in directory.rglob("*") if p.is_file()}
        committed = {Path(p).as_posix() for p in manifest["files"]}
        self.require(actual == committed | {"manifest.json"}, "Exact evidence inventory " + str(directory))
        for name, digest in manifest["files"].items():
            path = (directory / name).resolve()
            self.require(path.is_relative_to(directory), "Manifest path escapes directory")
            self.require(self.sha(path) == digest, "Manifest digest " + str(path))


def questions(audit, value, label):
    audit.require(set(value) == {"categories", "questions"} and value["categories"] == CATEGORIES,
                  "Question-only envelope " + label)
    rows = value["questions"]
    audit.require(isinstance(rows, list) and len(rows) == 100, "Question denominator " + label)
    audit.require(all(set(r) == {"id", "text"} and re.fullmatch(r"q_[0-9a-f]{12}", r["id"])
                      and isinstance(r["text"], str) and r["text"].strip() for r in rows), "Question row schema " + label)
    mapping = {r["id"]: r["text"] for r in rows}
    audit.require(len(mapping) == len(set(mapping.values())) == 100, "Question uniqueness " + label)
    return rows, mapping


def kappa(left, right):
    n = len(left)
    a, b = Counter(left), Counter(right)
    observed = sum(x == y for x, y in zip(left, right)) / n
    chance = sum(a[x] * b[x] for x in a.keys() | b.keys()) / (n * n)
    return (None if chance == 1 else (observed - chance) / (1 - chance)), chance


def independent_agreement(left, right):
    ids = sorted(left)
    n = len(ids)
    exact = sum(left[i] == right[i] for i in ids)
    ks, chance = kappa([stable(left[i]) for i in ids], [stable(right[i]) for i in ids])
    ls, rs = [len(left[i]["directives"]) for i in ids], [len(right[i]["directives"]) for i in ids]
    kc, cc = kappa(ls, rs)
    counts, total, targets, operations = Counter({f: 0 for f in FIELDS}), 0, 0, 0
    for i in ids:
        a = {d["category"]: d for d in left[i]["directives"]}
        b = {d["category"]: d for d in right[i]["directives"]}
        total += len(a.keys() | b.keys())
        targets += a.keys() == b.keys()
        operations += left[i]["operation"] == right[i]["operation"]
        for target in a.keys() & b.keys():
            for field in FIELDS:
                counts[field] += a[target][field] == b[target][field]
    size_matches = sum(a == b for a, b in zip(ls, rs))
    return {"n": n, "full_command_exact_agreement": exact / n,
            "full_command_exact_agreement_numerator": exact, "full_command_exact_agreement_denominator": n,
            "cohens_kappa": ks, "full_command_expected_chance_agreement": chance,
            "kappa_undefined_reason": "expected agreement is one" if ks is None else None,
            "directive_count_agreement": size_matches / n,
            "directive_count_agreement_numerator": size_matches, "directive_count_agreement_denominator": n,
            "directive_count_cohens_kappa": kc, "directive_count_expected_chance_agreement": cc,
            "directive_count_kappa_undefined_reason": "expected agreement is one" if kc is None else None,
            "field_agreement": {f: counts[f] / total if total else None for f in FIELDS},
            "field_agreement_counts": dict(counts), "field_comparison_count": total,
            "request_operation_agreement": operations / n, "request_operation_agreement_numerator": operations,
            "request_operation_agreement_denominator": n, "target_category_set_agreement": targets / n,
            "target_category_set_agreement_numerator": targets, "target_category_set_agreement_denominator": n,
            "disagreement_ids": [i for i in ids if left[i] != right[i]], "acceptance_cutoff": None}


def read_labels(audit, rows, texts, expected_ids, label):
    audit.require(isinstance(rows, list) and len(rows) == len(expected_ids), "Label denominator " + label)
    original = {r["id"]: r for r in rows}
    audit.require(len(original) == len(rows) and set(original) == set(expected_ids), "Label coverage " + label)
    result = {}
    for i, row in original.items():
        audit.require(set(row) == {"id", "gold", "rationale"} and isinstance(row["rationale"], str)
                      and row["rationale"].strip(), "Initial label fields " + label)
        result[i] = canonical(row["gold"])
        refs = {c for d in result[i]["directives"] for c in (d["category"], d["condition_category"]) if c is not None}
        audit.check(refs <= set(re.findall(r"\bcategory_\d+\b", texts[i])), "Unmentioned label categories " + i)
    return original, result


def verify_freeze(audit, study, repo, release, opened):
    protocol_path, full_path = study / "protocol/protocol-freeze.json", study / "custody/full-freeze.json"
    protocol, full = audit.read(protocol_path), audit.read(full_path)
    audit.require(protocol["study_id"] == full["study_id"] == STUDY, "Study IDs")
    audit.require(protocol["status"] == "protocol_frozen_before_authoring"
                  and full["status"] == "frozen_before_inference", "Freeze statuses")
    audit.check(audit.sha(protocol_path) == release["protocol_freeze_sha256"], "Protocol/release linkage")
    audit.check(timestamp(protocol["frozen_utc"]) <= timestamp(full["frozen_utc"]) <= opened, "Freeze chronology")
    for name, digest in protocol["source_sha256"].items():
        audit.require(audit.sha(repo / name) == digest, "Pre-authoring source hash " + name)
        audit.require(audit.sha(study / "protocol/source" / name) == digest, "Frozen source snapshot " + name)
    for name, digest in protocol["input_sha256"].items():
        audit.require(audit.sha(Path(name)) == digest, "Pre-authoring input hash " + name)
    for name, digest in full["files"].items():
        audit.require(Path(name).is_absolute() and audit.sha(Path(name)) == digest, "Full-freeze hash " + name)
    for required in (protocol_path, study / "custody/reference-freeze.json", study / "custody/final-cases.json",
                     study / "custody/agreement.json", study / "custody/initial-label-lock.json",
                     study / "inference/worker-bundle/release.json", Path(__file__).resolve()):
        audit.require(full["files"].get(str(required.resolve())) == audit.sha(required), "Required full-freeze member " + str(required))
    return protocol, full


def verify_references(audit, study, texts):
    lock = audit.read(study / "custody/initial-label-lock.json")
    comparison = audit.read(study / "custody/comparison-lock.json")
    reference = audit.read(study / "custody/reference-freeze.json")
    audit.require(lock["study_id"] == comparison["study_id"] == reference["study_id"] == STUDY, "Reference study IDs")
    audit.check(lock["status"] == "both_initial_AI_label_and_receipt_bytes_locked_before_comparison", "Initial lock status")
    audit.check(reference["status"] == "final_AI_references_frozen_before_inference", "Reference freeze status")
    for name, item in lock["inputs"].items():
        path = Path(item["path"])
        audit.require(audit.sha(path) == item["sha256"] and path.stat().st_size == item["bytes"], "Initial locked bytes " + name)
        if "snapshot_path" in item:
            audit.require(audit.sha(Path(item["snapshot_path"])) == item["sha256"], "Original snapshot " + name)
    audit.check(comparison["initial_lock_sha256"] == audit.sha(study / "custody/initial-label-lock.json"), "Comparison initial lock")
    for key, filename in (("agreement_sha256", "agreement.json"), ("disputes_sha256", "disputes.json")):
        audit.check(comparison[key] == audit.sha(study / "custody" / filename), "Comparison bytes " + key)
    fallback = {"initial_lock": "initial-label-lock.json", "comparison_lock": "comparison-lock.json",
                "agreement": "agreement.json", "disputes": "disputes.json"}
    for key, item in reference["source_hashes"].items():
        path = Path(item["path"]) if "path" in item else study / "custody" / fallback[key]
        audit.require(audit.sha(path) == item["sha256"], "Reference source hash " + key)
    for key, item in reference["final_hashes"].items():
        audit.require(audit.sha(Path(item["path"])) == item["sha256"], "Final reference hash " + key)
    master_rows, master = questions(audit, audit.read(study / "custody/questions-master.json"), "master")
    audit.require(master == texts, "Master versus inference text")
    bank = audit.read(study / "custody/bank-lock.json")
    audit.check(bank["question_master_sha256"] == audit.sha(study / "custody/questions-master.json"), "Bank master hash")
    originals, labels, receipts = {}, {}, {}
    import random
    for role, seed in (("tanishq", 20261015), ("khushi", 20261016)):
        base = study / "annotations" / role
        sheet_rows, sheet = questions(audit, audit.read(base / "questions.json"), role)
        expected_order = list(master_rows)
        random.Random(seed).shuffle(expected_order)
        audit.check(sheet_rows == expected_order and sheet == master, "Independent sheet/order " + role)
        originals[role], labels[role] = read_labels(audit, audit.read(base / "labels.json"), texts, texts, role)
        receipt = receipts[role] = audit.read(base / "receipt.json")
        audit.check(receipt["study_id"] == STUDY and receipt["role"] == role, "Receipt role " + role)
        audit.check(receipt["labels_sha256"] == audit.sha(base / "labels.json")
                    and receipt["source_sheet_sha256"] == audit.sha(base / "questions.json")
                    and bank["sheets"][role] == audit.sha(base / "questions.json"), "Receipt byte linkage " + role)
        identity, exposure = receipt["identity"], receipt["exposure"]
        audit.check(identity["is_ai"] is True and identity["fresh_context"] is True
                    and identity["model_id"] == "gpt-6.1-sol" and identity["reasoning_effort"] == "xhigh", "AI provenance " + role)
        for field in ("parser_implementation_access", "intent_plan_access", "predictions_access",
                      "practice_or_development_access", "other_initial_labels_access"):
            audit.check(exposure[field] is False, "Exposure declaration " + role + "/" + field)
        audit.check(timestamp(receipt["finalized_utc"]) <= timestamp(lock["locked_utc"])
                    <= timestamp(comparison["locked_utc"]), "Annotation lock chronology " + role)
        audit.check(identity["task_identity"] != lock["custodian"]["task_identity"], "Annotator/custodian separation " + role)
    audit.check(receipts["tanishq"]["identity"]["task_identity"] != receipts["khushi"]["identity"]["task_identity"], "Distinct initial tasks")
    expected_inference_order = list(master_rows)
    random.Random(20261017).shuffle(expected_inference_order)
    audit.check(audit.read(study / "inference/questions.json")["questions"] == expected_inference_order, "Frozen inference shuffle")
    agreement = independent_agreement(labels["tanishq"], labels["khushi"])
    audit.same(audit.read(study / "custody/agreement.json"), agreement, "Independent agreement")
    disputed = agreement["disagreement_ids"]
    packet = audit.read(study / "custody/disputes.json")
    audit.check({r["id"] for r in packet["disputes"]} == set(disputed), "Dispute coverage")
    for row in packet["disputes"]:
        audit.check(row["text"] == texts[row["id"]] and row["initial_AI_annotations"] ==
                    {role: originals[role][row["id"]] for role in originals}, "Dispute text/originals " + row["id"])
    decisions = {}
    if disputed:
        decision_path = study / "custody/adjudication-decisions.json"
        _, decisions = read_labels(audit, audit.read(decision_path), texts, disputed, "adjudicator")
        receipt = audit.read(study / "custody/adjudication-receipt.json")
        audit.check(receipt["decisions_sha256"] == audit.sha(decision_path)
                    and receipt["source_packet_sha256"] == audit.sha(study / "custody/disputes.json"), "Adjudication byte linkage")
        audit.check(receipt["identity"]["fresh_context"] is True and receipt["identity"]["is_ai"] is True
                    and receipt["identity"]["task_identity"] not in
                    {receipts[r]["identity"]["task_identity"] for r in receipts} | {lock["custodian"]["task_identity"]}, "Adjudicator independence")
        audit.check(timestamp(comparison["locked_utc"]) <= timestamp(receipt["finalized_utc"])
                    <= timestamp(reference["frozen_utc"]), "Adjudication chronology")
    else:
        audit.check(not (study / "custody/adjudication-decisions.json").exists()
                    and not (study / "custody/adjudication-receipt.json").exists(), "No fabricated zero-dispute adjudication")
    cases_list = audit.read(study / "custody/final-cases.json")
    cases = {c["id"]: c for c in cases_list}
    audit.require(len(cases_list) == len(cases) == 100 and set(cases) == set(texts), "Final reference coverage")
    audit.check(Counter(c["class"] for c in cases_list) == Counter({c: 25 for c in CLASSES}), "Final class balance")
    for i, case in cases.items():
        expected = decisions.get(i, labels["tanishq"][i])
        audit.check(case["text"] == texts[i] and canonical(case["gold"]) == expected
                    and expected["operation"] == "set", "Final label retention " + i)
    plan_path = study / "custody/intent-plan.json"
    plan = audit.read(plan_path)["slots"]
    audit.check(bank["intent_plan_sha256"] == audit.sha(plan_path), "Locked plan hash")
    audit.require(len(plan) == 100 and {s["id"] for s in plan} == set(cases), "Locked plan coverage")
    audit.check(Counter(s["subtype"] for s in plan if s["class"] == "graded") ==
                Counter({"slight_boost": 9, "strong_reduction": 8, "exclusion": 8}), "Graded subtype quotas")
    audit.check({s["target"] for s in plan} == set(CATEGORIES), "Every planned target covered")
    for slot in plan:
        target, second, label = slot["target"], slot["secondary"], slot["class"]
        d = {"operation": "boost", "category": target, "strength": "moderate", "floor": 0, "condition_category": None}
        directives = [d]
        if label == "compound":
            directives.append({"operation": "reduce", "category": second, "strength": "moderate", "floor": 0, "condition_category": None})
        elif label == "floor":
            d.update(operation="reduce", floor=1)
        elif label == "conditional":
            d["condition_category"] = second
        elif label == "graded":
            op, strength = {"slight_boost": ("boost", "slight"), "strong_reduction": ("reduce", "strong"),
                            "exclusion": ("exclude", "none")}[slot["subtype"]]
            d.update(operation=op, strength=strength)
        else:
            raise ValueError("Unknown planned class")
        audit.check(cases[slot["id"]]["class"] == label and canonical(cases[slot["id"]]["gold"]) ==
                    canonical({"operation": "set", "directives": directives}), "Final planned-form compatibility " + slot["id"])
    provenance = audit.read(study / "custody/final-reference-provenance.json")
    audit.check(provenance["initial_receipts"] == receipts, "Provenance initial receipts")
    audit.check({r["id"] for r in provenance["records"]} == set(cases), "Provenance coverage")
    for row in provenance["records"]:
        i = row["id"]
        audit.check(row["original_AI_annotations"] == {r: originals[r][i] for r in originals}
                    and canonical(row["final_canonical_gold"]) == canonical(cases[i]["gold"]), "Preserved reference provenance " + i)
    audit.same(audit.read(study / "evaluation/cases-with-final-ai-reference.json"), cases_list, "Evaluation reference copy")
    return cases, agreement, reference


def band(d, count, other, baseline_other, compound):
    if d["condition_category"] is not None:
        return count >= 2 and other <= baseline_other
    if d["floor"]:
        return 1 <= count <= 2
    if d["operation"] == "exclude":
        return count == 0
    if d["operation"] == "reduce":
        return count <= 1
    return count >= 2 if compound or d["strength"] != "slight" else 2 <= count <= 4


def metric_recount(top, baseline, gold, cat, next_item):
    base, ds = baseline[:10], gold["directives"]
    denominator = sum(1 / math.log2(i + 2) for i in range(10))
    counts, before, bands, basebands, moves, floors = {}, {}, [], [], [], []
    for d in ds:
        target, condition = d["category"], d["condition_category"]
        match = lambda i: target in cat[i] and (condition is None or condition in cat[i])
        other = lambda i: target in cat[i] and condition not in cat[i]
        n, bn = sum(map(match, top)), sum(map(match, base))
        on = sum(map(other, top)) if condition else 0
        bon = sum(map(other, base)) if condition else 0
        key = target if condition is None else target + "&" + condition
        counts[key], before[key] = n, bn
        if condition:
            counts[target + "&!" + condition], before[target + "&!" + condition] = on, bon
        exposure = lambda items, pred: sum(1 / math.log2(k + 2) for k, i in enumerate(items) if pred(i)) / denominator
        move = exposure(top, match) - exposure(base, match)
        if condition:
            move -= max(0.0, exposure(top, other) - exposure(base, other))
        elif d["operation"] != "boost":
            move = -move
        violated = d["floor"] == 1 and n < 1
        floors.append(violated)
        moves.append(0.0 if violated else move)
        bands.append(band(d, n, on, bon, len(ds) > 1))
        basebands.append(band(d, bn, bon, bon, len(ds) > 1))
    full = len(top) == 10
    movement = min(moves) if moves else 0.0
    success = bool(ds) and all(bands) and full
    return {"counts": counts, "baseline_counts": before, "full": full, "band_satisfied": success,
            "baseline_already_satisfies": bool(len(base) == 10 and ds and all(basebands)),
            "floor_violation": any(floors), "fill_rate": len(top) / 10,
            "intended_movement": float(movement), "induced_success": float(success and movement > 1e-12),
            "hr1": float(bool(top) and top[0] == next_item),
            "ndcg_at_10": 1 / math.log2(top.index(next_item) + 2) if next_item in top else 0.0}


def opportunity(gold, cat, baseline):
    discounts = [1 / math.log2(r + 2) for r in range(10)]
    denominator, bounds = sum(discounts), []
    for d in gold["directives"]:
        pred = lambda i: d["category"] in cat[i] and (d["condition_category"] is None or d["condition_category"] in cat[i])
        matches = sum(map(pred, cat))
        current = sum(discounts[r] for r, i in enumerate(baseline[:10]) if pred(i)) / denominator
        if d["operation"] == "boost":
            bounds.append(sum(discounts[:min(10, matches)]) / denominator - current)
        else:
            minimum = max(d["floor"], 10 - (len(cat) - matches), 0)
            bounds.append(current - (sum(discounts[10 - minimum:]) / denominator if minimum else 0.0))
    return not bounds or min(bounds) <= 1e-12


def feasible(gold, cat, baseline):
    refs = sorted({c for d in gold["directives"] for c in (d["category"], d["condition_category"]) if c is not None})
    if len(cat) < 10 or not refs:
        return False
    if len(refs) > 2:
        raise ValueError("Unsupported feasibility dimension")
    groups = Counter(tuple(c in values for c in refs) for values in cat.values())
    masks, limits = list(groups), list(groups.values())
    base_other = {d["category"]: sum(d["category"] in cat[i] and d["condition_category"] not in cat[i]
                  for i in baseline[:10]) if d["condition_category"] else 0 for d in gold["directives"]}

    def works(allocation):
        for d in gold["directives"]:
            t = refs.index(d["category"])
            c = refs.index(d["condition_category"]) if d["condition_category"] else None
            n = sum(amount for mask, amount in zip(masks, allocation) if mask[t] and (c is None or mask[c]))
            other = sum(amount for mask, amount in zip(masks, allocation) if mask[t] and c is not None and not mask[c])
            if not band(d, n, other, base_other[d["category"]], len(gold["directives"]) > 1):
                return False
        return True

    def search(index, remaining, allocation):
        if index == len(limits):
            return remaining == 0 and works(allocation)
        if sum(limits[index:]) < remaining:
            return False
        return any(search(index + 1, remaining - amount, allocation + [amount])
                   for amount in range(min(limits[index], remaining) + 1))
    return search(0, 10, [])


def assignment(data, cases):
    cat = {int(i["item_id"]): set(i["categories"]) for i in data["items"]}
    result, exclusions = {}, []
    for user in sorted(data["users"], key=lambda u: int(u["user_id"])):
        uid = int(user["user_id"])
        history = [int(i) for i in user["train"] + user["request_history"]]
        support = {c for i in history for c in cat[i]}
        for label in sorted(CLASSES):
            eligible = sorted((c for c in cases.values() if c["class"] == label and
                              {x for d in c["gold"]["directives"] for x in (d["category"], d["condition_category"]) if x is not None} <= support), key=lambda c: c["id"])
            if not eligible:
                exclusions.append({"user_id": uid, "class": label,
                                   "reason": "no_case_with_all_category_references_in_train_plus_request_history"})
                continue
            index = int.from_bytes(hashlib.sha256(f"2026:{uid}:{label}".encode()).digest()[:8], "big") % len(eligible)
            case = eligible[index]
            gold = canonical(case["gold"])
            first = gold["directives"][0]
            target, condition = first["category"], first["condition_category"]
            matches = [i for i in history if target in cat[i] and (condition is None or condition in cat[i])]
            policy = "latest_matching_intersection" if condition is not None and matches else "latest_matching_category"
            if not matches:
                matches = [i for i in history if target in cat[i]]
            request_id = f"u{uid}-{label}"
            result[request_id] = {"request_id": request_id, "user_id": uid, "case_id": case["id"],
                                  "class": label, "text": case["text"], "gold": gold,
                                  "exemplar_item": matches[-1], "exemplar_policy": policy,
                                  "A_operation": "boost" if first["operation"] == "boost" else "mute",
                                  "request_seed": 2026, "eligible_case_count": len(eligible),
                                  "history_sha256": fingerprint(history),
                                  "historical_categories": sorted(support, key=lambda c: int(c.split("_")[-1]))}
    return result, exclusions, cat


def bootstrap(values):
    import numpy as np
    if len(values) < 2:
        return {"n_users": len(values), "mean_difference": statistics.mean(values) if values else None,
                "ci95": None, "warning": "fewer_than_two_users", "method": None, "resamples": None}
    vector = np.asarray(values, dtype=float)
    # One independent draw matrix; evaluator uses chunks of 256 from the same RNG stream.
    indices = np.random.default_rng(2026).integers(0, len(vector), size=(5000, len(vector)))
    means = np.mean(vector[indices], axis=1)
    return {"n_users": len(values), "mean_difference": statistics.mean(values),
            "ci95": [float(v) for v in np.quantile(means, [0.025, 0.975], method="linear")],
            "warning": "degenerate_empirical_distribution" if max(values) == min(values)
                       else "small_user_sample" if len(values) < 30 else None,
            "method": "paired_user_percentile_bootstrap", "resamples": 5000}


def greater(values):
    import numpy as np
    from scipy.stats import wilcoxon
    rounded = np.round(np.asarray(values, dtype=float), 12)
    if not len(rounded) or not np.any(rounded):
        return 1.0
    return float(wilcoxon(rounded, zero_method="pratt", correction=False,
                          alternative="greater", method="approx").pvalue)


def bh(values):
    ordered = sorted(enumerate(values), key=lambda pair: pair[1])
    result, upper = [1.0] * len(values), 1.0
    for rank in range(len(values), 0, -1):
        index, p = ordered[rank - 1]
        upper = min(upper, p * len(values) / rank)
        result[index] = upper
    return result


def recount_statistics(audit, rows, summary):
    buckets = defaultdict(list)
    for row in rows:
        for metric in METRICS:
            buckets[(str(row["user_id"]), row["class"], row["condition"], metric)].append(float(row[metric]))
    means = {key: statistics.mean(values) for key, values in buckets.items()}
    pooled = defaultdict(list)
    for (uid, label, condition, metric), value in means.items():
        pooled[(uid, condition, metric)].append(value)
    for (uid, condition, metric), values in pooled.items():
        means[(uid, "pooled", condition, metric)] = statistics.mean(values)
    users = sorted({str(row["user_id"]) for row in rows})
    labels = sorted({row["class"] for row in rows})
    labels += [c for c in CLASSES if c not in labels]

    def differences(label, metric, reference, condition="llm"):
        left = [u for u in users if (u, label, condition, metric) in means]
        right = [u for u in users if (u, label, reference, metric) in means]
        audit.require(left == right, "Paired user mask " + str((label, metric, condition, reference)))
        return left, [means[(u, label, condition, metric)] - means[(u, label, reference, metric)] for u in left]

    tests = []
    specifications = [("H1", c, "induced_success", ref) for c in labels + ["pooled"] for ref in ("A", "rule")]
    specifications += [("H2", "pooled", "intended_movement", "A")]
    for hypothesis, label, metric, reference in specifications:
        mask, values = differences(label, metric, reference)
        tests.append({"hypothesis": hypothesis, "class": label, "condition": "llm", "reference": reference,
                      "metric": metric, "n_nonzero_users": sum(abs(v) > 1e-12 for v in values),
                      "p_one_sided": greater(values), **bootstrap(values),
                      "paired_user_ids": mask, "paired_differences_sha256": fingerprint(values)})
    audit.require(len(tests) == len(summary["tests"]) == 11, "Eleven-test family")
    for result, q in zip(tests, bh([t["p_one_sided"] for t in tests])):
        result.update(q_bh=q, bh_family_size=11, status="assessed" if result["n_users"] else "not_assessed",
                      positive_significant=(result["mean_difference"] > 0 and q < 0.05) if result["n_users"] else None)
        saved = next(t for t in summary["tests"] if all(t[k] == result[k] for k in ("hypothesis", "class", "condition", "reference", "metric")))
        audit.same(saved, {k: v for k, v in result.items() if k not in ("paired_user_ids", "paired_differences_sha256")}, "Independent test " + str((result["class"], result["reference"], result["metric"])))
    descriptive = {c: {label: {m: (statistics.mean(values) if values else None)
                     for m in METRICS for values in [[v for (u, lab, channel, metric), v in means.items()
                                                      if lab == label and channel == c and metric == m]]}
                       for label in labels + ["pooled"]} for c in CONDITIONS}
    audit.same(summary["descriptive"], descriptive, "Independent class/pooled means")
    h3 = []
    for condition in CONDITIONS:
        for reference in ("A", "recency"):
            if condition == reference:
                continue
            for metric in ("hr1", "ndcg_at_10"):
                mask, values = differences("pooled", metric, reference, condition)
                result = {"class": "pooled", "condition": condition, "reference": reference, "metric": metric,
                          "claim_status": "descriptive_only_no_noninferiority_claim",
                          "n_nonzero_users": sum(abs(v) > 1e-12 for v in values), **bootstrap(values)}
                saved = next(t for t in summary["H3"] if all(t[k] == result[k] for k in ("class", "condition", "reference", "metric")))
                audit.same(saved, result, "Independent quality CI " + str((condition, reference, metric)))
                h3.append(result | {"paired_user_ids": mask, "paired_differences_sha256": fingerprint(values)})
    h1 = all(t["positive_significant"] for t in tests if t["hypothesis"] == "H1" and t["class"] == "pooled")
    audit.same(summary, {"H1_passed": h1, "H2_passed": tests[-1]["positive_significant"],
                         "bootstrap_resamples": 5000, "bootstrap_seed": 2026, "user_count": len(users)}, "Hypothesis decisions")
    for condition in CONDITIONS:
        for label in labels + ["pooled"]:
            for metric in ("band_satisfied", "baseline_already_satisfies", "induced_success"):
                selected = [r for r in rows if r["condition"] == condition and (label == "pooled" or r["class"] == label)]
                values = {u: v for (u, lab, c, m), v in means.items() if lab == label and c == condition and m == metric}
                audit.same(summary["satisfaction_descriptive"][condition][label][metric],
                           {"user_mean": statistics.mean(values.values()) if values else None, "n_users": len(values),
                            "n_requests": len({r["request_id"] for r in selected}), "n_request_seed_rows": len(selected),
                            "user_aggregates": values}, "Satisfaction aggregation " + str((condition, label, metric)))
    return {"tests": tests, "descriptive": descriptive, "H3": h3,
            "H1_AI_passed": h1, "H2_AI_passed": tests[-1]["positive_significant"]}


def run(audit, args):
    study, repo = args.study.resolve(), args.repo.resolve()
    pred, evaluation = study / "inference/run-01", study / "evaluation"
    # No reference file is opened until the immutable prediction inventory passes.
    audit.require(audit.sha(pred / "manifest.json") == args.prediction_manifest_sha256, "Committed prediction manifest hash")
    manifest = audit.read(pred / "manifest.json")
    audit.require(manifest["status"] == "predictions_complete" and manifest["prediction_count"] == 200, "Complete predictions before references")
    audit.inventory(pred, manifest)
    policy = audit.read(pred / "protocol-before-inference.json")
    bundle = study / "inference/worker-bundle"
    release = audit.read(bundle / "release.json")
    opening = audit.read(study / "inference/opened.json")
    audit.check(opening["release_sha256"] == audit.sha(bundle / "release.json")
                and opening["questions_sha256"] == release["questions_sha256"], "Global opening byte commitments")
    audit.require(set(release) == RELEASE_FIELDS and set(release["worker_source_sha256"]) == SOURCE_PATHS, "Exact inference release schema")
    audit.same(release, {"study_id": STUDY, "status": "frozen_before_inference", "model": MODEL,
                         "options": OPTIONS, "timeout_seconds": 600}, "Frozen release policy")
    audit.check({p.relative_to(bundle).as_posix() for p in bundle.rglob("*") if p.is_file()} == SOURCE_PATHS | {"release.json", "questions.json"}, "Exact six-file inference bundle")
    for name, digest in release["worker_source_sha256"].items():
        audit.require(audit.sha(bundle / name) == digest, "Bundled source " + name)
    qrows, texts = questions(audit, audit.read(bundle / "questions.json"), "inference bundle")
    audit.require(audit.sha(bundle / "questions.json") == release["questions_sha256"], "Released question hash")
    audit.check(audit.read(study / "inference/questions.json") == {"categories": CATEGORIES, "questions": qrows}, "Inference question copy")
    outcomes = [audit.read(p) for p in sorted((pred / "predictions").glob("*.json"))]
    attempts = [audit.read(p) for p in sorted((pred / "attempts").glob("*.json"))]
    expected = {(b, i) for b in BACKENDS for i in texts}
    audit.require(len(outcomes) == 200 and {(r["backend"], r["id"]) for r in outcomes} == expected, "200 terminal predictions")
    audit.require(len(attempts) == 200 and {(r["backend"], r["id"]) for r in attempts} == expected, "200 unique durable attempts")
    lookup = {(r["backend"], r["id"]): r for r in outcomes}
    journals = {(r["backend"], r["id"]): r for r in attempts}
    for key, row in lookup.items():
        audit.require(row["text"] == texts[row["id"]], "Terminal exact text")
        canonical(row["command"])
        audit.check(timestamp(journals[key]["started_utc"]) <= timestamp(row["completed_utc"]), "Attempt/terminal chronology " + str(key))
        audit.check(timestamp(opening["opened_utc"]) <= timestamp(journals[key]["started_utc"]), "Opening precedes attempt " + str(key))
    audit.check(all(v == "denied_without_reading_bytes" for v in policy["reference_read_probes"].values())
                and bool(policy["reference_read_probes"]), "Protected-reference read probes")
    audit.same(policy["provenance"], MODEL, "Recorded model/runtime")
    audit.same(policy["options"], OPTIONS, "Recorded options")
    audit.check(policy["release"] == release, "Recorded release literal")
    audit.require(hashlib.sha256(policy["prompt"].encode("utf-8")).hexdigest() == args.expected_prompt_sha256, "Literal frozen prompt hash")
    audit.require(fingerprint(policy["schema"]) == args.expected_schema_sha256, "Literal frozen schema hash")
    audit.check(policy["python"].startswith("3.14.0"), "Frozen inference Python version")
    raw = [audit.read(p) for p in sorted((pred / "raw_llm").glob("*.json"))]
    raw_by_id = {}
    categories = policy["schema"]["properties"]["directives"]["items"]["properties"]["category"]["enum"]
    audit.check(set(categories) == set(CATEGORIES) and len(categories) == 31, "Schema category vocabulary")
    for record in raw:
        payload = record["payload"]
        user = json.loads(payload["messages"][1]["content"])
        i = next(i for i, text in texts.items() if text == user["request"])
        audit.require(i not in raw_by_id, "Duplicate raw response for " + i)
        raw_by_id[i] = record
        expected_payload = {"model": "llama3.1:8b", "messages": [
            {"role": "system", "content": policy["prompt"] + "\nSCHEMA: " + json.dumps(policy["schema"], sort_keys=True)},
            {"role": "user", "content": json.dumps({"allowed_categories": categories, "request": texts[i]})}],
            "format": policy["schema"], "stream": False, "keep_alive": "15m", "options": OPTIONS}
        audit.check(payload == expected_payload, "Literal complete payload " + i)
        audit.check(record["provenance"] == policy["provenance"] and record["base_url"] == "http://127.0.0.1:11434", "Raw provenance " + i)
        audit.check(record["prompt_version"] == "feedctrl-experiment2-compound-v2", "Prompt version " + i)
        cache_key = hashlib.sha256(json.dumps({"prompt_version": record["prompt_version"], "provenance": record["provenance"], "payload": payload}, sort_keys=True).encode()).hexdigest()
        audit.check(record["key"] == cache_key, "Raw cache fingerprint " + i)
        attempt, terminal = journals[("ollama_compound", i)], lookup[("ollama_compound", i)]
        audit.check(timestamp(attempt["started_utc"]) <= timestamp(record["request_started_at"])
                    <= timestamp(record["response_received_at"]) <= timestamp(terminal["completed_utc"]), "Raw request chronology " + i)
        if not terminal["error"]:
            audit.check(record["response"].get("done") is True and record["response"].get("done_reason") != "length", "Successful response completed " + i)
            try:
                canonical(json.loads(record["response"]["message"]["content"]), metadata=True)
            except (ValueError, KeyError, TypeError):
                audit.check(False, "Successful prediction has malformed raw command " + i)
    missing_raw = []
    for i in texts.keys() - raw_by_id.keys():
        error = lookup[("ollama_compound", i)]["error"]
        network = bool(error) and any(token in error.casefold() for token in
                    ("http", "urlerror", "timeout", "timed out", "connection", "network", "remote disconnected", "remotedisconnected", "refused"))
        audit.check(network, "Missing raw response lacks recorded network failure " + i)
        missing_raw.append({"id": i, "recorded_error": error, "network_failure_accounted": network})
    audit.check(len(raw) + len(missing_raw) == 100, "100 raw responses or accounted network failures")
    audit.same(manifest, {"failures": sum(bool(r["error"]) for r in outcomes), "raw_response_count": len(raw)}, "Prediction failure/raw totals")
    audit.check(Counter(stable(r) for r in audit.read(pred / "failures.json")) ==
                Counter(stable(r) for r in outcomes if r["error"]), "Complete preserved operational failures")
    evaluation_manifest = audit.read(evaluation / "manifest.json")
    audit.require(evaluation_manifest["status"] == "ai_reference_evaluation_completed", "Protected scoring complete")
    audit.inventory(evaluation, evaluation_manifest)
    audit.check(evaluation_manifest["prediction_manifest_sha256"] == args.prediction_manifest_sha256, "Scoring joined committed predictions")
    opened = timestamp(opening["opened_utc"])
    protocol, full = verify_freeze(audit, study, repo, release, opened)
    cases, agreement, reference = verify_references(audit, study, texts)
    audit.check(audit.sha(study / "custody/reference-freeze.json") == release["reference_freeze_sha256"], "Reference/release linkage")
    audit.check(timestamp(reference["frozen_utc"]) <= timestamp(release["frozen_utc"]) <= opened, "Reference/inference chronology")
    join = audit.read(evaluation / "predictions-committed-before-reference-join.json")
    audit.check(max(timestamp(r["completed_utc"]) for r in outcomes) <= timestamp(join["started_utc"]), "Predictions immutable before scoring join")
    parser = {}
    for backend in BACKENDS:
        def counts(rows):
            correct = sum(not r["error"] and canonical(r["command"]) == canonical(cases[r["id"]]["gold"]) for r in rows)
            return {"total": len(rows), "correct": correct, "accuracy": correct / len(rows) if rows else None,
                    "operational_errors": sum(bool(r["error"]) for r in rows),
                    "clarifications": sum(not r["error"] and r["command"]["operation"] == "clarify" for r in rows)}
        selected = [r for r in outcomes if r["backend"] == backend]
        parser[backend] = counts(selected) | {"by_class": {c: counts([r for r in selected if cases[r["id"]]["class"] == c]) for c in sorted(CLASSES)}}
    audit.same(audit.read(evaluation / "parser-agreement-with-ai-reference.json"), parser, "Independent parser exact agreement")
    parsed_copies = [audit.read(p) for p in (evaluation / "parse_cache").glob("*.json")]
    audit.require(len(parsed_copies) == 200, "Protected parser cache denominator")
    for row in parsed_copies:
        expected_row = lookup[(row["backend"], row["id"])] | {"class": cases[row["id"]]["class"]}
        audit.check(row == expected_row, "Immutable parser cache copy " + row["id"])
    expected_failures = [row for row in parsed_copies if row["error"] or canonical(row["command"]) != canonical(cases[row["id"]]["gold"])]
    audit.check(Counter(stable(r) for r in audit.read(evaluation / "parser-failures.json")) ==
                Counter(stable(r) for r in expected_failures), "Complete parser disagreement/failure inventory")
    data_path = args.archive.resolve() / "data/processed.json"
    audit.require(full["files"].get(str(data_path)) == audit.sha(data_path), "Ranking data full-freeze membership")
    data = audit.read(data_path)
    audit.require(len(data["users"]) == 865 and len(data["items"]) == 2593, "Frozen data dimensions")
    requests, exclusions, cat = assignment(data, cases)
    observed_requests = audit.read(evaluation / "assigned-requests.json")
    audit.require(len(observed_requests) == len(requests) and {r["request_id"] for r in observed_requests} == set(requests), "Assigned request coverage")
    for row in observed_requests:
        audit.check(row == requests[row["request_id"]], "Independent assignment " + row["request_id"])
    audit.check(audit.read(evaluation / "excluded-user-classes.json") == exclusions, "All eligibility exclusions")
    users = {int(u["user_id"]): u for u in data["users"]}
    item_ids, vectors = sorted(cat), {}
    for path in sorted((evaluation / "score_vectors").glob("*.json")):
        value = audit.read(path)
        key = (value["seed"], value["user_id"])
        audit.require(key not in vectors and value["item_ids"] == item_ids and len(value["scores"]) == len(item_ids)
                      and all(type(s) in (int, float) and math.isfinite(s) for s in value["scores"]), "Score vector validity")
        user = users[value["user_id"]]
        audit.check(value["history_sha256"] == fingerprint(user["train"] + user["request_history"])
                    and value["score_sha256"] == fingerprint(value["scores"]), "Score/history fingerprints " + str(key))
        scores = dict(zip(item_ids, value["scores"]))
        vectors[key] = (value, sorted(item_ids, key=lambda i: (-scores[i], i)))
    audit.require(set(vectors) == {(s, u) for s in SEEDS for u in users} and len(vectors) == 2595, "All 2595 full score vectors")
    rows = audit.read(evaluation / "ranking-rows.json")
    rowkeys = {(r["seed"], r["request_id"], r["condition"]) for r in rows}
    audit.require(len(rows) == len(rowkeys) == 12 * len(requests) and rowkeys ==
                  {(s, r, c) for s in SEEDS for r in requests for c in CONDITIONS}, "All assigned ranking rows retained")
    feasible_cache, recounted_rows = {}, []
    pop = Counter(int(i) for u in data["users"] for i in u["request_history"])
    recency = sorted(item_ids, key=lambda i: (-pop[i], i))
    for row in rows:
        req = requests[row["request_id"]]
        audit.check(all(row[k] == req[k] for k in ("user_id", "case_id", "class")), "Ranking row identity")
        vector, baseline = vectors[(row["seed"], row["user_id"])]
        audit.check(row["score_sha256"] == vector["score_sha256"] and row["baseline_sha256"] == fingerprint(baseline)
                    and row["candidate_count"] == 2593, "Ranking provenance " + row["request_id"])
        top = row["top_10"]
        audit.require(len(top) <= 10 and len(top) == len(set(top)) and set(top) <= set(cat), "Valid unique top list")
        recounted = metric_recount(top, baseline, canonical(req["gold"]), cat, users[row["user_id"]]["test"][0])
        key = (fingerprint(req["gold"]), stable(recounted["baseline_counts"]))
        if key not in feasible_cache:
            feasible_cache[key] = feasible(req["gold"], cat, baseline)
        recounted.update(structurally_infeasible=not feasible_cache[key], no_directional_opportunity=opportunity(req["gold"], cat, baseline))
        audit.same(row, recounted, "Independent ranking metrics " + str((row["seed"], row["request_id"], row["condition"])))
        if row["condition"] == "recency":
            audit.check(top == recency[:10] and row["ranking_sha256"] == fingerprint(recency), "Independent recency ranking")
        if row["condition"] in ("rule", "llm"):
            backend = "rule_compound" if row["condition"] == "rule" else "ollama_compound"
            parsed = lookup[(backend, row["case_id"])]
            audit.check(row["parser_error"] == bool(row["error_detail"]), "Ranking error flag")
            if parsed["error"] or row["parser_error"] or parsed["command"]["operation"] == "clarify":
                audit.check(top == baseline[:10] and row["ranking_sha256"] == fingerprint(baseline), "No control on failure/clarify")
                if parsed["error"]:
                    audit.check(row["parser_error"] is True, "Parser failure retained in ranking denominator")
        recounted_rows.append(row | recounted)
    summary = audit.read(evaluation / "ranking-summary.json")
    audit.same(summary, {"request_count": len(requests), "excluded_user_class_count": len(exclusions),
                         "exclusions_by_class": dict(Counter(r["class"] for r in exclusions)),
                         "structurally_infeasible_request_seed_count": sum(r["structurally_infeasible"] for r in recounted_rows if r["condition"] == "A"),
                         "baseline_satisfies_request_seed_count": sum(r["baseline_already_satisfies"] for r in recounted_rows if r["condition"] == "A"),
                         "no_directional_opportunity_request_seed_count": sum(r["no_directional_opportunity"] for r in recounted_rows if r["condition"] == "A"),
                         "floor_violations": {c: sum(r["floor_violation"] for r in recounted_rows if r["condition"] == c) for c in CONDITIONS}}, "Ranking totals/flags")
    for condition in CONDITIONS:
        selected = [r for r in recounted_rows if r["condition"] == condition and not r["structurally_infeasible"]]
        audit.same(summary["feasible_stratum"][condition], {"denominator_request_seeds": len(selected),
                   "induced_success_mean": statistics.mean(r["induced_success"] for r in selected) if selected else None}, "Feasible stratum " + condition)
    stats = recount_statistics(audit, recounted_rows, summary)
    raw_exact = 0
    for i, record in raw_by_id.items():
        try:
            raw_exact += canonical(json.loads(record["response"]["message"]["content"]), metadata=True) == canonical(cases[i]["gold"])
        except (ValueError, KeyError, TypeError):
            pass
    # Detect mutation during the audit; the auditor itself never rewrites evidence.
    audit.check(audit.sha(pred / "manifest.json") == args.prediction_manifest_sha256, "Prediction manifest unchanged after audit")
    for name, digest in full["files"].items():
        audit.check(audit.sha(Path(name)) == digest, "Frozen evidence unchanged after recount " + name)
    return {"parser_recount": parser, "agreement_recount": agreement, "statistics_recount": stats,
            "raw_response_files": len(raw), "accounted_missing_raw": missing_raw,
            "raw_prevalidation_exact_agreement": {"correct": raw_exact, "denominator": 100, "supplementary_only": True},
            "attempts": len(attempts), "terminal_predictions": len(outcomes), "requests": len(requests),
            "ranking_rows": len(rows), "score_vectors": len(vectors), "unique_language_cases": 100}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--prediction-manifest-sha256", required=True)
    parser.add_argument("--prediction-commit", required=True, help="Recorded immutable commitment identity; wrapper verifies supplied manifest hash, not Git signatures")
    parser.add_argument("--expected-prompt-sha256", required=True, help="UTF-8 prompt hash from pre-authoring-frozen parser policy")
    parser.add_argument("--expected-schema-sha256", required=True, help="SHA-256 of sorted-key compact UTF-8 JSON schema from frozen parser policy")
    parser.add_argument("--authorize-post-commit-audit", action="store_true", required=True)
    args = parser.parse_args()
    output = (args.output or args.study / "audit/independent-audit.json").resolve()
    if not output.is_relative_to((args.study / "audit").resolve()) or output.exists():
        parser.error("Use a new output file inside this study's audit directory")
    audit = Audit()
    report = {"study_id": STUDY, "started_utc": stamp(), "command": sys.argv,
              "prediction_commit_identity": args.prediction_commit,
              "expected_prediction_manifest_sha256": args.prediction_manifest_sha256,
              "method": "Separate AI reviewer; independent stdlib evidence/metric recount, direct SciPy one-sided Pratt Wilcoxon/BH and independent NumPy paired-user bootstrap. No feedctrl imports, inference or source edits.",
              "limitations": ["AI references are not independent human ground truth; reviewer shares the stated GPT model family.",
                              "Saved score vectors and rankings are audited; SASRec scoring and the language-control ranker are not independently reimplemented.",
                              "Recorded commitments and timestamps are consistency evidence, not cryptographic proof of host access history or a hostile-host security boundary.",
                              "The supplied prediction commitment identity is recorded; no Git signature or remote attestation is asserted."]}
    try:
        report.update(run(audit, args))
    except Exception as exc:
        audit.check(False, f"Fatal audit error: {type(exc).__name__}: {exc}")
        report["traceback"] = traceback.format_exc()
    report.update(completed_utc=stamp(), status="passed" if not audit.failure_count else "failed",
                  checks=audit.checks, failure_count=audit.failure_count, failures=audit.failures,
                  input_sha256=audit.inputs, python=sys.version)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False, allow_nan=False)
    print(json.dumps({"status": report["status"], "checks": audit.checks, "failure_count": audit.failure_count,
                      "output": str(output), "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}))
    return int(bool(audit.failure_count))


if __name__ == "__main__":
    raise SystemExit(main())
