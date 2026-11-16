"""Feed Control Studio: local web server.

Binds to 127.0.0.1 only. Requests whose Host or Origin header is not this
local address are refused with a bare 403 (protects against DNS rebinding and
cross-site requests). There is no password and no token: the person running it
brings their own model key, which stays in this process's memory.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from studio import workflows
from studio.engine import Studio, StudioError
from studio.providers import (ANTHROPIC_MODELS, DEFAULT_ANTHROPIC_MODEL, DEFAULT_EFFORT, DEFAULT_OPENAI_MODEL,
                              Ledger, ProviderError, build_provider, env_key_available)

STATIC = Path(__file__).parent / "static"


class ProviderBody(BaseModel):
    kind: str
    api_key: str | None = Field(default=None, repr=False)
    model: str | None = None
    effort: str | None = None
    base_url: str | None = None


class ManualBody(BaseModel):
    kind: str
    value: str
    action: str
    strength: str = "standard"


class InterpretBody(BaseModel):
    request: str


class DefineBody(BaseModel):
    description: str


class ClassifyBody(BaseModel):
    label: str
    definition: str
    action: str = "only"
    strength: str = "standard"


class NewItem(BaseModel):
    title: str
    description: str


class ItemsBody(BaseModel):
    items: list[NewItem]


class ApplyBody(BaseModel):
    preview_id: str


def create_app(port=8765, provider=None, studio=None, ledger=None):
    app = FastAPI(title="Feed Control Studio", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.studio = studio or Studio()
    app.state.ledger = ledger or Ledger()
    app.state.provider = provider or _default_provider()
    app.state.key_source = "environment" if app.state.provider.name in ("anthropic", "openai") else None
    allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    allowed_origins = {f"http://{h}" for h in allowed_hosts}

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        host = request.headers.get("host", "")
        origin = request.headers.get("origin")
        if host not in allowed_hosts or (origin is not None and origin not in allowed_origins):
            return PlainTextResponse("Forbidden", status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.exception_handler(StudioError)
    async def studio_error(_request, exc: StudioError):
        return JSONResponse({"error": str(exc)}, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request, exc: RequestValidationError):
        # Never echo submitted values (a pasted key could be among them).
        fields = sorted({".".join(str(p) for p in e.get("loc", [])[1:]) for e in exc.errors()})
        return JSONResponse({"error": "Invalid request: check " + (", ".join(fields) or "the input")}, status_code=422)

    @app.exception_handler(ProviderError)
    async def provider_error(_request, exc: ProviderError):
        return JSONResponse({"error": str(exc)}, status_code=502)

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    def provider_info():
        info = app.state.provider.describe()
        info["key_source"] = app.state.key_source
        info["env_keys"] = {"anthropic": env_key_available("anthropic"), "openai": env_key_available("openai")}
        info["models"] = {"anthropic": ANTHROPIC_MODELS, "claude-cli": ANTHROPIC_MODELS,
                          "openai": [DEFAULT_OPENAI_MODEL, "gpt-5", "gpt-5-nano"], "mock": ["mock-literal-v1"]}
        info["defaults"] = {"anthropic_model": DEFAULT_ANTHROPIC_MODEL, "effort": DEFAULT_EFFORT}
        info["cli_enabled"] = bool(os.environ.get("STUDIO_ENABLE_CLAUDE_CLI"))
        return info

    @app.get("/api/state")
    def state():
        return {**app.state.studio.state(), "provider": provider_info(), "spend_usd": app.state.ledger.total()}

    @app.get("/api/provider")
    def get_provider():
        return provider_info()

    @app.post("/api/provider")
    def set_provider(body: ProviderBody):
        if body.kind == "claude-cli" and not os.environ.get("STUDIO_ENABLE_CLAUDE_CLI"):
            raise StudioError("The Claude CLI provider is only for the author's computer. Start the Studio with --enable-claude-cli to use it.")
        key = (body.api_key or "").strip() or None
        app.state.provider = build_provider(body.kind, api_key=key, model=body.model or None,
                                            effort=body.effort or None, base_url=body.base_url or None)
        app.state.key_source = ("pasted" if key else "environment") if body.kind in ("anthropic", "openai") else None
        return provider_info()

    @app.get("/api/ledger")
    def ledger():
        return {"calls": app.state.ledger.calls, "total_usd": app.state.ledger.total()}

    @app.post("/api/preview/manual")
    def preview_manual(body: ManualBody):
        return workflows.manual_preview(app.state.studio, body.kind, body.value, body.action, body.strength)

    @app.post("/api/preview/interpret")
    def preview_interpret(body: InterpretBody):
        return workflows.interpret_preview(app.state.studio, app.state.provider, app.state.ledger, body.request)

    @app.post("/api/category/define")
    def category_define(body: DefineBody):
        return workflows.define_category(app.state.studio, app.state.provider, app.state.ledger, body.description)

    @app.post("/api/preview/category")
    def preview_category(body: ClassifyBody):
        return workflows.classify_category(app.state.studio, app.state.provider, app.state.ledger,
                                           body.label, body.definition, body.action, body.strength)

    @app.post("/api/preview/items")
    def preview_items(body: ItemsBody):
        return workflows.add_items_preview(app.state.studio, app.state.provider, app.state.ledger,
                                           [i.model_dump() for i in body.items])

    @app.post("/api/apply")
    def apply(body: ApplyBody):
        return app.state.studio.apply(body.preview_id)

    @app.post("/api/undo")
    def undo():
        return app.state.studio.undo()

    @app.post("/api/reset")
    def reset():
        app.state.studio.reset()
        return app.state.studio.state()

    return app


def _default_provider():
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return build_provider("anthropic")
        except ProviderError:
            pass
    return build_provider("mock")
