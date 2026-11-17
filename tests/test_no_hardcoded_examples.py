"""The language controls hold no example-specific logic.

The professor asked for a system that interprets requests, not one that recognises
demonstration requests. This test scans the shipped source of the KuaiRec language
controls (engine, workflows, routes, providers, page) and fails when it finds:

* any request text of a bundled scenario, the evaluation set or the demo scripts;
* Chinese text (the KuaiRec labels and items come from data, never from code), except in
  the mock provider's generic list of action verbs;
* a literal KuaiRec item ID (four or more digits) outside named constants;
* subject words that earlier demonstrations used (food, hunger, cooking and similar).
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ["feedctrl/lab.py", "feedctrl/lab_workflows.py", "feedctrl/lab_routes.py", "feedctrl/llm_providers.py",
           "feedctrl/kuairec_catalog.py", "feedctrl/lab_mock.py", "web/src/LabView.jsx", "scripts/run_app.py"]
CJK = re.compile(r"[㐀-鿿]")
SUBJECT_WORDS = re.compile(r"\b(hungry|hunger|food|cook\w*|recipe\w*|bak(e|ing)|kitchen|eat\w*|gam(e|ing)|"
                           r"pet|pets|dog|cat|travel|music|repair|sport\w*|dance|beauty|car|cars)\b", re.I)
# The mock may name generic action verbs in Chinese (hide, remove, less, only). They carry no subject.
MOCK_ACTION_WORDS = {"不要", "屏蔽", "去掉", "少", "只看"}
ALLOWED_NUMBERS = {"9_000_000", "8765", "11434", "1000", "2000", "8000", "16000", "3600", "1008", "2048", "4096", "8192", "16384", "32768"}  # + Ollama context sizes


def _requests():
    texts = set()
    for path in [ROOT / "scenarios/categories-and-tags/requests.json"]:
        if path.is_file():
            texts.update(v for v in json.loads(path.read_text(encoding="utf-8"))["requests"].values())
    for path in (ROOT / "docs/evidence").glob("lab-eval*/**/*.csv"):
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("request"):
                    texts.add(row["request"])
    for path in (ROOT / "docs/evidence").glob("lab-eval-set*/cases.frozen.json"):
        for case in json.loads(path.read_text(encoding="utf-8"))["cases"]:
            texts.update(t for t in (case.get("request"), case.get("description"), case.get("definition")) if t)
    for path in (ROOT / "tools").glob("**/demo_examples*.json"):
        texts.update(json.loads(path.read_text(encoding="utf-8")).get("requests", []))
    return {t.strip() for t in texts if len(t.strip()) >= 6}


def _code(path):
    text = (ROOT / path).read_text(encoding="utf-8")
    if path.endswith(".py"):   # docstrings and comments may explain; code and prompts may not decide
        import ast
        lines = text.splitlines(keepends=True)
        drop = []
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)) and node.body:
                first = node.body[0]
                if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                    drop.append((first.lineno, first.end_lineno))
        for start, end in sorted(drop, reverse=True):
            del lines[start - 1:end]
        text = re.sub(r"#[^\n]*", "", "".join(lines))
    else:
        text = re.sub(r"//[^\n]*", "", text)
    return text


def test_no_request_text_of_any_example_in_the_source():
    requests = _requests()
    assert requests, "expected at least the bundled scenario requests"
    for path in SOURCES:
        code = _code(path)
        found = [r for r in requests if r in code]
        assert not found, f"{path} contains example request text: {found[:3]}"


def test_no_chinese_subject_text_in_the_source():
    for path in SOURCES:
        chars = set()
        for run in re.findall(r"[㐀-鿿]+", _code(path)):
            if path.endswith("lab_mock.py") and run in MOCK_ACTION_WORDS:
                continue
            chars.add(run)
        assert not chars, f"{path} contains Chinese text: {sorted(chars)[:5]}"


def test_no_subject_words_in_decisions():
    for path in SOURCES:
        hits = sorted({m.group(0).lower() for m in SUBJECT_WORDS.finditer(_code(path))})
        assert not hits, f"{path} contains subject words in code: {hits}"


def test_no_literal_item_ids():
    for path in SOURCES:
        code = re.sub(r"(['\"])(?:(?!\1).)*\1", "''", _code(path))       # ignore string literals (prompts, labels)
        numbers = {n for n in re.findall(r"(?<![\w.])\d[\d_]{3,}(?![\w.])", code)} - ALLOWED_NUMBERS
        assert not numbers, f"{path} contains literal numbers that could be item IDs: {sorted(numbers)}"
