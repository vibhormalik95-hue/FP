"""Exploratory topic preview checks; frozen E1/E2 assets are not read."""

import csv
import json

import pytest
from fastapi.testclient import TestClient

from feedctrl.api import create_app
from feedctrl import semantic_controls as topic


FIELDS = ["video_id", "manual_cover_text", "caption", "topic_tag",
          "first_level_category_id", "first_level_category_name",
          "second_level_category_id", "second_level_category_name",
          "third_level_category_id", "third_level_category_name"]


def sidecar(path, ids):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for item_id in ids:
            writer.writerow({"video_id": item_id, "manual_cover_text": "UNKNOWN",
                             "caption": "做饭, 好吃" if item_id in (1, 2) else "跑步健身",
                             "topic_tag": "[]", "first_level_category_id": 1,
                             "first_level_category_name": "美食" if item_id in (1, 2) else "运动",
                             "second_level_category_id": -124, "second_level_category_name": "UNKNOWN",
                             "third_level_category_id": -124, "third_level_category_name": "UNKNOWN"})


def test_source_text_grounding_and_three_distinct_actions(tmp_path):
    path = tmp_path / "captions.csv"
    sidecar(path, range(1, 5))
    index = topic.load_topic_index(path, {1, 2, 3, 4})
    assert index["candidate_items"] == 4
    assert len(index["sha256"]) == 64
    command = topic.manual_topic_command("boost", "美食")
    matched, evidence = topic.match_topic(index, command)
    assert matched == {1, 2}
    assert evidence[0]["source_fields"] == ["first_level_category_name"]
    ids, scores = [1, 2, 3, 4], [0.1, 0.2, 0.21, 0.22]
    cats = {item: ["category_0"] for item in ids}
    assert topic.rerank_topic(ids, scores, cats, {}, matched, "boost") == [2, 4, 3, 1]
    assert topic.rerank_topic(ids, scores, cats, {}, matched, "boost", "light") == [4, 2, 3, 1]
    assert topic.rerank_topic(ids, scores, cats, {}, matched, "reduce") == [4, 3, 2, 1]
    assert topic.rerank_topic(ids, scores, cats, {}, matched, "exclude", "none") == [4, 3]
    assert topic.rerank_topic(ids, scores, cats, {"category_0": -1}, matched, "boost") == []
    with pytest.raises(topic.ParserOperationalError, match="No candidate"):
        topic.match_topic(index, topic.manual_topic_command("boost", "宠物"))


def test_source_coverage_and_command_validation(tmp_path):
    path = tmp_path / "captions.csv"
    sidecar(path, [1, 2])
    with pytest.raises(ValueError, match="covers 2 of 3"):
        topic.load_topic_index(path, {1, 2, 3})
    with pytest.raises(topic.ParserOperationalError, match="fields conflict"):
        topic.validate_topic_command({"operation": "boost", "strength": "standard", "topic": "", "search_terms": []}, "test")
    with pytest.raises(topic.ParserOperationalError, match="invalid keys"):
        topic.validate_topic_command({"operation": "boost", "strength": "standard", "topic": "food", "search_terms": ["美食"],
                                      "matched_items": [1]}, "test")
    with pytest.raises(topic.ParserOperationalError, match="bounded strength"):
        topic.validate_topic_command({"operation": "boost", "strength": "none", "topic": "food",
                                      "search_terms": ["美食"]}, "test")
    with pytest.raises(topic.ParserOperationalError, match="cannot have"):
        topic.validate_topic_command({"operation": "exclude", "strength": "strong", "topic": "food",
                                      "search_terms": ["美食"]}, "test")
    assert topic.manual_topic_command("reduce", "美食", "strong")["adjustment"] == -0.4
    assert topic.manual_topic_command("exclude", "美食")["strength"] == "none"
    mixed = topic.validate_topic_command({"operation": "boost", "strength": "light", "topic": "food",
                                          "search_terms": ["美食", "多"]}, "ollama:test")
    assert mixed["search_terms"] == ["美食"]
    assert mixed["rejected_terms"] == ["多"]


