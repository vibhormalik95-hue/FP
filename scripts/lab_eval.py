"""Measure the language controls on the frozen, human-reviewed KuaiRec evaluation set.

    python scripts/lab_eval.py run   --set <cases.frozen.json> --name gpt-5-mini --provider openai --model gpt-5-mini --out results/lab-eval/<run>
    python scripts/lab_eval.py score --run results/lab-eval/<run> --set <cases.frozen.json> --publish docs/evidence/lab-eval/<run>

``run`` sends every case to one model through the SAME functions the application uses
(``lab_workflows.interpret_request`` and ``lab_workflows.classify_members``). Nothing is
retried after a wrong answer; every failure is kept. New-category cases use the reference
label and definition, so every model classifies the same pool under the same definition.
``score`` computes the metrics of ``feedctrl.lab_metrics`` and the downstream effect of each
control on the trained SASRec ranking (TCP@10, TCER@10, NDCG@10, HR@1, non-inferiority at the
proposal's 10% margin), and writes summary.json (with the tables of the Results page) and
per-case CSV files without item text.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from feedctrl import lab_metrics as lm  # noqa: E402
from feedctrl import lab_workflows as wf  # noqa: E402
from feedctrl.kuairec_catalog import build_catalog, read_caption_table, read_english_layer, term_members  # noqa: E402
from feedctrl.lab import STRENGTHS, KuaiRecLab, UserLab, LabError  # noqa: E402
from feedctrl.llm_providers import Ledger, build_provider  # noqa: E402

CAPTIONS = ROOT / "data/raw/kuairec_caption_category.csv"
PROCESSED = ROOT / "data/processed.json"
ENGLISH = ROOT / "data/kuairec_text_en-v1.json"


def load_catalog(text="original"):
    """The item catalogue. "original" is the KuaiRec source text that the 17 Nov run used (scoring that run
    only; never shown or sent to a model by the app). "english" is the English text layer the app uses."""
    rows, _ = read_english_layer(ENGLISH) if text == "english" else read_caption_table(CAPTIONS)
    processed = json.loads(PROCESSED.read_text(encoding="utf-8"))
    return processed, build_catalog(processed, rows), None


def load_set(path):
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    frozen = data.get("frozen") or {}
    if not frozen.get("review_csv_sha256") or not frozen.get("reviewed_by"):
        raise SystemExit("The evaluation set is not frozen and reviewed; refusing to measure.")
    return data, hashlib.sha256(path.read_bytes()).hexdigest()


def git_commit():
    """Short commit of the code that produces predictions, with '+dirty' when it has local changes."""
    import subprocess
    try:
        head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "feedctrl", "scripts/lab_eval.py"], cwd=ROOT,
                               capture_output=True, text=True).stdout.strip()
        return (head + ("+dirty" if dirty else "")) if head else "unknown"
    except OSError:
        return "unknown"


# ------------------------------------------------------------------ run
def cmd_run(args):
    data, set_sha = load_set(args.set)
    _, catalog, _ = load_catalog(args.text)
    lab = KuaiRecLab(catalog, scorer=lambda u: {}, users={})
    vocabulary = lab.vocabulary(UserLab(), for_model=True)
    pool = [catalog[int(i)] for i in data["pool"]]
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    pred_path = out / f"{args.name}.jsonl"
    done = {}
    if pred_path.is_file():
        for line in pred_path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            done[row["case_id"]] = row
    provider = build_provider(args.provider, model=args.model, effort=args.effort, timeout=args.timeout)
    ledger = Ledger(budget_usd=args.budget_usd)
    meta = {"name": args.name, "provider": args.provider, "model": args.model, "effort": args.effort,
            "code_commit": git_commit(),
            "set_sha256": set_sha, "started_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    (out / f"{args.name}.meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    with pred_path.open("a", encoding="utf-8") as handle:
        for case in data["cases"]:
            if case["id"] in done:
                continue
            calls, started = [], time.monotonic()
            row = {"case_id": case["id"], "group": case["group"], "model": args.name}
            try:
                if case["group"] in ("NL", "AB"):
                    raw, controls, checks, evidence, calls = wf.interpret_request(provider, ledger, case["request"], vocabulary)
                    row.update(status=raw.get("status"), reason=raw.get("reason"), alternatives=raw.get("alternatives"),
                               controls=[{"action": c["action"], "strength": c["strength"],
                                          "term_id": f"{c['target']['kind']}:{c['target']['value']}"} for c in controls],
                               failed_checks=[c["check"] for c in checks if not c["ok"]])
                else:
                    rows, memberships, assessments = wf.classify_members(provider, ledger, case["label"], case["definition"], pool, calls)
                    row.update(selected=[r["item_id"] for r in rows if r["selected"]],
                               raw_match=[r["item_id"] for r in rows if r["verdict"] == "match"],
                               unknown=sum(r["verdict"] == "unknown" for r in rows),
                               missing=sum(r["missing"] for r in rows),
                               quote_failures=sum(not r["quote_verified"] for r in rows),
                               from_translation=sum(r["quote_from_translation"] for r in rows if r["selected"]),
                               verdicts={str(r["item_id"]): [r["verdict"], r["quote_verified"],
                                                             (r["assessment"] or {}).get("supports")] for r in rows})
            except LabError as exc:
                row["error"] = str(exc)[:500]
                calls = calls or [c for c in ledger.calls[-5:] if c.get("error")]
            row["seconds"] = round(time.monotonic() - started, 2)
            row["calls"] = [{k: c.get(k) for k in ("task", "latency_s", "input_tokens", "output_tokens", "cost_usd",
                                                    "cost_source", "error", "served_by")} for c in calls]
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            handle.flush()
            print(f"{args.name} {case['id']} {row.get('status') or ('%d selected' % len(row.get('selected', [])) if 'selected' in row else '')}"
                  f"{' ERROR ' + row['error'][:120] if row.get('error') else ''} {row['seconds']}s USD {ledger.total():.4f}", flush=True)
    return 0


# ------------------------------------------------------------------ downstream
def ndcg_hr(order, test_items, k=10):
    test = set(test_items)
    dcg = sum(1 / math.log2(i + 2) for i, item in enumerate(order[:k]) if item in test)
    ideal = sum(1 / math.log2(i + 2) for i in range(min(len(test), k)))
    return (dcg / ideal if ideal else 0.0), (1.0 if order and order[0] in test else 0.0)


def downstream(data, preds_by_model, catalog, users, n_users, seed):
    from feedctrl.controls import normalize_scores
    from feedctrl.model import load_model
    model = load_model(ROOT / "results/models/seed_42")
    rng = random.Random(seed)
    sample = rng.sample(sorted(u["user_id"] for u in users if u.get("test")), n_users)
    by_id = {u["user_id"]: u for u in users}
    ids = sorted(catalog)
    scores = {}
    for uid in sample:
        u = by_id[uid]
        raw = model.score(list(u["train"]) + list(u["request_history"]), ids)
        scores[uid] = dict(zip(ids, normalize_scores([float(x) for x in raw])))

    def items_of(term_ids):
        out = set()
        for t in term_ids:
            try:
                out |= term_members(catalog, t)
            except ValueError:
                pass
        return out

    from feedctrl.lab import apply_controls, make_control

    def label_controls(controls, group="case"):
        """The exact controls, applied by the application's own policy (strength, mixed actions, 'only' groups)."""
        out = []
        for c in controls:
            kind, _, value = c["term_id"].partition(":")
            out.append(make_control("eval", c["action"], {"kind": kind, "value": value}, c.get("strength", "standard"), group=group))
        return out

    def set_controls(members, action="boost"):
        custom = {"eval-set": {"label": "eval-set", "definition": "", "members": {str(i): {"selected": True} for i in members}}}
        return [make_control("eval", action, {"kind": "custom", "value": "eval-set"})], custom

    def measure(controls, custom, target):
        tp, nd, hr = [], [], []
        for uid in sample:
            order = [r[0] for r in apply_controls(scores[uid], catalog, controls, custom)]
            top = order[:10]
            tp.append(sum(i in target for i in top) / 10)
            n, h = ndcg_hr(order, by_id[uid]["test"])
            nd.append(n)
            hr.append(h)
        return {"target_share": sum(tp) / len(tp), "ndcg10": sum(nd) / len(nd), "hr1": sum(hr) / len(hr)}

    results = {}
    for case in data["cases"]:
        if case["group"] == "AB":
            continue
        if case["group"] == "NL":
            target, action = items_of(case["required"]), case["action"]
            ref_controls, ref_custom = label_controls([{"term_id": t, "action": action} for t in case["required"]]), {}
        else:
            target, action = {int(i) for i in case["members"]} - {int(i) for i in case.get("excluded", [])}, "boost"
            ref_controls, ref_custom = set_controls(target)
        base = measure([], {}, target)
        ref = measure(ref_controls, ref_custom, target)
        per_model = {}
        for name, preds in preds_by_model.items():
            p = preds.get(case["id"], {})
            if case["group"] == "NL":
                controls, custom = label_controls(p.get("controls") or []), {}
            else:
                selected = {int(i) for i in p.get("selected", [])}
                controls, custom = set_controls(selected) if selected else ([], {})
            per_model[name] = measure(controls, custom, target) if controls else dict(base)
        results[case["id"]] = {"action": action, "target_items": len(target), "none": base, "reference": ref,
                               "models": per_model}
    return sample, results


