"""
Output contracts for every Langflow flow.

One Pydantic model per flow output (shapes from the Phase 2 plan, section
"Flow specs"), the output component names each flow must expose, and
parse_flow_json(), the shared parser with one repair retry.

Money fields are always int rupiah or None — never float.
"""
from __future__ import annotations

import json
import re
from typing import Awaitable, Callable, Literal, TypeVar

from pydantic import BaseModel, Field, RootModel, ValidationError

from app.services.langflow_client import LangflowError

# ---------------------------------------------------------------------------
# Output component names (Chat Output display names in Langflow)
# ---------------------------------------------------------------------------
ORGANIZE_OUT = "organize_json"
WEBCHECK_OUT = "webcheck_json"
EXTRACT_OUT = "extract_json"
MAKER_OUT = "maker_json"
SERPER_RAW_OUT = "serper_raw"
CHECKER_OUT = "checker_json"
NARRATOR_OUT = "narrator_json"


# ---------------------------------------------------------------------------
# Organize
# ---------------------------------------------------------------------------

class LineItemDraft(BaseModel):
    name: str
    qty: int | None = None
    unit: str | None = None
    department: str | None = None
    quoted_unit_price_idr: int | None = None
    supplier: str | None = None


class OrganizeOut(BaseModel):
    items: list[LineItemDraft]


# ---------------------------------------------------------------------------
# Web Check (replaced by maker_agent in M18)
# ---------------------------------------------------------------------------

class WebOffer(BaseModel):
    # Permissive on purpose: web_check._save_quotes drops bad offers one by
    # one, so a single bad listing must not fail the whole reply.
    title: str | None = None
    url: str | None = None
    seller: str | None = None
    price_idr: int | None = None


class WebCheckOut(RootModel[list[WebOffer]]):
    pass


# ---------------------------------------------------------------------------
# maker_agent — two model outputs; Python joins them by line_no
# (app/services/maker.py).  serper_raw is the Serper Multi Search output.
# ---------------------------------------------------------------------------

class ExtractVendor(BaseModel):
    name: str | None = None
    doc_number: str | None = None
    doc_date: str | None = None
    payment_terms: str | None = None


class ExtractItem(BaseModel):
    line_no: int
    name_as_written: str
    brand: str | None = None
    spec: str | None = None
    # qty may be fractional ("1,5" meter); it is not money.
    qty: float | None = None
    unit: str | None = None
    # Money: int rupiah.  An integral float (1250000.0) is accepted, a
    # fractional one fails the contract.
    unit_price: int | None = None
    line_total: int | None = None
    division: str | None = None
    search_query: str


class ExtractOut(BaseModel):
    """extract_json: what the first model read from the document."""
    mode: Literal["PENAWARAN", "BON"]
    vendor: ExtractVendor = ExtractVendor()
    currency: str | None = "IDR"
    items: list[ExtractItem]
    document_total: int | None = None
    extraction_notes: list[str] = []


class EvidenceMatch(BaseModel):
    url: str
    title: str
    marketplace: str | None = None
    price: int | None = None
    price_text: str | None = None
    # How many of the item's unit one listing contains; Python divides.
    pack_qty: float | None = None
    match: Literal["exact", "close"]
    reason: str | None = None


class EvidenceItem(BaseModel):
    line_no: int
    matches: list[EvidenceMatch] = []
    note: str | None = None


class EvidenceOut(BaseModel):
    """maker_json: listings the second model says match each item."""
    items: list[EvidenceItem]


# ---------------------------------------------------------------------------
# checker_agent
# ---------------------------------------------------------------------------

class DocLine(BaseModel):
    name: str
    qty: int | None = None
    unit: str | None = None
    unit_price_idr: int | None = None
    line_total_idr: int | None = None


class Approval(BaseModel):
    name: str
    level: int | None = None


class PurchaseOrderDoc(BaseModel):
    doc_no: str | None = None
    date: str | None = None
    vendor_name: str | None = None
    vendor_npwp: str | None = None
    lines: list[DocLine] = []
    subtotal_idr: int | None = None
    total_idr: int | None = None
    approvals: list[Approval] = []


class GoodsReceiptDoc(BaseModel):
    doc_no: str | None = None
    date: str | None = None
    po_ref: str | None = None
    lines: list[DocLine] = []


class InvoiceDoc(BaseModel):
    doc_no: str | None = None
    date: str | None = None
    po_ref: str | None = None
    vendor_npwp: str | None = None
    lines: list[DocLine] = []
    subtotal_idr: int | None = None
    ppn_idr: int | None = None
    total_idr: int | None = None


class TaxInvoiceDoc(BaseModel):
    faktur_no: str | None = None
    faktur_code: str | None = None
    date: str | None = None
    seller_npwp: str | None = None
    buyer_npwp: str | None = None
    invoice_ref: str | None = None
    harga_jual_idr: int | None = None
    dpp_idr: int | None = None
    ppn_idr: int | None = None


class CheckerOut(BaseModel):
    po: PurchaseOrderDoc
    gr: GoodsReceiptDoc
    invoice: InvoiceDoc
    tax_invoice: TaxInvoiceDoc


# ---------------------------------------------------------------------------
# risk_narrator
# ---------------------------------------------------------------------------

class NarratorOut(BaseModel):
    summary: str = Field(max_length=600)
    patterns: list[str]
    actions: list[str] = Field(min_length=3, max_length=5)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

T = TypeVar("T", bound=BaseModel)

_CODE_FENCE = re.compile(r"```(?:json)?\s*([\s\S]*?)```", re.IGNORECASE)


class FlowContractError(LangflowError):
    """The flow's output did not fit its contract, even after a repair retry.

    A LangflowError, so callers that already turn LangflowError into a 502
    or a pending row handle it the same way.
    """


def strip_fences(text: str) -> str:
    """Remove markdown code fences wrapping JSON, if present."""
    m = _CODE_FENCE.search(text)
    if m:
        return m.group(1).strip()
    return text.strip()


def parse_flow_json_once(text: str, model: type[T]) -> T:
    """Strip fences, parse and validate.  Raises ValueError or ValidationError."""
    return model.model_validate(json.loads(strip_fences(text)))


def repair_hint(error: Exception) -> str:
    return (
        f"[Previous answer was invalid. Error: {error}. "
        f"Please reply with valid JSON only.]"
    )


async def parse_flow_json(
    text: str,
    model: type[T],
    rerun: Callable[[str], Awaitable[str]],
) -> T:
    """Parse *text* against *model*, with one repair retry.

    On failure, calls rerun(hint) once — the caller re-runs the flow with the
    hint appended and returns the new raw output — and parses that instead.
    Raises FlowContractError if the second answer is also invalid.
    LangflowError from rerun propagates.
    """
    try:
        return parse_flow_json_once(text, model)
    except (ValidationError, ValueError) as first_err:
        retry_text = await rerun(repair_hint(first_err))
    try:
        return parse_flow_json_once(retry_text, model)
    except (ValidationError, ValueError) as second_err:
        raise FlowContractError(
            f"{model.__name__} invalid after repair retry: {second_err}"
        ) from second_err
