"""Tests for Feed Control Studio (studio/). No network, no key, no cost."""
import json
import logging

import httpx
import httpx2
import pytest
from fastapi.testclient import TestClient

from studio import workflows
from studio.engine import Studio, StudioError, make_control
from studio.providers import (AnthropicProvider, Ledger, MockProvider, OpenAICompatibleProvider, Provider,
                              ProviderError, build_provider)
from studio.server import create_app

SECRET = "sk-ant-TESTKEY-0123456789abcdefghijklmnopqrstuvwxyz"


class Scripted(Provider):
    """Returns fixed answers per task; records payloads."""
    name, label = "scripted", "Scripted test double"

    def __init__(self, answers):
        super().__init__("scripted-1")
        self.answers, self.payloads = answers, []

    def complete(self, task, system, payload, schema):
        self.payloads.append((task, payload))
        ans = self.answers[task]
        data = ans(payload) if callable(ans) else ans
        return json.loads(json.dumps(data)), {"task": task, "provider": self.name, "model": self.model,
                                               "latency_s": 0.01, "input_tokens": 10, "output_tokens": 5,
                                               "cost_usd": 0.001, "cost_source": "test"}


def client(provider=None, port=8765):
    app = create_app(port=port, provider=provider or MockProvider())
    return TestClient(app, base_url=f"http://127.0.0.1:{port}"), app


# ------------------------------------------------------------------ engine
def test_feed_hide_only_boost_and_undo():
    s = Studio()
    assert s.feed()["eligible"] == 40
    p = s._new_preview("manual", "x", controls=[make_control("manual", "hide", {"kind": "category", "value": "Gaming"})])
    assert p["changes"]["eligible_after"] == 36 and s.feed()["eligible"] == 40  # preview changes nothing
    s.apply(p["id"])
    assert s.feed()["eligible"] == 36
    p = s._new_preview("manual", "x", controls=[make_control("manual", "only", {"kind": "tag", "value": "calm"})])
    s.apply(p["id"])
    assert all(i["category"] != "Gaming" for i in s.feed()["top"])
    assert s.feed()["eligible"] == 4  # calm items minus the cozy game
    s.undo(); s.undo()
    assert s.feed()["eligible"] == 40 and not s.controls


def test_boost_moves_items_up():
    s = Studio()
    before = [r["id"] for r in s.feed()["top"]]
    p = s._new_preview("manual", "x", controls=[make_control("manual", "boost", {"kind": "category", "value": "Money"}, "strong")])
    s.apply(p["id"])
    after = [r["id"] for r in s.feed()["top"]]
    assert {"v134", "v136"} <= set(after) and before != after


def test_stale_preview_is_refused_and_expired_preview_is_gone(monkeypatch):
    s = Studio()
    c = make_control("manual", "hide", {"kind": "category", "value": "Pets"})
    p1 = s._new_preview("manual", "a", controls=[c])
    p2 = s._new_preview("manual", "b", controls=[c])
    s.apply(p1["id"])
    with pytest.raises(StudioError) as e:
        s.apply(p2["id"])
    assert e.value.status == 409
    p3 = s._new_preview("manual", "c", controls=[c])
    import studio.engine as eng
    real = eng.time.time
    monkeypatch.setattr(eng.time, "time", lambda: real() + eng.PREVIEW_TTL_S + 1)
    with pytest.raises(StudioError) as e:
        s.apply(p3["id"])
    assert e.value.status == 404


def test_preview_lifetime_is_long_enough_for_a_person():
    import studio.engine as eng
    assert eng.PREVIEW_TTL_S >= 3600


def test_undo_with_nothing_to_undo():
    with pytest.raises(StudioError):
        Studio().undo()


# ------------------------------------------------------------------ workflows
def test_manual_rejects_unknown_label():
    with pytest.raises(StudioError):
        workflows.manual_preview(Studio(), "category", "Nope", "hide")


def test_interpret_validates_labels_and_spans():
    s, ledger = Studio(), Ledger()
    prov = Scripted({"interpret": {"status": "propose", "reason": "r", "alternatives": [], "controls": [
        {"action": "hide", "strength": "standard", "intent_span": "makes me hungry", "relation": "food",
         "term_ids": ["category:Cooking", "tag:invented-label", "tag:street food"]},
        {"action": "boost", "strength": "strong", "intent_span": "words not in the request", "relation": "x",
         "term_ids": ["category:Music"]}]}})
    p = workflows.interpret_preview(s, prov, ledger, "I'm not hungry, remove what makes me hungry")
    texts = [c["text"] for c in p["controls"]]
    assert texts == ["Hide: category 'Cooking'", "Hide: tag 'street food'"]
    assert any(not c["ok"] and "invented-label" in c["check"] for c in p["checks"])
    assert any(not c["ok"] and "words not in the request" in c["check"] for c in p["checks"])
    assert p["changes"]["eligible_after"] == 36
    # the model never sees item descriptions in this workflow
    task, payload = prov.payloads[0]
    assert "description" not in json.dumps(payload["labels"]) and ledger.total() == 0.001


