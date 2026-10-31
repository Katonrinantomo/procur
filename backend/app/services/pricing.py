"""
Reference price computation.

reference_from_history() — mean of the last N (default 3) purchase prices for
    a catalog item, rounded to the nearest whole rupiah.

reference_from_web() — median of web quote prices for a given item_key.
    NOTE: prefer computing the median directly from the quotes returned by
    get_web_quotes() instead of calling this function; it exists for
    stand-alone callers that already have an item_key.

diff_pct() — (quoted − reference) / reference × 100, rounded to 1 decimal.

reference_from_quotes() — median of kept quotes, only with ≥ WEB_MIN_QUOTES.
get_price_status() — band: KOMPETITIF / WAJAR / PERHATIAN / TIDAK WAJAR.
recommend() — SETUJU / NEGOSIASI / TOLAK from the band and diff_pct.
vendor_score() — 0–100 from value-weighted band points and arithmetic.

The model never sets a band, recommendation or score; only these functions do.
"""
from __future__ import annotations

from dataclasses import dataclass
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


def reference_from_quotes(prices: list[int]) -> int | None:
    """
    Median of kept web quote prices, rounded to whole rupiah.

    Returns None when fewer than settings.WEB_MIN_QUOTES positive prices
    remain ("data tidak cukup").
    """
    valid = [p for p in prices if p > 0]
    if len(valid) < settings.WEB_MIN_QUOTES:
        return None
    return round(median(valid))


def get_price_status(diff_pct: float | None) -> str:
    """Classify the percentage difference from the reference price.

    Edges are inclusive: KOMPETITIF <= -10, WAJAR <= +5, PERHATIAN <= +15,
    TIDAK WAJAR above.  Thresholds come from config.
    """
    if diff_pct is None:
        return "UNKNOWN"
    if diff_pct <= settings.PRICE_BAND_KOMPETITIF_PCT:
        return "KOMPETITIF"
    if diff_pct <= settings.PRICE_BAND_WAJAR_PCT:
        return "WAJAR"
    if diff_pct <= settings.PRICE_BAND_PERHATIAN_PCT:
        return "PERHATIAN"
    return "TIDAK WAJAR"


def recommend(band: str, diff_pct: float | None) -> str | None:
    """
    SETUJU for KOMPETITIF and WAJAR; NEGOSIASI for PERHATIAN and for
    TIDAK WAJAR up to +RECOMMEND_TOLAK_PCT; TOLAK above it.
    None when there is no band (no reference).
    """
    if band in ("KOMPETITIF", "WAJAR"):
        return "SETUJU"
    if band == "PERHATIAN":
        return "NEGOSIASI"
    if band == "TIDAK WAJAR":
        if diff_pct is not None and diff_pct <= settings.RECOMMEND_TOLAK_PCT:
            return "NEGOSIASI"
        return "TOLAK"
    return None


# Price points per band for the vendor score (Phase 2 plan, M18).
BAND_POINTS: dict[str, int] = {
    "KOMPETITIF": 100,
    "WAJAR": 85,
    "PERHATIAN": 50,
    "TIDAK WAJAR": 0,
}
_PRICE_WEIGHT = 0.8
_ARITHMETIC_POINTS = 20
_ARITHMETIC_TOLERANCE_IDR = 1


@dataclass(frozen=True)
class ScoreLine:
    band: str
    qty: int | None
    unit_price_idr: int | None
    line_total_idr: int | None


@dataclass(frozen=True)
class VendorScore:
    score: int | None          # 0–100; None when no line has a reference
    price_points: float | None  # 0–100 value-weighted band points
    arithmetic_ok: bool
    covered: int               # lines with a reference
    total: int


def _line_value(line: ScoreLine) -> int | None:
    if line.line_total_idr is not None:
        return line.line_total_idr
    if line.qty is not None and line.unit_price_idr is not None:
        return line.qty * line.unit_price_idr
    return None


def _arithmetic_ok(lines: list[ScoreLine], quote_total_idr: int | None) -> bool:
    if not lines:
        return False
    for line in lines:
        if line.qty is None or line.unit_price_idr is None or line.line_total_idr is None:
            return False
        if abs(line.qty * line.unit_price_idr - line.line_total_idr) > _ARITHMETIC_TOLERANCE_IDR:
            return False
    if quote_total_idr is not None:
        lines_sum = sum(line.line_total_idr for line in lines)  # type: ignore[misc]
        if abs(lines_sum - quote_total_idr) > _ARITHMETIC_TOLERANCE_IDR:
            return False
    return True


def vendor_score(lines: list[ScoreLine], quote_total_idr: int | None = None) -> VendorScore:
    """
    Vendor score 0–100 = 80% price + 20% arithmetic.

    Price: band points weighted by line value, over lines that have a
    reference (band in BAND_POINTS) and a known value.  Arithmetic: 20
    points only if every line total recomputes within Rp 1 and the line
    totals sum to quote_total_idr within Rp 1 (skipped when it is None).
    Score is None when no line has a reference.
    """
    covered_lines = [line for line in lines if line.band in BAND_POINTS]
    arithmetic_ok = _arithmetic_ok(lines, quote_total_idr)

    weighted = 0
    weight = 0
    for line in covered_lines:
        value = _line_value(line)
        if value is None or value <= 0:
            continue
        weighted += BAND_POINTS[line.band] * value
        weight += value

    if weight == 0:
        return VendorScore(None, None, arithmetic_ok, len(covered_lines), len(lines))

    price_points = weighted / weight
    score = round(_PRICE_WEIGHT * price_points + (_ARITHMETIC_POINTS if arithmetic_ok else 0))
    return VendorScore(score, round(price_points, 1), arithmetic_ok, len(covered_lines), len(lines))
