"""Render reproducible publication figures from an executed combined summary."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np

ROOT = Path(__file__).resolve().parents[1]

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("summary", help="One backend's combined-summary.json; no backend pooling")
    parser.add_argument("--output", default="results/figures")
    args = parser.parse_args()
    source = ROOT / args.summary
    result = json.loads(source.read_text(encoding="utf-8"))
    backend = result.get("backend")
    if backend not in ("rule", "ollama"):
        inferred = {json.loads((ROOT / Path(p).parent / "summary.json").read_text(encoding="utf-8"))["backend"] for p in result["input_files"]}
        if len(inferred) != 1:
            raise ValueError("Do not combine backends in a figure")
        backend = inferred.pop()
    output = ROOT / args.output
    output.mkdir(parents=True, exist_ok=True)
    label = "Rule diagnostic" if backend == "rule" else "Executed Llama 3.1 8B parser"
    color = "#315D82" if backend == "rule" else "#26745E"
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10,
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.titleweight": "bold", "pdf.fonttype": 42})
    files = []

    fig, axes = plt.subplots(1, 3, figsize=(11.7, 4.1), constrained_layout=True)
    panels = [("boost", "TCP@10: more target content", "Positive favors treatment"),
              ("mute", "TCER@10: less target exposure", "Negative favors treatment"),
              ("hr1", "Next-item HR@1", "Exploratory quality check")]
    for ax, (operation, title, direction) in zip(axes, panels):
        rows = result["hr1_noninferiority"] if operation == "hr1" else [r for r in result["primary_contrasts"] if r["operation"] == operation]
        extremes = [0.0]
        for index, condition in enumerate(("C", "D", "E")):
            row = next(r for r in rows if r["condition"] == condition)
            mean = row["mean_difference"] * 100
            lower, upper = [v * 100 for v in row["ci95"]]
            extremes.extend([lower, upper])
            ax.hlines(index, lower, upper, color=color, lw=2.2)
            ax.plot(mean, index, "o", color=color, ms=6)
            ax.annotate(f"{mean:+.2f} [{lower:+.2f}, {upper:+.2f}]", (mean, index),
                        xytext=(0, 12), textcoords="offset points", ha="center", fontsize=8)
        span = max(1.0, max(extremes) - min(extremes))
        ax.set_xlim(min(extremes) - span * .35, max(extremes) + span * .35)
        ax.axvline(0, color="#888888", lw=1, linestyle="--")
        ax.set_yticks(range(3), ["C: text", "D: profile", "E: combined"])
        ax.set_ylim(2.55, -.75)
        ax.set_title(title, fontsize=10, pad=12)
        ax.set_xlabel("Treatment − A (percentage points)\n" + direction, fontsize=9)
        ax.grid(axis="x", alpha=.15)
    fig.suptitle(f"{label}: paired effects with 95% user-bootstrap intervals\n"
                 f"{result['user_count']} users · {result['seed_count']} frozen seeds · synthetic controls", fontsize=12)
    for suffix in ("png", "pdf"):
        path = output / f"paired-effects-{backend}.{suffix}"
        fig.savefig(path, dpi=220, bbox_inches="tight")
        files.append(str(path))
    plt.close(fig)

    fig, axes = plt.subplots(2, 3, figsize=(11.7, 6.2), constrained_layout=True)
    conditions = ("A", "B", "C", "D", "E")
    for row_index, operation in enumerate(("boost", "mute")):
        for col_index, metric in enumerate(("target_proportion", "ndcg_at_k", "hr1")):
            ax = axes[row_index, col_index]
            values = [result["descriptive"][c][operation][metric] for c in conditions]
            ax.bar(conditions, values, color=["#7E8790", "#7E8790", color, color, color], width=.65)
            for index, value in enumerate(values):
                ax.annotate((f"{value:.4f}" if metric == "ndcg_at_k" else f"{value:.2%}"), (index, value), xytext=(0, 4), textcoords="offset points", ha="center", fontsize=8)
            ax.set_ylim(0, max(.01, max(values) * 1.3) if metric == "hr1" else max(.05, max(values) * 1.3) if metric == "ndcg_at_k" else 1.13)
            if metric != "ndcg_at_k":
                ax.yaxis.set_major_formatter(PercentFormatter(1))
            title = ("TCP@10" if operation == "boost" else "TCER@10") if metric == "target_proportion" else "Next-item NDCG@10 (zoomed scale)" if metric == "ndcg_at_k" else "Next-item HR@1 (zoomed scale)"
            ax.set_title(title, fontsize=10)
            ax.set_xlabel("Condition")
            if col_index == 0:
                ax.set_ylabel("Boost request" if operation == "boost" else "Mute request")
            ax.grid(axis="y", alpha=.15)
            ax.set_axisbelow(True)
    fig.suptitle(f"{label}: equal-user means across frozen seeds\n"
                 "Quality requires both NDCG@10 and HR@1; feed fill rates are reported separately", fontsize=12)
    for suffix in ("png", "pdf"):
        path = output / f"condition-means-{backend}.{suffix}"
        fig.savefig(path, dpi=220, bbox_inches="tight")
        files.append(str(path))
    plt.close(fig)
    manifest = {"source": str(source), "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "backend": backend, "figures": files, "ci": "paired user percentile bootstrap, two-sided95%; not simultaneous",
                "hr_axis": "Means chart explicitly zooms HR@1 and NDCG@10; units shown on each axis"}
    (output / f"figure-provenance-{backend}.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
