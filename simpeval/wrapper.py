import json
import time
from typing import Any

from .costs import calculate_cost
from .storage import insert_call
from .tracker import get_context, is_enabled


def wrap(client: Any) -> Any:
    """
    Wrap an OpenAI or Anthropic client to automatically log every LLM call.

    Usage:
        import simpeval
        from openai import OpenAI

        client = simpeval.wrap(OpenAI())          # one line — everything else stays the same
        client = simpeval.wrap(Anthropic())
    """
    type_name = type(client).__name__
    if type_name in ("OpenAI", "AzureOpenAI"):
        return _WrappedOpenAI(client)
    elif type_name == "Anthropic":
        return _WrappedAnthropic(client)
    else:
        raise TypeError(
            f"simpeval.wrap() received {type_name}. "
            "Supported: openai.OpenAI, openai.AzureOpenAI, anthropic.Anthropic"
        )


# ── OpenAI ─────────────────────────────────────────────────────────────────────

class _WrappedOpenAI:
    def __init__(self, client):
        self._client = client
        self.chat = _OAIChat(client.chat)

    def __getattr__(self, name):
        return getattr(self._client, name)


class _OAIChat:
    def __init__(self, chat):
        self._chat = chat
        self.completions = _OAICompletions(chat.completions)

    def __getattr__(self, name):
        return getattr(self._chat, name)


class _OAICompletions:
    def __init__(self, completions):
        self._completions = completions

    def create(self, **kwargs):
        if not is_enabled():
            return self._completions.create(**kwargs)

        t0 = time.perf_counter()
        response = self._completions.create(**kwargs)
        latency_ms = (time.perf_counter() - t0) * 1000

        try:
            _log_openai(kwargs, response, latency_ms)
        except Exception:
            pass  # logging must never break the caller

        return response

    def __getattr__(self, name):
        return getattr(self._completions, name)


def _log_openai(kwargs: dict, response: Any, latency_ms: float) -> None:
    model = kwargs.get("model", "unknown")
    messages = kwargs.get("messages", [])
    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "prompt_tokens", 0) or 0
    output_tokens = getattr(usage, "completion_tokens", 0) or 0

    try:
        response_dict = response.model_dump()
    except Exception:
        response_dict = {"raw": str(response)}

    insert_call(
        provider="openai",
        model=model,
        messages=messages,
        response=response_dict,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=calculate_cost(model, input_tokens, output_tokens),
        latency_ms=latency_ms,
        **get_context(),
    )


# ── Anthropic ──────────────────────────────────────────────────────────────────

class _WrappedAnthropic:
    def __init__(self, client):
        self._client = client
        self.messages = _AnthMessages(client.messages)

    def __getattr__(self, name):
        return getattr(self._client, name)


class _AnthMessages:
    def __init__(self, messages):
        self._messages = messages

    def create(self, **kwargs):
        if not is_enabled():
            return self._messages.create(**kwargs)

        t0 = time.perf_counter()
        response = self._messages.create(**kwargs)
        latency_ms = (time.perf_counter() - t0) * 1000

        try:
            _log_anthropic(kwargs, response, latency_ms)
        except Exception:
            pass

        return response

    def __getattr__(self, name):
        return getattr(self._messages, name)


def _log_anthropic(kwargs: dict, response: Any, latency_ms: float) -> None:
    model = kwargs.get("model", "unknown")
    messages = kwargs.get("messages", [])
    usage = getattr(response, "usage", None)
    input_tokens = getattr(usage, "input_tokens", 0) or 0
    output_tokens = getattr(usage, "output_tokens", 0) or 0

    try:
        response_dict = response.model_dump()
    except Exception:
        response_dict = {"raw": str(response)}

    insert_call(
        provider="anthropic",
        model=model,
        messages=messages,
        response=response_dict,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=calculate_cost(model, input_tokens, output_tokens),
        latency_ms=latency_ms,
        **get_context(),
    )
