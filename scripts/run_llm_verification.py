"""One-server sequence: frozen parser evaluation, main experiment, explanation sample.

Run under scripts/with_ollama.py after downloading the model. A nonzero stage is
recorded and the remaining independent stages still run; nothing is labelled passed
merely because later stages complete.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import time


def main() -> int:
    steps = [
        ("development_recheck", ["scripts/run_parser.py", "--data", "data/parser_dev.jsonl", "--backend", "ollama", "--output", "results/parser_ollama_dev_final", "--num-thread", "6"]),
        ("frozen_parser_test", ["scripts/run_parser.py", "--data", "data/parser_test.jsonl", "--backend", "ollama", "--output", "results/parser_ollama_test", "--num-thread", "6"]),
        ("main_experiment", ["scripts/evaluate_matrix.py", "--backend", "ollama", "--output", "results/llm", "--num-thread", "6"]),
        ("explanation_sample", ["scripts/generate_explanations.py", "--count", "10"]),
    ]
    outcomes = []
    for name, command in steps:
        print(json.dumps({"stage_start": name, "command": [sys.executable, *command]}), flush=True)
        start = time.monotonic()
        completed = subprocess.run([sys.executable, *command])
        outcomes.append({"stage": name, "exit_code": completed.returncode, "wall_seconds": time.monotonic() - start})
        Path("results/llm-stage-status.json").write_text(json.dumps(outcomes, indent=2), encoding="utf-8")
        print(json.dumps({"stage_end": name, **outcomes[-1]}), flush=True)
    return 2 if any(o["exit_code"] != 0 for o in outcomes) else 0


if __name__ == "__main__":
    raise SystemExit(main())
