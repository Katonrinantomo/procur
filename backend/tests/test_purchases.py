"""
Tests for GET /api/purchases, GET /api/purchases/item/{id}, and GET /api/suppliers.

Uses the seeded_db fixture from conftest.py (full seed including past requests).
"""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_procur.db")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.main import app  # noqa: E402
from app.models import Item, Purchase, Supplier  # noqa: E402

JAKARTA = timezone(timedelta(hours=7))

client = TestClient(app)


def _today_jakarta() -> date:
    return datetime.now(tz=JAKARTA).date()


# ---------------------------------------------------------------------------
# GET /api/suppliers
# ---------------------------------------------------------------------------

class TestListSuppliers:
    def test_returns_200(self, seeded_db):
        resp = client.get("/api/suppliers")
        assert resp.status_code == 200

    def test_returns_all_8_suppliers(self, seeded_db):
        resp = client.get("/api/suppliers")
        data = resp.json()
        assert len(data) >= 8  # seed has 8; other tests may add more via POST

    def test_sorted_by_name(self, seeded_db):
        resp = client.get("/api/suppliers")
        names = [s["name"] for s in resp.json()]
        assert names == sorted(names)

    def test_has_id_and_name(self, seeded_db):
        resp = client.get("/api/suppliers")
        first = resp.json()[0]
        assert "id" in first
        assert "name" in first


# ---------------------------------------------------------------------------
# GET /api/purchases — unfiltered
# ---------------------------------------------------------------------------

class TestListPurchasesUnfiltered:
    def test_returns_200(self, seeded_db):
        resp = client.get("/api/purchases")
        assert resp.status_code == 200

    def test_response_shape(self, seeded_db):
        data = client.get("/api/purchases").json()
        assert "rows" in data
        assert "total_count" in data
        assert "total_amount_idr" in data
        assert "page" in data
        assert "page_size" in data

    def test_page_size_50(self, seeded_db):
        data = client.get("/api/purchases").json()
        assert data["page_size"] == 50

    def test_first_page_at_most_50_rows(self, seeded_db):
        data = client.get("/api/purchases").json()
        assert len(data["rows"]) <= 50

    def test_newest_first(self, seeded_db):
        data = client.get("/api/purchases").json()
        rows = data["rows"]
        if len(rows) >= 2:
            dates = [r["purchase_date"] for r in rows]
            assert dates == sorted(dates, reverse=True)

    def test_total_count_positive(self, seeded_db):
        data = client.get("/api/purchases").json()
        assert data["total_count"] > 0

    def test_total_amount_idr_positive(self, seeded_db):
        data = client.get("/api/purchases").json()
        assert data["total_amount_idr"] > 0

    def test_row_has_expected_fields(self, seeded_db):
        data = client.get("/api/purchases").json()
        row = data["rows"][0]
        for field in ("id", "purchase_date", "item_id", "item_name",
                      "supplier_id", "supplier_name", "qty", "unit",
                      "unit_price_idr", "total_idr"):
            assert field in row, f"Missing field: {field}"

    def test_total_idr_is_qty_times_price(self, seeded_db):
        data = client.get("/api/purchases").json()
        for row in data["rows"]:
            assert row["total_idr"] == row["qty"] * row["unit_price_idr"]


# ---------------------------------------------------------------------------
# GET /api/purchases — supplier_id filter
# ---------------------------------------------------------------------------

class TestPurchasesSupplierFilter:
    def _get_first_supplier_id(self, seeded_db) -> int:
        from app import db as db_module
        sess = db_module.SessionLocal()
        try:
            s = sess.execute(select(Supplier).limit(1)).scalar_one()
            return s.id
        finally:
            sess.close()

    def test_supplier_filter_returns_only_that_supplier(self, seeded_db):
        sid = self._get_first_supplier_id(seeded_db)
        data = client.get(f"/api/purchases?supplier_id={sid}").json()
        for row in data["rows"]:
            assert row["supplier_id"] == sid

    def test_supplier_filter_unknown_returns_empty(self, seeded_db):
        data = client.get("/api/purchases?supplier_id=99999").json()
        assert data["rows"] == []
        assert data["total_count"] == 0


