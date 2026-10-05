"""Independent behavioural acceptance tests.

These tests use hand-constructed inputs and metamorphic checks; they do not
establish that an unexecuted KuaiRec or LLM experiment has completed.
"""

import copy
import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from feedctrl.controls import ParserOperationalError, parse_control, parse_profile, rerank
from feedctrl.evaluation import generate_requests, ranking_metrics, run_evaluation


def command(operation, category=None, strength=0.25):
    return {
        "operation": operation,
        "category": category,
        "strength": strength,
        "source": "independent_acceptance_fixture",
    }


class RankingAcceptance(unittest.TestCase):
    def test_ties_have_stable_item_id_order(self):
        actual = rerank(
            [31, 7, 19], [0.5, 0.5, 0.5],
            {31: ["category_1"], 7: ["category_2"], 19: ["category_3"]},
            command("clarify"),
        )
        self.assertEqual(actual, [7, 19, 31])

    def test_hard_mute_removes_every_multilabel_match(self):
        actual = rerank(
            [1, 2, 3, 4], [1.0, 0.9, 0.8, 0.7],
            {1: ["category_1"], 2: ["category_1", "category_2"],
             3: ["category_2"], 4: ["category_3"]},
            command("mute", "category_1"),
        )
        self.assertEqual(actual, [3, 4])

    def test_all_muted_returns_empty_without_forbidden_padding(self):
        actual = rerank(
            [1, 2], [0.9, 0.8],
            {1: ["category_1"], 2: ["category_1"]},
            command("mute", "category_1"),
        )
        self.assertEqual(actual, [])

    def test_boost_breaks_score_tie_in_requested_direction(self):
        actual = rerank(
            [1, 2], [0.5, 0.5],
            {1: ["category_1"], 2: ["category_2"]},
            command("boost", "category_2"),
        )
        self.assertEqual(actual, [2, 1])

    def test_score_normalization_is_positive_affine_invariant(self):
        ids = [1, 2, 3, 4]
        categories = {1: ["category_1"], 2: ["category_2"],
                      3: ["category_1"], 4: ["category_3"]}
        scores = [0.9, 0.85, 0.3, 0.05]
        original = rerank(ids, scores, categories, command("boost", "category_2"))
        transformed = rerank(
            ids, [100 * s + 7 for s in scores], categories,
            command("boost", "category_2"),
        )
        self.assertEqual(original, transformed)

    def test_reset_recovers_base_order(self):
        actual = rerank(
            [1, 2, 3], [0.1, 0.9, 0.4],
            {1: ["category_1"], 2: ["category_2"], 3: ["category_3"]},
            command("reset"),
        )
        self.assertEqual(actual, [2, 3, 1])


class RuleParserAcceptance(unittest.TestCase):
    """Rule-path checks are explicitly not LLM accuracy evidence."""

    def test_explicit_known_category_request(self):
        result = parse_control(
            "Show me more category_12", ["category_1", "category_12"],
            backend="rule",
        )
        self.assertEqual((result["operation"], result["category"]),
                         ("boost", "category_12"))

    def test_unknown_category_is_not_guessed(self):
        result = parse_control(
            "Show me more category_999", ["category_1", "category_12"],
            backend="rule",
        )
        self.assertEqual(result["operation"], "clarify")


class ProfileAndBackendAcceptance(unittest.TestCase):
    def test_equivalent_profile_and_command_do_not_double_count(self):
        ids = [1, 2, 3]
        scores = [1.0, 0.6, 0.0]
        categories = {1: ["category_1"], 2: ["category_2"], 3: ["category_3"]}
        boost = command("boost", "category_2")
        c = rerank(ids, scores, categories, boost)
        d = rerank(ids, scores, categories, command("clarify"), {"category_2": .25})
        e = rerank(ids, scores, categories, boost, {"category_2": .25})
        # Double counting would incorrectly move item 2 (0.6+0.5) ahead of item 1.
        self.assertEqual(c, [1, 2, 3])
        self.assertEqual(c, d)
        self.assertEqual(c, e)

    def test_profile_text_calls_profile_llm_schema(self):
        response = {"operation": "set", "preferences": [
            {"operation": "boost", "category": "category_1", "strength": .25},
            {"operation": "mute", "category": "category_2", "strength": 1.0},
        ]}
        with patch("feedctrl.controls._llm", return_value=(response, "mock:acceptance")) as mocked:
            result = parse_profile(
                "Show more category_1. Avoid category_2.",
                ["category_1", "category_2"], backend="ollama",
            )
        self.assertEqual(result["profile"], {"category_1": .25, "category_2": -1.0})
        self.assertTrue(mocked.call_args.kwargs["profile"])

    def test_backend_failure_does_not_fall_back_to_rule(self):
        with patch("feedctrl.controls._llm", side_effect=ParserOperationalError("injected outage")):
            with self.assertRaises(ParserOperationalError):
                parse_control("Show more category_1", ["category_1"], backend="ollama")

    def test_malformed_llm_response_is_rejected(self):
        with patch("feedctrl.controls._llm", return_value=({"operation": "boost"}, "mock:acceptance")):
            with self.assertRaises(ParserOperationalError):
                parse_control("Show more category_1", ["category_1"], backend="ollama")


