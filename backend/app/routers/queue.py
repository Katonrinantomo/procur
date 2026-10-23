"""GET /api/queue — procurement review queue."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Flag, Request, RequestItem, WebQuote
from app.schemas import QueueResponse, QueueRow, StatusCounts

router = APIRouter()

JAKARTA = timezone(timedelta(hours=7))

# Sort order: flagged → new → checked → approved → returned → pending
_STATUS_ORDER = {"flagged": 0, "new": 1, "checked": 2, "approved": 3, "returned": 4, "pending": 5}


def _today_jakarta() -> date:
    return datetime.now(tz=JAKARTA).date()


@router.get("/api/queue", response_model=QueueResponse)
def get_queue(
    date_param: Optional[str] = Query(None, alias="date"),
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Return all RequestItems whose parent Request was created on *date* (Asia/Jakarta).
    Default date is today in Asia/Jakarta.
    Optionally filter by status.
    Rows are sorted: flagged, new, checked, approved/returned, then by line_no within each group.
    Counts per status are always over the full date (ignoring the status filter).
    """
    if date_param:
        try:
            target_date = date.fromisoformat(date_param)
        except ValueError:
            target_date = _today_jakarta()
    else:
        target_date = _today_jakarta()

    # Bounds in Jakarta timezone → convert to UTC-aware for the DB query
    day_start = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0, tzinfo=JAKARTA)
    day_end = day_start + timedelta(days=1)

    # Fetch all RequestItems for the day (join to Request for requested_at/by)
    stmt = (
        select(RequestItem, Request)
        .join(Request, Request.id == RequestItem.request_id)
        .where(Request.requested_at >= day_start, Request.requested_at < day_end)
    )
    pairs = db.execute(stmt).all()

    # Build count dict over ALL rows (before status filter)
    counts = StatusCounts()
    for ri, _req in pairs:
        field = ri.status if ri.status in ("flagged", "new", "checked", "approved", "returned", "pending") else "pending"
        setattr(counts, field, getattr(counts, field) + 1)

    # Apply optional status filter
    if status:
        pairs = [(ri, req) for ri, req in pairs if ri.status == status]

    # Build flag code map  {request_item_id: [codes]}
    ri_ids = [ri.id for ri, _ in pairs]
    flag_codes: dict[int, list[str]] = {ri_id: [] for ri_id in ri_ids}
    if ri_ids:
        flags = db.execute(
            select(Flag).where(Flag.request_item_id.in_(ri_ids))
        ).scalars().all()
        for f in flags:
            flag_codes[f.request_item_id].append(f.code)

    # Web quote counts  {request_item_id: count}
    web_quote_counts: dict[int, int] = {}
    if ri_ids:
        wq_rows = db.execute(
            select(WebQuote.request_item_id, func.count(WebQuote.id).label("cnt"))
            .where(WebQuote.request_item_id.in_(ri_ids))
            .group_by(WebQuote.request_item_id)
        ).all()
        for row_id, cnt in wq_rows:
            web_quote_counts[row_id] = cnt

    # Assemble rows
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

    # Sort: primary = status group, secondary = line_no
    rows.sort(key=lambda r: (_STATUS_ORDER.get(r.status, 99), r.line_no))

    return QueueResponse(rows=rows, counts=counts)
