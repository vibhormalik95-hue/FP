from feedctrl import lab_metrics as lm


NL = {"id": "NL01", "language": "en", "action": "hide", "required": ["category:a", "tag:b"], "acceptable": ["category:c"]}


def pred(status="propose", labels=(), action="hide"):
    return {"status": status, "controls": [{"action": action, "term_id": t} for t in labels]}


def test_exact_profile_needs_action_required_and_nothing_wrong():
    assert lm.score_nl(NL, pred(labels=["category:a", "tag:b"]))["exact"]
    assert lm.score_nl(NL, pred(labels=["category:a", "tag:b", "category:c"]))["exact"]
    assert not lm.score_nl(NL, pred(labels=["category:a"]))["exact"]                       # missed required
    assert not lm.score_nl(NL, pred(labels=["category:a", "tag:b", "tag:z"]))["exact"]     # wrong label
    assert not lm.score_nl(NL, pred(labels=["category:a", "tag:b"], action="reduce"))["exact"]
    row = lm.score_nl(NL, pred(labels=["category:a", "tag:z"]))
    assert row["label_precision"] == 0.5 and row["label_recall"] == 0.5 and row["missed_required"] == ["tag:b"]


def test_abstention_and_false_acceptance():
    case = {"id": "AB01", "language": "zh", "expected_status": "unsupported"}
    ok = lm.score_ab(case, {"status": "unsupported", "controls": []})
    bad = lm.score_ab(case, pred(labels=["category:a"]))
    assert ok["abstained"] and ok["status_match"] and not ok["false_acceptance"]
    assert bad["false_acceptance"] and not bad["abstained"]
    assert not lm.score_ab(case, {"error": "timeout"})["abstained"]                       # an error is not an abstention


def test_member_scores():
    case = {"id": "NC01", "language": "en", "members": [1, 2, 3, 4]}
    row = lm.score_nc(case, {"selected": [1, 2, 9], "raw_match": [1, 2, 3, 9]})
    assert round(row["member_precision"], 3) == 0.667 and row["member_recall"] == 0.5
    assert row["missed_members"] == [3, 4] and row["false_members"] == [9]


def test_wilson_and_bh():
    assert lm.wilson(79, 100) == [0.7002, 0.8583]          # the frozen E1 interval
    assert lm.bh([0.01, 0.04, 0.03]) == [0.03, 0.04, 0.04]


def test_paired_tests_shape():
    a = [lm.score_nl(NL, pred(labels=["category:a", "tag:b"])), lm.score_ab({"id": "AB1", "language": "en", "expected_status": "no_match"}, {"status": "no_match"})]
    b = [lm.score_nl(NL, pred(labels=["category:a"])), lm.score_ab({"id": "AB1", "language": "en", "expected_status": "no_match"}, pred(labels=["x:y"]))]
    t = lm.paired_tests({"m1": a, "m2": b})[0]
    assert t["only_a"] == 2 and t["only_b"] == 0 and 0 < t["mcnemar_p_bh"] <= 1


def test_reviewer_drops_and_any_abstain():
    case = {"id": "NC02", "language": "en", "members": [1, 2], "excluded": [3]}
    row = lm.score_nc(case, {"selected": [1, 2, 3]})
    assert row["member_precision"] == 1.0 and row["exact"]
    ab = {"id": "AB12", "language": "en", "expected_status": "any_abstain"}
    assert lm.score_ab(ab, {"status": "unsupported", "controls": []})["status_match"]
    assert not lm.score_ab(ab, {"status": "propose", "controls": [{"action": "hide", "term_id": "x:y"}]})["status_match"]
