"""Reproduce the new-category and new-item steps of a take through the normal workflow functions and save
every model request and response, so membership can be traced call by call.

    python tools/diagnose_new_category.py --out runs/diagnose-X --model gpt-5 --effort minimal \
        --definition-file def.json [--hide "Social incident,Legal incident"] [--scope 10] [--description "..."]

Steps (user 14 by default): optional hide controls (applied), then either the given label and definition or
a definition proposed by the model from --description, classification of the scope, Apply, then the given
new items with Apply. Writes calls.jsonl (task, request payload, response), report.json (members, checks,
selection reasons, top ten before and after each Apply).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))


class Recorder:
    """Wraps a provider and keeps each request and response."""

    def __init__(self, inner, path):
        self.inner, self.path = inner, path

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def complete(self, task, system, payload, schema):
        data, call = self.inner.complete(task, system, payload, schema)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"task": task, "payload": payload, "response": data,
                                "call": {k: call.get(k) for k in ("model", "latency_s", "input_tokens",
                                                                   "output_tokens", "cost_usd")}},
                               ensure_ascii=False) + "\n")
        return data, call


def top_ten(lab, user):
    return [c["item_id"] for c in lab.feed(user)["items"]]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--user", type=int, default=14)
    ap.add_argument("--provider", default="openai")
    ap.add_argument("--model", default="gpt-5")
    ap.add_argument("--effort", default="low")
    ap.add_argument("--scope", type=int, default=10)
    ap.add_argument("--hide", default="")
    ap.add_argument("--definition-file")
    ap.add_argument("--description")
    ap.add_argument("--action", default="boost")
    ap.add_argument("--items-file", help="JSON list of {title, description}")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    import run_app
    from feedctrl import lab_workflows as wf
    from feedctrl.llm_providers import Ledger, build_provider
    _, lab = run_app.build(argparse.Namespace(provider="mock", model=None, base_url=None, budget_usd=None))
    provider = Recorder(build_provider(args.provider, model=args.model, effort=args.effort), out / "calls.jsonl")
    if args.provider == "openai":
        provider.inner.effort = args.effort
    ledger, user, report = Ledger(), args.user, {"args": vars(args)}
    if args.hide:
        p = wf.manual_preview(lab, user, "category", None, "hide", values=args.hide.split(","))
        lab.apply(user, p["preview_id"])
    report["top10_start"] = top_ten(lab, user)
    if args.definition_file:
        d = json.loads(Path(args.definition_file).read_text(encoding="utf-8"))
        label, definition = d["label"], d["definition"]
    else:
        d = wf.define_category(lab, provider, ledger, user, args.description, scope_size=args.scope)
        report["define"] = {k: d.get(k) for k in ("status", "label", "definition", "evidence")}
        label, definition = d["label"], d["definition"]
    p = wf.classify_category(lab, provider, ledger, user, label, definition, args.action, scope_size=args.scope)
    report["classify"] = {"rows": [{k: r.get(k) for k in ("item_id", "title", "verdict", "field", "quote", "quote_verified",
                                                          "assessment", "selected")} for r in p["evidence"]],
                          "selected": [r["item_id"] for r in p["evidence"] if r["selected"]],
                          "changes": p["changes"], "applicable": p["applicable"]}
    if p["applicable"]:
        lab.apply(user, p["preview_id"])
    report["top10_after_category"] = top_ten(lab, user)
    if args.items_file:
        items = json.loads(Path(args.items_file).read_text(encoding="utf-8"))
        q = wf.add_items_preview(lab, provider, ledger, user, items)
        report["new_items"] = {"evidence": q["evidence"], "checks": q["checks"], "changes": q["changes"]}
        lab.apply(user, q["preview_id"])
        report["members_after_items"] = sorted(
            int(k) for k, e in lab.user(user).custom[label]["members"].items() if e.get("selected"))
        report["top10_after_items"] = top_ten(lab, user)
    report["cost_usd"] = ledger.total()
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps({"selected": report["classify"]["selected"], "members_after_items": report.get("members_after_items"),
                      "cost_usd": round(ledger.total(), 4)}))


if __name__ == "__main__":
    main()
