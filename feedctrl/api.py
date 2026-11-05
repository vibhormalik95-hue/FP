"""Local, single-process research demonstrator. No held-out labels enter this API."""
from __future__ import annotations

import json
import math
import os
import secrets
import threading
import time
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator

from feedctrl.controls import DEFAULT_MODEL, ParserOperationalError, normalize_scores, parse_control, parse_profile, rerank
from feedctrl.explanations import cached_explanation
from feedctrl.semantic_controls import (TopicGroundingError, load_topic_index, manual_topic_command, match_topic,
                                        parse_topic_request, rerank_topic)
from feedctrl import semantic_workflow as steering
from feedctrl.semantic_review import install_semantic_routes
from feedctrl.synthetic_drafts import install_synthetic_routes

ROOT = Path(__file__).resolve().parents[1]
SESSION_TTL = 12 * 60 * 60
MAX_SESSIONS = 1024
CONDITIONS = {
    "A": "Item feedback", "B": "Item feedback + explanations",
    "C": "Free-text control", "D": "Editable profile", "E": "All channels",
}


def fixture_data():
    return {
        "metadata": {"source": "deterministic fixture", "is_fixture": True},
        "items": [{"item_id": i, "categories": [f"category_{i % 6}"]}
                  for i in range(1, 37)],
        "users": [{"user_id": u, "train": [u, u + 6, u + 12, u + 1],
                   "request_history": [u + 18, u + 2], "test": []}
                  for u in range(1, 4)],
    }


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: int = Field(ge=0)


class ControlRequest(Request):
    text: str = Field(min_length=1, max_length=500)
    backend: Literal["rule", "ollama"] = "rule"


class ProfileRequest(Request):
    profile: dict[str, float] = Field(max_length=200)

    @field_validator("profile")
    @classmethod
    def bounded_weights(cls, value):
        if any(len(k) > 120 or not math.isfinite(v) or not -1 <= v <= 1
               for k, v in value.items()):
            raise ValueError("Profile weights must be finite and between -1 and 1.")
        return value


class ProfileTextRequest(Request):
    text: str = Field(min_length=1, max_length=2000)
    backend: Literal["rule", "ollama"] = "rule"

    @field_validator("text")
    @classmethod
    def bounded_words(cls, value):
        if len(value.split()) > 200:
            raise ValueError("Profile must contain at most 200 words.")
        return value


class FeedbackRequest(Request):
    item_id: int = Field(ge=0)
    direction: Literal["like", "dislike", "clear"]


class TopicRequest(Request):
    text: str = Field(min_length=1, max_length=500)
    backend: Literal["manual", "ollama"] = "manual"
    operation: Literal["boost", "reduce", "exclude"] = "boost"
    strength: Literal["light", "standard", "strong"] = "standard"
    condition: Literal["C", "E"] = "C"


class SteeringPreviewRequest(Request):
    text: str = Field(default="", max_length=2000)
    backend: Literal["manual", "ollama"] = "ollama"
    mode: Literal["merge", "replace"] = "merge"
    actions: list[dict] | None = Field(default=None, max_length=8)
    bindings: list[dict] = Field(default_factory=list, max_length=8)


class SteeringHistoryRequest(Request):
    action: Literal["undo", "clear"]


class SteeringApplyRequest(Request):
    plan_id: str = Field(min_length=1, max_length=100)


class SteeringRemoveRequest(Request):
    topic: str = Field(min_length=2, max_length=80)


