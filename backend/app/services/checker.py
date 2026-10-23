"""
Check engine — orchestrates match, pricing, flags, and status for each row.

check_item(row, session) — runs the full pipeline for a single RequestItem
    and commits the result.

check_request(request_id, session) — runs check_item for every row in the
    request.

dry_check_item(draft, session) — same pipeline on a plain dict; never writes
    Request, RequestItem, or Flag rows.

Failures are caught and saved as status="pending" + check_error; they never
propagate to the caller.
"""
from __future__ import annotations

import traceback
from datetime import datetime, timezone
from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Flag, Item, Purchase, RequestItem, Stock, Supplier, WebQuote
from app.services import flags as flag_rules
from app.services import pricing
from app.services.matcher import match_item, normalize_name
from app.services.web_check import get_web_quotes


def check_item(row: RequestItem, session: Session) -> None:
    """
    Run the full check pipeline for *row* and flush the changes to the
    session.  Does NOT commit — the caller decides when to commit.

    On any unexpected exception the row is saved with status="pending"
    and check_error set; no exception is re-raised.
    """
    try:
        _do_check(row, session)
    except Exception:
        row.status = "pending"
        row.check_error = traceback.format_exc()
        session.flush()


def _do_check(row: RequestItem, session: Session) -> None:  # noqa: C901
    # ------------------------------------------------------------------
    # 1. Match
    # ------------------------------------------------------------------
    if row.item_id is None:
        matched = match_item(row.raw_name, session)
        if matched is not None:
            row.item_id = matched.id

    item: Item | None = None
    if row.item_id is not None:
        item = session.get(Item, row.item_id)

    # ------------------------------------------------------------------
    # 2 & 3. Reference price
    # ------------------------------------------------------------------
    ref_price: int | None = None
    checked_via: str = "none"
    history_count: int = 0

    if item is not None:
        ref_price, history_count = pricing.reference_from_history(item.id, session)
        if ref_price is not None:
            checked_via = "history"

    if ref_price is None:
        # Fall back to web quotes — may call Langflow for unmatched items
        get_web_quotes(row, session)  # refresh relationship; sets check_error on failure
        if row.check_error:
            # Langflow failed — save as pending and stop processing this row
            row.status = "pending"
            session.flush()
            return
        web_ref = pricing.reference_from_web(
            row.id, session, item_key=normalize_name(row.raw_name)
        )
        if web_ref is not None:
            ref_price = web_ref
            checked_via = "web"

    row.reference_unit_price_idr = ref_price
    row.checked_via = checked_via
    row.history_count = history_count if history_count > 0 else None

    # ------------------------------------------------------------------
    # 4. Difference
    # ------------------------------------------------------------------
    row.diff_pct = pricing.diff_pct(row.quoted_unit_price_idr, ref_price)

    # ------------------------------------------------------------------
    # 5. Flags
    # ------------------------------------------------------------------
    # Clear any previous flags for this row
    session.query(Flag).filter(Flag.request_item_id == row.id).delete()

    new_flags: list[tuple[str, str]] = []

    # PRICE_ABOVE_REF
    result = flag_rules.flag_price_above_ref(
        row.diff_pct,
        checked_via,
        settings.FLAG_PRICE_ABOVE_REF_PCT,
    )
    if result:
        new_flags.append(result)

    # STOCK_COVER_HIGH — only when we matched an item that has stock data
    if item is not None:
        stock: Stock | None = session.get(Stock, item.id)
        if stock is not None:
            result = flag_rules.flag_stock_cover_high(
                stock.qty_on_hand,
                stock.avg_monthly_use,
                settings.FLAG_STOCK_COVER_MONTHS,
            )
            if result:
                new_flags.append(result)

    # QTY_UNUSUAL — compare against past purchase quantities
    if item is not None and row.qty is not None:
        past_qtys = (
            session.execute(
                select(Purchase.qty).where(Purchase.item_id == item.id)
            )
            .scalars()
            .all()
        )
        result = flag_rules.flag_qty_unusual(
            row.qty,
            list(past_qtys),
            settings.FLAG_QTY_UNUSUAL_MULTIPLIER,
        )
        if result:
            new_flags.append(result)

    # NEW_SUPPLIER — supplier named but has no purchases at all
    if row.quoting_supplier_name:
        supplier_id = row.supplier_id
        has_purchases = False
        if supplier_id is not None:
            count = (
                session.execute(
                    select(Purchase.id)
                    .where(Purchase.supplier_id == supplier_id)
                    .limit(1)
                )
                .scalar()
            )
            has_purchases = count is not None
        result = flag_rules.flag_new_supplier(
            row.quoting_supplier_name,
            has_purchases,
        )
        if result:
            new_flags.append(result)

    for code, message in new_flags:
        session.add(Flag(request_item_id=row.id, code=code, message=message))

    # ------------------------------------------------------------------
    # 6. Status
    # ------------------------------------------------------------------
    # Approve/Return are set by user actions — never overwrite them here.
    if row.status not in ("approved", "returned"):
        if new_flags:
            row.status = "flagged"
        elif checked_via == "history":
            row.status = "checked"
        else:
            # web reference or no reference at all
            row.status = "new"

    row.check_error = None
    row.checked_at = datetime.now(tz=timezone.utc)
    session.flush()


