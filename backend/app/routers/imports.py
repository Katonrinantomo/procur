"""POST /api/imports/purchases — import purchase history from .xlsx or .csv.

Accepted formats
----------------
.xlsx   First sheet; header names matched case-insensitively in EN/ID.
        (primary format, stored with source="excel")
.csv    Original fallback; columns must use English names.
        (stored with source="csv")

Canonical columns (required):
    date, po_number, supplier, item, qty, unit, unit_price_idr

Indonesian aliases accepted in xlsx:
    tanggal, no_po, pemasok/vendor, barang/nama_barang, jumlah, satuan,
    harga_satuan/harga

Rules
-----
- Match items via matcher.py (token_set_ratio ≥ threshold).
  If nothing matches, create a new catalog Item and add the raw name as alias.
- Create Suppliers by name when they don't exist yet.
- Skip a line when the same po_number + item_id combo already exists.
- Return a summary: inserted, skipped, new_items, new_suppliers, errors.
- Errors carry the Excel/CSV row number (header = row 1).

GET /api/imports/purchases/template
------------------------------------
Returns procur-purchases-template.xlsx with the header row + 2 example rows.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Item, Purchase, Supplier
from app.routers.auth import get_current_user, require_roles
from app.services.matcher import match_item, normalize_name
from app.services.xlsx_parser import ParsedRow, RowError, parse_xlsx

router = APIRouter(dependencies=[Depends(get_current_user)])

_REQUIRED_COLS = {"date", "po_number", "supplier", "item", "qty", "unit", "unit_price_idr"}


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------

class ImportError(BaseModel):
    line: int
    message: str


class ImportSummary(BaseModel):
    inserted: int
    skipped: int
    new_items: int
    new_suppliers: int
    errors: list[ImportError]


# ---------------------------------------------------------------------------
# Helper: get-or-create Supplier by name
# ---------------------------------------------------------------------------

def _get_or_create_supplier(name: str, session: Session) -> tuple[Supplier, bool]:
    """Return (supplier, created). Created=True when a new row was inserted."""
    existing = session.execute(
        select(Supplier).where(Supplier.name == name)
    ).scalar_one_or_none()
    if existing:
        return existing, False
    supplier = Supplier(name=name)
    session.add(supplier)
    session.flush()
    return supplier, True


# ---------------------------------------------------------------------------
# Helper: get-or-create Item, appending alias when newly created
# ---------------------------------------------------------------------------

def _get_or_create_item(raw_name: str, unit: str, session: Session) -> tuple[Item, bool]:
    """Return (item, created). Uses matcher; creates a new item if no match."""
    matched = match_item(raw_name, session)
    if matched:
        existing_aliases: list[str] = list(matched.aliases or [])
        normalized = normalize_name(raw_name)
        if raw_name not in existing_aliases and normalized not in [normalize_name(a) for a in existing_aliases]:
            existing_aliases.append(raw_name)
            matched.aliases = existing_aliases
            session.flush()
        return matched, False

    item = Item(
        name=raw_name,
        aliases=[raw_name],
        category="imported",
        unit=unit,
    )
    session.add(item)
    session.flush()
    return item, True


# ---------------------------------------------------------------------------
# Duplicate check: same po_number + item_id already in purchases
# ---------------------------------------------------------------------------

def _purchase_exists(po_number: str, item_id: int, session: Session) -> bool:
    row = session.execute(
        select(Purchase).where(
            Purchase.po_number == po_number,
            Purchase.item_id == item_id,
        )
    ).scalar_one_or_none()
    return row is not None


# ---------------------------------------------------------------------------
# Core insert logic (shared by xlsx and csv paths)
# ---------------------------------------------------------------------------

def _insert_rows(
    parsed_rows: list[ParsedRow],
    parse_errors: list[RowError],
    source: str,
    db: Session,
) -> ImportSummary:
    inserted = 0
    skipped = 0
    new_items = 0
    new_suppliers = 0
    errors: list[ImportError] = [ImportError(line=e.row, message=e.message) for e in parse_errors]

    for row in parsed_rows:
        try:
            supplier, s_created = _get_or_create_supplier(row.supplier, db)
            item, i_created = _get_or_create_item(row.item, row.unit, db)

            if _purchase_exists(row.po_number, item.id, db):
                skipped += 1
                continue

            purchase = Purchase(
                po_number=row.po_number,
                purchase_date=row.date,
                item_id=item.id,
                supplier_id=supplier.id,
                qty=row.qty,
                unit_price_idr=row.unit_price_idr,
                source=source,
            )
            db.add(purchase)
            db.flush()

            inserted += 1
            if i_created:
                new_items += 1
            if s_created:
                new_suppliers += 1

        except Exception as exc:
            db.rollback()
            # We don't have the original row number in parsed_rows; use 0 as sentinel.
            errors.append(ImportError(line=0, message=str(exc)))
            continue

    db.commit()

    return ImportSummary(
        inserted=inserted,
        skipped=skipped,
        new_items=new_items,
        new_suppliers=new_suppliers,
        errors=errors,
    )


# ---------------------------------------------------------------------------
# CSV parsing (fallback)
# ---------------------------------------------------------------------------

def _parse_csv(content: str) -> tuple[list[ParsedRow], list[RowError]]:
    reader = csv.DictReader(io.StringIO(content))

    if reader.fieldnames is None:
        return [], [RowError(row=1, message="File is empty or has no header row")]

    missing = _REQUIRED_COLS - {f.strip().lower() for f in reader.fieldnames}
    if missing:
        return [], [RowError(row=1, message=f"Missing columns: {', '.join(sorted(missing))}")]

    parsed: list[ParsedRow] = []
    errors: list[RowError] = []

    for line_num, row in enumerate(reader, start=2):
        try:
            date_str = row["date"].strip()
            po_number = row["po_number"].strip()
            supplier_name = row["supplier"].strip()
            item_name = row["item"].strip()
            qty = int(row["qty"].strip())
            unit = row["unit"].strip()
            unit_price_idr = int(row["unit_price_idr"].strip())
            purchase_date = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
        except Exception as exc:
            errors.append(RowError(row=line_num, message=str(exc)))
            continue

        parsed.append(ParsedRow(
            date=purchase_date,
            po_number=po_number,
            supplier=supplier_name,
            item=item_name,
            qty=qty,
            unit=unit,
            unit_price_idr=unit_price_idr,
        ))

    return parsed, errors


# ---------------------------------------------------------------------------
# Template endpoint
# ---------------------------------------------------------------------------

_TEMPLATE_HEADERS = [
    "date", "po_number", "supplier", "item", "qty", "unit", "unit_price_idr"
]
_TEMPLATE_EXAMPLES = [
    ["2024-01-05", "PO-2024-001", "PT Sumber Teknik", "Hydraulic oil ISO VG 46 20L", 10, "drum", 1150000],
    ["2024-01-08", "PO-2024-002", "CV Maju Jaya",      "Bearing SKF 6205",           50, "pcs",  45000],
]


@router.get("/api/imports/purchases/template")
def download_template():
    """Return procur-purchases-template.xlsx with header + 2 example rows."""
    import openpyxl
    from openpyxl.styles import Font

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Purchases"

    ws.append(_TEMPLATE_HEADERS)
    # Bold header row
    for cell in ws[1]:
        cell.font = Font(bold=True)

    for example_row in _TEMPLATE_EXAMPLES:
        ws.append(example_row)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="procur-purchases-template.xlsx"'},
    )


# ---------------------------------------------------------------------------
# Import endpoint
# ---------------------------------------------------------------------------

_MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
# Magic bytes for the ZIP/OOXML container used by .xlsx files.
_XLSX_MAGIC = b"PK\x03\x04"


@router.post(
    "/api/imports/purchases",
    response_model=ImportSummary,
    dependencies=[Depends(require_roles("purchasing"))],
)
def import_purchases(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    filename = (file.filename or "").lower()

    # Accept only .xlsx and .csv
    if not (filename.endswith(".xlsx") or filename.endswith(".csv")):
        raise HTTPException(
            status_code=400,
            detail="Only .xlsx and .csv files are supported",
        )

    # Read one byte more than the limit so we can detect oversized files
    # without loading the entire stream into memory first.
    raw = file.file.read(_MAX_UPLOAD_BYTES + 1)

    # Reject files over 5 MB
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File is too large. Maximum size is 5 MB.",
        )

    if filename.endswith(".xlsx"):
        # Validate magic bytes — must start with the ZIP/OOXML header.
        if not raw[:4] == _XLSX_MAGIC:
            raise HTTPException(
                status_code=400,
                detail="File does not appear to be a valid .xlsx file (invalid header).",
            )
        parsed_rows, parse_errors = parse_xlsx(raw)
        return _insert_rows(parsed_rows, parse_errors, source="excel", db=db)

    # CSV path
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"File could not be decoded as UTF-8: {exc}",
        ) from exc
    parsed_rows, parse_errors = _parse_csv(content)
    return _insert_rows(parsed_rows, parse_errors, source="csv", db=db)
