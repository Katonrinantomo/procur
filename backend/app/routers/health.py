"""
GET /api/health/flows — owner only.

Reports whether Langflow is reachable, which flow IDs are set, and the
result of the last `python -m app.flowcheck` run.
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends

from app import flowcheck
from app.config import FLOW_ID_SETTINGS, settings
from app.routers.auth import CurrentUser, require_roles
from app.services import langflow_client

router = APIRouter()


def _last_flowcheck() -> dict | None:
    try:
        data = json.loads(flowcheck.RESULT_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return {
        "at": data.get("at"),
        "ok": data.get("ok"),
        "failed": [
            f"{r['flow']}/{r['fixture']}"
            for r in data.get("results", [])
            if r.get("ok") is False
        ],
    }


@router.get("/api/health/flows")
async def health_flows(
    current_user: CurrentUser = Depends(require_roles("owner")),
):
    flows = {
        name: {"configured": bool(getattr(settings, setting))}
        for name, setting in FLOW_ID_SETTINGS.items()
    }
    if not settings.LANGFLOW_API_KEY or not any(f["configured"] for f in flows.values()):
        langflow = "not configured"
    else:
        langflow = "ok" if await langflow_client.ping() else "down"

    return {
        "langflow": langflow,
        "flows": flows,
        "last_flowcheck": _last_flowcheck(),
    }
