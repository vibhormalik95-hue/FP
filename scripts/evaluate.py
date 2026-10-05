"""Run one frozen recommender seed through the full control benchmark."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.output_safety import require_new_output
from feedctrl.evaluation import run_evaluation
from feedctrl.model import load_model


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="data/processed.json")
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--backend", choices=("rule", "ollama"), default="rule")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--request-seed", type=int, default=2026)
    parser.add_argument("--bootstrap", type=int, default=5000)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--ollama-model")
    parser.add_argument("--ollama-url")
    parser.add_argument("--timeout", type=float)
    parser.add_argument("--parse-cache", help="Read-only input JSON cache; updated cache is saved under --output/parse-cache.json")
    parser.add_argument("--cache-dir", default=os.environ.get("FEEDCTRL_PARSER_CACHE"),
                        help="Raw LLM cache; defaults to a new directory under --output")
    args = parser.parse_args()
    try:
        output = require_new_output(args.output, ROOT, directory=True)
    except ValueError as error:
        parser.error(str(error))
    data = json.loads((ROOT / args.data).read_text(encoding="utf-8"))
    predictor = load_model(ROOT / args.model_dir)
    options = {k: v for k, v in {"model": args.ollama_model, "base_url": args.ollama_url, "timeout": args.timeout}.items() if v is not None}
    if args.backend == "ollama":
        options["cache_dir"] = str(ROOT / args.cache_dir if args.cache_dir else output / "raw_llm_cache")
    cache = json.loads((ROOT / args.parse_cache).read_text(encoding="utf-8")) if args.parse_cache else {}
    summary = run_evaluation(data, predictor, output, parser_backend=args.backend, seed=args.seed,
                             request_seed=args.request_seed, k=args.k, n_bootstrap=args.bootstrap,
                             parser_kwargs=options, parse_cache=cache)
    (output / "parse-cache.json").write_text(json.dumps(cache, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("evidence_status", "user_count", "request_count", "parse_operational_errors", "all_b_rank_invariant")}, indent=2))
    return 2 if summary["evidence_status"] in ("unavailable", "degraded", "empty") else 0


if __name__ == "__main__":
    raise SystemExit(main())