# ------------------------------------------------------------------ score
def cmd_score(args):
    data, set_sha = load_set(args.set)
    processed, catalog, _ = load_catalog(args.text)
    run = ROOT / args.run
    cases = {c["id"]: c for c in data["cases"]}
    preds_by_model, rows_by_model, calls_by_model, meta = {}, {}, {}, {}
    prov_path = run / "PROVENANCE.json"
    provenance = json.loads(prov_path.read_text(encoding="utf-8")) if prov_path.is_file() else {}
    for path in sorted(run.glob("*.jsonl")):
        name = path.stem
        preds = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            preds[r["case_id"]] = r
        missing = [cid for cid in cases if cid not in preds]
        meta[name] = {**json.loads((run / f"{name}.meta.json").read_text(encoding="utf-8")), "missing_cases": missing}
        if not meta[name].get("code_commit") and provenance.get(name):
            meta[name]["code_commit"] = provenance[name]["code_commit"]
            meta[name]["code_commit_source"] = provenance[name]["source"]
        rows = []
        for cid, case in cases.items():
            p = preds.get(cid, {"error": "not run"})
            if case["group"] == "NL":
                rows.append(lm.score_nl(case, p))
            elif case["group"] == "AB":
                rows.append(lm.score_ab(case, p))
            else:
                rows.append(lm.score_nc(case, p))
        preds_by_model[name], rows_by_model[name] = preds, rows
        calls_by_model[name] = [c for p in preds.values() for c in p.get("calls", [])]
    summaries = {n: lm.summarize(rows_by_model[n], calls_by_model[n]) for n in rows_by_model}
    tests = lm.paired_tests(rows_by_model)
    sample, effects = downstream(data, preds_by_model, catalog, processed["users"], args.users, args.seed)

    def agg(name, group_filter):
        vals = [e for cid, e in effects.items() if group_filter(cid, e)]
        if not vals:
            return None
        pick = (lambda e: e["models"][name]) if name not in ("none", "reference") else (lambda e: e[name])
        return {k: sum(pick(e)[k] for e in vals) / len(vals) for k in ("target_share", "ndcg10", "hr1")}

    boostish = lambda cid, e: e["action"] in ("boost", "only")
    removeish = lambda cid, e: e["action"] in ("hide", "reduce")
    eff_rows = []
    for name in ["none", "reference", *sorted(rows_by_model)]:
        b, r, allc = agg(name, boostish), agg(name, removeish), agg(name, lambda c, e: True)
        eff_rows.append([name, b and b["target_share"], r and r["target_share"], allc["ndcg10"], allc["hr1"]])
    base_all = agg("none", lambda c, e: True)
    noninf = []
    for name in sorted(rows_by_model):
        diffs = [e["models"][name]["hr1"] - e["none"]["hr1"] for e in effects.values()]
        nd = [e["models"][name]["ndcg10"] - e["none"]["ndcg10"] for e in effects.values()]
        ci = lm.bootstrap_ci(diffs)
        margin_rel = 0.10 * base_all["hr1"]
        noninf.append([name, sum(diffs) / len(diffs), ci and ci[0], -margin_rel, bool(ci and ci[0] > -margin_rel),
                       bool(ci and ci[0] > -0.10), sum(nd) / len(nd)])
    # TCP fidelity tests: model target share vs reference, per case (boost/only cases), Wilcoxon + BH
    fidelity = []
    for name in sorted(rows_by_model):
        d = [e["models"][name]["target_share"] - e["reference"]["target_share"] for e in effects.values() if e["action"] in ("boost", "only")]
        p = lm.wilcoxon(d, zero_method="pratt").pvalue if any(abs(x) > 1e-12 for x in d) else 1.0
        fidelity.append([name, len(d), sum(d) / len(d) if d else None, p])
    adj = lm.bh([f[3] for f in fidelity])
    for f, a in zip(fidelity, adj):
        f.append(a)

    names = sorted(rows_by_model)
    scoring_commit = git_commit()
    provenance_line = ("Predictions produced at commit: " + "; ".join(f"{n} {meta[n].get('code_commit', 'unknown')}" for n in names)
                       + f". Scored at commit {scoring_commit}.")
    pct = lambda v: None if v is None else f"{100 * v:.0f}%"
    tables = [
        {"title": "Nonliteral request to existing KuaiRec labels (NL, %d cases)" % summaries[names[0]]["nl_cases"],
         "columns": ["Model", "Exact intended profile", "95% CI (Wilson)", "Action correct %", "Label precision", "Label recall", "Label F1", "F1 95% CI", "Missed required labels", "Unwanted clarifications"],
         "rows": [[n, f"{s['nl_exact']}/{s['nl_cases']}", str(s["nl_exact_wilson"]), pct(s["nl_action_rate"]), s["nl_label_precision"], s["nl_label_recall"], s["nl_label_f1"], str(s["nl_label_f1_ci"]), s["retrieval_misses_labels"], s["nl_unwanted_clarification"]] for n, s in summaries.items()],
         "note": "Exact: the reference action and every required label, no label outside required + acceptable."},
        {"title": "Should not propose: ambiguous, unsupported, no match (AB, %d cases)" % summaries[names[0]]["ab_cases"],
         "columns": ["Model", "Correct abstention", "95% CI (Wilson)", "False acceptance", "Status matches reference"],
         "rows": [[n, f"{s['ab_abstained']}/{s['ab_cases']}", str(s["ab_abstention_wilson"]), s["false_acceptance"], s["ab_status_match"]] for n, s in summaries.items()]},
        {"title": "New category membership on a shared pool of %d KuaiRec items (NC, %d cases)" % (len(data["pool"]), summaries[names[0]]["nc_cases"]),
         "columns": ["Model", "Member precision", "Member recall", "Member F1", "F1 95% CI", "Raw-verdict F1", "Missed members"],
         "rows": [[n, s["nc_member_precision"], s["nc_member_recall"], s["nc_member_f1"], str(s["nc_member_f1_ci"]), s["nc_raw_f1"], s["retrieval_misses_members"]] for n, s in summaries.items()],
         "note": "Selected = verdict match, quotation found in the item, and the independent check supports it. Every model used the reviewed reference definition. Measured with the freeze-time quotation rule; the shipped app is stricter since 1de3955 (quotations of 2+ characters, 3+ letters for Latin text, whole tags)."},
        {"title": "Downstream effect on the trained SASRec ranking (%d sampled users, seed %d)" % (len(sample), args.seed),
         "columns": ["Control", "TCP@10 (boost/only cases)", "TCER@10 (hide/reduce cases)", "NDCG@10", "HR@1"],
         "rows": eff_rows, "note": "TCP/TCER: share of the top ten that is in the REFERENCE target set. none = no control; reference = the reviewed control."},
        {"title": "HR@1 non-inferiority against no control (proposal margin 10%)",
         "columns": ["Model", "Mean HR@1 diff", "95% CI lower", "Relative margin", "Non-inferior (relative 10%)", "Non-inferior (absolute 0.10)", "Mean NDCG@10 diff"],
         "rows": noninf, "note": "Bootstrap over cases. HR@1 of the base ranking is very low, so the relative margin is tiny."},
        {"title": "TCP@10 fidelity: model control vs reviewed control (boost/only cases)",
         "columns": ["Model", "Cases", "Mean TCP diff", "Wilcoxon p", "BH-adjusted p"], "rows": fidelity},
        {"title": "Paired comparisons between models (all %d cases)" % len(cases),
         "columns": ["Model A", "Model B", "Successes A", "Successes B", "Only A", "Only B", "McNemar p (BH)", "Mean per-case score diff", "Wilcoxon p (BH)"],
         "rows": [[t["a"], t["b"], t["success_a"], t["success_b"], t["only_a"], t["only_b"], t["mcnemar_p_bh"], t["mean_score_diff"], t["wilcoxon_p_bh"]] for t in tests],
         "note": "Success: exact profile (NL), abstention (AB), member F1 >= 0.8 (NC). Score: label F1, abstention, member F1."},
        {"title": "Latency, cost and failures", "columns": ["Model", "Calls", "Call errors", "Case errors", "Median s/call", "P90 s/call", "Cost USD"],
         "rows": [[n, s["calls"], s["call_errors"], s["errors"], s["latency_median_s"], s["latency_p90_s"], s["cost_usd"]] for n, s in summaries.items()],
         "note": "Cost: list price x tokens (OpenAI, Anthropic), as reported (Claude CLI), zero for local models (electricity not counted)."},
    ]
    for t in tables:   # every table names the commits that produced it
        t["note"] = (t.get("note", "") + " " + provenance_line).strip()
    summary = {"title": "KuaiRec language controls: local vs frontier models on the frozen reviewed set",
               "status_note": (f"Set {data.get('version')} (SHA-256 {set_sha[:16]}…), reviewed by {data['frozen']['reviewed_by']} "
                               f"at {data['frozen']['reviewed_utc']}. Review CSV SHA-256 {data['frozen']['review_csv_sha256'][:16]}…. "
                               f"{provenance_line}"),
               "scoring_commit": scoring_commit,
               "set_sha256": set_sha, "models": meta, "summaries": summaries, "paired_tests": tests,
               "downstream": {"users": sample, "cases": effects}, "tables": tables,
               "scored_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    pub = ROOT / args.publish
    pub.mkdir(parents=True, exist_ok=True)
    (pub / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    with (pub / "per-case.csv").open("w", encoding="utf-8", newline="") as handle:
        keys = sorted({k for rows in rows_by_model.values() for r in rows for k in r})
        w = csv.DictWriter(handle, fieldnames=["model", *keys])
        w.writeheader()
        for n, rows in rows_by_model.items():
            for r in rows:
                w.writerow({"model": n, **{k: json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v for k, v in r.items()}})
    lines = [f"# {summary['title']}", "", summary["status_note"], ""]
    for t in tables:
        lines += [f"## {t['title']}", "", "| " + " | ".join(t["columns"]) + " |", "|" + " --- |" * len(t["columns"])]
        for r in t["rows"]:
            lines.append("| " + " | ".join(f"{v:.4f}" if isinstance(v, float) else str(v) for v in r) + " |")
        if t.get("note"):
            lines += ["", t["note"]]
        lines.append("")
    (pub / "RESULTS.md").write_text("\n".join(lines), encoding="utf-8")
    spoken = {"gpt-5-mini": "GPT five mini", "gpt-5": "GPT five", "claude-sonnet-5-5-cli": "Claude Sonnet five point five",
              "llama3.1_8b": "Llama three point one eight B", "qwen2.5-coder_7b-instruct": "Qwen two point five coder seven B"}
    say = lambda n: spoken.get(n, n)
    order = sorted(summaries, key=lambda n: -(summaries[n]["nl_exact"] or 0))
    wraps = "[data-role='results'] .lab-table-wrap"
    narration = [
        {"selector": f"{wraps} >> nth=0", "say": "The first table is the nonliteral requests. Exact means the right action, every required "
         "label, and nothing outside the reviewed acceptable set. " + "; ".join(
             f"{say(n)} {summaries[n]['nl_exact']} of {summaries[n]['nl_cases']}" for n in order) + "."},
        {"selector": f"{wraps} >> nth=1", "say": "Next, cases where the model should not change the feed. Correct abstentions: " + "; ".join(
            f"{say(n)} {summaries[n]['ab_abstained']} of {summaries[n]['ab_cases']}" for n in order) + "."},
        {"selector": f"{wraps} >> nth=2", "say": "For new categories, member F1 on the shared pool of one hundred fifty KuaiRec items: " + "; ".join(
            f"{say(n)} {summaries[n]['nc_member_f1']:.2f}" for n in order if summaries[n]["nc_member_f1"] is not None) + "."},
        {"selector": f"{wraps} >> nth=3", "say": None}]
    local = sorted(n for n in order if meta[n].get("provider") == "ollama")
    hosted = sorted(n for n in order if meta[n].get("provider") != "ollama")
    eff = {r[0]: r for r in eff_rows}
    narration[-1]["say"] = (f"Downstream, on the trained ranker, the share of target videos in the top ten goes from {eff['none'][1]:.2f} "
                            f"with no control to {eff['reference'][1]:.2f} with the reviewed control. The frontier models reach "
                            + ", ".join(f"{eff[h][1]:.2f}" for h in hosted)
                            + ("; the local models only " + " and ".join(f"{eff[l][1]:.2f}" for l in local) if local else "")
                            + ". For the frontier models, hit rate at one stays within the absolute margin, but not within the "
                              "relative ten percent margin, because the base rate is so low.")
    if local and hosted:
        narration.append({"selector": f"{wraps} >> nth=0", "hold": 3.5, "say":
            f"Local versus frontier: the local models matched "
            + " and ".join(f"{summaries[l]['nl_exact']}" for l in local) + f" of {summaries[local[0]]['nl_cases']} nonliteral requests; "
            "where they proposed almost nothing, their abstention scores, "
            + " and ".join(f"{summaries[l]['ab_abstained']}" for l in local) + f" of {summaries[local[0]]['ab_cases']}, reflect refusing, not judgement. The frontier models matched "
            + " to ".join(str(v) for v in sorted({summaries[h]['nl_exact'] for h in hosted})) + f" of {summaries[hosted[0]]['nl_cases']}. "
            "Local calls cost nothing, but took " + " and ".join(f"{summaries[l]['latency_median_s']:.0f}" for l in local)
            + " seconds each at the median on this laptop."})
    parser = ROOT / "docs/evidence/lab-eval/20261117-b-parser-rerun/summary.json"
    if parser.is_file():
        rows = {r[0]: r for r in json.loads(parser.read_text(encoding="utf-8"))["tables"][0]["rows"]}
        parts = [f"{say(n)} {rows[n][1].split('/')[0]}" for n in ("llama3.1_8b", "qwen2.5-coder_7b-instruct", "gpt-5-mini", "gpt-5") if n in rows]
        narration.append({"selector": "[data-role='results'] .panel >> nth=1", "hold": 3.5, "say":
            "Finally, the old one-hundred-case parser bank, re-used and labelled as re-use, scored strictly: "
            + "; ".join(parts) + " out of one hundred. None reaches the eighty-five percent target."})
    narration.append({"selector": f"{wraps} >> nth=-1", "say": "The last table lists latency, cost and every failure of every model."})
    for n in narration:
        n.setdefault("hold", 3.0)
    (pub / "narration.json").write_text(json.dumps(narration, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n".join(lines))
    return 0


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--set", required=True)
    r.add_argument("--name", required=True)
    r.add_argument("--provider", required=True)
    r.add_argument("--model", required=True)
    r.add_argument("--effort", default="low")
    r.add_argument("--timeout", type=float)
    r.add_argument("--budget-usd", type=float)
    r.add_argument("--out", required=True)
    r.add_argument("--text", choices=("original", "english"), default="english")
    s = sub.add_parser("score")
    s.add_argument("--set", required=True)
    s.add_argument("--run", required=True)
    s.add_argument("--publish", required=True)
    s.add_argument("--text", choices=("original", "english"), default="original",
                   help="the item text the run used: original (17 Nov run) or english")
    s.add_argument("--users", type=int, default=200)
    s.add_argument("--seed", type=int, default=2026)
    args = ap.parse_args(argv)
    return cmd_run(args) if args.cmd == "run" else cmd_score(args)


if __name__ == "__main__":
    raise SystemExit(main())
