"""Aggregate paired user effects over seeds without pseudoreplication."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from feedctrl.evaluation import analyze_rows, load_metric_rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", help="request_metrics.csv paths for one backend, distinct seeds")
    parser.add_argument("--output", default="results/combined-summary.json")
    parser.add_argument("--bootstrap", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()
    rows = load_metric_rows(args.inputs)
    result = analyze_rows(rows, n_bootstrap=args.bootstrap, random_seed=args.seed)
    result["input_files"] = args.inputs
    result["seed_descriptive"] = {s: analyze_rows([r for r in rows if str(r["seed"]) == s], n_bootstrap=args.bootstrap,
                                                random_seed=args.seed)["descriptive"] for s in result["seeds"]}
    ranking_hashes = {(r["seed"], r["request_id"], r["condition"]): r["ranking_sha256"] for r in rows}
    result["all_b_rank_invariant"] = all(
        ranking_hashes[(b["seed"], b["request_id"], "A")] == b["ranking_sha256"]
        for b in rows if b["condition"] == "B")
    result["parser_failure_rows"] = sum(str(r["parser_error"]).lower() == "true" for r in rows)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"users": result["user_count"], "seeds": result["seed_count"], "output": str(path)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
