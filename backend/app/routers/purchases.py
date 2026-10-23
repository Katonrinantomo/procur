"""
GET /api/purchases              — paginated purchase history with filters
GET /api/purchases/item/{id}    — last 10 purchases + 3-buy average for one item
GET /api/suppliers              — supplier list for dropdown
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Text, cast, func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Item, Purchase, Supplier
from app.schemas import ItemPurchaseHistory, PurchaseRow, PurchasesResponse, SupplierOption

router = APIRouter()

JAKARTA = timezone(timedelta(hours=7))
PAGE_SIZE = 50


def _today_jakarta() -> date:
    return datetime.now(tz=JAKARTA).date()


def _jkt_midnight(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=JAKARTA)


def _to_purchase_row(p: Purchase) -> PurchaseRow:
    return PurchaseRow(
        id=p.id,
        purchase_date=p.purchase_date,
        po_number=p.po_number,
        item_id=p.item_id,
        item_name=p.item.name,
        supplier_id=p.supplier_id,
        supplier_name=p.supplier.name,
        qty=p.qty,
        unit=p.item.unit,
        unit_price_idr=p.unit_price_idr,
        total_idr=p.qty * p.unit_price_idr,  # both integers, no float
    )


# ---------------------------------------------------------------------------
# GET /api/purchases
# ---------------------------------------------------------------------------

@router.get("/api/purchases", response_model=PurchasesResponse)
def list_purchases(
    search: Optional[str] = Query(None),
    supplier_id: Optional[int] = Query(None),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
):
    """
    Return paginated purchase rows, newest first.
    - search: case-insensitive match against item name, item aliases (JSON LIKE),
              supplier name, or PO number.
    - supplier_id: exact supplier FK filter.
    - date_from / date_to: Jakarta calendar day bounds (inclusive).
    - page: 1-based; PAGE_SIZE rows per page.
    """
    today = _today_jakarta()
    # Default date range: last 90 days
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
            dt = today
    else:
        dt = today

    start_dt = _jkt_midnight(df)
    end_dt = _jkt_midnight(dt) + timedelta(days=1)

    # Base query
    stmt = (
        select(Purchase)
        .join(Item, Item.id == Purchase.item_id)
        .join(Supplier, Supplier.id == Purchase.supplier_id)
        .where(Purchase.purchase_date >= start_dt, Purchase.purchase_date < end_dt)
    )

    if supplier_id is not None:
        stmt = stmt.where(Purchase.supplier_id == supplier_id)

    if search:
        term = f"%{search}%"
        # Cast aliases JSON column to Text for LIKE search (works on SQLite and PostgreSQL)
        stmt = stmt.where(
            or_(
                Item.name.ilike(term),
                cast(Item.aliases, Text).ilike(term),
                Supplier.name.ilike(term),
                Purchase.po_number.ilike(term),
            )
        )

    # Count before pagination
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_count: int = db.execute(count_stmt).scalar_one()

    # Total amount over filtered set (before paging)
    amount_subq = stmt.subquery()
    amount_stmt = select(
        func.coalesce(
            func.sum(amount_subq.c.qty * amount_subq.c.unit_price_idr),
            0,
        )
    )
    total_amount_idr: int = int(db.execute(amount_stmt).scalar_one())

    # Paginate
    offset = (page - 1) * PAGE_SIZE
    paged = db.execute(
        stmt.order_by(Purchase.purchase_date.desc(), Purchase.id.desc())
        .offset(offset)
        .limit(PAGE_SIZE)
    ).scalars().all()

    rows = [_to_purchase_row(p) for p in paged]

    return PurchasesResponse(
        rows=rows,
        total_count=total_count,
        total_amount_idr=total_amount_idr,
        page=page,
        page_size=PAGE_SIZE,
    )


# ---------------------------------------------------------------------------
# GET /api/purchases/item/{item_id}
# ---------------------------------------------------------------------------

@router.get("/api/purchases/item/{item_id}", response_model=ItemPurchaseHistory)
def get_item_purchase_history(item_id: int, db: Session = Depends(get_db)):
    """Return last 10 purchases for the item plus 3-buy average reference price."""
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    last10 = db.execute(
        select(Purchase)
        .where(Purchase.item_id == item_id)
        .order_by(Purchase.purchase_date.desc(), Purchase.id.desc())
        .limit(10)
    ).scalars().all()

    rows = [_to_purchase_row(p) for p in last10]

    # 3-buy average (reference price)
    from app.services.pricing import reference_from_history
    ref_price, _count = reference_from_history(item_id, db)

    return ItemPurchaseHistory(
        item_id=item_id,
        item_name=item.name,
        last_purchases=rows,
        reference_price_idr=ref_price,
    )


# ---------------------------------------------------------------------------
# GET /api/suppliers
# ---------------------------------------------------------------------------

@router.get("/api/suppliers", response_model=list[SupplierOption])
def list_suppliers(db: Session = Depends(get_db)):
    """Return all suppliers sorted by name, for filter dropdowns."""
    suppliers = db.execute(
        select(Supplier).order_by(Supplier.name)
    ).scalars().all()
    return [SupplierOption(id=s.id, name=s.name) for s in suppliers]
