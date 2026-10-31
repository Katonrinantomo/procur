import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import FLOW_ID_SETTINGS, settings, validate_settings
from app.routers import audit_logs, auth, health, imports, items, purchases, queue, quick_check, request_items, request_items_list, requests
from app.security import limiter
from app.services import langflow_client

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: validate required settings
    validate_settings()

    # Startup: validate Langflow configuration
    if not settings.LANGFLOW_API_KEY:
        logger.error(
            "LANGFLOW_API_KEY is empty. "
            "Set it in backend/.env before using AI features."
        )
    for flow, setting in FLOW_ID_SETTINGS.items():
        if not getattr(settings, setting):
            logger.warning("Flow '%s' disabled: %s is empty", flow, setting)
    yield


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

# ---------------------------------------------------------------------------
# Security middleware (order matters: outermost added last)
# ---------------------------------------------------------------------------

# CORS: allow only the local Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# TrustedHost: block Host-header attacks and requests from unexpected origins.
# ALLOWED_HOSTS is comma-separated; set env var to override (e.g. in tests).
_allowed_hosts = [h.strip() for h in settings.ALLOWED_HOSTS.split(",") if h.strip()]
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=_allowed_hosts,
)

# Security response headers
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "font-src 'self' https://fonts.gstatic.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "img-src 'self' data:; "
        "connect-src 'self' ws://localhost:5173 http://localhost:5173;"
    )
    return response

# Rate-limiter state and error handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(auth.router)
app.include_router(audit_logs.router)
app.include_router(queue.router)
app.include_router(purchases.router)
app.include_router(request_items_list.router)  # must be before request_items (has /{id} param)
app.include_router(request_items.router)
app.include_router(requests.router)
app.include_router(items.router)
app.include_router(imports.router)
app.include_router(quick_check.router)
app.include_router(health.router)


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
    langflow_status = "ok" if await langflow_client.ping() else "down"
    return {"status": "ok", "app": settings.APP_NAME, "langflow": langflow_status}
