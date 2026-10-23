"""
Reference price computation.

reference_from_history() — mean of the last N (default 3) purchase prices for
    a catalog item, rounded to the nearest whole rupiah.

reference_from_web() — median of web quote prices for a given item_key.
    NOTE: prefer computing the median directly from the quotes returned by
    get_web_quotes() instead of calling this function; it exists for
    stand-alone callers that already have an item_key.

diff_pct() — (quoted − reference) / reference × 100, rounded to 1 decimal.
"""
from __future__ import annotations

from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Purchase, WebQuote


def reference_from_history(item_id: int, session: Session) -> tuple[int | None, int]:
    """
    Return (reference_price, count) where reference_price is the mean of the
    last settings.HISTORY_WINDOW purchases, rounded to whole rupiah.

    Returns (None, 0) when there are no purchases.
    """
    prices = (
        session.execute(
            select(Purchase.unit_price_idr)
            .where(Purchase.item_id == item_id)
            .order_by(Purchase.purchase_date.desc())
            .limit(settings.HISTORY_WINDOW)
        )
        .scalars()
        .all()
    )
    if not prices:
        return None, 0
    return round(sum(prices) / len(prices)), len(prices)


def reference_from_web(
    item_key: str,
    session: Session,
) -> int | None:
    """
    Return the median of cached web quote prices for the given item_key.

    Only queries by item_key — never by request_item_id IS NULL.
    Returns None when there are no quotes.
    """
    prices = (
        session.execute(
            select(WebQuote.price_idr).where(
                WebQuote.item_key == item_key,
                WebQuote.price_idr > 0,
            )
        )
        .scalars()
        .all()
    )
    if not prices:
        return None
    return round(median(prices))


def diff_pct(quoted: int | None, reference: int | None) -> float | None:
    """
    Percentage difference between quoted and reference price, rounded to 1 dp.
    Returns None when either price is missing.
    """
    if quoted is None or reference is None or reference == 0:
        return None
    return round((quoted - reference) / reference * 100, 1)
