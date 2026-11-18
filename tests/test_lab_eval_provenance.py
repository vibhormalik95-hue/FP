"""Regression tests for r6 findings C1 (resume provenance), C2a (control grouping) and C3a (derived narration)
in scripts/lab_eval.py. Each test fails on the code of c50ac96."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("lab_eval_r6", ROOT / "scripts" / "lab_eval.py")
le = importlib.util.module_from_spec(spec)
spec.loader.exec_module(le)


def args(**kw):
    base = dict(name="m", provider="openai", model="gpt-5-mini", effort="low", text="original",
                resume_across_code_change=False)
    base.update(kw)
    return SimpleNamespace(**base)


def write_run(tmp_path, meta, rows=1):
    pred, meta_path = tmp_path / "m.jsonl", tmp_path / "m.meta.json"
    pred.write_text("".join(json.dumps({"case_id": f"C{i}"}) + "\n" for i in range(rows)), encoding="utf-8")
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    return pred, meta_path, {f"C{i}": {} for i in range(rows)}


OLD = {"name": "m", "provider": "openai", "model": "gpt-5-mini", "effort": "low", "code_commit": "aaaa111",
       "set_sha256": "S1", "started_utc": "2026-11-17T00:00:00+00:00"}


def attempt(commit="aaaa111"):
    return {"code_commit": commit, "started_utc": "2026-11-18T00:00:00+00:00", "cases_already_done": 1}


@pytest.mark.parametrize("change", [dict(model="gpt-5"), dict(provider="ollama"), dict(effort="minimal"), dict(text="english")])
def test_resume_refuses_another_identity(tmp_path, change):
    pred, meta_path, done = write_run(tmp_path, OLD)
    with pytest.raises(SystemExit, match="Refusing to resume"):
        le.resume_meta(meta_path, pred, done, args(**change), "S1", attempt())


def test_resume_refuses_another_set(tmp_path):
    pred, meta_path, done = write_run(tmp_path, OLD)
    with pytest.raises(SystemExit, match="set_sha256"):
        le.resume_meta(meta_path, pred, done, args(), "S2", attempt())


def test_resume_refuses_a_code_change_unless_asked_and_then_keeps_every_attempt(tmp_path):
    pred, meta_path, done = write_run(tmp_path, OLD)
    with pytest.raises(SystemExit, match="earlier attempts ran at"):
        le.resume_meta(meta_path, pred, done, args(), "S1", attempt("bbbb222"))
    meta = le.resume_meta(meta_path, pred, done, args(resume_across_code_change=True), "S1", attempt("bbbb222"))
    assert [a["code_commit"] for a in meta["attempts"]] == ["aaaa111", "bbbb222"]
    assert meta["code_commit"] == "mixed: aaaa111, bbbb222" and meta["started_utc"] == OLD["started_utc"]


def test_resume_without_a_manifest_is_refused(tmp_path):
    pred, meta_path, done = write_run(tmp_path, OLD)
    meta_path.unlink()
    with pytest.raises(SystemExit, match="no manifest"):
        le.resume_meta(meta_path, pred, done, args(), "S1", attempt())


def test_same_identity_and_commit_resumes(tmp_path):
    pred, meta_path, done = write_run(tmp_path, OLD)
    meta = le.resume_meta(meta_path, pred, done, args(), "S1", attempt())
    assert meta["code_commit"] == "aaaa111" and len(meta["attempts"]) == 2


def test_stored_groups_follow_the_app_and_rows_without_groups_keep_v1():
    from feedctrl.lab import apply_controls
    items = {1: {"kuairec_categories": ["A"], "tags": []}, 2: {"kuairec_categories": ["B"], "tags": []},
             3: {"kuairec_categories": ["A", "B"], "tags": []}}
    scores = {1: 0.9, 2: 0.8, 3: 0.7}
    v1 = [{"action": "only", "term_id": "category:A"}, {"action": "only", "term_id": "category:B"}]
    app = [{**v1[0], "control_group": "0"}, {**v1[1], "control_group": "1"}]
    union = [r[0] for r in apply_controls(scores, items, le.eval_controls(v1), {})]
    inter = [r[0] for r in apply_controls(scores, items, le.eval_controls(app), {})]
    assert sorted(union) == [1, 2, 3]       # frozen rows: one group per case, as scored on 17 Nov
    assert inter == [3]                     # stored app groups: separate 'only' controls intersect, as in the app


def test_grouping_unknown_lists_only_ambiguous_cases():
    preds = {"m": {"NL06": {"controls": [{"action": "only", "term_id": "a"}, {"action": "only", "term_id": "b"}]},
                   "NL07": {"controls": [{"action": "only", "term_id": "a"}]},
                   "NL08": {"controls": [{"action": "only", "term_id": "a", "control_group": "0"},
                                         {"action": "only", "term_id": "b", "control_group": "1"}]}}}
    assert le.find_grouping_unknown(preds) == {"m": ["NL06"]}


def test_noninferiority_sentence_is_derived_from_the_table():
    rows = [["gpt-5", -0.01, -0.02, -0.001, False, True, 0.0], ["claude", -0.01, -0.02, -0.001, False, True, 0.0]]
    assert "absolute margin, but not within the relative" in le.noninf_sentence(rows, ["gpt-5", "claude"])
    rows[0][5] = False
    s = le.noninf_sentence(rows, ["gpt-5", "claude"])
    assert "absolute margin for claude" in s and "relative ten percent margin for no frontier model" in s
