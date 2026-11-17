"""Scoring of the KuaiRec language-control evaluation against the frozen, human-reviewed reference.

Per case (all functions are pure; inputs are the frozen reference and one model's prediction):

* NL (nonliteral request -> existing labels). The selected label set S is scored against the
  reference REQUIRED set R and ACCEPTABLE set A. Exact intended profile: status "propose",
  every control has the reference action, and R <= S <= R | A. Label precision |S & (R|A)| / |S|,
  recall |S & R| / |R|. A missed required label is a retrieval miss.
* AB (should not propose). Correct abstention: no applicable control. False acceptance: at
  least one applicable control. Status match: the returned status equals the expected one; for
  cases the reviewer marked "any_abstain", any non-propose status without a control matches.
* NC (new category). Member precision/recall/F1 of the selected set (verdict match, quotation
  found, independent check supports) against the reference members of the shared pool; the raw
  classifier verdicts are scored too. A missed reference member is a retrieval miss.

Confidence intervals: Wilson for proportions, a seeded percentile bootstrap over cases for
means. Paired tests between models: exact McNemar on per-case success and the Wilcoxon
signed-rank test (Pratt) on per-case F1, Benjamini-Hochberg across the comparisons, as named
in the proposal (alpha 0.05).
"""
from __future__ import annotations

import math
import random
from itertools import combinations

from scipy.stats import binomtest, wilcoxon


def wilson(k, n, z=1.959964):
    if not n:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 4), round(min(1.0, c + h), 4)]


def bootstrap_ci(values, n=5000, seed=2026):
    values = [v for v in values if v is not None]
    if not values:
        return None
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(values) for _ in values) / len(values) for _ in range(n))
    return [round(means[int(0.025 * n)], 4), round(means[int(0.975 * n) - 1], 4)]


def prf(selected, reference):
    selected, reference = set(selected), set(reference)
    tp = len(selected & reference)
    p = tp / len(selected) if selected else (1.0 if not reference else 0.0)
    r = tp / len(reference) if reference else (1.0 if not selected else 0.0)
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def score_nl(case, pred):
    controls = pred.get("controls") or []
    labels = {c["term_id"] for c in controls}
    actions = {c["action"] for c in controls}
    required, acceptable = set(case["required"]), set(case["acceptable"])
    allowed = required | acceptable
    proposed = pred.get("status") == "propose" and bool(controls)
    action_ok = proposed and actions == {case["action"]}
    exact = action_ok and required <= labels <= allowed
    precision = len(labels & allowed) / len(labels) if labels else 0.0
    recall = len(labels & required) / len(required) if required else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"case_id": case["id"], "group": "NL", "language": case["language"], "status": pred.get("status"),
            "error": pred.get("error"), "proposed": proposed, "action_ok": action_ok, "exact": exact,
            "label_precision": precision, "label_recall": recall, "label_f1": f1,
            "missed_required": sorted(required - labels), "wrong_labels": sorted(labels - allowed),
            "selected_labels": sorted(labels)}


def score_ab(case, pred):
    applicable = bool(pred.get("controls"))
    return {"case_id": case["id"], "group": "AB", "language": case["language"], "status": pred.get("status"),
            "error": pred.get("error"), "abstained": not applicable and not pred.get("error"),
            "false_acceptance": applicable,
            "status_match": (not applicable and not pred.get("error") and pred.get("status") != "propose")
            if case["expected_status"] == "any_abstain" else pred.get("status") == case["expected_status"]}


def score_nc(case, pred):
    dropped = {int(i) for i in case.get("excluded", [])}     # reviewer: drop from scoring
    reference = {int(i) for i in case["members"]} - dropped
    selected = {int(i) for i in pred.get("selected", [])} - dropped
    raw = {int(i) for i in pred.get("raw_match", [])} - dropped
    p, r, f = prf(selected, reference)
    rp, rr, rf = prf(raw, reference)
    return {"case_id": case["id"], "group": "NC", "language": case["language"], "error": pred.get("error"),
            "reference_members": len(reference), "selected": len(selected), "member_precision": p,
            "member_recall": r, "member_f1": f, "raw_precision": rp, "raw_recall": rr, "raw_f1": rf,
            "missed_members": sorted(reference - selected), "false_members": sorted(selected - reference),
            "unknown_or_missing": pred.get("unknown", 0), "quote_failures": pred.get("quote_failures", 0),
            "exact": selected == reference}


