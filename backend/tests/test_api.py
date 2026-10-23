"""
TestClient tests for:
  1. GET /api/queue  — correct sort order (flagged → new → checked)
  2. GET /api/request-items/{id}  — oil detail totals
       quoted_total  = 4 × 1,450,000 = 5,800,000
       reference_total = 4 × 1,120,000 = 4,480,000
       over_reference  = 5,800,000 − 4,480,000 = 1,320,000

The seeded_db fixture (from conftest.py) runs the full seed + check engine once
for the test session.  We use TestClient against the real FastAPI app but with
the engine redirected to the SQLite test DB.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone

import pytest

# Ensure the test DB URL is set before importing the app.
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_procur.db")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.main import app  # noqa: E402
from app.models import RequestItem  # noqa: E402

JAKARTA = timezone(timedelta(hours=7))

client = TestClient(app)


def _today_jakarta() -> str:
    return datetime.now(tz=JAKARTA).date().isoformat()


# ---------------------------------------------------------------------------
# Queue order
# ---------------------------------------------------------------------------

class TestQueueOrder:
    """
    The 5 seeded demo rows should come back in the order:
      flagged (row 1) → new (row 2) → checked (rows 3, 4, 5)
    Within each status group rows are ordered by line_no.
    """

    def test_queue_returns_200(self, seeded_db):
        resp = client.get(f"/api/queue?date={_today_jakarta()}")
        assert resp.status_code == 200

    def test_queue_has_five_rows(self, seeded_db):
        resp = client.get(f"/api/queue?date={_today_jakarta()}")
        data = resp.json()
        assert len(data["rows"]) == 5

    def test_queue_sort_order(self, seeded_db):
        resp = client.get(f"/api/queue?date={_today_jakarta()}")
        rows = resp.json()["rows"]
        statuses = [r["status"] for r in rows]
        # First must be flagged, last three checked
        assert statuses[0] == "flagged"
        assert statuses[1] == "new"
        assert statuses[2] == "checked"
        assert statuses[3] == "checked"
        assert statuses[4] == "checked"

    def test_queue_line_no_order_within_group(self, seeded_db):
        resp = client.get(f"/api/queue?date={_today_jakarta()}")
        rows = resp.json()["rows"]
        checked_rows = [r for r in rows if r["status"] == "checked"]
        line_nos = [r["line_no"] for r in checked_rows]
        assert line_nos == sorted(line_nos)

    def test_queue_counts(self, seeded_db):
        resp = client.get(f"/api/queue?date={_today_jakarta()}")
        counts = resp.json()["counts"]
        assert counts["flagged"] == 1
        assert counts["new"] == 1
        assert counts["checked"] == 3

    def test_queue_status_filter(self, seeded_db):
        resp = client.get(f"/api/queue?date={_today_jakarta()}&status=checked")
        rows = resp.json()["rows"]
        assert len(rows) == 3
        for r in rows:
            assert r["status"] == "checked"

    def test_queue_default_date_is_today(self, seeded_db):
        """Calling /api/queue without a date must return today's 5 rows."""
        resp = client.get("/api/queue")
        assert resp.status_code == 200
        assert len(resp.json()["rows"]) == 5


# ---------------------------------------------------------------------------
# Oil detail totals
# ---------------------------------------------------------------------------

