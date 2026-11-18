"""Regression tests for the trustworthy gates of scripts/run_all_tests.py (r6 findings D1a and D2a).

The old gate passed a pytest step whenever no FAILED line was parsed, whatever pytest's exit code; it checked
Undo by the eligible count only; it accepted any HTTP 200 from interpret; and a new-category step with no selected
member passed because all() of an empty list is true. Each test below fails on that old logic.
"""
import copy
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("run_all_tests", ROOT / "scripts" / "run_all_tests.py")
rat = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rat)

FROZEN = next(iter(rat.FROZEN_BY_DESIGN))


# ------------------------------------------------------------------ D1a: pytest exit code
def test_exit_1_without_a_parsed_failure_fails():
    assert not rat.pytest_verdict(1, "garbled output\n")["ok"]


def test_interrupted_or_empty_runs_fail():
    assert not rat.pytest_verdict(2, "!!! Interrupted: 4 errors during collection !!!\n4 errors in 0.5s\n")["ok"]
    assert not rat.pytest_verdict(5, "no tests ran in 0.01s\n")["ok"]
    assert not rat.pytest_verdict(4, "ERROR: usage\n")["ok"]


def test_only_the_frozen_failure_passes_and_any_other_fails():
    ok = rat.pytest_verdict(1, f"FAILED {FROZEN} - boom\n1 failed, 10 passed in 1s\n")
    assert ok["ok"] and ok["failed_frozen_by_design"] == [FROZEN]
    assert not rat.pytest_verdict(1, f"FAILED {FROZEN} - x\nFAILED tests/test_x.py::test_y - y\n2 failed, 9 passed\n")["ok"]
    # A collection error that is not listed as a FAILED line must still fail the step.
    assert not rat.pytest_verdict(1, f"FAILED {FROZEN} - x\n1 failed, 1 error, 9 passed\n")["ok"]


def test_clean_run_passes():
    assert rat.pytest_verdict(0, "10 passed, 2 skipped in 1.0s\n")["ok"]


# ------------------------------------------------------------------ D2a: exact Undo / Reset, semantic outcomes
class FakeLab:
    """A minimal in-memory Lab API: 30 items; a hide control removes item 25 (outside the shown top ten), so only
    the full ranking shows the change. ``broken_undo`` leaves the control applied."""

    def __init__(self, broken_undo=False, interpret_controls=1, select=1):
        self.controls, self.history, self.broken_undo = [], [], broken_undo
        self.interpret_controls, self.select, self.custom = interpret_controls, select, {}

    def ranked(self):
        ids = list(range(1, 31))
        if self.controls:
            ids = [i for i in ids if i != 25]
            ids[12], ids[13] = ids[13], ids[12]
        if self.custom:
            ids = [3] + [i for i in ids if i != 3]
        return ids

    def state(self):
        r = self.ranked()
        return {"controls": copy.deepcopy(self.controls), "custom": copy.deepcopy(self.custom), "added": [],
                "feed": {"eligible": len(r), "catalogue": 30, "ranked_ids": r,
                         "items": [{"item_id": i, "score": 1 - n / 100, "kuairec_categories": [], "tags": []}
                                   for n, i in enumerate(r[:10])]}}

    def __call__(self, base, path, body=None, timeout=0):
        if path.startswith("/api/lab/state"):
            return 200, self.state(), 0
        if path == "/api/lab/apply":
            self.history.append((copy.deepcopy(self.controls), copy.deepcopy(self.custom)))
            if body["preview_id"] == "cat":
                self.custom = {"c1": {"label": "x", "members": [3]}}
            else:
                self.controls.append({"action": "hide", "target": {"kind": "category", "value": "Z"}, "group": "g"})
            return 200, {"feed": {"eligible": 29}}, 0
        if path == "/api/lab/undo":
            if not self.broken_undo:
                self.controls, self.custom = self.history.pop()
            return 200, self.state(), 0
        if path == "/api/lab/reset":
            self.controls, self.custom = [], {}
            return 200, self.state(), 0
        if path == "/api/lab/manual":
            return 200, {"preview_id": "m", "applicable": True, "changes": {"eligible_before": 30}}, 0
        if path == "/api/lab/interpret":
            n = self.interpret_controls if "abstain" not in body["request"] else 0
            return 200, {"preview_id": "i", "applicable": bool(n), "proposal": {"status": "propose" if n else "no_match"},
                         "controls": [{"text": "Hide Z"}] * n}, 0
        if path == "/api/lab/define":
            return 200, {"status": "propose", "label": "x", "definition": "d"}, 0
        if path == "/api/lab/classify":
            ev = [{"item_id": 3, "selected": bool(self.select), "verdict": "match", "quote_verified": True,
                   "assessment": {"supports": True}}]
            return 200, {"preview_id": "cat", "applicable": bool(self.select), "evidence": ev}, 0
        if path == "/api/lab/new-items":
            return 200, {"preview_id": "n", "applicable": False, "evidence": [{}]}, 0
        raise AssertionError(path)


