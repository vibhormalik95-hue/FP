"""Run all frozen seeds, grouping LLM prompt warmup to reuse local prompt cache."""
from __future__ import annotations

import argparse
import gc
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.output_safety import require_new_output
from feedctrl.controls import parse_control, parse_profile, ollama_provenance
from feedctrl.data import load_data
from feedctrl.evaluation import generate_requests, run_evaluation, analyze_rows, load_metric_rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="data/processed.json")
    parser.add_argument("--models", default="results/models")
    parser.add_argument("--output", required=True)
    parser.add_argument("--backend", choices=("rule", "ollama"), default="rule")
    parser.add_argument("--seeds", type=int, nargs="+", default=[42, 43, 44])
    parser.add_argument("--bootstrap", type=int, default=5000)
    parser.add_argument("--ollama-model", default="llama3.1:8b")
    parser.add_argument("--num-thread", type=int, default=6)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--cache-dir", default=os.environ.get("FEEDCTRL_PARSER_CACHE"),
                        help="Raw LLM cache; defaults to a new directory under --output")
    args = parser.parse_args()
    start = time.monotonic()
    try:
        output = require_new_output(args.output, ROOT, directory=True)
    except ValueError as error:
        parser.error(str(error))
    output.mkdir(parents=True, exist_ok=True)
    data = load_data(ROOT / args.data)
    cache_dir = ROOT / args.cache_dir if args.cache_dir else output / "raw_llm_cache"
    options = {"model": args.ollama_model, "num_thread": args.num_thread, "base_url": args.ollama_url, "timeout": args.timeout,
               "cache_dir": str(cache_dir)} if args.backend == "ollama" else {}
    if args.backend == "ollama":
        provenance = ollama_provenance(model=args.ollama_model, base_url=args.ollama_url)
        print(json.dumps({"stage": "llm_provenance", **provenance}), flush=True)
        requests = generate_requests(data)
        categories = sorted({c for i in data["items"] for c in i["categories"]})
        warm = []
        # Same-system-prompt requests are adjacent, reducing CPU prompt evaluation.
        for key, function in (("text", parse_control), ("profile_text", parse_profile)):
            texts = sorted({r[key] for r in requests})
            for index, text in enumerate(texts):
                try:
                    result = function(text, categories, backend="ollama", **options)
                    row = {"channel": key, "text": text, "result": result, "error": None}
                except Exception as error:
                    row = {"channel": key, "text": text, "result": None, "error": f"{type(error).__name__}: {error}"}
                warm.append(row)
                (output / "warmup.json").write_text(json.dumps(warm, indent=2), encoding="utf-8")
                print(json.dumps({"stage": "llm_warmup", "channel": key, "completed": index + 1,
                                  "total": len(texts), "error": row["error"]}), flush=True)
    from feedctrl.model import load_model
    cache = {}
    statuses = {}
    for seed in args.seeds:
        model = load_model(ROOT / args.models / f"seed_{seed}")
        result = run_evaluation(data, model, output / f"seed_{seed}", parser_backend=args.backend,
                                seed=seed, parser_kwargs=options, parse_cache=cache,
                                n_bootstrap=args.bootstrap)
        statuses[str(seed)] = result["evidence_status"]
        (output / "parse-cache.json").write_text(json.dumps(cache, indent=2), encoding="utf-8")
        print(json.dumps({"stage": "seed_complete", "seed": seed, "status": result["evidence_status"],
                          "users": result["user_count"], "requests": result["request_count"]}), flush=True)
        del model
        gc.collect()
    paths = [output / f"seed_{s}" / "request_metrics.csv" for s in args.seeds]
    rows = load_metric_rows(paths)
    combined = analyze_rows(rows, n_bootstrap=args.bootstrap)
    combined.update({"input_files": [str(p) for p in paths], "seed_statuses": statuses,
                     "backend": args.backend, "wall_seconds": time.monotonic() - start})
    combined["seed_descriptive"] = {str(s): json.loads((output / f"seed_{s}" / "summary.json").read_text(encoding="utf-8"))["descriptive"] for s in args.seeds}
    hashes = {(r["seed"], r["request_id"], r["condition"]): r["ranking_sha256"] for r in rows}
    combined["all_b_rank_invariant"] = all(hashes[(r["seed"], r["request_id"], "A")] == r["ranking_sha256"] for r in rows if r["condition"] == "B")
    (output / "combined-summary.json").write_text(json.dumps(combined, indent=2), encoding="utf-8")
    print(json.dumps({"stage": "complete", "output": str(output), "wall_seconds": combined["wall_seconds"]}), flush=True)
    return 2 if any(s in ("unavailable", "degraded", "empty") for s in statuses.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
