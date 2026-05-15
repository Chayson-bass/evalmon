"""
Tests for the evalmon wrapper and storage layer.
Uses a temp SQLite DB so nothing touches the real ~/.evalmon/evalmon.db.
"""
import json
import os
import tempfile
import time
from unittest.mock import MagicMock, patch

import pytest

import evalmon
from evalmon import storage
from evalmon.costs import calculate_cost
from evalmon.wrapper import wrap


@pytest.fixture(autouse=True)
def temp_db(tmp_path):
    """Redirect all DB writes to a temp file for every test."""
    db = tmp_path / "test.db"
    storage.set_db_path(db)
    yield db
    storage.set_db_path(None)  # reset


# ── Cost calculation ───────────────────────────────────────────────────────────

def test_calculate_cost_known_model():
    cost = calculate_cost("gpt-4o", 1_000_000, 1_000_000)
    assert cost == pytest.approx(2.50 + 10.00)


def test_calculate_cost_unknown_model():
    assert calculate_cost("unknown-model-xyz", 500, 500) == 0.0


def test_calculate_cost_zero_tokens():
    assert calculate_cost("claude-sonnet-4-6", 0, 0) == 0.0


# ── Storage layer ──────────────────────────────────────────────────────────────

def test_insert_and_retrieve_call():
    storage.init_db()
    call_id = storage.insert_call(
        provider="openai",
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello"}],
        response={"choices": [{"message": {"content": "Hi"}}]},
        input_tokens=10,
        output_tokens=5,
        cost_usd=0.0001,
        latency_ms=120.5,
        prompt_version="v1",
        user_id="test_user",
    )
    assert call_id == 1

    calls = storage.get_calls()
    assert len(calls) == 1
    assert calls[0]["provider"] == "openai"
    assert calls[0]["model"] == "gpt-4o"
    assert calls[0]["prompt_version"] == "v1"
    assert calls[0]["user_id"] == "test_user"


def test_get_calls_filter_by_provider():
    storage.init_db()
    storage.insert_call("openai", "gpt-4o", [], {}, 10, 5, 0.0, 100.0)
    storage.insert_call("anthropic", "claude-sonnet-4-6", [], {}, 10, 5, 0.0, 100.0)

    openai_calls = storage.get_calls(provider="openai")
    assert all(c["provider"] == "openai" for c in openai_calls)
    assert len(openai_calls) == 1


def test_eval_crud():
    storage.init_db()
    eval_id = storage.insert_eval("always_polite", "Response must be polite")
    assert eval_id == 1

    evals = storage.get_evals()
    assert len(evals) == 1
    assert evals[0]["name"] == "always_polite"

    deleted = storage.delete_eval_by_name("always_polite")
    assert deleted is True
    assert len(storage.get_evals()) == 0


# ── Wrapper — OpenAI ───────────────────────────────────────────────────────────

def _mock_openai_response(content: str = "Hello!", input_tok: int = 10, output_tok: int = 5):
    usage = MagicMock()
    usage.prompt_tokens = input_tok
    usage.completion_tokens = output_tok
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.usage = usage
    resp.choices = [choice]
    resp.model_dump.return_value = {
        "choices": [{"message": {"content": content}}]
    }
    return resp


def test_wrap_openai_logs_call():
    fake_client = MagicMock()
    fake_client.__class__.__name__ = "OpenAI"
    fake_client.chat.completions.create.return_value = _mock_openai_response()

    wrapped = wrap(fake_client)
    wrapped.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Say hi"}],
    )

    calls = storage.get_calls()
    assert len(calls) == 1
    assert calls[0]["provider"] == "openai"
    assert calls[0]["model"] == "gpt-4o"
    assert calls[0]["input_tokens"] == 10
    assert calls[0]["output_tokens"] == 5


def test_wrap_passes_through_response():
    fake_client = MagicMock()
    fake_client.__class__.__name__ = "OpenAI"
    expected = _mock_openai_response("response text")
    fake_client.chat.completions.create.return_value = expected

    wrapped = wrap(fake_client)
    result = wrapped.chat.completions.create(model="gpt-4o", messages=[])
    assert result is expected


def test_wrap_logs_context_metadata():
    fake_client = MagicMock()
    fake_client.__class__.__name__ = "OpenAI"
    fake_client.chat.completions.create.return_value = _mock_openai_response()

    wrapped = wrap(fake_client)
    evalmon.set_context(prompt_version="v2", user_id="user_42")
    wrapped.chat.completions.create(model="gpt-4o", messages=[])

    calls = storage.get_calls()
    assert calls[0]["prompt_version"] == "v2"
    assert calls[0]["user_id"] == "user_42"


def test_wrap_unsupported_client():
    with pytest.raises(TypeError, match="evalmon.wrap"):
        wrap(object())


def test_wrap_disabled_skips_logging():
    evalmon.configure(enabled=False)
    fake_client = MagicMock()
    fake_client.__class__.__name__ = "OpenAI"
    fake_client.chat.completions.create.return_value = _mock_openai_response()

    wrapped = wrap(fake_client)
    wrapped.chat.completions.create(model="gpt-4o", messages=[])

    assert len(storage.get_calls()) == 0
    evalmon.configure(enabled=True)  # restore
