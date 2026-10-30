"""
Procurement flag rules.

Each function is pure — it takes only the data it needs and returns either
a (code, message) tuple when the flag fires, or None when it does not.

Thresholds come from app.config.settings so they can be changed without
touching this file.
"""
from __future__ import annotations

from statistics import median

# Points contributed by each flag code toward the composite risk score.
FLAG_RISK_WEIGHT: dict[str, int] = {
    "PRICE_ABOVE_REF": 30,
    "STOCK_COVER_HIGH": 20,
    "QTY_UNUSUAL": 15,
    "NEW_SUPPLIER": 10,
}

# Maximum points the diff_pct magnitude can add on top of flag weights.
DIFF_PCT_MAX_POINTS = 20
MAX_RISK_SCORE = 100


def calculate_risk_score(
    flag_codes: list[str],
    diff_pct: float | None,
) -> int:
    """
    Composite risk score (0–100) for a request item.

    Base is the sum of per-flag weights; the |diff_pct| magnitude adds up to
    DIFF_PCT_MAX_POINTS extra (capped).  The total is clamped to MAX_RISK_SCORE.

    Pure — never touches the database.
    """
    score = sum(FLAG_RISK_WEIGHT.get(code, 0) for code in flag_codes)
    if diff_pct is not None:
        score += min(int(abs(diff_pct)), DIFF_PCT_MAX_POINTS)
    return min(score, MAX_RISK_SCORE)


def flag_price_above_ref(
    diff_pct: float | None,
    checked_via: str,
    threshold: float,
) -> tuple[str, str] | None:
    """
    PRICE_ABOVE_REF — fires when diff_pct > threshold (default 15).

    checked_via is "history" or "web"; the message wording differs.
    """
    if diff_pct is None or diff_pct <= threshold:
        return None
    if checked_via == "web":
        source = "web median"
    else:
        source = "3-buy average"
    return (
        "PRICE_ABOVE_REF",
        f"Price > {threshold:.0f}% above {source}",
    )


def flag_stock_cover_high(
    qty_on_hand: int | None,
    avg_monthly_use: int | None,
    threshold_months: float,
) -> tuple[str, str] | None:
    """
    STOCK_COVER_HIGH — fires when stock cover (months) > threshold_months.

    Message shows cover in weeks: N = round(months × 4.3).
    """
    if (
        qty_on_hand is None
        or avg_monthly_use is None
        or avg_monthly_use == 0
    ):
        return None
    cover_months = qty_on_hand / avg_monthly_use
    if cover_months <= threshold_months:
        return None
    weeks = round(cover_months * 4.3)
    return (
        "STOCK_COVER_HIGH",
        f"Stock covers ~{weeks} weeks of use",
    )


def flag_qty_unusual(
    requested_qty: int | None,
    past_quantities: list[int],
    threshold_multiplier: float,
) -> tuple[str, str] | None:
    """
    QTY_UNUSUAL — fires when requested_qty > threshold_multiplier × median of
    past purchase quantities.
    """
    if not past_quantities or requested_qty is None:
        return None
    med = median(past_quantities)
    if med == 0:
        return None
    ratio = requested_qty / med
    if ratio <= threshold_multiplier:
        return None
    return (
        "QTY_UNUSUAL",
        f"Quantity is about {ratio:.0f}× the usual order",
    )


def flag_new_supplier(
    quoting_supplier_name: str | None,
    supplier_has_purchases: bool,
) -> tuple[str, str] | None:
    """
    NEW_SUPPLIER — fires when a supplier is named but has no purchases at all.
    """
    if not quoting_supplier_name:
        return None
    if supplier_has_purchases:
        return None
    return (
        "NEW_SUPPLIER",
        "Supplier not in purchase history",
    )
