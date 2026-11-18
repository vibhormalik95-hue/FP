"""R6 findings E2a-E2d: Lab scope of added items, the whole-tag quote rule, and honest language wording."""
from __future__ import annotations

import inspect

import pytest

from feedctrl import lab_workflows as wf
from feedctrl.kuairec_catalog import build_catalog, item_record, label_vocabulary
from feedctrl.lab import KuaiRecLab

CJK_PET = chr(0x5BA0) + chr(0x7269)          # two CJK ideographs ("pet")


def _lab():
    rows = {
        1: {"caption": "alpha river walk", "manual_cover_text": "alpha", "topic_tag": "[river, walk]",
            "first_level_category_name": "outdoors"},
        2: {"caption": "beta kitchen story", "manual_cover_text": "", "topic_tag": "[]",
            "first_level_category_name": "home"},
        3: {"caption": "gamma river boat", "manual_cover_text": "", "topic_tag": "[river]",
            "first_level_category_name": "outdoors"},
    }
    processed = {"items": [{"item_id": i, "categories": [f"category_{i % 2}"]} for i in rows]}
    scores = {1: 0.9, 2: 0.8, 3: 0.7}
    return KuaiRecLab(build_catalog(processed, rows), scorer=lambda user: dict(scores),
                      users={7: {"train": [], "request_history": []}})


def _added(item_id, caption, tags):
    record = item_record(item_id, [], {"caption": caption, "manual_cover_text": caption.split()[0],
                                       "topic_tag": "[" + ", ".join(tags) + "]"})
    return {**record, "origin": "added"}


# ---------------------------------------------------------------- E2a
def test_e2a_an_added_item_hidden_by_a_control_is_not_classified():
    lab = _lab()
    lab.user(7).added[9_000_001] = _added(9_000_001, "river picnic", ["river"])
    lab.user(7).added[9_000_002] = _added(9_000_002, "kitchen bread", ["bread"])
    preview = wf.manual_preview(lab, 7, "tag", "river", "hide")
    lab.apply(7, preview["preview_id"])                     # hides 1, 3 and the added river item
    ids = [item["item_id"] for item in lab.scope(7, 1)]
    # The hidden added item is not classified (the documented rule); the kept added item is included
    # although it is outside the top ``size``.
    assert ids == [2, 9_000_002]
    lab.undo(7)
    assert 9_000_001 in [item["item_id"] for item in lab.scope(7, 1)]   # visible again after Undo


# ---------------------------------------------------------------- E2b
def test_e2b_a_whole_tag_shorter_than_three_characters_counts():
    item = {"title": "Set list", "caption": "A DJ set at night", "tags": ["DJ", "night life"]}
    assert wf.quote_found(item, "tags", "DJ") and wf.quote_found(item, "tags", "#dj")
    # The three-character minimum still holds outside whole tags, and a part of a tag is not a tag.
    assert not wf.quote_found(item, "description", "DJ")
    assert not wf.quote_found(item, "tags", "D") and not wf.quote_found(item, "tags", "night")
    assert not wf.quote_found(item, "tags", "") and not wf.quote_found(item, "tags", " . ")


# ---------------------------------------------------------------- E2c
def test_e2c_label_names_are_not_claimed_to_be_original_chinese():
    doc = inspect.getdoc(label_vocabulary)
    assert "original Chinese text;" not in doc and "English machine translation" in doc
    processed = {"items": [{"item_id": 1, "categories": ["category_0"]}]}
    english = build_catalog(processed, {1: {"caption": "a cat naps", "first_level_category_name": "Pets",
                                            "topic_tag": "[cats]"}})
    values = {term["value"] for term in label_vocabulary(english)}
    assert {"Pets", "cats"} <= values                      # copied unchanged from the English rows


# ---------------------------------------------------------------- E2d
def test_e2d_the_missing_asset_message_names_the_english_layer(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from feedctrl.lab_routes import mount_lab
    app = FastAPI()
    app.state.demo = type("Demo", (), {"fixture": True, "users": {}, "model": None})()
    mount_lab(app, lab=None, results_dir=tmp_path)
    assert app.state.lab is None
    with TestClient(app) as client:
        reply = client.get("/api/lab/labels?user_id=7")
    assert reply.status_code == 503
    detail = reply.json()["detail"]
    assert "data/kuairec_text_en-v1.json" in detail and "English text layer" in detail and "caption table" not in detail


def test_e2d_english_only_also_cleans_dict_keys_and_says_what_it_covers():
    from feedctrl.lab_routes import NON_ENGLISH, english_only
    out, n = english_only({"custom": {"Pets " + CJK_PET: {"definition": "ok"}, "Pets " + chr(0x732B): {}}, "notes": []})
    assert n == 2 and all(CJK_PET not in key and chr(0x732B) not in key for key in out["custom"])
    assert sorted(out["custom"]) == ["Pets " + NON_ENGLISH, "Pets " + NON_ENGLISH + " (2)"]   # no key is lost
    doc = inspect.getdoc(english_only)
    assert "dict keys" in doc and "not a general English-language guarantee" in doc
    # Stated precisely: kana and Hangul are outside the CJK ranges and pass unchanged.
    kana_hangul = chr(0x3072) + chr(0xD55C)
    assert english_only({"a": kana_hangul}) == ({"a": kana_hangul}, 0)
