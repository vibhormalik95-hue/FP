"""Re-run the frozen 100-case parser test bank with other models. RE-USE, NOT NEW EVIDENCE.

The bank (data/parser_test.jsonl) was used for the frozen Experiment 1 result (Llama 3.1 8B:
79/100, rules 81/100). It is exposed: it has been seen and reported before. This script
sends each case, unchanged, with the ORIGINAL prompt (controls.CONTROL_PROMPT), the
ORIGINAL schema (controls.control_schema) and the ORIGINAL validator
(controls._validate_control) to another model through feedctrl.llm_providers. Nothing is
tuned; there is no retry for a wrong answer; every failure is kept. The frozen 79/100 is
never changed or replaced.

    python scripts/parser_rerun.py --provider openai --model gpt-5-mini --out results/parser-rerun-20261117
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from feedctrl.controls import CONTROL_PROMPT, ParserOperationalError, _validate_control, control_schema  # noqa: E402
from feedctrl.llm_providers import Ledger, ProviderError, build_provider  # noqa: E402
from feedctrl.parser_benchmark import _wilson  # noqa: E402

FROZEN_SHA256 = "836b6e0e1fc4ccfc2174c99426db052115caddc6c63a5da764381d7c8e01eed6"
LABEL = ("Re-use of the previously used 100-case parser test bank, unchanged, with no tuning. "
         "Not new unseen evidence. The frozen Llama 3.1 8B result (79/100) is unchanged.")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bank", default="data/parser_test.jsonl")
    ap.add_argument("--provider", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--effort", default="low")
    args = ap.parse_args(argv)
    raw = (ROOT / args.bank).read_bytes()
    if hashlib.sha256(raw).hexdigest() != FROZEN_SHA256:
        raise SystemExit("The parser bank does not match its frozen SHA-256; refusing to run.")
    cases = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    out = ROOT / args.out / args.model.replace(":", "_").replace("/", "_")
    out.mkdir(parents=True, exist_ok=False)
    provider = build_provider(args.provider, model=args.model, effort=args.effort)
    ledger = Ledger()
    rows = []
    started = time.monotonic()
    with (out / "predictions.jsonl").open("w", encoding="utf-8") as handle:
        for case in cases:
            schema = control_schema(case["categories"])
            system = CONTROL_PROMPT + "\nSCHEMA: " + json.dumps(schema, sort_keys=True)
            payload = {"allowed_categories": case["categories"], "request": case["text"]}
            row = {"case_id": case["case_id"], "group": case["group"], "expected": case["expected"],
                   "prediction": None, "correct": False, "operation_correct": False, "error": None}
            try:
                obj, call = provider.complete("parser", system, payload, schema)
                ledger.add(call)
                row["latency_s"], row["cost_usd"] = call.get("latency_s"), call.get("cost_usd")
                row["prediction"] = _validate_control(obj, case["categories"], f"{args.provider}:{args.model}")
                row["operation_correct"] = row["prediction"]["operation"] == case["expected"]["operation"]
                row["correct"] = all(row["prediction"][k] == case["expected"][k] for k in ("operation", "category", "strength"))
            except (ProviderError, ParserOperationalError) as exc:
                row["error"] = str(exc)[:300]
            rows.append(row)
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            handle.flush()
    correct = sum(r["correct"] for r in rows)
    clarify = [r for r in rows if r["expected"]["operation"] == "clarify"]
    summary = {"label": LABEL, "bank_sha256": FROZEN_SHA256, "provider": args.provider, "model": args.model,
               "effort": args.effort, "cases": len(rows), "correct": correct, "exact_accuracy": correct / len(rows),
               "exact_accuracy_wilson_95": _wilson(correct, len(rows)), "target": 0.85,
               "meets_85_target_point_estimate": correct / len(rows) >= 0.85,
               "operation_accuracy": sum(r["operation_correct"] for r in rows) / len(rows),
               "operational_errors": sum(r["error"] is not None for r in rows),
               "clarify_recall": f"{sum(r['correct'] for r in clarify)}/{len(clarify)}",
               "per_group": {g: f"{sum(r['correct'] for r in rows if r['group'] == g)}/{sum(r['group'] == g for r in rows)}"
                             for g in sorted({r["group"] for r in rows})},
               "cost_usd": ledger.total(), "elapsed_s": round(time.monotonic() - started, 1),
               "median_latency_s": sorted(r.get("latency_s") or 0 for r in rows)[len(rows) // 2]}
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
