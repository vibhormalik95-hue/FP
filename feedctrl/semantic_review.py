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
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator

from feedctrl.controls import ParserOperationalError, normalize_scores
from feedctrl.indirect_grounding import (APPLICATION_CHECK, BUDGET_CHECK, BUDGET_REASON, COMMAND_NEGATION,
                                         GUARD_CHECK, GUARD_PATTERN_WORDS, evidence_budget,
                                         GUARD_REASON, MODEL_REPORT, PROVIDER_FAILURE, REPLY_REJECTED,
                                         _catalogue, _digest, _response_snapshot, clean_page_text,
                                         failure_sentence, make_local_ollama_infer, propose_indirect,
                                         rejected_call)
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
# What the action prompt asks and no application check can test: the direction,
# whether a command is negated or a request is a quota or a condition, and
# whether a clarification is needed. For these the model alone decides. The
# application checks the schema, the declared control and that the span is a
# verbatim part of the request; the wording guard runs before this call.


MAX_GROUPS = 8
REVIEW_WINDOW_SECONDS = 300
LIMIT_CHECK = 'At most eight controls stay applied'
NAME_CHECK = 'The name of the new control is not the name of an applied control'


def scope_effect(label, members, outside, scope_size):
    """Display data: a control changes only the items of its evidence scope.

    ``outside`` lists the items outside the scope that carry the same category
    or terms. They do not change; the page states this next to the control.
    """
    message = f'This control selects {len(members)} of the {scope_size} items in the scope.'
    if outside:
        message += (f' {len(outside)} more items with the same category or terms are outside the scope. '
                    'They do not change.')
    return {'label': label, 'in_scope_item_ids': list(members), 'outside_scope_item_ids': list(outside),
            'message': message}


def printable_request(value):
    """The request goes to a provider and onto the review screen. A control or
    format character can hide or reorder words there, so it is refused."""
    if any(unicodedata.category(c) in {'Cf', 'Cs'}
           or (unicodedata.category(c) == 'Cc' and c not in '\n\r\t') for c in value):
        raise ValueError('Use printable request text without control or format characters')
    return value


def collision_reason(label):
    """The plain sentence for a name that an applied control already has."""
    return (f'An applied control already has the name "{clean_page_text(label, 80)}". Nothing was applied. '
            'Choose another name for this control, or remove the applied control first.')


def same_manual_control(group, category, operation):
    """True when an applied group is the manual control of this category and operation.

    Such a group is the earlier version of the same control, so a new manual
    control with the same name replaces it (the strength can differ).
    """
    proposal = group["proposal"]
    return (proposal["provenance"]["model"].get("backend") == "manual_category"
            and group["request"] == category and proposal["action"]["operation"] == operation)


def limit_reason(applied, added):
    """The plain sentence for a plan that would exceed the limit of applied controls."""
    return (f'At most {MAX_GROUPS} controls can be applied at one time. {applied} stay applied and this request '
            f'adds {added}. Remove a control first, or choose to replace the applied controls.')


class TooManyControls(ValueError):
    """A valid proposal that cannot be added: the limit of applied controls is reached."""

    def __init__(self, applied, added):
        super().__init__(limit_reason(applied, added))
        self.applied, self.added = applied, added


class OperatorMessage(ParserOperationalError):
    """An operational sentence that this application wrote itself. It holds no provider text."""
    page_safe = True


class ProviderFailure(HTTPException):
    """HTTP 502 for a provider call that failed before any reply could be used.

    The status code and the text ``detail`` are what earlier callers read. The
    response body also carries the fields of a not-ready answer (``body``), so
    that the page can say that a call was made and that it failed.
    """

    def __init__(self, detail, body):
        super().__init__(502, detail)
        self.body = body


