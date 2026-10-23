"""GET /api/items/{id}/suppliers — compare suppliers for a catalog item."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Item, Purchase, Supplier
from app.schemas import SupplierSummary, SuppliersResponse

router = APIRouter()


@router.get("/api/items/{item_id}/suppliers", response_model=SuppliersResponse)
def get_item_suppliers(item_id: int, db: Session = Depends(get_db)):
    """
    For a catalog item, return one row per supplier that has purchased it,
    showing last unit price, last purchase date, and total number of buys.
    Sorted by last_unit_price_idr ascending (cheapest last price first).
    """
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")

    # Aggregate: per supplier → buy count + latest purchase date
    agg = (
        db.execute(
            select(
                Purchase.supplier_id,
                func.count(Purchase.id).label("buy_count"),
                func.max(Purchase.purchase_date).label("last_date"),
            )
            .where(Purchase.item_id == item_id)
            .group_by(Purchase.supplier_id)
        )
        .all()
    )

    summaries: list[SupplierSummary] = []
    for row in agg:
        # Fetch the unit_price_idr for that supplier's most recent purchase
        last_purchase = db.execute(
            select(Purchase)
            .where(Purchase.item_id == item_id, Purchase.supplier_id == row.supplier_id)
            .order_by(Purchase.purchase_date.desc())
            .limit(1)
        ).scalar_one()

        supplier = db.get(Supplier, row.supplier_id)

        summaries.append(
            SupplierSummary(
                supplier_id=row.supplier_id,
                supplier_name=supplier.name,
                last_unit_price_idr=last_purchase.unit_price_idr,
                last_purchase_date=last_purchase.purchase_date,
                buy_count=row.buy_count,
            )
        )

    # Sort cheapest last price first
    summaries.sort(key=lambda s: s.last_unit_price_idr)

    return SuppliersResponse(item_id=item_id, item_name=item.name, suppliers=summaries)
