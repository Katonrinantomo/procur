"""
Evidence guards for maker_agent listings.

The evidence model reports listings (url, title, price) it says it found in
the search results for an item.  Python keeps a listing only if:

  1. its URL is a safe http(s) URL,
  2. that URL appears in serper_raw among the results for the same line_no,
  3. that result is a product page, not a marketplace search page, and
  4. its price appears in that result's title, snippet or price field.

A kept listing's per-unit price is the listing price divided by pack_qty
(when the model says one listing holds several of the item's unit),
rounded to whole rupiah.  Everything here is pure: no database, no
network.  Money is integer rupiah only.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from typing import Any
from urllib.parse import urlparse

from app.flows.contracts import EvidenceMatch, strip_fences
from app.security import safe_http_url

# Reason code -> Indonesian label shown in the UI.
DROP_REASONS: dict[str, str] = {
    "bad_url": "URL tidak valid",
    "url_not_in_search": "tidak ada di hasil pencarian",
    "search_page": "halaman pencarian, bukan produk",
    "no_price": "harga tidak tercantum",
    "price_not_in_result": "harga tidak ada di hasil pencarian",
    "bad_pack_qty": "isi kemasan tidak jelas",
}


@dataclass(frozen=True)
class SerperResult:
    url: str
    title: str = ""
    snippet: str = ""
    page_type: str = "product"


@dataclass(frozen=True)
class KeptListing:
    title: str
    url: str
    seller: str | None       # marketplace name
    price_idr: int            # per item unit, after pack_qty
    listing_price_idr: int    # as shown on the listing
    pack_qty: int | None
    match: str                # exact | close


@dataclass(frozen=True)
class DroppedListing:
    title: str
    url: str
    price_idr: int | None
    reason: str


@dataclass
class GuardResult:
    kept: list[KeptListing] = field(default_factory=list)
    dropped: list[DroppedListing] = field(default_factory=list)


# ---------------------------------------------------------------------------
# serper_raw parsing
# ---------------------------------------------------------------------------

def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, int) or (isinstance(value, float) and value.is_integer()):
        return str(int(value))
    return ""


def _result(node: dict) -> SerperResult | None:
    url = node.get("link") or node.get("url")
    if not isinstance(url, str):
        return None
    # The price field ("Rp125.000" or a number) is searched with the snippet.
    snippet = " ".join(p for p in (_text(node.get("snippet")), _text(node.get("price"))) if p)
    page_type = node.get("page_type") if node.get("page_type") == "search_page" else "product"
    return SerperResult(url=url, title=_text(node.get("title")), snippet=snippet, page_type=page_type)


def parse_serper_groups(text: str | None) -> dict[int, list[SerperResult]]:
    """line_no -> search results, from Serper Multi Search's grouped output.

    Expects [{"line_no": 1, "results": [{title, link, snippet, price,
    page_type}, ...]}, ...], optionally in code fences.  Anything else
    returns {} so every listing is dropped.
    """
    if not text:
        return {}
    try:
        data = json.loads(strip_fences(text))
    except (ValueError, TypeError):
        return {}
    if not isinstance(data, list):
        return {}
    groups: dict[int, list[SerperResult]] = {}
    for group in data:
        if not isinstance(group, dict) or not isinstance(group.get("line_no"), int):
            continue
        results = group.get("results")
        if not isinstance(results, list):
            continue
        parsed = [r for r in (_result(n) for n in results if isinstance(n, dict)) if r]
        groups.setdefault(group["line_no"], []).extend(parsed)
    return groups


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


def per_unit_price(price_idr: int, pack_qty: float | None) -> int | None:
    """Listing price per item unit, rounded half up to whole rupiah.

    None pack_qty means one listing is one unit.  A pack_qty that is not a
    positive whole number returns None.
    """
    if pack_qty is None:
        return price_idr
    if pack_qty <= 0 or not float(pack_qty).is_integer():
        return None
    n = int(pack_qty)
    return int(Fraction(price_idr, n) + Fraction(1, 2))


# ---------------------------------------------------------------------------
# Guard
# ---------------------------------------------------------------------------

def guard_listings(matches: list[EvidenceMatch], results: list[SerperResult]) -> GuardResult:
    """Split one item's *matches* into kept and dropped, given that item's
    search results."""
    by_url: dict[str, list[SerperResult]] = {}
    for r in results:
        by_url.setdefault(normalize_url(r.url), []).append(r)

    out = GuardResult()
    for m in matches:
        def drop(reason: str) -> None:
            out.dropped.append(DroppedListing(m.title, m.url, m.price, reason))

        if safe_http_url(m.url) is None:
            drop("bad_url")
            continue
        found = by_url.get(normalize_url(m.url))
        if not found:
            drop("url_not_in_search")
            continue
        if all(r.page_type == "search_page" for r in found):
            drop("search_page")
            continue
        if m.price is None or m.price <= 0:
            drop("no_price")
            continue
        if not any(price_in_text(m.price, f"{r.title} {r.snippet}") for r in found):
            drop("price_not_in_result")
            continue
        unit_price = per_unit_price(m.price, m.pack_qty)
        if unit_price is None or unit_price <= 0:
            drop("bad_pack_qty")
            continue
        out.kept.append(KeptListing(
            title=m.title,
            url=m.url,
            seller=m.marketplace,
            price_idr=unit_price,
            listing_price_idr=m.price,
            pack_qty=int(m.pack_qty) if m.pack_qty is not None else None,
            match=m.match,
        ))
    return out


def summarize_dropped(dropped: list[DroppedListing]) -> dict[str, int]:
    """Reason code -> count, for "2 harga dibuang: tidak ada di hasil pencarian"."""
    counts: dict[str, int] = {}
    for d in dropped:
        counts[d.reason] = counts.get(d.reason, 0) + 1
    return counts
