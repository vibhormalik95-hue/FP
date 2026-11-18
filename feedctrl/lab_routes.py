"""HTTP routes of the KuaiRec language controls, mounted on the original Feed Control Lab app.

``mount_lab(app)`` adds ``/api/lab/*`` to the app that ``feedctrl.api.create_app`` built on
the processed KuaiRec data and the trained checkpoint. The original A to E routes are
unchanged. There is no token or password: the server binds to 127.0.0.1, and
``LoopbackGuard`` silently refuses any request whose peer, Host or Origin is not this
computer. An API key typed into the page is held in this process's memory only; it is
never written to disk, logged, returned by the API or put into an error message.
"""
from __future__ import annotations

import ipaddress
import json
import re
import os
import threading
from collections import Counter
from pathlib import Path

from fastapi import Body, HTTPException, Query
from fastapi.responses import JSONResponse

from feedctrl import lab_workflows as wf
from feedctrl.kuairec_catalog import ENGLISH_LABEL, build_catalog, read_caption_table, read_english_layer
from feedctrl.lab import KuaiRecLab, LabError
from feedctrl.llm_providers import Ledger, ProviderError, build_provider, env_key_available

ROOT = Path(__file__).resolve().parents[1]
PROVIDER_KINDS = {"mock": "Mock (no AI, for tests)", "openai": "OpenAI or OpenAI-compatible API",
                  "anthropic": "Anthropic API", "ollama": "Ollama (local model on this computer)",
                  "claude-cli": "Claude CLI (this computer only)"}


class LoopbackGuard:
    """ASGI guard: loopback peer, a loopback Host, a same-origin Origin, no proxy headers."""

    def __init__(self, app, port):
        self.app, self.port = app, int(port)
        self.hosts = {f"127.0.0.1:{port}".encode(), f"localhost:{port}".encode()}
        self.origins = {b"http://" + h for h in self.hosts}

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            headers = scope.get("headers", [])
            peer = scope.get("client")
            try:
                local = bool(peer and ipaddress.ip_address(peer[0]).is_loopback)
            except ValueError:
                local = False
            hosts = [v for k, v in headers if k.lower() == b"host"]
            origins = [v for k, v in headers if k.lower() == b"origin"]
            forwarded = any(k.lower() == b"forwarded" or k.lower().startswith(b"x-forwarded-") for k, _ in headers)
            ok = (local and not forwarded and len(hosts) == 1 and hosts[0].lower() in self.hosts
                  and all(o.lower() in self.origins for o in origins))
            if not ok:
                if scope["type"] == "websocket":
                    await send({"type": "websocket.close", "code": 1008})
                    return
                await send({"type": "http.response.start", "status": 403,
                            "headers": [(b"cache-control", b"no-store"), (b"content-type", b"text/plain")]})
                await send({"type": "http.response.body", "body": b"Forbidden"})
                return
        await self.app(scope, receive, send)


class ProviderSlot:
    """The one provider of this server. The key lives only inside the provider object."""

    def __init__(self, budget_usd=None):
        self._lock = threading.Lock()
        self.provider = build_provider("mock")
        self.key_source = "none"
        self.ledger = Ledger(budget_usd=budget_usd)

    def configure(self, kind, *, model=None, api_key=None, base_url=None, effort=None, timeout=None):
        if kind not in PROVIDER_KINDS:
            raise LabError(f"Unknown provider {kind!r}.")
        api_key = (api_key or "").strip() or None
        try:
            provider = build_provider(kind, api_key=api_key, model=model or None, effort=effort or "low",
                                      base_url=base_url or None, timeout=timeout)
        except ProviderError as exc:
            raise LabError(str(exc)) from None
        except ImportError:
            raise LabError(f"The Python package for {PROVIDER_KINDS[kind]} is not installed.") from None
        with self._lock:
            self.provider = provider
            self.key_source = "typed into this page (memory only)" if api_key else (
                "environment variable" if env_key_available(kind) and kind in ("openai", "anthropic") else "none")
        return self.describe()

    def describe(self):
        info = self.provider.describe()
        info.pop("api_key", None)
        return {**info, "key_source": self.key_source, "spent_usd": self.ledger.total(),
                "calls": len(self.ledger.calls), "budget_usd": self.ledger.budget_usd}


# How the Results page labels a run by the item text it used. Runs before the English layer used the
# original KuaiRec text (summary.json has no "input_text"); those files are frozen and are not edited.
ORIGINAL_TEXT_PENDING = "Measured on the original-text run (17 Nov); English-input re-run pending."
ORIGINAL_TEXT_PRIOR = "Prior run: measured on the original KuaiRec text (17 Nov)."
ENGLISH_TEXT_RUN = "Measured on the English text layer (machine translation of KuaiRec)."


