"""Pydantic v2 response (and request) schemas for Procur.AI REST API."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Queue
# ---------------------------------------------------------------------------

class QueueRow(BaseModel):
    id: int
    request_id: int
    line_no: int
    raw_name: str
    department: Optional[str]
    qty: Optional[int]
    unit: Optional[str]
    quoted_unit_price_idr: Optional[int]
    reference_unit_price_idr: Optional[int]
    diff_pct: Optional[float]
    checked_via: Optional[str]
    history_count: Optional[int]
    web_quote_count: Optional[int]
    status: str
    requested_by: Optional[str]
    requested_at: datetime
    flag_codes: list[str]
    risk_score: int = 0

    model_config = {"from_attributes": True}


class StatusCounts(BaseModel):
    flagged: int = 0
    new: int = 0
    checked: int = 0
    approved: int = 0
    returned: int = 0
    pending: int = 0


class QueueResponse(BaseModel):
    rows: list[QueueRow]
    counts: StatusCounts


# ---------------------------------------------------------------------------
# Request item detail
# ---------------------------------------------------------------------------

class FlagOut(BaseModel):
    code: str
    message: str

    model_config = {"from_attributes": True}


class PurchaseOut(BaseModel):
    purchase_date: datetime
    po_number: Optional[str]
    supplier_name: str
    qty: int
    unit_price_idr: int

    model_config = {"from_attributes": True}


class WebQuoteOut(BaseModel):
    seller: Optional[str]
    title: Optional[str]
    url: Optional[str]
    price_idr: int
    fetched_at: datetime

    model_config = {"from_attributes": True}


class ActionOut(BaseModel):
    action: str
    note: Optional[str]
    actor: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogOut(BaseModel):
    action: str
    note: Optional[str]
    actor_role: str
    created_at: datetime

    model_config = {"from_attributes": True}


class RequestItemDetail(BaseModel):
    # Row fields
    id: int
    request_id: int
    line_no: int
    catalog_item_id: Optional[int]  # matched catalog item (None for new items)
    raw_name: str
    department: Optional[str]
    qty: Optional[int]
    unit: Optional[str]
    quoted_unit_price_idr: Optional[int]
    quoting_supplier_name: Optional[str]
    reference_unit_price_idr: Optional[int]
    diff_pct: Optional[float]
    checked_via: Optional[str]
    history_count: Optional[int]
    usual_qty: Optional[int]         # median past purchase qty (for QTY_UNUSUAL detail)
    status: str
    risk_score: int = 0
    check_error: Optional[str]
    checked_at: Optional[datetime]

    # Requester and time (from parent request)
    requested_by: Optional[str]
    requested_at: datetime

    # Totals (computed)
    quoted_total_idr: Optional[int]          # qty × quoted_unit_price_idr
    reference_total_idr: Optional[int]       # qty × reference_unit_price_idr
    over_reference_idr: Optional[int]        # quoted_total − reference_total

    # Stock
    qty_on_hand: Optional[int]
    avg_monthly_use: Optional[int]

    # Flags
    flags: list[FlagOut]

    # History (last 5 purchases) OR web quotes
    last_purchases: Optional[list[PurchaseOut]]   # when checked_via == "history"
    web_quotes: Optional[list[WebQuoteOut]]       # when checked_via == "web"

    # Audit trail
    actions: list[ActionOut]

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# POST /api/requests  — inbound body
# ---------------------------------------------------------------------------

class RequestItemIn(BaseModel):
    line_no: int
    raw_name: str
    department: Optional[str] = None
    qty: Optional[int] = None
    unit: Optional[str] = None
    quoted_unit_price_idr: Optional[int] = None
    quoting_supplier_name: Optional[str] = None


class RequestIn(BaseModel):
    requested_by: Optional[str] = None
    requested_at: Optional[datetime] = None   # defaults to now(Jakarta)
    raw_text: Optional[str] = None
    items: list[RequestItemIn]


# ---------------------------------------------------------------------------
# Supplier comparison
# ---------------------------------------------------------------------------

class SupplierSummary(BaseModel):
    supplier_id: int
    supplier_name: str
    last_unit_price_idr: int
    last_purchase_date: datetime
    buy_count: int


class SuppliersResponse(BaseModel):
    item_id: int
    item_name: str
    suppliers: list[SupplierSummary]


# ---------------------------------------------------------------------------
# Action endpoints — inbound body
# ---------------------------------------------------------------------------

class ReturnIn(BaseModel):
    note: str
    actor: Optional[str] = None


class ApproveIn(BaseModel):
    actor: Optional[str] = None


# ---------------------------------------------------------------------------
# Purchases history
# ---------------------------------------------------------------------------

class PurchaseRow(BaseModel):
    id: int
    purchase_date: datetime
    po_number: Optional[str]
    item_id: int
    item_name: str
    supplier_id: int
    supplier_name: str
    qty: int
    unit: str
    unit_price_idr: int
    total_idr: int  # qty × unit_price_idr, computed in Python


class PurchasesResponse(BaseModel):
    rows: list[PurchaseRow]
    total_count: int
    total_amount_idr: int
    page: int
    page_size: int


class SupplierOption(BaseModel):
    id: int
    name: str


class ItemPurchaseHistory(BaseModel):
    item_id: int
    item_name: str
    last_purchases: list[PurchaseRow]
    reference_price_idr: Optional[int]  # 3-buy average


# ---------------------------------------------------------------------------
# Request items list (History → Requests tab)
# ---------------------------------------------------------------------------

class RequestItemsListResponse(BaseModel):
    rows: list[QueueRow]
    total_count: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Quick check (dry-run — no DB writes)
# ---------------------------------------------------------------------------

class QuickCheckResult(BaseModel):
    raw_name: str
    name: str                            # catalog item name, or raw_name if unmatched
    catalog_item_id: Optional[int]
    category: Optional[str]             # catalog item category
    qty: Optional[int]
    unit: Optional[str]
    department: Optional[str]
    quoted_unit_price_idr: Optional[int]
    quoting_supplier_name: Optional[str]
    history_count: int                   # 0 if no history
    last_purchases: list[PurchaseOut]    # last 3 (empty if web/none)
    web_quotes: list[WebQuoteOut]        # (empty if history/none)
    reference_unit_price_idr: Optional[int]
    checked_via: str                     # "history" | "web" | "none"
    diff_pct: Optional[float]
    flags: list[FlagOut]
    status: str
    check_error: Optional[str]
