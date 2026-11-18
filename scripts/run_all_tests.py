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


def pytest_verdict(code, text):
    """The pytest step passes only when pytest's own exit code agrees with the parsed failures.

    Exit 0 with no failure line passes. Exit 1 passes only when every parsed failure is listed in
    FROZEN_BY_DESIGN and the summary line counts exactly those failures. Any other exit code (2 interrupted,
    3 internal error, 4 usage error, 5 no tests collected), or exit 1 with no parsed failure line, fails."""
    failed = re.findall(r"^(?:FAILED|ERROR) (\S+)", text, re.M)
    unexpected = [f for f in failed if f not in FROZEN_BY_DESIGN]
    frozen = [f for f in failed if f in FROZEN_BY_DESIGN]
    last = [line for line in text.splitlines() if re.search(r"\d+ (passed|failed|errors?)\b", line)]
    summary = last[-1] if last else ""
    counted = sum(int(n) for n in re.findall(r"(\d+) (?:failed|errors?)\b", summary))
    problems = list(unexpected)
    if code == 0:
        if failed:
            problems.append(f"pytest exit 0 but {len(failed)} failure line(s) parsed")
    elif code == 1:
        if not failed:
            problems.append("pytest exit 1 without a parsed failure line")
        elif counted != len(failed):
            problems.append(f"pytest summary counts {counted} failure(s) or error(s), {len(failed)} parsed")
    else:
        problems.append(f"pytest exit {code} (not a test-failure exit)")
    if code in (0, 1) and not summary:
        problems.append("no pytest summary line")
    return {"exit": code, "result": summary or "?", "failed_unexpected": problems,
            "failed_frozen_by_design": frozen, "ok": not problems}


def snapshot(base, user):
    """The exact applied state and feed of one user: controls, new categories with members, added items,
    eligible count and the ordered item ids with scores of the shown feed."""
    st, s, _ = call(base, f"/api/lab/state?user_id={user}")
    if st != 200:
        return {"error": st}
    return {"controls": [(c.get("action"), (c.get("target") or {}).get("kind"), (c.get("target") or {}).get("value"),
                          c.get("strength"), c.get("group")) for c in s["controls"]],
            "custom": {k: v["members"] for k, v in s["custom"].items()},
            "added": [(a["item_id"], a["title"]) for a in s["added"]],
            "eligible": s["feed"]["eligible"],
            "order": [(i["item_id"], i["score"]) for i in s["feed"]["items"]],
            "ranked": s["feed"].get("ranked_ids"),
            "items": {i["item_id"]: {"categories": i.get("kuairec_categories") or [], "tags": i.get("tags") or []}
                      for i in s["feed"]["items"]}}


def same_state(a, b):
    keys = ("controls", "custom", "added", "eligible", "order", "ranked")
    return all(a.get(k) == b.get(k) for k in keys)


def feed_changed(before, after):
    return before["eligible"] != after["eligible"] or before["order"] != after["order"] \
        or before.get("ranked") != after.get("ranked") \
        or before["custom"] != after["custom"] or before["added"] != after["added"]


def expected_interpret(provider, kind):
    """What a correct run must do. A language model must propose for every example request; an abstain example
    must change nothing. The mock reads literal words only: on a nonliteral request it may or may not find a
    literal label word, so either outcome is accepted, but a proposal must still apply and undo exactly."""
    if kind == "abstain":
        return "abstain"
    if provider == "mock" and kind == "nonliteral":
        return "any"
    return "propose"


