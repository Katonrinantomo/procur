"""xlsx_parser.py — parse purchase history from an .xlsx workbook.

Reads the first sheet.  Header names are matched case-insensitively with
English and Indonesian aliases:

    date        → tanggal
    po_number   → no_po
    supplier    → pemasok, vendor
    item        → barang, nama_barang
    qty         → jumlah
    unit        → satuan
    unit_price_idr → harga_satuan, harga

Date parsing supports:
  - Real Excel date serial (openpyxl returns a datetime/date object directly)
  - ISO 8601 text "2026-08-12"
  - Indonesian day-first text "12/08/2026"

Price parsing supports:
  - Numeric cell values (int or float)
  - Text like "Rp 1.130.000" or "1.130.000" (dots are thousands separators)

Returns a list of ParsedRow dicts and a list of RowError dicts.
Empty rows (all cells None or blank) are silently skipped.
The header row is row 1; data rows are numbered from 2 onward.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

import openpyxl

# ---------------------------------------------------------------------------
# Column alias map: canonical name → accepted aliases (lower-cased)
# ---------------------------------------------------------------------------

_ALIASES: dict[str, list[str]] = {
    "date":          ["date", "tanggal"],
    "po_number":     ["po_number", "no_po"],
    "supplier":      ["supplier", "pemasok", "vendor"],
    "item":          ["item", "barang", "nama_barang"],
    "qty":           ["qty", "jumlah"],
    "unit":          ["unit", "satuan"],
    "unit_price_idr": ["unit_price_idr", "harga_satuan", "harga"],
}

_ALIAS_TO_CANONICAL: dict[str, str] = {
    alias: canonical
    for canonical, aliases in _ALIASES.items()
    for alias in aliases
}

_REQUIRED: frozenset[str] = frozenset(_ALIASES.keys())


# ---------------------------------------------------------------------------
# Parsed row and error types
# ---------------------------------------------------------------------------

@dataclass
class ParsedRow:
    date: datetime
    po_number: str
    supplier: str
    item: str
    qty: int
    unit: str
    unit_price_idr: int


@dataclass
class RowError:
    row: int          # 1-based Excel row number (header = row 1)
    message: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_RE_PRICE = re.compile(r"[Rr][Pp][\s.]?")  # strip "Rp" prefix


def _parse_price(value: Any) -> int:
    """Convert a cell value to integer rupiah.

    Accepts int, float, or text like "Rp 1.130.000" / "1.130.000".
    Raises ValueError on unrecognisable input.
    """
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        cleaned = _RE_PRICE.sub("", value.strip())   # remove "Rp" prefix
        cleaned = cleaned.replace(".", "").replace(",", "").strip()
        if not cleaned:
            raise ValueError(f"Empty price value: {value!r}")
        return int(cleaned)
    raise ValueError(f"Cannot parse price from {value!r} ({type(value).__name__})")


def _parse_date(value: Any) -> datetime:
    """Convert a cell value to a UTC datetime.

    Accepts:
      - datetime  (openpyxl returns this for date-formatted cells)
      - date      (openpyxl may return bare date)
      - str in ISO 8601 ("2026-08-12") or day-first ("12/08/2026")
    """
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    if isinstance(value, str):
        s = value.strip()
        # ISO 8601
        if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
            return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        # Day-first dd/mm/yyyy
        if re.match(r"^\d{1,2}/\d{1,2}/\d{4}$", s):
            return datetime.strptime(s, "%d/%m/%Y").replace(tzinfo=timezone.utc)
        raise ValueError(f"Unrecognised date format: {s!r}")
    raise ValueError(f"Cannot parse date from {value!r} ({type(value).__name__})")


def _is_empty_row(cells: list[Any]) -> bool:
    return all(v is None or (isinstance(v, str) and v.strip() == "") for v in cells)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_xlsx(data: bytes) -> tuple[list[ParsedRow], list[RowError]]:
    """Parse *data* (raw .xlsx bytes) and return (rows, errors).

    The header row is row 1.  Data rows start at row 2.
    Errors carry the 1-based Excel row number.
    """
    import io
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    ws = wb.worksheets[0]

    rows_iter = ws.iter_rows(values_only=True)

    # ---- Locate and map header ----
    try:
        raw_header = next(rows_iter)
    except StopIteration:
        return [], [RowError(row=1, message="File is empty or has no header row")]

    col_map: dict[str, int] = {}  # canonical name → 0-based column index
    for idx, cell in enumerate(raw_header):
        if cell is None:
            continue
        canonical = _ALIAS_TO_CANONICAL.get(str(cell).strip().lower())
        if canonical:
            col_map[canonical] = idx

    missing = _REQUIRED - set(col_map.keys())
    if missing:
        return [], [RowError(row=1, message=f"Missing columns: {', '.join(sorted(missing))}")]

    # ---- Parse data rows ----
    parsed: list[ParsedRow] = []
    errors: list[RowError] = []

    for excel_row_num, row_values in enumerate(rows_iter, start=2):
        row_list = list(row_values)
        if _is_empty_row(row_list):
            continue

        def get(name: str) -> Any:
            idx = col_map[name]
            return row_list[idx] if idx < len(row_list) else None

        try:
            purchase_date = _parse_date(get("date"))
            po_number = str(get("po_number") or "").strip()
            supplier = str(get("supplier") or "").strip()
            item = str(get("item") or "").strip()
            qty_val = get("qty")
            unit = str(get("unit") or "").strip()
            price_val = get("unit_price_idr")

            if not supplier:
                raise ValueError("supplier is empty")
            if not item:
                raise ValueError("item is empty")
            if qty_val is None:
                raise ValueError("qty is empty")
            if price_val is None:
                raise ValueError("unit_price_idr is empty")

            qty = int(qty_val) if not isinstance(qty_val, str) else int(qty_val.strip())
            unit_price_idr = _parse_price(price_val)

        except Exception as exc:
            errors.append(RowError(row=excel_row_num, message=str(exc)))
            continue

        parsed.append(ParsedRow(
            date=purchase_date,
            po_number=po_number,
            supplier=supplier,
            item=item,
            qty=qty,
            unit=unit,
            unit_price_idr=unit_price_idr,
        ))

    wb.close()
    return parsed, errors