class TestOilDetail:
    """
    Hydraulic oil (line_no=1):
      qty=4, quoted=1,450,000, reference=1,120,000
      quoted_total  = 5,800,000
      reference_total = 4,480,000
      over_reference  = 1,320,000
    """

    def _get_oil_id(self, seeded_db) -> int:
        """Return the RequestItem.id for today's hydraulic oil row (line_no 1)."""
        from app import db as db_module
        from app.models import Request
        from datetime import datetime, timedelta, timezone
        JAKARTA = timezone(timedelta(hours=7))
        today = datetime.now(tz=JAKARTA).date()
        day_start = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=JAKARTA)
        day_end = day_start + timedelta(days=1)

        sess = db_module.SessionLocal()
        try:
            row = sess.execute(
                select(RequestItem)
                .join(Request, Request.id == RequestItem.request_id)
                .where(
                    RequestItem.line_no == 1,
                    Request.requested_at >= day_start,
                    Request.requested_at < day_end,
                )
            ).scalar_one()
            return row.id
        finally:
            sess.close()

    def test_oil_detail_returns_200(self, seeded_db):
        oil_id = self._get_oil_id(seeded_db)
        resp = client.get(f"/api/request-items/{oil_id}")
        assert resp.status_code == 200

    def test_oil_quoted_total(self, seeded_db):
        oil_id = self._get_oil_id(seeded_db)
        data = client.get(f"/api/request-items/{oil_id}").json()
        assert data["quoted_total_idr"] == 5_800_000

    def test_oil_reference_total(self, seeded_db):
        oil_id = self._get_oil_id(seeded_db)
        data = client.get(f"/api/request-items/{oil_id}").json()
        assert data["reference_total_idr"] == 4_480_000

    def test_oil_over_reference(self, seeded_db):
        oil_id = self._get_oil_id(seeded_db)
        data = client.get(f"/api/request-items/{oil_id}").json()
        assert data["over_reference_idr"] == 1_320_000

    def test_oil_has_flags(self, seeded_db):
        oil_id = self._get_oil_id(seeded_db)
        data = client.get(f"/api/request-items/{oil_id}").json()
        codes = {f["code"] for f in data["flags"]}
        assert "PRICE_ABOVE_REF" in codes
        assert "STOCK_COVER_HIGH" in codes

    def test_oil_has_last_purchases(self, seeded_db):
        oil_id = self._get_oil_id(seeded_db)
        data = client.get(f"/api/request-items/{oil_id}").json()
        # History path → last_purchases present, web_quotes absent
        assert data["last_purchases"] is not None
        assert len(data["last_purchases"]) >= 3
        assert data["web_quotes"] is None

    def test_oil_last_purchases_sorted_newest_first(self, seeded_db):
        oil_id = self._get_oil_id(seeded_db)
        data = client.get(f"/api/request-items/{oil_id}").json()
        dates = [p["purchase_date"] for p in data["last_purchases"]]
        assert dates == sorted(dates, reverse=True)


# ---------------------------------------------------------------------------
# Quick check → Add to queue (POST /api/requests)
# ---------------------------------------------------------------------------

class TestQuickCheckAddToQueue:
    """
    Simulates the "Add to today's queue" button on the Quick Check page.
    Sends a POST /api/requests with requested_by="Quick check" and a single
    item line, then verifies:
      - 201 status
      - response is a list with one QueueRow
      - requested_by is "Quick check"
      - history_count and web_quote_count are present (not missing / 500)
      - the row was persisted in the database

    Uses line_no=99 so it never collides with the seeded demo rows (line_no 1-5)
    that test_check_engine.py looks up by line_no in the session-scoped DB.
    """

    # Shared payload — avoids repeating the dict in every test method.
    _PAYLOAD = {
        "requested_by": "Quick check",
        "items": [{
            "line_no": 99,
            "raw_name": "bearing 6205 ZZ",
            "qty": 20,
            "unit": "pcs",
            "quoted_unit_price_idr": 38500,
        }],
    }

    def test_add_quick_check_item_returns_201(self, seeded_db):
        resp = client.post("/api/requests", json=self._PAYLOAD)
        assert resp.status_code == 201

    def test_add_quick_check_item_returns_one_row(self, seeded_db):
        resp = client.post("/api/requests", json=self._PAYLOAD)
        rows = resp.json()
        assert isinstance(rows, list)
        assert len(rows) == 1

    def test_add_quick_check_item_requested_by(self, seeded_db):
        resp = client.post("/api/requests", json=self._PAYLOAD)
        row = resp.json()[0]
        assert row["requested_by"] == "Quick check"

    def test_add_quick_check_item_has_history_count(self, seeded_db):
        """history_count must be present in the response (was the source of the 500)."""
        resp = client.post("/api/requests", json=self._PAYLOAD)
        row = resp.json()[0]
        assert "history_count" in row

    def test_add_quick_check_item_has_web_quote_count(self, seeded_db):
        """web_quote_count must be present in the response (was the source of the 500)."""
        resp = client.post("/api/requests", json=self._PAYLOAD)
        row = resp.json()[0]
        assert "web_quote_count" in row

    def test_add_quick_check_item_persisted(self, seeded_db):
        """The new RequestItem must exist in the database after the call."""
        from app import db as db_module
        resp = client.post("/api/requests", json=self._PAYLOAD)
        row_id = resp.json()[0]["id"]
        sess = db_module.SessionLocal()
        try:
            item = sess.execute(
                select(RequestItem).where(RequestItem.id == row_id)
            ).scalar_one_or_none()
            assert item is not None
            assert item.raw_name == "bearing 6205 ZZ"
        finally:
            sess.close()