def test_interpret_no_match_is_not_applicable():
    s = Studio()
    prov = Scripted({"interpret": {"status": "no_match", "reason": "nothing", "alternatives": [], "controls": []}})
    p = workflows.interpret_preview(s, prov, Ledger(), "something unrelated")
    assert not p["applicable"]
    with pytest.raises(StudioError):
        s.apply(p["id"])


def _define(label="Teaches a skill"):
    return {"status": "propose", "label": label, "definition": "The video teaches a practical skill in steps.",
            "rationale": "r", "alternatives": [], "evidence": [
                {"item_id": "v125", "field": "description", "quote": "one step at a time", "reason": "steps"},
                {"item_id": "v101", "field": "description", "quote": "this text is not there", "reason": "bad"}]}


def _classify(payload):
    out = []
    for it in payload["items"]:
        if it["item_id"] == "v125":
            out.append({"item_id": "v125", "verdict": "match", "field": "description", "quote": "one step at a time", "reason": "steps"})
        elif it["item_id"] == "v113":
            out.append({"item_id": "v113", "verdict": "match", "field": "description", "quote": "four slow steps", "reason": "lesson"})
        elif it["item_id"] == "v103":   # hallucinated quote -> must not be selected
            out.append({"item_id": "v103", "verdict": "match", "field": "description", "quote": "a quote that is invented", "reason": "x"})
        elif it["item_id"] == "v140":   # omitted -> unknown
            continue
        else:
            out.append({"item_id": it["item_id"], "verdict": "unknown", "field": "none", "quote": "", "reason": "no info"})
    return {"memberships": out}


def _assess(payload):
    return {"assessments": [{"item_id": i["item_id"], "supports": i["item_id"] != "v113", "reason": "r"} for i in payload["items"]]}


def test_define_verifies_quotes_and_flags_duplicates():
    s = Studio()
    d = workflows.define_category(s, Scripted({"define": _define()}), Ledger(), "teach me skills")
    assert [e["quote_verified"] for e in d["evidence"]] == [True, False]
    d2 = workflows.define_category(s, Scripted({"define": _define("Cooking")}), Ledger(), "food")
    assert d2["duplicate"]


def test_classify_batches_quotes_and_independent_assessment():
    s, ledger = Studio(), Ledger()
    prov = Scripted({"classify": _classify, "assess": _assess})
    p = workflows.classify_category(s, prov, ledger, "Teaches a skill", "The video teaches a practical skill in steps.", "only")
    rows = {r["item_id"]: r for r in p["evidence"]}
    assert rows["v125"]["selected"]                       # match + quote found + assessor agrees
    assert not rows["v113"]["selected"]                   # assessor disagrees
    assert not rows["v103"]["selected"] and not rows["v103"]["quote_verified"]
    assert rows["v140"]["verdict"] == "unknown"           # omitted by the model
    assert p["changes"]["eligible_after"] == 1
    tasks = [t for t, _ in prov.payloads]
    assert tasks.count("classify") == 4                   # 40 items in batches of 10
    assess_payloads = [pl for t, pl in prov.payloads if t == "assess"]
    assert all("verdict" not in json.dumps(pl) for pl in assess_payloads)   # assessor never sees the verdict
    assert {i["item_id"] for pl in assess_payloads for i in pl["items"]} == {"v125", "v113"}
    s.apply(p["id"])
    assert s.custom_members("Teaches a skill") == ["v125"] and s.feed()["eligible"] == 1
    s.undo()
    assert not s.custom and s.feed()["eligible"] == 40


def test_classify_refuses_existing_label():
    with pytest.raises(StudioError):
        workflows.classify_category(Studio(), Scripted({}), Ledger(), "Cooking", "def", "hide")


