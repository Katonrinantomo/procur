import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

import httpx

from app.config import settings
from app.routers import imports, items, purchases, queue, quick_check, request_items, request_items_list, requests

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: validate Langflow configuration
    missing = []
    if not settings.LANGFLOW_API_KEY:
        missing.append("LANGFLOW_API_KEY")
    if not settings.LANGFLOW_ORGANIZE_FLOW_ID:
        missing.append("LANGFLOW_ORGANIZE_FLOW_ID")
    if not settings.LANGFLOW_WEBCHECK_FLOW_ID:
        missing.append("LANGFLOW_WEBCHECK_FLOW_ID")
    if missing:
        logger.error(
            "Langflow is not fully configured. Missing or empty: %s. "
            "Set these in backend/.env before using AI features.",
            ", ".join(missing),
        )
    yield


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

app.include_router(queue.router)
app.include_router(purchases.router)
app.include_router(request_items_list.router)  # must be before request_items (has /{id} param)
app.include_router(request_items.router)
app.include_router(requests.router)
app.include_router(items.router)
app.include_router(imports.router)
app.include_router(quick_check.router)


def _langflow_configured() -> bool:
    return bool(
        settings.LANGFLOW_API_KEY
        and settings.LANGFLOW_ORGANIZE_FLOW_ID
        and settings.LANGFLOW_WEBCHECK_FLOW_ID
    )


@app.get("/api/health")
async def health():
    if not _langflow_configured():
        return {"status": "ok", "app": settings.APP_NAME, "langflow": "not configured"}

    # Check Langflow reachability with a short timeout
    langflow_status = "down"
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{settings.LANGFLOW_URL}/api/v1/version")
            if r.status_code < 500:
                langflow_status = "ok"
    except Exception:  # noqa: BLE001
        pass

    return {"status": "ok", "app": settings.APP_NAME, "langflow": langflow_status}
