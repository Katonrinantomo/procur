"""
Vendor quotations (M18).

POST /api/quotations                — upload a PDF/XLSX quotation (purchasing),
                                      extract text, run maker_agent MODE: PENAWARAN,
                                      store lines with band/recommendation/score.
GET  /api/quotations                — 20 most recent quotations.
GET  /api/quotations/{id}           — one quotation with its lines.
POST /api/quotations/{id}/to-queue  — turn the lines into a request on today's
                                      queue and run the check engine (creator only).
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi import Request as StarletteRequest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Quotation, Request, RequestItem, Supplier
from app.routers.auth import CurrentUser, get_current_user, require_roles
from app.routers.requests import build_queue_rows
from app.schemas import (
    QueueRow,
    QuotationLineOut,
    QuotationOut,
    QuotationSummary,
    QuoteDroppedOut,
    QuoteEvidenceOut,
)
from app.security import RATE_LLM, limiter
from app.services.checker import check_request
from app.services.evidence import DROP_REASONS
from app.services.quotation import UnreadableDocument, check_quotation, extract_text

router = APIRouter(dependencies=[Depends(get_current_user)])

JAKARTA = timezone(timedelta(hours=7))

_MAGIC = {"pdf": b"%PDF-", "xlsx": b"PK\x03\x04"}


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def _to_out(q: Quotation) -> QuotationOut:
    summary: dict[str, int] = {}
    lines: list[QuotationLineOut] = []
    for line in q.lines:
        dropped: list[QuoteDroppedOut] = []
        for d in line.dropped or []:
            label = DROP_REASONS.get(d.get("reason", ""), d.get("reason", ""))
            summary[label] = summary.get(label, 0) + 1
            dropped.append(QuoteDroppedOut(
                title=d.get("title"), url=d.get("url"), price_idr=d.get("price_idr"),
                reason=d.get("reason", ""), reason_label=label,
            ))
        lines.append(QuotationLineOut(
            line_no=line.line_no,
            name=line.name,
            qty=line.qty,
            unit=line.unit,
            unit_price_idr=line.unit_price_idr,
            line_total_idr=line.line_total_idr,
            catalog_item_id=line.item_id,
            reference_unit_price_idr=line.reference_unit_price_idr,
            reference_source=line.reference_source,
            history_count=line.history_count,
            diff_pct=float(line.diff_pct) if line.diff_pct is not None else None,
            band=line.band,
            recommendation=line.recommendation,
            evidence=[QuoteEvidenceOut(**e) for e in line.evidence or []],
            dropped=dropped,
        ))
    return QuotationOut(
        id=q.id,
        filename=q.filename,
        status=q.status,
        check_error=q.check_error,
        vendor_name=q.vendor_name,
        quote_no=q.quote_no,
        quote_date=q.quote_date,
        quote_total_idr=q.quote_total_idr,
        vendor_score=q.vendor_score,
        price_points=float(q.price_points) if q.price_points is not None else None,
        arithmetic_ok=q.arithmetic_ok,
        covered_lines=q.covered_lines,
        total_lines=q.total_lines,
        dropped_count=q.dropped_count,
        dropped_summary=summary,
        request_id=q.request_id,
        created_by_user_id=q.created_by_user_id,
        created_at=q.created_at,
        lines=lines,
    )


def _get_or_404(quotation_id: int, db: Session) -> Quotation:
    q = db.get(Quotation, quotation_id)
    if q is None:
        raise HTTPException(status_code=404, detail="Quotation not found")
    return q


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/api/quotations", response_model=QuotationOut, status_code=201)
@limiter.limit(RATE_LLM)
def upload_quotation(
    request: StarletteRequest,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles("purchasing")),
):
    filename = file.filename or "quotation"
    lower = filename.lower()
    kind = "pdf" if lower.endswith(".pdf") else "xlsx" if lower.endswith(".xlsx") else None
    if kind is None:
        raise HTTPException(status_code=400, detail="Only .pdf and .xlsx files are supported")

    max_bytes = settings.QUOTATION_MAX_BYTES
    raw = file.file.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File is too large. Maximum size is {max_bytes // (1024 * 1024)} MB.",
        )
    if not raw.startswith(_MAGIC[kind]):
        raise HTTPException(
            status_code=400,
            detail=f"File does not appear to be a valid .{kind} file (invalid header).",
        )

    q = Quotation(
        created_by_user_id=current_user.id,
        filename=filename[:255],
        file_sha256=hashlib.sha256(raw).hexdigest(),
        status="pending",
    )
    db.add(q)
    db.flush()

    try:
        text = extract_text(raw, kind)
    except UnreadableDocument as exc:
        q.status = "unreadable"
        q.check_error = str(exc)
    else:
        check_quotation(q, text, db)

    db.commit()
    db.refresh(q)
    return _to_out(q)


@router.get("/api/quotations", response_model=list[QuotationSummary])
def list_quotations(db: Session = Depends(get_db)):
    rows = (
        db.execute(select(Quotation).order_by(Quotation.created_at.desc(), Quotation.id.desc()).limit(20))
        .scalars()
        .all()
    )
    return [
        QuotationSummary(
            id=q.id, filename=q.filename, status=q.status,
            vendor_name=q.vendor_name, vendor_score=q.vendor_score, created_at=q.created_at,
        )
        for q in rows
    ]


@router.get("/api/quotations/{quotation_id}", response_model=QuotationOut)
def get_quotation(quotation_id: int, db: Session = Depends(get_db)):
    return _to_out(_get_or_404(quotation_id, db))


@router.post(
    "/api/quotations/{quotation_id}/to-queue",
    response_model=list[QueueRow],
    status_code=201,
)
def quotation_to_queue(
    quotation_id: int,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles("purchasing")),
):
    q = _get_or_404(quotation_id, db)
    if q.created_by_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the user who uploaded this quotation can queue it")
    if q.request_id is not None or q.status == "queued":
        raise HTTPException(status_code=409, detail="Quotation is already on the queue")
    if q.status != "checked" or not q.lines:
        raise HTTPException(status_code=422, detail="Quotation has no checked lines to queue")

    supplier_id: int | None = None
    if q.vendor_name:
        sup = db.execute(select(Supplier).where(Supplier.name == q.vendor_name)).scalar_one_or_none()
        if sup is not None:
            supplier_id = sup.id

    label = " · ".join(part for part in (q.quote_no, q.vendor_name) if part) or q.filename
    req = Request(
        requested_at=datetime.now(tz=JAKARTA),
        requested_by=current_user.username,
        raw_text=f"Penawaran {label}",
        created_by_user_id=current_user.id,
    )
    db.add(req)
    db.flush()

    for line in q.lines:
        db.add(RequestItem(
            request_id=req.id,
            line_no=line.line_no,
            raw_name=line.name,
            item_id=line.item_id,
            qty=line.qty,
            unit=line.unit,
            quoted_unit_price_idr=line.unit_price_idr,
            quoting_supplier_name=q.vendor_name,
            supplier_id=supplier_id,
            status="pending",
        ))
    q.request_id = req.id
    q.status = "queued"
    db.flush()

    # Runs the check engine on every row and commits.
    check_request(req.id, db)
    return build_queue_rows(req.id, db)
