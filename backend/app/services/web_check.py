"""
Web price check (Flow 2).

get_web_quotes(raw_name, session) returns the list of WebQuote ORM objects
for the given item name.

Cache lookup: reuse web_quotes rows whose item_key matches (exactly or via
token_set_ratio ≥ MATCH_THRESHOLD) and that are at most WEB_QUOTE_MAX_AGE_DAYS
old.  If none exist, call the Web check Langflow flow, parse the JSON array,
drop bad offers, keep at most 5, and save them with item_key set.

On any Langflow failure the function returns whatever cached quotes exist
(possibly empty) without raising, and returns ([], error_message).  The
caller is responsible for acting on the error.

Callers must NOT pass an unsaved RequestItem or call session.refresh().
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import WebQuote
from app.security import safe_http_url
from app.services.langflow_client import LangflowError, run_flow
from app.services.matcher import normalize_name

logger = logging.getLogger(__name__)

_MAX_QUOTES = 5


def _cache_key(raw_name: str) -> str:
    """Return the normalized item name used as the cache/DB item_key."""
    return normalize_name(raw_name)


def _flow_input(raw_name: str) -> str:
    """Return the search string sent to the Web check flow."""
    query = f"harga {normalize_name(raw_name)} site:tokopedia.com OR site:shopee.co.id OR site:blibli.com OR site:lazada.co.id"
    return query


def _fetch_cached(item_key: str, session: Session) -> list[WebQuote]:
    """
    Return cached WebQuote rows whose item_key matches *item_key* (exact or
    fuzzy token_set_ratio ≥ MATCH_THRESHOLD) and that are within
    WEB_QUOTE_MAX_AGE_DAYS.
    """
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=settings.WEB_QUOTE_MAX_AGE_DAYS)
    # Fetch all candidate rows within the age window that have an item_key.
    candidates: list[WebQuote] = (
        session.execute(
            select(WebQuote)
            .where(WebQuote.item_key.isnot(None), WebQuote.fetched_at >= cutoff)
        )
        .scalars()
        .all()
    )

    threshold = settings.MATCH_THRESHOLD
    matched: list[WebQuote] = []
    for row in candidates:
        if row.item_key == item_key:
            matched.append(row)
        elif fuzz.token_set_ratio(item_key, row.item_key) >= threshold:
            matched.append(row)

    return matched


def _call_flow(flow_input: str) -> list[dict]:
    """
    Call the Web check flow synchronously and return the parsed JSON array.
    Raises LangflowError on failure; callers must handle it.
    """
    raw = asyncio.run(run_flow(settings.LANGFLOW_WEBCHECK_FLOW_ID, flow_input))
    # Strip optional code fences
    raw = raw.strip()
    if raw.startswith("```"):
        import re
        m = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw, re.IGNORECASE)
        raw = m.group(1).strip() if m else raw
    return json.loads(raw)


def _save_quotes(
    item_key: str,
    query: str,
    offers: list[dict],
    session: Session,
) -> list[WebQuote]:
    """Validate, filter, persist, and return the new WebQuote rows.

    Quotes are saved with request_item_id=None (standalone cache rows).
    Call link_quotes_to_row() after the RequestItem is flushed to associate them.
    """
    saved: list[WebQuote] = []
    for offer in offers:
        raw_url = offer.get("url") or ""
        price_idr = offer.get("price_idr")
        if not isinstance(price_idr, int) or price_idr <= 0:
            continue
        # Validate URL — only http/https with a real hostname are kept.
        # Quotes with an invalid URL are stored with url=None (price still saved).
        safe_url = safe_http_url(raw_url)
        wq = WebQuote(
            request_item_id=None,
            item_key=item_key,
            query=query,
            title=offer.get("title"),
            url=safe_url,
            seller=offer.get("seller"),
            price_idr=price_idr,
        )
        session.add(wq)
        saved.append(wq)
        if len(saved) >= _MAX_QUOTES:
            break
    session.flush()
    return saved


def link_quotes_to_row(quotes: list[WebQuote], request_item_id: int, session: Session) -> None:
    """
    Associate *quotes* with the given saved RequestItem id.

    For quotes that currently have no request_item_id (standalone cache rows),
    sets the FK directly.  For quotes already linked to a different row,
    creates a lightweight copy linked to this row so the inspector can find
    them later via request_item_id.
    """
    for wq in quotes:
        if wq.request_item_id is None:
            wq.request_item_id = request_item_id
        elif wq.request_item_id != request_item_id:
            # Quote is already owned by another row — clone it for this row
            copy = WebQuote(
                request_item_id=request_item_id,
                item_key=wq.item_key,
                query=wq.query,
                title=wq.title,
                url=wq.url,
                seller=wq.seller,
                price_idr=wq.price_idr,
                fetched_at=wq.fetched_at,
            )
            session.add(copy)
    session.flush()


def get_web_quotes(raw_name: str, session: Session) -> tuple[list[WebQuote], str | None]:
    """
    Return (quotes, error_message) for *raw_name*.

    Tries cached quotes first (fuzzy name match within WEB_QUOTE_MAX_AGE_DAYS).
    If none exist, calls the Langflow Web check flow.

    On Langflow failure: returns whatever stale quotes exist plus an error string.
    The caller decides whether to treat this as fatal (check_error) or silent.

    Never calls session.refresh() and never accesses ORM relationships.
    """
    key = _cache_key(raw_name)

    cached = _fetch_cached(key, session)
    if cached:
        return cached, None

    # No recent cache — call the flow
    try:
        offers = _call_flow(_flow_input(raw_name))
    except (LangflowError, Exception) as exc:  # noqa: BLE001
        msg = f"web_check failed: {exc}"
        logger.warning(msg)
        # Return any stale quotes for this key (skips the age filter),
        # applying the same fuzzy-match threshold so only relevant quotes are returned.
        stale_candidates = (
            session.execute(
                select(WebQuote)
                .where(WebQuote.item_key.isnot(None))
            )
            .scalars()
            .all()
        )
        stale_matched: list[WebQuote] = []
        for row in stale_candidates:
            if row.item_key == key:
                stale_matched.append(row)
            elif fuzz.token_set_ratio(key, row.item_key) >= settings.MATCH_THRESHOLD:
                stale_matched.append(row)
        return stale_matched, msg

    new_quotes = _save_quotes(key, key, offers, session)
    return new_quotes, None
