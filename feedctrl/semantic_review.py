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
import threading
import unicodedata
from typing import Literal

from fastapi import Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

from feedctrl.controls import ParserOperationalError, normalize_scores
from feedctrl.indirect_grounding import _catalogue, _digest, _response_snapshot, make_local_ollama_infer, propose_indirect
from feedctrl.label_validation import is_printable_label
from feedctrl.semantic_controls import STRENGTH_WEIGHTS
from feedctrl import induction_integration as induction

ACTION_CHOICES = {f"{operation}/{strength}": (operation, strength)
    for operation in ("boost", "reduce") for strength in STRENGTH_WEIGHTS}
ACTION_CHOICES["exclude/none"] = ("exclude", "none")
ACTION_SCHEMA = {"type": "object", "additionalProperties": False,
    "required": ["needs_clarification", "question", "control", "intent_span"],
    "properties": {"needs_clarification": {"type": "boolean"}, "question": {"type": "string"},
        "control": {"type": "string", "enum": list(ACTION_CHOICES)},
        "intent_span": {"type": "string"}}}
ACTION_PROMPT = """Interpret exactly one current feed-control request.
Return one control enum encoding operation/strength: boost or reduce (still
eligible) with light=.10, standard=.25 or strong=.40; exclude/none removes
entirely. Choose the exact enum value; do not emit separate operation/strength fields. intent_span
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
    backend: Literal["ollama", "manual_category", "configured_model"] = "ollama"
    action_source: Literal["ollama", "manual", "model", "confirmed"] = "ollama"
    confirmed_target: str | None = Field(default=None, min_length=1, max_length=2000)
    target_confirmed: StrictBool = False
    category: str | None = Field(default=None, max_length=120)
    operation: Literal["boost", "reduce", "exclude"] = "boost"
    strength: Literal["light", "standard", "strong", "none"] = "standard"
    mode: Literal["merge", "replace"] = "merge"


class SemanticApply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: int = Field(ge=0)
    plan_id: str = Field(min_length=1, max_length=100)


class InductionPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: int = Field(ge=0)
    objective: str = Field(min_length=1, max_length=2000)
    candidate_ids: list[StrictInt] = Field(min_length=2, max_length=induction.MAX_ITEMS)
    operation: Literal["boost", "reduce", "exclude"] = "boost"
    strength: Literal["light", "standard", "strong", "none"] = "standard"
    mode: Literal["merge", "replace"] = "merge"


class SemanticHistory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: int = Field(ge=0)
    action: Literal["undo", "clear"]


def interpret_action(text, infer):
    if not text.strip():
        raise ValueError("A current natural-language request is required")
    raw = infer({"system": ACTION_PROMPT, "request": text}, deepcopy(ACTION_SCHEMA))
    if (not isinstance(raw, dict) or set(raw) != set(ACTION_SCHEMA["required"])
            or type(raw["needs_clarification"]) is not bool or not isinstance(raw["question"], str)
            or not isinstance(raw["control"], str) or raw["control"] not in ACTION_CHOICES
            or not isinstance(raw["intent_span"], str)):
        raise ValueError("Invalid semantic action schema")
    if raw["needs_clarification"]:
        return None, raw["question"][:2000] or "Name one current subject and direction"
    # Decode a declared enum value exactly. Invalid pairs are never repaired.
    operation, strength = ACTION_CHOICES[raw["control"]]
    action = {"operation": operation, "strength": strength, "intent_span": raw["intent_span"]}
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


def confirmed_target_context(body):
    """A new explicit user instruction, never a repaired model interpretation."""
    if body.action_source != 'confirmed':
        if body.confirmed_target is not None or body.target_confirmed:
            raise ValueError('Confirmed target fields require explicit confirmed-target mode')
        return None
    if (body.backend == 'manual_category' or body.target_confirmed is not True
            or not body.text.strip() or not body.confirmed_target
            or not body.confirmed_target.strip()):
        raise ValueError('Explicit original request, target and user confirmation required')
    if any(unicodedata.category(c) in {'Cc', 'Cf', 'Cs'}
           for c in body.confirmed_target):
        raise ValueError('Use printable target text without control or format characters')
    if (body.strength != 'none' if body.operation == 'exclude'
            else body.strength not in STRENGTH_WEIGHTS):
        raise ValueError('Explicit target action has an invalid strength')
    return {'kind':'explicit-user-target-v1','confirmed':True,
        'original_request':body.text,'original_request_sha256':_digest(body.text),
        'target':body.confirmed_target,'target_sha256':_digest(body.confirmed_target),
        'direction_source':'user'}


def seal_group(label, request, proposal, index, eligible_ids):
    if proposal["status"] != "review" or not proposal["item_ids"]:
        raise ValueError("Only a nonempty reviewed proposal can become a named group")
    if not is_printable_label(label):
        raise ValueError("Use a printable category label")
    group = {"label": label.strip(), "request": request, "proposal": deepcopy(proposal),
        "scope_ids": sorted(index["items"]), "eligible_sha256": _digest(sorted(eligible_ids))}
    group["revision"] = _digest(group)
    return group


def validate_group(group, index, eligible_ids, original_categories=None):
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
    confirmation = proposal.get('target_confirmation')
    if confirmation is not None:
        if (not isinstance(confirmation,dict) or set(confirmation) != {
                'kind','confirmed','original_request','original_request_sha256',
                'target','target_sha256','direction_source'}
                or confirmation['kind']!='explicit-user-target-v1'
                or confirmation['confirmed'] is not True
                or confirmation['direction_source']!='user'
                or proposal.get('action_source')!='user_confirmed_target'
                or not isinstance(confirmation['original_request'],str)
                or not confirmation['original_request'].strip()
                or confirmation['original_request_sha256']!=_digest(confirmation['original_request'])
                or confirmation['target']!=owned['request']
                or confirmation['target_sha256']!=provenance['request_sha256']
                or proposal['action']['intent_span']!=confirmation['target']):
            raise ValueError('Confirmed target or original request changed after review')
    elif proposal.get('action_source')=='user_confirmed_target':
        raise ValueError('Confirmed target provenance is missing')
    if "induction" in proposal:
        induction.revalidate_category(proposal, scope, original_categories)
    return deepcopy(group)


def rank_groups(ids, scores, groups, index, limit=10, *, original_categories=None):
    """One cached score vector, additive bounded controls, hard exclusion wins."""
    if (not ids or len(ids) != len(scores) or len(ids) != len(set(ids))
            or any(type(i) is not int for i in ids)
            or any(not isinstance(s, (int, float)) or not math.isfinite(s) for s in scores)):
        raise ValueError("One score per distinct catalogue item is required")
    base = dict(zip(ids, normalize_scores(scores)))
    adjusted, excluded = dict(base), set()
    for group in groups:
        validate_group(group, index, ids, original_categories)
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


def install_semantic_routes(app, demo, *, infer_factory=None, category_infer_factory=None, allow_local_models=True):
    """Session-scoped prototype. Existing A-E and literal topic state are untouched."""
    from feedctrl.category_provider import CategoryProvider
    category_provider = CategoryProvider(category_infer_factory, allow_local_models=allow_local_models)
    configured_adapter = None
    configured_adapter_lock = threading.Lock()

    def configured_infer():
        # A configured app owns one run. Never replenish a paid call cap by
        # reconstructing a transport on each preview or concurrent request.
        nonlocal configured_adapter
        with configured_adapter_lock:
            if configured_adapter is None:
                if infer_factory is None:
                    raise ParserOperationalError("No authorized configured model adapter is installed")
                infer, provenance = infer_factory()
                if (not callable(infer) or not isinstance(provenance, dict)
                        or not all(isinstance(provenance.get(k), str) and provenance[k]
                                   for k in ("backend", "model", "digest"))):
                    raise ValueError("Configured adapter omitted model provenance")
                configured_adapter = infer, deepcopy(provenance)
            return configured_adapter[0], deepcopy(configured_adapter[1])

    def state_for(token, user):
        state = demo.user_state(token, user)
        if demo.topic_index is None:
            raise HTTPException(503, "Caption sidecar metadata is required")
        for key, value in (("semantic_groups", []), ("semantic_revision", 0),
                           ("semantic_pending", None), ("semantic_history", []),
                           ("semantic_definition_pending", None)):
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
        result = rank_groups(ids, scores, groups, demo.topic_index, original_categories=demo.items)
        for item in result["items"]:
            item["categories"] = demo.items[item["item_id"]]
            item["source_text"] = demo.source_text(item["item_id"])
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
            "configured_model": (os.getenv("FEEDCTRL_STEERING_MODEL", "qwen2.5-coder:7b-instruct")
                                 if allow_local_models else None),
            "local_models_allowed": allow_local_models,
            "category_adapter_available": category_infer_factory is not None,
            "external_adapter_available": infer_factory is not None}

    def review_source_binding():
        # Bind even empty clear/undo plans to the source and original category
        # content used to render the reviewed feed, not only to item IDs.
        index = demo.topic_index
        try:
            catalogue = _catalogue(index)
            return _digest({"source_sha256": index["sha256"], "catalogue": catalogue,
                            "original_categories": [[i, demo.items[i]] for i in sorted(demo.items)]})
        except (KeyError, TypeError, UnicodeError) as exc:
            raise ValueError("Invalid current source or category inventory") from exc

    def review(state, user, groups, history_action="none", proposal=None):
        preview_feed = feed(user, groups)  # validate before installing a review token
        source_binding = review_source_binding()
        plan_id = secrets.token_urlsafe(24)
        state["semantic_pending"] = {"id": plan_id, "created": time.monotonic(),
            "revision": state["semantic_revision"], "groups": deepcopy(groups), "history_action": history_action,
            "preview_nonce": state.get("semantic_preview_nonce"), "source_binding": source_binding}
        scope = sorted({item for group in groups for item in group["scope_ids"]})
        return {"ready": True, "applied": False, "plan_id": plan_id, "history_action": history_action,
            "groups": deepcopy(groups), "proposal": proposal, "feed": preview_feed,
            # Display only: what each item in the reviewed scope says. Not sealed, not approved.
            "scope_items": [{"item_id": item, "source_text": demo.source_text(item, full=True)} for item in scope],
            "evidence_context": evidence_context(proposal),
            "note": "Only the declared supplied items were assessed; quotes are not relevance proof."}

    def evidence_context(proposal, index=None):
        """Read-only display aid: the full supplied field around each cited quote.

        An exact quotation proves only that the text exists. A reviewer needs the
        surrounding field (for example a negation just before the quote) to judge
        meaning. Return the complete field, including all repeated occurrences and
        distant qualifiers; a prefix or quote window can hide contrary meaning.
        This is not part of the sealed group and never affects approval.
        Definition routes pass their already-validated candidate scope explicitly;
        an empty supplied index must not fall back to the full catalogue.
        """
        index = demo.topic_index if index is None else index
        rows = []
        for e in (proposal or {}).get("evidence") or []:
            item = index["items"].get(e.get("item_id")) if index else None
            text = item["fields"].get(e.get("field")) if item else None
            text = text if isinstance(text, str) else None
            rows.append({"item_id": e.get("item_id"), "field": e.get("field"), "quote": e.get("quote"),
                "supplied_field_text": text,
                "truncated": False,
                "quote_present": bool(text and isinstance(e.get("quote"), str) and e["quote"] and e["quote"] in text),
                "semantic_check": "not performed: quote custody only; a human must judge meaning"})
        return rows

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
        if body.backend == "ollama" and not allow_local_models:
            raise HTTPException(403, "Local models are disabled in this application; no inference was attempted")
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
            confirmation = confirmed_target_context(body)
            if body.backend == "configured_model" and body.action_source not in ("model", "confirmed"):
                raise ValueError("Configured adapter requires model-interpreted action; no fallback")
            if body.backend != "configured_model" and body.action_source == "model":
                raise ValueError("Model action source requires the configured adapter")
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
                if body.backend == "configured_model":
                    # Operator-selected transport, never request-supplied URLs or keys.
                    infer, provenance = configured_infer()
                else:
                    infer, provenance = make_local_ollama_infer(os.getenv("FEEDCTRL_STEERING_MODEL", "qwen2.5-coder:7b-instruct"), timeout=90)
                def tracked_infer(payload, schema):
                    # Own raw receipts; these are returned only to this session's caller.
                    try:
                        raw = _response_snapshot(infer(deepcopy(payload), deepcopy(schema)))
                    except RecursionError as exc:
                        raise ValueError('Model response exceeds JSON nesting budget') from exc
                    calls.append({"request_sha256": _digest(payload), "schema_sha256": _digest(schema),
                        "response_sha256": _digest(raw), "raw_response": deepcopy(raw)})
                    return raw
                grounding_request = body.confirmed_target if confirmation else body.text
                if confirmation:
                    action = {'operation':body.operation,'strength':body.strength,
                              'intent_span':grounding_request}
                    question = ''
                elif body.action_source == "manual":
                    # Explicit ablation/user choice, never a fallback after model failure.
                    action = {"operation": body.operation, "strength": body.strength, "intent_span": body.text}
                    question = ""
                else:
                    action, question = interpret_action(body.text, tracked_infer)
                # Do not start a second provider call for a request that a newer
                # review or reset already superseded while action inference ran.
                # Recheck under the state lock, then release it before inference.
                with demo.lock:
                    state = state_for(x_session_id, body.user_id)
                    if state["semantic_revision"] != revision or state.get("semantic_preview_nonce") != nonce:
                        raise HTTPException(409, "Preferences changed during inference; review again")
                if action is None:
                    return {"ready": False, "applied": False, "status": "clarify", "reason": question,
                            "model_calls": calls, "model_provenance": provenance}
                proposal = propose_indirect(grounding_request, action, index, tracked_infer, model_provenance=provenance)
                proposal["action_source"] = 'user_confirmed_target' if confirmation else body.action_source
                if confirmation:
                    proposal['target_confirmation'] = deepcopy(confirmation)
                if proposal["status"] != "review":
                    return {"ready": False, "applied": False, **proposal, "model_calls": calls}
                request = grounding_request
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
                        "model_calls": calls if body.backend != "manual_category" else []}
        except ValueError as exc:
            if body.backend != "manual_category":
                return {"ready": False, "applied": False, "status": "error",
                    "reason": f"Model proposal rejected ({type(exc).__name__}): {exc}",
                    "model_calls": calls, "model_provenance": provenance}
            raise HTTPException(422, str(exc)) from exc
        except ParserOperationalError as exc:
            raise HTTPException(422 if body.backend == "manual_category" else 502,
                f"Semantic proposal failed ({type(exc).__name__}); no preferences changed: {exc}") from exc

    @app.post("/api/semantic/induction/preview")
    def induction_preview(body: InductionPreview, x_session_id: str | None = Header(default=None)):
        try:
            category_provider.require_available()
        except ParserOperationalError as exc:
            raise HTTPException(503, str(exc)) from exc
        calls = []
        with demo.lock:
            state = state_for(x_session_id, body.user_id)
            revision, nonce = state["semantic_revision"], secrets.token_urlsafe(16)
            state["semantic_preview_nonce"] = nonce
            state["semantic_pending"] = None
            existing = deepcopy(state["semantic_groups"])
            try:
                index = scoped_index(demo.topic_index, body.candidate_ids)
                inventory = induction.projected_inventory(index, demo.items, existing)
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from exc
        if (body.strength != "none" if body.operation == "exclude" else body.strength not in STRENGTH_WEIGHTS):
            raise HTTPException(422, "Exclusion has strength none; boost/reduce need a graded strength")
        try:
            infer, provenance, calls = category_provider.stage(
                "combined", os.getenv("FEEDCTRL_STEERING_MODEL", "qwen2.5-coder:7b-instruct"))
            envelope = induction.producer.propose_category(body.objective, index, infer,
                model_provenance=provenance, existing_categories=inventory,
                max_items=induction.MAX_ITEMS, max_bytes=induction.PRODUCER_BYTES)
            if envelope["status"] != "review":
                return {"ready": False, "applied": False, "status": envelope["status"],
                    "reason": envelope["reason"], "induction": envelope, "model_calls": deepcopy(calls)}
            control = induction.category_as_control(envelope, body.objective, index, inventory,
                                                    body.operation, body.strength, provenance)
            control["induction"]["model_calls"] = deepcopy(calls)
            group = seal_group(envelope["proposal"]["label"], body.objective, control, index, demo.items)
            groups = ([] if body.mode == "replace" else existing) + [group]
            if len(groups) > 8:
                raise ValueError("At most eight active semantic groups")
            with demo.lock:
                state = state_for(x_session_id, body.user_id)
                if state["semantic_revision"] != revision or state.get("semantic_preview_nonce") != nonce:
                    raise HTTPException(409, "Preferences changed during induction; review again")
                current_scope = scoped_index(demo.topic_index, body.candidate_ids)
                current_inventory = induction.projected_inventory(current_scope, demo.items, state["semantic_groups"])
                induction.producer.validate_current_source(envelope, body.objective, current_scope, current_inventory)
                result = review(state, body.user_id, groups, proposal=control)
                state["semantic_pending"]["induction_context"] = {
                    "candidate_ids": sorted(body.candidate_ids), "inventory_sha256": _digest(inventory)}
                return {**result, "induction": deepcopy(envelope), "model_calls": deepcopy(calls),
                        "action_source": "manual", "research_note": "Generated definition and membership are hypotheses; review is mandatory."}
        except (ValueError, ParserOperationalError) as exc:
            return {"ready": False, "applied": False, "status": "error",
                "reason": f"Category induction rejected ({type(exc).__name__}): {exc}",
                "model_calls": deepcopy(calls)}

    @app.post("/api/semantic/history/preview")
    def history(body: SemanticHistory, x_session_id: str | None = Header(default=None)):
        with demo.lock:
            state = state_for(x_session_id, body.user_id)
            if body.action == "undo" and not state["semantic_history"]:
                return {"ready": False, "applied": False, "reason": "No earlier applied semantic profile"}
            try:
                result = review(state, body.user_id,
                    state["semantic_history"][-1] if body.action == "undo" else [], body.action)
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc
            state["semantic_preview_nonce"] = None
            state["semantic_pending"]["preview_nonce"] = None
            return result

    @app.post("/api/semantic/apply")
    def apply(body: SemanticApply, x_session_id: str | None = Header(default=None)):
        with demo.lock:
            state = state_for(x_session_id, body.user_id)
            pending = state["semantic_pending"]
            if (not pending or pending["id"] != body.plan_id or pending["revision"] != state["semantic_revision"]
                    or "preview_nonce" not in pending or pending["preview_nonce"] != state.get("semantic_preview_nonce")
                    or time.monotonic() - pending["created"] > 300):
                raise HTTPException(409, "Review expired or changed; review again")
            try:
                if pending.get("source_binding") != review_source_binding():
                    raise ValueError("Source or category inventory changed; review again")
                context = pending.get("induction_context")
                if context:
                    scope = scoped_index(demo.topic_index, context["candidate_ids"])
                    inventory = induction.projected_inventory(scope, demo.items, state["semantic_groups"])
                    if _digest(inventory) != context["inventory_sha256"]:
                        raise ValueError("Category inventory changed since induction review")
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

    from feedctrl.staged_routes import install_staged_routes
    install_staged_routes(app,demo,state_for,review,evidence_context=evidence_context,category_provider=category_provider)