def test_new_items_checks_categories_tags_and_custom_membership():
    s = Studio()
    p = workflows.classify_category(s, Scripted({"classify": _classify, "assess": _assess}), Ledger(),
                                    "Teaches a skill", "The video teaches a practical skill in steps.", "boost")
    s.apply(p["id"])
    prov = Scripted({"new-items": lambda pl: {"items": [
        {"item_id": pl["new_items"][0]["item_id"], "category": "Cooking", "category_reason": "bread",
         "tags": ["baking", "made-up-tag"], "new_categories": [
             {"label": "Teaches a skill", "verdict": "match", "quote": "step by step", "reason": "steps"}]},
        {"item_id": pl["new_items"][1]["item_id"], "category": "Invented", "category_reason": "?", "tags": [],
         "new_categories": []}]},
        "assess": lambda pl: {"assessments": [{"item_id": i["item_id"], "supports": True, "reason": "ok"} for i in pl["items"]]}})
    p = workflows.add_items_preview(s, prov, Ledger(), [
        {"title": "Sourdough day 3", "description": "A baker shows step by step how to feed a starter."},
        {"title": "Kart race", "description": "Players race karts."}])
    ev = {e["title"]: e for e in p["evidence"]}
    assert ev["Sourdough day 3"]["category"] == "Cooking" and ev["Sourdough day 3"]["tags"] == ["baking"]
    assert ev["Kart race"]["category"] == "none"
    assert any(not c["ok"] and "made-up-tag" in c["check"] for c in p["checks"])
    new_id = p["new_items"][0]["id"]
    s.apply(p["id"])
    assert new_id in s.items and new_id in s.custom_members("Teaches a skill")
    s.undo()
    assert new_id not in s.items and new_id not in s.custom_members("Teaches a skill")


def test_no_example_specific_logic_in_runtime():
    import pathlib
    root = pathlib.Path(workflows.__file__).parent
    for name in ("workflows.py", "engine.py", "server.py", "providers.py", "mock_logic.py", "static/app.js"):
        text = (root / name).read_text(encoding="utf-8").lower()
        for word in ("hungry", "hunger", "food"):
            assert word not in text, f"{name} mentions {word!r}"


def test_mock_is_literal_and_cannot_read_nonliteral_requests():
    p = workflows.interpret_preview(Studio(), MockProvider(), Ledger(), "I want peace and quiet tonight")
    assert p["proposal"]["status"] == "no_match"


# ------------------------------------------------------------------ server & key handling
def test_host_and_origin_checks():
    c, _ = client()
    assert c.get("/api/state").status_code == 200
    assert c.get("/api/state", headers={"host": "evil.example"}).status_code == 403
    assert c.post("/api/undo", headers={"origin": "http://evil.example"}).status_code == 403
    assert c.get("/", headers={"host": "127.0.0.1:9999"}).status_code == 403
    r = c.get("/api/state", headers={"host": "localhost:8765", "origin": "http://localhost:8765"})
    assert r.status_code == 200


def test_no_password_or_token_anywhere():
    c, _ = client()
    page = c.get("/").text.lower()
    assert "password" in page  # only as the masked key input type
    for word in ("unlock", "operator token", "authorize"):
        assert word not in page


