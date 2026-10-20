"""Prospective, leakage-resistant control benchmark and paired user analysis.

Synthetic controls are experimental assignments, not observations of human intent.
Every request and parser outcome is retained, including failed/clarified controls.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

CONDITIONS = ("A", "B", "C", "D", "E")
METRICS = ("target_proportion", "conditional_exposure", "fill_rate", "hr1", "ndcg_at_k", "compliant_filled_success")


def generate_requests(data: dict, request_seed: int = 2026) -> list[dict]:
    """Assign one boost and one mute from historical category support per user.

    Only catalogue metadata and train/request_history are accessed here. Separate
    construction and metric stages make test-label invariance directly testable.
    """
    item_categories = {int(i["item_id"]): tuple(sorted(set(i["categories"]))) for i in data["items"]}
    requests = []
    for user in sorted(data["users"], key=lambda x: int(x["user_id"])):
        history = list(user["train"]) + list(user["request_history"])
        historical_categories = sorted({c for i in history for c in item_categories[int(i)]})
        if not historical_categories:
            continue
        for operation in ("boost", "mute"):
            key = f"{request_seed}:{user['user_id']}:{operation}".encode()
            index = int.from_bytes(hashlib.sha256(key).digest()[:8], "big") % len(historical_categories)
            category = historical_categories[index]
            exemplar = next(int(i) for i in reversed(history) if category in item_categories[int(i)])
            text = f"Show more {category}" if operation == "boost" else f"Do not show {category}"
            profile_text = f"My preference is to see more {category}" if operation == "boost" else f"My preference is to avoid {category}"
            requests.append({"request_id": f"u{user['user_id']}-{operation}", "user_id": int(user["user_id"]),
                             "operation": operation, "category": category, "exemplar_item": exemplar,
                             "text": text, "profile_text": profile_text, "strength": 0.25,
                             "request_seed": request_seed, "source": "assigned_from_train_plus_request_history",
                             "historical_category_count": len(historical_categories)})
    return requests


def ranking_metrics(ranking: list[int], category: str, item_categories: dict[int, list[str]],
                    next_item: int, k: int = 10, operation: str = "boost") -> dict[str, float | None]:
    """Use fixed K denominator plus conditional exposure and an explicit fill gate.

    A multi-labelled item counts at most once for the requested category. An empty
    feed has exposure 0/K but cannot pass compliant_filled_success.
    """
    if k < 1:
        raise ValueError("k must be positive")
    if len(set(ranking)) != len(ranking):
        raise ValueError("Ranking contains duplicate item IDs")
    if any(i not in item_categories for i in ranking):
        raise ValueError("Ranking contains an item outside the candidate catalogue")
    top = ranking[:k]
    hits = sum(category in set(item_categories[i]) for i in top)
    full = len(top) == k
    success = full and (hits == 0 if operation == "mute" else hits > 0)
    return {"target_proportion": hits / k,
            "conditional_exposure": hits / len(top) if top else None,
            "fill_rate": len(top) / k, "hr1": float(bool(top) and top[0] == next_item),
            "ndcg_at_k": 1 / math.log2(top.index(next_item) + 2) if next_item in top else 0.0,
            "compliant_filled_success": float(success)}


def item_feedback_ranking(item_ids: list[int], scores: list[float], exemplar: int,
                          operation: str, strength: float = 0.25) -> list[int]:
    from .controls import normalize_scores
    if exemplar not in item_ids:
        raise ValueError("Historical exemplar absent from candidate catalogue")
    normalized = normalize_scores(scores)
    adjusted = {i: s + (strength if i == exemplar and operation == "boost" else 0.0)
                for i, s in zip(item_ids, normalized)}
    candidates = [i for i in item_ids if not (operation == "mute" and i == exemplar)]
    return sorted(candidates, key=lambda i: (-adjusted[i], i))


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(v) for v in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _parsed_profile(command: dict) -> dict[str, float]:
    if command["operation"] == "boost":
        return {command["category"]: float(command["strength"])}
    if command["operation"] == "mute":
        return {command["category"]: -1.0}
    return {}


def run_evaluation(data: dict, model: Any, output_dir: str | Path, parser_backend: str = "rule",
                   seed: int = 42, request_seed: int = 2026, k: int = 10,
                   n_bootstrap: int = 5000, parser_kwargs: dict | None = None,
                   parse_cache: dict | None = None, **kwargs) -> dict:
    """Evaluate all A-E conditions against the same frozen scores per user.

    Operational parser errors are written and treated as no control in affected
    channel (intention-to-treat), never silently replaced by the rule parser.
    The returned status exposes unavailable or partially failing LLM runs.
    """
    from .controls import (parse_control, parse_profile, rerank, ollama_provenance,
                           DEFAULT_MODEL, CONTROL_PROMPT, PROFILE_PROMPT)
    if parser_backend not in ("rule", "ollama"):
        raise ValueError("backend must be rule or ollama")
    if k < 1 or n_bootstrap < 100:
        raise ValueError("positive K and >=100 bootstrap resamples required")
    model_metadata = getattr(model, "metadata", {})
    training_fingerprint = _fingerprint([{"user_id": u["user_id"], "train": u["train"]} for u in data["users"]])
    if model_metadata.get("train_sequence_sha256") and model_metadata["train_sequence_sha256"] != training_fingerprint:
        raise ValueError("Model was trained on different data/user cohort")
    if model_metadata.get("seed") is not None and int(model_metadata["seed"]) != seed:
        raise ValueError("Requested evaluation seed does not match model provenance")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    item_ids = sorted(int(i["item_id"]) for i in data["items"])
    if not item_ids or len(set(item_ids)) != len(item_ids):
        raise ValueError("Candidate catalogue must be nonempty and unique")
    item_categories = {int(i["item_id"]): list(set(i["categories"])) for i in data["items"]}
    categories = sorted({c for cs in item_categories.values() for c in cs})
    users = {int(u["user_id"]): u for u in data["users"]}
    if len(users) != len(data["users"]):
        raise ValueError("Duplicate user IDs")
    if any(not u["test"] for u in users.values()):
        raise ValueError("All included users require a held-out next item")
    requests = generate_requests(data, request_seed=request_seed)
    parse_cache = {} if parse_cache is None else parse_cache
    for cache_key in list(parse_cache):
        if parse_cache[cache_key].get("error"):
            del parse_cache[cache_key]
    parser_kwargs = dict(parser_kwargs or {})
    for key in ("model", "base_url", "timeout"):
        if key in kwargs:
            parser_kwargs[key] = kwargs[key]
    llm_provenance, startup_error = None, None
    if parser_backend == "ollama":
        try:
            llm_provenance = ollama_provenance(
                base_url=parser_kwargs.get("base_url", "http://127.0.0.1:11434"),
                model=parser_kwargs.get("model", DEFAULT_MODEL), timeout=10)
        except Exception as error:
            startup_error = f"{type(error).__name__}: {error}"
    parser_policy_sha256 = _fingerprint({"control": CONTROL_PROMPT, "profile": PROFILE_PROMPT,
                                          "controls_source_sha256": hashlib.sha256(Path(__file__).with_name("controls.py").read_bytes()).hexdigest()})
    reset = {"operation": "clarify", "category": None, "strength": 0.0, "source": "evaluation_no_control"}

    def parse(text: str, channel: str = "control") -> dict:
        cache_key = _fingerprint({"text": text, "channel": channel, "backend": parser_backend, "kwargs": parser_kwargs, "categories": categories, "llm_provenance": llm_provenance, "startup_error": startup_error, "parser_policy_sha256": parser_policy_sha256})
        if cache_key not in parse_cache:
            try:
                if startup_error:
                    raise RuntimeError(startup_error)
                raw_profile_response = None
                profile = {}
                if channel == "profile":
                    raw_profile_response = parse_profile(text, categories, backend=parser_backend, **parser_kwargs)
                    if raw_profile_response.get("operation") not in ("set", "reset", "clarify"):
                        raise ValueError("Profile parser returned unknown operation")
                    profile = raw_profile_response.get("profile", {})
                    if any(c not in categories or not math.isfinite(float(v)) for c, v in profile.items()):
                        raise ValueError("Invalid profile category or value")
                    if len(profile) == 1 and raw_profile_response["operation"] == "set":
                        category, weight = next(iter(profile.items()))
                        command = {"operation": "mute" if weight < 0 else "boost", "category": category,
                                   "strength": abs(weight), "source": raw_profile_response.get("source", "profile")}
                    else:
                        command = dict(reset)
                else:
                    command = parse_control(text, categories, backend=parser_backend, **parser_kwargs)
                op = command.get("operation")
                if op not in ("boost", "mute", "reset", "clarify"):
                    raise ValueError("Parser returned unknown operation")
                if op in ("boost", "mute") and command.get("category") not in categories:
                    raise ValueError("Parser returned unknown category")
                if not math.isfinite(float(command.get("strength", 0.0))):
                    raise ValueError("Parser returned nonfinite strength")
                parse_cache[cache_key] = {"command": command, "profile": profile, "raw_profile_response": raw_profile_response,
                                          "clarified": raw_profile_response["operation"] == "clarify" if raw_profile_response is not None else command["operation"] == "clarify",
                                          "error": None, "cache_key": cache_key}
            except Exception as error:
                parse_cache[cache_key] = {"command": dict(reset), "profile": {}, "clarified": False, "error": f"{type(error).__name__}: {error}", "cache_key": cache_key}
        return parse_cache[cache_key]

    score_cache = {}
    rows, provenance = [], []
    for request in requests:
        user = users[request["user_id"]]
        history = [int(i) for i in user["train"] + user["request_history"]]
        if request["user_id"] not in score_cache:
            scores = [float(s) for s in model.score(history, item_ids)]
            if len(scores) != len(item_ids) or not all(math.isfinite(s) for s in scores):
                raise ValueError("Model returned wrong-length or nonfinite scores")
            score_cache[request["user_id"]] = scores
        scores = score_cache[request["user_id"]]
        parsed_c, parsed_d = parse(request["text"]), parse(request["profile_text"], "profile")
        command_c, command_d = parsed_c["command"], parsed_d["command"]
        profile = parsed_d["profile"]
        rank_a = item_feedback_ranking(item_ids, scores, request["exemplar_item"], request["operation"], request["strength"])
        ranks = {"A": rank_a, "B": list(rank_a),
                 "C": rerank(item_ids, scores, item_categories, command_c),
                 "D": rerank(item_ids, scores, item_categories, reset, profile=profile),
                 "E": rerank(item_ids, scores, item_categories, command_c, profile=profile)}
        assert ranks["A"] == ranks["B"], "Explanations must not change B rankings"
        for condition, ranking in ranks.items():
            required_parses = [parsed_c] if condition == "C" else [parsed_d] if condition == "D" else [parsed_c, parsed_d] if condition == "E" else []
            errors = [p["error"] for p in required_parses if p["error"]]
            clarified = any(p.get("clarified", p["command"]["operation"] == "clarify" and not p["error"]) for p in required_parses)
            intent_correct = all(p["command"]["operation"] == request["operation"] and p["command"].get("category") == request["category"] for p in required_parses)
            metrics = ranking_metrics(ranking, request["category"], item_categories, int(user["test"][0]), k, request["operation"])
            rows.append({"seed": seed, "request_id": request["request_id"], "user_id": request["user_id"],
                         "operation": request["operation"], "category": request["category"], "condition": condition,
                         "parser_backend": parser_backend, "parser_error": bool(errors), "parser_clarify": clarified,
                         "parser_intent_correct": intent_correct, "error_detail": " | ".join(errors),
                         "ranked_count": len(ranking), "candidate_count": len(item_ids),
                         "ranking_sha256": _fingerprint(ranking), "top_k": json.dumps(ranking[:k]), **metrics})
        provenance.append({**request, "seed": seed, "parsed_free_text": parsed_c, "parsed_profile": parsed_d,
                           "profile_state": profile, "ranking_hashes": {c: _fingerprint(r) for c, r in ranks.items()},
                           "score_sha256": _fingerprint(scores), "history_sha256": _fingerprint(history),
                           "explanations": {
                               "B": {"source": "verified_policy_template", "text":
                                     f"Frozen sequential-model scores plus item-only {request['operation']} feedback on historical item {request['exemplar_item']}. This explanation does not alter ranking."},
                               "E": {"source": "verified_policy_template", "text":
                                     "Frozen sequential-model scores plus validated current category commands and profile preferences; matching directives are applied once. This explanation does not alter ranking."}},
                           "b_rank_invariance": ranks["A"] == ranks["B"],
                           "c_d_e_equal": ranks["C"] == ranks["D"] == ranks["E"]})
    summary = analyze_rows(rows, n_bootstrap=n_bootstrap, random_seed=request_seed)
    used = [p[channel] for p in provenance for channel in ("parsed_free_text", "parsed_profile")]
    error_count = sum(p["error"] is not None for p in used)
    summary.update({"schema_version": 1, "created_utc": datetime.now(timezone.utc).isoformat(),
                    "backend": parser_backend, "run_seed": seed, "request_seed": request_seed, "k": k,
                    "data_sha256": _fingerprint(data), "data_metadata": data.get("metadata", {}),
                    "model_metadata": model_metadata, "verified_train_sequence_sha256": training_fingerprint,
                    "candidate_policy": "full catalogue; training/request items may recur; same pre-control candidates for A-E",
                    "next_item_policy": "first temporally ordered held-out test item; no test input to requests or scores",
                    "request_count": len(requests), "excluded_no_historical_categories": len(users) - len({r['user_id'] for r in requests}),
                    "parse_request_count": len(used), "unique_parse_count": len({p['cache_key'] for p in used}),
                    "parse_operational_errors": error_count,
                    "parser_intent_accuracy_request_weighted": {
                        condition: sum(r["parser_intent_correct"] for r in rows if r["condition"] == condition) / len(requests) if requests else None
                        for condition in ("C", "D", "E")},
                    "explanation_backend": "verified_policy_template; no human or LLM explanation-quality evaluation",
                    "parse_clarifications": sum(p.get('clarified', p['command']['operation'] == 'clarify' and not p['error']) for p in used),
                    "all_b_rank_invariant": all(p["b_rank_invariance"] for p in provenance),
                    "c_d_e_equal_request_fraction": sum(p["c_d_e_equal"] for p in provenance) / len(provenance) if provenance else None,
                    "evidence_status": "empty" if not used else "unavailable" if error_count == len(used) else "degraded" if error_count else "rule_diagnostic" if parser_backend == "rule" else "executed_llm",
                    "parser_kwargs": parser_kwargs, "llm_provenance": llm_provenance,
                    "parser_policy_sha256": parser_policy_sha256, "request_generation_accesses_test": False})
    (output / "requests.json").write_text(json.dumps(_jsonable(provenance), indent=2), encoding="utf-8")
    (output / "summary.json").write_text(json.dumps(_jsonable(summary), indent=2), encoding="utf-8")
    if rows:
        with (output / "request_metrics.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    return summary


def bh_adjust(p_values: list[float]) -> list[float]:
    """Benjamini-Hochberg step-up adjusted p-values in original order."""
    if not all(math.isfinite(p) and 0 <= p <= 1 for p in p_values):
        raise ValueError("p-values must be finite in [0,1]")
    n = len(p_values)
    order = sorted(range(n), key=p_values.__getitem__)
    adjusted, previous = [1.0] * n, 1.0
    for rank in range(n, 0, -1):
        index = order[rank - 1]
        previous = min(previous, p_values[index] * n / rank)
        adjusted[index] = previous
    return adjusted


def paired_bootstrap(differences: list[float], n_resamples: int = 5000, seed: int = 2026,
                     margin: float = 0.10, family_size: int = 3) -> dict:
    """Resample users, after all request/seed aggregation; percentile intervals.

    Positive difference favors treatment. NI H0: delta <= -margin. One-sided
    lower alpha=.05 bound is distinct from a two-sided 95% CI lower bound.
    """
    values = np.asarray(differences, dtype=float)
    if len(values) < 2:
        return {"n_users": len(values), "mean_difference": float(values.mean()) if len(values) else None,
                "ci95": None, "one_sided_lower95": None, "simultaneous_lower": None,
                "ni_margin_absolute": margin, "ni_exploratory_supported": False,
                "warning": "fewer_than_two_users"}
    if not np.isfinite(values).all() or n_resamples < 100 or family_size < 1:
        raise ValueError("Finite differences, >=100 resamples and positive family size required")
    rng = np.random.default_rng(seed)
    boot = np.empty(n_resamples)
    for start in range(0, n_resamples, 256):
        count = min(256, n_resamples - start)
        indices = rng.integers(0, len(values), size=(count, len(values)))
        boot[start:start + count] = values[indices].mean(axis=1)
    low, high = np.quantile(boot, [0.025, 0.975])
    lower95 = float(np.quantile(boot, 0.05))
    simultaneous = float(np.quantile(boot, 0.05 / family_size))
    return {"n_users": len(values), "mean_difference": float(values.mean()), "ci95": [float(low), float(high)],
            "one_sided_lower95": lower95, "simultaneous_lower": simultaneous,
            "simultaneous_family_size": family_size, "ni_margin_absolute": margin,
            "ni_exploratory_supported": bool(simultaneous > -margin and len(values) >= 30),
            "warning": "degenerate_empirical_distribution" if np.ptp(values) == 0 else "small_user_sample" if len(values) < 30 else None,
            "method": "paired_user_percentile_bootstrap", "resamples": n_resamples}


def paired_randomization_p(differences: list[float], seed: int = 2026, n_resamples: int = 10000) -> float:
    """Two-sided sign-flip test on paired user differences (exchangeability assumption)."""
    values = np.asarray(differences, dtype=float)
    if not len(values) or not np.isfinite(values).all():
        raise ValueError("Nonempty finite differences required")
    values = values[values != 0]
    if not len(values):
        return 1.0
    observed = abs(float(values.mean()))
    if len(values) <= 16:
        indices = np.arange(2 ** len(values), dtype=np.uint64)[:, None]
        signs = 2 * ((indices >> np.arange(len(values), dtype=np.uint64)) & 1).astype(float) - 1
        statistics = abs((signs * values).mean(axis=1))
        return float(np.mean(statistics >= observed - 1e-12))
    rng, greater = np.random.default_rng(seed), 0
    for start in range(0, n_resamples, 256):
        count = min(256, n_resamples - start)
        signs = rng.integers(0, 2, size=(count, len(values))) * 2 - 1
        greater += int(np.sum(abs((signs * values).mean(axis=1)) >= observed - 1e-12))
    return (greater + 1) / (n_resamples + 1)


def paired_wilcoxon_p(differences: list[float]) -> float:
    """Prespecified two-sided signed-rank test, Pratt zeros, tie-adjusted asymptotic p."""
    from scipy.stats import wilcoxon
    values = np.round(np.asarray(differences, dtype=float), decimals=12)
    if not len(values) or not np.isfinite(values).all():
        raise ValueError("Nonempty finite differences required")
    if not np.any(values):
        return 1.0
    return float(wilcoxon(values, zero_method="pratt", correction=False,
                          alternative="two-sided", method="approx").pvalue)


def analyze_rows(rows: list[dict], n_bootstrap: int = 5000, random_seed: int = 2026) -> dict:
    """Equal-weight users, within-user mean across requests and available seeds.

    Joint analyses require complete pairing across every condition and seed; this
    prevents failed or missing rows from selectively dropping hard requests.
    """
    if not rows:
        return {"user_count": 0, "seed_count": 0, "descriptive": {}, "primary_contrasts": [], "hr1_noninferiority": []}
    keys = [(str(r["seed"]), str(r["request_id"]), r["condition"]) for r in rows]
    if len(set(keys)) != len(keys):
        raise ValueError("Duplicate seed/request/condition rows")
    pairs = defaultdict(set)
    for r in rows:
        pairs[(str(r["seed"]), str(r["request_id"]))].add(r["condition"])
    if any(v != set(CONDITIONS) for v in pairs.values()):
        raise ValueError("Incomplete A-E pairing")
    backends = {r.get("parser_backend", "unknown") for r in rows}
    if len(backends) != 1:
        raise ValueError("Do not pool diagnostic and LLM backend runs")
    request_identity = defaultdict(set)
    for row in rows:
        request_identity[str(row["request_id"])].add((str(row["user_id"]), row["operation"], row["category"]))
    if any(len(identities) != 1 for identities in request_identity.values()):
        raise ValueError("Request identity changed across seeds")
    seeds = sorted({str(r["seed"]) for r in rows})
    per_seed_requests = {s: {str(r["request_id"]) for r in rows if str(r["seed"]) == s} for s in seeds}
    if any(per_seed_requests[s] != per_seed_requests[seeds[0]] for s in seeds):
        raise ValueError("Seed runs contain different request cohorts")
    buckets = defaultdict(list)
    for row in rows:
        for metric in METRICS:
            value = row.get(metric)
            if value is not None and value != "":
                buckets[(str(row["user_id"]), row["condition"], row["operation"], metric)].append(float(value))
    aggregate = {key: float(np.mean(vals)) for key, vals in buckets.items()}
    user_ids = sorted({str(r["user_id"]) for r in rows})
    descriptive = {}
    for condition in CONDITIONS:
        descriptive[condition] = {}
        for operation in ("boost", "mute"):
            descriptive[condition][operation] = {}
            for metric in METRICS:
                vals = [aggregate[(u, condition, operation, metric)] for u in user_ids if (u, condition, operation, metric) in aggregate]
                descriptive[condition][operation][metric] = float(np.mean(vals)) if vals else None
    contrasts, ni = [], []
    for condition in ("C", "D", "E"):
        for operation in ("boost", "mute"):
            diffs = [aggregate[(u, condition, operation, "target_proportion")] - aggregate[(u, "A", operation, "target_proportion")] for u in user_ids]
            stats = paired_bootstrap(diffs, n_resamples=n_bootstrap, seed=random_seed)
            contrasts.append({"condition": condition, "reference": "A", "operation": operation,
                              "metric": "TCP@K" if operation == "boost" else "TCER@K", "favorable_direction": "positive" if operation == "boost" else "negative",
                              "mean_difference": stats["mean_difference"], "ci95": stats["ci95"], "n_users": stats["n_users"],
                              "p_two_sided": paired_wilcoxon_p(diffs),
                              "p_signflip_sensitivity": paired_randomization_p(diffs, seed=random_seed),
                              "test": "Wilcoxon signed-rank; Pratt zero handling; normal approximation; two-sided",
                              "ci_method": stats.get("method"), "bootstrap_warning": stats.get("warning")})
        hr_diffs = [float(np.mean([aggregate[(u, condition, op, "hr1")] - aggregate[(u, "A", op, "hr1")] for op in ("boost", "mute")])) for u in user_ids]
        ni.append({"condition": condition, "reference": "A", "metric": "HR@1", "claim_status": "exploratory",
                   **paired_bootstrap(hr_diffs, n_resamples=n_bootstrap, seed=random_seed, margin=0.10, family_size=3)})
    for result, adjusted in zip(contrasts, bh_adjust([c["p_two_sided"] for c in contrasts])):
        result["p_bh"] = adjusted
        result["bh_family_size"] = len(contrasts)
    return {"user_count": len(user_ids), "seed_count": len(seeds), "seeds": seeds,
            "analysis_unit": "user; average requests and seeds within each user before paired inference",
            "descriptive": descriptive, "primary_contrasts": contrasts, "hr1_noninferiority": ni,
            "statistical_limitations": ["Wilcoxon signed-rank assumes symmetric user differences; Pratt zeros and ties use normal approximation. Small-sample p-values are exploratory.",
                                       "Sign-flip sensitivity p-values assume exchangeability/symmetry of user differences under the null.",
                                       "BH controls FDR under independence or suitable positive dependence; correlated contrasts are exploratory.",
                                       "Intervals condition on these seeds; three seeds do not establish population-wide training-seed robustness.",
                                       "NI margin is 0.10 absolute HR@1 points, not 10% relative loss; low baseline HR may make it weak.",
                                       "Synthetic controls measure policy compliance, not human agency or preference validity."]}


def load_metric_rows(paths: list[str | Path]) -> list[dict]:
    rows = []
    for path in paths:
        with Path(path).open(newline="", encoding="utf-8") as handle:
            rows.extend(csv.DictReader(handle))
    return rows
