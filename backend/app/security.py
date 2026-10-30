"""
Shared security utilities for Procur.AI backend.
"""
from __future__ import annotations

import ipaddress
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
    Blokir juga IP lokal/privat (loopback, link-local, private) untuk cegah SSRF.
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
    # Blokir IP lokal/privat untuk mencegah SSRF
    try:
        ip = ipaddress.ip_address(p.hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            return None
    except ValueError:
        # Bukan IP numerik, berarti domain teks.
        # Blokir localhost secara eksplisit (loopback via hostname).
        if p.hostname and p.hostname.lower() in ("localhost",):
            return None
        pass
    return url


# ---------------------------------------------------------------------------
# Password hashing (PBKDF2-HMAC-SHA256, stdlib only)
# ---------------------------------------------------------------------------
import base64
import hashlib
import hmac
import json
import time
from app.config import settings

_SALT = b"procur.ai"
_HASH_NAME = "sha256"
_ITERATIONS = 100_000
_DK_LEN = 32

def hash_password(password: str) -> str:
    dk = hashlib.pbkdf2_hmac(_HASH_NAME, password.encode(), _SALT, _ITERATIONS, dklen=_DK_LEN)
    return base64.urlsafe_b64encode(dk).decode()

def verify_password(password: str, hashed: str) -> bool:
    try:
        expected = base64.urlsafe_b64decode(hashed.encode())
        actual = hashlib.pbkdf2_hmac(_HASH_NAME, password.encode(), _SALT, _ITERATIONS, dklen=_DK_LEN)
        return hmac.compare_digest(expected, actual)
    except Exception:
        return False

# ---------------------------------------------------------------------------
# JWT (HMAC-SHA256, stdlib only)
# ---------------------------------------------------------------------------
_SECRET_KEY = getattr(settings, "SECRET_KEY", "procur.ai-dev-secret-change-me").encode()
_JWT_ALG = "HS256"
_JWT_EXPIRY_SECONDS = 3600  # 1 hour

def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def _base64url_decode(data: str) -> bytes:
    padding = "=" * (4 - (len(data) % 4))
    return base64.urlsafe_b64decode(data + padding)

def create_access_token(user_id: int, role: str) -> str:
    header = {"alg": _JWT_ALG, "typ": "JWT"}
    payload = {"sub": str(user_id), "role": role, "exp": int(time.time()) + _JWT_EXPIRY_SECONDS}
    
    header_b64 = _base64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = _base64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    
    signing_input = f"{header_b64}.{payload_b64}".encode()
    signature = hmac.new(_SECRET_KEY, signing_input, hashlib.sha256).digest()
    signature_b64 = _base64url_encode(signature)
    
    return f"{header_b64}.{payload_b64}.{signature_b64}"

def decode_access_token(token: str) -> dict:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return {}
        header_b64, payload_b64, signature_b64 = parts
        
        signing_input = f"{header_b64}.{payload_b64}".encode()
        expected_sig = hmac.new(_SECRET_KEY, signing_input, hashlib.sha256).digest()
        actual_sig = _base64url_decode(signature_b64)
        
        if not hmac.compare_digest(expected_sig, actual_sig):
            return {}
            
        payload = json.loads(_base64url_decode(payload_b64).decode())
        if payload.get("exp", 0) < time.time():
            return {}
            
        return payload
    except Exception:
        return {}
