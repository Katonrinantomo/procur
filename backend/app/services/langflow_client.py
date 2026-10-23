"""
Langflow HTTP client.

All Langflow calls in the backend go through run_flow().  No other module
may call httpx or the Langflow API directly.
"""
from __future__ import annotations

import httpx

from app.config import settings


class LangflowError(Exception):
    pass


async def run_flow(flow_id: str, text: str) -> str:
    url = f"{settings.LANGFLOW_URL}/api/v1/run/{flow_id}"
    payload = {"input_value": text, "input_type": "chat", "output_type": "chat"}
    headers = {"x-api-key": settings.LANGFLOW_API_KEY}
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(url, json=payload, headers=headers)
            if r.status_code in (401, 403):
                raise LangflowError("Langflow rejected the API key")
            r.raise_for_status()
            return r.json()["outputs"][0]["outputs"][0]["results"]["message"]["text"]
    except LangflowError:
        raise
    except httpx.TimeoutException as e:
        raise LangflowError("Langflow took too long. Try again.") from e
    except (httpx.HTTPError, KeyError, IndexError) as e:
        raise LangflowError(f"Langflow call failed: {e}") from e
