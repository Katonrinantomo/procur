"""
Langflow HTTP client.

All Langflow calls in the backend go through this module (run_flow and
ping).  No other module may call httpx or the Langflow API directly.
"""
from __future__ import annotations

import asyncio
import uuid
from typing import Any

import httpx

from app.config import settings


class LangflowError(Exception):
    pass


def _result_text(results: dict[str, Any]) -> str:
    """Return the text of one output's results block.

    Chat Output puts it under results.message.text; Type Convert and other
    text outputs use another key, so fall back to the first *.text found.
    """
    message = results.get("message")
    if isinstance(message, dict) and isinstance(message.get("text"), str):
        return message["text"]
    for value in results.values():
        if isinstance(value, dict) and isinstance(value.get("text"), str):
            return value["text"]
    raise KeyError("no text in output results")


def _collect_outputs(body: dict[str, Any]) -> dict[str, str]:
    """Map each output component's display name to its text.

    If two outputs share a display name, the later one is keyed by its
    component_id so neither is lost.
    """
    collected: dict[str, str] = {}
    for out in body["outputs"][0]["outputs"]:
        name = out.get("component_display_name") or out.get("component_id")
        if not name or name in collected:
            name = out.get("component_id") or f"output_{len(collected)}"
        collected[name] = _result_text(out["results"])
    if not collected:
        raise KeyError("flow returned no outputs")
    return collected


async def run_flow(
    flow_id: str,
    text: str,
    tweaks: dict[str, Any] | None = None,
    timeout: float = 60,
) -> dict[str, str]:
    """Run a flow and return {output display name: text}.

    Every call uses a fresh session_id so no chat history carries over
    between documents.  Timeouts, HTTP errors and malformed responses are
    tried 3 times; an auth failure is raised at once.
    """
    url = f"{settings.LANGFLOW_URL}/api/v1/run/{flow_id}"
    payload: dict[str, Any] = {
        "input_value": text,
        "input_type": "chat",
        "output_type": "chat",
        "session_id": uuid.uuid4().hex,
    }
    if tweaks:
        payload["tweaks"] = tweaks
    headers = {"x-api-key": settings.LANGFLOW_API_KEY}

    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                r = await client.post(url, json=payload, headers=headers)
                if r.status_code in (401, 403):
                    raise LangflowError("Langflow rejected the API key")
                r.raise_for_status()
                return _collect_outputs(r.json())
        except LangflowError:
            # Auth failures are not transient — don't retry.
            raise
        except (httpx.TimeoutException, httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as e:
            last_exc = e
            if attempt < 2:
                await asyncio.sleep(1.5)

    raise LangflowError(f"Langflow call failed after 3 attempts: {last_exc}") from last_exc


def pick_output(outputs: dict[str, str], name: str) -> str:
    """Return the output called *name*.

    A flow with a single output returns that output whatever its name, so
    services keep working before the Chat Output is renamed in Langflow.
    """
    if name in outputs:
        return outputs[name]
    if len(outputs) == 1:
        return next(iter(outputs.values()))
    raise LangflowError(
        f"Flow output '{name}' not found; got {sorted(outputs)}"
    )


async def ping(timeout: float = 3) -> bool:
    """Return True if Langflow answers its version endpoint."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(f"{settings.LANGFLOW_URL}/api/v1/version")
            return r.status_code < 500
    except Exception:  # noqa: BLE001
        return False