def workflows(base, user, examples, provider="mock"):
    rows = []

    def record(workflow, ex, status, payload, seconds, outcome, ok, why=""):
        calls = payload.get("calls", []) if isinstance(payload, dict) else []
        rows.append({"workflow": workflow, "domain": ex.get("domain"), "input": ex.get("request") or ex.get("description")
                     or ex.get("value") or ex.get("items", [{}])[0].get("title"), "http": status, "seconds": seconds,
                     "model_calls": len(calls), "cost_usd": round(sum(c.get("cost_usd") or 0 for c in calls), 6),
                     "unknown_cost_calls": sum(c.get("cost_usd") is None for c in calls),
                     "call_errors": [c["error"] for c in calls if c.get("error")], "outcome": outcome, "ok": bool(ok),
                     "why_not_ok": "" if ok else why,
                     "detail": payload.get("detail") if isinstance(payload, dict) else None})

    def check_row(name, ok, outcome, why):
        rows.append({"workflow": name, "domain": "all", "input": "", "http": None, "seconds": 0, "model_calls": 0,
                     "cost_usd": 0, "unknown_cost_calls": 0, "call_errors": [], "outcome": outcome, "ok": bool(ok),
                     "why_not_ok": "" if ok else why, "detail": None})

    def apply_undo(preview, check=None):
        """Apply, require a real change (and the semantic ``check`` on the applied state), Undo, and require the exact
        earlier state: the same controls, members, added items, eligible count, item ids, order and scores."""
        before = snapshot(base, user)
        s1, applied, _ = call(base, "/api/lab/apply", {"user_id": user, "preview_id": preview["preview_id"]})
        after = snapshot(base, user)
        semantic = check(after) if (check and s1 == 200) else (True, "")
        s2, _, _ = call(base, "/api/lab/undo", {"user_id": user})
        restored = snapshot(base, user)
        why = []
        if s1 != 200 or s2 != 200:
            why.append(f"apply {s1}, undo {s2}")
        if s1 == 200 and not feed_changed(before, after):
            why.append("Apply changed nothing")
        if not semantic[0]:
            why.append(semantic[1])
        if not same_state(restored, before):
            why.append("Undo did not restore the exact earlier state (ids, order, scores, controls)")
        return not why, applied.get("feed", {}).get("eligible"), "; ".join(why)

    def label_gone(kind, value):
        key = {"category": "categories", "tag": "tags"}.get(kind)

        def check(after):
            bad = [i for i, it in after["items"].items() if key and value in it[key]]
            return not bad, f"hidden label {value!r} still in the shown feed: {bad[:5]}"
        return check

    initial = snapshot(base, user)
    for ex in examples["manual"]:
        st, p, sec = call(base, "/api/lab/manual", {"user_id": user, **{k: ex[k] for k in ("kind", "value", "action")},
                                                    "strength": ex.get("strength", "standard")})
        check = label_gone(ex["kind"], ex["value"]) if ex["action"] == "hide" else None
        ok, after, why = apply_undo(p, check) if st == 200 and p.get("applicable") else (False, None, f"http {st}, not applicable")
        record("manual", ex, st, p, sec, f"eligible {p.get('changes', {}).get('eligible_before')} -> {after}", ok, why)
    for ex in examples["interpret"] + examples.get("interpret_abstain", []):
        kind = ex.get("kind", "abstain")
        st, p, sec = call(base, "/api/lab/interpret", {"user_id": user, "request": ex["request"]})
        status = (p.get("proposal") or {}).get("status") if st == 200 else None
        want = expected_interpret(provider, kind)
        ok, why = st == 200, "" if st == 200 else f"http {st}"
        if ok and want == "any" and p.get("applicable"):
            ok, _, why = apply_undo(p)
        elif ok and want == "propose":
            if not (p.get("applicable") and p.get("controls")):
                ok, why = False, f"expected an applicable proposal, got status {status} with {len(p.get('controls', []))} control(s)"
            else:
                ok, _, why = apply_undo(p)
        elif ok and want == "abstain" and (p.get("applicable") or p.get("controls")):
            ok, why = False, f"expected no change, got {len(p.get('controls', []))} control(s)"
        record(f"interpret ({kind}, expect {want})", ex, st, p, sec,
               f"{status}: " + "; ".join(c["text"] for c in p.get("controls", []))[:300]
               if st == 200 else str(p.get("detail"))[:300], ok, why)
    members_seen, label = 0, None
    for ex in examples["new_category"]:
        st, d, sec = call(base, "/api/lab/define", {"user_id": user, "description": ex["description"], "scope_size": 100})
        record("new-category: define", ex, st, d, sec, f"{d.get('status')}: {d.get('label')}" if st == 200 else str(d.get("detail")),
               st == 200, f"http {st}")
        if st == 200 and d.get("status") == "propose":
            st, p, sec = call(base, "/api/lab/classify", {"user_id": user, "label": d["label"], "definition": d["definition"],
                                                          "action": "boost", "strength": "strong", "scope_size": 100})
            ev = p.get("evidence", []) if st == 200 else []
            selected = [r for r in ev if r.get("selected")]
            # The application's rule: selected = verdict match + quotation found + the independent check supports it.
            bad = [r["item_id"] for r in selected if not (r.get("verdict") == "match" and r.get("quote_verified")
                                                          and (r.get("assessment") or {}).get("supports") is True)]
            ok, why = st == 200 and not bad, (f"http {st}" if st != 200 else f"selected without match+quote+check: {bad}")
            if ok and selected:
                members_seen += len(selected)
                before = snapshot(base, user)
                s1, _, _ = call(base, "/api/lab/apply", {"user_id": user, "preview_id": p["preview_id"]})
                after = snapshot(base, user)
                got = set()
                for k, m in after.get("custom", {}).items():
                    if k not in before.get("custom", {}):
                        got = set(m)
                want_ids = {r["item_id"] for r in selected}
                if s1 != 200 or got != want_ids:
                    ok, why = False, f"apply {s1}; members after Apply {sorted(got)[:10]} differ from selected {sorted(want_ids)[:10]}"
                elif not feed_changed(before, after):
                    ok, why = False, "Apply of the new category changed nothing"
                else:
                    label = d["label"]
            record("new-category: classify", ex, st, p, sec, f"{len(selected)} selected of {len(ev)}", ok, why)
    check_row("new-category: at least one category selects members and feeds the filter", members_seen > 0,
              f"{members_seen} members selected", "no example selected any member")
    for ex in examples.get("new_category_negative", []):
        st, d, sec = call(base, "/api/lab/define", {"user_id": user, "description": ex["description"], "scope_size": 100})
        n = 0
        if st == 200 and d.get("status") == "propose":
            st2, p, _ = call(base, "/api/lab/classify", {"user_id": user, "label": d["label"], "definition": d["definition"],
                                                         "action": "boost", "strength": "strong", "scope_size": 100})
            n = sum(bool(r.get("selected")) for r in p.get("evidence", [])) if st2 == 200 else -1
        record("new-category: negative (expect no member)", ex, st, d, sec, f"{d.get('status')}: {n} selected",
               st == 200 and n == 0, f"http {st}, {n} selected")
    for ex in examples["new_items"]:
        st, p, sec = call(base, "/api/lab/new-items", {"user_id": user, "items": ex["items"]})
        ok, why = st == 200 and bool(p.get("applicable")), f"http {st}"
        if ok:
            title = ex["items"][0]["title"]
            ok, _, why = apply_undo(p, lambda after: (any(t == title for _, t in after["added"]),
                                                       f"the item {title!r} was not added"))
        ev = p.get("evidence", [{}])[0] if st == 200 else {}
        record("new-items", ex, st, p, sec, f"categories {ev.get('categories')} tags {ev.get('tags')} "
               f"new-category verdicts {[(n['label'], n['verdict'], n.get('selected')) for n in ev.get('new_categories', [])]}"
               if st == 200 else str(p.get("detail")), ok, why)
    s_reset, _, _ = call(base, "/api/lab/reset", {"user_id": user})
    final = snapshot(base, user)
    check_row("reset restores the exact initial feed (ids, order, scores, no controls)",
              s_reset == 200 and same_state(final, initial), f"reset http {s_reset}",
              "state after Reset differs from the initial state")
    return rows, label


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", default="mock")
    ap.add_argument("--model")
    ap.add_argument("--user", type=int, default=14)
    ap.add_argument("--skip-browser", action="store_true")
    ap.add_argument("--only-workflows", action="store_true", help="skip the test suites and the browser")
    ap.add_argument("--examples", default="tools/demo_examples.json")
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(args.out) if args.out else ROOT / "runs" / f"all-tests-{stamp}"
    out.mkdir(parents=True, exist_ok=False)
    summary = {"started_utc": stamp, "provider": args.provider, "model": args.model, "steps": {}}

    if args.only_workflows:
        args.skip_browser = True
    code, sec = (0, 0) if args.only_workflows else sh([PY, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rfE", "tests"], out / "pytest.log")
    if args.only_workflows:
        (out / "pytest.log").write_text("skipped (--only-workflows)", encoding="utf-8")
    text = (out / "pytest.log").read_text(encoding="utf-8", errors="replace")
    summary["steps"]["pytest"] = {"seconds": sec, **({"exit": 0, "result": "skipped (--only-workflows)", "failed_unexpected": [],
                                                       "failed_frozen_by_design": [], "ok": True}
                                                      if args.only_workflows else pytest_verdict(code, text))}

    node = shutil.which("node")
    tests = sorted(str(p.relative_to(ROOT)) for p in (ROOT / "web/tests").glob("*.test.mjs"))
    code, sec = (0, 0) if args.only_workflows else sh([node, "--test", *tests], out / "node.log")
    if args.only_workflows:
        (out / "node.log").write_text("skipped", encoding="utf-8")
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
            code, sec = sh([node, "tests/browser/cjk_check.cjs", "--base", base, "--out", str(out / "cjk")],
                           out / "cjk.log", timeout=3600)
            receipt = out / "cjk" / "cjk-check-receipt.json"
            r = json.loads(receipt.read_text(encoding="utf-8")) if receipt.is_file() else {}
            summary["steps"]["cjk"] = {"exit": code, "seconds": sec, "ok": code == 0,
                                       "result": f"{r.get('screens', 0)} screens, {r.get('failed', '?')} with CJK"}
            call(base, "/api/lab/reset", {"user_id": args.user})
        examples = json.loads((ROOT / args.examples).read_text(encoding="utf-8"))
        started = time.monotonic()
        rows, _ = workflows(base, args.user, examples, provider=args.provider)
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
        lines += ["", "Unexpected test failures or pytest problems:"] + [f"- `{t}`" for t in summary["steps"]["pytest"]["failed_unexpected"]]
    wrows = json.loads((out / "workflows.json").read_text(encoding="utf-8")) if (out / "workflows.json").is_file() else []
    if any(not r["ok"] for r in wrows):
        lines += ["", "Workflow checks that failed:"] + [f"- {r['workflow']} ({r['domain']}): {r.get('why_not_ok')}"
                                                          for r in wrows if not r["ok"]]
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