def evaluation_fixture():
    return {
        "metadata": {"kind": "independent_synthetic_fixture"},
        "items": [{"item_id": i, "categories": [f"category_{i % 3}"]} for i in range(1, 13)],
        "users": [
            {"user_id": 21, "train": [1, 2, 3], "request_history": [4, 5], "test": [1]},
            {"user_id": 22, "train": [3, 2, 1], "request_history": [5, 4], "test": [1]},
        ],
    }


class RecordingModel:
    def __init__(self):
        self.histories = []

    def score(self, history, item_ids):
        self.histories.append(list(history))
        return [float(13 - i) for i in item_ids]


class EvaluationAcceptance(unittest.TestCase):
    def test_metric_denominators_and_fill_gate_manually(self):
        metrics = ranking_metrics(
            [4, 1, 5], "category_1",
            {4: ["category_2"], 1: ["category_1", "category_3"], 5: ["category_2"]},
            next_item=4, k=5, operation="boost",
        )
        self.assertAlmostEqual(metrics["target_proportion"], 1 / 5)
        self.assertAlmostEqual(metrics["conditional_exposure"], 1 / 3)
        self.assertAlmostEqual(metrics["fill_rate"], 3 / 5)
        self.assertEqual(metrics["hr1"], 1)
        self.assertEqual(metrics["compliant_filled_success"], 0)

    def test_no_exposure_in_empty_feed_is_not_filled_success(self):
        metrics = ranking_metrics([], "category_1", {1: ["category_1"]}, 1, k=10, operation="mute")
        self.assertEqual(metrics["target_proportion"], 0)
        self.assertIsNone(metrics["conditional_exposure"])
        self.assertEqual(metrics["compliant_filled_success"], 0)
        self.assertEqual(metrics["hr1"], 0)

    def test_final_labels_do_not_change_requests_or_rankings(self):
        original = evaluation_fixture()
        changed = copy.deepcopy(original)
        for user in changed["users"]:
            user["test"] = [12]
        self.assertEqual(generate_requests(original), generate_requests(changed))
        with tempfile.TemporaryDirectory() as path:
            model_a, model_b = RecordingModel(), RecordingModel()
            with patch("feedctrl.controls.parse_profile", wraps=parse_profile) as profile_parser:
                summary_a = run_evaluation(original, model_a, Path(path) / "a", n_bootstrap=100, k=3)
            self.assertGreater(profile_parser.call_count, 0)
            summary_b = run_evaluation(changed, model_b, Path(path) / "b", n_bootstrap=100, k=3)
            requests_a = json.loads((Path(path) / "a/requests.json").read_text())
            requests_b = json.loads((Path(path) / "b/requests.json").read_text())
            self.assertEqual(requests_a, requests_b)
            with (Path(path) / "a/request_metrics.csv").open(newline="") as handle:
                rows_a = list(csv.DictReader(handle))
            with (Path(path) / "b/request_metrics.csv").open(newline="") as handle:
                rows_b = list(csv.DictReader(handle))
        self.assertEqual(model_a.histories, model_b.histories)
        self.assertEqual(model_a.histories, [[1, 2, 3, 4, 5], [3, 2, 1, 5, 4]])
        self.assertEqual([r["ranking_sha256"] for r in rows_a], [r["ranking_sha256"] for r in rows_b])
        self.assertGreater(sum(float(r["hr1"]) for r in rows_a), sum(float(r["hr1"]) for r in rows_b))
        self.assertTrue(summary_a["all_b_rank_invariant"])
        self.assertTrue(summary_b["all_b_rank_invariant"])
        self.assertEqual(summary_a["c_d_e_equal_request_fraction"], 1)
        self.assertEqual(summary_a["evidence_status"], "rule_diagnostic")

    def test_unavailable_llm_has_explicit_failure_status(self):
        with tempfile.TemporaryDirectory() as path:
            with patch("feedctrl.controls._llm", side_effect=ParserOperationalError("injected outage")):
                summary = run_evaluation(evaluation_fixture(), RecordingModel(), path,
                                         parser_backend="ollama", n_bootstrap=100, k=3)
        self.assertEqual(summary["evidence_status"], "unavailable")
        self.assertEqual(summary["parse_operational_errors"], summary["parse_request_count"])


