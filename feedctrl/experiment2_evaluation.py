"""Prospective Experiment 2: sealed language evaluation and paired control analysis.

This module never reads a reserved language file implicitly. Only the staged runner
may open it after its human annotation, frozen-input, and single-opening gates.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from .evaluation import bh_adjust, item_feedback_ranking, paired_bootstrap, paired_wilcoxon_p

SEEDS = (42, 43, 44)
CONDITIONS = ("A", "rule", "llm", "recency")
CLASSES = ("compound", "graded", "floor", "conditional")
RESET = {"operation": "clarify", "directives": []}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_new_json(path: str | Path, value: Any) -> None:
    """An exclusive complete evidence record, with no overwrite escape hatch."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def category_key(category: str) -> tuple:
    try:
        return (0, int(category.rsplit("_", 1)[-1]))
    except (ValueError, AttributeError):
        return (1, str(category))


def canonical(command: dict) -> dict:
    """Ignore diagnostic metadata; directive ordering has no semantic meaning."""
    from .experiment2_controls import canonical_command, validate_command
    result = canonical_command(command)
    refs = [c for d in result.get("directives", []) if isinstance(d, dict) for c in (d.get("category"), d.get("condition_category")) if isinstance(c, str)]
    try:
        validate_command(result, sorted(set(refs)) or ["category_0"])
    except Exception as error:
        raise ValueError(f"Invalid compound command: {error}") from error
    return {"operation": result["operation"], "directives": sorted(
        [{key: d[key] for key in ("operation", "category", "strength", "floor", "condition_category")}
         for d in result["directives"]], key=lambda d: (category_key(d["category"]), d["operation"]))}


def load_cases(path: str | Path, expected_count: int | None = None) -> list[dict]:
    records = [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]
    if expected_count is not None and len(records) != expected_count:
        raise ValueError(f"Expected {expected_count} cases, received {len(records)}")
    ids = [r["id"] for r in records]
    if len(set(ids)) != len(ids) or any(not isinstance(i, str) or not i for i in ids):
        raise ValueError("Case IDs must be unique nonempty strings")
    for row in records:
        if not isinstance(row["text"], str) or not row["text"] or not isinstance(row["class"], str):
            raise ValueError("Each case requires exact text and a class")
        canonical(row["gold"])
    return records


def category_references(command: dict) -> set[str]:
    return {c for d in canonical(command)["directives"] for c in (d["category"], d["condition_category"]) if c is not None}



RANKING_CLASS_FORMS = {
    "compound": "two unconditional floor-0 directives on distinct targets: boost/moderate and reduce/moderate",
    "graded": "one unconditional floor-0 directive: boost/slight, reduce/strong, or exclude/none",
    "floor": "one unconditional reduce/moderate directive with floor 1",
    "conditional": "one boost/moderate directive with floor 0 and a distinct non-null condition category",
}


class UnsupportedRankingGold(ValueError):
    """Human consensus is preserved but is outside this study's prespecified metrics."""
    def __init__(self, issues: list[dict]):
        self.issues = issues
        super().__init__("Ranking/full freeze blocked by unsupported final gold; preserve labels and resolve the prospective study design: "
                         + json.dumps(issues, sort_keys=True))


def ranking_shape_issues(cases: list[dict]) -> list[dict]:
    """Check committed class semantics without changing, dropping or relabeling cases."""
    issues = []
    for case in cases:
        label, case_id = case.get("class"), case.get("id")
        problem = None
        if label not in RANKING_CLASS_FORMS:
            problem = "unknown_or_missing_committed_class"
        else:
            try:
                gold = canonical(case["gold"])
            except (ValueError, KeyError, TypeError) as error:
                problem = f"invalid_command_schema: {error}"
            else:
                ds = gold["directives"]
                if gold["operation"] == "clarify":
                    problem = "clarify_has_no_prespecified_ranking_metric"
                else:
                    unconditional = all(d["condition_category"] is None for d in ds)
                    if label == "compound":
                        supported = (len(ds) == 2 and unconditional and
                                     {(d["operation"], d["strength"], d["floor"]) for d in ds} ==
                                     {("boost", "moderate", 0), ("reduce", "moderate", 0)})
                    elif label == "graded":
                        supported = (len(ds) == 1 and unconditional and ds[0]["floor"] == 0 and
                                     (ds[0]["operation"], ds[0]["strength"]) in
                                     {("boost", "slight"), ("reduce", "strong"), ("exclude", "none")})
                    elif label == "floor":
                        supported = (len(ds) == 1 and unconditional and
                                     (ds[0]["operation"], ds[0]["strength"], ds[0]["floor"]) == ("reduce", "moderate", 1))
                    else:
                        supported = (len(ds) == 1 and ds[0]["condition_category"] is not None and
                                     (ds[0]["operation"], ds[0]["strength"], ds[0]["floor"]) == ("boost", "moderate", 0))
                    if not supported:
                        problem = "command_shape_does_not_match_committed_class"
        if problem:
            issues.append({"id": case_id, "class": label, "reason": problem,
                           "expected_form": RANKING_CLASS_FORMS.get(label)})
    return issues


def validate_ranking_cases(cases: list[dict]) -> None:
    issues = ranking_shape_issues(cases)
    if issues:
        raise UnsupportedRankingGold(issues)


def validate_final_gold_classes(final_gold: dict, manifest: dict) -> None:
    committed_classes = {record["id"]: record.get("class") for record in manifest.get("cases", [])}
    validate_ranking_cases([{"id": case_id, "class": committed_classes.get(case_id), "gold": gold}
                            for case_id, gold in sorted(final_gold.items())])

def assign_requests(data: dict, cases: list[dict], request_seed: int = 2026) -> tuple[list[dict], list[dict]]:
    """One unchanged held-out utterance per eligible user and class, without test labels."""
    validate_ranking_cases(cases)
    catmap = {int(i["item_id"]): set(i["categories"]) for i in data["items"]}
    classes = sorted({r["class"] for r in cases})
    requests, exclusions = [], []
    for user in sorted(data["users"], key=lambda u: int(u["user_id"])):
        uid = int(user["user_id"])
        history = [int(i) for i in user["train"] + user["request_history"]]
        support = {c for i in history for c in catmap[i]}
        for label in classes:
            eligible = sorted([r for r in cases if r["class"] == label and category_references(r["gold"]) <= support], key=lambda r: r["id"])
            if not eligible:
                exclusions.append({"user_id": uid, "class": label, "reason": "no_case_with_all_category_references_in_train_plus_request_history"})
                continue
            index = int.from_bytes(hashlib.sha256(f"{request_seed}:{uid}:{label}".encode()).digest()[:8], "big") % len(eligible)
            case = eligible[index]
            gold = canonical(case["gold"])
            first = gold["directives"][0]
            target, condition = first["category"], first["condition_category"]
            exemplars = [i for i in history if target in catmap[i] and (condition is None or condition in catmap[i])]
            exemplar_policy = "latest_matching_intersection" if condition is not None and exemplars else "latest_matching_category"
            if not exemplars:
                exemplars = [i for i in history if target in catmap[i]]
            requests.append({"request_id": f"u{uid}-{label}", "user_id": uid, "case_id": case["id"],
                             "class": label, "text": case["text"], "gold": gold, "exemplar_item": exemplars[-1],
                             "exemplar_policy": exemplar_policy, "A_operation": "boost" if first["operation"] == "boost" else "mute",
                             "request_seed": request_seed, "eligible_case_count": len(eligible),
                             "history_sha256": fingerprint(history), "historical_categories": sorted(support, key=category_key)})
    return requests, exclusions


def _count(ranking: list[int], catmap: dict[int, list[str]], target: str, condition: str | None = None, negate: bool = False) -> int:
    return sum(target in catmap[i] and (condition is None or ((condition not in catmap[i]) if negate else (condition in catmap[i]))) for i in ranking)


def _discount_exposure(ranking: list[int], catmap: dict[int, list[str]], target: str, condition: str | None, negate: bool, k: int) -> float:
    denominator = sum(1 / math.log2(rank + 2) for rank in range(k))
    return sum(1 / math.log2(rank + 2) for rank, i in enumerate(ranking[:k])
               if target in catmap[i] and (condition is None or ((condition not in catmap[i]) if negate else (condition in catmap[i])))) / denominator


def _directive_band(directive: dict, count: int, other_count: int, baseline_other: int, compound: bool) -> bool:
    if directive["condition_category"] is not None:
        return count >= 2 and other_count <= baseline_other
    if directive["floor"] == 1:
        return 1 <= count <= 2
    if directive["operation"] == "exclude":
        return count == 0
    if directive["operation"] == "reduce":
        return count <= 1
    if compound:
        return count >= 2
    if directive["strength"] == "slight":
        return 2 <= count <= 4
    return count >= 2