EXAMPLES = {"manual": [{"domain": "d", "kind": "category", "value": "Z", "action": "hide"}],
            "interpret": [{"domain": "d", "kind": "literal", "request": "hide Z"}],
            "interpret_abstain": [{"domain": "none", "request": "abstain please"}],
            "new_category": [{"domain": "d", "description": "x"}], "new_items": []}


def run(monkeypatch, fake, provider="mock"):
    monkeypatch.setattr(rat, "call", fake)
    rows, _ = rat.workflows("http://fake", 1, copy.deepcopy(EXAMPLES), provider=provider)
    return {r["workflow"]: r for r in rows}


def test_a_change_outside_the_shown_top_ten_counts_and_an_exact_undo_passes(monkeypatch):
    rows = run(monkeypatch, FakeLab())
    assert rows["manual"]["ok"], rows["manual"]["why_not_ok"]
    assert all(r["ok"] for r in rows.values()), [(k, r["why_not_ok"]) for k, r in rows.items() if not r["ok"]]


def test_an_undo_that_keeps_the_control_fails(monkeypatch):
    rows = run(monkeypatch, FakeLab(broken_undo=True))
    assert not rows["manual"]["ok"] and "Undo" in rows["manual"]["why_not_ok"]


def test_a_literal_request_without_a_control_fails(monkeypatch):
    rows = run(monkeypatch, FakeLab(interpret_controls=0))
    assert not rows["interpret (literal, expect propose)"]["ok"]


def test_an_abstain_example_with_a_control_fails(monkeypatch):
    fake = FakeLab()
    orig = fake.__call__

    def always(base, path, body=None, timeout=0):
        if path == "/api/lab/interpret":
            return 200, {"preview_id": "i", "applicable": True, "proposal": {"status": "propose"},
                         "controls": [{"text": "Hide Z"}]}, 0
        return orig(base, path, body, timeout)
    rows = run(monkeypatch, always)
    assert not rows["interpret (abstain, expect abstain)"]["ok"]


def test_no_selected_member_anywhere_fails_the_new_category_gate(monkeypatch):
    rows = run(monkeypatch, FakeLab(select=0))
    gate = rows["new-category: at least one category selects members and feeds the filter"]
    assert not gate["ok"]


def test_expected_interpret_outcomes():
    assert rat.expected_interpret("openai", "nonliteral") == "propose"
    assert rat.expected_interpret("mock", "nonliteral") == "any"
    assert rat.expected_interpret("openai", "abstain") == "abstain"


def test_a_control_that_leaves_the_ranking_unchanged_fails(monkeypatch):
    class Inert(FakeLab):
        def ranked(self):
            return list(range(1, 31))
    rows = run(monkeypatch, Inert())
    assert not rows["manual"]["ok"] and "ranking" in rows["manual"]["why_not_ok"]