class DemoState:
    def __init__(self, data_path=None, model_path=None, fixture=False, semantic_path=None):
        data_path = Path(data_path or os.getenv("FEEDCTRL_DATA", ROOT / "data/processed.json"))
        model_path = Path(model_path or os.getenv("FEEDCTRL_MODEL", ROOT / "results/models/seed_42"))
        self.data = fixture_data() if fixture or not data_path.exists() else json.loads(data_path.read_text(encoding="utf-8"))
        self.items = {int(i["item_id"]): list(i["categories"]) for i in self.data["items"]}
        self.users = {int(u["user_id"]): u for u in self.data["users"]}
        self.categories = sorted({c for cats in self.items.values() for c in cats})
        meta = self.data.get("metadata", {})
        self.fixture = (bool(meta.get("is_fixture")) or meta.get("source") == "deterministic fixture"
                        or meta.get("kind") == "synthetic_fixture")
        self.model = None
        if not self.fixture and model_path.exists():
            from feedctrl.model import load_model
            self.model = load_model(model_path)
        self.sessions = {}
        self.lock = threading.RLock()
        sidecar = semantic_path or os.getenv("FEEDCTRL_CAPTION_SIDECAR")
        self.topic_index = load_topic_index(sidecar, set(self.items)) if sidecar else None

    def create_session(self):
        now = time.monotonic()
        with self.lock:
            expired = [k for k, s in self.sessions.items() if now - s["seen"] > SESSION_TTL]
            for k in expired:
                del self.sessions[k]
            if len(self.sessions) >= MAX_SESSIONS:
                raise HTTPException(503, "Session capacity reached; restart the local demo or wait for expiry.")
            token = secrets.token_urlsafe(32)
            self.sessions[token] = {"seen": now, "users": {}}
        return token

    def user_state(self, token, user_id):
        if not token or token not in self.sessions:
            raise HTTPException(401, "Session expired or missing. Reload the page to start a new session.")
        session = self.sessions[token]
        if time.monotonic() - session["seen"] > SESSION_TTL:
            del self.sessions[token]
            raise HTTPException(401, "Session expired. Reload the page.")
        if user_id not in self.users:
            raise HTTPException(404, "Unknown user.")
        session["seen"] = time.monotonic()
        return session["users"].setdefault(user_id, {
            "profile": {}, "command": {"operation": "clarify", "category": None,
                                       "strength": 0, "source": "none"}, "feedback": {},
            "profile_text": self.initial_profile(user_id),
        })

    def initial_profile(self, user_id):
        user = self.users[user_id]
        history = list(user["train"]) + list(user["request_history"])
        counts = Counter(c for i in history for c in self.items.get(i, []))
        top = ", ".join(f"{c} ({n} occurrences)" for c, n in counts.most_common(8))
        return (f"My observed interaction history contains {len(history)} items. "
                f"The most frequent category IDs in that history are {top}. "
                "These are historical observations, not stated current preferences.")

    def steering_state(self, token, user_id):
        if self.topic_index is None:
            raise HTTPException(503, "Official caption sidecar is required for catalogue steering")
        state = self.user_state(token, user_id)
        for key, value in (("steering_commands", []), ("steering_revision", 0),
                           ("steering_pending", None), ("steering_text", ""),
                           ("steering_history", []), ("steering_focus", None)):
            state.setdefault(key, value)
        return state

    def steering_feed(self, user_id, commands):
        user = self.users[user_id]
        history = list(user["train"]) + list(user["request_history"])
        ids = sorted(self.items)
        if self.model is not None:
            raw = self.model.score(history, ids)
        else:
            counts = Counter(c for item in history for c in self.items.get(item, []))
            raw = [sum(counts[c] for c in self.items[item]) + ((item * 17 + user_id * 7) % 19) / 100 for item in ids]
        result = steering.rank(ids, raw, commands, self.topic_index)
        neutral = steering.rank(ids, raw, [], self.topic_index)
        neutral_ids = {item["item_id"] for item in neutral["items"]}
        score_map = dict(zip(ids, normalize_scores(raw)))
        groups = [match_topic(self.topic_index, command)[0] for command in commands]
        for command, exposure in zip(commands, result["topic_exposure"]):
            exposure["baseline_top_k_match_count"] = len(match_topic(self.topic_index, command)[0] & neutral_ids)
        for position, item in enumerate(result["items"], 1):
            signals = [f"Source text matches {c['topic']}: {c['operation']} ({c['strength']})."
                       for c, group in zip(commands, groups) if item["item_id"] in group]
            item.update(rank=position, categories=self.items[item["item_id"]],
                        base_score=float(score_map[item["item_id"]]),
                        explanation=signals or ["No saved subject phrase matches this item's supplied text."],
                        explanation_source="source_text_policy")
        return {"mode": "Reviewed catalogue steering; separate from frozen A-E",
                "data_mode": "fixture" if self.fixture else "processed dataset",
                "model_mode": "trained model" if self.model else "deterministic diagnostic scorer",
                "category_exposure": dict(Counter(c for item in result["items"] for c in item["categories"])),
                "commands_count": len(commands), "baseline_items": neutral["items"], **result}

    @staticmethod
    def steering_snapshot(state):
        return deepcopy({"commands": state["steering_commands"], "text": state["steering_text"],
                         "focus": state["steering_focus"]})

    def steering_remember(self, state):
        state["steering_history"].append(self.steering_snapshot(state))
        state["steering_history"] = state["steering_history"][-10:]

    def profile_description(self, user_id, profile):
        clauses = [f"{'Mute' if v < 0 else 'Show me more'} {c}." for c,v in sorted(profile.items())]
        return self.initial_profile(user_id) + ("\n" + " ".join(clauses) if clauses else "")

    def rank(self, user_id, state, condition, limit):
        user = self.users[user_id]
        history = list(user["train"]) + list(user["request_history"])
        ids = sorted(self.items)
        if self.model is not None:
            raw = self.model.score(history, ids)
        else:
            counts = Counter(c for i in history for c in self.items.get(i, []))
            raw = [sum(counts[c] for c in self.items[i]) + ((i * 17 + user_id * 7) % 19) / 100 for i in ids]
        scores = normalize_scores(raw)
        if condition in "AB":
            scores = [s + max(state["feedback"].get(i, 0), 0) * .25 for i, s in zip(ids, scores)]
        neutral = {"operation": "clarify", "category": None, "strength": 0, "source": "none"}
        command = state["command"] if condition in "CE" else neutral
        profile = state["profile"] if condition in "DE" else {}
        order = rerank(ids, scores, self.items, command, profile=profile)
        if condition in "AB":
            order = [i for i in order if state["feedback"].get(i, 0) >= 0]
        score_map = dict(zip(ids, scores))
        history_counts = Counter(c for i in history for c in self.items.get(i, []))
        explain = condition in "BE"
        cards = []
        for position, item_id in enumerate(order[:limit], 1):
            explanation = cached_explanation(item_id, self.items[item_id], history, self.items,
                                             index_path=Path(os.getenv("FEEDCTRL_EXPLANATION_INDEX", ROOT / "results/explanations.json"))) if explain else None
            signals = list(explanation["statements"]) if explanation else []
            if condition in "AB" and state["feedback"].get(item_id):
                signals.append("Direct item feedback changes this item's base score.")
            affected = []
            for c in self.items[item_id]:
                weight = profile.get(c, 0)
                if command["category"] == c and command["operation"] == "boost":
                    weight = command["strength"]
                if weight > 0:
                    affected.append(c)
            if affected:
                signals.append("Active category boost: " + ", ".join(affected) + ".")
            cards.append({"item_id": item_id, "categories": self.items[item_id],
                          "rank": position, "base_score": round(float(score_map[item_id]), 4),
                          "explanation": signals if explain else [],
                          "explanation_source": explanation["source"] if explanation else "disabled"})
        counts = Counter(c for card in cards for c in card["categories"])
        return {"condition": condition, "label": CONDITIONS[condition], "items": cards,
                "fill_rate": len(cards) / limit, "available_items": len(order),
                "category_exposure": dict(sorted(counts.items())),
                "explanations_enabled": explain, "profile": state["profile"],
                "profile_text": state["profile_text"],
                "command": state["command"], "feedback_count": len(state["feedback"])}

    def topic_preview(self, user_id, state, command, condition, limit):
        if self.topic_index is None:
            raise ValueError("Official caption sidecar is not configured")
        matched, evidence = match_topic(self.topic_index, command)
        user = self.users[user_id]
        history = list(user["train"]) + list(user["request_history"])
        ids = sorted(self.items)
        if self.model is not None:
            raw = self.model.score(history, ids)
        else:
            counts = Counter(c for item in history for c in self.items.get(item, []))
            raw = [sum(counts[c] for c in self.items[item]) + ((item * 17 + user_id * 7) % 19) / 100
                   for item in ids]
        scores = normalize_scores(raw)
        profile = state["profile"] if condition == "E" else {}
        order = rerank_topic(ids, scores, self.items, profile, matched,
                             command["operation"], command["strength"])
        top = order[:limit]
        return {"mode": "exploratory semantic topic preview; not A-E study evidence",
                "condition_context": condition,
                "data_mode": "fixture" if self.fixture else "processed dataset",
                "model_mode": "trained model" if self.model else "deterministic diagnostic scorer",
                "command": command, "candidate_matches": len(matched),
                "match_fraction": len(matched) / len(ids), "match_evidence": evidence,
                "items": [{"item_id": item, "categories": self.items[item], "rank": position,
                           "topic_text_match": item in matched,
                           "base_score": round(scores[ids.index(item)], 4)}
                          for position, item in enumerate(top, 1)],
                "top_k_match_count": sum(item in matched for item in top),
                "available_items": len(order),
                "fill_rate": len(top) / limit,
                "sidecar": {key: self.topic_index[key] for key in
                            ("source", "sha256", "candidate_items", "items_with_caption",
                             "ignored_non_item_rows")},
                "research_note": "Text-match exposure is not a human relevance label or experimental result."}


