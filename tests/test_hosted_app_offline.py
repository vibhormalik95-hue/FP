"""No-network policy/wiring contracts, not hosted-model or UI acceptance.

Run directly with unittest. Route functions are called in-process; no HTTP
server/client, socket, real transport, token, model or private data is used.
"""
from copy import deepcopy
import ast
import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from feedctrl.api import (create_app, fixture_data, ControlRequest, ProfileTextRequest,
                          TopicRequest, SteeringPreviewRequest)
from feedctrl.category_provider import CategoryProvider
from feedctrl.controls import ParserOperationalError
from feedctrl.hosted_app import category_payload, shared_factories, create_openai_hosted_app
from feedctrl.model_adapters import HostedRunBudget
from feedctrl.semantic_review import SemanticPreview, InductionPreview, SemanticApply, SemanticHistory
from feedctrl.semantic_controls import TEXT_FIELDS
from feedctrl.staged_routes import DefinitionApproval
from feedctrl.synthetic_drafts import DraftRequest


IDENTITY = {"backend": "openai-responses", "model": "not-a-real-model",
            "digest": "offline-configuration-only",
            "digest_kind": "configuration_sha256_not_model_weights"}


def endpoint(app, path):
    return next(route.endpoint for route in app.routes if getattr(route, "path", None) == path)