class ApiAcceptance(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from feedctrl.api import create_app
        self.client = TestClient(create_app(fixture=True))
        first = self.client.post("/api/session").json()["session_id"]
        second = self.client.post("/api/session").json()["session_id"]
        self.first = {"X-Session-ID": first}
        self.second = {"X-Session-ID": second}

    def tearDown(self):
        self.client.close()

    def feed(self, headers=None, user=1, condition="E", limit=10):
        return self.client.get(
            "/api/feed", params={"user_id": user, "condition": condition, "limit": limit},
            headers=self.first if headers is None else headers,
        )

    def test_text_profile_is_applied_and_isolated_by_session_and_user(self):
        with patch("feedctrl.api.parse_profile", wraps=parse_profile) as profile_parser:
            response = self.client.post(
                "/api/profile/text", headers=self.first,
                json={"user_id": 1, "text": "Show more category_1. Avoid category_2.", "backend": "rule"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(profile_parser.call_count, 1)
        self.assertEqual(response.json()["profile"], {"category_1": .25, "category_2": -1.0})
        self.assertEqual(self.feed().json()["profile"], {"category_1": .25, "category_2": -1.0})
        self.assertEqual(self.feed(headers=self.second).json()["profile"], {})
        self.assertEqual(self.feed(user=2).json()["profile"], {})
        self.assertTrue(all("category_2" not in item["categories"] for item in self.feed().json()["items"]))

    def test_all_muted_profile_is_empty_and_reset_restores_state(self):
        categories = self.client.get("/api/categories").json()["categories"]
        response = self.client.put("/api/profile", headers=self.first,
                                   json={"user_id": 1, "profile": {c: -1 for c in categories}})
        self.assertEqual(response.status_code, 200)
        muted = self.feed().json()
        self.assertEqual(muted["items"], [])
        self.assertEqual(muted["fill_rate"], 0)
        self.assertEqual(self.client.post("/api/reset", headers=self.first, json={"user_id": 1}).status_code, 200)
        reset = self.feed().json()
        self.assertEqual(len(reset["items"]), 10)
        self.assertEqual(reset["profile"], {})
        self.assertEqual(reset["feedback_count"], 0)

    def test_input_and_session_boundaries(self):
        self.assertEqual(self.feed(headers={}).status_code, 401)
        self.assertEqual(self.feed(user=99999).status_code, 404)
        self.assertEqual(self.feed(limit=10000).status_code, 422)
        self.assertEqual(self.client.put("/api/profile", headers=self.first,
                         json={"user_id": 1, "profile": {"category_999": 1}}).status_code, 422)
        self.assertEqual(self.client.post("/api/control", headers=self.first,
                         json={"user_id": 1, "text": "x" * 501}).status_code, 422)
        self.assertEqual(self.client.post("/api/profile/text", headers=self.first,
                         json={"user_id": 1, "text": "word " * 201}).status_code, 422)

    def test_natural_language_global_reset_clears_item_feedback_too(self):
        baseline = self.feed(condition="A").json()
        item = baseline["items"][0]["item_id"]
        self.client.post("/api/feedback", headers=self.first,
                         json={"user_id": 1, "item_id": item, "direction": "dislike"})
        response = self.client.post("/api/control", headers=self.first,
                                    json={"user_id": 1, "text": "Reset my feed", "backend": "rule"})
        self.assertEqual(response.status_code, 200)
        restored = self.feed(condition="A").json()
        self.assertEqual(restored["feedback_count"], 0)
        self.assertEqual([i["item_id"] for i in baseline["items"]],
                         [i["item_id"] for i in restored["items"]])

    def test_visible_backend_error_preserves_prior_state(self):
        self.client.post("/api/control", headers=self.first,
                         json={"user_id": 1, "text": "Show more category_1"})
        before = self.feed().json()
        for endpoint, parser in (("/api/control", "parse_control"), ("/api/profile/text", "parse_profile")):
            with patch(f"feedctrl.api.{parser}", side_effect=ParserOperationalError("injected outage")):
                response = self.client.post(endpoint, headers=self.first,
                              json={"user_id": 1, "text": "Avoid category_2", "backend": "ollama"})
            self.assertEqual(response.status_code, 502)
            self.assertIn("failed", response.json()["detail"])
            self.assertEqual(self.feed().json(), before)

    def test_feedback_and_explanations_match_offline_condition_policy(self):
        before = self.client.get("/api/compare", headers=self.first, params={"user_id": 1, "limit": 36}).json()
        disliked = before["A"]["items"][0]["item_id"]
        response = self.client.post("/api/feedback", headers=self.first,
                                    json={"user_id": 1, "item_id": disliked, "direction": "dislike"})
        self.assertEqual(response.status_code, 200)
        after = self.client.get("/api/compare", headers=self.first, params={"user_id": 1, "limit": 36}).json()
        item_ids = lambda result: [item["item_id"] for item in result["items"]]
        self.assertNotIn(disliked, item_ids(after["A"]))
        self.assertEqual(item_ids(after["A"]), item_ids(after["B"]))
        for condition in ("C", "D", "E"):
            self.assertEqual(item_ids(before[condition]), item_ids(after[condition]))

    def test_api_discloses_fixture_and_never_returns_test_labels(self):
        status = self.client.get("/api/status").json()
        self.assertEqual(status["data_mode"], "fixture")
        self.assertIn("diagnostic", status["model_mode"])
        payloads = [status, self.client.get("/api/users").json(), self.feed().json()]
        def assert_no_test_fields(value):
            if isinstance(value, dict):
                self.assertFalse({"test", "test_items", "held_out", "next_item"}.intersection(value))
                for entry in value.values():
                    assert_no_test_fields(entry)
            elif isinstance(value, list):
                for entry in value:
                    assert_no_test_fields(entry)
        for payload in payloads:
            assert_no_test_fields(payload)

    def test_missing_data_fixture_fallback_never_loads_real_checkpoint(self):
        from fastapi.testclient import TestClient
        from feedctrl.api import create_app
        with tempfile.TemporaryDirectory() as path:
            model_dir = Path(path) / "existing-checkpoint-directory"
            model_dir.mkdir()
            with patch("feedctrl.model.load_model") as loader:
                app = create_app(data_path=Path(path) / "missing-data.json", model_path=model_dir)
            loader.assert_not_called()
            with TestClient(app) as client:
                status = client.get("/api/status").json()
                self.assertEqual(status["data_mode"], "fixture")
                self.assertIn("diagnostic", status["model_mode"])
                token = client.post("/api/session").json()["session_id"]
                result = client.get("/api/feed", headers={"X-Session-ID": token}, params={"user_id": 1})
                self.assertEqual(result.status_code, 200)
                self.assertEqual(len(result.json()["items"]), 10)


class ExplanationAcceptance(unittest.TestCase):
    def test_generation_rejects_ungrounded_llm_statement(self):
        from feedctrl.explanations import generate_explanation
        response = {"done": True, "message": {"content": json.dumps({
            "item_id": 1, "statements": ["You like sports, so this video will make you happy."]})}}
        with tempfile.TemporaryDirectory() as path:
            with patch("feedctrl.explanations.ollama_provenance", return_value={"model": "mock", "digest": "mock"}):
                with patch("feedctrl.explanations._request", return_value=response):
                    with self.assertRaises(ParserOperationalError):
                        generate_explanation(1, ["category_1"], [1], {1: ["category_1"]},
                                             backend="ollama", cache_dir=path)

    def test_cached_text_cannot_bypass_grounded_statements(self):
        from feedctrl.explanations import cached_explanation, generate_explanation
        record = generate_explanation(1, ["category_1"], [1], {1: ["category_1"]})
        record.update(source="ollama_constrained_fact_selection",
                      provenance={"model": "mock", "digest": "mock"},
                      text="Invented explanation that must never be returned.")
        with tempfile.TemporaryDirectory() as path:
            index = Path(path) / "index.json"
            index.write_text(json.dumps({"explanations": [record]}))
            actual = cached_explanation(1, ["category_1"], [1], {1: ["category_1"]}, index_path=index)
        self.assertEqual(actual["text"], " ".join(actual["statements"]))
        self.assertNotIn("Invented", actual["text"])

    def test_stale_or_empty_cache_falls_back_with_explicit_source(self):
        from feedctrl.explanations import cached_explanation, generate_explanation
        record = generate_explanation(1, ["category_1"], [1], {1: ["category_1"]})
        record.update(source="ollama_constrained_fact_selection", provenance={"model": "mock", "digest": "mock"})
        with tempfile.TemporaryDirectory() as path:
            index = Path(path) / "index.json"
            index.write_text(json.dumps({"explanations": [record]}))
            stale = cached_explanation(1, ["category_1"], [1, 1], {1: ["category_1"]}, index_path=index)
            self.assertEqual(stale["source"], "verified_template")
            record["statements"] = []
            record["text"] = ""
            index.write_text(json.dumps({"explanations": [record]}))
            empty = cached_explanation(1, ["category_1"], [1], {1: ["category_1"]}, index_path=index)
            self.assertEqual(empty["source"], "verified_template")


if __name__ == "__main__":
    unittest.main()
