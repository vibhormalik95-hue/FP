from copy import deepcopy

import pytest

from feedctrl.semantic_induction import (MembershipValidationError, catalogue_snapshot,
    manual_category_membership, rerank_membership, validate_induced_category)


@pytest.fixture
def source():
    return catalogue_snapshot([
        {"item_id": 1, "source_text": "A bowl of vegetable soup.", "categories": ["category_0"]},
        {"item_id": 2, "source_text": "An electric guitar performance.", "categories": ["category_1"]},
        {"item_id": 3, "source_text": "No description supplied.", "categories": []},
    ])


@pytest.fixture
def proposal():
    return {"label": "Meal ideas", "definition": "Items whose supplied description depicts food.",
        "memberships": [
            {"item_id": 1, "verdict": "match", "evidence_quote": "vegetable soup", "reason": "The source describes a dish."},
            {"item_id": 2, "verdict": "not_match", "evidence_quote": "guitar performance", "reason": "The source describes music."},
            {"item_id": 3, "verdict": "unknown", "evidence_quote": "", "reason": "The description has no usable subject evidence."},
        ]}


PROVENANCE = {"model_id": "fixture-only", "model_revision": "fixture-v1", "prompt_sha256": "fixture-no-model-call"}


def test_category_definition_is_not_restricted_to_source_taxonomy(source, proposal):
    result = validate_induced_category(proposal, source, PROVENANCE)
    assert result["label"] == "Meal ideas"
    assert result["member_ids"] == [1] and result["unknown_ids"] == [3]
    assert result["semantic_entailment_verified"] is False
    assert manual_category_membership(source, "category_0") == [1]


@pytest.mark.parametrize("change", ["new_id", "duplicate", "missing", "invented_quote", "empty_match_quote", "bad_verdict"])
def test_unverifiable_membership_is_rejected(source, proposal, change):
    if change == "new_id": proposal["memberships"][0]["item_id"] = 999
    elif change == "duplicate": proposal["memberships"][1]["item_id"] = 1
    elif change == "missing": proposal["memberships"].pop()
    elif change == "invented_quote": proposal["memberships"][0]["evidence_quote"] = "hamburger"
    elif change == "empty_match_quote": proposal["memberships"][0]["evidence_quote"] = ""
    else: proposal["memberships"][0]["verdict"] = "probably"
    with pytest.raises(MembershipValidationError):
        validate_induced_category(proposal, source, PROVENANCE)


def test_input_and_catalogue_revisions_are_preserved(source, proposal):
    original = deepcopy(proposal)
    first = validate_induced_category(proposal, source, PROVENANCE)
    assert proposal == original
    changed = deepcopy(source)
    changed[1]["source_text"] += " Additional supplied information."
    second = validate_induced_category(proposal, changed, PROVENANCE)
    assert first["catalogue_sha256"] != second["catalogue_sha256"]
    assert first["category_revision"] != second["category_revision"]


def test_manual_and_induced_membership_use_identical_enforcement(source, proposal):
    induced = validate_induced_category(proposal, source, PROVENANCE)
    manual = manual_category_membership(source, "category_0")
    assert rerank_membership([1,2,3], [.3,.5,.4], manual, "boost", "strong") == \
           rerank_membership([1,2,3], [.3,.5,.4], induced["member_ids"], "boost", "strong")


def test_reduce_retains_eligibility_and_exclusion_removes_members():
    reduced = rerank_membership([1,2,3], [.3,.5,.4], [1], "reduce", "strong")
    excluded = rerank_membership([1,2,3], [.3,.5,.4], [1], "exclude", "none")
    assert reduced["available_items"] == 3 and excluded["available_items"] == 2
    assert 1 in [x["item_id"] for x in reduced["items"]]
    assert 1 not in [x["item_id"] for x in excluded["items"]]


def test_ranking_cannot_invent_new_item_ids():
    with pytest.raises(MembershipValidationError):
        rerank_membership([1,2], [.2,.8], [999], "boost")


def test_membership_policy_preserves_existing_numeric_id_tie_break():
    result = rerank_membership([3,1,2], [.5,.5,.5], [], "boost")
    assert [row["item_id"] for row in result["items"]] == [1,2,3]


def test_returned_category_does_not_alias_nested_caller_inputs(source, proposal):
    provenance = {**PROVENANCE, "settings": {"temperature": 0}}
    result = validate_induced_category(proposal, source, provenance)
    before = deepcopy(result)
    provenance["settings"]["temperature"] = 99
    proposal["memberships"][0]["item_id"] = 999
    source[1]["categories"].append("invented")
    assert result == before


def test_returned_category_mutation_does_not_modify_caller_inputs(source, proposal):
    provenance = {**PROVENANCE, "settings": {"temperature": 0}}
    result = validate_induced_category(proposal, source, provenance)
    result["provenance"]["settings"]["temperature"] = 99
    result["memberships"][0]["item_id"] = 999
    assert provenance["settings"]["temperature"] == 0
    assert proposal["memberships"][0]["item_id"] == 1
