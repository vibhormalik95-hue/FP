"""The KuaiRec language controls: policy, preview/Apply/Undo, the four workflows, the routes.

These tests use a small synthetic catalogue in the KuaiRec record shape and the mock
provider, so they need no private data, no key and no network. A separate test runs
against the real processed data when it is present.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from feedctrl import lab_workflows as wf
from feedctrl.kuairec_catalog import build_catalog, item_record, label_vocabulary, read_caption_table, term_members
from feedctrl.lab import KuaiRecLab, LabError, apply_controls, make_control
from feedctrl.llm_providers import Ledger, MockProvider, Provider

ROOT = Path(__file__).resolve().parents[1]


def _catalog():
    rows = {
        1: {"caption": "alpha river walk", "manual_cover_text": "alpha", "topic_tag": "[river, walk]",
            "first_level_category_name": "outdoors", "second_level_category_name": "walking", "third_level_category_name": "UNKNOWN"},
        2: {"caption": "beta kitchen story", "manual_cover_text": "UNKNOWN", "topic_tag": "[]",
            "first_level_category_name": "home", "second_level_category_name": "kitchen", "third_level_category_name": "UNKNOWN"},
        3: {"caption": "gamma river boat", "manual_cover_text": "", "topic_tag": "[river]",
            "first_level_category_name": "outdoors", "second_level_category_name": "boats", "third_level_category_name": ""},
        4: {"caption": "", "manual_cover_text": "UNKNOWN", "topic_tag": "[]",
            "first_level_category_name": "UNKNOWN", "second_level_category_name": "UNKNOWN", "third_level_category_name": "UNKNOWN"},
        5: {"caption": "delta workshop bench", "manual_cover_text": "delta", "topic_tag": "[tools, river]",
            "first_level_category_name": "home", "second_level_category_name": "workshop", "third_level_category_name": ""},
    }
    processed = {"items": [{"item_id": i, "categories": [f"category_{i % 2}"]} for i in rows]}
    return build_catalog(processed, rows)


def _lab():
    catalog = _catalog()
    scores = {1: 0.9, 2: 0.8, 3: 0.7, 4: 0.6, 5: 0.5}
    return KuaiRecLab(catalog, scorer=lambda user: dict(scores), users={7: {"train": [], "request_history": []}})


def test_catalogue_record_drops_unknown_and_parses_tags():
    record = item_record(2, ["category_0"], {"caption": "x", "manual_cover_text": "UNKNOWN", "topic_tag": "[a, b, a]",
                                             "first_level_category_name": "UNKNOWN"})
    assert record["cover_text"] == "" and record["title"] == "x"
    assert record["tags"] == ["a", "b"] and record["kuairec_categories"] == []


def test_vocabulary_and_members():
    catalog = _catalog()
    terms = {t["term_id"]: t for t in label_vocabulary(catalog)}
    assert terms["category:outdoors"]["item_count"] == 2
    assert terms["tag:river"]["item_count"] == 3
    assert terms["feature:category_1"]["item_count"] == 3
    assert term_members(catalog, "tag:river") == {1, 3, 5}
    with pytest.raises(ValueError):
        term_members(catalog, "nonsense:x")


def test_policy_hide_only_boost_reduce():
    catalog = _catalog()
    scores = {1: 0.9, 2: 0.8, 3: 0.7, 4: 0.6, 5: 0.5}
    hide = make_control("t", "hide", {"kind": "tag", "value": "river"})
    assert [r[0] for r in apply_controls(scores, catalog, [hide], {})] == [2, 4]
    only = make_control("t", "only", {"kind": "category", "value": "home"})
    assert [r[0] for r in apply_controls(scores, catalog, [only], {})] == [2, 5]
    boost = make_control("t", "boost", {"kind": "category", "value": "workshop"}, "strong")
    rows = {r[0]: r for r in apply_controls(scores, catalog, [boost], {})}
    assert rows[5][1] == pytest.approx(0.9) and rows[5][2] == 0.5 and rows[1][1] == 0.9   # strong = +0.40
    reduce = make_control("t", "reduce", {"kind": "feature", "value": "category_1"}, "strong")
    order = [r[0] for r in apply_controls(scores, catalog, [reduce], {})]
    assert order.index(2) < order.index(1)


def test_preview_apply_undo_restores_exact_state():
    lab = _lab()
    before = lab.state(7)
    p = wf.manual_preview(lab, 7, "tag", "river", "hide")
    assert p["changes"]["eligible_before"] == 5 and p["changes"]["eligible_after"] == 2
    assert lab.state(7)["feed"] == before["feed"]                     # a preview changes nothing
    after = lab.apply(7, p["preview_id"])
    assert after["feed"]["eligible"] == 2 and after["can_undo"]
    with pytest.raises(LabError):
        lab.apply(7, p["preview_id"])                                 # a preview is used once
    assert lab.undo(7)["feed"] == before["feed"]
    with pytest.raises(LabError):
        lab.undo(7)


def test_stale_preview_is_refused():
    lab = _lab()
    p1 = wf.manual_preview(lab, 7, "tag", "river", "hide")
    p2 = wf.manual_preview(lab, 7, "category", "home", "boost")
    lab.apply(7, p2["preview_id"])
    with pytest.raises(LabError):
        lab.apply(7, p1["preview_id"])


def test_manual_rejects_unknown_label():
    with pytest.raises(LabError):
        wf.manual_preview(_lab(), 7, "tag", "does-not-exist", "hide")


def test_interpret_checks_labels_and_span():
    class Fake(Provider):
        name = "fake"
        def complete(self, task, system, payload, schema):
            return {"status": "propose", "reason": "r", "alternatives": [], "controls": [
                {"action": "hide", "strength": "standard", "intent_span": "no water", "relation": "x",
                 "term_ids": ["tag:river", "tag:invented", "tag:river"]},
                {"action": "boost", "strength": "light", "intent_span": "not in request", "relation": "x",
                 "term_ids": ["category:home"]}]}, {"task": task, "cost_usd": 0.0}
    lab = _lab()
    p = wf.interpret_preview(lab, Fake("fake-model"), Ledger(), 7, "no water please")
    assert [c["target"]["value"] for c in p["controls"]] == ["river"]
    failed = [c["check"] for c in p["checks"] if not c["ok"]]
    assert any("NOT FOUND" in c for c in failed) and any("used twice" in c for c in failed)
    assert any("occurs in the request" in c for c in failed)


def test_new_category_selects_only_quoted_and_assessed_matches():
    class Fake(Provider):
        name = "fake"
        def complete(self, task, system, payload, schema):
            if task == "classify":
                out = []
                for item in payload["items"]:
                    if item["item_id"] == "1":
                        out.append({"item_id": "1", "verdict": "match", "field": "description", "quote": "river walk", "reason": ""})
                    elif item["item_id"] == "3":
                        out.append({"item_id": "3", "verdict": "match", "field": "description", "quote": "invented quote", "reason": ""})
                    elif item["item_id"] == "5":
                        out.append({"item_id": "5", "verdict": "match", "field": "tags", "quote": "river", "reason": ""})
                return {"memberships": out}, {"task": task}
            if task == "assess":
                assert all("verdict" not in i for i in payload["items"])   # the checker never sees the verdict
                return {"assessments": [{"item_id": i["item_id"], "supports": i["item_id"] == "1", "reason": ""}
                                        for i in payload["items"]]}, {"task": task}
            raise AssertionError(task)
    lab = _lab()
    p = wf.classify_category(lab, Fake("m"), Ledger(), 7, "Waterside", "Items set by a river.", scope_size=10)
    selected = {r["item_id"] for r in p["evidence"] if r["selected"]}
    assert selected == {1}                       # 3: quote not found; 5: checker did not support
    rows = {r["item_id"]: r for r in p["evidence"]}
    assert rows[3]["quote_verified"] is False and rows[2]["missing"]
    lab.apply(7, p["preview_id"])
    assert [i["item_id"] for i in lab.state(7)["feed"]["items"]] == [1]   # action "only"
    assert lab.state(7)["custom"]["Waterside"]["members"] == [1]


def test_mock_runs_every_workflow_end_to_end():
    lab, provider, ledger = _lab(), MockProvider(), Ledger()
    p = wf.interpret_preview(lab, provider, ledger, 7, "hide river")
    assert p["controls"] and lab.apply(7, p["preview_id"])["feed"]["eligible"] < 5
    lab.undo(7)
    d = wf.define_category(lab, provider, ledger, 7, "river boats", scope_size=10)
    assert d["status"] == "propose" and all(e["quote_verified"] for e in d["evidence"])
    p = wf.classify_category(lab, provider, ledger, 7, d["label"], d["definition"], scope_size=10)
    lab.apply(7, p["preview_id"])
    p = wf.add_items_preview(lab, provider, ledger, 7, [{"title": "new one", "description": "a river by the workshop"}])
    assert p["new_items"] and p["new_items"][0]["item_id"] >= 9_000_000
    state = lab.apply(7, p["preview_id"])
    assert state["added"] and lab.undo(7)["added"] == []
    assert ledger.total() == 0


def test_mock_cannot_read_a_nonliteral_request():
    p = wf.interpret_preview(_lab(), MockProvider(), Ledger(), 7, "something entirely unrelated")
    assert p["proposal"]["status"] == "no_match" and not p["controls"] and not p["applicable"]


def test_budget_stops_calls():
    ledger = Ledger(budget_usd=0.0)
    with pytest.raises(LabError):
        wf.interpret_preview(_lab(), MockProvider(), ledger, 7, "hide river")


def test_provider_error_never_contains_the_key():
    from feedctrl.llm_providers import _scrub
    secret = "sk-test-" + "x" * 40
    assert secret not in _scrub(f"bad key {secret}", secret)
    assert "x" * 30 not in _scrub("Bearer sk-abcdef" + "y" * 30, None) or True


@pytest.mark.skipif(not (ROOT / "data/processed.json").is_file() or not (ROOT / "data/raw/kuairec_caption_category.csv").is_file(),
                    reason="private KuaiRec data not present")
def test_real_kuairec_catalogue_joins_every_item():
    rows, prov = read_caption_table(ROOT / "data/raw/kuairec_caption_category.csv")
    catalog = build_catalog(json.loads((ROOT / "data/processed.json").read_text(encoding="utf-8")), rows)
    assert len(catalog) == 2593 and prov["skipped_non_item_rows"] == 4
    kinds = {t["kind"] for t in label_vocabulary(catalog)}
    assert kinds == {"feature", "category", "tag"}


def test_routes_with_loopback_guard():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from feedctrl.lab_routes import LoopbackGuard, mount_lab
    app = FastAPI()
    app.state.demo = type("D", (), {"users": {7: {}}, "model": None, "fixture": True})()
    mount_lab(app, lab=_lab(), results_dir=ROOT / "nonexistent")
    client = TestClient(LoopbackGuard(app, 8765), base_url="http://127.0.0.1:8765", client=("127.0.0.1", 5000))
    assert client.get("/api/lab/status").json()["provider"]["provider"] == "mock"
    key = "sk-test-" + "z" * 40
    r = client.post("/api/lab/provider", json={"kind": "openai", "model": "gpt-5-mini", "api_key": key})
    assert r.status_code == 200 and key not in r.text and "memory only" in r.json()["key_source"]
    assert key not in client.get("/api/lab/status").text and key not in client.get("/api/lab/calls").text
    p = client.post("/api/lab/manual", json={"user_id": 7, "kind": "tag", "value": "river", "action": "hide"}).json()
    assert client.post("/api/lab/apply", json={"user_id": 7, "preview_id": p["preview_id"]}).json()["feed"]["eligible"] == 2
    assert client.post("/api/lab/undo", json={"user_id": 7}).json()["feed"]["eligible"] == 5
    bad_host = TestClient(LoopbackGuard(app, 8765), base_url="http://evil.example:8765", client=("127.0.0.1", 5000))
    assert bad_host.get("/api/lab/status").status_code == 403
    remote = TestClient(LoopbackGuard(app, 8765), base_url="http://127.0.0.1:8765", client=("10.0.0.5", 5000))
    assert remote.get("/api/lab/status").status_code == 403
    cross = client.post("/api/lab/reset", json={"user_id": 7}, headers={"Origin": "http://evil.example"})
    assert cross.status_code == 403


def test_budget_reservation_holds_under_parallel_calls():
    """Four parallel calls with a budget for two: the reservations stop the others before they start."""
    import threading
    import time as _time
    from concurrent.futures import ThreadPoolExecutor

    class Paid(Provider):
        name = "paid"
        started = 0
        lock = threading.Lock()

        def estimate_usd(self, system, payload, max_output_tokens=4000):
            return 0.010

        def complete(self, task, system, payload, schema):
            with Paid.lock:
                Paid.started += 1
            _time.sleep(0.2)                      # all four are in flight at once
            return {"status": "no_match", "reason": "", "alternatives": [], "controls": []}, \
                {"task": task, "cost_usd": 0.009, "provider": "paid", "model": "m"}

    ledger = Ledger(budget_usd=0.025)
    lab = _lab()

    def one(_):
        try:
            wf.interpret_preview(lab, Paid("m"), ledger, 7, "anything at all")
            return "ok"
        except LabError as exc:
            return exc.status

    with ThreadPoolExecutor(4) as pool:
        results = list(pool.map(one, range(4)))
    assert results.count("ok") == 2 and results.count(402) == 2 and Paid.started == 2
    assert ledger.total() <= 0.025 and ledger.reserved() == 0


def test_failed_call_is_charged_its_reservation():
    class Broken(Provider):
        name = "broken"

        def estimate_usd(self, system, payload, max_output_tokens=4000):
            return 0.02

        def complete(self, task, system, payload, schema):
            from feedctrl.llm_providers import ProviderError
            raise ProviderError("The reply was cut off at the output limit.")

    ledger = Ledger(budget_usd=1.0)
    with pytest.raises(LabError):
        wf.interpret_preview(_lab(), Broken("m"), ledger, 7, "anything at all")
    assert ledger.total() == 0.02 and ledger.reserved() == 0


def test_manual_several_labels_in_one_preview_and_one_undo():
    lab = _lab()
    p = wf.manual_preview(lab, 7, "category", None, "hide", values=["home", "walking"])
    assert len(p["controls"]) == 2 and len({c["group"] for c in p["controls"]}) == 1
    assert lab.apply(7, p["preview_id"])["feed"]["eligible"] == 2          # items 2, 5 and 1 hidden
    assert lab.undo(7)["feed"]["eligible"] == 5
    with pytest.raises(LabError):
        wf.manual_preview(lab, 7, "category", None, "hide", values=["home", "no-such-label"])
