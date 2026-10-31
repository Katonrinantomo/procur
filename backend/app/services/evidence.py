"""
Evidence guards for maker_agent listings.

The model reports listings (title, url, price) it says it found in the
search results.  Python keeps a listing only if:

  1. its URL is a safe http(s) URL,
  2. that URL appears in the raw Serper output (serper_raw), and
  3. its price appears in that search result's title or snippet.

Listings the model marks matches_item=false are dropped too.  Everything
here is pure: no database, no network.  Money is integer rupiah only.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlparse

from app.flows.contracts import MakerListing, strip_fences
from app.security import safe_http_url

# Reason code -> Indonesian label shown in the UI.
DROP_REASONS: dict[str, str] = {
    "bad_url": "URL tidak valid",
    "url_not_in_search": "tidak ada di hasil pencarian",
    "price_not_in_result": "harga tidak ada di hasil pencarian",
    "not_matching_item": "barang tidak cocok",
    "bad_price": "harga tidak valid",
}


@dataclass(frozen=True)
class SerperResult:
    url: str
    title: str = ""
    snippet: str = ""


@dataclass(frozen=True)
class DroppedListing:
    title: str
    url: str
    price_idr: int
    reason: str


@dataclass
class GuardResult:
    kept: list[MakerListing] = field(default_factory=list)
    dropped: list[DroppedListing] = field(default_factory=list)


# ---------------------------------------------------------------------------
# serper_raw parsing
# ---------------------------------------------------------------------------

def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _walk(node: Any, out: list[SerperResult]) -> None:
    if isinstance(node, dict):
        url = node.get("link") or node.get("url")
        if isinstance(url, str) and ("title" in node or "snippet" in node):
            # Serper shopping results carry the price in its own field.
            snippet = " ".join(
                part for part in (_text(node.get("snippet")), _text(node.get("price"))) if part
            )
            out.append(SerperResult(url=url, title=_text(node.get("title")), snippet=snippet))
        for value in node.values():
            _walk(value, out)
    elif isinstance(node, list):
        for value in node:
            _walk(value, out)


def parse_serper_raw(text: str | None) -> list[SerperResult]:
    """Collect every search result (url + title/snippet) in the raw output.

    Accepts a single Serper response, a list of them (Multi Search), or
    either one wrapped in code fences.  Unparseable text returns [].
    """
    if not text:
        return []
    try:
        data = json.loads(strip_fences(text))
    except (ValueError, TypeError):
        return []
    out: list[SerperResult] = []
    _walk(data, out)
    return out


# ---------------------------------------------------------------------------
# URL and price matching
# ---------------------------------------------------------------------------

def normalize_url(url: str) -> str:
    """host + path, lowercased host, no www., scheme, query, fragment or trailing /."""
    p = urlparse(url.strip())
    host = (p.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return f"{host}{p.path.rstrip('/')}"


_NUMBER = re.compile(r"(\d[\d.,]*)\s*(rb|ribu|k|jt|juta)?\b", re.IGNORECASE)
_SUFFIX = {"rb": 1_000, "ribu": 1_000, "k": 1_000, "jt": 1_000_000, "juta": 1_000_000}


def _to_rupiah(number: str, suffix: str | None) -> int | None:
    number = number.rstrip(".,")
    if suffix:
        # "1,45jt" / "1.5jt" / "45rb": the separator is a decimal point.
        try:
            value = Decimal(number.replace(",", ".")) * _SUFFIX[suffix.lower()]
        except InvalidOperation:
            return None
        return int(value) if value == value.to_integral_value() else None
    # "1.450.000,00" / "1,450,000.00": drop a 2-digit decimal tail.
    if re.search(r"[.,]\d{2}$", number) and re.search(r"[.,]\d{3}", number):
        number = number[:-3]
    digits = re.sub(r"[.,]", "", number)
    return int(digits) if digits else None


def prices_in_text(text: str) -> set[int]:
    """Every rupiah amount written in *text*."""
    found: set[int] = set()
    for m in _NUMBER.finditer(text):
        value = _to_rupiah(m.group(1), m.group(2))
        if value is not None:
            found.add(value)
    return found


def price_in_text(price_idr: int, text: str) -> bool:
    return price_idr in prices_in_text(text)


# ---------------------------------------------------------------------------
# Guard
# ---------------------------------------------------------------------------

def guard_listings(listings: list[MakerListing], results: list[SerperResult]) -> GuardResult:
    """Split *listings* into kept and dropped (with a reason code)."""
    by_url: dict[str, list[SerperResult]] = {}
    for r in results:
        by_url.setdefault(normalize_url(r.url), []).append(r)

    out = GuardResult()
    for listing in listings:
        def drop(reason: str) -> None:
            out.dropped.append(
                DroppedListing(listing.title, listing.url, listing.price_idr, reason)
            )

        if listing.price_idr <= 0:
            drop("bad_price")
            continue
        if safe_http_url(listing.url) is None:
            drop("bad_url")
            continue
        matches = by_url.get(normalize_url(listing.url))
        if not matches:
            drop("url_not_in_search")
            continue
        if not any(price_in_text(listing.price_idr, f"{r.title} {r.snippet}") for r in matches):
            drop("price_not_in_result")
            continue
        if not listing.matches_item:
            drop("not_matching_item")
            continue
        out.kept.append(listing)
    return out


def summarize_dropped(dropped: list[DroppedListing]) -> dict[str, int]:
    """Reason code -> count, for "2 harga dibuang: tidak ada di hasil pencarian"."""
    counts: dict[str, int] = {}
    for d in dropped:
        counts[d.reason] = counts.get(d.reason, 0) + 1
    return counts