class HostedBoundaryTests(unittest.TestCase):
    def test_category_prompt_mapping_preserves_evidence_and_inputs(self):
        payload = {"instructions": "Trusted producer instruction", "objective": "test",
                   "catalogue": [{"item_id": 1, "fields": {"caption": "旅行"}}]}
        before = deepcopy(payload)
        mapped = category_payload(payload)
        self.assertEqual(mapped, {"system": payload["instructions"],
                                 "objective": payload["objective"], "catalogue": payload["catalogue"]})
        mapped["catalogue"][0]["fields"].clear()
        self.assertEqual(payload, before)

    def test_category_prompt_mapping_rejects_ambiguous_or_missing_instructions(self):
        for bad in (None, [], {}, {"instructions": ""}, {"instructions": 1},
                    {"instructions": "trusted", "system": "other"}):
            with self.subTest(payload=bad), self.assertRaises(ValueError):
                category_payload(bad)

    def test_one_callable_and_budget_shared_across_both_workflows(self):
        budget = HostedRunBudget(2)
        calls = []
        def infer(payload, schema):
            budget.reserve()
            calls.append(deepcopy((payload, schema)))
            return {"synthetic": True}
        semantic, category = shared_factories(infer, IDENTITY)
        semantic()[0]({"system": "action", "request": "test"}, {"type": "object"})
        category()[0]({"instructions": "definition", "objective": "test"}, {"type": "object"})
        with self.assertRaises(ParserOperationalError):
            semantic()[0]({"system": "another"}, {"type": "object"})
        self.assertEqual(budget.attempted, 2)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1][0], {"system": "definition", "objective": "test"})

    def test_binding_provenance_is_snapshot_and_not_weight_claim(self):
        identity = deepcopy(IDENTITY)
        semantic, category = shared_factories(lambda *_: {}, identity)
        identity["model"] = "changed"
        first = semantic()[1]
        first["model"] = "caller mutation"
        self.assertEqual(semantic()[1], IDENTITY)
        self.assertEqual(category()[1], {"backend": "openai-responses",
                                        "model_id": "not-a-real-model",
                                        "model_revision": "offline-configuration-only"})

    def test_binding_does_not_accept_unrelated_or_missing_identity(self):
        for bad in ({}, {**IDENTITY, "backend": "ollama-loopback"},
                    {**IDENTITY, "digest": ""}, {**IDENTITY, "model": None}):
            with self.subTest(identity=bad), self.assertRaises(ValueError):
                shared_factories(lambda *_: {}, bad)

    def test_category_missing_provider_fails_before_local_factory(self):
        provider = CategoryProvider(allow_local_models=False)
        with patch("feedctrl.induction_integration.make_induction_infer",
                   side_effect=AssertionError("Must never start local inference")):
            for stage in ("combined", "definition", "membership", "evidence_audit"):
                with self.subTest(stage=stage), self.assertRaises(ParserOperationalError):
                    provider.stage(stage, "unused")

    def test_category_configured_failure_never_falls_back(self):
        calls = []
        def factory():
            calls.append(True)
            raise RuntimeError("synthetic initialization failure")
        provider = CategoryProvider(factory, allow_local_models=False)
        with patch("feedctrl.induction_integration.make_induction_infer",
                   side_effect=AssertionError("Must never fall back")):
            for _ in range(2):
                with self.assertRaises(ValueError):
                    provider.stage("definition", "unused")
        self.assertEqual(len(calls), 1)

    def test_all_app_local_paths_reject_before_session_or_state_work(self):
        app = create_app(fixture=True, allow_local_models=False)
        cases = [
            ("/api/control", ControlRequest(user_id=1, text="test", backend="ollama")),
            ("/api/profile/text", ProfileTextRequest(user_id=1, text="test", backend="ollama")),
            ("/api/topic/preview", TopicRequest(user_id=1, text="test", backend="ollama")),
            ("/api/steering/preview", SteeringPreviewRequest(user_id=1, text="test")),
            ("/api/semantic/preview", SemanticPreview(user_id=1, label="test", candidate_ids=[1, 2])),
            ("/api/synthetic/preview", DraftRequest(user_id=1, brief="test", synthetic_acknowledged=True)),
        ]
        with patch.object(app.state.demo, "user_state", side_effect=AssertionError("No state work")), \
             patch.object(app.state.demo, "steering_state", side_effect=AssertionError("No state work")):
            for path, body in cases:
                with self.subTest(path=path), self.assertRaises(HTTPException) as raised:
                    endpoint(app, path)(body, "not-a-session")
                self.assertEqual(raised.exception.status_code, 403)

    def test_policy_status_does_not_claim_model_execution(self):
        app = create_app(fixture=True, allow_local_models=False)
        status = endpoint(app, "/api/status")()
        self.assertIs(status["local_models_allowed"], False)
        self.assertIn("Disabled", status["ollama_status"])
        self.assertEqual(status["model_mode"], "deterministic diagnostic scorer")

    def test_explicit_boolean_policy_only(self):
        for value in (None, 0, 1, "false"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                create_app(fixture=True, allow_local_models=value)

    def test_nonfixture_checkpoint_is_rejected_before_local_recommender_load(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data = fixture_data()
            data["metadata"] = {"source": "authored non-fixture constructor test"}
            path = root / "data.json"
            path.write_text(json.dumps(data))
            model = root / "existing-checkpoint-placeholder"
            model.mkdir()
            with patch("feedctrl.model.load_model", side_effect=AssertionError("No local model load")):
                with self.assertRaisesRegex(ValueError, "loading or replacing"):
                    create_app(data_path=path, model_path=model, allow_local_models=False,
                               allow_local_recommender=False)

    def test_import_has_no_eager_app_factory_call(self):
        source = Path(__file__).resolve().parents[1] / "feedctrl/api.py"
        module = ast.parse(source.read_text())
        calls = []
        for node in module.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.Expr)):
                value = node.value
                if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
                    calls.append(value.func.id)
        self.assertNotIn("create_app", calls)

    def test_unconfigured_category_routes_reject_before_session_work(self):
        app = create_app(fixture=True, allow_local_models=False)
        body = InductionPreview(user_id=1, candidate_ids=[1, 2], objective="Authored test")
        cases = [("/api/semantic/induction/preview", body),
                 ("/api/semantic/definition/preview", body),
                 ("/api/semantic/definition/classify", DefinitionApproval(
                     user_id=1, plan_id="not-a-plan", evidence_reviewed=True))]
        with patch.object(app.state.demo, "user_state", side_effect=AssertionError("No state work")):
            for path, request in cases:
                with self.subTest(path=path), self.assertRaises(HTTPException) as raised:
                    endpoint(app, path)(request, "not-a-session")
                self.assertEqual(raised.exception.status_code, 503)

    def test_hosted_factory_constructs_once_without_invoking(self):
        infer_calls = []
        receipts = []
        def fake_infer(*args):
            infer_calls.append(args)
            raise AssertionError("Construction must not invoke inference")
        with patch("feedctrl.hosted_app.make_openai_responses_infer",
                   return_value=(fake_infer, deepcopy(IDENTITY), receipts)) as transport:
            app = create_openai_hosted_app(api_key="offline-placeholder", model="not-a-real-model",
                                          reasoning_effort="medium", run_budget=HostedRunBudget(2),
                                          authorized=False, fixture=True, spend_guard=object())
        self.assertEqual(transport.call_count, 1)
        self.assertIs(transport.call_args.kwargs["authorized"], False)
        self.assertIs(app.state.allow_local_models, False)
        self.assertIs(app.state.hosted_model_receipts, receipts)
        self.assertEqual(infer_calls, [])

    def test_real_constructor_rejects_absent_authorization_before_setup(self):
        with patch("feedctrl.model_adapters.urllib.request.build_opener",
                   side_effect=AssertionError("No transport setup")):
            with self.assertRaises(ValueError):
                create_openai_hosted_app(api_key="offline-placeholder", model="not-a-real-model",
                                        reasoning_effort="medium", run_budget=HostedRunBudget(2),
                                        fixture=True, spend_guard=object())

    def test_factory_rejects_call_cap_without_durable_spending_guard(self):
        with patch("feedctrl.hosted_app.make_openai_responses_infer",
                   side_effect=AssertionError("No transport construction")):
            with self.assertRaisesRegex(ValueError, "dollar cap"):
                create_openai_hosted_app(api_key="offline-placeholder", model="not-a-real-model",
                                        reasoning_effort="medium", run_budget=HostedRunBudget(5),
                                        authorized=True, fixture=True)


