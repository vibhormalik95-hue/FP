"""One-server sequence: frozen parser evaluation, main experiment, explanation sample.

Run under scripts/with_ollama.py after downloading the model. A nonzero stage is
recorded and the remaining independent stages still run; nothing is labelled passed
merely because later stages complete.

This is a PROSPECTIVE re-run. Every output goes to one fresh folder (default
runs/llm-verification-<UTC time>), which scripts/output_safety.py accepts. The old
receipts under results/ (results/llm, results/parser_ollama_*, the old stage-status
file) are never written: results/llm is a protected frozen destination.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.output_safety import require_new_output  # noqa: E402


def stages(out: Path):
    """The commands of the sequence; every output is a new path inside ``out``."""
    return [
        ("development_recheck", ["scripts/run_parser.py", "--data", "data/parser_dev.jsonl", "--backend", "ollama",
                                 "--output", str(out / "parser_ollama_dev"), "--num-thread", "6"]),
        ("frozen_parser_test", ["scripts/run_parser.py", "--data", "data/parser_test.jsonl", "--backend", "ollama",
                                "--output", str(out / "parser_ollama_test"), "--num-thread", "6"]),
        ("main_experiment", ["scripts/evaluate_matrix.py", "--backend", "ollama", "--output", str(out / "llm"),
                             "--num-thread", "6"]),
        ("explanation_sample", ["scripts/generate_explanations.py", "--count", "10",
                                "--output", str(out / "explanations" / "explanations.json")]),
    ]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--output-root", help="a NEW folder for every output of this run; "
                                              "default: runs/llm-verification-<UTC time>")
    args = parser.parse_args(argv)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = require_new_output(args.output_root or f"runs/llm-verification-{stamp}", ROOT, directory=True)
    out.mkdir(parents=True, exist_ok=True)
    status_path = out / "stage-status.json"
    outcomes = []
    for name, command in stages(out):
        print(json.dumps({"stage_start": name, "command": [sys.executable, *command]}), flush=True)
        start = time.monotonic()
        completed = subprocess.run([sys.executable, *command], cwd=ROOT)
        outcomes.append({"stage": name, "exit_code": completed.returncode, "wall_seconds": time.monotonic() - start})
        status_path.write_text(json.dumps(outcomes, indent=2), encoding="utf-8")
        print(json.dumps({"stage_end": name, **outcomes[-1]}), flush=True)
    return 2 if any(o["exit_code"] != 0 for o in outcomes) else 0


if __name__ == "__main__":
    raise SystemExit(main())
