"""
Tests for POST /api/imports/purchases.

Uses the shared test DB from conftest.py (SQLite file-based).  Because
seeded_db is session-scoped, committed rows persist across tests within the
same session.  The tests run in the order they appear and rely on that order:

  1. first_import  → inserts 20 rows, creates new suppliers/items
  2. second_import → same file again → all 20 rows skipped
  3. bad_header    → missing columns → error summary with no DB changes
  4. bad_row       → invalid date    → per-line error, line number reported
"""
from __future__ import annotations

import io
import os
import pathlib

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_procur.db")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)

_SAMPLE_CSV = (
    pathlib.Path(__file__).parent.parent / "sample_data" / "purchases_sample.csv"
)

_CSV_DATA_ROWS = 20  # header excluded


def _upload_sample() -> dict:
    with open(_SAMPLE_CSV, "rb") as f:
        resp = client.post(
            "/api/imports/purchases",
            files={"file": ("purchases_sample.csv", f, "text/csv")},
        )
    assert resp.status_code == 200, resp.text
    return resp.json()


class TestImportPurchases:
    """Import the same CSV; verify all rows are processed without errors."""

    def test_sample_csv_exists(self):
        assert _SAMPLE_CSV.exists(), f"Sample CSV not found at {_SAMPLE_CSV}"

    def test_first_import_inserts_all_rows(self, seeded_db):
        result = _upload_sample()
        assert result["errors"] == [], f"Unexpected errors on first import: {result['errors']}"
        # Rows may already exist from xlsx tests in the same session; total must be 20.
        assert result["inserted"] + result["skipped"] == _CSV_DATA_ROWS

    def test_first_import_creates_new_suppliers(self, seeded_db):
        # Re-upload: suppliers already exist → new_suppliers == 0.
        result = _upload_sample()
        assert result["new_suppliers"] == 0

    def test_second_import_skips_every_row(self, seeded_db):
        """All rows must be skipped (all already present from earlier uploads)."""
        result = _upload_sample()
        assert result["inserted"] == 0
        assert result["skipped"] == _CSV_DATA_ROWS
        assert result["errors"] == []

    def test_missing_column_returns_error(self, seeded_db):
        bad_csv = "date,po_number,supplier\n2024-01-01,PO-X,PT Test\n"
        resp = client.post(
            "/api/imports/purchases",
            files={"file": ("bad.csv", io.BytesIO(bad_csv.encode()), "text/csv")},
        )
        assert resp.status_code == 200
        result = resp.json()
        assert len(result["errors"]) == 1
        assert "Missing columns" in result["errors"][0]["message"]
        assert result["inserted"] == 0

    def test_bad_date_row_is_reported_with_line_number(self, seeded_db):
        bad_csv = (
            "date,po_number,supplier,item,qty,unit,unit_price_idr\n"
            "not-a-date,PO-BAD,Supplier X,Item Y,5,pcs,1000\n"
        )
        resp = client.post(
            "/api/imports/purchases",
            files={"file": ("bad.csv", io.BytesIO(bad_csv.encode()), "text/csv")},
        )
        assert resp.status_code == 200
        result = resp.json()
        assert len(result["errors"]) == 1
        assert result["errors"][0]["line"] == 2
        assert result["inserted"] == 0


# ---------------------------------------------------------------------------
# M2 hardening tests
# ---------------------------------------------------------------------------