class HostedWorkflowTests(unittest.TestCase):
    """Authored replies exercise application plumbing, never semantic accuracy."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        path = Path(self.temp.name) / "synthetic.csv"
        with path.open("w", newline="", encoding="utf8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["video_id", *TEXT_FIELDS])
            writer.writeheader()
            for item in range(1, 37):
                writer.writerow({"video_id": item, "caption":
                                 "Freshly baked bread" if item in (3, 4) else "Bicycle commuting"})
        self.budget = HostedRunBudget(5)
        self.calls = []
        def infer(payload, schema):
            self.assertIn("system", payload)
            self.assertNotIn("instructions", payload)
            self.budget.reserve()
            keys = schema["required"]
            if "control" in keys:
                self.calls.append("action")
                return {"needs_clarification": False, "question": "", "control": "exclude/none",
                        "intent_span": "makes me hungry"}
            if "negation_resolved" in keys:
                self.calls.append("grounding")
                return {"status": "propose", "reason": "Authored test reply, not model semantics",
                        "negation_resolved": True, "alternatives": [], "evidence": [
                            {"item_id": 3, "field": "caption", "quote": "Freshly baked bread"}]}
            if keys == ["title", "description", "category_label"]:
                self.calls.append("draft")
                return {"title": "Imagined harbor", "description": "A fictional harbor.",
                        "category_label": "Imaginary places"}
            rows = payload["catalogue"]
            if "evidence" in keys:
                self.calls.append("definition")
                return {"status": "propose", "label": "Bread preparation", "definition":
                        "Videos describing bread preparation.", "rationale": "Authored test reply.",
                        "alternatives": [], "evidence": [{"item_id": 3, "field": "caption",
                        "quote": "Freshly baked bread", "reason": "Synthetic supporting evidence."}]}
            if keys == ["memberships"]:
                self.calls.append("membership")
                return {"memberships": [{"item_id": r["item_id"], "verdict":
                        "match" if r["item_id"] in (3, 4) else "not_match", "field": "caption",
                        "evidence_quote": r["fields"]["caption"], "reason": "Authored test disposition."}
                        for r in rows]}
            if "memberships" in keys:
                self.calls.append("combined")
                return {"status": "propose", "label": "Bread preparation", "definition":
                        "Videos describing bread preparation.", "rationale": "Authored test reply.",
                        "alternatives": [], "memberships": [{"item_id": r["item_id"], "verdict":
                        "match" if r["item_id"] in (3, 4) else "not_match", "field": "caption",
                        "evidence_quote": r["fields"]["caption"], "reason": "Authored test disposition."}
                        for r in rows]}
            self.assertEqual(keys, ["assessments"])
            self.calls.append("evidence_audit")
            return {"assessments": [{"item_id": r["item_id"], "assessment":
                    "supported" if r["item_id"] in (3, 4) else "contradicted", "field": "caption",
                    "quote": r["fields"]["caption"], "reason": "Authored test assessment."}
                    for r in rows]}
        semantic, category = shared_factories(infer, IDENTITY)
        self.app = create_app(fixture=True, semantic_path=path, allow_local_models=False,
                              semantic_infer_factory=semantic, category_infer_factory=category,
                              synthetic_infer_factory=semantic)
        self.session = endpoint(self.app, "/api/session")()["session_id"]

    def call(self, path, body):
        return endpoint(self.app, path)(body, self.session)

    def saved(self):
        return endpoint(self.app, "/api/semantic/groups")(1, self.session)

    def apply(self, proposal):
        return self.call("/api/semantic/apply", SemanticApply(user_id=1, plan_id=proposal["plan_id"]))

    def test_both_workflows_share_cap_and_explicit_apply_undo(self):
        original = self.saved()["feed"]
        indirect = self.call("/api/semantic/preview", SemanticPreview(
            user_id=1, label="Authored fixture", candidate_ids=list(range(1, 9)),
            text="Hide what makes me hungry", backend="configured_model", action_source="model"))
        self.assertTrue(indirect["ready"])
        self.assertFalse(indirect["applied"])
        self.assertEqual(self.saved()["groups"], [])
        self.assertEqual(self.calls, ["action", "grounding"])
        self.assertEqual(self.apply(indirect)["feed"]["available_items"], 35)
        undo = self.call("/api/semantic/history/preview", SemanticHistory(user_id=1, action="undo"))
        self.assertEqual(self.apply(undo)["feed"], original)
        definition = self.call("/api/semantic/definition/preview", InductionPreview(
            user_id=1, candidate_ids=list(range(1, 9)), objective="Find preparation scenes.",
            operation="exclude", strength="none"))
        self.assertTrue(definition["definition_ready"])
        self.assertFalse(definition["applied"])
        self.assertEqual(self.saved()["groups"], [])
        membership = self.call("/api/semantic/definition/classify", DefinitionApproval(
            user_id=1, plan_id=definition["definition_plan_id"], evidence_reviewed=True))
        self.assertTrue(membership["ready"])
        self.assertFalse(membership["applied"])
        self.assertEqual(self.saved()["groups"], [])
        self.assertEqual(self.calls, ["action", "grounding", "definition", "membership", "evidence_audit"])
        self.assertEqual(self.budget.attempted, 5)
        self.assertEqual(self.apply(membership)["feed"]["available_items"], 34)
        # Reusing factories must not renew the transport's shared allowance.
        exhausted = self.call("/api/semantic/definition/preview", InductionPreview(
            user_id=1, candidate_ids=list(range(1, 9)), objective="Find preparation scenes."))
        self.assertFalse(exhausted["definition_ready"])
        self.assertEqual(exhausted["status"], "error")
        self.assertEqual(len(self.calls), 5)
        self.assertEqual(self.saved()["feed"]["available_items"], 34)

    def test_indirect_category_and_draft_share_one_attempt_cap(self):
        original = self.saved()["feed"]
        indirect = self.call("/api/semantic/preview", SemanticPreview(
            user_id=1, label="Authored fixture", candidate_ids=list(range(1, 9)),
            text="Hide what makes me hungry", backend="configured_model", action_source="model"))
        self.assertTrue(indirect["ready"])
        category = self.call("/api/semantic/induction/preview", InductionPreview(
            user_id=1, candidate_ids=list(range(1, 9)), objective="Find preparation scenes."))
        self.assertTrue(category["ready"])
        for _ in range(2):
            draft = self.call("/api/synthetic/preview", DraftRequest(
                user_id=1, brief="Imagine a fictional harbor.", synthetic_acknowledged=True))
            self.assertTrue(draft["ready"])
            self.assertFalse(draft["admitted"])
        exhausted = self.call("/api/synthetic/preview", DraftRequest(
            user_id=1, brief="Imagine a fictional harbor.", synthetic_acknowledged=True))
        self.assertFalse(exhausted["ready"])
        self.assertEqual(self.calls, ["action", "grounding", "combined", "draft", "draft"])
        self.assertEqual(self.budget.attempted, 5)
        self.assertEqual(self.saved()["feed"], original)
        self.assertEqual(endpoint(self.app, "/api/synthetic/items")(1, self.session)["items"], [])

    def test_combined_category_uses_bridge_without_apply_or_budget_reset(self):
        before = self.saved()["feed"]
        proposal = self.call("/api/semantic/induction/preview", InductionPreview(
            user_id=1, candidate_ids=list(range(1, 9)), objective="Find preparation scenes.",
            operation="exclude", strength="none"))
        self.assertTrue(proposal["ready"])
        self.assertFalse(proposal["applied"])
        self.assertEqual(self.calls, ["combined"])
        self.assertEqual(self.saved()["feed"], before)
        self.assertEqual(self.apply(proposal)["feed"]["available_items"], 34)
        undo = self.call("/api/semantic/history/preview", SemanticHistory(user_id=1, action="undo"))
        self.assertEqual(self.apply(undo)["feed"], before)
        self.assertEqual(self.budget.attempted, 1)

    def test_superseded_action_stops_before_grounding_call(self):
        from feedctrl import semantic_review
        interpret = semantic_review.interpret_action
        current = []
        def replace_review(text, infer):
            result = interpret(text, infer)
            current.append(self.call("/api/semantic/preview", SemanticPreview(
                user_id=1, label="New explicit manual review", candidate_ids=list(range(1, 9)),
                backend="manual_category", action_source="manual", category="category_1",
                operation="exclude", strength="none")))
            return result
        with patch("feedctrl.semantic_review.interpret_action", replace_review):
            with self.assertRaises(HTTPException) as raised:
                self.call("/api/semantic/preview", SemanticPreview(
                    user_id=1, label="Superseded request", candidate_ids=list(range(1, 9)),
                    text="I'm not hungry, remove all the stuff that makes me hungry.",
                    backend="configured_model", action_source="model"))
        self.assertEqual(raised.exception.status_code, 409)
        self.assertEqual(self.calls, ["action"])
        self.assertEqual(self.budget.attempted, 1)
        self.assertEqual(self.saved()["groups"], [])
        self.assertEqual(self.apply(current[0])["feed"]["available_items"], 34)


if __name__ == "__main__":
    unittest.main(verbosity=2)
