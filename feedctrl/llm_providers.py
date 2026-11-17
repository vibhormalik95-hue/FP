"""Model providers for the language controls (bring your own key).

Every provider exposes one method, ``complete(task, system, payload, schema)``,
which returns ``(data, call)``: the parsed JSON object that matches ``schema``
and a call record (provider, model, latency, tokens, cost). Keys are held only
in the provider object in process memory. They are never written to disk,
logged, returned by the API or put into an exception message.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time

# USD per million tokens (input, output). Anthropic first-party list prices as of
# November 2026; OpenAI entries are rough defaults and are labelled estimates.
PRICES = {
    "claude-fable-5-2": (8.0, 40.0),
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
}
ANTHROPIC_MODELS = ["claude-sonnet-5-5", "claude-opus-5-5", "claude-fable-5-2", "claude-haiku-5-5"]
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5-5"
DEFAULT_OPENAI_MODEL = "gpt-5-mini"
DEFAULT_EFFORT = "low"
CALL_TIMEOUT_S = 120
OLLAMA_BASE_URL = "http://127.0.0.1:11434/v1"
LOCAL_MAX_TOKENS = 2048


class ProviderError(Exception):
    """A provider failed. The message never contains a key."""


def _scrub(text, secret):
    text = str(text)
    if secret:
        text = text.replace(secret, "[key]")
    return re.sub(r"(sk-[A-Za-z0-9_\-]{6})[A-Za-z0-9_\-]+", r"\1…", text)[:600]


def _cost(model, tokens_in, tokens_out):
    price = PRICES.get(model)
    if not price:
        return None
    return round(tokens_in / 1e6 * price[0] + tokens_out / 1e6 * price[1], 6)


class Provider:
    name = "base"
    label = "base"
    is_ai = True

    def __init__(self, model=None):
        self.model = model

    def describe(self):
        return {"provider": self.name, "label": self.label, "model": self.model, "is_ai": self.is_ai}

    def complete(self, task, system, payload, schema):  # pragma: no cover - interface
        raise NotImplementedError

    def _record(self, task, started, tokens_in, tokens_out, cost, cost_source, **extra):
        return {"task": task, "provider": self.name, "model": self.model,
                "latency_s": round(time.monotonic() - started, 3),
                "input_tokens": tokens_in, "output_tokens": tokens_out,
                "cost_usd": cost, "cost_source": cost_source, **extra}


class AnthropicProvider(Provider):
    """Claude through the Anthropic Messages API with the user's own key."""
    name = "anthropic"
    label = "Anthropic API"

    def __init__(self, api_key, model=DEFAULT_ANTHROPIC_MODEL, effort=DEFAULT_EFFORT, http_client=None):
        super().__init__(model or DEFAULT_ANTHROPIC_MODEL)
        if not api_key or not isinstance(api_key, str):
            raise ProviderError("An Anthropic API key is required.")
        import anthropic
        self._secret = api_key.strip()
        kwargs = {"api_key": self._secret, "timeout": CALL_TIMEOUT_S, "max_retries": 1,
                  "base_url": "https://api.anthropic.com"}
        if http_client is not None:
            kwargs["http_client"] = http_client
        self._client = anthropic.Anthropic(**kwargs)
        self.effort = effort or DEFAULT_EFFORT

    def describe(self):
        return {**super().describe(), "effort": self.effort}

    def complete(self, task, system, payload, schema):
        import anthropic
        started = time.monotonic()
        try:
            # Streaming keeps long replies inside HTTP timeouts. The server-side
            # fallback re-runs a refused request on a fallback model in the same call.
            with self._client.beta.messages.stream(
                model=self.model,
                max_tokens=16000,
                system=system,
                messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                betas=["server-side-fallback-2026-07-01"],
                extra_body={"fallbacks": "default",
                            "output_config": {"effort": self.effort,
                                              "format": {"type": "json_schema", "schema": schema}}},
            ) as stream:
                message = stream.get_final_message()
        except anthropic.AuthenticationError:
            raise ProviderError("The Anthropic API rejected the key (401). Check the key and try again.") from None
        except anthropic.RateLimitError:
            raise ProviderError("The Anthropic API is rate limiting this key (429). Wait and try again.") from None
        except anthropic.APIStatusError as exc:
            raise ProviderError(f"Anthropic API error {exc.status_code}: {_scrub(exc.message, self._secret)}") from None
        except anthropic.APIConnectionError as exc:
            raise ProviderError(f"Could not reach the Anthropic API: {_scrub(exc, self._secret)}") from None
        if message.stop_reason == "refusal":
            raise ProviderError("The model declined this request (refusal).")
        if message.stop_reason == "max_tokens":
            raise ProviderError("The reply was cut off at the output limit.")
        text = next((b.text for b in message.content if getattr(b, "type", "") == "text"), "")
        data = _parse_json(text)
        usage = message.usage
        tokens_in = (usage.input_tokens or 0) + (getattr(usage, "cache_creation_input_tokens", 0) or 0) \
            + (getattr(usage, "cache_read_input_tokens", 0) or 0)
        served = getattr(message, "model", self.model) or self.model
        return data, self._record(task, started, tokens_in, usage.output_tokens or 0,
                                  _cost(served, tokens_in, usage.output_tokens or 0), "list price x tokens",
                                  served_by=served)