def summarize(rows, calls):
    nl = [r for r in rows if r["group"] == "NL"]
    ab = [r for r in rows if r["group"] == "AB"]
    nc = [r for r in rows if r["group"] == "NC"]
    k_exact = sum(r["exact"] for r in nl)
    lat = sorted(c["latency_s"] for c in calls if c.get("latency_s") is not None)
    out = {
        "nl_cases": len(nl), "nl_exact": k_exact, "nl_exact_rate": k_exact / len(nl) if nl else None,
        "nl_exact_wilson": wilson(k_exact, len(nl)),
        "nl_action_rate": sum(r["action_ok"] for r in nl) / len(nl) if nl else None,
        "nl_label_precision": _mean(r["label_precision"] for r in nl),
        "nl_label_recall": _mean(r["label_recall"] for r in nl), "nl_label_f1": _mean(r["label_f1"] for r in nl),
        "nl_label_f1_ci": bootstrap_ci([r["label_f1"] for r in nl]),
        "nl_unwanted_clarification": sum(not r["proposed"] for r in nl),
        "ab_cases": len(ab), "ab_abstained": sum(r["abstained"] for r in ab),
        "ab_abstention_rate": sum(r["abstained"] for r in ab) / len(ab) if ab else None,
        "ab_abstention_wilson": wilson(sum(r["abstained"] for r in ab), len(ab)),
        "false_acceptance": sum(r["false_acceptance"] for r in ab),
        "ab_status_match": sum(r["status_match"] for r in ab),
        "nc_cases": len(nc), "nc_member_precision": _mean(r["member_precision"] for r in nc),
        "nc_member_recall": _mean(r["member_recall"] for r in nc), "nc_member_f1": _mean(r["member_f1"] for r in nc),
        "nc_member_f1_ci": bootstrap_ci([r["member_f1"] for r in nc]),
        "nc_raw_f1": _mean(r["raw_f1"] for r in nc),
        "retrieval_misses_labels": sum(len(r["missed_required"]) for r in nl),
        "retrieval_misses_members": sum(len(r["missed_members"]) for r in nc),
        "errors": sum(bool(r.get("error")) for r in rows),
        "calls": len(calls), "call_errors": sum(bool(c.get("error")) for c in calls),
        "cost_usd": round(sum(c.get("cost_usd") or 0 for c in calls), 4),
        "latency_median_s": lat[len(lat) // 2] if lat else None,
        "latency_p90_s": lat[int(0.9 * (len(lat) - 1))] if lat else None,
    }
    return out


def _mean(values):
    values = list(values)
    return sum(values) / len(values) if values else None


def success(row):
    """One per-case success bit for paired tests across all groups."""
    if row["group"] == "NL":
        return row["exact"]
    if row["group"] == "AB":
        return row["abstained"]
    return row["member_f1"] >= 0.8


def per_case_score(row):
    return {"NL": row.get("label_f1"), "NC": row.get("member_f1"),
            "AB": 1.0 if row.get("abstained") else 0.0}[row["group"]]


def bh(pvalues):
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i])
    adjusted = [0.0] * m
    running = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        running = min(running, pvalues[i] * m / rank)
        adjusted[i] = running
    return adjusted


def paired_tests(by_model):
    """by_model: model -> list of case rows (same case order). Returns pairwise test rows."""
    models = sorted(by_model)
    tests = []
    for a, b in combinations(models, 2):
        ra = {r["case_id"]: r for r in by_model[a]}
        rb = {r["case_id"]: r for r in by_model[b]}
        ids = sorted(set(ra) & set(rb))
        sa = [success(ra[i]) for i in ids]
        sb = [success(rb[i]) for i in ids]
        only_a = sum(x and not y for x, y in zip(sa, sb))
        only_b = sum(y and not x for x, y in zip(sa, sb))
        mcnemar = binomtest(only_a, only_a + only_b, 0.5).pvalue if only_a + only_b else 1.0
        da = [per_case_score(ra[i]) for i in ids]
        db = [per_case_score(rb[i]) for i in ids]
        diffs = [x - y for x, y in zip(da, db) if x is not None and y is not None]
        if any(abs(d) > 1e-12 for d in diffs):
            w = wilcoxon(diffs, zero_method="pratt").pvalue
        else:
            w = 1.0
        tests.append({"a": a, "b": b, "cases": len(ids), "success_a": sum(sa), "success_b": sum(sb),
                      "only_a": only_a, "only_b": only_b, "mcnemar_p": mcnemar,
                      "mean_score_diff": sum(diffs) / len(diffs) if diffs else 0.0, "wilcoxon_p": w})
    for key in ("mcnemar_p", "wilcoxon_p"):
        adjusted = bh([t[key] for t in tests])
        for t, p in zip(tests, adjusted):
            t[key + "_bh"] = p
    return tests