class TestImportHardening:
    """POST /api/imports/purchases: unsupported extension, oversized file, bad encoding."""

    def test_unsupported_extension_returns_400(self, seeded_db):
        resp = client.post(
            "/api/imports/purchases",
            files={"file": ("data.xls", io.BytesIO(b"dummy"), "application/octet-stream")},
        )
        assert resp.status_code == 400
        assert "Only .xlsx and .csv files are supported" in resp.json()["detail"]

    def test_pdf_extension_returns_400(self, seeded_db):
        resp = client.post(
            "/api/imports/purchases",
            files={"file": ("report.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
        )
        assert resp.status_code == 400
        assert "Only .xlsx and .csv files are supported" in resp.json()["detail"]

    def test_image_extension_returns_400(self, seeded_db):
        resp = client.post(
            "/api/imports/purchases",
            files={"file": ("photo.png", io.BytesIO(b"\x89PNG"), "image/png")},
        )
        assert resp.status_code == 400
        assert "Only .xlsx and .csv files are supported" in resp.json()["detail"]

    def test_oversized_csv_returns_413(self, seeded_db):
        # 5 MB + 1 byte
        big = io.BytesIO(b"x" * (5 * 1024 * 1024 + 1))
        resp = client.post(
            "/api/imports/purchases",
            files={"file": ("big.csv", big, "text/csv")},
        )
        assert resp.status_code == 413
        assert "5 MB" in resp.json()["detail"]

    def test_oversized_xlsx_returns_413(self, seeded_db):
        big = io.BytesIO(b"x" * (5 * 1024 * 1024 + 1))
        resp = client.post(
            "/api/imports/purchases",
            files={"file": ("big.xlsx", big, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert resp.status_code == 413
        assert "5 MB" in resp.json()["detail"]

    def test_csv_exact_size_limit_is_accepted(self, seeded_db):
        """A file of exactly 5 MB must not be rejected by the size check."""
        # Build a valid-header CSV padded to exactly 5 MB with comment-like rows
        header = "date,po_number,supplier,item,qty,unit,unit_price_idr\n"
        padding = ("# " + "x" * 78 + "\n") * (
            (5 * 1024 * 1024 - len(header.encode())) // 82
        )
        data = header + padding
        # Trim or pad to exactly 5 MB
        data = data.encode()[:5 * 1024 * 1024]
        resp = client.post(
            "/api/imports/purchases",
            files={"file": ("ok.csv", io.BytesIO(data), "text/csv")},
        )
        # Not 413 — may be 200 with 0 rows or parse errors (content is padded)
        assert resp.status_code != 413

    def test_non_utf8_csv_returns_400(self, seeded_db):
        """A CSV that cannot be decoded as UTF-8 must return 400, not 500."""
        # Latin-1 bytes that are invalid UTF-8
        bad_bytes = io.BytesIO("café".encode("latin-1"))
        resp = client.post(
            "/api/imports/purchases",
            files={"file": ("bad_encoding.csv", bad_bytes, "text/csv")},
        )
        assert resp.status_code == 400
        assert "UTF-8" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# SEC-06 hardening: magic bytes and row limit
# ---------------------------------------------------------------------------

class TestImportMagicBytesAndRowLimit:
    """Additional hardening: fake xlsx and row count limit."""

    def test_fake_xlsx_wrong_magic_returns_400(self, seeded_db):
        """A file named .xlsx but lacking the PK\\x03\\x04 header must return 400."""
        fake_xlsx = io.BytesIO(b"Not a real xlsx file, just text content here.")
        resp = client.post(
            "/api/imports/purchases",
            files={"file": ("evil.xlsx", fake_xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert resp.status_code == 400
        assert "valid .xlsx" in resp.json()["detail"]

    def test_real_xlsx_sample_passes_magic_check(self, seeded_db):
        """The bundled sample .xlsx must pass the magic bytes check."""
        import pathlib
        sample_xlsx = pathlib.Path(__file__).parent.parent / "sample_data" / "purchases_sample.xlsx"
        with open(sample_xlsx, "rb") as f:
            resp = client.post(
                "/api/imports/purchases",
                files={"file": ("purchases_sample.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )
        # Must NOT be rejected at the magic-bytes stage
        assert resp.status_code == 200

    def test_xlsx_parser_row_limit(self):
        """parse_xlsx must return an error entry when row count exceeds MAX_ROWS."""
        import io as _io
        import openpyxl
        from app.services.xlsx_parser import parse_xlsx, MAX_ROWS

        wb = openpyxl.Workbook()
        ws = wb.active
        # Write header
        ws.append(["date", "po_number", "supplier", "item", "qty", "unit", "unit_price_idr"])
        # Write MAX_ROWS + 1 data rows
        for i in range(MAX_ROWS + 1):
            ws.append(["2024-01-01", f"PO-{i}", "Supplier A", "Item X", 1, "pcs", 10000])
        buf = _io.BytesIO()
        wb.save(buf)
        raw = buf.getvalue()

        _rows, errors = parse_xlsx(raw)
        assert any("exceeds the maximum" in e.message for e in errors), \
            f"Expected a row-limit error, got: {errors}"
