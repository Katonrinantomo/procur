"""
GET /api/decisions       — decision log, filtered by Jakarta date and subject type
GET /api/decisions.csv   — same rows as CSV (opens in Excel)
GET /api/review          — undecided request rows for the owner's Review page

The decision log is read-only over HTTP: no route updates or deletes a row.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AuditLog, Flag, Request, RequestItem, User, WebQuote
from app.routers.auth import CurrentUser, get_current_user, require_roles
from app.schemas import DecisionOut, QueueRow, ReviewResponse
from app.services.decisions import JAKARTA, decisions_csv, review_sort_key

router = APIRouter(dependencies=[Depends(get_current_user)])

SubjectType = Literal["request_item", "quotation", "bundle"]

# Rows still waiting for a decision. pending rows have not been checked yet.
_REVIEW_STATUSES = ("flagged", "new", "checked")


def _jkt_midnight(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=JAKARTA)


def _query_decisions(
    db: Session,
    date_from: date | None,
    date_to: date | None,
    subject_type: str | None,
) -> list[DecisionOut]:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="'from' must be on or before 'to'")

    stmt = (
        select(AuditLog, User.username, RequestItem.raw_name)
        .outerjoin(User, User.id == AuditLog.user_id)
        .outerjoin(
            RequestItem,
            (AuditLog.subject_type == "request_item") & (RequestItem.id == AuditLog.subject_id),
        )
    )
    if date_from:
        stmt = stmt.where(AuditLog.created_at >= _jkt_midnight(date_from))
    if date_to:
        stmt = stmt.where(AuditLog.created_at < _jkt_midnight(date_to) + timedelta(days=1))
    if subject_type:
        stmt = stmt.where(AuditLog.subject_type == subject_type)

    rows = db.execute(stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())).all()
    return [
        DecisionOut(
            id=log.id,
            created_at=log.created_at,
            subject_type=log.subject_type,
            subject_id=log.subject_id,
            item_name=item_name,
            decision=log.decision,
            reason=log.reason,
            outcome_tag=log.outcome_tag,
            username=username,
            role=log.role,
            snapshot=log.snapshot,
        )
        for log, username, item_name in rows
    ]


@router.get("/api/decisions", response_model=list[DecisionOut])
def list_decisions(
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
    subject_type: Optional[SubjectType] = Query(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles("owner", "finance")),
):
    """Newest first. from/to are Jakarta calendar days, inclusive."""
    return _query_decisions(db, date_from, date_to, subject_type)


@router.get("/api/decisions.csv")
def export_decisions_csv(
    date_from: Optional[date] = Query(None, alias="from"),
    date_to: Optional[date] = Query(None, alias="to"),
    subject_type: Optional[SubjectType] = Query(None),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles("owner", "finance")),
):
    rows = _query_decisions(db, date_from, date_to, subject_type)
    body = decisions_csv(r.model_dump() for r in rows)
    span = f"{date_from or 'all'}_{date_to or 'all'}"
    return Response(
        content=body.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="decisions_{span}.csv"'},
    )


@router.get("/api/review", response_model=ReviewResponse)
def get_review(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles("owner")),
):
    """Every undecided row across dates: flagged first, then risk score descending."""
    pairs = db.execute(
        select(RequestItem, Request, User.username)
        .join(Request, Request.id == RequestItem.request_id)
        .outerjoin(User, User.id == Request.created_by_user_id)
        .where(RequestItem.status.in_(_REVIEW_STATUSES))
    ).all()

    ri_ids = [ri.id for ri, _, _ in pairs]
    flag_codes: dict[int, list[str]] = {ri_id: [] for ri_id in ri_ids}
    web_quote_counts: dict[int, int] = {}
    if ri_ids:
        for f in db.execute(select(Flag).where(Flag.request_item_id.in_(ri_ids))).scalars():
            flag_codes[f.request_item_id].append(f.code)
        for row_id, cnt in db.execute(
            select(WebQuote.request_item_id, func.count(WebQuote.id))
            .where(WebQuote.request_item_id.in_(ri_ids))
            .group_by(WebQuote.request_item_id)
        ).all():
            web_quote_counts[row_id] = cnt

    pairs = sorted(
        pairs,
        key=lambda p: review_sort_key(p[0].status, p[0].risk_score, p[1].requested_at, p[0].line_no),
    )
    rows = [
        QueueRow(
            id=ri.id,
            request_id=ri.request_id,
            line_no=ri.line_no,
            raw_name=ri.raw_name,
            department=ri.department,
            qty=ri.qty,
            unit=ri.unit,
            quoted_unit_price_idr=ri.quoted_unit_price_idr,
            reference_unit_price_idr=ri.reference_unit_price_idr,
            diff_pct=float(ri.diff_pct) if ri.diff_pct is not None else None,
            checked_via=ri.checked_via,
            history_count=ri.history_count,
            web_quote_count=web_quote_counts.get(ri.id),
            status=ri.status,
            requested_by=req.requested_by,
            requested_at=req.requested_at,
            flag_codes=flag_codes.get(ri.id, []),
            risk_score=ri.risk_score,
            entered_by=username,
        )
        for ri, req, username in pairs
    ]
    return ReviewResponse(rows=rows)
