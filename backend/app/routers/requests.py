"""
POST /api/requests        — save a request with its line items and run check_request.
POST /api/requests/parse  — send pasted text to Flow 1, return draft line items.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi import Request as StarletteRequest
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Request, RequestItem, Supplier
from app.schemas import QueueRow, RequestIn
from app.security import limiter, RATE_LLM
from app.services.checker import check_request
from app.services.langflow_client import LangflowError
from app.services.organizer import LineItemDraft, parse_text

router = APIRouter()

JAKARTA = timezone(timedelta(hours=7))


# ---------------------------------------------------------------------------
# POST /api/requests/parse
# ---------------------------------------------------------------------------

class ParseIn(BaseModel):
    text: str = Field(..., max_length=10_000)
    requested_by: Optional[str] = None


@router.post("/api/requests/parse", response_model=list[LineItemDraft])
@limiter.limit(RATE_LLM)
async def parse_request(request: StarletteRequest, body: ParseIn):
    """
    Send pasted text to the Organize flow and return draft line items.
    Saves nothing to the database.
    Returns 502 if Langflow is unreachable or returns an error.
    """
    if not settings.LANGFLOW_ORGANIZE_FLOW_ID:
        raise HTTPException(
            status_code=502,
            detail=(
                "The Organize flow isn't configured. "
                "Set LANGFLOW_ORGANIZE_FLOW_ID in backend/.env."
            ),
        )
    try:
        drafts = await parse_text(body.text)
    except LangflowError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return drafts


@router.post("/api/requests", response_model=list[QueueRow], status_code=201)
def create_request(body: RequestIn, db: Session = Depends(get_db)):
    """
    Save a new request and all its line items, run the check engine on each,
    then return the resulting rows in the same format as the queue.
    """
    now_jkt = datetime.now(tz=JAKARTA)

    req = Request(
        requested_at=body.requested_at or now_jkt,
        requested_by=body.requested_by,
        raw_text=body.raw_text,
    )
    db.add(req)
    db.flush()

    # Resolve supplier names → IDs where possible
    for item_in in body.items:
        supplier_id: int | None = None
        if item_in.quoting_supplier_name:
            sup = (
                db.query(Supplier)
                .filter(Supplier.name == item_in.quoting_supplier_name)
                .first()
            )
            if sup:
                supplier_id = sup.id

        ri = RequestItem(
            request_id=req.id,
            line_no=item_in.line_no,
            raw_name=item_in.raw_name,
            department=item_in.department,
            qty=item_in.qty,
            unit=item_in.unit,
            quoted_unit_price_idr=item_in.quoted_unit_price_idr,
            quoting_supplier_name=item_in.quoting_supplier_name,
            supplier_id=supplier_id,
            status="pending",
        )
        db.add(ri)

    db.flush()

    # Run the check engine (commits internally)
    check_request(req.id, db)

    # Re-fetch the rows with their parent request for the response
    from sqlalchemy import func, select
    from app.models import Flag, WebQuote

    rows_with_req = (
        db.execute(
            select(RequestItem, Request)
            .join(Request, Request.id == RequestItem.request_id)
            .where(RequestItem.request_id == req.id)
            .order_by(RequestItem.line_no)
        )
        .all()
    )

    # Build flag code map
    ri_ids = [ri.id for ri, _ in rows_with_req]
    flag_map: dict[int, list[str]] = {rid: [] for rid in ri_ids}
    for f in db.execute(select(Flag).where(Flag.request_item_id.in_(ri_ids))).scalars():
        flag_map[f.request_item_id].append(f.code)

    # Web quote counts
    web_quote_counts: dict[int, int] = {}
    if ri_ids:
        for row_id, cnt in db.execute(
            select(WebQuote.request_item_id, func.count(WebQuote.id).label("cnt"))
            .where(WebQuote.request_item_id.in_(ri_ids))
            .group_by(WebQuote.request_item_id)
        ).all():
            web_quote_counts[row_id] = cnt

    result: list[QueueRow] = []
    for ri, r in rows_with_req:
        result.append(
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
                requested_by=r.requested_by,
                requested_at=r.requested_at,
                flag_codes=flag_map.get(ri.id, []),
            )
        )

    return result