# ---------------------------------------------------------------------------
# GET /api/purchases — search filter
# ---------------------------------------------------------------------------

class TestPurchasesSearchFilter:
    def test_search_by_item_name(self, seeded_db):
        data = client.get("/api/purchases?search=Bearing").json()
        assert data["total_count"] > 0
        for row in data["rows"]:
            assert "bearing" in row["item_name"].lower()

    def test_search_by_supplier_name(self, seeded_db):
        data = client.get("/api/purchases?search=Sinar").json()
        assert data["total_count"] > 0
        for row in data["rows"]:
            assert "sinar" in row["supplier_name"].lower()

    def test_search_by_po_number(self, seeded_db):
        # PO-0318 is from 2026-03-18; expand the date range to cover it
        data = client.get("/api/purchases?search=PO-0318&date_from=2026-01-01&date_to=2026-12-31").json()
        assert data["total_count"] >= 1

    def test_search_no_match_returns_empty(self, seeded_db):
        data = client.get("/api/purchases?search=XXXXXXXXXXXXXXXX").json()
        assert data["rows"] == []
        assert data["total_count"] == 0


# ---------------------------------------------------------------------------
# GET /api/purchases — date filter
# ---------------------------------------------------------------------------

class TestPurchasesDateFilter:
    def test_date_from_date_to_narrows_results(self, seeded_db):
        today = _today_jakarta()
        # Use a narrow 7-day window ending yesterday
        d_to = today - timedelta(days=1)
        d_from = d_to - timedelta(days=6)
        url = f"/api/purchases?date_from={d_from.isoformat()}&date_to={d_to.isoformat()}"
        data = client.get(url).json()
        # All returned rows should be within that window
        for row in data["rows"]:
            row_date = datetime.fromisoformat(row["purchase_date"]).astimezone(JAKARTA).date()
            assert d_from <= row_date <= d_to

    def test_future_date_range_returns_empty(self, seeded_db):
        future = (_today_jakarta() + timedelta(days=365)).isoformat()
        data = client.get(f"/api/purchases?date_from={future}&date_to={future}").json()
        assert data["total_count"] == 0


# ---------------------------------------------------------------------------
# GET /api/purchases — pagination
# ---------------------------------------------------------------------------

class TestPurchasesPagination:
    def test_page2_different_from_page1(self, seeded_db):
        data1 = client.get("/api/purchases?page=1").json()
        data2 = client.get("/api/purchases?page=2").json()
        # If there are more than 50 rows the pages should differ
        if data1["total_count"] > 50:
            ids1 = {r["id"] for r in data1["rows"]}
            ids2 = {r["id"] for r in data2["rows"]}
            assert ids1.isdisjoint(ids2)

    def test_page2_empty_when_not_enough_rows(self, seeded_db):
        data = client.get("/api/purchases?page=9999").json()
        assert data["rows"] == []


# ---------------------------------------------------------------------------
# GET /api/purchases — total_amount_idr accuracy
# ---------------------------------------------------------------------------

class TestPurchasesTotalAmount:
    def test_total_amount_matches_sum_of_rows(self, seeded_db):
        """
        The total_amount_idr should equal the sum of (qty × unit_price_idr) for
        ALL matching rows (not just the current page).
        We verify this by computing the expected total from the DB directly.
        """
        from app import db as db_module
        from sqlalchemy import func as sqlfunc

        sess = db_module.SessionLocal()
        try:
            today = _today_jakarta()
            d_from = today - timedelta(days=90)
            d_to = today

            JAKARTA_TZ = JAKARTA
            start_dt = datetime(d_from.year, d_from.month, d_from.day, 0, 0, 0, tzinfo=JAKARTA_TZ)
            end_dt = datetime(d_to.year, d_to.month, d_to.day, 23, 59, 59, tzinfo=JAKARTA_TZ) + timedelta(seconds=1)

            rows = sess.execute(
                select(Purchase)
                .where(Purchase.purchase_date >= start_dt, Purchase.purchase_date < end_dt)
            ).scalars().all()
            expected_total = sum(p.qty * p.unit_price_idr for p in rows)
        finally:
            sess.close()

        data = client.get("/api/purchases").json()
        assert data["total_amount_idr"] == expected_total