_C = chr
CJK = re.compile("[" + _C(0x3000) + "-" + _C(0x303F) + _C(0x3400) + "-" + _C(0x9FFF) + _C(0xFF00) + "-" + _C(0xFFEF) + "]+")
NON_ENGLISH = "[non-English text removed]"


def english_only(value):
    """Replace any CJK run in a response by a marker; returns (value, number of replacements).

    The app loads the English text layer, so item text and labels should already be English. This
    catches model output (a reason, a label, a definition) that a model wrote in CJK script despite
    the English-only prompts. Scope, stated precisely: it covers string values and string dict keys
    (a custom category is keyed by its model-proposed label), and only the ranges in ``CJK`` (CJK
    symbols and punctuation, CJK unified ideographs with extension A, halfwidth and fullwidth
    forms). Other scripts, such as kana, Hangul, Cyrillic or Arabic, pass through unchanged: this is
    not a general English-language guarantee. Two keys that become equal get a numbered suffix."""
    count = 0

    def clean(text):
        nonlocal count
        new, n = CJK.subn(NON_ENGLISH, text)
        count += n
        return new

    def walk(v):
        if isinstance(v, str):
            return clean(v)
        if isinstance(v, list):
            return [walk(x) for x in v]
        if isinstance(v, dict):
            out = {}
            for k, x in v.items():
                key = clean(k) if isinstance(k, str) else k
                if key in out:
                    n = 2
                    while f"{key} ({n})" in out:
                        n += 1
                    key = f"{key} ({n})"
                out[key] = walk(x)
            return out
        return v
    out = walk(value)
    if count and isinstance(out, dict) and isinstance(out.get("notes"), list):
        out["notes"].append(f"{count} run(s) of non-English model text were removed from this view.")
    return out, count


def build_lab(demo, english_path=None):
    """The English KuaiRec catalogue joined to the processed items, scored by the app's recommender.

    The app reads the English text layer (machine translation of KuaiRec) only. Without it, a caption
    sidecar in the same format is accepted (tests and fixtures).
    """
    english_path = english_path or os.getenv("FEEDCTRL_ENGLISH_LAYER")
    sidecar = os.getenv("FEEDCTRL_CAPTION_SIDECAR")
    if demo.fixture or not (english_path or sidecar):
        return None
    rows, provenance = read_english_layer(english_path) if english_path else read_caption_table(sidecar)
    if any(CJK.search(str(v)) for row in rows.values() for v in row.values()):
        raise ValueError("The item text holds CJK characters; the app needs the English text layer "
                         "(data/kuairec_text_en-v1.json, see fetch-assets).")
    catalog = build_catalog(demo.data, rows)

    def scorer(user_id):
        user = demo.users[user_id]
        history = list(user["train"]) + list(user["request_history"])
        ids = sorted(demo.items)
        if demo.model is not None:
            raw = demo.model.score(history, ids)
        else:
            counts = Counter(c for i in history for c in demo.items.get(i, []))
            raw = [sum(counts[c] for c in demo.items[i]) + ((i * 17 + user_id * 7) % 19) / 100 for i in ids]
        return dict(zip(ids, raw))

    lab = KuaiRecLab(catalog, scorer=scorer, users=demo.users)
    lab.provenance = {**provenance, "text": ENGLISH_LABEL if english_path else "caption sidecar",
                      "items_with_text": sum(r["has_text"] for r in catalog.values())}
    return lab


def _error(exc):
    return JSONResponse({"detail": str(exc)}, status_code=getattr(exc, "status", 400))


