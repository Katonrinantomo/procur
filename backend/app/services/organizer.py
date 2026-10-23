"""
Organizer — calls Flow 1 (Organize) and parses the result into LineItemDraft objects.

organizer.parse_text(text) -> list[LineItemDraft]

- Calls run_flow with the Organize flow ID.
- Strips markdown code fences if the model wraps the JSON.
- Parses {"items": [...]} with Pydantic.
- On ValidationError, retries once with the error appended to the input.
- Propagates LangflowError to the caller.
"""
from __future__ import annotations

import json
import re

from pydantic import BaseModel, ValidationError

from app.config import settings
from app.services.langflow_client import LangflowError, run_flow

# ---------------------------------------------------------------------------
# Pydantic model for a single draft line item
# ---------------------------------------------------------------------------

class LineItemDraft(BaseModel):
    name: str
    qty: int | None = None
    unit: str | None = None
    department: str | None = None
    quoted_unit_price_idr: int | None = None
    supplier: str | None = None


class _OrganizeResponse(BaseModel):
    items: list[LineItemDraft]


# ---------------------------------------------------------------------------
# Code fence stripper
# ---------------------------------------------------------------------------
_CODE_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


def _strip_fences(text: str) -> str:
    """Remove markdown code fences wrapping JSON, if present."""
    m = _CODE_FENCE.search(text)
    if m:
        return m.group(1).strip()
    return text.strip()


# ---------------------------------------------------------------------------
# Parse helper (raises ValidationError on bad data)
# ---------------------------------------------------------------------------

def _parse_response(raw: str) -> list[LineItemDraft]:
    cleaned = _strip_fences(raw)
    data = json.loads(cleaned)
    return _OrganizeResponse.model_validate(data).items


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def parse_text(text: str) -> list[LineItemDraft]:
    """
    Send *text* to the Organize flow and return a list of LineItemDraft.

    Retries once if the model output fails Pydantic validation, appending
    the validation error to the original input so the model can correct
    itself.  Propagates LangflowError on connectivity failures.
    """
    raw = await run_flow(settings.LANGFLOW_ORGANIZE_FLOW_ID, text)

    try:
        return _parse_response(raw)
    except (ValidationError, ValueError, KeyError) as first_err:
        retry_input = (
            f"{text}\n\n"
            f"[Previous answer was invalid. Error: {first_err}. "
            f"Please reply with valid JSON only.]"
        )
        raw2 = await run_flow(settings.LANGFLOW_ORGANIZE_FLOW_ID, retry_input)
        return _parse_response(raw2)