# ---------------------------------------------------------------------------
# Dry-run check (no DB writes to Request / RequestItem / Flag)
# ---------------------------------------------------------------------------

class DryCheckDraft(TypedDict):
    raw_name: str
    qty: int | None
    unit: str | None
    quoted_unit_price_idr: int | None
    quoting_supplier_name: str | None
    supplier_id: int | None


def dry_check_item(draft: DryCheckDraft, session: Session) -> dict:  # noqa: C901
    """
    Run the full check pipeline on a draft dict without writing any
    Request, RequestItem, or Flag rows.  Returns a plain dict matching
    the QuickCheckResult schema.

    WebQuote cache rows may still be written by get_web_quotes (acceptable
    side-effect — price cache, not request data).
    """
    result: dict = {
        "raw_name": draft["raw_name"],
        "name": draft["raw_name"],
        "catalog_item_id": None,
        "category": None,
        "qty": draft["qty"],
        "unit": draft["unit"],
        "department": None,
        "quoted_unit_price_idr": draft["quoted_unit_price_idr"],
        "quoting_supplier_name": draft["quoting_supplier_name"],
        "history_count": 0,
        "last_purchases": [],
        "web_quotes": [],
        "reference_unit_price_idr": None,
        "checked_via": "none",
        "diff_pct": None,
        "flags": [],
        "status": "new",
        "check_error": None,
    }

    # ------------------------------------------------------------------
    # 1. Match
    # ------------------------------------------------------------------
    item: Item | None = None
    matched = match_item(draft["raw_name"], session)
    if matched is not None:
        item = matched
        result["catalog_item_id"] = item.id
        result["name"] = item.name
        result["category"] = item.category

    # ------------------------------------------------------------------
    # 2 & 3. Reference price
    # ------------------------------------------------------------------
    ref_price: int | None = None
    checked_via: str = "none"
    history_count: int = 0

    if item is not None:
        ref_price, history_count = pricing.reference_from_history(item.id, session)
        if ref_price is not None:
            checked_via = "history"
            result["history_count"] = history_count

    if ref_price is None:
        # Fall back to web quotes via a transient RequestItem shim
        shim = RequestItem(raw_name=draft["raw_name"])  # not added to session
        get_web_quotes(shim, session)
        if shim.check_error:
            result["status"] = "pending"
            result["check_error"] = shim.check_error
            return result
        item_key = normalize_name(draft["raw_name"])
        web_ref = pricing.reference_from_web(None, session, item_key=item_key)
        if web_ref is not None:
            ref_price = web_ref
            checked_via = "web"

    result["reference_unit_price_idr"] = ref_price
    result["checked_via"] = checked_via

    # ------------------------------------------------------------------
    # 4. Difference
    # ------------------------------------------------------------------
    result["diff_pct"] = pricing.diff_pct(draft["quoted_unit_price_idr"], ref_price)

    # ------------------------------------------------------------------
    # 5. Flags (pure — no ORM writes)
    # ------------------------------------------------------------------
    new_flags: list[dict] = []

    # PRICE_ABOVE_REF
    flag_result = flag_rules.flag_price_above_ref(
        result["diff_pct"],
        checked_via,
        settings.FLAG_PRICE_ABOVE_REF_PCT,
    )
    if flag_result:
        new_flags.append({"code": flag_result[0], "message": flag_result[1]})

    # STOCK_COVER_HIGH
    if item is not None:
        stock: Stock | None = session.get(Stock, item.id)
        if stock is not None:
            flag_result = flag_rules.flag_stock_cover_high(
                stock.qty_on_hand,
                stock.avg_monthly_use,
                settings.FLAG_STOCK_COVER_MONTHS,
            )
            if flag_result:
                new_flags.append({"code": flag_result[0], "message": flag_result[1]})

    # QTY_UNUSUAL
    if item is not None and draft["qty"] is not None:
        past_qtys = (
            session.execute(
                select(Purchase.qty).where(Purchase.item_id == item.id)
            )
            .scalars()
            .all()
        )
        flag_result = flag_rules.flag_qty_unusual(
            draft["qty"],
            list(past_qtys),
            settings.FLAG_QTY_UNUSUAL_MULTIPLIER,
        )
        if flag_result:
            new_flags.append({"code": flag_result[0], "message": flag_result[1]})

    # NEW_SUPPLIER
    if draft["quoting_supplier_name"]:
        supplier_id = draft["supplier_id"]
        has_purchases = False
        if supplier_id is not None:
            count = (
                session.execute(
                    select(Purchase.id)
                    .where(Purchase.supplier_id == supplier_id)
                    .limit(1)
                )
                .scalar()
            )
            has_purchases = count is not None
        flag_result = flag_rules.flag_new_supplier(
            draft["quoting_supplier_name"],
            has_purchases,
        )
        if flag_result:
            new_flags.append({"code": flag_result[0], "message": flag_result[1]})

    result["flags"] = new_flags

    # ------------------------------------------------------------------
    # 6. Status
    # ------------------------------------------------------------------
    if new_flags:
        result["status"] = "flagged"
    elif checked_via == "history":
        result["status"] = "checked"
    else:
        result["status"] = "new"

    # ------------------------------------------------------------------
    # ST-3: last_purchases (history path) / web_quotes (web path)
    # ------------------------------------------------------------------
    if checked_via == "history" and item is not None:
        purchases = (
            session.execute(
                select(Purchase)
                .where(Purchase.item_id == item.id)
                .order_by(Purchase.purchase_date.desc())
                .limit(3)
            )
            .scalars()
            .all()
        )
        result["last_purchases"] = [
            {
                "purchase_date": p.purchase_date,
                "po_number": p.po_number,
                "supplier_name": p.supplier.name,
                "qty": p.qty,
                "unit_price_idr": p.unit_price_idr,
            }
            for p in purchases
        ]
    elif checked_via == "web":
        item_key = normalize_name(draft["raw_name"])
        wq_rows = (
            session.execute(
                select(WebQuote).where(WebQuote.item_key == item_key)
            )
            .scalars()
            .all()
        )
        result["web_quotes"] = [
            {
                "seller": wq.seller,
                "title": wq.title,
                "url": wq.url,
                "price_idr": wq.price_idr,
                "fetched_at": wq.fetched_at,
            }
            for wq in wq_rows
        ]

    return result


def check_request(request_id: int, session: Session) -> None:
    """
    Run check_item for every RequestItem in the given request.
    Commits after all rows are processed.
    """
    rows = (
        session.execute(
            select(RequestItem).where(RequestItem.request_id == request_id)
        )
        .scalars()
        .all()
    )
    for row in rows:
        check_item(row, session)
    session.commit()
