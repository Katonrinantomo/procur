"""
Shared security utilities for Procur.AI backend.
"""
from __future__ import annotations

from urllib.parse import urlparse

from slowapi import Limiter
from slowapi.util import get_remote_address

# ---------------------------------------------------------------------------
# Rate limiter — single shared instance.
# Import this from routers and main to avoid circular deps.
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address, default_limits=[])

# Rate limit string for LLM-touching endpoints (10 requests per minute per IP).
RATE_LLM = "10/minute"


def safe_http_url(url: str | None) -> str | None:
    """Loloskan hanya URL http/https dengan hostname valid, panjang <= 2048.

    Menolak skema javascript:, file:, data:, ftp:, URL tanpa hostname,
    dan URL yang melebihi 2048 karakter.
    URL yang lolos dikembalikan apa adanya (setelah strip spasi).
    URL yang gagal dikembalikan None.
    """
    if not url:
        return None
    url = url.strip()
    if len(url) > 2048:
        return None
    try:
        p = urlparse(url)
    except Exception:
        return None
    if p.scheme not in ("http", "https"):
        return None
    if not p.hostname:
        return None
    return url
