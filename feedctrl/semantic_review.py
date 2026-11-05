"""Opt-in reviewed semantic item sets, separate from literal controls and studies.

Only supplied existing items can enter a named group. Quotes establish source
custody, not relevance. All inference proposals require explicit approval.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import os
import math
import secrets
import time
from typing import Literal

from fastapi import Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from feedctrl.controls import ParserOperationalError, normalize_scores
from feedctrl.indirect_grounding import _catalogue, _digest, make_local_ollama_infer, propose_indirect
from feedctrl.semantic_controls import STRENGTH_WEIGHTS

ACTION_SCHEMA = {"type": "object", "additionalProperties": False,
    "required": ["needs_clarification", "question", "operation", "strength", "intent_span"],
    "properties": {"needs_clarification": {"type": "boolean"}, "question": {"type": "string"},
        "operation": {"type": "string", "enum": ["boost", "reduce", "exclude"]},
        "strength": {"type": "string", "enum": ["light", "standard", "strong", "none"]},
        "intent_span": {"type": "string"}}}
ACTION_PROMPT = """Interpret exactly one current feed-control request.
Return boost, reduce (still eligible), or exclude (remove entirely), and strength
light=.10, standard=.25 or strong=.40; exclusion has strength none. intent_span
must be a verbatim continuous substring of the request describing the intended
subject, including modifiers. It may describe an indirect relationship such as
a personal goal, without using a category name. Do not substitute a category
label for the original words. Parse direction and subject span only; a separate
evidence stage will assess which supplied items satisfy that subject. A clear
indirect goal need not name a category. Negation of a personal state does not
negate an explicit control: preserve the requested subject including negation.
Clarify multiple actions, unknown direction, a negated/contradictory command,
quotas, conditional requests or unresolved references. No history or cross-turn
context is supplied. When clarifying still emit valid placeholder
fields; they will not execute. Output only the schema. Nothing is applied."""


class SemanticPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: int = Field(ge=0)
    text: str = Field(default="", max_length=2000)
    label: str = Field(min_length=1, max_length=80)
    candidate_ids: list[StrictInt] = Field(min_length=2, max_length=20)
    backend: Literal["ollama", "manual_category"] = "ollama"
    action_source: Literal["ollama", "manual"] = "ollama"
    category: str | None = Field(default=None, max_length=120)
    operation: Literal["boost", "reduce", "exclude"] = "boost"
    strength: Literal["light", "standard", "strong", "none"] = "standard"
    mode: Literal["merge", "replace"] = "merge"


class SemanticApply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: int = Field(ge=0)
    plan_id: str = Field(min_length=1, max_length=100)


class SemanticHistory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: int = Field(ge=0)
    action: Literal["undo", "clear"]


def interpret_action(text, infer):
    if not text.strip():
        raise ValueError("A current natural-language request is required")
    raw = infer({"system": ACTION_PROMPT, "request": text}, deepcopy(ACTION_SCHEMA))
    if (not isinstance(raw, dict) or set(raw) != set(ACTION_SCHEMA["required"])
            or type(raw["needs_clarification"]) is not bool or not isinstance(raw["question"], str)):
        raise ValueError("Invalid semantic action schema")
    if raw["needs_clarification"]:
        return None, raw["question"][:2000] or "Name one current subject and direction"
    action = {k: raw[k] for k in ("operation", "strength", "intent_span")}
    if (not isinstance(action["operation"], str) or not isinstance(action["strength"], str)
            or action["operation"] not in ("boost", "reduce", "exclude")
            or not isinstance(action["intent_span"], str) or not action["intent_span"].strip()
            or action["intent_span"] not in text
            or (action["strength"] != "none" if action["operation"] == "exclude"
                else action["strength"] not in STRENGTH_WEIGHTS)):
        raise ValueError("Action is not bound to the request or has invalid strength")
    return deepcopy(action), ""


def scoped_index(index, ids):
    if (not index or len(ids) != len(set(ids)) or any(type(i) is not int or i not in index["items"] for i in ids)):
        raise ValueError("Choose distinct existing catalogue IDs")
    return {"sha256": index["sha256"], "items": {i: deepcopy(index["items"][i]) for i in sorted(ids)}}


def seal_group(label, request, proposal, index, eligible_ids):
    if proposal["status"] != "review" or not proposal["item_ids"]:
        raise ValueError("Only a nonempty reviewed proposal can become a named group")
    group = {"label": label.strip(), "request": request, "proposal": deepcopy(proposal),
        "scope_ids": sorted(index["items"]), "eligible_sha256": _digest(sorted(eligible_ids))}
    if not group["label"] or any(ord(c) < 32 for c in group["label"]):
        raise ValueError("Use a printable category label")
    group["revision"] = _digest(group)
    return group


def validate_group(group, index, eligible_ids):
    owned = deepcopy(group)
    revision = owned.pop("revision", None)
    if revision != _digest(owned):
        raise ValueError("Named group changed after review")
    proposal = owned["proposal"]
    provenance = proposal["provenance"]
    scope = scoped_index(index, owned["scope_ids"])
    if (owned["eligible_sha256"] != _digest(sorted(eligible_ids))
            or provenance["source_sha256"] != index["sha256"]
            or provenance["catalogue_sha256"] != _digest(_catalogue(scope))
            or provenance["request_sha256"] != _digest(owned["request"])
            or provenance["action_sha256"] != _digest(proposal["action"])):
        raise ValueError("Source, request or action changed; generate and review a new proposal")
    if not set(proposal["item_ids"]) <= set(scope["items"]):
        raise ValueError("Reviewed members are outside the supplied evidence scope")
    return deepcopy(group)


def rank_groups(ids, scores, groups, index, limit=10):
    """One cached score vector, additive bounded controls, hard exclusion wins."""
    if (not ids or len(ids) != len(scores) or len(ids) != len(set(ids))
            or any(type(i) is not int for i in ids)
            or any(not isinstance(s, (int, float)) or not math.isfinite(s) for s in scores)):
        raise ValueError("One score per distinct catalogue item is required")
    base = dict(zip(ids, normalize_scores(scores)))
    adjusted, excluded = dict(base), set()
    for group in groups:
        validate_group(group, index, ids)
        proposal = group["proposal"]
        action, members = proposal["action"], set(proposal["item_ids"])
        if action["operation"] == "exclude":
            excluded.update(members)
        else:
            delta = STRENGTH_WEIGHTS[action["strength"]] * (1 if action["operation"] == "boost" else -1)
            for item in members:
                adjusted[item] += delta
    order = sorted((i for i in ids if i not in excluded), key=lambda i: (-adjusted[i], i))
    top = order[:limit]
    neutral = sorted(ids, key=lambda i: (-base[i], i))[:limit]
    return {"items": [{"item_id": i, "score": float(adjusted[i]), "base_score": float(base[i]), "rank": pos}
                      for pos, i in enumerate(top, 1)],
        "available_items": len(order), "fill_rate": len(top) / limit,
        "baseline_items": neutral, "group_exposure": [{"label": g["label"],
            "before": len(set(neutral) & set(g["proposal"]["item_ids"])),
            "after": len(set(top) & set(g["proposal"]["item_ids"]))} for g in groups]}


def install_semantic_routes(app, demo):
    """Session-scoped prototype. Existing A-E and literal topic state are untouched."""
    def state_for(token, user):
        state = demo.user_state(token, user)
        if demo.topic_index is None:
            raise HTTPException(503, "Official source metadata is required")
        for key, value in (("semantic_groups", []), ("semantic_revision", 0),
                           ("semantic_pending", None), ("semantic_history", [])):
            state.setdefault(key, deepcopy(value))
        return state

    def feed(user, groups):
        ids = sorted(demo.items)
        user_data = demo.users[user]
        history = list(user_data["train"]) + list(user_data["request_history"])
        if demo.model:
            scores = demo.model.score(history, ids)
        else:
            counts = Counter(c for i in history for c in demo.items.get(i, []))
            scores = [sum(counts[c] for c in demo.items[i]) + ((i * 17 + user * 7) % 19) / 100 for i in ids]
        result = rank_groups(ids, scores, groups, demo.topic_index)
        for item in result["items"]:
            item["categories"] = demo.items[item["item_id"]]
            item["explanation"] = [f"Reviewed semantic group: {g['label']} ({g['proposal']['action']['operation']})."
                for g in groups if item["item_id"] in g["proposal"]["item_ids"]]
            item["explanation_source"] = "reviewed_semantic_item_set"
        result.update(mode="Experimental reviewed semantic item sets; not frozen A-E",
            category_exposure=dict(Counter(c for i in result["items"] for c in i["categories"])),
            commands_count=len(groups), data_mode="fixture" if demo.fixture else "processed dataset",
            model_mode="trained model" if demo.model else "deterministic diagnostic scorer")
        return result

    def response(state, user):
        return {"groups": deepcopy(state["semantic_groups"]), "revision": state["semantic_revision"],
            "can_undo": bool(state["semantic_history"]), "feed": feed(user, state["semantic_groups"]),
            "configured_model": os.getenv("FEEDCTRL_STEERING_MODEL", "qwen2.5-coder:7b-instruct")}

    def review(state, user, groups, history_action="none", proposal=None):
        preview_feed = feed(user, groups)  # validate before installing a review token
        plan_id = secrets.token_urlsafe(24)
        state["semantic_pending"] = {"id": plan_id, "created": time.monotonic(),
            "revision": state["semantic_revision"], "groups": deepcopy(groups), "history_action": history_action}
        return {"ready": True, "applied": False, "plan_id": plan_id,
            "groups": deepcopy(groups), "proposal": proposal, "feed": preview_feed,
            "note": "Only the declared supplied items were assessed; quotes are not relevance proof."}

    @app.get("/api/semantic/groups")
    def get_groups(user_id: int = Query(ge=0), x_session_id: str | None = Header(default=None)):
        with demo.lock:
            state = state_for(x_session_id, user_id)
            try:
                return response(state, user_id)
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc

    @app.post("/api/semantic/preview")
    def preview(body: SemanticPreview, x_session_id: str | None = Header(default=None)):
        calls, provenance = [], None
        with demo.lock:
            state = state_for(x_session_id, body.user_id)
            revision = state["semantic_revision"]
            nonce = secrets.token_urlsafe(16)
            state["semantic_preview_nonce"] = nonce
            state["semantic_pending"] = None
            existing = deepcopy(state["semantic_groups"])
            try:
                index = scoped_index(demo.topic_index, body.candidate_ids)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
        try:
            if body.backend == "manual_category":
                if body.category not in demo.categories:
                    raise ValueError("Manual baseline requires an existing category ID")
                action = {"operation": body.operation, "strength": body.strength, "intent_span": body.category}
                if ((action["strength"] != "none") if body.operation == "exclude"
                    else action["strength"] not in STRENGTH_WEIGHTS):
                    raise ValueError("Invalid manual strength")
                members = [i for i in index["items"] if body.category in demo.items[i]]
                if not members:
                    return {"ready": False, "applied": False, "status": "no_match", "reason": "No scoped item has that category"}
                proposal = {"status": "review", "requires_review": True, "reason": "Exact existing-category baseline, no model",
                    "action": action, "item_ids": members, "evidence": [], "provenance": {
                        "source_sha256": index["sha256"], "catalogue_sha256": _digest(_catalogue(index)),
                        "request_sha256": _digest(body.category), "action_sha256": _digest(action),
                        "model": {"backend": "manual_category", "model": "none", "digest": "not_applicable"}}}
                request = body.category
            else:
                infer, provenance = make_local_ollama_infer(os.getenv("FEEDCTRL_STEERING_MODEL", "qwen2.5-coder:7b-instruct"), timeout=90)
                def tracked_infer(payload, schema):
                    # Own raw receipts; these are returned only to this session's caller.
                    raw = infer(deepcopy(payload), deepcopy(schema))
                    calls.append({"request_sha256": _digest(payload), "schema_sha256": _digest(schema),
                        "response_sha256": _digest(raw), "raw_response": deepcopy(raw)})
                    return raw
                if body.action_source == "manual":
                    # Explicit ablation/user choice, never a fallback after model failure.
                    action = {"operation": body.operation, "strength": body.strength, "intent_span": body.text}
                    question = ""
                else:
                    action, question = interpret_action(body.text, tracked_infer)
                if action is None:
                    return {"ready": False, "applied": False, "status": "clarify", "reason": question,
                            "model_calls": calls, "model_provenance": provenance}
                proposal = propose_indirect(body.text, action, index, tracked_infer, model_provenance=provenance)
                proposal["action_source"] = body.action_source
                if proposal["status"] != "review":
                    return {"ready": False, "applied": False, **proposal, "model_calls": calls}
                request = body.text
            group = seal_group(body.label, request, proposal, index, demo.items)
            groups = ([] if body.mode == "replace" else
                      [g for g in existing if g["label"].casefold() != group["label"].casefold()]) + [group]
            if len(groups) > 8:
                raise ValueError("At most eight active semantic groups")
            with demo.lock:
                state = state_for(x_session_id, body.user_id)
                if state["semantic_revision"] != revision or state.get("semantic_preview_nonce") != nonce:
                    raise HTTPException(409, "Preferences changed during inference; review again")
                return {**review(state, body.user_id, groups, proposal=proposal),
                        "model_calls": calls if body.backend == "ollama" else []}
        except ValueError as exc:
            if body.backend == "ollama":
                return {"ready": False, "applied": False, "status": "error",
                    "reason": f"Model proposal rejected ({type(exc).__name__}): {exc}",
                    "model_calls": calls, "model_provenance": provenance}
            raise HTTPException(422, str(exc)) from exc
        except ParserOperationalError as exc:
            raise HTTPException(422 if body.backend == "manual_category" else 502,
                f"Semantic proposal failed ({type(exc).__name__}); no preferences changed: {exc}") from exc

    @app.post("/api/semantic/history/preview")
    def history(body: SemanticHistory, x_session_id: str | None = Header(default=None)):
        with demo.lock:
            state = state_for(x_session_id, body.user_id)
            state["semantic_preview_nonce"] = None
            state["semantic_pending"] = None
            if body.action == "undo" and not state["semantic_history"]:
                return {"ready": False, "applied": False, "reason": "No earlier applied semantic profile"}
            try:
                return review(state, body.user_id,
                    state["semantic_history"][-1] if body.action == "undo" else [], body.action)
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc

    @app.post("/api/semantic/apply")
    def apply(body: SemanticApply, x_session_id: str | None = Header(default=None)):
        with demo.lock:
            state = state_for(x_session_id, body.user_id)
            pending = state["semantic_pending"]
            if (not pending or pending["id"] != body.plan_id or pending["revision"] != state["semantic_revision"]
                    or time.monotonic() - pending["created"] > 300):
                raise HTTPException(409, "Review expired or changed; review again")
            try:
                feed(body.user_id, pending["groups"])  # current-source and digest revalidation before any state write
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc
            if pending["history_action"] == "undo":
                state["semantic_history"].pop()
            else:
                state["semantic_history"] = (state["semantic_history"] + [deepcopy(state["semantic_groups"])])[-10:]
            state["semantic_groups"] = deepcopy(pending["groups"])
            state["semantic_revision"] += 1
            state["semantic_pending"] = None
            return {"applied": True, **response(state, body.user_id)}
