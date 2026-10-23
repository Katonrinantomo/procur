"""
Web price check (Flow 2).

get_web_quotes(request_item, session) returns the list of WebQuote ORM objects
for the given RequestItem.

Cache lookup: reuse web_quotes rows whose item_key matches (exactly or via
token_set_ratio ≥ MATCH_THRESHOLD) and that are at most WEB_QUOTE_MAX_AGE_DAYS
old.  If none exist, call the Web check Langflow flow, parse the JSON array,
drop bad offers, keep at most 5, and save them with item_key set.

On any Langflow failure the function returns whatever cached quotes exist
(possibly empty) without raising.
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
from app.models import RequestItem, WebQuote
from app.services.langflow_client import LangflowError, run_flow
from app.services.matcher import normalize_name

logger = logging.getLogger(__name__)

_MAX_QUOTES = 5


def _cache_key(raw_name: str) -> str:
    """Return the normalized item name used as the cache/DB item_key."""
    return normalize_name(raw_name)


def _flow_input(raw_name: str) -> str:
    """Return the search string sent to the Web check flow."""
    return f"harga {normalize_name(raw_name)}"


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
    request_item_id: int | None,
    item_key: str,
    query: str,
    offers: list[dict],
    session: Session,
) -> list[WebQuote]:
    """Validate, filter, persist, and return the new WebQuote rows."""
    saved: list[WebQuote] = []
    for offer in offers:
        url = offer.get("url") or ""
        price_idr = offer.get("price_idr")
        if not url or not isinstance(price_idr, int) or price_idr <= 0:
            continue
        wq = WebQuote(
            request_item_id=request_item_id,
            item_key=item_key,
            query=query,
            title=offer.get("title"),
            url=url,
            seller=offer.get("seller"),
            price_idr=price_idr,
        )
        session.add(wq)
        saved.append(wq)
        if len(saved) >= _MAX_QUOTES:
            break
    session.flush()
    return saved


def get_web_quotes(request_item: RequestItem, session: Session) -> list[WebQuote]:
    """
    Return web quotes for *request_item*, fetching from Langflow if no
    recent cache exists.  Never raises; on Langflow failure the existing
    (possibly empty) cache is returned and check_error is set on the row.
    """
    key = _cache_key(request_item.raw_name)

    cached = _fetch_cached(key, session)
    if cached:
        return cached

    # No recent cache — call the flow
    try:
        offers = _call_flow(_flow_input(request_item.raw_name))
    except (LangflowError, Exception) as exc:  # noqa: BLE001
        msg = f"web_check failed: {exc}"
        logger.warning(msg)
        request_item.check_error = msg
        session.flush()
        # Return any stale quotes that might exist for this item
        session.refresh(request_item)
        return list(request_item.web_quotes)

    new_quotes = _save_quotes(request_item.id, key, key, offers, session)
    session.refresh(request_item)
    return new_quotes
