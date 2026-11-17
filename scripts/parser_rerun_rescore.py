"""Re-score saved parser re-run predictions with the grounding rule of controls.parse_control.

The first version of scripts/parser_rerun.py applied the original validator but not the
grounding rule that parse_control adds (a boost or mute must name exactly the one category
that the request names). This applies that deterministic rule to the saved predictions; no
model is called. It writes summary-grounded.json next to each summary.json.

    python scripts/parser_rerun_rescore.py results/parser-rerun-20261117 results/parser-rerun-20261117-run2
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from parser_rerun import grounded  # noqa: E402
from feedctrl.parser_benchmark import _wilson  # noqa: E402


def main(folders):
    texts = {json.loads(l)["case_id"]: json.loads(l)["text"] for l in (ROOT / "data/parser_test.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
    for folder in folders:
        for model_dir in sorted(p for p in (ROOT / folder).iterdir() if (p / "predictions.jsonl").is_file()):
            rows = [json.loads(l) for l in (model_dir / "predictions.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
            for r in rows:
                if r.get("prediction") and not grounded(r["prediction"], texts[r["case_id"]]):
                    r["correct"] = False
                    r["error"] = "LLM action is not grounded in exactly one explicit allowed category"
            s = json.loads((model_dir / "summary.json").read_text(encoding="utf-8"))
            correct = sum(r["correct"] for r in rows)
            clar = [r for r in rows if r["expected"]["operation"] == "clarify"]
            s.update(correct=correct, exact_accuracy=correct / len(rows), exact_accuracy_wilson_95=_wilson(correct, len(rows)),
                     operational_errors=sum(r["error"] is not None for r in rows),
                     clarify_recall=f"{sum(r['correct'] for r in clar)}/{len(clar)}",
                     grounding_note="Re-scored with the grounding rule of controls.parse_control (scripts/parser_rerun_rescore.py).")
            if "posthoc_format_lenient_correct" in s:
                s["posthoc_format_lenient_correct"] = sum(bool(r.get("posthoc_lenient_correct")) and (not r.get("prediction") or grounded(r["prediction"], texts[r["case_id"]])) for r in rows)
            (model_dir / "summary-grounded.json").write_text(json.dumps(s, indent=2), encoding="utf-8")
            print(model_dir.name, folder, correct, s["operational_errors"], s.get("posthoc_format_lenient_correct"))


if __name__ == "__main__":
    main(sys.argv[1:])
