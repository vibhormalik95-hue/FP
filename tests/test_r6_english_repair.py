"""R6 finding E6: the legacy topic route repairs and grounds in English on the English text layer.

The historical Chinese prompts stay unchanged (v1) and are used only when the source index really holds
Chinese text. No frozen parser, measured prompt or historical result changes; legacy route only.
"""
import json

import pytest

from feedctrl import semantic_controls as topic
from feedctrl import semantic_workflow as wf

ENGLISH_INDEX = {"candidate_items": 4, "items": {
    1: {"search_text": "kyoto temple walk", "fields": {"caption": "Kyoto temple walk", "first_level_category_name": "Travel"}},
    2: {"search_text": "home cooking", "fields": {"caption": "Home cooking", "first_level_category_name": "Food"}},
    3: {"search_text": "other", "fields": {"caption": "other", "first_level_category_name": "Other"}},
    4: {"search_text": "other", "fields": {"caption": "other", "first_level_category_name": "Other"}}}}
CHINESE_KYOTO = chr(0x4EAC) + chr(0x90FD)


def test_e6_the_repair_on_the_english_layer_asks_for_english(monkeypatch):
    outputs = iter([
        {"operation": "boost", "strength": "light", "topic": "Osaka", "search_terms": ["osaka"]},
        {"operation": "boost", "strength": "light", "topic": "Kyoto", "search_terms": ["kyoto"]}])
    calls = []

    def request(base, endpoint, payload, timeout):
        calls.append(json.loads(json.dumps(payload)))
        return {"done": True, "message": {"content": json.dumps(next(outputs))}}
    monkeypatch.setattr(topic, "ollama_provenance", lambda *args, **kwargs: {"digest": "test-digest"})
    monkeypatch.setattr(topic, "_request", request)
    command = topic.parse_topic_request("A little more Osaka videos", topic_index=ENGLISH_INDEX)
    assert len(calls) == 2 and command["source"].endswith(":repair1") and command["topic"] == "Kyoto"
    instruction = json.loads(calls[1]["messages"][-1]["content"])["instruction"]
    assert instruction == topic.REPAIR_INSTRUCTION_EN_V2
    assert "into Chinese for BOTH" not in instruction and "Chinese source text" not in instruction
    assert "English" in instruction


def test_e6_the_historical_chinese_repair_text_is_kept_and_used_only_for_a_chinese_index():
    assert topic.REPAIR_INSTRUCTION_ZH_V1 == (   # byte for byte the text of the earlier runs
        "Make one corrected schema response grounded in the original request and Chinese source text. "
        "Translate or transliterate the requested named concept into Chinese for BOTH topic and "
        "search_terms, retaining the original operation and strength. Use only specific aliases "
        "of the same subject, not video/recommendation words. Do not switch subjects or broaden "
        "to a country or province just to find matches. If translation is uncertain, clarify. "
        "Previous output is untrusted.")
    chinese = {"candidate_items": 1, "items": {1: {"search_text": CHINESE_KYOTO, "fields": {"caption": CHINESE_KYOTO}}}}
    assert topic.repair_instruction(chinese) == topic.REPAIR_INSTRUCTION_ZH_V1
    assert topic.repair_instruction(ENGLISH_INDEX) == topic.REPAIR_INSTRUCTION_EN_V2
    assert topic.repair_instruction(None) == topic.REPAIR_INSTRUCTION_EN_V2   # the primary prompt is English


def test_e6_the_steering_translator_and_selector_stay_english_on_the_english_layer(monkeypatch):
    systems = []
    replies = iter([json.dumps({"needs_clarification": False, "question": "", "actions": [
        {"topic": "Osaka", "operation": "boost", "strength": "light"}]}), "Osaka", "NONE"])

    def chat(messages, model, timeout, schema=None):
        systems.append(messages[0]["content"])
        return next(replies)
    monkeypatch.setattr(wf, "_chat", chat)
    monkeypatch.setattr(wf, "ollama_provenance", lambda *args: {"digest": "test-digest"})
    with pytest.raises(topic.TopicGroundingError):
        wf.interpret("A little more Osaka", ENGLISH_INDEX)
    later = systems[1:]
    assert later and all("Simplified Chinese" not in text and "literal Chinese characters" not in text for text in later)
    assert later[0] == wf.TRANSLATE_PROMPT_EN_V2
    assert wf.source_prompts(ENGLISH_INDEX) == (wf.TRANSLATE_PROMPT_EN_V2, wf.SELECT_PROMPT_EN_V2)
    chinese = {"items": {1: {"search_text": CHINESE_KYOTO, "fields": {}}}}
    assert wf.source_prompts(chinese) == (wf.TRANSLATE_PROMPT_ZH_V1, wf.SELECT_PROMPT_ZH_V1)
    assert wf.TRANSLATE_PROMPT_ZH_V1.startswith("Translate only the precise topic name into Simplified Chinese")