def evaluate_ranking(ranking: list[int], baseline: list[int], gold: dict,
                     item_categories: dict[int, list[str]], next_item: int, k: int = 10) -> dict:
    if k != 10:
        raise ValueError("Experiment 2 prespecifies K=10")
    if len(set(ranking)) != len(ranking) or len(set(baseline)) != len(baseline):
        raise ValueError("Duplicate items in ranking")
    if any(i not in item_categories for i in ranking + baseline):
        raise ValueError("Ranking contains an item outside the shared catalogue")
    gold = canonical(gold)
    directives = gold["directives"]
    top, base = ranking[:k], baseline[:k]
    full = len(top) == k
    counts, base_counts, moves, bands, base_bands, violations = {}, {}, [], [], [], []
    for directive in directives:
        target, condition = directive["category"], directive["condition_category"]
        count = _count(top, item_categories, target, condition)
        before = _count(base, item_categories, target, condition)
        other = _count(top, item_categories, target, condition, True) if condition else 0
        base_other = _count(base, item_categories, target, condition, True) if condition else 0
        key = target if condition is None else f"{target}&{condition}"
        counts[key], base_counts[key] = count, before
        if condition:
            counts[f"{target}&!{condition}"], base_counts[f"{target}&!{condition}"] = other, base_other
        delta = _discount_exposure(top, item_categories, target, condition, False, k) - _discount_exposure(base, item_categories, target, condition, False, k)
        if condition:
            leakage = _discount_exposure(top, item_categories, target, condition, True, k) - _discount_exposure(base, item_categories, target, condition, True, k)
            movement = delta - max(0.0, leakage)
        else:
            movement = delta if directive["operation"] == "boost" else -delta
        if directive["floor"] == 1 and count < 1:
            movement = 0.0
        moves.append(movement)
        bands.append(_directive_band(directive, count, other, base_other, len(directives) > 1))
        base_bands.append(_directive_band(directive, before, base_other, base_other, len(directives) > 1))
        violations.append(directive["floor"] == 1 and count < 1)
    movement = min(moves) if moves else 0.0
    band = bool(directives) and all(bands)
    return {"full": full, "band_satisfied": bool(full and band), "intended_movement": float(movement),
            "induced_success": float(full and band and movement > 1e-12),
            "baseline_already_satisfies": bool(len(base) == k and directives and all(base_bands)),
            "floor_violation": any(violations), "fill_rate": len(top) / k,
            "hr1": float(bool(top) and top[0] == next_item),
            "ndcg_at_10": 1 / math.log2(top.index(next_item) + 2) if next_item in top else 0.0,
            "counts": counts, "baseline_counts": base_counts}



