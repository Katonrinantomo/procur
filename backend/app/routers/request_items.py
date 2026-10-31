"""
GET  /api/request-items/{id}   — item detail (totals, stock, flags, history/web)
POST /api/request-items/{id}/recheck  — re-run check engine
POST /api/request-items/{id}/approve  — set status approved + log decision
POST /api/request-items/{id}/return   — set status returned + log decision (reason required)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import median

from fastapi import APIRouter, Depends, HTTPException
from fastapi import Request as StarletteRequest
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.routers.auth import CurrentUser, get_current_user, require_roles
from app.db import get_db
from app.models import AuditLog, Flag, Purchase, Request, RequestItem, Stock, User, WebQuote
from app.schemas import (
    ActionOut,
    ApproveIn,
    DecisionOut,
    FlagOut,
    PurchaseOut,
    RequestItemDetail,
    ReturnIn,
    WebQuoteOut,
)
from app.security import limiter, mask_pii, RATE_LLM
from app.services.checker import check_item
from app.services.decisions import DecisionError, is_override, record_request_item_decision
from app.services.pricing import get_price_status

# Router-level auth: all endpoints in this router require a valid token.
# Role-specific restrictions are applied per endpoint with require_roles().
router = APIRouter(dependencies=[Depends(get_current_user)])

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

    # Decision history (oldest first) with the decider's username
    decision_rows = db.execute(
        select(AuditLog, User.username)
        .outerjoin(User, User.id == AuditLog.user_id)
        .where(AuditLog.subject_type == "request_item", AuditLog.subject_id == ri.id)
        .order_by(AuditLog.created_at, AuditLog.id)
    ).all()
    decisions = [
        DecisionOut(
            id=log.id,
            created_at=log.created_at,
            subject_type=log.subject_type,
            subject_id=log.subject_id,
            item_name=ri.raw_name,
            decision=log.decision,
            reason=log.reason,
            outcome_tag=log.outcome_tag,
            username=username,
            role=log.role,
            snapshot=log.snapshot,
        )
        for log, username in decision_rows
    ]
    # Legacy view of the same decisions, kept for older clients.
    actions = [
        ActionOut(action=d.decision, note=d.reason, actor=d.username, created_at=d.created_at)
        for d in decisions
    ]

    entered_by = None
    if req.created_by_user_id is not None:
        entered_by = db.execute(
            select(User.username).where(User.id == req.created_by_user_id)
        ).scalar_one_or_none()

    diff_pct = float(ri.diff_pct) if ri.diff_pct is not None else None

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
        quoting_supplier_name=(
            mask_pii(ri.quoting_supplier_name)
            if ri.quoting_supplier_name is not None
            else None
        ),
        reference_unit_price_idr=ri.reference_unit_price_idr,
        diff_pct=diff_pct,
        price_status=get_price_status(diff_pct),
        checked_via=ri.checked_via,
        history_count=ri.history_count,
        usual_qty=usual_qty,
        status=ri.status,
        risk_score=ri.risk_score,
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
        actions=actions,
        decisions=decisions,
        entered_by=entered_by,
        override_required=is_override((f.code for f in flags), ri.risk_score, ri.status),
    )


# ---------------------------------------------------------------------------
# GET /api/request-items/{id}
# All authenticated users may read a row.
# ---------------------------------------------------------------------------

@router.get("/api/request-items/{item_id}", response_model=RequestItemDetail)
def get_request_item(item_id: int, db: Session = Depends(get_db)):
    ri = _get_or_404(db, item_id)
    return _build_detail(ri, db)


# ---------------------------------------------------------------------------
# POST /api/request-items/{id}/recheck
# purchasing: own returned rows; owner: any row.
# We allow both roles and verify per-row ownership in the handler.
# ---------------------------------------------------------------------------

@router.post("/api/request-items/{item_id}/recheck", response_model=RequestItemDetail)
@limiter.limit(RATE_LLM)
def recheck_request_item(
    request: StarletteRequest,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    ri = _get_or_404(db, item_id)

    # purchasing may only recheck their own returned rows; owner may recheck any
    if current_user.role == "purchasing":
        parent_req = db.get(Request, ri.request_id)
        if parent_req is None or parent_req.created_by_user_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Purchasing can only recheck their own returned rows",
            )
    elif current_user.role not in ("owner",):
        raise HTTPException(status_code=403, detail="Not authorised to recheck")

    check_item(ri, db)
    db.commit()
    db.refresh(ri)
    return _build_detail(ri, db)


def _decide(
    item_id: int,
    decision: str,
    reason: str | None,
    outcome_tag: str | None,
    db: Session,
    current_user: CurrentUser,
) -> RequestItemDetail:
    ri = _get_or_404(db, item_id)

    # Self-approval guard: owner may not decide on a request they created
    parent_req = db.get(Request, ri.request_id)
    if parent_req is not None and parent_req.created_by_user_id == current_user.id:
        verb = "approve" if decision == "approve" else "return"
        raise HTTPException(
            status_code=403,
            detail=f"You cannot {verb} a request you created",
        )

    try:
        record_request_item_decision(
            db,
            ri,
            decision=decision,
            user_id=current_user.id,
            role=current_user.role,
            reason=reason,
            outcome_tag=outcome_tag,
        )
    except DecisionError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    db.refresh(ri)
    return _build_detail(ri, db)


# ---------------------------------------------------------------------------
# POST /api/request-items/{id}/approve
# owner only; 403 if the owner created the request.
# Approving a flagged or high-risk row (an override) needs reason + outcome_tag.
# ---------------------------------------------------------------------------

@router.post("/api/request-items/{item_id}/approve", response_model=RequestItemDetail)
def approve_request_item(
    item_id: int,
    body: ApproveIn = ApproveIn(),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles("owner")),
):
    return _decide(item_id, "approve", body.reason, body.outcome_tag, db, current_user)


# ---------------------------------------------------------------------------
# POST /api/request-items/{id}/return
# owner only; 403 if the owner created the request. Reason required.
# ---------------------------------------------------------------------------

@router.post("/api/request-items/{item_id}/return", response_model=RequestItemDetail)
def return_request_item(
    item_id: int,
    body: ReturnIn,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles("owner")),
):
    reason = body.reason if body.reason is not None else body.note
    return _decide(item_id, "return", reason, body.outcome_tag, db, current_user)
