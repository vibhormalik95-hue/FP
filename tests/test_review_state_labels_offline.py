"""Synthetic, in-process review contracts; no model or live acceptance claim.

Run with unittest. All inference is authored data and all routes are invoked
directly, without an HTTP client, listener, provider, or local recommender.
"""
from copy import deepcopy
import csv
from pathlib import Path
import tempfile
import unittest

from fastapi import HTTPException

from feedctrl.api import (create_app, SteeringApplyRequest, SteeringHistoryRequest,
                          SteeringPreviewRequest, SteeringRemoveRequest)
from feedctrl import category_induction_producer as producer
from feedctrl import semantic_induction as induction
from feedctrl import semantic_review as review
from feedctrl import staged_induction as staged
from feedctrl.semantic_controls import TEXT_FIELDS


MODEL = {"backend": "offline-test-double", "model_id": "authored-fixture",
         "model_revision": "not-model-evidence"}
PROVENANCE = {"model_id": "authored-fixture", "model_revision": "not-model-evidence",
              "prompt_sha256": "offline-fixture-only"}
OBJECTIVE = "Discover a preparation category in the supplied synthetic records."


def endpoint(app, path):
    return next(route.endpoint for route in app.routes if getattr(route, "path", None) == path)


def label_inputs(label, quote="Bread preparation"):
    index = {"sha256": "a" * 64, "items": {
        1: {"fields": {"caption": quote}},
        2: {"fields": {"caption": "Bicycle commuting"}}}}
    memberships = [
        {"item_id": 1, "verdict": "match", "field": "caption",
         "evidence_quote": quote, "reason": "Authored fixture disposition."},
        {"item_id": 2, "verdict": "not_match", "field": "caption",
         "evidence_quote": "Bicycle commuting", "reason": "Authored fixture disposition."}]
    raw = {"status": "propose", "label": label, "definition": "Bread preparation scenes.",
           "rationale": "Authored fixture only.", "alternatives": [], "memberships": memberships}
    definition = {key: deepcopy(raw[key]) for key in
                  ("status", "label", "definition", "rationale", "alternatives")}
    definition["evidence"] = [{"item_id": 1, "field": "caption", "quote": quote,
                               "reason": "Authored fixture support."}]
    proposal = {key: deepcopy(raw[key]) for key in ("label", "definition")}
    proposal["memberships"] = [{key: row[key] for key in
        ("item_id", "verdict", "evidence_quote", "reason")} for row in memberships]
    catalogue = induction.catalogue_snapshot(producer.catalogue_records(index))
    return index, raw, definition, proposal, catalogue


class RemovalStateTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        source = Path(temp.name) / "synthetic.csv"
        with source.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["video_id", *TEXT_FIELDS])
            writer.writeheader()
            for item in range(1, 37):
                writer.writerow({"video_id": item, "caption": "Bread preparation"
                                 if item in (1, 2) else "Bicycle commuting"
                                 if item in (3, 4) else "Running outside"})
        self.app = create_app(fixture=True, semantic_path=source,
                              allow_local_models=False, allow_local_recommender=False)
        self.demo = self.app.state.demo
        self.session = self.demo.create_session()
        self.state = self.demo.steering_state(self.session, 1)
        # Unrelated A-E and semantic state must survive either removal outcome.
        self.state.update(profile={"category_1": .25}, feedback={1: -1},
                          semantic_groups=[{"fixture": "untouched"}], semantic_revision=9,
                          semantic_pending={"fixture": "unrelated pending review"})

    def preview(self, topic="Bread", strength="standard"):
        result = endpoint(self.app, "/api/steering/preview")(
            SteeringPreviewRequest(user_id=1, backend="manual", actions=[
                {"topic": topic, "operation": "boost", "strength": strength}]), self.session)
        self.assertIs(result["ready"], True)
        return result

    def apply(self, plan):
        return endpoint(self.app, "/api/steering/apply")(
            SteeringApplyRequest(user_id=1, plan_id=plan["plan_id"]), self.session)

    def remove(self, topic="Absent topic"):
        return endpoint(self.app, "/api/steering/remove")(
            SteeringRemoveRequest(user_id=1, topic=topic), self.session)

    def undo(self):
        plan = endpoint(self.app, "/api/steering/history/preview")(
            SteeringHistoryRequest(user_id=1, action="undo"), self.session)
        return self.apply(plan)

    def assert_noop(self, topic="Absent topic"):
        before = deepcopy(self.state)
        result = self.remove(topic)
        self.assertIs(result["removed"], False)
        self.assertEqual(self.state, before)
        self.assertEqual(result["commands"], before["steering_commands"])
        self.assertEqual(result["text"], before["steering_text"])
        self.assertEqual(result["revision"], before["steering_revision"])
        self.assertEqual(result["focus"], before["steering_focus"])
        self.assertEqual(result["can_undo"], bool(before["steering_history"]))
        self.assertEqual(result["feed"], self.demo.steering_feed(1, before["steering_commands"]))

    def test_absent_remove_on_empty_state_does_not_create_history(self):
        self.assert_noop()
        self.assertEqual(self.state["steering_history"], [])

    def test_absent_remove_on_nonempty_state_preserves_focus(self):
        self.apply(self.preview())
        self.assertIsNotNone(self.state["steering_focus"])
        self.assert_noop()

    def test_repeated_misses_preserve_pending_review_and_all_state(self):
        self.apply(self.preview())
        pending = self.preview("Bicycle")
        for _ in range(15):
            self.assert_noop()
        self.assertIs(self.apply(pending)["applied"], True)

    def test_repeated_remove_preserves_a_new_pending_review(self):
        self.apply(self.preview())
        topic = self.state["steering_commands"][0]["topic"]
        self.assertIs(self.remove(topic)["removed"], True)
        pending = self.preview("Bicycle")
        for _ in range(15):
            self.assert_noop(topic)
        self.assertIs(self.apply(pending)["applied"], True)

    def test_misses_cannot_evict_meaningful_undo_history(self):
        for index in range(10):
            self.apply(self.preview(strength="light" if index % 2 else "strong"))
        before = deepcopy(self.state["steering_history"])
        self.assertEqual(len(before), 10)
        for _ in range(20):
            self.assert_noop()
        self.assertEqual(self.state["steering_history"], before)
        for expected in reversed(before):
            result = self.undo()
            self.assertEqual(result["commands"], expected["commands"])
            self.assertEqual(result["focus"], expected["focus"])
        self.assertEqual(self.state["steering_commands"], [])
        self.assertEqual(self.state["steering_history"], [])

    def test_true_casefold_removal_invalidates_review_and_remains_undoable(self):
        self.apply(self.preview())
        prior = deepcopy(self.state)
        pending = self.preview("Bicycle")
        before = deepcopy(self.state)
        topic = before["steering_commands"][0]["topic"]
        result = self.remove(topic.upper())
        self.assertIs(result["removed"], True)
        self.assertEqual(result["commands"], [])
        self.assertEqual(result["revision"], before["steering_revision"] + 1)
        self.assertEqual(self.state["steering_history"], before["steering_history"] + [
            self.demo.steering_snapshot(before)])
        self.assertIsNone(self.state["steering_pending"])
        self.assertIsNone(result["focus"])
        for key in before:
            if not key.startswith("steering_"):
                self.assertEqual(self.state[key], before[key])
        with self.assertRaises(HTTPException) as raised:
            self.apply(pending)
        self.assertEqual(raised.exception.status_code, 409)
        restored = self.undo()
        self.assertEqual(restored["commands"], prior["steering_commands"])
        self.assertEqual(restored["text"], prior["steering_text"])
        self.assertEqual(restored["focus"], prior["steering_focus"])
        self.assertEqual(self.state["steering_history"], prior["steering_history"])

    def test_label_rejection_cannot_apply_and_valid_label_still_requires_review(self):
        self.state.update(semantic_groups=[], semantic_revision=0, semantic_pending=None,
                          semantic_history=[])
        def semantic_preview(label):
            return endpoint(self.app, "/api/semantic/preview")(
                review.SemanticPreview(user_id=1, label=label, candidate_ids=list(range(1, 9)),
                    backend="manual_category", action_source="manual", category="category_1"),
                self.session)
        pending = semantic_preview("Café & 京都")
        self.assertIs(pending["ready"], True)
        self.assertIs(pending["applied"], False)
        self.assertEqual(self.state["semantic_groups"], [])
        applied = endpoint(self.app, "/api/semantic/apply")(
            review.SemanticApply(user_id=1, plan_id=pending["plan_id"]), self.session)
        self.assertIs(applied["applied"], True)
        active = deepcopy(self.state["semantic_groups"])
        revision = self.state["semantic_revision"]
        history = deepcopy(self.state["semantic_history"])
        for label in ("\u200b", "Café & 京都\u200b", "Bread\u202e", "\tBread"):
            with self.subTest(label=repr(label)):
                with self.assertRaises(HTTPException) as raised:
                    semantic_preview(label)
                self.assertEqual(raised.exception.status_code, 422)
                self.assertEqual(self.state["semantic_groups"], active)
                self.assertEqual(self.state["semantic_revision"], revision)
                self.assertEqual(self.state["semantic_history"], history)
                self.assertIsNone(self.state["semantic_pending"])