class OpenAICompatibleProvider(Provider):
    """Any server that speaks the OpenAI Chat Completions API (OpenAI, Ollama, vLLM, LM Studio...)."""
    name = "openai"
    label = "OpenAI-compatible"

    def __init__(self, api_key, model=DEFAULT_OPENAI_MODEL, base_url=None, http_client=None, effort=None, timeout=None):
        super().__init__(model or DEFAULT_OPENAI_MODEL)
        self.timeout = float(timeout or CALL_TIMEOUT_S)
        # Reasoning models (gpt-5 family, o-series) accept reasoning_effort; others ignore the setting.
        self.effort = effort if effort in ("low", "medium", "high") and re.match(r"^(gpt-5|o\d)", self.model) else None
        from openai import OpenAI
        self._secret = (api_key or "").strip()
        # Always explicit: an OPENAI_BASE_URL in the environment must never redirect the key.
        kwargs = {"api_key": self._secret or "not-needed", "timeout": self.timeout, "max_retries": 1,
                  "base_url": base_url or "https://api.openai.com/v1"}
        if http_client is not None:
            kwargs["http_client"] = http_client
        self._client = OpenAI(**kwargs)
        self.base_url = base_url or "https://api.openai.com/v1"

    def describe(self):
        return {**super().describe(), "base_url": self.base_url, "effort": self.effort}

    def complete(self, task, system, payload, schema):
        import openai
        started = time.monotonic()
        extra = {"reasoning_effort": self.effort} if self.effort else {}
        client = self._client
        if self.name == "ollama":   # deterministic local decoding, as in the original parser runs
            # Operational limits (added 17 Nov after a runaway generation in the local run): an output cap far
            # above any valid reply, and no automatic retry of a call that already used the whole timeout.
            extra.update(temperature=0, seed=42, max_tokens=LOCAL_MAX_TOKENS)
            client = self._client.with_options(max_retries=0)
        try:
            response = client.chat.completions.create(
                model=self.model, **extra,
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
                response_format={"type": "json_schema",
                                 "json_schema": {"name": task.replace("-", "_"), "schema": schema, "strict": True}},
            )
        except openai.AuthenticationError:
            raise ProviderError("The server rejected the key (401). Check the key and try again.") from None
        except openai.APIStatusError as exc:
            raise ProviderError(f"API error {exc.status_code}: {_scrub(exc.message, self._secret)}") from None
        except openai.APIConnectionError as exc:
            raise ProviderError(f"Could not reach {self.base_url}: {_scrub(exc, self._secret)}") from None
        choice = response.choices[0]
        if self.name == "ollama" and getattr(choice, "finish_reason", None) == "length":
            raise ProviderError(f"The local model hit the {LOCAL_MAX_TOKENS}-token output cap without finishing its reply.")
        if getattr(choice.message, "refusal", None):
            raise ProviderError("The model declined this request (refusal).")
        data = _parse_json(choice.message.content or "")
        usage = response.usage
        tokens_in = getattr(usage, "prompt_tokens", 0) or 0
        tokens_out = getattr(usage, "completion_tokens", 0) or 0
        if self.name == "ollama":
            # A local server silently drops the start of a prompt longer than its context window.
            if any(abs(tokens_in - size) <= 4 for size in (2048, 4096, 8192, 16384, 32768)):
                raise ProviderError(f"The local model server cut the prompt at its context limit ({tokens_in} tokens). "
                                    "Start Ollama with OLLAMA_CONTEXT_LENGTH=32768 and try again.")
            return data, self._record(task, started, tokens_in, tokens_out, 0.0, "local model (no API charge)")
        return data, self._record(task, started, tokens_in, tokens_out,
                                  _openai_cost(self.model, tokens_in, tokens_out), "estimate (list price table)")


