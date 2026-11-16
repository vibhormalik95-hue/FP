"""Deterministic answers for the mock provider.

This is not an AI and has no knowledge of any example request. It matches
whole words literally (with a crude plural strip), so it will return no_match for
a nonliteral request such as one that never names a label. It exists only so
the workflows, checks, Apply and Undo can be tested without a key.
"""
import re

STOP = set("a an and any are as at be but by for from i i'm im in into is it its me more my no not of on or "
           "please remove show less hide only the them these this to videos video with without want stuff all "
           "that what which who where about some anything everything clips clip makes make".split())
NEGATIVE = ("hide", "remove", "no ", "without", "stop", "less", "fewer", "don't", "do not", "skip")


def words(text):
    out = set()
    for w in re.findall(r"[a-z0-9][a-z0-9'\-]*", str(text).lower()):
        if w in STOP or len(w) < 3:
            continue
        out.add(w)
        if w.endswith("s") and len(w) > 4:
            out.add(w[:-1])
    return out


def answer(task, payload):
    return {"interpret": _interpret, "define": _define, "classify": _classify,
            "assess": _assess, "new-items": _new_items}[task](payload)


def _interpret(p):
    req = p["request"]
    req_words = words(req)
    hits = [t for t in p["labels"] if words(t["value"]) and words(t["value"]) <= req_words]
    if not hits:
        return {"status": "no_match", "reason": "Mock: no label word appears literally in the request.",
                "alternatives": [], "controls": []}
    low = req.lower()
    action = "hide" if any(n in low for n in ("hide", "remove", "without", "skip", "no more")) else \
        "reduce" if any(n in low for n in ("less", "fewer")) else \
        "only" if "only" in low else "boost"
    span = next((w for w in re.findall(r"\S+", req) if words(w) & set().union(*[words(h["value"]) for h in hits])), req)
    return {"status": "propose", "reason": "Mock: literal word overlap.", "alternatives": [],
            "controls": [{"action": action, "strength": "standard", "intent_span": span,
                          "relation": "Mock: the label word appears in the request.",
                          "term_ids": [h["term_id"] for h in hits]}]}


def _define(p):
    desc_words = words(p["description"])
    label = " ".join(w.capitalize() for w in p["description"].split()[:4])[:60]
    ev = []
    for item in p["catalogue"]:
        hit = desc_words & words(item["description"])
        if hit:
            w = sorted(hit)[0]
            m = re.search(re.escape(w), item["description"], re.I)
            if m:
                ev.append({"item_id": item["item_id"], "field": "description", "quote": m.group(0),
                           "reason": "Mock: shares a word with the description."})
        if len(ev) == 3:
            break
    if not ev:
        return {"status": "no_match", "label": "", "definition": "", "rationale": "Mock: no shared words.",
                "alternatives": [], "evidence": []}
    return {"status": "propose", "label": f"Mock: {label}",
            "definition": f"Items whose title or description mentions any of: {', '.join(sorted(desc_words)[:8])}.",
            "rationale": "Mock definition built from the description's words.", "alternatives": [], "evidence": ev}


def _definition_words(definition):
    m = re.search(r"any of: (.*)\.$", definition)
    return {w.strip() for w in m.group(1).split(",")} if m else words(definition)


def _classify(p):
    keys = _definition_words(p["definition"])
    out = []
    for item in p["items"]:
        text = item["title"] + " " + item["description"]
        hit = sorted(keys & words(text))
        if hit:
            m = re.search(re.escape(hit[0]), item["description"], re.I)
            field, src = ("description", item["description"]) if m else ("title", item["title"])
            m = m or re.search(re.escape(hit[0]), item["title"], re.I)
            out.append({"item_id": item["item_id"], "verdict": "match", "field": field,
                        "quote": m.group(0) if m else hit[0], "reason": "Mock: definition word found."})
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
        text_words = words(item["title"] + " " + item["description"])
        cat = next((c for c in p["existing_categories"] if words(c) & text_words), "none")
        tags = [t for t in p["existing_tags"] if words(t) and words(t) <= text_words]
        customs = []
        for c in p["user_created_categories"]:
            hit = sorted(_definition_words(c["definition"]) & text_words)
            m = re.search(re.escape(hit[0]), item["description"], re.I) if hit else None
            customs.append({"label": c["label"], "verdict": "match" if m else "unknown",
                            "quote": m.group(0) if m else "", "reason": "Mock: literal word check."})
        out.append({"item_id": item["item_id"], "category": cat,
                    "category_reason": "Mock: literal word overlap with the category name.",
                    "tags": tags, "new_categories": customs})
    return {"items": out}
