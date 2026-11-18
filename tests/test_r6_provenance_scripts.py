"""R6 findings C3b, C6 and C7: scripts that must not overwrite, misreport or mislabel records.

No model call is made: every provider here is a local fake, and the frozen evidence is only read.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

from feedctrl.llm_providers import Provider, ProviderError  # noqa: E402


# ---------------------------------------------------------------------------------------------- C6

def test_c6_english_eval_set_refuses_an_existing_output_before_any_call(tmp_path, monkeypatch):
    import build_english_eval_set as eval_set
    monkeypatch.setattr(eval_set, "build_provider", lambda *a, **k: pytest.fail("no model call may start"))
    for name in ("cases.en.json", "FROZEN-EN.json"):
        folder = tmp_path / name.split(".")[0]
        folder.mkdir()
        (folder / name).write_text("frozen bytes", encoding="utf-8")
        with pytest.raises(SystemExit) as stopped:
            eval_set.main(["--out", str(folder)])
        assert "never" in str(stopped.value) and (folder / name).read_text(encoding="utf-8") == "frozen bytes"
    # The frozen folder itself is refused, and no output path means no run at all.
    frozen = ROOT / "docs/evidence/lab-eval-set-20261117-en"
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in frozen.iterdir() if p.is_file()}
    with pytest.raises(SystemExit):
        eval_set.main(["--out", str(frozen)])
    with pytest.raises(SystemExit):
        eval_set.main([])
    assert before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in frozen.iterdir() if p.is_file()}


def test_c6_the_writer_is_exclusive(tmp_path):
    import build_english_eval_set as eval_set
    target = tmp_path / "cases.en.json"
    eval_set.write_new(target, "first")
    with pytest.raises(FileExistsError):
        eval_set.write_new(target, "second")
    assert target.read_text(encoding="utf-8") == "first"


# ---------------------------------------------------------------------------------------------- C7

class Flaky(Provider):
    """Answers a valid reset to every third request, and fails the other two."""
    name = "fake"

    def __init__(self):
        super().__init__("fake-model")
        self.n = 0

    def complete(self, task, system, payload, schema):
        self.n += 1
        if self.n % 3:
            raise ProviderError("timeout")
        return ({"operation": "reset", "category": None, "strength": 0.0},
                {"task": task, "latency_s": 5.0, "cost_usd": 0.001, "provider": "fake", "model": "fake-model"})


def test_c7_failed_calls_do_not_add_zero_latency_and_make_the_cost_unknown(tmp_path, monkeypatch):
    import parser_rerun
    monkeypatch.setattr(parser_rerun, "ROOT", tmp_path)
    bank = (ROOT / "data/parser_test.jsonl").read_bytes()
    (tmp_path / "data").mkdir()
    (tmp_path / "data/parser_test.jsonl").write_bytes(bank)
    monkeypatch.setattr(parser_rerun, "build_provider", lambda *a, **k: Flaky())
    assert parser_rerun.main(["--provider", "fake", "--model", "fake-model", "--out", "rerun"]) == 0
    summary = json.loads((tmp_path / "rerun/fake-model/summary.json").read_text(encoding="utf-8"))
    assert summary["failed_provider_calls"] == 67
    assert summary["median_latency_s"] == 5.0          # old code: 67 zeros and 33 fives gave a median of 0
    assert summary["latency_calls_measured"] == 33
    assert summary["cost_usd"] is None and summary["cost_usd_of_completed_calls"] == pytest.approx(0.033)


def test_c7_median_is_not_pulled_to_zero_by_failures():
    import parser_rerun
    rows = [{"latency_s": None, "provider_call_failed": True}] * 3 + [{"latency_s": 2.0}, {"latency_s": 4.0}]
    out = parser_rerun.latency_and_cost(rows, 0.01)
    assert out["median_latency_s"] == 4.0 and out["failed_provider_calls"] == 3 and out["cost_usd"] is None
    # The old expression put a 0 for each failure: the median of [0, 0, 0, 2, 4] is 0.
    assert sorted(r.get("latency_s") or 0 for r in rows)[len(rows) // 2] == 0