def test_llm_output_is_validated_and_never_silently_replaced(monkeypatch):
    monkeypatch.setattr(topic, "ollama_provenance", lambda *args, **kwargs: {"digest": "test-digest"})
    monkeypatch.setattr(topic, "_request", lambda *args, **kwargs: {
        "done": True, "message": {"content": json.dumps({"operation": "boost", "strength": "light", "topic": "food",
                                                          "search_terms": ["美食", "做饭"]})}})
    result = topic.parse_topic_request("Show me more cooking videos")
    assert result == {"operation": "boost", "strength": "light", "adjustment": 0.1,
                      "topic": "food", "search_terms": ["美食", "做饭"],
                      "source": "ollama:llama3.1:8b:test-digest"}
    monkeypatch.setattr(topic, "_request", lambda *args, **kwargs: {
        "done": True, "message": {"content": json.dumps({"operation": "boost", "strength": "strong", "topic": "food",
                                                          "search_terms": []})}})
    with pytest.raises(topic.ParserOperationalError):
        topic.parse_topic_request("Show me more cooking videos")


def test_llm_repairs_one_ungrounded_term_with_model_only(monkeypatch):
    index = {"items": {i: {"fields": {"caption": "topic_zh" if i == 1 else "other"},
                           "search_text": "topic_zh" if i == 1 else "other"}
                       for i in range(1, 5)}, "candidate_items": 4}
    outputs = iter([
        {"operation": "boost", "strength": "light", "topic": "topic",
         "search_terms": ["qingdao"]},
        {"operation": "boost", "strength": "light", "topic": "topic",
         "search_terms": ["topic_zh"]}])
    requests = []
    def fake_request(base, endpoint, payload, timeout):
        requests.append(payload)
        return {"done": True, "message": {"content": json.dumps(next(outputs))}}
    monkeypatch.setattr(topic, "ollama_provenance", lambda *args, **kwargs: {"digest": "test-digest"})
    monkeypatch.setattr(topic, "_request", fake_request)
    result = topic.parse_topic_request("A little more topic", topic_index=index)
    assert len(requests) == 2
    assert "No candidate item text matches" in requests[1]["messages"][-1]["content"]
    assert result["source"].endswith(":repair1")
    assert topic.match_topic(index, result)[0] == {1}


def test_llm_repairs_one_invalid_term_then_stops(monkeypatch):
    outputs = iter([
        {"operation": "boost", "strength": "light", "topic": "topic", "search_terms": ["x"]},
        {"operation": "boost", "strength": "light", "topic": "topic", "search_terms": ["topic"]}])
    calls = []
    def fake_request(base, endpoint, payload, timeout):
        calls.append(payload)
        return {"done": True, "message": {"content": json.dumps(next(outputs))}}
    monkeypatch.setattr(topic, "ollama_provenance", lambda *args, **kwargs: {"digest": "test-digest"})
    monkeypatch.setattr(topic, "_request", fake_request)
    result = topic.parse_topic_request("A little more topic")
    assert result["search_terms"] == ["topic"]
    assert result["source"].endswith(":repair1")
    assert len(calls) == 2


def test_preview_is_opt_in_and_does_not_mutate_ae_state(tmp_path):
    path = tmp_path / "captions.csv"
    sidecar(path, range(1, 37))
    with TestClient(create_app(fixture=True, semantic_path=path)) as client:
        session = client.post("/api/session", json={}).json()["session_id"]
        headers = {"X-Session-ID": session}
        before = client.get("/api/feed?user_id=1&condition=C", headers=headers).json()
        response = client.post("/api/topic/preview", headers=headers,
                               json={"user_id": 1, "text": "美食", "operation": "exclude",
                                     "backend": "manual", "condition": "C"})
        assert response.status_code == 200, response.text
        preview = response.json()
        assert preview["applied"] is True and preview["candidate_matches"] == 2
        assert preview["top_k_match_count"] == 0 and preview["fill_rate"] == 1
        assert preview["available_items"] == 34
        assert preview["command"]["source"] == "manual_literal"
        assert preview["command"]["strength"] == "none"
        assert client.get("/api/feed?user_id=1&condition=C", headers=headers).json() == before


