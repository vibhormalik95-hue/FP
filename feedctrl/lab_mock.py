"""Deterministic answers for the mock provider. Not an AI.

It matches text literally: English words of three or more letters. It therefore cannot understand a nonliteral request and returns ``no_match`` when no
label word occurs in the request. It knows no example request, label or item. It exists so
that the tests and ``run-all-tests.cmd`` can drive every workflow with no key and no cost;
its results are plumbing checks, never evidence of interpretation quality.
"""
from __future__ import annotations

import re

STOP = set("a an and any are as at be but by for from i i'm im in into is it its me more my no not of on or "
           "please remove show less hide only the them these this to videos video with without want stuff all "
           "that what which who where about some anything everything clips clip makes make feed less fewer".split())


def tokens(text):
    text = str(text or "")
    out = set()
    for w in re.findall(r"[a-z0-9][a-z0-9'\-]*", text.lower()):
        if w in STOP or len(w) < 3:
            continue
        out.add(w)
        if w.endswith("s") and len(w) > 4:
            out.add(w[:-1])
    return out


def _action(text):
    low = text.lower()
    if any(n in low for n in ("hide", "remove", "without", "no more")):
        return "hide"
    if any(n in low for n in ("less", "fewer")):
        return "reduce"
    if "only" in low:
        return "only"
    return "boost"


def answer(task, payload):
    return {"interpret": _interpret, "define": _define, "classify": _classify, "assess": _assess,
            "new-items": _new_items, "translate": _translate}[task](payload)


def _label_tokens(label):
    return tokens(label["value"])


def _interpret(p):
    request = p["request"]
    req = tokens(request)
    hits = [t for t in p["labels"] if _label_tokens(t) and (_label_tokens(t) & req)]
    if not hits:
        return {"status": "no_match", "reason": "Mock: no label word appears literally in the request.",
                "alternatives": [], "controls": []}
    return {"status": "propose", "reason": "Mock: literal word overlap.", "alternatives": [],
            "controls": [{"action": _action(request), "strength": "standard", "intent_span": request,
                          "relation": "Mock: a label word appears in the request.",
                          "term_ids": [h["term_id"] for h in hits[:5]]}]}


def _item_fields(item):
    return [("title", item.get("title", "")), ("description", item.get("description", "")),
            *[("tags", t) for t in item.get("tags", [])]]


def _first_hit(item, keys):
    for field, text in _item_fields(item):
        for key in sorted(keys):
            if key and key.lower() in str(text).lower():
                start = str(text).lower().index(key.lower())
                return field, str(text)[start:start + len(key)]
    return None


def _define(p):
    keys = tokens(p["description"])
    evidence = []
    for item in p["catalogue"]:
        hit = _first_hit(item, keys)
        if hit:
            evidence.append({"item_id": item["item_id"], "field": hit[0], "quote": hit[1],
                             "reason": "Mock: shares a word with the description."})
        if len(evidence) == 3:
            break
    if not evidence:
        return {"status": "no_match", "label": "", "definition": "", "rationale": "Mock: no shared words.",
                "alternatives": [], "evidence": []}
    words = sorted(keys)[:8]
    return {"status": "propose", "label": ("Mock: " + p["description"])[:60],
            "definition": f"Items whose text mentions any of: {', '.join(words)}.",
            "rationale": "Mock definition built from the description's words.", "alternatives": [],
            "evidence": evidence}


def _definition_keys(definition):
    m = re.search(r"any of: (.*)\.$", definition)
    return {w.strip() for w in m.group(1).split(",")} if m else tokens(definition)


def _classify(p):
    keys = _definition_keys(p["definition"])
    out = []
    for item in p["items"]:
        hit = _first_hit(item, keys)
        if hit:
            out.append({"item_id": item["item_id"], "verdict": "match", "field": hit[0], "quote": hit[1],
                        "reason": "Mock: a definition word occurs in the item."})
        else:
            out.append({"item_id": item["item_id"], "verdict": "unknown", "field": "none", "quote": "",
                        "reason": "Mock: no definition word found."})
    return {"memberships": out}


def _assess(p):
    return {"assessments": [{"item_id": i["item_id"], "supports": True,
                             "reason": "Mock: accepts every cited quotation."} for i in p["items"]]}


def _new_items(p):
    out = []
    for item in p["new_items"]:
        text = tokens(item["title"] + " " + item["description"])
        cats = [c["value"] for c in p["existing_categories"] if _label_tokens(c) & text][:3]
        tags = [t["value"] for t in p["existing_tags"] if _label_tokens(t) & text][:5]
        customs = []
        for c in p["user_created_categories"]:
            hit = _first_hit({"title": item["title"], "description": item["description"]}, _definition_keys(c["definition"]))
            customs.append({"label": c["label"], "verdict": "match" if hit else "unknown",
                            "quote": hit[1] if hit else "", "reason": "Mock: literal word check."})
        out.append({"item_id": item["item_id"], "categories": cats,
                    "category_reason": "Mock: literal word overlap with the category name.",
                    "tags": tags, "new_categories": customs})
    return {"items": out}


def _translate(p):
    return {"translations": [{"id": t["id"], "en": "[mock translation] " + t["text"]} for t in p["texts"]]}
