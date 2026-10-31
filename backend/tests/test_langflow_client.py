"""
Tests for langflow_client.run_flow / pick_output / ping.

httpx is routed through a MockTransport — no live Langflow calls are made.
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock

import httpx
import pytest

from app.services import langflow_client
from app.services.langflow_client import LangflowError, pick_output, run_flow


def _output(display_name: str, component_id: str, text: str, key: str = "message") -> dict:
    return {
        "component_display_name": display_name,
        "component_id": component_id,
        "results": {key: {"text": text}},
    }


def _body(*outputs: dict) -> dict:
    return {"outputs": [{"outputs": list(outputs)}]}


@pytest.fixture
def transport(monkeypatch):
    """Route every httpx.AsyncClient through a handler set by the test."""
    state: dict = {"handler": None, "requests": []}
    real_client = httpx.AsyncClient

    def handler(request: httpx.Request) -> httpx.Response:
        state["requests"].append(request)
        return state["handler"](request)

    def factory(**kwargs):
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(langflow_client.httpx, "AsyncClient", factory)
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())
    return state


@pytest.mark.asyncio
async def test_run_flow_keys_outputs_by_display_name(transport):
    transport["handler"] = lambda r: httpx.Response(200, json=_body(
        _output("maker_json", "ChatOutput-a", '{"mode": "ITEMS"}'),
        _output("serper_raw", "ChatOutput-b", "[]", key="text"),
    ))

    out = await run_flow("flow-1", "hello")

    assert out == {"maker_json": '{"mode": "ITEMS"}', "serper_raw": "[]"}


@pytest.mark.asyncio
async def test_run_flow_duplicate_display_name_falls_back_to_component_id(transport):
    transport["handler"] = lambda r: httpx.Response(200, json=_body(
        _output("Chat Output", "ChatOutput-a", "first"),
        _output("Chat Output", "ChatOutput-b", "second"),
    ))

    out = await run_flow("flow-1", "hello")

    assert out == {"Chat Output": "first", "ChatOutput-b": "second"}


@pytest.mark.asyncio
async def test_run_flow_sends_tweaks_and_fresh_session_id(transport):
    transport["handler"] = lambda r: httpx.Response(200, json=_body(_output("o", "c", "x")))

    await run_flow("flow-1", "a", tweaks={"TextInput-1": {"input_value": "po"}})
    await run_flow("flow-1", "b")

    first, second = (json.loads(r.content) for r in transport["requests"])
    assert first["tweaks"] == {"TextInput-1": {"input_value": "po"}}
    assert "tweaks" not in second
    assert first["session_id"] and second["session_id"]
    assert first["session_id"] != second["session_id"]


@pytest.mark.asyncio
async def test_run_flow_retries_timeouts_three_times_then_raises(transport):
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    transport["handler"] = handler

    with pytest.raises(LangflowError, match="after 3 attempts"):
        await run_flow("flow-1", "hello")
    assert len(transport["requests"]) == 3


@pytest.mark.asyncio
async def test_run_flow_recovers_after_one_timeout(transport):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ReadTimeout("slow", request=request)
        return httpx.Response(200, json=_body(_output("o", "c", "ok")))

    transport["handler"] = handler

    assert await run_flow("flow-1", "hello") == {"o": "ok"}


@pytest.mark.asyncio
async def test_run_flow_does_not_retry_auth_failure(transport):
    transport["handler"] = lambda r: httpx.Response(401)

    with pytest.raises(LangflowError, match="API key"):
        await run_flow("flow-1", "hello")
    assert len(transport["requests"]) == 1


@pytest.mark.asyncio
async def test_run_flow_empty_outputs_is_retried_then_raises(transport):
    transport["handler"] = lambda r: httpx.Response(200, json=_body())

    with pytest.raises(LangflowError):
        await run_flow("flow-1", "hello")
    assert len(transport["requests"]) == 3


def test_pick_output_by_name():
    assert pick_output({"a": "1", "b": "2"}, "b") == "2"


def test_pick_output_single_output_fallback():
    assert pick_output({"Chat Output": "x"}, "organize_json") == "x"


def test_pick_output_missing_raises():
    with pytest.raises(LangflowError, match="maker_json"):
        pick_output({"a": "1", "b": "2"}, "maker_json")


@pytest.mark.asyncio
async def test_ping(transport):
    transport["handler"] = lambda r: httpx.Response(200, json={"version": "1"})
    assert await langflow_client.ping() is True

    def down(request):
        raise httpx.ConnectError("refused", request=request)

    transport["handler"] = down
    assert await langflow_client.ping() is False
