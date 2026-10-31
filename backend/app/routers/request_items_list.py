"""
GET /api/request-items   — paginated history of request items across any date range.

This router is registered BEFORE request_items.router in main.py so FastAPI
matches the list path before the /{item_id} path-param route.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Flag, Request, RequestItem, WebQuote
from app.routers.auth import get_current_user
from app.schemas import QueueRow, RequestItemsListResponse

router = APIRouter(dependencies=[Depends(get_current_user)])

JAKARTA = timezone(timedelta(hours=7))
PAGE_SIZE = 50

_STATUS_ORDER = {"flagged": 0, "new": 1, "checked": 2, "approved": 3, "returned": 4, "pending": 5}


def _today_jakarta() -> date:
    return datetime.now(tz=JAKARTA).date()


def _jkt_midnight(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=JAKARTA)


@router.get("/api/request-items", response_model=RequestItemsListResponse)
def list_request_items(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    """
    Return paginated RequestItems from any date range, newest first.
    - date_from / date_to: Jakarta calendar day (inclusive); default last 90 days.
    - status: exact status filter; omit or "all" returns all statuses.
    - page: 1-based; PAGE_SIZE rows per page.
    """
    today = _today_jakarta()

    if date_from:
        try:
            df = date.fromisoformat(date_from)
        except ValueError:
            df = today - timedelta(days=90)
    else:
        df = today - timedelta(days=90)

    if date_to:
        try:
            dt = date.fromisoformat(date_to)
        except ValueError:
            dt = today - timedelta(days=1)
    else:
        dt = today - timedelta(days=1)

    start_dt = _jkt_midnight(df)
    end_dt = _jkt_midnight(dt) + timedelta(days=1)

    stmt = (
        select(RequestItem, Request)
        .join(Request, Request.id == RequestItem.request_id)
        .where(Request.requested_at >= start_dt, Request.requested_at < end_dt)
    )

    if status and status.lower() != "all":
        stmt = stmt.where(RequestItem.status == status)

    # Total count
    count_stmt = select(func.count()).select_from(
        select(RequestItem.id)
        .join(Request, Request.id == RequestItem.request_id)
        .where(Request.requested_at >= start_dt, Request.requested_at < end_dt)
        .where(*(
            [RequestItem.status == status]
            if status and status.lower() != "all"
            else []
        ))
        .subquery()
    )
    total_count: int = db.execute(count_stmt).scalar_one()

    # Paginate — newest first (by request date then line_no)
    offset = (page - 1) * PAGE_SIZE
    pairs = db.execute(
        stmt.order_by(Request.requested_at.desc(), RequestItem.line_no)
        .offset(offset)
        .limit(PAGE_SIZE)
    ).all()

    # Flag codes
    ri_ids = [ri.id for ri, _ in pairs]
    flag_codes: dict[int, list[str]] = {ri_id: [] for ri_id in ri_ids}
    if ri_ids:
        flags = db.execute(
            select(Flag).where(Flag.request_item_id.in_(ri_ids))
        ).scalars().all()
        for f in flags:
            flag_codes[f.request_item_id].append(f.code)

    # Web quote counts
    web_quote_counts: dict[int, int] = {}
    if ri_ids:
        wq_rows = db.execute(
            select(WebQuote.request_item_id, func.count(WebQuote.id).label("cnt"))
            .where(WebQuote.request_item_id.in_(ri_ids))
            .group_by(WebQuote.request_item_id)
        ).all()
        for row_id, cnt in wq_rows:
            web_quote_counts[row_id] = cnt

    rows: list[QueueRow] = []
    for ri, req in pairs:
        rows.append(
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
            )
        )

    return RequestItemsListResponse(
        rows=rows,
        total_count=total_count,
        page=page,
        page_size=PAGE_SIZE,
    )