def test_pasted_key_stays_in_memory_only(caplog, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    caplog.set_level(logging.DEBUG)
    c, app = client()
    r = c.post("/api/provider", json={"kind": "anthropic", "api_key": SECRET, "model": "claude-sonnet-5-5"})
    assert r.status_code == 200 and r.json()["key_source"] == "pasted"
    seen = [r.text, c.get("/api/state").text, c.get("/api/provider").text, c.get("/api/ledger").text,
            repr(app.state.provider.describe()), caplog.text]
    assert all(SECRET not in s for s in seen)
    assert not any(SECRET in p.read_text(errors="ignore") for p in tmp_path.rglob("*") if p.is_file())


def test_claude_cli_needs_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("STUDIO_ENABLE_CLAUDE_CLI", raising=False)
    c, _ = client()
    r = c.post("/api/provider", json={"kind": "claude-cli"})
    assert r.status_code == 400


def test_provider_errors_never_echo_the_key():
    def handler(request):
        return httpx2.Response(401, json={"type": "error", "error": {"type": "authentication_error", "message": f"bad key {SECRET}"}})
    p = AnthropicProvider(SECRET, http_client=httpx2.Client(transport=httpx2.MockTransport(handler)))
    with pytest.raises(ProviderError) as e:
        p.complete("interpret", "sys", {"request": "x"}, workflows.INTERPRET_SCHEMA)
    assert SECRET not in str(e.value) and "401" in str(e.value)


def _sse(events):
    return "".join(f"event: {name}\ndata: {json.dumps(data)}\n\n" for name, data in events)


def test_anthropic_request_shape_and_cost():
    seen = {}
    reply = {"status": "no_match", "reason": "none", "alternatives": [], "controls": []}

    def handler(request):
        seen["body"] = json.loads(request.content)
        seen["headers"] = dict(request.headers)
        text = json.dumps(reply)
        events = [
            ("message_start", {"type": "message_start", "message": {"id": "m1", "type": "message", "role": "assistant",
                "model": "claude-sonnet-5-5", "content": [], "stop_reason": None, "stop_sequence": None,
                "usage": {"input_tokens": 1000, "output_tokens": 1}}}),
            ("content_block_start", {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}),
            ("content_block_delta", {"type": "content_block_delta", "index": 0, "delta": {"type": "text_delta", "text": text}}),
            ("content_block_stop", {"type": "content_block_stop", "index": 0}),
            ("message_delta", {"type": "message_delta", "delta": {"stop_reason": "end_turn", "stop_sequence": None},
                               "usage": {"output_tokens": 200}}),
            ("message_stop", {"type": "message_stop"})]
        return httpx2.Response(200, headers={"content-type": "text/event-stream"}, text=_sse(events))

    p = AnthropicProvider(SECRET, model="claude-sonnet-5-5", effort="low",
                          http_client=httpx2.Client(transport=httpx2.MockTransport(handler)))
    data, call = p.complete("interpret", "system prompt", {"request": "x"}, workflows.INTERPRET_SCHEMA)
    body = seen["body"]
    assert data == reply and body["model"] == "claude-sonnet-5-5" and body["stream"] is True
    assert body["output_config"]["effort"] == "low"
    assert body["output_config"]["format"]["type"] == "json_schema"
    assert body["fallbacks"] == "default" and "server-side-fallback-2026-07-01" in seen["headers"]["anthropic-beta"]
    assert "thinking" not in body and "temperature" not in body
    assert call["cost_usd"] == round(1000 / 1e6 * 2 + 200 / 1e6 * 10, 6)


def test_openai_compatible_request_shape():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"id": "c1", "object": "chat.completion", "created": 1, "model": "gpt-5-mini",
            "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant",
                         "content": json.dumps({"memberships": []})}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}})

    p = OpenAICompatibleProvider("sk-test-openai", base_url="http://localhost:9/v1",
                                 http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    data, call = p.complete("classify", "sys", {"items": []}, workflows.MEMBERSHIP_SCHEMA)
    assert data == {"memberships": []}
    assert seen["body"]["response_format"]["json_schema"]["strict"] is True
    assert seen["auth"] == "Bearer sk-test-openai" and call["input_tokens"] == 100


def test_schemas_are_strict_everywhere():
    def walk(s):
        if s.get("type") == "object":
            assert s["additionalProperties"] is False and set(s["required"]) == set(s["properties"])
            for v in s["properties"].values():
                walk(v)
        if s.get("type") == "array":
            walk(s["items"])
    for schema in (workflows.INTERPRET_SCHEMA, workflows.DEFINE_SCHEMA, workflows.MEMBERSHIP_SCHEMA,
                   workflows.ASSESS_SCHEMA, workflows.NEW_ITEMS_SCHEMA):
        walk(schema)


def test_build_provider_unknown_and_missing_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ProviderError):
        build_provider("anthropic")
    with pytest.raises(ProviderError):
        build_provider("nope")


def test_full_http_flow_with_mock():
    c, _ = client()
    p = c.post("/api/preview/manual", json={"kind": "category", "value": "Comedy", "action": "hide"}).json()
    assert c.post("/api/apply", json={"preview_id": p["id"]}).json()["feed"]["eligible"] == 36
    assert c.post("/api/undo").json()["feed"]["eligible"] == 40
    assert c.post("/api/apply", json={"preview_id": p["id"]}).status_code == 404   # a preview is used once


# ------------------------------------------------------------------ CLI
def test_cli_mock_run_writes_results(tmp_path):
    from studio import cli
    code = cli.main(["--out", str(tmp_path)])
    folder = next(p for p in tmp_path.iterdir() if p.is_dir())
    res = json.loads((folder / "results.json").read_text(encoding="utf-8"))
    assert code == 0 and res["summary"]["failed"] == 0
    assert {r["workflow"] for r in res["results"]} >= {"manual", "interpret", "new-category", "new-videos"}
    assert (folder / "calls.csv").exists() and (folder / "summary.md").exists()