def validate_case_bank(cases: list[dict], categories: list[str], expected_count: int, manifest: dict | None = None) -> None:
    if len(cases) != expected_count or Counter(r["class"] for r in cases) != Counter({label: expected_count // 4 for label in CLASSES}):
        raise ValueError("Language bank must preserve the prespecified four equal-sized classes")
    if len({r["text"] for r in cases}) != len(cases):
        raise ValueError("Language cases must have unique exact utterances")
    if any(not category_references(r["gold"]) <= set(categories) for r in cases):
        raise ValueError("Language bank references categories outside the frozen catalogue")
    if manifest is not None:
        if sorted(r["id"] for r in cases) != manifest_case_ids(manifest):
            raise ValueError("Opened cases differ from the public committed case IDs")
        public_classes = {r["id"]: r["class"] for r in manifest["cases"]}
        if any(public_classes[r["id"]] != r["class"] for r in cases):
            raise ValueError("Opened classes differ from the public commitment")


def no_directional_opportunity(gold: dict, item_categories: dict[int, list[str]], baseline: list[int], k: int = 10) -> bool:
    """A conservative impossibility flag using optimistic per-directive exposure bounds.

    A false value does not guarantee a joint solution. The separate exact count
    feasibility flag detects contradictory bands and impossible intersections.
    """
    discounts = [1 / math.log2(r + 2) for r in range(k)]
    denominator = sum(discounts)
    bounds = []
    for directive in canonical(gold)["directives"]:
        target, condition = directive["category"], directive["condition_category"]
        matches = _count(list(item_categories), item_categories, target, condition)
        current = _discount_exposure(baseline, item_categories, target, condition, False, k)
        if directive["operation"] == "boost":
            bound = sum(discounts[:min(k, matches)]) / denominator - current
        else:
            minimum_count = max(directive["floor"], k - (len(item_categories) - matches), 0)
            minimum = sum(discounts[k - minimum_count:]) / denominator if minimum_count else 0.0
            bound = current - minimum
        bounds.append(bound)
    return not bounds or min(bounds) <= 1e-12


def structurally_feasible(gold: dict, item_categories: dict[int, list[str]], baseline: list[int], k: int = 10) -> bool:
    """Exact count feasibility over four category-membership groups, no relevance labels."""
    refs = sorted(category_references(gold), key=category_key)
    if len(item_categories) < k or not refs:
        return False
    if len(refs) > 2:
        raise ValueError("Prespecified requests reference at most two categories")
    groups = defaultdict(list)
    for item, cats in item_categories.items():
        groups[tuple(c in cats for c in refs)].append(item)
    # Counts, not order, determine bands. Enumerate at most 11^3 allocations.
    groups = list(groups.values())
    def candidates(index: int, picked: list[int]):
        if index == len(groups):
            if len(picked) == k:
                yield picked
            return
        group = groups[index]
        for amount in range(min(len(group), k - len(picked)) + 1):
            yield from candidates(index + 1, picked + group[:amount])
    return any(evaluate_ranking(rank, baseline, gold, item_categories, -1, k)["band_satisfied"] for rank in candidates(0, []))


def summarize_parser(outcomes: list[dict], cases: list[dict]) -> dict:
    gold = {r["id"]: r for r in cases}
    expected = {(i, b) for i in gold for b in ("rule_compound", "ollama_compound")}
    keys = [(r["id"], r["backend"]) for r in outcomes]
    if len(keys) != len(set(keys)) or set(keys) != expected:
        raise ValueError("Parser outcomes must contain every case once for each parser")
    result = {}
    for backend in ("rule_compound", "ollama_compound"):
        rows = [r for r in outcomes if r["backend"] == backend]
        def report(subset):
            correct = sum(not r.get("error") and canonical(r["command"]) == canonical(gold[r["id"]]["gold"]) for r in subset)
            return {"total": len(subset), "correct": correct, "accuracy": correct / len(subset) if subset else None,
                    "operational_errors": sum(bool(r.get("error")) for r in subset),
                    "clarifications": sum(not r.get("error") and r["command"]["operation"] == "clarify" for r in subset)}
        result[backend] = {**report(rows), "by_class": {label: report([r for r in rows if gold[r["id"]]["class"] == label]) for label in sorted({r["class"] for r in cases})}}
    return result


def paired_wilcoxon_greater(differences: list[float]) -> float:
    """Convert E1's two-sided Pratt test using signed-rank direction, never mean sign."""
    from scipy.stats import rankdata
    values = np.round(np.asarray(differences, dtype=float), 12)
    if not len(values):
        return 1.0
    two_sided = paired_wilcoxon_p(values.tolist())
    if not np.any(values):
        return 1.0
    direction = float(np.sum(rankdata(np.abs(values)) * np.sign(values)))
    return two_sided / 2 if direction > 0 else 1 - two_sided / 2 if direction < 0 else 0.5


def _descriptive_bootstrap(differences: list[float], n_bootstrap: int) -> dict:
    source = paired_bootstrap(differences, n_resamples=n_bootstrap, seed=2026)
    return {key: source.get(key) for key in ("n_users", "mean_difference", "ci95", "warning", "method", "resamples")}


def analyze_rows(rows: list[dict], n_bootstrap: int = 5000) -> dict:
    if not rows:
        return {"status": "not_run", "user_count": 0, "tests": [], "descriptive": {}, "satisfaction_descriptive": {}, "H1_passed": None, "H2_passed": None, "H1_status": "not_assessed", "H2_status": "not_assessed", "H3": []}
    keys = [(r["seed"], r["request_id"], r["condition"]) for r in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicate ranking rows")
    pairs = defaultdict(set)
    identities = defaultdict(set)
    for row in rows:
        pairs[row["request_id"]].add((int(row["seed"]), row["condition"]))
        identities[row["request_id"]].add((row["user_id"], row["class"]))
    expected = {(s, c) for s in SEEDS for c in CONDITIONS}
    if any(v != expected for v in pairs.values()) or any(len(v) != 1 for v in identities.values()):
        raise ValueError("Every assigned request must retain all four conditions and three seeds with stable identity")
    labels = sorted({r["class"] for r in rows})
    if len(labels) > 4:
        raise ValueError("Experiment 2 has four request classes")
    # Preserve all four prespecified class slots even in a sparse eligible cohort.
    if len(labels) < 4:
        labels += [label for label in CLASSES if label not in labels][:4 - len(labels)]
    metrics = ("induced_success", "intended_movement", "hr1", "ndcg_at_10", "band_satisfied", "baseline_already_satisfies")
    per_request = defaultdict(list)
    for row in rows:
        for metric in metrics:
            if metric not in row and metric in ("band_satisfied", "baseline_already_satisfies"):
                continue
            value = float(row[metric])
            if not math.isfinite(value):
                raise ValueError("Nonfinite metric")
            per_request[(str(row["user_id"]), row["request_id"], row["class"], row["condition"], metric)].append(value)
    class_buckets = defaultdict(list)
    for (uid, request, label, condition, metric), values in per_request.items():
        class_buckets[(uid, label, condition, metric)].append(float(np.mean(values)))
    aggregate = {key: float(np.mean(values)) for key, values in class_buckets.items()}
    pool = defaultdict(list)
    for (uid, label, condition, metric), value in aggregate.items():
        pool[(uid, condition, metric)].append(value)
    for (uid, condition, metric), values in pool.items():
        aggregate[(uid, "pooled", condition, metric)] = float(np.mean(values))
    users = sorted({str(r["user_id"]) for r in rows})
    def diffs(label, metric, reference, condition="llm"):
        return [aggregate[(u, label, condition, metric)] - aggregate[(u, label, reference, metric)]
                for u in users if (u, label, condition, metric) in aggregate]
    tests = []
    for label in labels + ["pooled"]:
        for reference in ("A", "rule"):
            differences = diffs(label, "induced_success", reference)
            tests.append({"hypothesis": "H1", "class": label, "condition": "llm", "reference": reference,
                          "metric": "induced_success", "n_nonzero_users": sum(abs(v) > 1e-12 for v in differences), "p_one_sided": paired_wilcoxon_greater(differences),
                          **_descriptive_bootstrap(differences, n_bootstrap)})
    differences = diffs("pooled", "intended_movement", "A")
    tests.append({"hypothesis": "H2", "class": "pooled", "condition": "llm", "reference": "A",
                  "metric": "intended_movement", "n_nonzero_users": sum(abs(v) > 1e-12 for v in differences), "p_one_sided": paired_wilcoxon_greater(differences),
                  **_descriptive_bootstrap(differences, n_bootstrap)})
    for record, q in zip(tests, bh_adjust([r["p_one_sided"] for r in tests])):
        record.update({"q_bh": q, "bh_family_size": 11, "status": "assessed" if record["n_users"] else "not_assessed", "positive_significant": bool(record["mean_difference"] is not None and record["mean_difference"] > 0 and q < 0.05) if record["n_users"] else None})
    descriptive = {condition: {label: {metric: float(np.mean([v for (u, lab, c, m), v in aggregate.items() if lab == label and c == condition and m == metric])) if any(lab == label and c == condition and m == metric for u, lab, c, m in aggregate) else None for metric in metrics} for label in labels + ["pooled"]} for condition in CONDITIONS}
    h3 = [{"class": "pooled", "condition": condition, "reference": reference, "metric": metric,
           "claim_status": "descriptive_only_no_noninferiority_claim",
           "n_nonzero_users": sum(abs(v) > 1e-12 for v in diffs("pooled", metric, reference, condition)),
           **_descriptive_bootstrap(diffs("pooled", metric, reference, condition), n_bootstrap)}
          for condition in CONDITIONS for reference in ("A", "recency") if condition != reference for metric in ("hr1", "ndcg_at_10")]
    satisfaction = {}
    for condition in CONDITIONS:
        satisfaction[condition] = {}
        for label in labels + ["pooled"]:
            satisfaction[condition][label] = {}
            for metric in ("band_satisfied", "baseline_already_satisfies", "induced_success"):
                selected = [r for r in rows if r["condition"] == condition and (label == "pooled" or r["class"] == label) and metric in r]
                values = {u: v for (u, lab, channel, measure), v in aggregate.items() if lab == label and channel == condition and measure == metric}
                satisfaction[condition][label][metric] = {
                    "user_mean": float(np.mean(list(values.values()))) if values else None,
                    "n_users": len(values), "n_requests": len({r["request_id"] for r in selected}),
                    "n_request_seed_rows": len(selected), "user_aggregates": values,
                    "status": "descriptive" if values else "not_recorded_or_no_eligible_users"}
    warnings = ["Offline relevance proxies do not measure satisfaction, naturalness, or human preference.", "Recency popularity uses global request-history counts from the same allowed pretest corpus; this is a different estimator, not an additional language channel."]
    if any((descriptive[c]["pooled"]["hr1"] or 0) < 0.01 for c in ("A", "recency")):
        warnings.append("Low absolute baseline HR@1; quality differences may be sparse and cannot support a noninferiority claim.")
    if any(sum(abs(v) > 1e-12 for v in diffs("pooled", metric, reference)) < 30 for reference in ("A", "recency") for metric in ("hr1", "ndcg_at_10")):
        warnings.append("Fewer than 30 nonzero paired user quality differences in at least one H3 comparison.")
    return {"status": "executed", "user_count": len(users), "seed_count": 3, "seeds": list(SEEDS),
            "analysis_unit": "user: average three seeds within request, requests within class, then equal eligible classes within user for pooled inference",
            "test_method": "one-sided Wilcoxon signed-rank, Pratt zeros, 12 decimal rounding, asymptotic tie adjustment; BH across all 11 tests",
            "bootstrap_resamples": n_bootstrap, "bootstrap_seed": 2026, "tests": tests, "descriptive": descriptive, "satisfaction_descriptive": satisfaction, "H3": h3,
            "H1_passed": all(r["positive_significant"] for r in tests if r["hypothesis"] == "H1" and r["class"] == "pooled"),
            "H2_passed": tests[-1]["positive_significant"], "warnings": warnings}


def _require_timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be an explicit timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"Invalid {label}") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include timezone")
    return parsed


def _identity(value: Any, label: str) -> None:
    if not isinstance(value, str) or len(value.strip()) < 3 or value.strip().lower() in {"student", "unknown", "pending", "todo", "ai", "chatgpt", "test", "placeholder"}:
        raise ValueError(f"{label} requires the actual human's identity, not a placeholder")


def manifest_case_ids(manifest: dict) -> list[str]:
    records = manifest.get("cases", manifest.get("records", manifest.get("case_ids", [])))
    ids = [r["id"] if isinstance(r, dict) else r for r in records]
    if len(ids) != 100 or len(set(ids)) != 100:
        raise ValueError("Public reserved manifest must identify exactly 100 unique test cases")
    return sorted(ids)


def _annotation_id_map(value: Any) -> dict[str, str]:
    if isinstance(value, dict) and "mapping" in value:
        value = value["mapping"]
    if isinstance(value, dict):
        return {k: (v.get("id", v.get("case_id")) if isinstance(v, dict) else v) for k, v in value.items()}
    return {r["annotation_id"]: r.get("id", r.get("case_id")) for r in value}


def validate_student_annotation_pass(annotations_path: str | Path, receipt_path: str | Path,
                                     manifest_path: str | Path, id_map_path: str | Path,
                                     sealed_sha256: str) -> dict:
    """Validate a completed independent pass before any adjudication is required."""
    paths = [Path(p) for p in (annotations_path, receipt_path, manifest_path, id_map_path)]
    if any(not p.is_file() for p in paths):
        raise ValueError("Blocked: completed independent student annotations and genuine student receipt are required")
    annotations_path, receipt_path, manifest_path, id_map_path = paths
    manifest, receipt = read_json(manifest_path), read_json(receipt_path)
    expected = manifest_case_ids(manifest)
    if manifest.get("sealed_sha256") != sealed_sha256:
        raise ValueError("Public manifest sealed commitment mismatch")
    id_map = _annotation_id_map(read_json(id_map_path))
    if set(id_map.values()) != set(expected) or len(id_map) != 100:
        raise ValueError("Blind annotation ID map must cover all 100 test cases exactly")
    _identity(receipt.get("annotator_identity"), "annotator_identity")
    student_completed = _require_timestamp(receipt.get("annotated_utc"), "annotated_utc")
    if any(receipt.get(k) is not True for k in ("student_attestation", "independent_annotation", "no_model_outputs_seen")):
        raise ValueError("Explicit student, independent annotation and no-model-output attestations are required")
    for field, actual in (("student_annotations_sha256", sha256_file(annotations_path)),
                          ("source_test_sha256", sealed_sha256)):
        if receipt.get(field) != actual:
            raise ValueError(f"Student receipt {field} mismatch")
    if sorted(receipt.get("case_ids", [])) != expected:
        raise ValueError("Student receipt must cover every canonical test ID")
    with annotations_path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    annotations = {}
    row_timestamps = []
    for row in rows:
        case_id = id_map.get(row.get("annotation_id"))
        if case_id is None or case_id in annotations:
            raise ValueError("Unknown or duplicate blind student annotation ID")
        if row.get("annotator", "").strip() != receipt["annotator_identity"].strip():
            raise ValueError("Every student row must identify the attested annotator")
        row_timestamps.append(_require_timestamp(row.get("timestamp_utc"), "student row timestamp_utc"))
        if not row.get("text"):
            raise ValueError("Student annotation text is missing")
        try:
            command = canonical({"operation": row["operation"], "directives": json.loads(row["directives_json"])})
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError("Every student row needs a valid independent command") from error
        annotations[case_id] = {"gold": command, "text_sha256": hashlib.sha256(row["text"].encode()).hexdigest()}
    if sorted(annotations) != expected:
        raise ValueError("Independent student annotation must contain all 100 test cases")
    return {"status": "verified_independent_student_pass", "annotator_identity": receipt["annotator_identity"],
            "annotated_utc": receipt["annotated_utc"], "earliest_student_utc": min([student_completed, *row_timestamps]).isoformat(),
            "latest_student_utc": max([student_completed, *row_timestamps]).isoformat(),
            "student_annotations": annotations, "case_ids": expected,
            "language_manifest": manifest, "manifest_sha256": sha256_file(manifest_path),
            "id_map_sha256": sha256_file(id_map_path), "annotation_state_dir": str(manifest_path.parent.resolve()),
            "student_annotations_sha256": sha256_file(annotations_path), "receipt_sha256": sha256_file(receipt_path)}


def validate_student_gate(annotations_path: str | Path, receipt_path: str | Path,
                          adjudication_path: str | Path, manifest_path: str | Path,
                          id_map_path: str | Path, sealed_sha256: str,
                          agreement_path: str | Path | None = None,
                          annotation_state_dir: str | Path | None = None) -> dict:
    """Require the completed independent pass, prior computed comparison and adjudication."""
    student = validate_student_annotation_pass(annotations_path, receipt_path, manifest_path, id_map_path, sealed_sha256)
    if agreement_path is None or not Path(agreement_path).is_file():
        raise ValueError("Agreement record computed before adjudication is required")
    if not Path(adjudication_path).is_file():
        raise ValueError("Completed independent student annotations and genuine adjudication receipt are required")
    receipt, adjudication = read_json(receipt_path), read_json(adjudication_path)
    expected = student["case_ids"]
    annotations = student["student_annotations"]
    if receipt.get("adjudication_sha256") != sha256_file(adjudication_path):
        raise ValueError("Student receipt adjudication_sha256 mismatch")
    _identity(adjudication.get("adjudicator_identity"), "adjudicator_identity")
    adjudication_completed = _require_timestamp(adjudication.get("completed_utc"), "adjudication completed_utc")
    if _require_timestamp(student["latest_student_utc"], "latest_student_utc") > adjudication_completed:
        raise ValueError("Student annotation timestamps must not be later than adjudication")
    if any(adjudication.get(k) is not True for k in ("disagreements_resolved", "blind_before_model_outputs", "original_annotations_preserved")):
        raise ValueError("Adjudication must resolve disagreements blind and preserve both original passes")
    if adjudication.get("source_test_sha256") != sealed_sha256 or adjudication.get("student_annotations_sha256") != sha256_file(annotations_path):
        raise ValueError("Adjudication source hashes mismatch")
    final_records = adjudication.get("final_gold", [])
    if len(final_records) != 100 or sorted(r.get("id", "") for r in final_records) != expected:
        raise ValueError("Adjudication final_gold must contain every case exactly once")
    finals = {r["id"]: canonical(r["gold"]) for r in final_records}
    for row in final_records:
        if not isinstance(row.get("reason"), str) or not row["reason"].strip():
            raise ValueError("Every adjudicated case requires an agreement or resolution reason")
    final_hash = fingerprint([{ "id": i, "gold": finals[i]} for i in expected])
    if receipt.get("final_gold_sha256") != final_hash:
        raise ValueError("Final adjudicated gold commitment mismatch")
    validate_final_gold_classes(finals, read_json(manifest_path))
    agreement_record = verify_agreement_record(agreement_path, student, sealed_sha256, adjudication["completed_utc"],
                                               annotation_state_dir=annotation_state_dir)
    if receipt.get("agreement_record_sha256") != sha256_file(agreement_path):
        raise ValueError("Final student receipt agreement_record_sha256 mismatch")
    if receipt.get("student_only_receipt_sha256") != agreement_record["student_only_receipt_sha256"]:
        raise ValueError("Final receipt does not preserve the original student-only receipt")
    return {**student, "status": "verified_human_attestations", "adjudicated_utc": adjudication["completed_utc"],
            "agreement_created_utc": agreement_record["created_utc"], "agreement_record_sha256": sha256_file(agreement_path),
            "annotation_commit_sha256": sha256_file(Path(agreement_path).with_name("annotation-commit.json")),
            "agreement_parser_commitment_sha256": agreement_record["parser_commitment_sha256"],
            "adjudicator_identity": adjudication["adjudicator_identity"], "final_gold": finals, "final_gold_sha256": final_hash}


REQUIRED_ARTIFACTS = {"parser_module", "evaluator", "runner", "protocol", "dev", "test_commitment", "data",
                      "language_manifest", "annotation_id_map", "student_annotations", "student_receipt", "adjudication",
                      "legacy_controls", "legacy_evaluation", "legacy_model", "parser_commitment", "agreement_record", "annotation_commit_record"} | {
                      f"{kind}_{seed}" for kind in ("checkpoint", "checkpoint_metadata") for seed in SEEDS}


def policy_fingerprints(categories: list[str]) -> dict:
    from .experiment2_controls import COMPOUND_PROMPT, PROMPT_VERSION, RULE_VERSION, compound_schema
    return {"prompt_sha256": fingerprint(COMPOUND_PROMPT), "schema_sha256": fingerprint(compound_schema(categories)),
            "rule_version_sha256": fingerprint(RULE_VERSION), "prompt_version": PROMPT_VERSION, "rule_version": RULE_VERSION,
            "categories_sha256": fingerprint(categories)}



def make_parser_commitment(parser_module: str | Path, development_path: str | Path,
                           sealed_path: str | Path, categories: list[str]) -> dict:
    """Commit the parser before annotation, without reading reserved case contents."""
    if Path(sealed_path).with_name("test.opened.json").exists():
        raise ValueError("Test already opened; cannot create a parser commitment")
    return {"status": "parser_frozen_before_reserved_evaluation", "created_utc": utc_now(),
            "scope": "Parser prompt, schema, rule implementation and compound ranker; human evidence and evaluator require a later full freeze.",
            "parser_module": str(Path(parser_module).resolve()), "parser_sha256": sha256_file(parser_module),
            "policy": policy_fingerprints(categories), "test_sha256": sha256_file(sealed_path),
            "development_sha256": sha256_file(development_path), "reserved_test_opened_for_evaluation": False,
            "change_rule": "Never replace a commitment; corrections require a new prospective commitment before annotation, without reserved-language or outcome tuning."}


def verify_parser_commitment(path: str | Path, artifacts: dict[str, str | Path], categories: list[str],
                             earliest_student_utc: str | None = None) -> dict:
    if not Path(path).is_file():
        raise ValueError("Parser commitment is required before independent student annotation")
    record = read_json(path)
    if record.get("status") != "parser_frozen_before_reserved_evaluation" or record.get("reserved_test_opened_for_evaluation") is not False:
        raise ValueError("Invalid parser-only commitment status")
    for field, label in (("parser_sha256", "parser_module"), ("test_sha256", "test_commitment"), ("development_sha256", "dev")):
        if record.get(field) != sha256_file(artifacts[label]):
            raise ValueError(f"Parser commitment mismatch: {field}")
    if record.get("policy") != policy_fingerprints(categories):
        raise ValueError("Parser commitment policy mismatch")
    committed_time = _require_timestamp(record.get("created_utc"), "parser commitment created_utc")
    if earliest_student_utc is not None and committed_time > _require_timestamp(earliest_student_utc, "earliest_student_utc"):
        raise ValueError("Parser commitment must precede every student row and annotation receipt timestamp")
    return record

def make_freeze_receipt(artifacts: dict[str, str | Path], categories: list[str], student_gate: dict,
                        parser_options: dict, llm_provenance: dict) -> dict:
    if set(artifacts) != REQUIRED_ARTIFACTS:
        raise ValueError(f"Freeze artifact labels differ: missing {sorted(REQUIRED_ARTIFACTS - set(artifacts))}, extra {sorted(set(artifacts) - REQUIRED_ARTIFACTS)}")
    if student_gate.get("status") != "verified_human_attestations" or len(student_gate.get("case_ids", [])) != 100:
        raise ValueError("Freeze blocked until complete independent student annotation and adjudication")
    final_gold = student_gate.get("final_gold", {})
    if set(final_gold) != set(student_gate["case_ids"]):
        raise ValueError("Final gold must cover every frozen test ID")
    if any(not category_references(command) <= set(categories) for command in final_gold.values()):
        raise ValueError("Final gold references categories outside the frozen catalogue")
    validate_final_gold_classes(final_gold, read_json(artifacts["language_manifest"]))
    created_utc = utc_now()
    freeze_time = _require_timestamp(created_utc, "freeze created_utc")
    annotated_time = _require_timestamp(student_gate.get("annotated_utc"), "annotated_utc")
    adjudicated_time = _require_timestamp(student_gate.get("adjudicated_utc"), "adjudicated_utc")
    earliest_time = _require_timestamp(student_gate.get("earliest_student_utc"), "earliest_student_utc")
    if not earliest_time <= annotated_time <= adjudicated_time <= freeze_time:
        raise ValueError("Required time order: student annotation <= adjudication <= full freeze")
    verify_parser_commitment(artifacts["parser_commitment"], artifacts, categories, student_gate["earliest_student_utc"])
    if student_gate.get("agreement_record_sha256") != sha256_file(artifacts["agreement_record"]):
        raise ValueError("Frozen agreement record differs from verified human evidence")
    if student_gate.get("agreement_parser_commitment_sha256") != sha256_file(artifacts["parser_commitment"]):
        raise ValueError("Agreement record parser commitment differs from full freeze")
    for field, label in (("manifest_sha256", "language_manifest"), ("id_map_sha256", "annotation_id_map"),
                         ("annotation_commit_sha256", "annotation_commit_record")):
        if student_gate.get(field) != sha256_file(artifacts[label]):
            raise ValueError(f"Annotation comparison evidence differs from current full-freeze artifact: {label}")
    verify_agreement_record(artifacts["agreement_record"], student_gate, sha256_file(artifacts["test_commitment"]),
                            student_gate["adjudicated_utc"], annotation_state_dir=Path(artifacts["test_commitment"]).parent,
                            commit_path=artifacts["annotation_commit_record"])
    return {"schema_version": 1, "experiment": "experiment2", "status": "frozen_before_test", "created_utc": created_utc,
            "earliest_student_utc": student_gate["earliest_student_utc"], "adjudicated_utc": student_gate["adjudicated_utc"],
            "artifacts": {label: {"path": str(Path(path).resolve()), "sha256": sha256_file(path)} for label, path in sorted(artifacts.items())},
            "policy": policy_fingerprints(categories), "parser_options": parser_options, "llm_provenance": llm_provenance,
            "seeds": list(SEEDS), "k": 10, "request_seed": 2026, "bootstrap_resamples": 5000,
            "student_receipt_sha256": student_gate["receipt_sha256"], "final_gold_sha256": student_gate["final_gold_sha256"]}


def verify_freeze_receipt(receipt: dict, artifacts: dict[str, str | Path], categories: list[str],
                          parser_options: dict | None = None) -> None:
    if receipt.get("status") != "frozen_before_test" or set(receipt.get("artifacts", {})) != REQUIRED_ARTIFACTS or set(artifacts) != REQUIRED_ARTIFACTS:
        raise ValueError("Invalid or incomplete freeze receipt")
    for label, path in artifacts.items():
        committed = receipt["artifacts"][label]
        if sha256_file(path) != committed.get("sha256"):
            raise ValueError(f"Frozen artifact changed: {label}")
    verify_parser_commitment(artifacts["parser_commitment"], artifacts, categories, receipt.get("earliest_student_utc"))
    if not _require_timestamp(receipt.get("earliest_student_utc"), "earliest_student_utc") <= _require_timestamp(receipt.get("adjudicated_utc"), "adjudicated_utc") <= _require_timestamp(receipt.get("created_utc"), "freeze created_utc"):
        raise ValueError("Frozen annotation/adjudication timeline changed")
    if receipt.get("policy") != policy_fingerprints(categories):
        raise ValueError("Frozen prompt, schema, rule version or category set changed")
    if parser_options is not None and receipt.get("parser_options") != parser_options:
        raise ValueError("Frozen parser options changed")
    if receipt.get("seeds") != list(SEEDS) or receipt.get("k") != 10 or receipt.get("bootstrap_resamples") != 5000 or receipt.get("request_seed") != 2026:
        raise ValueError("Frozen analysis constants changed")


def open_reserved_once(sealed_path: str | Path, opening_path: str | Path, freeze_path: str | Path,
                       output_path: str | Path, expected_sha256: str) -> list[dict]:
    if sha256_file(sealed_path) != expected_sha256:
        raise ValueError("Reserved test commitment changed")
    try:
        write_new_json(opening_path, {"opened_utc": utc_now(), "test_sha256": expected_sha256,
                                     "freeze_receipt_sha256": sha256_file(freeze_path), "output_path": str(Path(output_path).resolve()),
                                     "policy": "single opening; interrupted run may replay immutable evidence only"})
    except FileExistsError as error:
        raise ValueError("Reserved test already opened; only immutable cache replay is permitted") from error
    return load_cases(sealed_path, expected_count=100)


class AnnotationWordingMismatch(ValueError):
    """A retryable student worksheet transport/wording mismatch, never a label error."""


def annotation_agreement(cases: list[dict], student_gate: dict) -> dict:
    """Computed only after authorized opening; original student labels stay preserved."""
    golds = {r["id"]: canonical(r["gold"]) for r in cases}
    students = {i: a["gold"] for i, a in student_gate["student_annotations"].items()}
    if set(golds) != set(students):
        raise ValueError("Student and author case IDs differ")
    for case in cases:
        if hashlib.sha256(case["text"].encode()).hexdigest() != student_gate["student_annotations"][case["id"]]["text_sha256"]:
            raise AnnotationWordingMismatch("Student annotation wording differs from committed reserved utterance")
    author_labels = [fingerprint(golds[i]) for i in sorted(golds)]
    student_labels = [fingerprint(students[i]) for i in sorted(golds)]
    n = len(golds)
    exact_matches = sum(a == b for a, b in zip(author_labels, student_labels))
    observed = exact_matches / n
    a_count, b_count = Counter(author_labels), Counter(student_labels)
    chance = sum(a_count[label] * b_count[label] for label in set(a_count) | set(b_count)) / (n * n)
    # Align by target identity. A directive about a different target is missing,
    # even when its operation, strength, floor and condition happen to match.
    field_names = ("operation", "category", "strength", "floor", "condition_category")
    agreement_counts = {field: 0 for field in field_names}
    comparison_count, same_target_sets = 0, 0
    for case_id in golds:
        author_by_target = {d["category"]: d for d in golds[case_id]["directives"]}
        student_by_target = {d["category"]: d for d in students[case_id]["directives"]}
        targets = set(author_by_target) | set(student_by_target)
        same_target_sets += set(author_by_target) == set(student_by_target)
        comparison_count += len(targets)
        for target in targets:
            author_directive = author_by_target.get(target)
            student_directive = student_by_target.get(target)
            if author_directive is not None and student_directive is not None:
                for field in field_names:
                    agreement_counts[field] += author_directive[field] == student_directive[field]
    fields = {field: agreement_counts[field] / comparison_count if comparison_count else None for field in field_names}
    author_sizes = [len(golds[i]["directives"]) for i in sorted(golds)]
    student_sizes = [len(students[i]["directives"]) for i in sorted(golds)]
    size_matches = sum(a == b for a, b in zip(author_sizes, student_sizes))
    size_observed = size_matches / n
    author_size_counts, student_size_counts = Counter(author_sizes), Counter(student_sizes)
    size_chance = sum(author_size_counts[size] * student_size_counts[size] for size in (0, 1, 2)) / (n * n)
    return {"n": n, "full_command_exact_agreement": observed,
            "full_command_exact_agreement_numerator": exact_matches, "full_command_exact_agreement_denominator": n, "cohens_kappa": (observed - chance) / (1 - chance) if chance < 1 else None,
            "kappa_undefined_reason": "expected agreement is one" if chance == 1 else None,
            "directive_count_agreement": size_observed, "directive_count_agreement_numerator": size_matches,
            "directive_count_agreement_denominator": n,
            "directive_count_cohens_kappa": (size_observed - size_chance) / (1 - size_chance) if size_chance < 1 else None,
            "directive_count_kappa_undefined_reason": "expected agreement is one" if size_chance == 1 else None,
            "field_agreement": fields, "field_agreement_counts": agreement_counts,
            "field_comparison_count": comparison_count, "field_alignment": "union of target category IDs within each case; a missing directive disagrees on every field",
            "request_operation_agreement": sum(golds[i]["operation"] == students[i]["operation"] for i in golds) / n,
            "target_category_set_agreement": same_target_sets / n, "disagreement_ids": [i for i in sorted(golds) if golds[i] != students[i]],
            "status": "actual_preserved_human_annotations_after_authorized_opening"}



def _agreement_cases(source_text: str) -> list[dict]:
    cases = [json.loads(line) for line in source_text.splitlines() if line.strip()]
    if len(cases) != 100 or len({r["id"] for r in cases}) != 100:
        raise ValueError("Annotation comparison requires exactly 100 unique original cases")
    return cases


def _verify_author_manifest(cases: list[dict], manifest: dict) -> None:
    """The public class commitment must describe the exact original source IDs."""
    manifest_case_ids(manifest)
    public = manifest.get("cases", manifest.get("records", []))
    if len(public) != 100 or any(not isinstance(row, dict) or "class" not in row for row in public):
        raise ValueError("Public manifest must preserve every original author case ID and class")
    if {row["id"]: row.get("class") for row in cases} != {row["id"]: row["class"] for row in public}:
        raise ValueError("Original author case IDs/classes differ from the public manifest")


def _annotation_journal(state_dir: Path, first_access: dict, first_hash: str,
                        successful_attempt_id: str | None = None) -> list[dict]:
    """Validate the whole current journal, never a caller-selected historical branch."""
    attempt_dir = state_dir / "annotation-attempts"
    paths = list(attempt_dir.iterdir()) if attempt_dir.exists() else []
    starts, finishes = {}, {}
    for path in paths:
        if not path.is_file() or not path.name.endswith(("-started.json", "-finished.json")):
            raise ValueError("Annotation journal has an unknown or failed-commit record; manual review is required")
        suffix = "-started.json" if path.name.endswith("-started.json") else "-finished.json"
        attempt_id = path.name[:-len(suffix)]
        if not attempt_id:
            raise ValueError("Annotation journal has an invalid attempt ID")
        (starts if suffix == "-started.json" else finishes)[attempt_id] = read_json(path)
    if not starts or starts.keys() != finishes.keys():
        raise ValueError("Annotation journal contains an unfinished or orphan attempt")
    ordered = sorted(starts.values(), key=lambda row: row.get("attempt_index", -1))
    if [row.get("attempt_index") for row in ordered] != list(range(1, len(ordered) + 1)):
        raise ValueError("Annotation journal sequence is missing, duplicated or out of order")
    previous = None
    finished_records = []
    for index, started in enumerate(ordered):
        attempt_id = started.get("attempt_id")
        if attempt_id not in starts or starts[attempt_id] != started:
            raise ValueError("Annotation journal attempt filename differs from its record")
        finished = finishes[attempt_id]
        if finished.get("started_record") != started or finished.get("first_opening_sha256") != first_hash:
            raise ValueError("Annotation journal finished evidence differs from its immutable start or first opening")
        if started.get("prior_failed_attempt") != previous or started.get("anchors") != first_access.get("anchors"):
            raise ValueError("Annotation journal skips history or changes frozen inputs")
        if index == 0:
            if attempt_id != first_access.get("first_attempt_id") or fingerprint(started) != first_access.get("first_attempt_fingerprint"):
                raise ValueError("Annotation journal no longer matches the immutable first access")
            times = [started.get("parser_committed_utc"), started.get("earliest_student_utc"),
                     started.get("latest_student_utc"), first_access.get("created_utc"), started.get("started_utc")]
        else:
            prior_start = previous["started_record"]
            labels = lambda row: {i: r["gold"] for i, r in row.get("student_annotations", {}).items()}
            if labels(started) != labels(prior_start) or started.get("annotator_identity") != prior_start.get("annotator_identity") or not started.get("correction_reason"):
                raise ValueError("Annotation journal retry changes labels/annotator or lacks a correction reason")
            times = [previous.get("completed_utc"), started.get("started_utc")]
        parsed_times = [_require_timestamp(value, "annotation journal timestamp") for value in times]
        if parsed_times != sorted(parsed_times):
            raise ValueError("Annotation journal parser/student/access timestamps are out of order")
        if _require_timestamp(finished.get("completed_utc"), "attempt completed_utc") < _require_timestamp(started.get("started_utc"), "attempt started_utc"):
            raise ValueError("Annotation journal completion precedes its start")
        is_success = successful_attempt_id is not None and index == len(ordered) - 1
        if is_success:
            if attempt_id != successful_attempt_id or finished.get("status") != "completed" or finished.get("retryable") is not False:
                raise ValueError("Annotation journal lacks the final successful comparison")
        elif finished.get("status") != "failed_validation" or finished.get("retryable") is not True:
            raise ValueError("Annotation journal contains a nonretryable or completed attempt")
        finished_records.append(finished)
        previous = finished
    return finished_records


def _annotation_commit_evidence(state_dir: Path, agreement_path: Path, record: dict) -> dict:
    """Read successful transaction evidence through current logical locations."""
    opening, completed = state_dir / "annotation.opened.json", state_dir / "annotation.completed.json"
    if not opening.is_file() or not completed.is_file():
        raise ValueError("Annotation comparison lacks its successful completion marker or first access")
    first_access, marker = read_json(opening), read_json(completed)
    first_hash, agreement_hash = sha256_file(opening), sha256_file(agreement_path)
    attempt = record.get("annotation_attempt", {})
    if record.get("first_annotation_access") != first_access or record.get("first_opening_sha256") != first_hash:
        raise ValueError("Preserved first annotation access differs from its actual immutable marker")
    finished = _annotation_journal(state_dir, first_access, first_hash, attempt.get("attempt_id"))
    if finished[-1].get("started_record") != attempt or finished[-1].get("agreement_sha256") != agreement_hash:
        raise ValueError("Finished comparison attempt differs from the agreement bytes")
    if marker.get("attempt_id") != attempt.get("attempt_id") or marker.get("agreement_sha256") != agreement_hash or marker.get("first_opening_sha256") != first_hash:
        raise ValueError("Successful comparison marker differs from the agreement bytes")
    times = [record.get("created_utc"), marker.get("completed_utc"), finished[-1].get("completed_utc")]
    parsed_times = [_require_timestamp(value, "annotation completion timestamp") for value in times]
    if parsed_times != sorted(parsed_times):
        raise ValueError("Annotation comparison transaction timestamps are out of order")
    return {"agreement_sha256": agreement_hash,
            "first_access": {"sha256": first_hash, "record": first_access},
            "completion_marker": {"sha256": sha256_file(completed), "record": marker},
            "journal": {path.name: {"sha256": sha256_file(path), "record": read_json(path)}
                        for path in sorted((state_dir / "annotation-attempts").iterdir())}}


def _verify_annotation_commit(path: Path, state_dir: Path, agreement_path: Path, record: dict,
                              adjudicated_utc: str) -> None:
    if os.path.lexists(state_dir / "annotation.in-progress.json"):
        raise ValueError("Annotation comparison has a surviving process lock; downstream human evidence fails closed")
    if not path.is_file():
        raise ValueError("Annotation comparison has no committed successful transaction proof")
    proof = read_json(path)
    expected = _annotation_commit_evidence(state_dir, agreement_path, record)
    if proof.get("status") != "committed_annotation_comparison" or proof.get("evidence") != expected:
        raise ValueError("Annotation comparison transaction proof does not match the current complete journal")
    times = [expected["journal"][record["annotation_attempt"]["attempt_id"] + "-finished.json"]["record"]["completed_utc"],
             proof.get("created_utc"), adjudicated_utc]
    parsed_times = [_require_timestamp(value, "annotation commit timestamp") for value in times]
    if parsed_times != sorted(parsed_times):
        raise ValueError("Successful annotation transaction must finish before adjudication")



def _check_failed_annotation_history(previous: dict, first_access: dict, first_hash: str) -> None:
    """Bind every retry's preserved labels back to the immutable first attempt."""
    later_start = None
    while previous is not None:
        if previous.get("status") != "failed_validation" or previous.get("retryable") is not True or previous.get("first_opening_sha256") != first_hash:
            raise ValueError("Annotation retry history is not an immutable validation failure")
        current = previous.get("started_record", {})
        if current.get("anchors") != first_access.get("anchors"):
            raise ValueError("Annotation retry history changed frozen inputs")
        if later_start is not None:
            earlier_labels = {i: row["gold"] for i, row in current.get("student_annotations", {}).items()}
            later_labels = {i: row["gold"] for i, row in later_start.get("student_annotations", {}).items()}
            if earlier_labels != later_labels or current.get("annotator_identity") != later_start.get("annotator_identity"):
                raise ValueError("Annotation retry history changed labels or annotator")
        previous = current.get("prior_failed_attempt")
        if previous is None:
            if current.get("attempt_id") != first_access.get("first_attempt_id") or fingerprint(current) != first_access.get("first_attempt_fingerprint"):
                raise ValueError("Failed attempt evidence no longer matches the immutable first access")
        later_start = current

def compare_annotations(annotations_path: str | Path, receipt_path: str | Path, manifest_path: str | Path,
                        id_map_path: str | Path, sealed_path: str | Path, parser_commitment_path: str | Path,
                        parser_module: str | Path, dev_path: str | Path, categories: list[str], output: str | Path,
                        retry_attempt_path: str | Path | None = None, correction_reason: str | None = None) -> dict:
    """Compare once successfully; retry only recorded wording failures with unchanged labels."""
    import uuid
    sealed_path, output = Path(sealed_path), Path(output)
    source_hash = sha256_file(sealed_path)
    student = validate_student_annotation_pass(annotations_path, receipt_path, manifest_path, id_map_path, source_hash)
    receipt = read_json(receipt_path)
    if any(key in receipt for key in ("adjudication_sha256", "final_gold_sha256", "agreement_record_sha256")):
        raise ValueError("Comparison requires the original student-only receipt before adjudication")
    artifacts = {"parser_module": parser_module, "dev": dev_path, "test_commitment": sealed_path}
    parser_commitment = verify_parser_commitment(parser_commitment_path, artifacts, categories, student["earliest_student_utc"])
    started = utc_now()
    if _require_timestamp(started, "comparison started_utc") < _require_timestamp(student["latest_student_utc"], "latest_student_utc"):
        raise ValueError("Comparison cannot precede completion of the student pass")
    if sealed_path.with_name("test.opened.json").exists():
        raise ValueError("Reserved evaluation already opened; a blind annotation comparison is no longer available")
    opening = sealed_path.with_name("annotation.opened.json")
    completed = sealed_path.with_name("annotation.completed.json")
    attempt_dir = sealed_path.parent / "annotation-attempts"
    lock = sealed_path.with_name("annotation.in-progress.json")
    if completed.exists():
        raise ValueError("Annotation comparison already completed; a successful comparison cannot be rerun")
    if (output / "agreement-before-adjudication.json").exists():
        raise ValueError("Agreement output already exists; use a fresh output directory")
    anchors = {"source_test_sha256": source_hash, "parser_commitment_sha256": sha256_file(parser_commitment_path),
               "parser_sha256": sha256_file(parser_module), "development_sha256": sha256_file(dev_path),
               "manifest_sha256": sha256_file(manifest_path), "id_map_sha256": sha256_file(id_map_path)}
    attempt_id = uuid.uuid4().hex
    write_new_json(lock, {"started_utc": started, "attempt_id": attempt_id, "output_path": str(output.resolve())})
    attempt_start, first_access, finished_path = None, None, attempt_dir / f"{attempt_id}-finished.json"
    try:
        if completed.exists() or sealed_path.with_name("test.opened.json").exists():
            raise ValueError("A completed comparison or evaluation opening prevents annotation access")
        previous, journal = None, []
        if opening.exists():
            first_access = read_json(opening)
            if first_access.get("anchors") != anchors:
                raise ValueError("Retry must use the exact first-access parser commitment, bank, manifest and ID map")
            if retry_attempt_path is None or not isinstance(correction_reason, str) or not correction_reason.strip():
                raise ValueError("Annotation was already accessed; retry requires --retry-annotation-attempt and --annotation-correction-reason")
            previous_path = Path(retry_attempt_path)
            if previous_path.resolve().parent != attempt_dir.resolve() or not previous_path.is_file():
                raise ValueError("Retry must reference an immutable failed attempt for this bank")
            journal = _annotation_journal(sealed_path.parent, first_access, sha256_file(opening))
            latest_id = journal[-1]["started_record"]["attempt_id"]
            if previous_path.name != f"{latest_id}-finished.json":
                raise ValueError("Retry must reference the actual latest permissible failed attempt; older journal entries cannot be skipped")
            previous = read_json(previous_path)
            _check_failed_annotation_history(previous, first_access, sha256_file(opening))
            if previous.get("status") != "failed_validation" or previous.get("retryable") is not True:
                raise ValueError("Only an incomplete wording-validation failure permits annotation retry")
            if previous.get("first_opening_sha256") != sha256_file(opening):
                raise ValueError("Failed attempt belongs to a different first annotation opening")
            prior_start = previous.get("started_record", {})
            if prior_start.get("anchors") != anchors or prior_start.get("annotator_identity") != student["annotator_identity"]:
                raise ValueError("Retry changed parser, bank or annotator")
            prior_labels = {i: r["gold"] for i, r in prior_start.get("student_annotations", {}).items()}
            labels = {i: r["gold"] for i, r in student["student_annotations"].items()}
            if prior_labels != labels:
                raise ValueError("Annotation retry may correct wording or transport only; command labels and case IDs must remain unchanged")
        elif retry_attempt_path is not None or correction_reason is not None:
            raise ValueError("No prior annotation access exists for this retry")
        elif attempt_dir.exists() and any(attempt_dir.iterdir()):
            raise ValueError("Annotation journal exists without its immutable first-access marker")
        attempt_start = {"attempt_id": attempt_id, "attempt_index": len(journal) + 1, "started_utc": started, "anchors": anchors,
                         "parser_committed_utc": parser_commitment["created_utc"],
                         "earliest_student_utc": student["earliest_student_utc"], "latest_student_utc": student["latest_student_utc"],
                         "output_path": str(output.resolve()), "annotator_identity": student["annotator_identity"],
                         "student_annotations": student["student_annotations"],
                         "student_annotations_text": Path(annotations_path).read_bytes().decode("utf-8"),
                         "student_receipt_text": Path(receipt_path).read_bytes().decode("utf-8"),
                         "student_annotations_sha256": student["student_annotations_sha256"],
                         "student_receipt_sha256": sha256_file(receipt_path),
                         "prior_failed_attempt": previous, "correction_reason": correction_reason.strip() if correction_reason else None}
        write_new_json(attempt_dir / f"{attempt_id}-started.json", attempt_start)
        if first_access is None:
            first_access = {"created_utc": started, "purpose": "first annotation-only access before adjudication; no evaluation inference",
                            "anchors": anchors, "first_attempt_id": attempt_id, "first_attempt_fingerprint": fingerprint(attempt_start),
                            "output_path": str(output.resolve())}
            write_new_json(opening, first_access)
        source_text = sealed_path.read_bytes().decode("utf-8")
        if hashlib.sha256(source_text.encode("utf-8")).hexdigest() != source_hash:
            raise ValueError("Reserved commitment changed during annotation opening")
        cases = _agreement_cases(source_text)
        _verify_author_manifest(cases, student["language_manifest"])
        agreement = annotation_agreement(cases, student)
        if sorted(r["id"] for r in cases) != student["case_ids"]:
            raise ValueError("Original author and student case IDs differ")
        record = {"schema_version": 2, "status": "compared_before_adjudication", "started_utc": started, "created_utc": utc_now(),
                  "source_test_sha256": source_hash, "student_annotations_sha256": student["student_annotations_sha256"],
                  "student_only_receipt_sha256": sha256_file(receipt_path), "parser_commitment_sha256": sha256_file(parser_commitment_path),
                  "source_test_text": source_text, "student_annotations_text": attempt_start["student_annotations_text"],
                  "student_only_receipt_text": attempt_start["student_receipt_text"], "author_cases": cases,
                  "student_annotations": student["student_annotations"], "agreement": agreement,
                  "first_annotation_access": first_access, "first_opening_sha256": sha256_file(opening),
                  "annotation_attempt": attempt_start, "annotation_attempt_fingerprint": fingerprint(attempt_start),
                  "disagreements": [{"id": row["id"], "text": row["text"], "author_gold": canonical(row["gold"]),
                                      "student_gold": student["student_annotations"][row["id"]]["gold"]}
                                     for row in cases if canonical(row["gold"]) != student["student_annotations"][row["id"]]["gold"]]}
        write_new_json(output / "agreement-before-adjudication.json", record)
        write_new_json(completed, {"completed_utc": utc_now(), "attempt_id": attempt_id,
                                   "agreement_sha256": sha256_file(output / "agreement-before-adjudication.json"),
                                   "agreement_path": str((output / "agreement-before-adjudication.json").resolve()),
                                   "first_opening_sha256": sha256_file(opening)})
        write_new_json(finished_path, {"status": "completed", "retryable": False, "completed_utc": utc_now(),
                                       "started_record": attempt_start, "first_opening_sha256": sha256_file(opening),
                                       "agreement_sha256": sha256_file(output / "agreement-before-adjudication.json")})
        write_new_json(output / "annotation-commit.json", {"status": "committed_annotation_comparison", "created_utc": utc_now(),
                       "evidence": _annotation_commit_evidence(sealed_path.parent, output / "agreement-before-adjudication.json", record)})
        return record
    except Exception as error:
        if attempt_start is not None and not finished_path.exists():
            retryable = isinstance(error, AnnotationWordingMismatch)
            write_new_json(finished_path, {"status": "failed_validation" if retryable else "failed_nonretryable", "retryable": retryable,
                                           "completed_utc": utc_now(), "started_record": attempt_start,
                                           "first_opening_sha256": sha256_file(opening) if opening.exists() else None,
                                           "error": f"{type(error).__name__}: {error}"})
            if retryable:
                raise AnnotationWordingMismatch(f"{error}; immutable failed attempt: {finished_path}. An explicit same-label correction may retry into a fresh output.") from error
        elif attempt_start is not None:
            # A failure after a successful finish must never turn an incomplete
            # transaction into usable evidence. Preserve the successful write too.
            write_new_json(attempt_dir / f"{attempt_id}-commit-failed.json", {
                "status": "failed_nonretryable", "completed_utc": utc_now(), "attempt_id": attempt_id,
                "error": f"{type(error).__name__}: {error}"})
        raise
    finally:
        lock.unlink()


def verify_agreement_record(path: str | Path, student: dict, source_hash: str,
                            adjudicated_utc: str, annotation_state_dir: str | Path | None = None,
                            commit_path: str | Path | None = None) -> dict:
    path = Path(path)
    record = read_json(path)
    if record.get("status") != "compared_before_adjudication":
        raise ValueError("Invalid agreement-before-adjudication record")
    attempt = record.get("annotation_attempt", {})
    first_access = record.get("first_annotation_access", {})
    if record.get("annotation_attempt_fingerprint") != fingerprint(attempt):
        raise ValueError("Annotation attempt evidence changed")
    anchors = attempt.get("anchors", {})
    for field in ("manifest_sha256", "id_map_sha256"):
        if anchors.get(field) != student.get(field):
            raise ValueError(f"Annotation comparison {field} differs from the current public metadata")
    if first_access.get("anchors") != anchors or anchors.get("source_test_sha256") != source_hash or anchors.get("parser_commitment_sha256") != record.get("parser_commitment_sha256"):
        raise ValueError("Annotation access evidence does not preserve the frozen parser and bank")
    if attempt.get("student_annotations") != student["student_annotations"] or attempt.get("annotator_identity") != student["annotator_identity"]:
        raise ValueError("Annotation attempt labels or identity differ from the genuine pass")
    previous = attempt.get("prior_failed_attempt")
    if previous is not None:
        _check_failed_annotation_history(previous, first_access, record.get("first_opening_sha256"))
        prior_start = previous.get("started_record", {})
        prior_labels = {i: r["gold"] for i, r in prior_start.get("student_annotations", {}).items()}
        if previous.get("status") != "failed_validation" or previous.get("retryable") is not True or not attempt.get("correction_reason"):
            raise ValueError("Annotation retry lacks a preserved validation failure and correction reason")
        if prior_start.get("anchors") != anchors or prior_start.get("annotator_identity") != student["annotator_identity"] or prior_labels != {i: r["gold"] for i, r in student["student_annotations"].items()}:
            raise ValueError("Annotation retry changed labels, annotator or frozen inputs")
    compared = _require_timestamp(record.get("created_utc"), "agreement created_utc")
    first_time = _require_timestamp(first_access.get("created_utc"), "first annotation access created_utc")
    attempt_time = _require_timestamp(attempt.get("started_utc"), "annotation attempt started_utc")
    if not first_time <= attempt_time <= compared:
        raise ValueError("Annotation access timestamps are out of order")
    if previous is None and (first_access.get("first_attempt_id") != attempt.get("attempt_id") or first_access.get("first_attempt_fingerprint") != fingerprint(attempt)):
        raise ValueError("Initial annotation access no longer matches the first attempt")
    if previous is not None and previous.get("first_opening_sha256") != record.get("first_opening_sha256"):
        raise ValueError("Annotation retry changed the preserved first opening")
    if not _require_timestamp(student["latest_student_utc"], "latest_student_utc") <= compared <= _require_timestamp(adjudicated_utc, "adjudication completed_utc"):
        raise ValueError("Agreement comparison must follow the student pass and precede adjudication")
    expected = (("source_test_sha256", "source_test_text", source_hash),
                ("student_annotations_sha256", "student_annotations_text", student["student_annotations_sha256"]))
    for hash_key, text_key, actual in expected:
        if record.get(hash_key) != actual or not isinstance(record.get(text_key), str) or hashlib.sha256(record[text_key].encode("utf-8")).hexdigest() != actual:
            raise ValueError(f"Agreement record source mismatch: {hash_key}")
    original_receipt_text = record.get("student_only_receipt_text", "")
    if hashlib.sha256(original_receipt_text.encode("utf-8")).hexdigest() != record.get("student_only_receipt_sha256"):
        raise ValueError("Original student-only receipt bytes changed")
    original_receipt = json.loads(original_receipt_text)
    for field, expected_value in (("annotator_identity", student["annotator_identity"]), ("annotated_utc", student["annotated_utc"]),
                                  ("student_annotations_sha256", student["student_annotations_sha256"]), ("source_test_sha256", source_hash)):
        if original_receipt.get(field) != expected_value:
            raise ValueError(f"Original student-only receipt differs: {field}")
    if sorted(original_receipt.get("case_ids", [])) != student["case_ids"]:
        raise ValueError("Original student-only receipt case IDs differ")
    if any(original_receipt.get(field) is not True for field in ("student_attestation", "independent_annotation", "no_model_outputs_seen")):
        raise ValueError("Original student-only attestations missing")
    if any(field in original_receipt for field in ("adjudication_sha256", "final_gold_sha256", "agreement_record_sha256")):
        raise ValueError("Original comparison receipt already contained adjudication")
    cases = _agreement_cases(record["source_test_text"])
    _verify_author_manifest(cases, student["language_manifest"])
    if record.get("author_cases") != cases or record.get("student_annotations") != student["student_annotations"]:
        raise ValueError("Preserved original author or student labels changed")
    if record.get("agreement") != annotation_agreement(cases, student):
        raise ValueError("Recorded IAA does not recompute from preserved original annotations")
    disagreements = [{"id": row["id"], "text": row["text"], "author_gold": canonical(row["gold"]), "student_gold": student["student_annotations"][row["id"]]["gold"]}
                     for row in cases if canonical(row["gold"]) != student["student_annotations"][row["id"]]["gold"]]
    if record.get("disagreements") != disagreements:
        raise ValueError("Preserved disagreement labels differ from original annotations")
    state_dir = Path(annotation_state_dir or student["annotation_state_dir"])
    _verify_annotation_commit(Path(commit_path) if commit_path is not None else path.with_name("annotation-commit.json"),
                              state_dir, path, record, adjudicated_utc)
    return record

def parse_cases(cases: list[dict], categories: list[str], output: str | Path, parser_options: dict,
                parser=None) -> list[dict]:
    """Parse each exact utterance once per backend; preserve every error and raw result."""
    if parser is None:
        from .experiment2_controls import parse_control as parser
    output = Path(output)
    if (output / "parse_cache").exists() and any((output / "parse_cache").iterdir()):
        raise ValueError("Parse cache already exists; no repeated inference is permitted")
    records = []
    import time
    for backend in ("rule_compound", "ollama_compound"):
        for case in cases:
            started = time.monotonic()
            command, raw, error = dict(RESET), None, None
            try:
                raw = parser(case["text"], categories, backend=backend, **(parser_options if backend == "ollama_compound" else {}))
                command = canonical(raw)
            except Exception as exception:
                error = f"{type(exception).__name__}: {exception}"
            record = {"id": case["id"], "class": case["class"], "text": case["text"], "text_sha256": hashlib.sha256(case["text"].encode()).hexdigest(),
                      "backend": backend, "command": command, "raw_result": raw, "error": error,
                      "completed_utc": utc_now(), "wall_seconds": time.monotonic() - started}
            record["record_sha256"] = fingerprint(record)
            write_new_json(output / "parse_cache" / f"{backend}-{case['id']}.json", record)
            records.append(record)
    return records


def load_immutable_parse_cache(output: str | Path, cases: list[dict]) -> list[dict]:
    output = Path(output)
    expected = {f"{backend}-{case['id']}.json" for case in cases for backend in ("rule_compound", "ollama_compound")}
    files = list((output / "parse_cache").glob("*.json"))
    if {p.name for p in files} != expected:
        raise ValueError("Replay requires the complete immutable parse cache; missing parses cannot be regenerated")
    records = []
    texts = {r["id"]: r["text"] for r in cases}
    for path in sorted(files):
        row = read_json(path)
        committed = row.pop("record_sha256", None)
        if fingerprint(row) != committed or row["text"] != texts[row["id"]]:
            raise ValueError("Immutable parse record or exact wording changed")
        records.append({**row, "record_sha256": committed})
    summarize_parser(records, cases)
    return records


def run_rankings(data: dict, cases: list[dict], outcomes: list[dict], models: dict,
                 n_bootstrap: int = 5000) -> tuple[list[dict], dict, list[dict], list[dict]]:
    from .experiment2_controls import rerank
    if set(models) != set(SEEDS):
        raise ValueError("All three frozen checkpoint seeds are required")
    summarize_parser(outcomes, cases)
    parsed = {(r["id"], r["backend"]): r for r in outcomes}
    requests, exclusions = assign_requests(data, cases)
    users = {int(u["user_id"]): u for u in data["users"]}
    item_ids = sorted(int(i["item_id"]) for i in data["items"])
    catmap = {int(i["item_id"]): sorted(set(i["categories"]), key=category_key) for i in data["items"]}
    pop = Counter(int(i) for u in data["users"] for i in u["request_history"])
    recency = sorted(item_ids, key=lambda i: (-pop[i], i))
    train_hash = fingerprint([{"user_id": u["user_id"], "train": u["train"]} for u in data["users"]])
    rows, score_cache, feasible_cache = [], {}, {}
    for seed in SEEDS:
        model = models[seed]
        metadata = getattr(model, "metadata", {})
        if metadata.get("seed") != seed or metadata.get("train_sequence_sha256") != train_hash:
            raise ValueError("Checkpoint seed or training cohort provenance does not match")
        for request in requests:
            uid = request["user_id"]
            user = users[uid]
            if (seed, uid) not in score_cache:
                scores = [float(s) for s in model.score(user["train"] + user["request_history"], item_ids)]
                if len(scores) != len(item_ids) or not all(math.isfinite(s) for s in scores):
                    raise ValueError("Frozen scorer returned invalid scores")
                score_cache[(seed, uid)] = scores
            scores = score_cache[(seed, uid)]
            score_map = dict(zip(item_ids, scores))
            baseline = sorted(item_ids, key=lambda i: (-score_map[i], i))
            rankings = {"A": item_feedback_ranking(item_ids, scores, request["exemplar_item"], request["A_operation"]), "recency": recency}
            errors = {}
            for condition, backend in (("rule", "rule_compound"), ("llm", "ollama_compound")):
                outcome = parsed[(request["case_id"], backend)]
                errors[condition] = outcome.get("error")
                try:
                    rankings[condition] = rerank(item_ids, scores, catmap, outcome["command"] if not outcome.get("error") else dict(RESET))
                except Exception as exception:
                    rankings[condition] = baseline
                    errors[condition] = f"ranker: {type(exception).__name__}: {exception}"
            feasibility_key = fingerprint({"gold": request["gold"], "baseline_counts": evaluate_ranking(baseline, baseline, request["gold"], catmap, -1)["counts"]})
            if feasibility_key not in feasible_cache:
                feasible_cache[feasibility_key] = structurally_feasible(request["gold"], catmap, baseline)
            # Test relevance is accessed only after request assignment, scoring and all rankings.
            next_item = int(user["test"][0])
            for condition, ranking in rankings.items():
                metrics = evaluate_ranking(ranking, baseline, request["gold"], catmap, next_item)
                rows.append({"seed": seed, "request_id": request["request_id"], "user_id": uid, "case_id": request["case_id"],
                             "class": request["class"], "condition": condition, "parser_error": bool(errors.get(condition)),
                             "error_detail": errors.get(condition), "structurally_infeasible": not feasible_cache[feasibility_key],
                             "no_directional_opportunity": no_directional_opportunity(request["gold"], catmap, baseline),
                             "score_sha256": fingerprint(scores), "ranking_sha256": fingerprint(ranking), "baseline_sha256": fingerprint(baseline),
                             "top_10": ranking[:10], "candidate_count": len(item_ids), **metrics})
    summary = analyze_rows(rows, n_bootstrap=n_bootstrap)
    summary.update({"request_count": len(requests), "excluded_user_class_count": len(exclusions),
                    "exclusions_by_class": dict(Counter(r["class"] for r in exclusions)),
                    "structurally_infeasible_request_seed_count": sum(r["structurally_infeasible"] for r in rows if r["condition"] == "A"),
                    "baseline_satisfies_request_seed_count": sum(r["baseline_already_satisfies"] for r in rows if r["condition"] == "A"),
                    "no_directional_opportunity_request_seed_count": sum(r["no_directional_opportunity"] for r in rows if r["condition"] == "A"),
                    "floor_violations": {c: sum(r["floor_violation"] for r in rows if r["condition"] == c) for c in CONDITIONS},
                    "feasible_stratum": {c: {"denominator_request_seeds": sum(not r["structurally_infeasible"] for r in rows if r["condition"] == c),
                                               "induced_success_mean": float(np.mean([r["induced_success"] for r in rows if r["condition"] == c and not r["structurally_infeasible"]])) if any(r["condition"] == c and not r["structurally_infeasible"] for r in rows) else None} for c in CONDITIONS}})
    return rows, summary, requests, exclusions
