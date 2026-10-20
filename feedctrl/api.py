"""Local, single-process research demonstrator. No held-out labels enter this API."""
from __future__ import annotations

import json
import math
import os
import secrets
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator

from feedctrl.controls import DEFAULT_MODEL, normalize_scores, parse_control, parse_profile, rerank
from feedctrl.explanations import cached_explanation

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


class DemoState:
    def __init__(self, data_path=None, model_path=None, fixture=False):
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
                                             index_path=ROOT / "results/explanations.json") if explain else None
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


def create_app(data_path=None, model_path=None, fixture=False):
    app = FastAPI(title="Feed Control Lab", version="1.0.0")
    demo = DemoState(data_path, model_path, fixture)
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

    @app.post("/api/control")
    def control(body: ControlRequest, x_session_id: str | None = Header(default=None)):
        with demo.lock:
            demo.user_state(x_session_id, body.user_id)
        try:
            kwargs = {"model": os.getenv("FEEDCTRL_OLLAMA_MODEL", DEFAULT_MODEL),
                      "cache_dir": ROOT / os.getenv("FEEDCTRL_PARSER_CACHE", "results/parser_cache")} if body.backend == "ollama" else {}
            command = parse_control(body.text, demo.categories, backend=body.backend, **kwargs)
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
        return {"reset": True}

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