def test_cli_stops_at_budget(tmp_path):
    from studio import cli
    ledger = tmp_path / "ledger.json"
    ledger.write_text(json.dumps({"runs": [], "total_usd": 60.0}))
    code = cli.main(["--out", str(tmp_path), "--ledger", str(ledger), "--budget-usd", "50"])
    folder = next(p for p in tmp_path.iterdir() if p.is_dir())
    res = json.loads((folder / "results.json").read_text(encoding="utf-8"))
    assert code == 1 and res["summary"]["stopped"].startswith("Budget reached")


def test_validation_errors_never_echo_values():
    c, _ = client()
    r = c.post("/api/provider", json={"kind": ["x"], "api_key": SECRET, "model": {"a": SECRET}})
    assert r.status_code == 422 and SECRET not in r.text
    r = c.post("/api/provider", json={"kind": "anthropic", "api_key": {"nested": SECRET}})
    assert r.status_code == 422 and SECRET not in r.text


# ------------------------------------------------------------------ regressions from the independent review
class Racer(Scripted):
    """Applies another preview while 'the model' is answering."""
    def __init__(self, answers, studio, other_preview_id):
        super().__init__(answers)
        self.studio, self.other = studio, other_preview_id

    def complete(self, task, system, payload, schema):
        if self.other:
            self.studio.apply(self.other)
            self.other = None
        return super().complete(task, system, payload, schema)


def _items_answer(pl):
    return {"items": [{"item_id": i["item_id"], "category": "Cooking", "category_reason": "r", "tags": [],
                       "new_categories": []} for i in pl["new_items"]]}


def test_change_applied_during_a_model_call_makes_the_preview_stale():
    s = Studio()
    first = workflows.add_items_preview(s, Scripted({"new-items": _items_answer}), Ledger(),
                                        [{"title": "Pasta night", "description": "Cooking pasta."}])
    with pytest.raises(StudioError) as e:
        workflows.add_items_preview(s, Racer({"new-items": _items_answer}, s, first["id"]), Ledger(),
                                    [{"title": "Gym day", "description": "Lifting."}])
    assert e.value.status == 409
    assert any(i["title"] == "Pasta night" for i in s.items.values()) and len(s.items) == 41


def test_only_with_several_labels_of_one_preference_is_an_or():
    s = Studio()
    prov = Scripted({"interpret": {"status": "propose", "reason": "r", "alternatives": [], "controls": [
        {"action": "only", "strength": "standard", "intent_span": "cooking or travel", "relation": "x",
         "term_ids": ["category:Cooking", "category:Travel"]}]}})
    p = workflows.interpret_preview(s, prov, Ledger(), "show only cooking or travel")
    assert p["changes"]["eligible_after"] == 8


def test_budget_stops_calls_and_unknown_prices_are_counted():
    ledger = Ledger(budget_usd=0.0001)
    ledger.add({"task": "x", "model": "unknown-model", "input_tokens": 1000, "output_tokens": 1000, "cost_usd": None})
    assert ledger.total() > 0 and "upper-bound" in ledger.calls[0]["cost_source"]
    with pytest.raises(StudioError) as e:
        workflows.interpret_preview(Studio(), MockProvider(), ledger, "hide gaming")
    assert e.value.status == 402


def test_new_videos_need_the_independent_check_for_user_categories():
    s = Studio()
    p = workflows.classify_category(s, Scripted({"classify": _classify, "assess": _assess}), Ledger(),
                                    "Teaches a skill", "Teaches a practical skill in steps.", "boost")
    s.apply(p["id"])
    answer = lambda pl: {"items": [{"item_id": i["item_id"], "category": "none", "category_reason": "r", "tags": [],
                                    "new_categories": [{"label": "Teaches a skill", "verdict": "match",
                                                        "quote": i["title"], "reason": "r"}]} for i in pl["new_items"]]}
    disagree = lambda pl: {"assessments": [{"item_id": i["item_id"], "supports": False, "reason": "no"} for i in pl["items"]]}
    prov = Scripted({"new-items": answer, "assess": disagree})
    p = workflows.add_items_preview(s, prov, Ledger(), [{"title": "Knitting basics", "description": "Needles."}])
    entry = p["evidence"][0]["new_categories"][0]
    assert entry["field"] == "title" and entry["quote_verified"] and not entry["selected"]
    assert "assess" in [t for t, _ in prov.payloads]


def test_environment_openai_key_is_not_sent_to_other_servers(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-secret")
    p = build_provider("openai", base_url="http://localhost:11434/v1")
    assert p._secret == ""
    assert build_provider("openai")._secret == "sk-env-secret"
