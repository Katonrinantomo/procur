"""SQLAlchemy 2 ORM models for Procur.AI."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BIGINT,
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    event,
    func,
)
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship

from app.db import Base


# ---------------------------------------------------------------------------
# suppliers
# ---------------------------------------------------------------------------
class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50))
    city: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    purchases: Mapped[list[Purchase]] = relationship(back_populates="supplier")
    request_items: Mapped[list[RequestItem]] = relationship(back_populates="supplier")


# ---------------------------------------------------------------------------
# items
# ---------------------------------------------------------------------------
class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    aliases: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    purchases: Mapped[list[Purchase]] = relationship(back_populates="item")
    stock: Mapped[Stock | None] = relationship(back_populates="item", uselist=False)
    request_items: Mapped[list[RequestItem]] = relationship(back_populates="item")


# ---------------------------------------------------------------------------
# purchases
# ---------------------------------------------------------------------------
class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    po_number: Mapped[str | None] = mapped_column(String(50))
    purchase_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False)
    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price_idr: Mapped[int] = mapped_column(BIGINT, nullable=False)
    # source: seed | csv | excel | manual
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="seed")

    item: Mapped[Item] = relationship(back_populates="purchases")
    supplier: Mapped[Supplier] = relationship(back_populates="purchases")


# ---------------------------------------------------------------------------
# stock
# ---------------------------------------------------------------------------
class Stock(Base):
    __tablename__ = "stock"

    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), primary_key=True)
    qty_on_hand: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_monthly_use: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    item: Mapped[Item] = relationship(back_populates="stock")


# ---------------------------------------------------------------------------
# requests
# ---------------------------------------------------------------------------
class Request(Base):
    __tablename__ = "requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    requested_by: Mapped[str | None] = mapped_column(String(100))
    raw_text: Mapped[str | None] = mapped_column(Text)
    # FK to users — nullable so old rows and seed rows without a user are valid.
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    items: Mapped[list[RequestItem]] = relationship(back_populates="request")


# ---------------------------------------------------------------------------
# request_items
# ---------------------------------------------------------------------------
class RequestItem(Base):
    __tablename__ = "request_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id"), nullable=False)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_name: Mapped[str] = mapped_column(String(255), nullable=False)
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"), nullable=True)
    department: Mapped[str | None] = mapped_column(String(100))
    qty: Mapped[int | None] = mapped_column(Integer)
    unit: Mapped[str | None] = mapped_column(String(50))
    quoted_unit_price_idr: Mapped[int | None] = mapped_column(BIGINT)
    quoting_supplier_name: Mapped[str | None] = mapped_column(String(255))
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    reference_unit_price_idr: Mapped[int | None] = mapped_column(BIGINT)
    diff_pct: Mapped[float | None] = mapped_column(Numeric(8, 1))
    # checked_via: history | web | none
    checked_via: Mapped[str | None] = mapped_column(String(20))
    history_count: Mapped[int | None] = mapped_column(Integer)
    # status: pending | checked | new | flagged | approved | returned
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # 0–100 composite risk score (flags + |diff_pct|); 0 = no risk.
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    check_error: Mapped[str | None] = mapped_column(Text)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    request: Mapped[Request] = relationship(back_populates="items")
    item: Mapped[Item | None] = relationship(back_populates="request_items")
    supplier: Mapped[Supplier | None] = relationship(back_populates="request_items")
    web_quotes: Mapped[list[WebQuote]] = relationship(back_populates="request_item")
    flags: Mapped[list[Flag]] = relationship(back_populates="request_item")
    actions: Mapped[list[Action]] = relationship(back_populates="request_item")


# ---------------------------------------------------------------------------
# web_quotes
# ---------------------------------------------------------------------------
class WebQuote(Base):
    __tablename__ = "web_quotes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # request_item_id is nullable — standalone cache rows have no linked request item.
    request_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("request_items.id"), nullable=True
    )
    # item_key is the normalized item name (same normalization as matcher.py).
    # Used for cache lookups independent of request_item_id.
    item_key: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    query: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500))
    url: Mapped[str | None] = mapped_column(String(1000))
    seller: Mapped[str | None] = mapped_column(String(255))
    price_idr: Mapped[int] = mapped_column(BIGINT, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    request_item: Mapped[RequestItem | None] = relationship(back_populates="web_quotes")


# ---------------------------------------------------------------------------
# flags
# ---------------------------------------------------------------------------
class Flag(Base):
    __tablename__ = "flags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_item_id: Mapped[int] = mapped_column(
        ForeignKey("request_items.id"), nullable=False
    )
    # code: PRICE_ABOVE_REF | STOCK_COVER_HIGH | QTY_UNUSUAL | NEW_SUPPLIER
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    request_item: Mapped[RequestItem] = relationship(back_populates="flags")


# ---------------------------------------------------------------------------
# actions
# ---------------------------------------------------------------------------
class Action(Base):
    __tablename__ = "actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_item_id: Mapped[int] = mapped_column(
        ForeignKey("request_items.id"), nullable=False
    )
    # action: approve | return
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    # No longer written (M19): the decider lives in audit_log.user_id.
    actor: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    request_item: Mapped[RequestItem] = relationship(back_populates="actions")


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="purchasing")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="user")


# ---------------------------------------------------------------------------
# audit_log — the decision log (M19). Append-only: no code path may update or
# delete a row; the before_flush guard below enforces it for the ORM.
# ---------------------------------------------------------------------------
class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_subject", "subject_type", "subject_id"),
        Index("ix_audit_log_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    request_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("request_items.id"), nullable=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    # Legacy columns, still written: action mirrors decision, note mirrors reason.
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    # subject_type: request_item | quotation | bundle
    subject_type: Mapped[str] = mapped_column(String(20), nullable=False)
    subject_id: Mapped[int] = mapped_column(Integer, nullable=False)
    # decision: approve | return | pay | hold | clarify
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    # Role of the deciding user at decision time.
    role: Mapped[str | None] = mapped_column(String(20))
    # outcome_tag: false_alarm | risk_accepted — set only on overrides.
    outcome_tag: Mapped[str | None] = mapped_column(String(20))
    # Flags, risk score, reference price and source at decision time.
    snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship(back_populates="audit_logs")


class AuditLogImmutableError(RuntimeError):
    """Raised when a session tries to update or delete a decision-log row."""


@event.listens_for(Session, "before_flush")
def _audit_log_append_only(session: Session, flush_context, instances) -> None:
    for obj in session.deleted:
        if isinstance(obj, AuditLog):
            raise AuditLogImmutableError("audit_log rows cannot be deleted")
    for obj in session.dirty:
        if isinstance(obj, AuditLog) and session.is_modified(obj, include_collections=False):
            raise AuditLogImmutableError("audit_log rows cannot be updated")


# ---------------------------------------------------------------------------
# quotations (M18) — a vendor quotation checked by maker_agent + pricing.py
# ---------------------------------------------------------------------------
class Quotation(Base):
    __tablename__ = "quotations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    vendor_name: Mapped[str | None] = mapped_column(String(255))
    quote_no: Mapped[str | None] = mapped_column(String(100))
    quote_date: Mapped[date | None] = mapped_column(Date)
    quote_total_idr: Mapped[int | None] = mapped_column(BIGINT)
    # status: pending | checked | unreadable | queued
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    check_error: Mapped[str | None] = mapped_column(Text)
    # Computed by pricing.vendor_score — never by the model.
    vendor_score: Mapped[int | None] = mapped_column(Integer)
    price_points: Mapped[float | None] = mapped_column(Numeric(5, 1))
    arithmetic_ok: Mapped[bool | None] = mapped_column(Boolean)
    covered_lines: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_lines: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dropped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Set by POST /api/quotations/{id}/to-queue
    request_id: Mapped[int | None] = mapped_column(ForeignKey("requests.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    lines: Mapped[list[QuotationLine]] = relationship(
        back_populates="quotation", order_by="QuotationLine.line_no", cascade="all, delete-orphan"
    )


class QuotationLine(Base):
    __tablename__ = "quotation_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quotation_id: Mapped[int] = mapped_column(
        ForeignKey("quotations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    qty: Mapped[int | None] = mapped_column(Integer)
    unit: Mapped[str | None] = mapped_column(String(50))
    unit_price_idr: Mapped[int | None] = mapped_column(BIGINT)
    line_total_idr: Mapped[int | None] = mapped_column(BIGINT)
    item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"), nullable=True)
    reference_unit_price_idr: Mapped[int | None] = mapped_column(BIGINT)
    # reference_source: history | web | none
    reference_source: Mapped[str] = mapped_column(String(20), nullable=False, default="none")
    history_count: Mapped[int | None] = mapped_column(Integer)
    diff_pct: Mapped[float | None] = mapped_column(Numeric(8, 1))
    # band: KOMPETITIF | WAJAR | PERHATIAN | TIDAK WAJAR | UNKNOWN
    band: Mapped[str] = mapped_column(String(20), nullable=False, default="UNKNOWN")
    # recommendation: SETUJU | NEGOSIASI | TOLAK | None
    recommendation: Mapped[str | None] = mapped_column(String(20))
    search_query: Mapped[str | None] = mapped_column(String(500))
    # Kept listings: [{title, url, seller, price_idr}]
    evidence: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    # Dropped listings: [{title, url, price_idr, reason}]
    dropped: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)

    quotation: Mapped[Quotation] = relationship(back_populates="lines")