class LabelValidationTests(unittest.TestCase):
    def assert_rejected(self, label):
        index, raw, definition, proposal, catalogue = label_inputs(label)
        before = deepcopy((index, raw, definition, proposal, catalogue))
        with self.assertRaises(ValueError):
            review.seal_group(label, OBJECTIVE, {"status": "review", "item_ids": [1]}, index, [1, 2])
        with self.assertRaises(induction.MembershipValidationError):
            induction.validate_induced_category(proposal, catalogue, PROVENANCE)
        result = producer.propose_category(OBJECTIVE, index, lambda *_: raw, model_provenance=MODEL)
        self.assertEqual(result["status"], "error")
        self.assertIsNone(result["proposal"])
        with self.assertRaises(ValueError):
            staged.propose_definition(OBJECTIVE, index, [], lambda *_: definition, MODEL)
        self.assertEqual((index, raw, definition, proposal, catalogue), before)

    def test_zero_width_embedded_bidi_and_surrogate_labels_are_rejected(self):
        for label in ("\u200b", " \u200b ", "Bread\u200b", "Br\u200dead",
                      "Bread\u2060", "\ufeffBread", "Bread\u202e", "\u2066Bread\u2069",
                      "Bread\x7f", "Bread\x85", "Bread\ud800", "\tBread", "Bread\n"):
            with self.subTest(label=repr(label)):
                self.assert_rejected(label)

    def test_ordinary_whitespace_only_labels_still_reject(self):
        for label in ("", " ", "\u00a0"):
            with self.subTest(label=repr(label)):
                self.assert_rejected(label)

    def test_multilingual_labels_punctuation_and_existing_trimming_survive(self):
        for label in ("京都美食", "Café / pâtisserie (été)", "Cafe\u0301, pain & thé!",
                      "مرحبا بالعالم", "हिन्दी भोजन", "パン・料理", "  Bread & tea  "):
            with self.subTest(label=label):
                index, raw, definition, proposal, catalogue = label_inputs(label)
                group = review.seal_group(label, OBJECTIVE,
                    {"status": "review", "item_ids": [1]}, index, [1, 2])
                self.assertEqual(group["label"], label.strip())
                owned = deepcopy(group)
                revision = owned.pop("revision")
                self.assertEqual(revision, producer._digest(owned))
                member = induction.validate_induced_category(proposal, catalogue, PROVENANCE)
                self.assertEqual(member["label"], label.strip())
                owned = deepcopy(member)
                revision = owned.pop("category_revision")
                self.assertEqual(revision, induction.canonical_hash(owned))
                envelope = producer.propose_category(OBJECTIVE, index, lambda *_: raw, model_provenance=MODEL)
                self.assertEqual(envelope["status"], "review")
                self.assertIs(envelope["requires_review"], True)
                self.assertEqual(envelope["proposal"]["label"], label)
                self.assertEqual(envelope["audit"]["response_sha256"], producer._digest(raw))
                result = staged.propose_definition(OBJECTIVE, index, [], lambda *_: definition, MODEL)
                self.assertEqual(result["status"], "definition_review")
                self.assertIs(result["requires_review"], True)
                self.assertEqual(result["proposal"]["label"], label)
                staged.check_seal(result, "definition_revision")

    def test_format_characters_in_source_quotes_are_byte_exact_not_label_filtered(self):
        quote = "Bread\u200b preparation\u202e\t\nCafé"
        index, raw, definition, proposal, catalogue = label_inputs("Bread preparation", quote)
        before = deepcopy((index, raw, definition, proposal, catalogue))
        member = induction.validate_induced_category(proposal, catalogue, PROVENANCE)
        self.assertEqual(member["memberships"][0]["evidence_quote"], quote)
        self.assertEqual(member["catalogue_sha256"], induction.canonical_hash(
            [catalogue[item] for item in sorted(catalogue)]))
        envelope = producer.propose_category(OBJECTIVE, index, lambda *_: raw, model_provenance=MODEL)
        self.assertEqual(envelope["status"], "review")
        self.assertEqual(envelope["proposal"]["memberships"][0]["evidence_quote"], quote)
        self.assertEqual(envelope["field_evidence"][0]["evidence_quote"], quote)
        self.assertEqual(envelope["audit"]["response_sha256"], producer._digest(raw))
        result = staged.propose_definition(OBJECTIVE, index, [], lambda *_: definition, MODEL)
        self.assertEqual(result["status"], "definition_review")
        self.assertEqual(result["proposal"]["evidence"][0]["quote"], quote)
        group = review.seal_group("Bread preparation", OBJECTIVE,
            {"status": "review", "item_ids": [1], "evidence": [{"quote": quote}]}, index, [1, 2])
        self.assertEqual(group["proposal"]["evidence"][0]["quote"], quote)
        self.assertEqual((index, raw, definition, proposal, catalogue), before)

    def test_label_filter_does_not_tighten_definition_text_policy(self):
        index, raw, definition, proposal, catalogue = label_inputs("Bread")
        text = "Bread\u200b preparation\u202e."
        raw["definition"] = definition["definition"] = proposal["definition"] = text
        self.assertEqual(induction.validate_induced_category(proposal, catalogue, PROVENANCE)["definition"], text)
        envelope = producer.propose_category(OBJECTIVE, index, lambda *_: raw, model_provenance=MODEL)
        self.assertEqual(envelope["status"], "review")
        self.assertEqual(envelope["proposal"]["definition"], text)
        result = staged.propose_definition(OBJECTIVE, index, [], lambda *_: definition, MODEL)
        self.assertEqual(result["status"], "definition_review")
        self.assertEqual(result["proposal"]["definition"], text)

    def test_valid_casefold_duplicates_still_reject_and_invisible_suffix_cannot_bypass(self):
        inventory = [{"category_id": "existing", "label": "CAFÉ", "member_ids": [2]}]
        for label, expected in (("Café", "duplicate"), ("Café\u200b", "error")):
            index, raw, definition, _, _ = label_inputs(label)
            result = producer.propose_category(OBJECTIVE, index, lambda *_: raw,
                model_provenance=MODEL, existing_categories=inventory)
            self.assertEqual(result["status"], expected)
            self.assertIsNone(result["proposal"])
            if expected == "error":
                with self.assertRaises(ValueError):
                    staged.propose_definition(OBJECTIVE, index, inventory, lambda *_: definition, MODEL)
            else:
                result = staged.propose_definition(OBJECTIVE, index, inventory, lambda *_: definition, MODEL)
                self.assertEqual(result["status"], "duplicate")

    def test_existing_label_length_and_evidence_byte_budgets_remain(self):
        for size in (80, 81):
            index, raw, definition, proposal, catalogue = label_inputs("界" * size)
            if size == 80:
                self.assertEqual(induction.validate_induced_category(proposal, catalogue, PROVENANCE)["label"], "界" * size)
                self.assertEqual(producer.propose_category(OBJECTIVE, index, lambda *_: raw,
                    model_provenance=MODEL)["status"], "review")
                self.assertEqual(staged.propose_definition(OBJECTIVE, index, [], lambda *_: definition, MODEL)["status"], "definition_review")
            else:
                with self.assertRaises(induction.MembershipValidationError):
                    induction.validate_induced_category(proposal, catalogue, PROVENANCE)
                self.assertEqual(producer.propose_category(OBJECTIVE, index, lambda *_: raw,
                    model_provenance=MODEL)["status"], "error")
                with self.assertRaises(ValueError):
                    staged.propose_definition(OBJECTIVE, index, [], lambda *_: definition, MODEL)
        def forbidden(*_):
            self.fail("Evidence budget must stop before authored inference")
        self.assertEqual(producer.propose_category(OBJECTIVE, index, forbidden,
            model_provenance=MODEL, max_bytes=1)["status"], "blocked")
        large_index, _, _, _, _ = label_inputs("Bread", "界" * 2400)
        with self.assertRaisesRegex(ValueError, "Evidence budget"):
            staged.propose_definition(OBJECTIVE, large_index, [], forbidden, MODEL)


if __name__ == "__main__":
    unittest.main(verbosity=2)