# ---------------------------------------------------------------------------
# GET /api/purchases/item/{item_id}
# ---------------------------------------------------------------------------

class TestItemPurchaseHistory:
    def _get_bearing_id(self, seeded_db) -> int:
        from app import db as db_module
        sess = db_module.SessionLocal()
        try:
            item = sess.execute(
                select(Item).where(Item.name == "Bearing 6205 ZZ")
            ).scalar_one()
            return item.id
        finally:
            sess.close()

    def test_returns_200(self, seeded_db):
        bearing_id = self._get_bearing_id(seeded_db)
        resp = client.get(f"/api/purchases/item/{bearing_id}")
        assert resp.status_code == 200

    def test_404_for_unknown_item(self, seeded_db):
        resp = client.get("/api/purchases/item/99999")
        assert resp.status_code == 404

    def test_returns_at_most_10_purchases(self, seeded_db):
        bearing_id = self._get_bearing_id(seeded_db)
        data = client.get(f"/api/purchases/item/{bearing_id}").json()
        assert len(data["last_purchases"]) <= 10

    def test_3buy_average_for_bearing(self, seeded_db):
        """Bearing 6205 ZZ last 3 purchases are all 38,000 → avg = 38,000."""
        bearing_id = self._get_bearing_id(seeded_db)
        data = client.get(f"/api/purchases/item/{bearing_id}").json()
        assert data["reference_price_idr"] == 38_000

    def test_has_item_name(self, seeded_db):
        bearing_id = self._get_bearing_id(seeded_db)
        data = client.get(f"/api/purchases/item/{bearing_id}").json()
        assert data["item_name"] == "Bearing 6205 ZZ"

    def test_total_idr_per_row(self, seeded_db):
        bearing_id = self._get_bearing_id(seeded_db)
        data = client.get(f"/api/purchases/item/{bearing_id}").json()
        for row in data["last_purchases"]:
            assert row["total_idr"] == row["qty"] * row["unit_price_idr"]


# ---------------------------------------------------------------------------
# GET /api/request-items (list, no path param)
# ---------------------------------------------------------------------------

class TestRequestItemsList:
    def test_returns_200(self, seeded_db):
        resp = client.get("/api/request-items")
        assert resp.status_code == 200

    def test_response_shape(self, seeded_db):
        data = client.get("/api/request-items").json()
        assert "rows" in data
        assert "total_count" in data
        assert "page" in data
        assert "page_size" in data

    def test_default_excludes_today(self, seeded_db):
        """Default date_to is yesterday, so today's 5 rows should not appear."""
        today = _today_jakarta()
        data = client.get("/api/request-items").json()
        for row in data["rows"]:
            row_date = datetime.fromisoformat(row["requested_at"]).astimezone(JAKARTA).date()
            assert row_date < today, f"Today's row found: {row_date}"

    def test_past_rows_present(self, seeded_db):
        """The 10 seeded past requests should yield rows."""
        data = client.get("/api/request-items").json()
        assert data["total_count"] >= 10

    def test_status_filter(self, seeded_db):
        data = client.get("/api/request-items?status=approved").json()
        for row in data["rows"]:
            assert row["status"] == "approved"

    def test_status_all_returns_all(self, seeded_db):
        all_data = client.get("/api/request-items?status=all").json()
        no_status = client.get("/api/request-items").json()
        assert all_data["total_count"] == no_status["total_count"]

    def test_existing_detail_endpoint_not_shadowed(self, seeded_db):
        """GET /api/request-items/{id} still works for numeric IDs."""
        # Get any valid request item id
        from app import db as db_module
        from app.models import RequestItem
        sess = db_module.SessionLocal()
        try:
            ri = sess.execute(select(RequestItem).limit(1)).scalar_one()
            ri_id = ri.id
        finally:
            sess.close()
        resp = client.get(f"/api/request-items/{ri_id}")
        assert resp.status_code == 200
        # Verify it's the detail schema (has 'flags', 'actions', etc.)
        assert "flags" in resp.json()
