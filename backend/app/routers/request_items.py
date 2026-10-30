"""
GET  /api/request-items/{id}   — item detail (totals, stock, flags, history/web)
POST /api/request-items/{id}/recheck  — re-run check engine
POST /api/request-items/{id}/approve  — set status approved + log action
POST /api/request-items/{id}/return   — set status returned + log action (with note)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import median

from fastapi import APIRouter, Depends, HTTPException
from fastapi import Request as StarletteRequest
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Action, Flag, Item, Purchase, Request, RequestItem, Stock, WebQuote
from app.schemas import (
    ActionOut,
    ApproveIn,
    FlagOut,
    PurchaseOut,
    RequestItemDetail,
    ReturnIn,
    WebQuoteOut,
)
from app.security import limiter, RATE_LLM
from app.services.checker import check_item

router = APIRouter()

JAKARTA = timezone(timedelta(hours=7))


def _get_or_404(db: Session, item_id: int) -> RequestItem:
    row = db.get(RequestItem, item_id)
    if row is None:
        raise HTTPException(status_code=404, detail="RequestItem not found")
    return row


def _build_detail(ri: RequestItem, db: Session) -> RequestItemDetail:
    req: Request = db.get(Request, ri.request_id)

    # Totals
    quoted_total = (
        ri.quoted_unit_price_idr * ri.qty
        if ri.quoted_unit_price_idr is not None and ri.qty is not None
        else None
    )
    ref_total = (
        ri.reference_unit_price_idr * ri.qty
        if ri.reference_unit_price_idr is not None and ri.qty is not None
        else None
    )
    over_ref = (
        quoted_total - ref_total
        if quoted_total is not None and ref_total is not None
        else None
    )

    # Stock
    qty_on_hand: int | None = None
    avg_monthly_use: int | None = None
    usual_qty: int | None = None
    if ri.item_id is not None:
        stock = db.get(Stock, ri.item_id)
        if stock is not None:
            qty_on_hand = stock.qty_on_hand
            avg_monthly_use = stock.avg_monthly_use
        # Median past purchase quantity (used by QTY_UNUSUAL detail line)
        past_qtys = (
            db.execute(select(Purchase.qty).where(Purchase.item_id == ri.item_id))
            .scalars()
            .all()
        )
        if past_qtys:
            usual_qty = int(median(past_qtys))

    # Flags
    flags = (
        db.execute(select(Flag).where(Flag.request_item_id == ri.id))
        .scalars()
        .all()
    )

    # Last 5 purchases (history path)
    last_purchases = None
    web_quotes_out = None

    if ri.checked_via == "history" and ri.item_id is not None:
        purchases = (
            db.execute(
                select(Purchase)
                .where(Purchase.item_id == ri.item_id)
                .order_by(Purchase.purchase_date.desc())
                .limit(5)
            )
            .scalars()
            .all()
        )
        last_purchases = [
            PurchaseOut(
                purchase_date=p.purchase_date,
                po_number=p.po_number,
                supplier_name=p.supplier.name,
                qty=p.qty,
                unit_price_idr=p.unit_price_idr,
            )
            for p in purchases
        ]
    else:
        # web quotes (covers "web" and "none" paths)
        # Only show quotes that were actually used — linked to this row by
        # link_quotes_to_row during check_item().  No item_key fallback, no
        # request_item_id IS NULL queries.
        wq_rows = (
            db.execute(
                select(WebQuote).where(WebQuote.request_item_id == ri.id)
            )
            .scalars()
            .all()
        )
        if wq_rows:
            web_quotes_out = [
                WebQuoteOut(
                    seller=wq.seller,
                    title=wq.title,
                    url=wq.url,
                    price_idr=wq.price_idr,
                    fetched_at=wq.fetched_at,
                )
                for wq in wq_rows
            ]

    # Actions
    actions = (
        db.execute(
            select(Action)
            .where(Action.request_item_id == ri.id)
            .order_by(Action.created_at)
        )
        .scalars()
        .all()
    )

    return RequestItemDetail(
        id=ri.id,
        request_id=ri.request_id,
        line_no=ri.line_no,
        catalog_item_id=ri.item_id,
        raw_name=ri.raw_name,
        department=ri.department,
        qty=ri.qty,
        unit=ri.unit,
        quoted_unit_price_idr=ri.quoted_unit_price_idr,
        quoting_supplier_name=ri.quoting_supplier_name,
        reference_unit_price_idr=ri.reference_unit_price_idr,
        diff_pct=float(ri.diff_pct) if ri.diff_pct is not None else None,
        checked_via=ri.checked_via,
        history_count=ri.history_count,
        usual_qty=usual_qty,
        status=ri.status,
        check_error=ri.check_error,
        checked_at=ri.checked_at,
        requested_by=req.requested_by,
        requested_at=req.requested_at,
        quoted_total_idr=quoted_total,
        reference_total_idr=ref_total,
        over_reference_idr=over_ref,
        qty_on_hand=qty_on_hand,
        avg_monthly_use=avg_monthly_use,
        flags=[FlagOut(code=f.code, message=f.message) for f in flags],
        last_purchases=last_purchases,
        web_quotes=web_quotes_out,
        actions=[ActionOut.model_validate(a) for a in actions],
    )


# ---------------------------------------------------------------------------
# GET /api/request-items/{id}
# ---------------------------------------------------------------------------

@router.get("/api/request-items/{item_id}", response_model=RequestItemDetail)
def get_request_item(item_id: int, db: Session = Depends(get_db)):
    ri = _get_or_404(db, item_id)
    return _build_detail(ri, db)


# ---------------------------------------------------------------------------
# POST /api/request-items/{id}/recheck
# ---------------------------------------------------------------------------

@router.post("/api/request-items/{item_id}/recheck", response_model=RequestItemDetail)
@limiter.limit(RATE_LLM)
def recheck_request_item(request: StarletteRequest, item_id: int, db: Session = Depends(get_db)):
    ri = _get_or_404(db, item_id)
    check_item(ri, db)
    db.commit()
    db.refresh(ri)
    return _build_detail(ri, db)


# ---------------------------------------------------------------------------
# POST /api/request-items/{id}/approve
# ---------------------------------------------------------------------------

@router.post("/api/request-items/{item_id}/approve", response_model=RequestItemDetail)
def approve_request_item(
    item_id: int,
    body: ApproveIn = ApproveIn(),
    db: Session = Depends(get_db),
):
    ri = _get_or_404(db, item_id)
    ri.status = "approved"
    db.add(Action(
        request_item_id=ri.id,
        action="approve",
        note=None,
        actor=body.actor,
    ))
    db.commit()
    db.refresh(ri)
    return _build_detail(ri, db)


# ---------------------------------------------------------------------------
# POST /api/request-items/{id}/return
# ---------------------------------------------------------------------------

@router.post("/api/request-items/{item_id}/return", response_model=RequestItemDetail)
def return_request_item(
    item_id: int,
    body: ReturnIn,
    db: Session = Depends(get_db),
):
    ri = _get_or_404(db, item_id)
    ri.status = "returned"
    db.add(Action(
        request_item_id=ri.id,
        action="return",
        note=body.note,
        actor=body.actor,
    ))
    db.commit()
    db.refresh(ri)
    return _build_detail(ri, db)