def mount_lab(app, *, english_path=None, results_dir=None, budget_usd=None, lab=None):
    demo = app.state.demo
    lab = lab or build_lab(demo, english_path)
    slot = ProviderSlot(budget_usd)
    app.state.lab, app.state.provider_slot = lab, slot
    results_dir = Path(results_dir or ROOT / "docs" / "evidence" / "lab-eval")

    def need_lab():
        if lab is None:
            raise HTTPException(503, "The KuaiRec language controls need the processed data (data/processed.json) and "
                                     "the English text layer (data/kuairec_text_en-v1.json); run fetch-assets first.")
        return lab

    def guarded(fn):
        try:
            return english_only(fn())[0]
        except LabError as exc:
            return _error(exc)

    @app.get("/api/lab/status")
    def lab_status():
        return {"available": lab is not None, "provider": slot.describe(), "providers": PROVIDER_KINDS,
                "model_mode": "trained SASRec checkpoint" if demo.model else "diagnostic scorer (no checkpoint)",
                "catalogue": len(lab.catalog) if lab else 0, "users": len(demo.users),
                "provenance": getattr(lab, "provenance", None), "feed_size": lab.feed_size if lab else None,
                "env_keys": {k: env_key_available(k) for k in ("openai", "anthropic")}}

    @app.post("/api/lab/provider")
    def set_provider(body: dict = Body(...)):
        return guarded(lambda: slot.configure(str(body.get("kind", "mock")), model=body.get("model"),
                                              api_key=body.get("api_key"), base_url=body.get("base_url"),
                                              effort=body.get("effort"), timeout=body.get("timeout")))

    @app.get("/api/lab/calls")
    def calls():
        return {"total_usd": slot.ledger.total(), "calls": slot.ledger.calls[-200:]}

    @app.get("/api/lab/labels")
    def labels(user_id: int = Query(ge=0), kind: str = "", q: str = "", limit: int = Query(default=300, le=2000)):
        lab_ = need_lab()
        terms = lab_.vocabulary(lab_.user(user_id))
        q = q.strip().casefold()
        out = [t for t in terms if (not kind or t["kind"] == kind)
               and (not q or q in t["value"].casefold())]
        out.sort(key=lambda t: (-t["item_count"], t["value"]))
        return {"total": len(out), "labels": out[:limit]}

    @app.get("/api/lab/state")
    def state(user_id: int = Query(ge=0)):
        return guarded(lambda: need_lab().state(user_id))

    @app.post("/api/lab/manual")
    def manual(body: dict = Body(...)):
        values = body.get("values") if isinstance(body.get("values"), list) else None
        return guarded(lambda: wf.manual_preview(need_lab(), int(body["user_id"]), body.get("kind"), body.get("value"),
                                                 body.get("action"), body.get("strength", "standard"),
                                                 values=[str(v) for v in values] if values else None))

    @app.post("/api/lab/interpret")
    def interpret(body: dict = Body(...)):
        return guarded(lambda: wf.interpret_preview(need_lab(), slot.provider, slot.ledger, int(body["user_id"]),
                                                    body.get("request", "")))

    @app.post("/api/lab/define")
    def define(body: dict = Body(...)):
        return guarded(lambda: wf.define_category(need_lab(), slot.provider, slot.ledger, int(body["user_id"]),
                                                  body.get("description", ""),
                                                  max(10, min(200, int(body.get("scope_size", wf.DEFAULT_SCOPE))))))

    @app.post("/api/lab/classify")
    def classify(body: dict = Body(...)):
        return guarded(lambda: wf.classify_category(need_lab(), slot.provider, slot.ledger, int(body["user_id"]),
                                                    body.get("label"), body.get("definition"),
                                                    body.get("action", "only"), body.get("strength", "standard"),
                                                    max(10, min(200, int(body.get("scope_size", wf.DEFAULT_SCOPE))))))

    @app.post("/api/lab/new-items")
    def new_items(body: dict = Body(...)):
        return guarded(lambda: wf.add_items_preview(need_lab(), slot.provider, slot.ledger, int(body["user_id"]),
                                                    body.get("items", [])))

    @app.post("/api/lab/apply")
    def apply(body: dict = Body(...)):
        return guarded(lambda: need_lab().apply(int(body["user_id"]), str(body.get("preview_id", ""))))

    @app.post("/api/lab/undo")
    def undo(body: dict = Body(...)):
        return guarded(lambda: need_lab().undo(int(body["user_id"])))

    @app.post("/api/lab/reset")
    def reset(body: dict = Body(...)):
        def run():
            need_lab().reset(int(body["user_id"]))
            return need_lab().state(int(body["user_id"]))
        return guarded(run)

    @app.get("/api/lab/results")
    def results():
        """The measured tables, read from the result files (newest run first)."""
        runs = []
        if results_dir.is_dir():
            for folder in sorted((p for p in results_dir.iterdir() if p.is_dir()), reverse=True):
                summary = folder / "summary.json"
                if summary.is_file():
                    try:
                        runs.append({"run": folder.name, **json.loads(summary.read_text(encoding="utf-8"))})
                    except json.JSONDecodeError:
                        runs.append({"run": folder.name, "error": "summary.json is not valid JSON"})
        english = any(r.get("input_text") == "english" for r in runs)
        for r in runs:
            if r.get("input_text", "original") == "original":
                r["text_label"] = (ORIGINAL_TEXT_PRIOR if english else ORIGINAL_TEXT_PENDING)
            else:
                r["text_label"] = ENGLISH_TEXT_RUN
        return {"runs": runs, "folder": results_dir.name}

    return lab