def test_llm_failure_is_visible_and_does_not_change_existing_feed(tmp_path, monkeypatch):
    path = tmp_path / "captions.csv"
    sidecar(path, range(1, 37))
    def unavailable(*args, **kwargs):
        raise topic.ParserOperationalError("Local model unavailable")
    monkeypatch.setattr("feedctrl.api.parse_topic_request", unavailable)
    with TestClient(create_app(fixture=True, semantic_path=path)) as client:
        headers = {"X-Session-ID": client.post("/api/session", json={}).json()["session_id"]}
        before = client.get("/api/feed?user_id=1&condition=E", headers=headers).json()
        response = client.post("/api/topic/preview", headers=headers,
                               json={"user_id": 1, "text": "Show me more cooking videos",
                                     "backend": "ollama", "condition": "E"})
        assert response.status_code == 502
        assert "previous A-E state is preserved" in response.json()["detail"]
        assert client.get("/api/feed?user_id=1&condition=E", headers=headers).json() == before


def test_ungrounded_model_topic_returns_no_action_not_server_error(tmp_path, monkeypatch):
    path = tmp_path / "captions.csv"
    sidecar(path, range(1, 37))
    def ungrounded(*args, **kwargs):
        raise topic.TopicGroundingError("No candidate item text matches the proposed topic; no feed change")
    monkeypatch.setattr("feedctrl.api.parse_topic_request", ungrounded)
    with TestClient(create_app(fixture=True, semantic_path=path)) as client:
        headers = {"X-Session-ID": client.post("/api/session", json={}).json()["session_id"]}
        before = client.get("/api/feed?user_id=1&condition=C", headers=headers).json()
        response = client.post("/api/topic/preview", headers=headers,
                               json={"user_id": 1, "text": "Show me more absent-topic videos",
                                     "backend": "ollama", "condition": "C"})
        assert response.status_code == 200
        assert response.json()["applied"] is False
        assert "No topic preview was applied" in response.json()["message"]
        assert client.get("/api/feed?user_id=1&condition=C", headers=headers).json() == before


def test_mocked_english_llm_request_reaches_source_text_preview(tmp_path, monkeypatch):
    path = tmp_path / "captions.csv"
    sidecar(path, range(1, 37))
    monkeypatch.setattr("feedctrl.api.parse_topic_request", lambda text, **kwargs:
                        topic.validate_topic_command({"operation": "boost", "strength": "strong", "topic": "cooking",
                                                      "search_terms": ["美食", "做饭"]},
                                                     "ollama:mock-digest"))
    with TestClient(create_app(fixture=True, semantic_path=path)) as client:
        headers = {"X-Session-ID": client.post("/api/session", json={}).json()["session_id"]}
        response = client.post("/api/topic/preview", headers=headers,
                               json={"user_id": 1, "text": "Show me more cooking videos",
                                     "backend": "ollama", "condition": "C"})
        assert response.status_code == 200, response.text
        assert response.json()["command"]["source"] == "ollama:mock-digest"
        assert response.json()["command"]["adjustment"] == 0.4
        assert response.json()["candidate_matches"] == 2


def test_llm_grounding_repair_reaches_api_and_preserves_ae(tmp_path, monkeypatch):
    path = tmp_path / "captions.csv"
    sidecar(path, range(1, 37))
    outputs = iter([
        {"operation": "boost", "strength": "light", "topic": "cooking",
         "search_terms": ["unmatched"]},
        {"operation": "boost", "strength": "light", "topic": "cooking",
         "search_terms": ["美食", "多"]}])
    monkeypatch.setattr(topic, "ollama_provenance", lambda *args, **kwargs: {"digest": "test-digest"})
    monkeypatch.setattr(topic, "_request", lambda *args, **kwargs: {
        "done": True, "message": {"content": json.dumps(next(outputs))}})
    with TestClient(create_app(fixture=True, semantic_path=path)) as client:
        headers = {"X-Session-ID": client.post("/api/session", json={}).json()["session_id"]}
        before = client.get("/api/feed?user_id=1&condition=C", headers=headers).json()
        response = client.post("/api/topic/preview", headers=headers,
                               json={"user_id": 1, "text": "A little more cooking",
                                     "backend": "ollama", "condition": "C"})
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["applied"] is True and result["candidate_matches"] == 2
        assert result["command"]["strength"] == "light"
        assert result["command"]["rejected_terms"] == ["多"]
        assert result["command"]["source"].endswith(":repair1")
        assert client.get("/api/feed?user_id=1&condition=C", headers=headers).json() == before