OPENAI_PRICES = {"gpt-5-mini": (0.25, 2.0), "gpt-5": (1.25, 10.0), "gpt-5-nano": (0.05, 0.40),
                 "gpt-4.1-mini": (0.40, 1.60), "gpt-4o-mini": (0.15, 0.60)}


def _openai_cost(model, tokens_in, tokens_out):
    price = OPENAI_PRICES.get(model)
    if not price:
        return None
    return round(tokens_in / 1e6 * price[0] + tokens_out / 1e6 * price[1], 6)


class ClaudeCLIProvider(Provider):
    """The locally installed Claude Code CLI (``claude -p``). For the author's machine only:
    it uses whatever account the CLI is signed in to. Costs are as reported by the CLI."""
    name = "claude-cli"
    label = "Claude CLI (this computer)"

    def __init__(self, model=DEFAULT_ANTHROPIC_MODEL, effort=DEFAULT_EFFORT, executable=None):
        super().__init__(model or DEFAULT_ANTHROPIC_MODEL)
        self.effort = effort or DEFAULT_EFFORT
        if not re.fullmatch(r"[A-Za-z0-9._:\-]{1,80}", self.model or "") or self.effort not in ("low", "medium", "high", "xhigh", "max"):
            raise ProviderError("Invalid model name or effort for the Claude CLI.")
        self.executable = executable or shutil.which("claude")
        if not self.executable:
            raise ProviderError("The claude command was not found on PATH.")
        self._workdir = tempfile.mkdtemp(prefix="feedctrl-cli-")

    def describe(self):
        return {**super().describe(), "effort": self.effort}

    def complete(self, task, system, payload, schema):
        started = time.monotonic()
        cmd = [self.executable, "-p", "--output-format", "json", "--model", self.model,
               "--effort", self.effort, "--tools", "", "--strict-mcp-config", "--setting-sources", "",
               "--no-session-persistence", "--disable-slash-commands",
               "--system-prompt", system, "--json-schema", json.dumps(schema)]
        try:
            proc = subprocess.run(cmd, input=json.dumps(payload, ensure_ascii=False), capture_output=True,
                                  text=True, encoding="utf-8", timeout=CALL_TIMEOUT_S * 2, cwd=self._workdir)
        except subprocess.TimeoutExpired:
            raise ProviderError(f"The Claude CLI did not answer within {CALL_TIMEOUT_S * 2} s.") from None
        try:
            out = json.loads(proc.stdout)
        except json.JSONDecodeError:
            raise ProviderError(f"The Claude CLI returned no JSON (exit {proc.returncode}): {_scrub(proc.stderr, None)}") from None
        if out.get("is_error"):
            raise ProviderError(f"The Claude CLI reported an error: {_scrub(out.get('result'), None)}")
        data = out.get("structured_output")
        if not isinstance(data, dict):
            data = _parse_json(out.get("result") or "")
        usage = out.get("usage") or {}
        tokens_in = sum(usage.get(k, 0) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
        return data, self._record(task, started, tokens_in, usage.get("output_tokens", 0) or 0,
                                  out.get("total_cost_usd"), "reported by Claude CLI",
                                  served_by=",".join(out.get("modelUsage", {}).keys()) or self.model)


class MockProvider(Provider):
    """A deterministic stand-in with no AI. It exists so that the tests and the
    Windows CLI can exercise every workflow with no key and no cost. It matches
    words literally, so it cannot understand nonliteral requests; results are
    plumbing checks, not evidence of interpretation quality."""
    name = "mock"
    label = "Mock (no AI, for tests)"
    is_ai = False

    def __init__(self, model="mock-literal-v1", delay_s=0.0):
        super().__init__(model)
        self.delay_s = delay_s

    def complete(self, task, system, payload, schema):
        from feedctrl import lab_mock as mock_logic
        started = time.monotonic()
        if self.delay_s:
            time.sleep(self.delay_s)
        data = mock_logic.answer(task, payload)
        return data, self._record(task, started, 0, 0, 0.0, "mock (free)")


def _parse_json(text):
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        raise ProviderError("The model reply was not valid JSON.") from None
    if not isinstance(data, dict):
        raise ProviderError("The model reply was not a JSON object.")
    return data


def build_provider(kind, *, api_key=None, model=None, effort=None, base_url=None, timeout=None):
    """Create a provider. If ``api_key`` is empty, the matching environment variable is used."""
    kind = (kind or "mock").strip().lower()
    if kind == "mock":
        return MockProvider()
    if kind == "anthropic":
        return AnthropicProvider(api_key or os.environ.get("ANTHROPIC_API_KEY", ""), model=model, effort=effort)
    if kind == "openai":
        # The environment key is only sent to OpenAI itself, never to another server.
        from urllib.parse import urlsplit
        parts = urlsplit(base_url or "https://api.openai.com/v1")
        official = parts.scheme == "https" and parts.hostname == "api.openai.com" and parts.username is None
        env_key = os.environ.get("OPENAI_API_KEY", "") if official else ""
        return OpenAICompatibleProvider(api_key or env_key, model=model, base_url=base_url, effort=effort, timeout=timeout)
    if kind == "ollama":
        provider = OpenAICompatibleProvider("", model=model or "llama3.1:8b", base_url=base_url or OLLAMA_BASE_URL,
                                            timeout=timeout or 600)
        provider.name, provider.label = "ollama", "Ollama (local model on this computer)"
        return provider
    if kind == "claude-cli":
        return ClaudeCLIProvider(model=model, effort=effort)
    raise ProviderError(f"Unknown provider: {kind}")


def env_key_available(kind):
    return bool({"anthropic": os.environ.get("ANTHROPIC_API_KEY"),
                 "openai": os.environ.get("OPENAI_API_KEY")}.get(kind))


CEILING_PRICE = (16.0, 80.0)   # highest per-token price we know (fast mode); used when a price is unknown


class Ledger:
    """Running record of every model call: cost per call and running total.

    ``budget_usd`` (optional) is the amount this process may still spend; once the
    running total reaches it, no further calls are started."""

    def __init__(self, budget_usd=None):
        self.calls = []
        self.budget_usd = budget_usd
        self._lock = threading.Lock()

    def over_budget(self):
        return self.budget_usd is not None and self.total() >= self.budget_usd

    def add(self, call):
        with self._lock:
            if call.get("cost_usd") is None and not call.get("error"):
                tin, tout = call.get("input_tokens") or 0, call.get("output_tokens") or 0
                call["cost_usd"] = round(tin / 1e6 * CEILING_PRICE[0] + tout / 1e6 * CEILING_PRICE[1], 6)
                call["cost_source"] = "price unknown: upper-bound estimate"
            self.calls.append(call)
            call["running_total_usd"] = self.total()
        return call

    def total(self):
        return round(sum(c.get("cost_usd") or 0 for c in self.calls), 6)
