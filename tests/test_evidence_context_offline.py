"""Pure display regression: AST-isolated function, no application imports/startup.

Run directly with Python (not the broader application's pytest/conftest).
These checks prove text custody/display only, never semantic correctness.
"""
import ast
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "feedctrl/semantic_review.py"


def display(text, quote, *, missing_item=False):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    install = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                   and n.name == "install_semantic_routes")
    fn = next(n for n in install.body if isinstance(n, ast.FunctionDef)
              and n.name == "evidence_context")
    # Load only the display function and its former literal display limit.
    # Never import semantic_review, register routes or execute an app factory.
    ns = {"demo": SimpleNamespace(topic_index={"items": {} if missing_item else {
        1: {"fields": {"caption": text}}}}), "EVIDENCE_CONTEXT_CHARS": 2000}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), str(SOURCE), "exec"), ns)
    proposal = {"evidence": [{"item_id": 1, "field": "caption", "quote": quote}]}
    before = deepcopy(proposal)
    result = ns["evidence_context"](proposal)[0]
    if proposal != before:
        raise AssertionError("Display mutated the proposal")
    return result


class EvidenceContextTests(unittest.TestCase):
    def assert_full(self, text, quote):
        row = display(text, quote)
        self.assertEqual(row["supplied_field_text"], text)
        self.assertFalse(row["truncated"])
        self.assertTrue(row["quote_present"])
        self.assertIn("not performed", row["semantic_check"])
        return row

    def test_quote_beyond_2000_and_nearby_negation(self):
        text = "Introduction. " * 200 + "This does not need batteries; mains only."
        self.assert_full(text, "need batteries")

    def test_qualifier_after_quote_remains_visible(self):
        self.assert_full("x" * 1990 + "portable, but not suitable for air travel.", "portable")

    def test_multiple_occurrences_keep_conflicting_contexts(self):
        text = "not waterproof. " + "background " * 300 + "waterproof only with cover."
        row = self.assert_full(text, "waterproof")
        self.assertEqual(row["supplied_field_text"].count("waterproof"), 2)

    def test_absent_quote_is_not_claimed_present(self):
        text = "x" * 2500 + "No travel claim."
        row = display(text, "air travel")
        self.assertEqual(row["supplied_field_text"], text)
        self.assertFalse(row["quote_present"])
        self.assertFalse(row["truncated"])

    def test_length_boundaries(self):
        for length in (1, 1999, 2000, 2001, 10000):
            with self.subTest(length=length):
                self.assert_full("a" * length, "a")

    def test_unicode_and_combining_characters_preserved_exactly(self):
        self.assert_full("🧭旅行" * 800 + "不可登机；cafe\u0301 only, not café.", "cafe\u0301")

    def test_missing_item_and_nonstring_field(self):
        for row in (display("text", "text", missing_item=True), display(None, "text"),
                    display(123, "text")):
            self.assertIsNone(row["supplied_field_text"])
            self.assertFalse(row["quote_present"])
            self.assertFalse(row["truncated"])

    def test_empty_field_and_invalid_quote(self):
        for text, quote in (("", ""), ("some text", None), ("some text", "")):
            row = display(text, quote)
            self.assertEqual(row["supplied_field_text"], text)
            self.assertFalse(row["quote_present"])

    def test_contradictory_quote_is_custody_not_semantic_success(self):
        row = self.assert_full("This does not need batteries.", "need batteries")
        self.assertEqual(row["semantic_check"],
                         "not performed: quote custody only; a human must judge meaning")

    def test_existing_frontend_renders_field_and_warnings(self):
        ui = (SOURCE.parents[1] / "web/src/SemanticPanel.jsx").read_text()
        self.assertIn("e.supplied_field_text??", ui)
        self.assertIn("e.truncated?", ui)
        self.assertIn("e.quote_present?", ui)
        self.assertIn("not semantic relevance", ui)


if __name__ == "__main__":
    unittest.main(verbosity=2)
