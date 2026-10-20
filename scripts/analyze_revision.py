"""Versioned, post-audit sensitivity analyses of the unchanged frozen experiment.

This script performs no training, parsing, request generation, or model scoring.
It preserves the original summaries and uses the original user-paired bootstrap.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from feedctrl.evaluation import (CONDITIONS, load_metric_rows, paired_bootstrap,
                                 paired_wilcoxon_p)

OPERATIONS = ("boost", "mute")


def aggregate_rows(rows: list[dict]) -> tuple[list[str], list[str], dict]:
    """Require one paired request per user/operation/seed, then average seeds."""
    if not rows:
        raise ValueError("No metric rows")
    if len({r["parser_backend"] for r in rows}) != 1:
        raise ValueError("Do not pool parser backends")
    users = sorted({str(r["user_id"]) for r in rows})
    seeds = sorted({str(r["seed"]) for r in rows})
    seen = set()
    identities = defaultdict(set)
    request_assignments = defaultdict(set)
    buckets = defaultdict(list)
    for row in rows:
        user, seed = str(row["user_id"]), str(row["seed"])
        condition, operation = row["condition"], row["operation"]
        key = (user, seed, condition, operation)
        if key in seen:
            raise ValueError("Duplicate user/seed/condition/operation row")
        seen.add(key)
        if condition not in CONDITIONS or operation not in OPERATIONS:
            raise ValueError("Unknown condition or operation")
        identities[str(row["request_id"])].add((user, operation, row["category"]))
        request_assignments[(user, operation)].add((str(row["request_id"]), row["category"]))
        for metric in ("hr1", "ndcg_at_k", "target_proportion", "fill_rate"):
            value = float(row[metric])
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError(f"Invalid bounded metric: {metric}")
            if metric == "hr1" and value not in (0, 1):
                raise ValueError("Per-request HR@1 must be binary")
            buckets[(user, condition, operation, metric)].append(value)
    expected = {(u, s, c, o) for u in users for s in seeds for c in CONDITIONS for o in OPERATIONS}
    if seen != expected:
        raise ValueError("Incomplete paired user/seed/condition/operation matrix")
    if any(len(x) != 1 for x in identities.values()) or any(len(x) != 1 for x in request_assignments.values()):
        raise ValueError("Request identity or category changed across seeds/conditions")
    return users, seeds, {key: float(np.mean(values)) for key, values in buckets.items()}


def ni_interpretation(stats: dict, baseline: float, margin: float, informative_users: int) -> dict:
    """Keep the mathematical criterion separate from a nontrivial-margin guard.

    The guard is a descriptive diagnostic, not a new validated power criterion.
    Passing it alone does not establish adequacy of the benchmark or margin.
    """
    if not math.isfinite(baseline) or not 0 <= baseline <= 1:
        raise ValueError("Baseline must be in [0,1]")
    if not math.isfinite(margin) or not 0 <= margin <= 1:
        raise ValueError("Margin must be in [0,1]")
    lower = stats.get("simultaneous_lower")
    raw_pass = lower is not None and lower > -margin and stats["n_users"] >= 30
    complete_loss_allowed = margin >= baseline
    informative = bool(raw_pass and not complete_loss_allowed and informative_users > 0 and baseline > 0)
    return {
        "margin_absolute": margin,
        "baseline_hr1": baseline,
        "margin_exceeds_baseline": margin > baseline,
        "margin_allows_complete_baseline_loss": complete_loss_allowed,
        "statistical_criterion_passed": bool(raw_pass),
        "informative_statistical_support": informative,
        "interpretation": ("statistical_criterion_failed" if not raw_pass else
                           "passes_but_margin_allows_complete_baseline_loss" if complete_loss_allowed else
                           "passes_nontrivial_margin_guard_subject_to_sparse_outcome_limitations" if informative else
                           "passes_but_no_informative_user_differences"),
    }


def analyze_backend(rows: list[dict], data: dict, n_bootstrap: int = 5000, seed: int = 2026) -> dict:
    users, seeds, means = aggregate_rows(rows)
    data_users = {str(u["user_id"]) for u in data["users"]}
    if set(users) != data_users:
        raise ValueError("Metric users differ from processed cohort")
    get = lambda condition, operation, metric: [means[(u, condition, operation, metric)] for u in users]
    baseline_by_operation = {o: float(np.mean(get("A", o, "hr1"))) for o in OPERATIONS}
    baseline_user = np.asarray([np.mean([means[(u, "A", o, "hr1")] for o in OPERATIONS]) for u in users])
    baseline = float(baseline_user.mean())
    ni = []
    for condition in ("C", "D", "E"):
        treatment_user = np.asarray([np.mean([means[(u, condition, o, "hr1")] for o in OPERATIONS]) for u in users])
        # Match the frozen analysis's operation-paired difference arithmetic/order.
        differences = [float(np.mean([means[(u, condition, o, "hr1")] - means[(u, "A", o, "hr1")] for o in OPERATIONS])) for u in users]
        stats = paired_bootstrap(differences, n_resamples=n_bootstrap, seed=seed, margin=.10, family_size=3)
        informative_users = int(np.count_nonzero(np.round(differences, 12)))
        ni.append({
            "condition": condition, "reference": "A", "metric": "HR@1",
            "claim_status": "post_audit_exploratory_sensitivity",
            "n_users": len(users), "informative_users_nonzero_paired_difference": informative_users,
            "users_with_any_baseline_hit": int(np.count_nonzero(baseline_user)),
            "baseline_hr1": baseline, "treatment_hr1": float(treatment_user.mean()),
            "baseline_hr1_by_operation": baseline_by_operation,
            "mean_difference": stats["mean_difference"], "ci95": stats["ci95"],
            "one_sided_lower95": stats["one_sided_lower95"],
            "simultaneous_lower": stats["simultaneous_lower"],
            "bonferroni_family_size": 3, "one_sided_family_alpha": .05,
            "bootstrap_method": stats["method"], "bootstrap_resamples": n_bootstrap,
            "bootstrap_random_seed": seed,
            "decision_rule": "simultaneous_lower > -margin AND n_users >= 30 (unchanged original rule)",
            "absolute_10_percentage_points": ni_interpretation(stats, baseline, .10, informative_users),
            "relative_10_percent_of_observed_reference": ni_interpretation(stats, baseline, .10 * baseline, informative_users),
            "relative_margin_caveat": "Sensitivity uses 10% of observed A HR@1, held fixed while bootstrapping paired differences. It is not a prospectively justified margin or a full ratio-based NI analysis.",
        })
    ndcg_a = np.asarray(get("A", "boost", "ndcg_at_k"))
    ndcg_c = np.asarray(get("C", "boost", "ndcg_at_k"))
    differences = ndcg_c - ndcg_a
    ndcg_stats = paired_bootstrap(differences.tolist(), n_resamples=n_bootstrap, seed=seed)
    ndcg = {
        "condition": "C", "reference": "A", "operation": "boost", "metric": "NDCG@10",
        "claim_status": "post_hoc_secondary_contrast_not_in_primary_BH_family",
        "n_users": len(users), "informative_users_nonzero_paired_difference": int(np.count_nonzero(np.round(differences, 12))),
        "reference_mean": float(ndcg_a.mean()), "condition_mean": float(ndcg_c.mean()),
        "mean_difference": ndcg_stats["mean_difference"], "ci95": ndcg_stats["ci95"],
        "relative_change": float(ndcg_c.mean() / ndcg_a.mean() - 1) if ndcg_a.mean() else None,
        "p_two_sided_unadjusted": paired_wilcoxon_p(differences.tolist()),
        "test": "Wilcoxon signed-rank; Pratt zeros; normal approximation; two-sided; rounded differences to 12 decimals",
        "ci_method": "paired_user_percentile_bootstrap", "bootstrap_resamples": n_bootstrap, "bootstrap_random_seed": seed,
        "interpretation": "Exploratory paired quality trade-off, conditional on the three frozen seeds; no new confirmatory family is claimed.",
    }
    counts = Counter(c for item in data["items"] for c in set(item["categories"]))
    assigned = sorted({r["category"] for r in rows})
    if any(c not in counts for c in assigned):
        raise ValueError("Assigned category missing from catalogue")
    catalogue_ids = {int(item["item_id"]) for item in data["items"]}
    if len(catalogue_ids) != len(data["items"]):
        raise ValueError("Duplicate catalogue item")
    items = {int(item["item_id"]): set(item["categories"]) for item in data["items"]}
    ks = set()
    for row in rows:
        top = json.loads(row["top_k"]) if isinstance(row["top_k"], str) else row["top_k"]
        if len(top) != len(set(top)) or not set(top).issubset(catalogue_ids):
            raise ValueError("Invalid saved top-k ranking")
        fill = float(row["fill_rate"])
        if fill <= 0:
            raise ValueError("K cannot be inferred from empty saved ranking")
        k_float = len(top) / fill
        if not math.isclose(k_float, round(k_float)):
            raise ValueError("Inconsistent K and fill rate")
        k = round(k_float)
        ks.add(k)
        if not math.isclose(sum(row["category"] in items[i] for i in top) / k, float(row["target_proportion"]), abs_tol=1e-12):
            raise ValueError("Saved TCP disagrees with saved top-k and catalogue")
    if len(ks) != 1:
        raise ValueError("Mixed K values")
    k = ks.pop()
    saturation = {
        "k": k, "catalogue_items": len(catalogue_ids), "catalogue_categories": len(counts),
        "assigned_categories": len(assigned), "category_item_counts": dict(sorted(counts.items())),
        "assigned_category_min_items": min(counts[c] for c in assigned),
        "assigned_category_max_items": max(counts[c] for c in assigned),
        "every_assigned_category_has_at_least_k_items": all(counts[c] >= k for c in assigned),
        "every_assigned_category_has_at_least_k_other_items": all(len(catalogue_ids) - counts[c] >= k for c in assigned),
        "boost_users_saturated_tcp_one_all_seeds": {c: sum(math.isclose(v, 1., abs_tol=1e-12) for v in get(c, "boost", "target_proportion")) for c in CONDITIONS},
        "boost_saturation_by_seed": {s: {c: sum(float(r["target_proportion"]) == 1 for r in rows if str(r["seed"]) == s and r["operation"] == "boost" and r["condition"] == c) for c in CONDITIONS} for s in seeds},
        "mute_users_zero_exposure_all_seeds": {c: sum(v == 0 for v in get(c, "mute", "target_proportion")) for c in CONDITIONS},
        "item_only_boost_max_tcp_change_from_uncontrolled": 1 / k,
        "interpretation": "Category-level policies act on many items; A edits one item. Hard mute guarantees zero target exposure when validly parsed and sufficient other items exist. Positive boost favors target items but does not universally guarantee a strict TCP gain. Observed gains and saturation therefore demonstrate policy compliance, not independent LLM value or mass-matched interface superiority.",
    }
    return {"backend": rows[0]["parser_backend"], "row_count": len(rows), "user_count": len(users), "seeds": seeds,
            "analysis_unit": "user; equal-weight mean across frozen seeds; NI also averages boost and mute within user",
            "hr1_noninferiority_sensitivity": ni, "boost_ndcg_tradeoff": ndcg, "policy_saturation": saturation}


def stable_write(path: Path, contents: bytes) -> None:
    if path.exists() and path.read_bytes() != contents:
        raise ValueError(f"Refusing to overwrite a different versioned analysis artifact: {path}; increment --version")
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(contents)


def render_markdown(result: dict) -> str:
    lines = ["# Post-audit analysis, version " + str(result["version"]), "", "This is a supplemental analysis of frozen outputs. No experiments were rerun or rewritten. Original combined summaries are preserved beside this report. All new analyses are exploratory; the primary family is unchanged.", ""]
    for backend, analysis in result["backends"].items():
        ni, ndcg, sat = analysis["hr1_noninferiority_sensitivity"][0], analysis["boost_ndcg_tradeoff"], analysis["policy_saturation"]
        lines += [f"## {backend}", "", f"{analysis['user_count']} users; seeds {', '.join(analysis['seeds'])}; {analysis['row_count']} metric rows.", "",
                  f"For each of C, D, and E versus A, the original NI analysis averages seeds and both operations within user. Its paired A baseline is {ni['baseline_hr1']:.12f} ({100*ni['baseline_hr1']:.6f}%), rather than the boost-only baseline of {ni['baseline_hr1_by_operation']['boost']:.12f}. The common mean HR@1 difference is {ni['mean_difference']:.12f}, and the Bonferroni family-of-three lower bound is {ni['simultaneous_lower']:.12f}.", "",
                  "| Reading of proposal margin | Absolute margin | Statistical criterion | Informative support |", "|---|---:|---|---|"]
        for label, key in (("10 percentage points", "absolute_10_percentage_points"), ("10% of observed A HR@1", "relative_10_percent_of_observed_reference")):
            item = ni[key]
            lines.append(f"| {label} | {item['margin_absolute']:.12f} | {'Pass' if item['statistical_criterion_passed'] else 'Fail'} | {'Passes nontrivial-margin guard only' if item['informative_statistical_support'] else 'No'} |")
        lines += ["", f"The absolute margin exceeds baseline and permits losing every baseline hit. Its mathematical exploratory pass is preserved, but is not evidence of practically preserved accuracy. The relative reading fails the same decision rule. There are {ni['informative_users_nonzero_paired_difference']}/{ni['n_users']} users with nonzero paired HR@1 differences. The relative margin is an observed-baseline sensitivity with that margin held fixed, not a prospectively specified ratio analysis. Neither reading resolves supervisor approval or margin justification.", "",
                  f"Post-hoc boost C−A NDCG@10: {ndcg['reference_mean']:.12f} → {ndcg['condition_mean']:.12f}; paired difference {ndcg['mean_difference']:.12f}, 95% user-bootstrap CI [{ndcg['ci95'][0]:.12f}, {ndcg['ci95'][1]:.12f}], relative change {ndcg['relative_change']:.2%}; two-sided Wilcoxon–Pratt p={ndcg['p_two_sided_unadjusted']:.6g}. Nonzero paired differences: {ndcg['informative_users_nonzero_paired_difference']}/{ndcg['n_users']}. This is an unadjusted exploratory secondary contrast, outside the unchanged primary BH family.", "",
                  f"Catalogue: {sat['catalogue_items']} items, {sat['catalogue_categories']} categories; {sat['assigned_categories']} assigned categories contain {sat['assigned_category_min_items']}–{sat['assigned_category_max_items']} items each. In C, {sat['boost_users_saturated_tcp_one_all_seeds']['C']}/{analysis['user_count']} boost users have TCP=1 across all seeds; {sat['mute_users_zero_exposure_all_seeds']['C']}/{analysis['user_count']} mute users have zero exposure across all seeds. A's single-item boost can change TCP by at most {sat['item_only_boost_max_tcp_change_from_uncontrolled']:.1f} versus uncontrolled ranking.", "", sat["interpretation"], ""]
    lines += ["## Interpretation boundaries", "", "Hard mute has a structural compliance advantage. A positive +0.25 category boost does not mathematically guarantee a strict increase for every possible ranking (ties, already-saturated lists, or large score gaps can yield no change). The observed primary hypothesis is statistically supported on this cohort, but its interpretation is restricted by deterministic policy enforcement, category/item intervention granularity, saturation, and identical rule/LLM main results. Claims of broad LLM benefit or general recommendation quality do not follow.", "", "The bootstrap conditions on these users and three realized training seeds. Sparse nonzero HR@1 differences weaken precision and resampling reliability; 865 total users alone does not cure the sparse-outcome problem.", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--version", type=int, default=1)
    parser.add_argument("--bootstrap", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()
    if args.version < 1 or args.bootstrap < 100:
        parser.error("Positive version and >=100 bootstrap resamples required")
    root = args.project.resolve()
    output = (args.output_dir or root / "results/audit_revision").resolve()
    prefix = f"analysis-v{args.version}"
    data_path = root / "data/processed.json"
    data = json.loads(data_path.read_text(encoding="utf-8"))
    input_paths = [data_path, root / "feedctrl/evaluation.py"]
    result = {"schema_version": 1, "version": args.version, "status": "supplemental_post_audit_analysis",
              "frozen_experiment_modified": False, "backends": {}}
    snapshots = {}
    for backend in ("rule", "llm"):
        paths = sorted((root / "results" / backend).glob("seed_*/request_metrics.csv"))
        if not paths:
            raise ValueError(f"No frozen metric inputs for {backend}")
        summary_path = root / "results" / backend / "combined-summary.json"
        input_paths += paths + [summary_path]
        snapshots[backend] = summary_path.read_bytes()
        analysis = analyze_backend(load_metric_rows(paths), data, args.bootstrap, args.seed)
        original = json.loads(snapshots[backend])
        if args.bootstrap == 5000 and args.seed == 2026:
            for revised, frozen in zip(analysis["hr1_noninferiority_sensitivity"], original["hr1_noninferiority"]):
                for field in ("mean_difference", "ci95", "one_sided_lower95", "simultaneous_lower"):
                    if not np.allclose(revised[field], frozen[field], rtol=0, atol=1e-15):
                        raise ValueError(f"Frozen NI replay mismatch: {backend}/{field}")
        result["backends"][backend] = analysis
    result["rule_llm_metrics_identical"] = all(
        result["backends"]["rule"][field] == result["backends"]["llm"][field]
        for field in ("hr1_noninferiority_sensitivity", "boost_ndcg_tradeoff", "policy_saturation"))
    manifest = {"schema_version": 1, "purpose": "frozen input hashes and byte-exact original combined-summary copies",
                "files": {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in input_paths},
                "analysis_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    # Snapshot before writing new interpretations; versioning rejects accidental replacement.
    for backend, raw in snapshots.items():
        stable_write(output / f"{prefix}-original" / f"{backend}-combined-summary.json", raw)
    stable_write(output / f"{prefix}-input-manifest.json", (json.dumps(manifest, indent=2) + "\n").encode())
    stable_write(output / f"{prefix}.json", (json.dumps(result, indent=2, allow_nan=False) + "\n").encode())
    stable_write(output / f"{prefix}.md", render_markdown(result).encode())
    if any(hashlib.sha256((root / p).read_bytes()).hexdigest() != h for p, h in manifest["files"].items()):
        raise RuntimeError("Frozen input changed during analysis")
    print(json.dumps({"json": str(output / f"{prefix}.json"), "markdown": str(output / f"{prefix}.md"), "frozen_inputs_unchanged": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
