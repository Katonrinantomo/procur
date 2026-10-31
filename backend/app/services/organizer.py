"""
Organizer — calls Flow 1 (Organize) and parses the result into LineItemDraft objects.

organizer.parse_text(text) -> list[LineItemDraft]

- Calls run_flow with the Organize flow ID and reads its organize_json output.
- Parses {"items": [...]} against OrganizeOut (code fences stripped).
- On invalid output, retries once with the error appended to the input.
- Propagates LangflowError (FlowContractError included) to the caller.
"""
from __future__ import annotations

from app.config import settings
from app.flows.contracts import ORGANIZE_OUT, LineItemDraft, OrganizeOut, parse_flow_json
from app.services.langflow_client import LangflowError, pick_output, run_flow

__all__ = ["LangflowError", "LineItemDraft", "parse_text"]


async def _run(text: str) -> str:
    outputs = await run_flow(settings.LANGFLOW_ORGANIZE_FLOW_ID, text)
    return pick_output(outputs, ORGANIZE_OUT)


async def parse_text(text: str) -> list[LineItemDraft]:
    """
    Send *text* to the Organize flow and return a list of LineItemDraft.

    Retries once if the model output fails validation, appending the error
    to the original input so the model can correct itself.
    """
    raw = await _run(text)

    async def rerun(hint: str) -> str:
        return await _run(f"{text}\n\n{hint}")

    return (await parse_flow_json(raw, OrganizeOut, rerun)).items
