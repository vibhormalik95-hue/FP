"""The app works on the English text layer only (machine translation of KuaiRec, CC BY-SA 4.0)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from feedctrl import kuairec_catalog as kc  # noqa: E402
from feedctrl import lab_workflows as wf  # noqa: E402

C = chr
CJK = re.compile("[" + C(0x3000) + "-" + C(0x303F) + C(0x3400) + "-" + C(0x9FFF) + C(0xFF00) + "-" + C(0xFFEF) + "]")


def layer(tmp_path, items, label=kc.ENGLISH_LABEL):
    path = tmp_path / "layer.json"
    path.write_text(json.dumps({"label": label, "version": "v1", "items": items}), encoding="utf-8")
    return path


ITEMS = {"1": {"manual_cover_text": "Weekend hike", "caption": "A steep trail #Hiking",
               "topic_tag": ["Hiking", "Mountains; rivers"], "first_level_category_name": "Travel",
               "second_level_category_name": "Outdoor", "third_level_category_name": ""},
         "2": {"manual_cover_text": "", "caption": "", "topic_tag": [], "first_level_category_name": "Pets",
               "second_level_category_name": "", "third_level_category_name": ""}}
PROCESSED = {"items": [{"item_id": 1, "categories": ["category_1"]}, {"item_id": 2, "categories": ["category_2"]}]}


def test_layer_must_carry_the_machine_translation_label(tmp_path):
    with pytest.raises(ValueError, match="machine translation of KuaiRec"):
        kc.read_english_layer(layer(tmp_path, ITEMS, label="something else"))
    rows, prov = kc.read_english_layer(layer(tmp_path, ITEMS))
    assert prov["label"] == "machine translation of KuaiRec (CC BY-SA 4.0)" and len(prov["sha256"]) == 64
    assert rows[1]["caption"] == "A steep trail #Hiking"


def test_catalog_and_vocabulary_from_the_layer_are_english(tmp_path):
    rows, _ = kc.read_english_layer(layer(tmp_path, ITEMS))
    catalog = kc.build_catalog(PROCESSED, rows)
    assert catalog[1]["tags"] == ["Hiking", "Mountains; rivers"]
    assert catalog[1]["kuairec_categories"] == ["Travel", "Outdoor"]
    terms = {t["term_id"] for t in kc.label_vocabulary(catalog)}
    assert {"category:Travel", "category:Pets", "tag:Hiking"} <= terms
    assert not any("gloss_en" in t for t in kc.label_vocabulary(catalog))


def test_english_csv_round_trips_for_the_study_view(tmp_path):
    rows, _ = kc.read_english_layer(layer(tmp_path, ITEMS))
    csv_path = kc.write_english_csv(rows, tmp_path / "en.csv")
    back, _ = kc.read_caption_table(csv_path)
    assert kc._tags(back[1]["topic_tag"]) == ["Hiking", "Mountains; rivers"]
    assert back[2]["first_level_category_name"] == "Pets"


def test_prompts_and_quote_rules_are_english_only():
    for prompt in (wf.INTERPRET_PROMPT, wf.DEFINE_PROMPT, wf.MEMBERSHIP_PROMPT, wf.ASSESS_PROMPT, wf.NEW_ITEMS_PROMPT):
        assert not CJK.search(prompt)
        assert "gloss" not in prompt
    assert "gloss" not in wf.FIELDS
    item = {"title": "Weekend hike", "caption": "A steep trail", "tags": ["Hiking"]}
    assert wf.quote_found(item, "description", "steep trail")
    assert not wf.quote_found(item, "description", "a")          # too short to prove anything
    assert wf.quote_found(item, "tags", "hiking") and not wf.quote_found(item, "tags", "hik")
    assert not wf.quote_found(item, "gloss", "Weekend hike")      # there is no translation field any more


def test_the_app_needs_the_english_layer_not_the_chinese_table():
    import scripts.run_app as run_app  # noqa: PLC0415
    assert "data/kuairec_text_en-v1.json" in run_app.NEEDED.values()
    assert not any("kuairec_caption_category" in v for v in run_app.NEEDED.values())


def test_results_are_labelled_by_the_text_they_were_measured_on(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from feedctrl import lab_routes

    run = tmp_path / "lab-eval" / "20261117-main"
    run.mkdir(parents=True)
    (run / "summary.json").write_text(json.dumps({"title": "T", "tables": []}), encoding="utf-8")
    app = FastAPI()
    app.state.demo = type("D", (), {"fixture": True})()
    lab_routes.mount_lab(app, results_dir=tmp_path / "lab-eval", lab=object())
    runs = TestClient(app).get("/api/lab/results").json()["runs"]
    assert runs[0]["text_label"] == lab_routes.ORIGINAL_TEXT_PENDING
    assert "English-input re-run pending" in runs[0]["text_label"]
    new = tmp_path / "lab-eval" / "20261120-english"
    new.mkdir()
    (new / "summary.json").write_text(json.dumps({"title": "E", "input_text": "english", "tables": []}), encoding="utf-8")
    runs = {r["run"]: r for r in TestClient(app).get("/api/lab/results").json()["runs"]}
    assert runs["20261120-english"]["text_label"] == lab_routes.ENGLISH_TEXT_RUN
    assert runs["20261117-main"]["text_label"] == lab_routes.ORIGINAL_TEXT_PRIOR


def test_the_published_english_layer_has_no_cjk_when_present():
    path = ROOT / "data" / "kuairec_text_en-v1.json"
    if not path.is_file():
        pytest.skip("the English layer is fetched by fetch-assets; not present")
    text = path.read_text(encoding="utf-8")
    assert not CJK.search(text)
    assert json.loads(text)["label"] == kc.ENGLISH_LABEL