def create_app(data_path=None, model_path=None, fixture=False, semantic_path=None):
    app = FastAPI(title="Feed Control Lab", version="1.0.0")
    demo = DemoState(data_path, model_path, fixture, semantic_path)
    app.state.demo = demo

    @app.middleware("http")
    async def response_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/status")
    def status():
        return {"data_mode": "fixture" if demo.fixture else "processed dataset",
                "source": str(demo.data.get("metadata", {}).get("source", "processed dataset")),
                "model_mode": "trained model" if demo.model else "deterministic diagnostic scorer",
                "users": len(demo.users), "items": len(demo.items), "categories": len(demo.categories),
                "default_parser": "rule", "ollama_model": os.getenv("FEEDCTRL_OLLAMA_MODEL", DEFAULT_MODEL),
                "ollama_status": "Not checked; selecting Ollama makes a real request. Failures remain visible.",
                "research_note": "Synthetic category controls measure offline behavior; this demo does not establish human agency or satisfaction.",
                "category_note": "Opaque dataset category IDs; no invented topic names.",
                "semantic_topic": ("Official caption sidecar loaded; exploratory preview only"
                                   if demo.topic_index else "Unavailable until FEEDCTRL_CAPTION_SIDECAR is configured"),
                "asset_note": "Metadata cards only; no original video assets are distributed."}

    @app.post("/api/session", status_code=201)
    def session():
        return {"session_id": demo.create_session(), "expires_after_idle_seconds": SESSION_TTL}

    @app.get("/api/users")
    def users():
        return [{"user_id": u, "history_items": len(v["train"]) + len(v["request_history"])}
                for u, v in sorted(demo.users.items())]

    @app.get("/api/categories")
    def categories():
        return {"categories": demo.categories}

    @app.get("/api/feed")
    def feed(user_id: int = Query(ge=0), condition: Literal["A", "B", "C", "D", "E"] = "E",
             limit: int = Query(default=10, ge=1, le=50), x_session_id: str | None = Header(default=None)):
        with demo.lock:
            state = demo.user_state(x_session_id, user_id)
            return demo.rank(user_id, state, condition, limit)

    @app.get("/api/compare")
    def compare(user_id: int = Query(ge=0), limit: int = Query(default=10, ge=1, le=50),
                x_session_id: str | None = Header(default=None)):
        with demo.lock:
            state = demo.user_state(x_session_id, user_id)
            return {c: demo.rank(user_id, state, c, limit) for c in CONDITIONS}

    @app.get("/api/steering")
    def steering_profile(user_id: int = Query(ge=0), x_session_id: str | None = Header(default=None)):
        with demo.lock:
            state = demo.steering_state(x_session_id, user_id)
            return {"commands": state["steering_commands"], "text": state["steering_text"],
                    "configured_model": os.getenv("FEEDCTRL_STEERING_MODEL", steering.DEFAULT_STEERING_MODEL),
                    "revision": state["steering_revision"],
                    "can_undo": bool(state["steering_history"]), "focus": state["steering_focus"],
                    "feed": demo.steering_feed(user_id, state["steering_commands"])}

    def review_steering(state, user_id, proposed, interpretation, focus=None, history_action="none"):
        plan_id = secrets.token_urlsafe(24)
        state["steering_pending"] = {"id": plan_id, "revision": state["steering_revision"],
            "created": time.monotonic(), "commands": deepcopy(proposed), "focus": focus,
            "history_action": history_action}
        return {"ready": True, "applied": False, "plan_id": plan_id,
            "interpretation": interpretation, "commands": proposed,
            "baseline": demo.steering_feed(user_id, []), "preview": demo.steering_feed(user_id, proposed),
            "message": "Review the source subjects and effects, then apply explicitly. Active preferences are unchanged."}

    def history_proposal(state, user_id, action, interpretation):
        if action == "undo":
            if not state["steering_history"]:
                return {"ready": False, "applied": False, "needs_clarification": True,
                        "question": "No earlier applied topic change is available to undo", "commands": []}
            target = state["steering_history"][-1]
            return review_steering(state, user_id, deepcopy(target["commands"]), interpretation,
                                   target["focus"], "undo")
        return review_steering(state, user_id, [], interpretation, None, "clear")

    @app.post("/api/steering/history/preview")
    def steering_history(body: SteeringHistoryRequest, x_session_id: str | None = Header(default=None)):
        with demo.lock:
            state = demo.steering_state(x_session_id, body.user_id)
            state["steering_pending"] = None
            return history_proposal(state, body.user_id, body.action,
                {"history_action": body.action, "commands": [], "source": "explicit_history_button"})

    @app.post("/api/steering/preview")
    def steering_preview(body: SteeringPreviewRequest, x_session_id: str | None = Header(default=None)):
        with demo.lock:
            state = demo.steering_state(x_session_id, body.user_id)
            revision = state["steering_revision"]
            existing = list(state["steering_commands"])
            focus = state["steering_focus"]
            state["steering_pending"] = None
        try:
            explicit_bindings = steering.confirmed_bindings(body.bindings, demo.topic_index)
            scope_bindings = steering.known_bindings(existing)
            scope_bindings.update(explicit_bindings)
            if body.backend == "manual":
                commands = steering.ground_actions(body.actions, demo.topic_index, "manual_structured",
                                                   bindings=scope_bindings, existing=existing)
                interpretation = {"needs_clarification": False, "question": "", "commands": commands}
            else:
                if body.actions is not None:
                    raise ValueError("LLM interpretation takes text, not preselected actions")
                interpretation = steering.interpret(body.text, demo.topic_index,
                    model=os.getenv("FEEDCTRL_STEERING_MODEL", steering.DEFAULT_STEERING_MODEL),
                    context={"commands": existing, "focus": focus, "mode": body.mode}, bindings=explicit_bindings)
                if interpretation["needs_clarification"]:
                    return {"ready": False, "applied": False, **interpretation}
                commands = interpretation["commands"]
            action = interpretation.get("history_action", "none")
            proposed = steering.compose(existing, commands, body.mode) if action == "none" else []
            with demo.lock:
                state = demo.steering_state(x_session_id, body.user_id)
                if state["steering_revision"] != revision:
                    raise HTTPException(409, "Preferences changed while interpreting; review again")
                if action != "none":
                    return history_proposal(state, body.user_id, action, interpretation)
                next_focus = commands[0]["topic"] if len(commands) == 1 and commands[0]["operation"] != "remove" else None
                return review_steering(state, body.user_id, proposed, interpretation, next_focus)
        except steering.GroundingClarification as error:
            return {"ready": False, "applied": False, "needs_clarification": True,
                "question": str(error), "commands": [], "clarification": {
                    "requested_topic": error.requested_topic, "suggested_topic": error.suggested_topic,
                    "literal_topic": error.literal_topic}}
        except TopicGroundingError as error:
            return {"ready": False, "applied": False, "needs_clarification": True,
                    "question": str(error), "commands": []}
        except (ValueError, ParserOperationalError) as error:
            # Structural/model errors never become a rule interpretation or a partial apply.
            raise HTTPException(422 if body.backend == "manual" else 502,
                f"{body.backend} steering failed ({type(error).__name__}); active preferences are unchanged") from error

    @app.post("/api/steering/apply")
    def steering_apply(body: SteeringApplyRequest, x_session_id: str | None = Header(default=None)):
        with demo.lock:
            state = demo.steering_state(x_session_id, body.user_id)
            pending = state["steering_pending"]
            if (not pending or pending["id"] != body.plan_id or pending["revision"] != state["steering_revision"]
                    or time.monotonic() - pending["created"] > 300):
                raise HTTPException(409, "This review expired or was replaced; review the current request again")
            if pending.get("history_action") == "undo":
                state["steering_history"].pop()
            else:
                demo.steering_remember(state)
            state["steering_commands"] = pending["commands"]
            state["steering_text"] = steering.profile_text(pending["commands"])
            state["steering_focus"] = pending.get("focus")
            state["steering_revision"] += 1
            state["steering_pending"] = None
            return {"applied": True, "commands": state["steering_commands"], "text": state["steering_text"],
                    "revision": state["steering_revision"],
                    "can_undo": bool(state["steering_history"]), "focus": state["steering_focus"],
                    "feed": demo.steering_feed(body.user_id, state["steering_commands"])}

    @app.post("/api/steering/remove")
    def steering_remove(body: SteeringRemoveRequest, x_session_id: str | None = Header(default=None)):
        with demo.lock:
            state = demo.steering_state(x_session_id, body.user_id)
            demo.steering_remember(state)
            state["steering_commands"] = [c for c in state["steering_commands"]
                                         if c["topic"].casefold() != body.topic.casefold()]
            state["steering_text"] = steering.profile_text(state["steering_commands"])
            state["steering_revision"] += 1
            state["steering_pending"] = None
            state["steering_focus"] = None
            return {"removed": True, "commands": state["steering_commands"],
                    "text": state["steering_text"], "revision": state["steering_revision"],
                    "can_undo": bool(state["steering_history"]), "focus": None,
                    "feed": demo.steering_feed(body.user_id, state["steering_commands"])}

    @app.post("/api/topic/preview")
    def topic_preview(body: TopicRequest, x_session_id: str | None = Header(default=None)):
        with demo.lock:
            demo.user_state(x_session_id, body.user_id)
        if demo.topic_index is None:
            raise HTTPException(503, "Official caption sidecar is not configured; no topic preview was run.")
        try:
            command = (manual_topic_command(body.operation, body.text, body.strength) if body.backend == "manual"
                       else parse_topic_request(body.text, model=os.getenv("FEEDCTRL_OLLAMA_MODEL", DEFAULT_MODEL),
                                                topic_index=demo.topic_index))
            if command["operation"] == "clarify":
                return {"applied": False, "command": command,
                        "message": "Request needs one clear current topic and action; no preview was changed."}
            with demo.lock:
                state = demo.user_state(x_session_id, body.user_id)
                return {"applied": True,
                        **demo.topic_preview(body.user_id, state, command, body.condition, 10)}
        except TopicGroundingError as exc:
            return {"applied": False,
                    "message": f"{exc}. No topic preview was applied; A-E state is unchanged."}
        except Exception as exc:
            code = 422 if body.backend == "manual" else 502
            raise HTTPException(code, f"{body.backend} topic preview failed ({type(exc).__name__}); previous A-E state is preserved.") from exc

    @app.post("/api/control")
    def control(body: ControlRequest, x_session_id: str | None = Header(default=None)):
        with demo.lock:
            demo.user_state(x_session_id, body.user_id)
        try:
            kwargs = {"model": os.getenv("FEEDCTRL_OLLAMA_MODEL", DEFAULT_MODEL),
                      "cache_dir": ROOT / os.getenv("FEEDCTRL_PARSER_CACHE", "results/parser_cache")} if body.backend == "ollama" else {}
            command = parse_control(body.text, demo.categories, backend=body.backend, **kwargs)
        except ParserOperationalError as exc:
            if str(exc) == "LLM action is not grounded in exactly one explicit allowed category":
                raise HTTPException(422,
                    "The model proposed an unsupported category for this instruction. "
                    "Original A-E controls require one explicit existing category_N; "
                    "use Reviewed topic feed for named catalogue subjects. Previous state is preserved.") from exc
            raise HTTPException(502, f"{body.backend} parser failed ({type(exc).__name__}). Check the backend and retry; previous state is preserved.") from exc
        except Exception as exc:
            # Operational failure must never turn into an apparent successful rule result.
            raise HTTPException(502, f"{body.backend} parser failed ({type(exc).__name__}). Check the backend and retry; previous state is preserved.") from exc
        with demo.lock:
            state = demo.user_state(x_session_id, body.user_id)
            if command["operation"] != "clarify":
                state["command"] = command
                if command["operation"] == "reset":
                    state["profile"] = {}
                    state["feedback"] = {}
                    state["profile_text"] = demo.initial_profile(body.user_id)
            return {"command": command, "applied": command["operation"] != "clarify"}

    @app.put("/api/profile")
    def profile(body: ProfileRequest, x_session_id: str | None = Header(default=None)):
        if any(c not in demo.categories for c in body.profile):
            raise HTTPException(422, "Profile contains an unknown category.")
        with demo.lock:
            state = demo.user_state(x_session_id, body.user_id)
            state["profile"] = {c: w for c, w in body.profile.items() if w != 0}
            state["profile_text"] = demo.profile_description(body.user_id, state["profile"])
            if state["command"]["operation"] == "reset":
                state["command"] = {"operation": "clarify", "category": None, "strength": 0, "source": "none"}
            return {"profile": state["profile"]}

    @app.post("/api/profile/text")
    def profile_text(body: ProfileTextRequest, x_session_id: str | None = Header(default=None)):
        with demo.lock:
            demo.user_state(x_session_id, body.user_id)
        try:
            kwargs = {"model": os.getenv("FEEDCTRL_OLLAMA_MODEL", DEFAULT_MODEL),
                      "cache_dir": ROOT / os.getenv("FEEDCTRL_PARSER_CACHE", "results/parser_cache")} if body.backend == "ollama" else {}
            result = parse_profile(body.text, demo.categories, backend=body.backend, **kwargs)
        except Exception as exc:
            raise HTTPException(502, f"{body.backend} profile parser failed ({type(exc).__name__}). Check the backend and retry; previous profile is preserved.") from exc
        with demo.lock:
            state = demo.user_state(x_session_id, body.user_id)
            if result["operation"] in {"set", "reset"}:
                state["profile"] = result["profile"]
                state["profile_text"] = body.text if result["operation"] == "set" else demo.initial_profile(body.user_id)
                if state["command"]["operation"] == "reset":
                    state["command"] = {"operation": "clarify", "category": None, "strength": 0, "source": "none"}
            return {**result, "applied": result["operation"] != "clarify"}

    @app.post("/api/feedback")
    def feedback(body: FeedbackRequest, x_session_id: str | None = Header(default=None)):
        if body.item_id not in demo.items:
            raise HTTPException(422, "Unknown item.")
        with demo.lock:
            state = demo.user_state(x_session_id, body.user_id)
            if body.direction == "clear":
                state["feedback"].pop(body.item_id, None)
            else:
                state["feedback"][body.item_id] = 1 if body.direction == "like" else -1
            return {"feedback_count": len(state["feedback"])}

    @app.post("/api/reset")
    def reset(body: Request, x_session_id: str | None = Header(default=None)):
        with demo.lock:
            state = demo.user_state(x_session_id, body.user_id)
            state.update(profile={}, profile_text=demo.initial_profile(body.user_id), command={"operation": "clarify", "category": None, "strength": 0, "source": "none"}, feedback={})
            state.update(steering_commands=[], steering_pending=None, steering_text="",
                         steering_revision=state.get("steering_revision", 0) + 1,
                         steering_history=[], steering_focus=None)
            state.update(semantic_groups=[], semantic_pending=None, semantic_definition_pending=None, semantic_history=[],
                         semantic_revision=state.get("semantic_revision", 0) + 1)
            state.update(synthetic_items=[], synthetic_pending=None, synthetic_nonce=None, synthetic_last_removed=None,
                         synthetic_revision=state.get("synthetic_revision", 0) + 1)
        return {"reset": True}

    install_semantic_routes(app, demo)
    install_synthetic_routes(app, demo)

    dist = ROOT / "web/dist"
    if (dist / "assets").exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def index():
        if not (dist / "index.html").exists():
            raise HTTPException(503, "Frontend not built. Run npm ci and npm run build in web/ before starting the app.")
        return FileResponse(dist / "index.html")

    return app


app = create_app()
