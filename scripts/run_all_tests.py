"""Run every test suite, the browser flows and every workflow end to end; write one dated report.

    python scripts/run_all_tests.py                                   # mock provider, no key, no cost
    python scripts/run_all_tests.py --provider openai --model gpt-5-mini
    python scripts/run_all_tests.py --provider ollama --model qwen2.5-coder:7b-instruct

Steps: (1) pytest on tests/, (2) the Node unit tests of the page, (3) the app on real KuaiRec
in a child process, (4) the browser flows (tests/browser/lab_flows.cjs), (5) every workflow
through the HTTP API on the examples of tools/demo_examples.json from several domains, with
latency and cost of every model call. Output: runs/all-tests-<UTC>/summary.json and summary.md.
Tests that fail by design (a frozen 11 November profile) are listed in FROZEN_BY_DESIGN and
reported separately; they do not hide any other failure.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
# Frozen by design: the guarded driver of the frozen 11 November personal-adapter profile imports a
# module that loads ctypes on Windows, which its offline guard blocks. The profile is not changed.
FROZEN_BY_DESIGN = {
    "tests/test_guarded_current_contract.py::test_the_driver_checks_pass_on_a_copy_and_the_frozen_profile_is_not_changed":
        "frozen 11 Nov profile; its offline guard blocks ctypes, which click loads on Windows",
}


def sh(cmd, log, timeout=1800, env=None):
    started = time.monotonic()
    with open(log, "w", encoding="utf-8") as handle:
        proc = subprocess.run(cmd, cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT, timeout=timeout, env=env,
                              shell=isinstance(cmd, str))
    return proc.returncode, round(time.monotonic() - started, 1)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def call(base, path, body=None, timeout=900):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(base + path, data=data, method="GET" if body is None else "POST",
                                 headers={"Content-Type": "application/json"})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read()), round(time.monotonic() - started, 2)
    except urllib.error.HTTPError as e:
        try:
            payload = json.loads(e.read())
        except Exception:
            payload = {"detail": str(e)}
        return e.code, payload, round(time.monotonic() - started, 2)


def workflows(base, user, examples):
    rows = []

    def record(workflow, ex, status, payload, seconds, outcome, ok):
        calls = payload.get("calls", []) if isinstance(payload, dict) else []
        rows.append({"workflow": workflow, "domain": ex.get("domain"), "input": ex.get("request") or ex.get("description")
                     or ex.get("value") or ex.get("items", [{}])[0].get("title"), "http": status, "seconds": seconds,
                     "model_calls": len(calls), "cost_usd": round(sum(c.get("cost_usd") or 0 for c in calls), 6),
                     "call_errors": [c["error"] for c in calls if c.get("error")], "outcome": outcome, "ok": ok,
                     "detail": payload.get("detail") if isinstance(payload, dict) else None})

    def apply_undo(preview):
        s1, applied, _ = call(base, "/api/lab/apply", {"user_id": user, "preview_id": preview["preview_id"]})
        s2, undone, _ = call(base, "/api/lab/undo", {"user_id": user})
        return s1 == 200 and s2 == 200 and undone["feed"]["eligible"] == preview["before"]["eligible"], \
            applied.get("feed", {}).get("eligible")

    for ex in examples["manual"]:
        st, p, sec = call(base, "/api/lab/manual", {"user_id": user, **{k: ex[k] for k in ("kind", "value", "action")},
                                                    "strength": ex.get("strength", "standard")})
        ok, after = apply_undo(p) if st == 200 else (False, None)
        record("manual", ex, st, p, sec, f"eligible {p.get('changes', {}).get('eligible_before')} -> {after}", ok)
    for ex in examples["interpret"]:
        st, p, sec = call(base, "/api/lab/interpret", {"user_id": user, "request": ex["request"]})
        status = (p.get("proposal") or {}).get("status") if st == 200 else None
        ok = st == 200
        if ok and p["applicable"]:
            ok, _ = apply_undo(p)
        record("interpret", ex, st, p, sec, f"{status}: " + "; ".join(c["text"] for c in p.get("controls", []))[:300]
               if st == 200 else str(p.get("detail"))[:300], ok)
    label = None
    for ex in examples["new_category"]:
        st, d, sec = call(base, "/api/lab/define", {"user_id": user, "description": ex["description"], "scope_size": 30})
        record("new-category: define", ex, st, d, sec, f"{d.get('status')}: {d.get('label')}" if st == 200 else str(d.get("detail")), st == 200)
        if st == 200 and d.get("status") == "propose":
            st, p, sec = call(base, "/api/lab/classify", {"user_id": user, "label": d["label"], "definition": d["definition"],
                                                          "action": "boost", "strength": "strong", "scope_size": 30})
            selected = [r["item_id"] for r in p.get("evidence", []) if r.get("selected")] if st == 200 else []
            ok = st == 200 and all(r["quote_verified"] or r["verdict"] == "unknown" for r in p.get("evidence", [])
                                   if r.get("selected"))
            if ok and p["applicable"]:
                s1, _, _ = call(base, "/api/lab/apply", {"user_id": user, "preview_id": p["preview_id"]})
                ok, label = s1 == 200, d["label"]
            record("new-category: classify", ex, st, p, sec, f"{len(selected)} selected of {len(p.get('evidence', []))}", ok)
    for ex in examples["new_items"]:
        st, p, sec = call(base, "/api/lab/new-items", {"user_id": user, "items": ex["items"]})
        ok = st == 200
        if ok:
            ok, _ = apply_undo(p)
        ev = p.get("evidence", [{}])[0] if st == 200 else {}
        record("new-items", ex, st, p, sec, f"categories {ev.get('categories')} tags {ev.get('tags')} "
               f"new-category verdicts {[(n['label'], n['verdict']) for n in ev.get('new_categories', [])]}"
               if st == 200 else str(p.get("detail")), ok)
    call(base, "/api/lab/reset", {"user_id": user})
    return rows, label


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", default="mock")
    ap.add_argument("--model")
    ap.add_argument("--user", type=int, default=14)
    ap.add_argument("--skip-browser", action="store_true")
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(args.out) if args.out else ROOT / "runs" / f"all-tests-{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    summary = {"started_utc": stamp, "provider": args.provider, "model": args.model, "steps": {}}

    code, sec = sh([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rfE", "tests"], out / "pytest.log")
    text = (out / "pytest.log").read_text(encoding="utf-8", errors="replace")
    failed = re.findall(r"^(?:FAILED|ERROR) (\S+)", text, re.M)
    unexpected = [f for f in failed if f not in FROZEN_BY_DESIGN]
    last = [line for line in text.splitlines() if re.search(r"\d+ (passed|failed)", line)]
    summary["steps"]["pytest"] = {"exit": code, "seconds": sec, "result": last[-1] if last else "?",
                                  "failed_unexpected": unexpected,
                                  "failed_frozen_by_design": [f for f in failed if f in FROZEN_BY_DESIGN],
                                  "ok": not unexpected}

    node = shutil.which("node")
    tests = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "web/tests").glob("*.test.mjs"))
    code, sec = sh([node, "--test", *tests], out / "node.log")
    ntext = (out / "node.log").read_text(encoding="utf-8", errors="replace")
    summary["steps"]["node"] = {"exit": code, "seconds": sec, "ok": code == 0,
                                "result": " ".join(re.findall(r"^# (?:pass|fail) \d+", ntext, re.M))}

    port = free_port()
    base = f"http://127.0.0.1:{port}"
    server_log = open(out / "server.log", "w", encoding="utf-8")
    cmd = [PY, "scripts/run_app.py", "--port", str(port), "--provider", args.provider]
    if args.model:
        cmd += ["--model", args.model]
    server = subprocess.Popen(cmd, cwd=ROOT, stdout=server_log, stderr=subprocess.STDOUT)
    try:
        for _ in range(120):
            try:
                if call(base, "/api/lab/status")[0] == 200:
                    break
            except OSError:
                time.sleep(1)
        else:
            raise SystemExit("The app did not start; see server.log")
        if not args.skip_browser:
            code, sec = sh([node, "tests/browser/lab_flows.cjs", "--base", base, "--out", str(out / "browser")],
                           out / "browser.log", timeout=3600)
            receipt = out / "browser" / "lab-browser-receipt.json"
            r = json.loads(receipt.read_text(encoding="utf-8")) if receipt.is_file() else {}
            summary["steps"]["browser"] = {"exit": code, "seconds": sec, "ok": code == 0,
                                           "result": f"{r.get('passed', 0)} passed, {r.get('failed', '?')} failed"}
            call(base, "/api/lab/reset", {"user_id": args.user})
        examples = json.loads((ROOT / "tools/demo_examples.json").read_text(encoding="utf-8"))
        started = time.monotonic()
        rows, _ = workflows(base, args.user, examples)
        _, calls, _ = call(base, "/api/lab/calls")
        summary["steps"]["workflows"] = {"seconds": round(time.monotonic() - started, 1), "ok": all(r["ok"] for r in rows),
                                         "cases": len(rows), "failed": sum(not r["ok"] for r in rows),
                                         "model_calls": len(calls["calls"]), "cost_usd": calls["total_usd"]}
        (out / "workflows.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        (out / "model-calls.json").write_text(json.dumps(calls, ensure_ascii=False, indent=1), encoding="utf-8")
    finally:
        server.terminate()
        server.wait(timeout=30)
        server_log.close()
    summary["ok"] = all(s["ok"] for s in summary["steps"].values())
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    lines = [f"# run-all-tests {stamp}", "", f"Provider: {args.provider} {args.model or ''}", "",
             "| Step | OK | Result | Seconds |", "| --- | --- | --- | --- |"]
    for name, s in summary["steps"].items():
        lines.append(f"| {name} | {'yes' if s['ok'] else 'NO'} | {s.get('result', '')} {s.get('cases', '')} | {s['seconds']} |")
    if summary["steps"]["pytest"]["failed_frozen_by_design"]:
        lines += ["", "Frozen by design (reported, not counted as failures):"] + [
            f"- `{t}`: {FROZEN_BY_DESIGN[t]}" for t in summary["steps"]["pytest"]["failed_frozen_by_design"]]
    if summary["steps"]["pytest"]["failed_unexpected"]:
        lines += ["", "Unexpected test failures:"] + [f"- `{t}`" for t in summary["steps"]["pytest"]["failed_unexpected"]]
    lines += ["", "| Workflow | Domain | Input | OK | Seconds | Calls | USD | Outcome |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in json.loads((out / "workflows.json").read_text(encoding="utf-8")) if (out / "workflows.json").is_file() else []:
        lines.append(f"| {r['workflow']} | {r['domain']} | {str(r['input'])[:60]} | {'yes' if r['ok'] else 'NO'} | {r['seconds']} | "
                     f"{r['model_calls']} | {r['cost_usd']} | {str(r['outcome'])[:120]} |")
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nWritten: {out}")
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