def provider_failure_response(_request, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse({'detail': exc.detail, **exc.body}, status_code=exc.status_code,
                        headers={'Cache-Control': 'no-store'})


def watch_provider(infer, raised):
    """Wrap one stage callable so that an exception of the provider is kept as an object.

    The category provider records only the text of a failure. The routes need
    the exception itself to decide whether its sentence may be shown.
    """
    def watched(payload, schema):
        try:
            return infer(payload, schema)
        except Exception as exc:
            raised.append(exc)
            raise
    return watched


def page_calls(calls, raised):
    """Call records for a response: the raw failure text of a provider is not sent to the page."""
    shown, failures = deepcopy(calls), list(raised)
    for call in shown:
        if isinstance(call, dict) and call.get('status') == 'error':
            call['error'] = failure_sentence(failures.pop(0)) if failures else 'The call to the provider failed.'
    return shown


def stage_outcome(exc, calls, raised):
    """``(reason, outcome_source)`` for an exception in a route that uses the category provider."""
    if raised and raised[-1] is exc:
        return failure_sentence(exc), PROVIDER_FAILURE
    returned = any(isinstance(call, dict) and call.get('status') == 'returned_json' for call in calls)
    if isinstance(exc, ParserOperationalError):
        # Written by the application or by the provider wrapper, never by a reply.
        return failure_sentence(exc), APPLICATION_CHECK if not calls else PROVIDER_FAILURE
    # ``application_check`` only when no call was begun: the page says then that no model was called.
    return clean_page_text(exc), REPLY_REJECTED if returned else PROVIDER_FAILURE if calls else APPLICATION_CHECK


def plan_notes(groups, catalogue_size):
    """Things a reviewer should see about a whole plan. Display only; they never block.

    A note names two controls that reach the same items, says what the policy
    does with them (removal takes priority; rank adjustments add up), and one
    note gives the total share of the catalogue that is removed when it is more
    than half. The limits of one request are checked elsewhere; these notes
    cover the controls that are already applied together with the new ones.
    """
    notes = []
    for a, first in enumerate(groups):
        for second in groups[a + 1:]:
            shared = sorted(set(first['proposal']['item_ids']) & set(second['proposal']['item_ids']))
            if not shared:
                continue
            kinds = {first['proposal']['action']['operation'], second['proposal']['action']['operation']}
            names = f'"{first["label"]}" and "{second["label"]}"'
            if kinds == {'boost', 'exclude'}:
                kind, effect = 'conflict', 'One control shows more of them and the other removes them. Removal takes priority, so the increase has no effect on them.'
            elif kinds == {'boost', 'reduce'}:
                kind, effect = 'conflict', 'One control shows more of them and the other shows less. Both adjustments apply and partly cancel.'
            elif kinds == {'reduce', 'exclude'}:
                kind, effect = 'overlap', 'One control shows less of them and the other removes them. Removal takes priority.'
            elif kinds == {'exclude'}:
                kind, effect = 'overlap', 'Both controls remove them.'
            else:
                kind, effect = 'overlap', 'Both controls adjust their rank in the same direction, and the adjustments add up.'
            notes.append({'kind': kind, 'controls': [first['label'], second['label']], 'item_ids': shared,
                          'message': f'The controls {names} both reach the items {", ".join(map(str, shared))}. {effect}'})
    removed = sorted({item for group in groups if group['proposal']['action']['operation'] == 'exclude'
                      for item in group['proposal']['item_ids']})
    if catalogue_size and len(removed) > catalogue_size / 2:
        notes.append({'kind': 'broad_total', 'controls': [], 'item_ids': removed,
                      'message': f'After this plan, {len(removed)} of the {catalogue_size} items of the catalogue are removed.'})
    return notes


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

    @field_validator("text")
    @classmethod
    def printable(cls, value):
        return printable_request(value)


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
    if proposal.get("grounding") == "vocabulary":
        from feedctrl import vocabulary_grounding  # imported here: that module imports this one
        vocabulary_grounding.revalidate_control(proposal, scope)
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
                    raise OperatorMessage("No authorized configured model adapter is installed")
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
        index = demo.topic_index
        try:
            return _digest({"source_sha256": index["sha256"], "catalogue": _catalogue(index),
                            "original_categories": [[i, demo.items[i]] for i in sorted(demo.items)]})
        except (KeyError, TypeError, UnicodeError) as exc:
            raise ValueError("Invalid current source or category inventory") from exc

    def review(state, user, groups, history_action="none", proposal=None, proposals=None):
        # ``proposals`` is for a review that adds several groups at once: the
        # cited field of every one of them is shown, not only of one proposal.
        preview_feed = feed(user, groups)  # validate before installing a review token
        plan_id = secrets.token_urlsafe(24)
        state["semantic_pending"] = {"id": plan_id, "created": time.monotonic(),
            "revision": state["semantic_revision"], "groups": deepcopy(groups), "history_action": history_action,
            "preview_nonce": state.get("semantic_preview_nonce"), "source_binding": review_source_binding()}
        scope = sorted({item for group in groups for item in group["scope_ids"]})
        from feedctrl import vocabulary_grounding  # imported here: that module imports this one
        return {"ready": True, "applied": False, "plan_id": plan_id, "history_action": history_action,
            "groups": deepcopy(groups), "proposal": proposal, "feed": preview_feed,
            # Display only: what each item in the reviewed scope says and carries. Not sealed, not
            # approved. ``categories`` is the catalogue category that the manual control reads;
            # ``labels`` are the category and tag values of the source metadata.
            "scope_items": [{"item_id": item, "source_text": demo.source_text(item, full=True),
                             "categories": list(demo.items.get(item, [])),
                             "labels": vocabulary_grounding.item_labels(demo.topic_index["items"][item]["fields"])}
                            for item in scope],
            "evidence_context": (evidence_context(proposal) if proposals is None else
                                 [row for each in proposals for row in evidence_context(each)]),
            # Display only: overlaps and contradictions between the controls of the whole plan.
            "plan_notes": plan_notes(groups, len(demo.items)),
            # The reviewer must approve within this time; Apply refuses an older review.
            "review_window_seconds": REVIEW_WINDOW_SECONDS,
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
        manual = body.backend == "manual_category"
        calls, provenance, checks = [], None, []
        # One entry for each provider invocation that was begun, also one that
        # raised. ``failed`` holds the exception that a provider call raised, so
        # that a provider failure is never taken for an application check.
        attempts, failed, stage = [], [], ["interpretation"]
        preview_scope = None
        guarded_infer = None
        with demo.lock:
            state = state_for(x_session_id, body.user_id)
            revision = state["semantic_revision"]
            nonce = secrets.token_urlsafe(16)
            state["semantic_preview_nonce"] = nonce
            state["semantic_pending"] = None
            existing = deepcopy(state["semantic_groups"])
            guarded_infer = getattr(infer_factory, 'preview_scope_infer', None) if body.backend == 'configured_model' else None
            if guarded_infer is not None:
                def preview_is_current():
                    current = state_for(x_session_id, body.user_id)
                    return (current['semantic_revision'] == revision
                            and current.get('semantic_preview_nonce') == nonce)
                try:
                    preview_scope = guarded_infer.open_preview_scope(
                        state_lock=demo.lock, validate=preview_is_current,
                        identity=(x_session_id, body.user_id, nonce))
                except ValueError as exc:
                    raise HTTPException(409, 'Preview scope unavailable') from exc
            try:
                index = scoped_index(demo.topic_index, body.candidate_ids)
            except ValueError as exc:
                if preview_scope is not None: preview_scope.close()
                raise HTTPException(422, str(exc)) from exc
            except BaseException:
                if preview_scope is not None: preview_scope.close()
                raise

        def not_ready(status, reason, source, **extra):
            value = {"ready": False, "applied": False, "status": status, "reason": reason,
                     "item_ids": [], "checks": deepcopy(checks),
                     "model_calls": deepcopy(calls), "model_provenance": deepcopy(provenance),
                     "calls_attempted": len(attempts), "call_attempts": deepcopy(attempts),
                     "outcome_source": source, "failed_stage": stage[0]}
            value.update(extra)
            return value

        try:
            confirmation = confirmed_target_context(body)
            if body.backend == "configured_model" and body.action_source not in ("model", "confirmed"):
                raise ValueError("Configured adapter requires model-interpreted action; no fallback")
            if body.backend != "configured_model" and body.action_source == "model":
                raise ValueError("Model action source requires the configured adapter")
            # The person names this control. In merge mode a name that an applied
            # control already has is a collision, reported before any call: only
            # the same manual control (same category and operation) is replaced
            # by its new version. Every other applied control stays, so the
            # limit is also known before any call.
            name = body.label.strip().casefold()
            named = [] if body.mode == "replace" else [g for g in existing if g["label"].casefold() == name]
            if named and not (manual and all(same_manual_control(g, body.category, body.operation) for g in named)):
                checks.append({"check": NAME_CHECK, "passed": False, "detail": clean_page_text(body.label, 80)})
                return not_ready("label_collision", collision_reason(body.label.strip()), APPLICATION_CHECK)
            kept = [] if body.mode == "replace" else [g for g in existing if g not in named]
            if len(kept) + 1 > MAX_GROUPS:
                raise TooManyControls(len(kept), 1)
            if manual:
                if body.category not in demo.categories:
                    raise ValueError("Manual baseline requires an existing category ID")
                action = {"operation": body.operation, "strength": body.strength, "intent_span": body.category}
                if ((action["strength"] != "none") if body.operation == "exclude"
                    else action["strength"] not in STRENGTH_WEIGHTS):
                    raise ValueError("Invalid manual strength")
                members = [i for i in index["items"] if body.category in demo.items[i]]
                if not members:
                    return {"ready": False, "applied": False, "status": "no_match", "reason": "No scoped item has that category",
                            "calls_attempted": 0, "outcome_source": APPLICATION_CHECK, "model_calls": []}
                outside = sorted(i for i in demo.items if i not in index["items"] and body.category in demo.items[i])
                checks.append({"check": "The chosen category exists in the catalogue", "passed": True, "detail": ""})
                checks.append({"check": "The selected items are exactly the scope items that carry the category",
                               "passed": True, "detail": f"{len(members)} of {len(index['items'])} scope items"})
                scope_effects = [scope_effect(body.label.strip(), members, outside, len(index["items"]))]
                proposal = {"status": "review", "requires_review": True, "reason": "Exact existing-category baseline, no model",
                    "action": action, "item_ids": members, "evidence": [], "provenance": {
                        "source_sha256": index["sha256"], "catalogue_sha256": _digest(_catalogue(index)),
                        "request_sha256": _digest(body.category), "action_sha256": _digest(action),
                        "model": {"backend": "manual_category", "model": "none", "digest": "not_applicable"}}}
                request = body.category
            else:
                grounding_request = body.confirmed_target if confirmation else body.text
                # The wording guard runs before any provider is asked. A stated and
                # confirmed target is the explicit interpretation that the guard asks
                # for, so in that mode the guard reads the target, not the original words.
                checks.append({"check": GUARD_CHECK, "passed": not COMMAND_NEGATION.search(grounding_request),
                               "detail": GUARD_PATTERN_WORDS})
                if not checks[-1]["passed"]:
                    return not_ready("clarify", GUARD_REASON, APPLICATION_CHECK)
                # The evidence budget is also known before the first call: no call
                # is spent on a request whose items cannot be sent in the evidence call.
                passed, detail = evidence_budget(grounding_request, index)
                checks.append({"check": BUDGET_CHECK, "passed": passed, "detail": detail})
                if not passed:
                    return not_ready("clarify", BUDGET_REASON, APPLICATION_CHECK)
                if body.backend == "configured_model":
                    # Operator-selected transport, never request-supplied URLs or keys.
                    infer, provenance = configured_infer()
                    if getattr(infer, 'requires_preview_scope', False) is True:
                        if preview_scope is None or infer is not guarded_infer:
                            raise ValueError('Configured preview scope unavailable')
                        infer = preview_scope
                else:
                    infer, provenance = make_local_ollama_infer(os.getenv("FEEDCTRL_STEERING_MODEL", "qwen2.5-coder:7b-instruct"), timeout=90)
                def tracked_infer(payload, schema):
                    # Own raw receipts; these are returned only to this session's caller.
                    attempt = {"stage": stage[0], "status": "started"}
                    attempts.append(attempt)
                    try:
                        raw = infer(deepcopy(payload), deepcopy(schema))
                    except Exception as exc:
                        attempt.update(status="failed", error_type=type(exc).__name__)
                        failed.append(exc)
                        raise
                    try:
                        bounded = _response_snapshot(raw)
                    except (TypeError, ValueError, RecursionError) as exc:
                        # A reply came back and is not bounded JSON. It stays visible as text.
                        attempt["status"] = "reply_rejected"
                        calls.append(rejected_call(payload, schema, raw))
                        if stage[0] == "evidence":
                            return raw  # the evidence step rejects it itself and records the check
                        raise ValueError("Response is not bounded finite JSON") from exc
                    raw = bounded
                    attempt["status"] = "returned"
                    calls.append({"request_sha256": _digest(payload), "schema_sha256": _digest(schema),
                        "response_sha256": _digest(raw), "raw_response": deepcopy(raw)})
                    return raw
                if confirmation:
                    action = {'operation':body.operation,'strength':body.strength,
                              'intent_span':grounding_request}
                    question = ''
                elif body.action_source == "manual":
                    # Explicit ablation/user choice, never a fallback after model failure.
                    action = {"operation": body.operation, "strength": body.strength, "intent_span": body.text}
                    question = ""
                else:
                    try:
                        action, question = interpret_action(body.text, tracked_infer)
                    except ValueError as exc:
                        if not failed:
                            # The reply came back and the application rejected it. Keep that visible.
                            checks.append({"check": "The action reply has the declared fields, a declared control "
                                                    "and a span that is a verbatim part of the request",
                                           "passed": False, "detail": clean_page_text(exc, 200)})
                        raise
                    checks.append({"check": "The action reply has the declared fields, a declared control "
                                            "and a span that is a verbatim part of the request",
                                   "passed": True, "detail": ""})
                # Do not start a second provider call for a request that a newer
                # review or reset already superseded while action inference ran.
                # Recheck under the state lock, then release it before inference.
                with demo.lock:
                    state = state_for(x_session_id, body.user_id)
                    if state["semantic_revision"] != revision or state.get("semantic_preview_nonce") != nonce:
                        raise HTTPException(409, "Preferences changed during inference; review again")
                if action is None:
                    # The question is the reply's own text; the application did not write it.
                    return not_ready("clarify", question, MODEL_REPORT, reply_reason=question)
                stage[0] = "evidence"
                proposal = propose_indirect(grounding_request, action, index, tracked_infer, model_provenance=provenance)
                # Checks of the action stage first, then every check of the evidence stage
                # (the evidence stage repeats the wording guard for callers that use it alone).
                checks.extend(row for row in proposal.pop("checks") if row["check"] not in (GUARD_CHECK, BUDGET_CHECK))
                proposal.pop("call_attempted", None)
                proposal["action_source"] = 'user_confirmed_target' if confirmation else body.action_source
                if confirmation:
                    proposal['target_confirmation'] = deepcopy(confirmation)
                if proposal["status"] != "review":
                    source = proposal.pop("outcome_source")
                    extra = {"reply_reason": proposal["reason"]} if source == MODEL_REPORT else {}
                    return {**not_ready(proposal["status"], proposal["reason"], source, **extra),
                            **{key: value for key, value in proposal.items() if key not in ("status", "reason")}}
                scope_effects = []
                request = grounding_request
            group = seal_group(body.label, request, proposal, index, demo.items)
            groups = [g for g in kept if g["label"].casefold() != group["label"].casefold()] + [group]
            if len(groups) > MAX_GROUPS:
                raise TooManyControls(len(groups) - 1, 1)
            with demo.lock:
                state = state_for(x_session_id, body.user_id)
                if state["semantic_revision"] != revision or state.get("semantic_preview_nonce") != nonce:
                    raise HTTPException(409, "Preferences changed during inference; review again")
                return {**review(state, body.user_id, groups, proposal=proposal),
                        "model_calls": [] if manual else calls, "checks": deepcopy(checks),
                        "calls_attempted": len(attempts), "call_attempts": deepcopy(attempts),
                        "scope_effects": scope_effects}
        except TooManyControls as exc:
            # Its own outcome for every method, also the manual one: a plain sentence, not an error.
            checks.append({"check": LIMIT_CHECK, "passed": False,
                           "detail": f"{exc.applied} stay applied; this request adds {exc.added}"})
            return not_ready("limit", str(exc), APPLICATION_CHECK)
        except ValueError as exc:
            if manual:
                raise HTTPException(422, str(exc)) from exc
            if failed and failed[-1] is exc:
                return not_ready("error", failure_sentence(exc), PROVIDER_FAILURE)
            # An application sentence about the request or about the reply; it holds no provider text.
            return not_ready("error", f"Model proposal rejected ({type(exc).__name__}): {clean_page_text(exc)}",
                             REPLY_REJECTED if attempts else APPLICATION_CHECK)
        except ParserOperationalError as exc:
            if manual:
                raise HTTPException(422, str(exc)) from exc
            # HTTP 502: the provider could not be reached or its call failed. The
            # text names the failure only through a page-safe sentence or type names.
            sentence = failure_sentence(exc)
            raise ProviderFailure(
                f"Semantic proposal failed ({type(exc).__name__}); no preferences changed: {sentence}",
                not_ready("error", sentence, PROVIDER_FAILURE)) from exc
        except HTTPException:
            raise
        except Exception as exc:
            if failed and failed[-1] is exc:
                # A provider raised an unexpected type: a failed call, not a crash of the application.
                return not_ready("error", failure_sentence(exc), PROVIDER_FAILURE)
            raise
        finally:
            if preview_scope is not None:
                preview_scope.close()

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
        raised = []

        def not_ready(status, reason, source, **extra):
            return {"ready": False, "applied": False, "status": status, "reason": reason,
                    "model_calls": page_calls(calls, raised), "calls_attempted": len(calls),
                    "outcome_source": source, "failed_stage": "combined", **extra}

        if body.mode != "replace" and len(existing) + 1 > MAX_GROUPS:
            # A new category always adds a control, so the limit is known before the call.
            return not_ready("limit", limit_reason(len(existing), 1), APPLICATION_CHECK,
                             checks=[{"check": LIMIT_CHECK, "passed": False,
                                      "detail": f"{len(existing)} stay applied; this request adds 1"}])
        try:
            infer, provenance, calls = category_provider.stage(
                "combined", os.getenv("FEEDCTRL_STEERING_MODEL", "qwen2.5-coder:7b-instruct"))
            envelope = induction.producer.propose_category(body.objective, index, watch_provider(infer, raised),
                model_provenance=provenance, existing_categories=inventory,
                max_items=induction.MAX_ITEMS, max_bytes=induction.PRODUCER_BYTES)
            if envelope["status"] != "review":
                if raised:
                    # The producer keeps only the type of a failed call; show the provider's sentence.
                    return not_ready("error", failure_sentence(raised[-1]), PROVIDER_FAILURE, induction=envelope)
                source = (APPLICATION_CHECK if not calls else
                          REPLY_REJECTED if envelope["status"] in ("error", "duplicate") else MODEL_REPORT)
                if envelope["status"] == "duplicate" and envelope["reason"].startswith("Label already exists"):
                    # A name collision is its own outcome with a plain sentence.
                    from feedctrl.staged_routes import duplicate_name  # that module imports this one
                    reason, name_checks = duplicate_name(calls)
                    return not_ready("duplicate", reason, source, induction=envelope, checks=name_checks)
                return not_ready(envelope["status"], envelope["reason"], source, induction=envelope)
            control = induction.category_as_control(envelope, body.objective, index, inventory,
                                                    body.operation, body.strength, provenance)
            control["induction"]["model_calls"] = deepcopy(calls)
            group = seal_group(envelope["proposal"]["label"], body.objective, control, index, demo.items)
            groups = ([] if body.mode == "replace" else existing) + [group]
            if len(groups) > MAX_GROUPS:
                raise TooManyControls(len(groups) - 1, 1)
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
                        "calls_attempted": len(calls),
                        "action_source": "manual", "research_note": "Generated definition and membership are hypotheses; review is mandatory."}
        except TooManyControls as exc:
            return not_ready("limit", str(exc), APPLICATION_CHECK,
                             checks=[{"check": LIMIT_CHECK, "passed": False,
                                      "detail": f"{exc.applied} stay applied; this request adds {exc.added}"}])
        except (ValueError, ParserOperationalError) as exc:
            reason, source = stage_outcome(exc, calls, raised)
            return not_ready("error", f"Category induction rejected ({type(exc).__name__}): {reason}", source)

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
                    or time.monotonic() - pending["created"] > REVIEW_WINDOW_SECONDS):
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

    app.add_exception_handler(ProviderFailure, provider_failure_response)
    from feedctrl.staged_routes import install_staged_routes
    install_staged_routes(app,demo,state_for,review,evidence_context=evidence_context,category_provider=category_provider)
    from feedctrl.vocabulary_routes import install_vocabulary_routes
    install_vocabulary_routes(app, demo, state_for, review, configured_infer=configured_infer,
                              provider_available=infer_factory is not None)

    from feedctrl.combined_routes import install_combined_routes
    install_combined_routes(app, demo, state_for, review, configured_infer=configured_infer,
                            provider_available=infer_factory is not None,
                            scope_guard=getattr(infer_factory, 'configured_flow_guard', None),
                            scope_identity=getattr(infer_factory, 'model_identity', None))
