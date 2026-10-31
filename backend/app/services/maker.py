"""
maker_agent client.

call_maker(flow_input) runs the flow once and reads its three outputs:

  extract_json — items the first model read from the document (ExtractOut)
  maker_json   — listings the second model matched to each item (EvidenceOut)
  serper_raw   — Serper Multi Search results, grouped by line_no

Python joins extract and evidence by line_no, runs the evidence guards on
each item against that item's own search results, and returns a
MakerResult.  The model never sets a band, recommendation or score; it
supplies text, numbers as written, and listings.

If either JSON output breaks its contract, the whole flow is re-run once
with a repair hint (so all three outputs come from the same run); a second
failure raises FlowContractError.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from pydantic import ValidationError

from app.config import settings
from app.flows.contracts import (
    EXTRACT_OUT,
    MAKER_OUT,
    SERPER_RAW_OUT,
    EvidenceOut,
    ExtractOut,
    FlowContractError,
    parse_flow_json_once,
    repair_hint,
)
from app.services.evidence import (
    DroppedListing,
    KeptListing,
    guard_listings,
    parse_serper_groups,
)
from app.services.langflow_client import LangflowError, pick_output, run_flow


@dataclass
class MakerLine:
    line_no: int
    name: str
    qty: int | None
    unit: str | None
    unit_price_idr: int | None
    line_total_idr: int | None
    search_query: str
    kept: list[KeptListing] = field(default_factory=list)
    dropped: list[DroppedListing] = field(default_factory=list)
    note: str | None = None


@dataclass
class MakerResult:
    mode: str  # PENAWARAN | BON
    vendor_name: str | None
    quote_no: str | None
    quote_date: date | None
    quote_total_idr: int | None
    lines: list[MakerLine]
    notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Flow input
# ---------------------------------------------------------------------------

def items_input(names: list[str]) -> str:
    """Input for a list of item names (no prices): MODE BON."""
    body = "\n".join(f"{i}. {name}" for i, name in enumerate(names, start=1))
    return f"MODE: BON\nFILE: items.txt\n---\n{body}"


def quote_input(filename: str, text: str) -> str:
    """Input for a vendor quotation's extracted text: MODE PENAWARAN."""
    safe_name = re.sub(r"[\r\n]+", " ", filename)[:255]
    return f"MODE: PENAWARAN\nFILE: {safe_name}\n---\n{text}"


# ---------------------------------------------------------------------------
# Join
# ---------------------------------------------------------------------------

def _whole(qty: float | None) -> int | None:
    """Fractional quantities ("1,5 meter") don't fit an integer qty column."""
    if qty is None or not float(qty).is_integer():
        return None
    return int(qty)


_DATE_FORMATS = (
    re.compile(r"^(?P<y>\d{4})-(?P<m>\d{1,2})-(?P<d>\d{1,2})$"),
    re.compile(r"^(?P<d>\d{1,2})[-/.](?P<m>\d{1,2})[-/.](?P<y>\d{4})$"),
)


def parse_doc_date(value: str | None) -> date | None:
    """YYYY-MM-DD or DD-MM-YYYY (also / or .); anything else is None."""
    if not value:
        return None
    for pattern in _DATE_FORMATS:
        m = pattern.match(value.strip())
        if m:
            try:
                return date(int(m["y"]), int(m["m"]), int(m["d"]))
            except ValueError:
                return None
    return None


def build_result(extract: ExtractOut, evidence: EvidenceOut, serper_raw: str | None) -> MakerResult:
    groups = parse_serper_groups(serper_raw)
    matches_by_line = {e.line_no: e for e in evidence.items}

    lines: list[MakerLine] = []
    for item in extract.items:
        ev = matches_by_line.get(item.line_no)
        guarded = guard_listings(ev.matches if ev else [], groups.get(item.line_no, []))
        lines.append(MakerLine(
            line_no=item.line_no,
            name=item.name_as_written,
            qty=_whole(item.qty),
            unit=item.unit,
            unit_price_idr=item.unit_price,
            line_total_idr=item.line_total,
            search_query=item.search_query,
            kept=guarded.kept,
            dropped=guarded.dropped,
            note=ev.note if ev else None,
        ))

    return MakerResult(
        mode=extract.mode,
        vendor_name=extract.vendor.name,
        quote_no=extract.vendor.doc_number,
        quote_date=parse_doc_date(extract.vendor.doc_date),
        quote_total_idr=extract.document_total,
        lines=lines,
        notes=list(extract.extraction_notes),
    )


def parse_outputs(outputs: dict[str, str]) -> tuple[ExtractOut, EvidenceOut]:
    """Validate extract_json and maker_json.  Raises ValueError,
    ValidationError or LangflowError (output missing)."""
    extract = parse_flow_json_once(pick_output(outputs, EXTRACT_OUT), ExtractOut)
    evidence = parse_flow_json_once(pick_output(outputs, MAKER_OUT), EvidenceOut)
    return extract, evidence


async def run_maker(flow_id: str, flow_input: str) -> tuple[dict[str, str], bool]:
    """Run the flow, re-running once with a repair hint if its JSON outputs
    break their contracts.  Returns (outputs, repaired)."""
    outputs = await run_flow(flow_id, flow_input)
    try:
        parse_outputs(outputs)
        return outputs, False
    except (ValidationError, ValueError, LangflowError) as first_err:
        hint = repair_hint(first_err)
    outputs = await run_flow(flow_id, f"{flow_input}\n\n{hint}")
    try:
        parse_outputs(outputs)
    except (ValidationError, ValueError, LangflowError) as second_err:
        raise FlowContractError(f"maker_agent outputs invalid after repair retry: {second_err}") from second_err
    return outputs, True


async def call_maker(flow_input: str) -> MakerResult:
    """Run maker_agent and return the joined, evidence-checked result.
    Raises LangflowError (FlowContractError included) on failure."""
    flow_id = settings.LANGFLOW_MAKER_FLOW_ID
    if not flow_id:
        raise LangflowError("LANGFLOW_MAKER_FLOW_ID is not set")
    outputs, _ = await run_maker(flow_id, flow_input)
    extract, evidence = parse_outputs(outputs)
    return build_result(extract, evidence, outputs.get(SERPER_RAW_OUT))
