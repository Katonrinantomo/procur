"""
POST /api/quick-check — dry-run price check.

Parses freeform text into draft line items (via Organize flow), runs the full
check pipeline on each draft (match → reference price → diff_pct → flags →
status), and returns the results without writing any request, request_item, or
flag rows to the database.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Supplier
from app.schemas import QuickCheckResult
from app.services.checker import DryCheckDraft, dry_check_item
from app.services.langflow_client import LangflowError
from app.services.organizer import parse_text

router = APIRouter()


class QuickCheckIn(BaseModel):
    text: str


@router.post("/api/quick-check", response_model=list[QuickCheckResult])
async def quick_check(body: QuickCheckIn, db: Session = Depends(get_db)):
    """
    Parse *text* via the Organize flow, then dry-check each draft item.
    Returns 502 if Langflow is unreachable.
    Per-item check errors are included inline (not a 502).
    """
    try:
        drafts = await parse_text(body.text)
    except LangflowError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    results: list[QuickCheckResult] = []

    for draft in drafts:
        # Resolve supplier name → id (same pattern as create_request)
        supplier_id: int | None = None
        if draft.supplier:
            sup = (
                db.query(Supplier)
                .filter(Supplier.name == draft.supplier)
                .first()
            )
            if sup:
                supplier_id = sup.id

        dry_draft: DryCheckDraft = {
            "raw_name": draft.name,
            "qty": draft.qty,
            "unit": draft.unit,
            "quoted_unit_price_idr": draft.quoted_unit_price_idr,
            "quoting_supplier_name": draft.supplier,
            "supplier_id": supplier_id,
        }

        row = dry_check_item(dry_draft, db)
        results.append(QuickCheckResult.model_validate(row))

    return results
