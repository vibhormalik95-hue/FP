"""End-to-end test runner for the Studio (Windows, macOS, Linux).

    python -m studio.cli                      # mock provider, no key, no cost
    python -m studio.cli --provider anthropic --model claude-sonnet-5-5
    python -m studio.cli --provider claude-cli --model claude-opus-5-5   (author's computer)

It starts the real web server on a free local port, drives every workflow over
HTTP exactly as the page does (preview -> Apply -> check feed -> Undo -> check
feed restored), and writes results, failures, latency and cost to a dated folder.
Failures are recorded, never hidden. A running spend ledger stops the run once
the budget is reached.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import socket
import sys
import threading
import time
import traceback
from pathlib import Path

import httpx
import uvicorn

from studio.providers import Ledger, ProviderError, build_provider
from studio.server import create_app

EXAMPLES = Path(__file__).parent / "data" / "examples.json"


class BudgetReached(Exception):
    pass


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Runner:
    def __init__(self, client, out, ledger_path, budget, prior_total):
        self.c, self.out, self.ledger_path, self.budget = client, out, ledger_path, budget
        self.prior_total = prior_total
        self.results, self.failures = [], []

    # -- HTTP helpers
    def post(self, path, body=None):
        t = time.monotonic()
        r = self.c.post(path, json=body or {})
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {"error": r.text}
        if r.status_code == 402:
            raise BudgetReached(data.get("error", "Budget reached"))
        if r.status_code >= 400:
            raise RuntimeError(f"{path} -> HTTP {r.status_code}: {data.get('error', data)}")
        return data, round(time.monotonic() - t, 3)

    def state(self):
        return self.c.get("/api/state").json()

    def spent(self):
        return self.c.get("/api/ledger").json()["total_usd"]

    def check_budget(self):
        total = self.prior_total + self.spent()
        if total >= self.budget:
            raise BudgetReached(f"Budget reached: USD {total:.4f} >= {self.budget:.2f}")

    # -- one example
    def run(self, workflow, name, fn):
        self.check_budget()
        started, spent_before = time.monotonic(), self.spent()
        rec = {"workflow": workflow, "example": name, "ok": False}
        try:
            rec.update(fn())
            rec["ok"] = rec.get("ok_steps", True)
        except BudgetReached:
            raise
        except Exception as exc:  # recorded, not hidden
            rec["error"] = str(exc)
            rec["trace"] = traceback.format_exc(limit=3)
            self.failures.append({"workflow": workflow, "example": name, "error": str(exc)})
        rec["seconds"] = round(time.monotonic() - started, 2)
        rec["cost_usd"] = round(self.spent() - spent_before, 6)
        self.results.append(rec)
        mark = "PASS" if rec["ok"] else "FAIL"
        exp = rec.get("expectation")
        print(f"  [{mark}] {workflow:13s} {name:22s} {rec['seconds']:6.1f}s  ${rec['cost_usd']:.4f}"
              + (f"  expectation: {exp}" if exp else "") + (f"  error: {rec['error']}" if "error" in rec else ""), flush=True)
        return rec

    def apply_and_undo(self, preview, keep=False):
        before = self.state()["feed"]
        steps = {"preview_eligible_after": preview["changes"]["eligible_after"]}
        if not preview["applicable"]:
            return {**steps, "applied": False, "ok_steps": True}
        applied, t_apply = self.post("/api/apply", {"preview_id": preview["id"]})
        steps["apply_s"] = t_apply
        steps["applied_eligible"] = applied["feed"]["eligible"]
        steps["apply_matches_preview"] = applied["feed"]["top"] == preview["feed_after"]["top"]
        if keep:
            return {**steps, "applied": True, "ok_steps": steps["apply_matches_preview"]}
        undone, _ = self.post("/api/undo")
        steps["undo_restores"] = undone["feed"] == before
        return {**steps, "applied": True, "ok_steps": steps["apply_matches_preview"] and steps["undo_restores"]}

    # -- workflows
    def manual(self, ex):
        def go():
            p, t = self.post("/api/preview/manual", {k: ex[k] for k in ("kind", "value", "action", "strength")})
            res = {"preview_s": t, "summary": p["summary"], "changes": p["changes"]}
            res.update(self.apply_and_undo(p))
            met = p["changes"]["eligible_after"] == ex["expect_eligible_after"]
            res["expectation"] = f"eligible {p['changes']['eligible_after']} (expected {ex['expect_eligible_after']}) {'met' if met else 'NOT met'}"
            res["ok_steps"] = res["ok_steps"] and met
            return res
        return self.run("manual", ex["name"], go)

    def interpret(self, ex):
        def go():
            p, t = self.post("/api/preview/interpret", {"request": ex["request"]})
            labels = [f"{c['target']['kind']}:{c['target']['value']}" for c in p["controls"]]
            res = {"preview_s": t, "request": ex["request"], "domain": ex["domain"],
                   "status": (p.get("proposal") or {}).get("status"), "controls": [c["text"] for c in p["controls"]],
                   "evidence": p["evidence"], "checks": p["checks"], "notes": p["notes"], "changes": p["changes"],
                   "calls": p["calls"]}
            res.update(self.apply_and_undo(p))
            hit = sorted(set(labels) & set(ex["expect_any"]))
            act_ok = ex["expect_action"] is None or any(c["action"] == ex["expect_action"] for c in p["controls"])
            res["expectation"] = (f"labels {labels}; expected any of {ex['expect_any']} -> "
                                  f"{'met' if hit and act_ok else 'NOT met'}")
            res["expectation_met"] = bool(hit and act_ok)
            return res
        return self.run("interpret", ex["name"], go)

    def category(self, ex, keep=False):
        def go():
            d, t1 = self.post("/api/category/define", {"description": ex["description"]})
            res = {"define_s": t1, "description": ex["description"], "domain": ex["domain"],
                   "definition": {k: d[k] for k in ("status", "label", "definition", "rationale", "alternatives", "evidence", "duplicate")},
                   "calls": list(d["calls"])}
            if d["status"] != "propose" or not d["label"]:
                res["expectation"] = f"definition status {d['status']}; nothing to classify"
                res["ok_steps"] = False
                return res
            self.check_budget()
            p, t2 = self.post("/api/preview/category", {"label": d["label"], "definition": d["definition"],
                                                        "action": ex["action"], "strength": "standard"})
            selected = sorted(r["item_id"] for r in p["evidence"] if r["selected"])
            res.update({"classify_s": t2, "selected": selected, "notes": p["notes"], "checks": p["checks"],
                        "rows": p["evidence"], "changes": p["changes"]})
            res["calls"] += p["calls"]
            res.update(self.apply_and_undo(p, keep=keep))
            exp = set(ex["expect_members"])
            tp = len(exp & set(selected))
            prec = tp / len(selected) if selected else 0.0
            rec = tp / len(exp) if exp else 0.0
            res["agreement_with_author_expectation"] = {"precision": round(prec, 2), "recall": round(rec, 2),
                                                        "missed": sorted(exp - set(selected)),
                                                        "extra": sorted(set(selected) - exp)}
            res["expectation"] = f"selected {len(selected)}; author-expected overlap P={prec:.2f} R={rec:.2f}"
            return res
        return self.run("new-category", ex["name"], go)

    def items(self, ex):
        def go():
            body = {"items": [{"title": i["title"], "description": i["description"]} for i in ex["items"]]}
            p, t = self.post("/api/preview/items", body)
            res = {"preview_s": t, "evidence": p["evidence"], "checks": p["checks"], "changes": p["changes"],
                   "calls": p["calls"], "custom_categories": [c["label"] for c in self.state()["custom"]]}
            res.update(self.apply_and_undo(p))
            got = [e["category"] for e in p["evidence"]]
            want = [i["expect_category"] for i in ex["items"]]
            res["expectation"] = f"categories {got} (expected {want}) {'met' if got == want else 'NOT met'}"
            res["expectation_met"] = got == want
            return res
        return self.run("new-videos", ex["name"], go)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m studio.cli", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", default="mock", choices=["mock", "anthropic", "openai", "claude-cli"])
    ap.add_argument("--model", default=None)
    ap.add_argument("--effort", default=None, choices=["low", "medium", "high", "xhigh", "max"])
    ap.add_argument("--base-url", default=None)
    ap.add_argument("--out", default="studio-results", help="Parent folder for the dated results folder.")
    ap.add_argument("--budget-usd", type=float, default=50.0, help="Stop when the running total reaches this (default 50).")
    ap.add_argument("--ledger", default=None, help="JSON file with the running spend across runs (default: <out>/spend-ledger.json).")
    ap.add_argument("--only", default=None, help="Comma list of workflows: manual,interpret,category,items")
    ap.add_argument("--examples", default=str(EXAMPLES))
    args = ap.parse_args(argv)

    try:
        provider = build_provider(args.provider, model=args.model, effort=args.effort, base_url=args.base_url)
    except ProviderError as exc:
        print(f"Cannot start provider: {exc}", file=sys.stderr)
        return 2
    examples = json.loads(Path(args.examples).read_text(encoding="utf-8"))
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = Path(args.out) / f"{stamp}-{provider.name}-{(provider.model or '').replace('/', '_')}"
    out.mkdir(parents=True, exist_ok=True)
    ledger_path = Path(args.ledger) if args.ledger else Path(args.out) / "spend-ledger.json"
    prior = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.exists() else {"runs": [], "total_usd": 0.0}

    port = free_port()
    app = create_app(port=port, provider=provider, ledger=Ledger(budget_usd=max(0.0, args.budget_usd - prior["total_usd"])))
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", access_log=False))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)

    print(f"Studio started on http://127.0.0.1:{port}/  provider={provider.label} model={provider.model}")
    print(f"Results folder: {out}")
    print(f"Spend before this run: USD {prior['total_usd']:.4f}; budget USD {args.budget_usd:.2f}")
    only = set((args.only or "manual,interpret,category,items").split(","))
    client = httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=900)
    r = Runner(client, out, ledger_path, args.budget_usd, prior["total_usd"])
    started = time.monotonic()
    stopped = None
    try:
        page = client.get("/")
        r.results.append({"workflow": "startup", "example": "page loads", "ok": page.status_code == 200 and "Feed Control Studio" in page.text})
        bad = client.get("/api/state", headers={"host": "attacker.example"})
        r.results.append({"workflow": "startup", "example": "foreign Host refused", "ok": bad.status_code == 403})
        if "manual" in only:
            for ex in examples["manual"]:
                r.manual(ex)
        if "interpret" in only:
            for ex in examples["interpret"]:
                r.interpret(ex)
        cats = {ex["name"]: ex for ex in examples["category"]}
        if "category" in only:
            for ex in examples["category"]:
                r.category(ex)
        if "items" in only:
            for ex in examples["items"]:
                client.post("/api/reset")
                if "category" in only and ex.get("after_category") in cats:
                    r.category(cats[ex["after_category"]], keep=True)   # make a new category first
                r.items(ex)
    except BudgetReached as exc:
        stopped = str(exc)
        print(f"STOPPED: {exc}")
    finally:
        ledger = client.get("/api/ledger").json()
        server.should_exit = True
        thread.join(timeout=10)

    run_total = ledger["total_usd"]
    summary = {
        "started": stamp, "provider": provider.describe(), "port": port, "python": sys.version.split()[0],
        "platform": sys.platform, "duration_s": round(time.monotonic() - started, 1),
        "examples": len([x for x in r.results if x["workflow"] != "startup"]),
        "passed": sum(1 for x in r.results if x["ok"]), "failed": sum(1 for x in r.results if not x["ok"]),
        "expectations_met": sum(1 for x in r.results if x.get("expectation_met")),
        "model_calls": len(ledger["calls"]), "failed_calls": sum(1 for c in ledger["calls"] if c.get("error")),
        "run_cost_usd": round(run_total, 6), "total_spend_usd": round(prior["total_usd"] + run_total, 6),
        "budget_usd": args.budget_usd, "stopped": stopped,
    }
    (out / "results.json").write_text(json.dumps({"summary": summary, "results": r.results, "failures": r.failures},
                                                 indent=2, ensure_ascii=False), encoding="utf-8")
    with open(out / "calls.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["n", "task", "provider", "model", "served_by", "latency_s", "input_tokens", "output_tokens",
                    "cost_usd", "running_total_usd", "cost_source", "error"])
        for i, c in enumerate(ledger["calls"], 1):
            w.writerow([i, c.get("task"), c.get("provider"), c.get("model"), c.get("served_by", ""), c.get("latency_s"),
                        c.get("input_tokens"), c.get("output_tokens"), c.get("cost_usd"), c.get("running_total_usd"),
                        c.get("cost_source", ""), c.get("error", "")])
    (out / "summary.md").write_text(render_summary(summary, r), encoding="utf-8")
    prior["runs"].append({"folder": out.name, "cost_usd": run_total, "calls": len(ledger["calls"])})
    prior["total_usd"] = round(prior["total_usd"] + run_total, 6)
    ledger_path.write_text(json.dumps(prior, indent=2), encoding="utf-8")
    print(f"\n{summary['passed']} passed, {summary['failed']} failed; {summary['model_calls']} model calls "
          f"({summary['failed_calls']} failed); run cost USD {run_total:.4f}; total USD {prior['total_usd']:.4f}")
    print(f"Wrote {out / 'summary.md'}")
    return 0 if summary["failed"] == 0 and not stopped else 1


def render_summary(s, r):
    lines = [f"# Studio CLI run {s['started']}", "",
             f"- Provider: {s['provider']['label']} · model `{s['provider']['model']}`"
             + (f" · effort {s['provider'].get('effort')}" if s['provider'].get('effort') else ""),
             f"- Platform: {s['platform']}, Python {s['python']}; duration {s['duration_s']} s",
             f"- Results: {s['passed']} passed, {s['failed']} failed (startup checks included)",
             f"- Model calls: {s['model_calls']} ({s['failed_calls']} failed); run cost USD {s['run_cost_usd']:.4f}; "
             f"running total USD {s['total_spend_usd']:.4f} of budget {s['budget_usd']:.2f}",
             f"- Stopped early: {s['stopped'] or 'no'}", "",
             "| Workflow | Example | Pass | Time (s) | Cost (USD) | Expectation / error |", "|---|---|---|---|---|---|"]
    for x in r.results:
        lines.append(f"| {x['workflow']} | {x['example']} | {'yes' if x['ok'] else '**no**'} | {x.get('seconds', '')} | "
                     f"{x.get('cost_usd', '')} | {(x.get('expectation') or '') + (' ERROR: ' + x['error'] if x.get('error') else '')} |")
    lines += ["", "Pass means every step worked: preview, Apply (feed equals the preview), Undo (feed restored), and for manual",
              "controls the exact expected count. For model workflows, the expectation column compares the model's answer with",
              "the author's expectation; it is reported, not enforced. 'Mock' runs test plumbing only: the mock is not an AI."]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
