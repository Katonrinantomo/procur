"""
Integration tests for the check engine — verifies the 5 demo rows produce
exactly the results documented in the plan's Database section.

All assertions are against the seeded + checked data; no live Langflow calls
are made (web_check.py returns cached quotes only).
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import Flag, Item, RequestItem


def _get_row(session, line_no: int) -> RequestItem:
    """Return today's seeded RequestItem for the given line number."""
    from app.models import Request
    from datetime import datetime, timedelta, timezone
    JAKARTA = timezone(timedelta(hours=7))
    today = datetime.now(tz=JAKARTA).date()
    day_start = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=JAKARTA)
    day_end = day_start + timedelta(days=1)
    row = session.execute(
        select(RequestItem)
        .join(Request, Request.id == RequestItem.request_id)
        .where(
            RequestItem.line_no == line_no,
            Request.requested_at >= day_start,
            Request.requested_at < day_end,
        )
    ).scalar_one()
    return row


class TestHydraulicOil:
    """
    Row 01 — Hydraulic oil ISO VG 46, 20L
    Expected: reference 1,120,000 · +29.5% · flagged (PRICE_ABOVE_REF + STOCK_COVER_HIGH)
    """

    def test_reference_price(self, session):
        row = _get_row(session, 1)
        assert row.reference_unit_price_idr == 1_120_000

    def test_diff_pct(self, session):
        row = _get_row(session, 1)
        assert float(row.diff_pct) == pytest.approx(29.5, abs=0.05)

    def test_status_flagged(self, session):
        row = _get_row(session, 1)
        assert row.status == "flagged"

    def test_flag_price_above_ref(self, session):
        row = _get_row(session, 1)
        codes = [f.code for f in row.flags]
        assert "PRICE_ABOVE_REF" in codes

    def test_flag_stock_cover_high(self, session):
        row = _get_row(session, 1)
        codes = [f.code for f in row.flags]
        assert "STOCK_COVER_HIGH" in codes

    def test_stock_cover_message(self, session):
        row = _get_row(session, 1)
        stock_flag = next(f for f in row.flags if f.code == "STOCK_COVER_HIGH")
        # 3 drum / 2 per month = 1.5 months = ~6.45 weeks → rounds to 6
        assert "6" in stock_flag.message
        assert "weeks" in stock_flag.message

    def test_checked_via_history(self, session):
        row = _get_row(session, 1)
        assert row.checked_via == "history"

    def test_history_count(self, session):
        row = _get_row(session, 1)
        assert row.history_count == 3


class TestSolenoidValve:
    """
    Row 02 — Solenoid valve 24V DC, 1/2"
    Expected: not in catalog · reference 425,000 from 3 web quotes (median) · new
    """

    def test_no_catalog_match(self, session):
        row = _get_row(session, 2)
        assert row.item_id is None

    def test_reference_price_web_median(self, session):
        # quotes: 398_000, 425_000, 465_000 — median is 425_000
        row = _get_row(session, 2)
        assert row.reference_unit_price_idr == 425_000

    def test_checked_via_web(self, session):
        row = _get_row(session, 2)
        assert row.checked_via == "web"

    def test_status_new(self, session):
        row = _get_row(session, 2)
        assert row.status == "new"

    def test_no_flags(self, session):
        row = _get_row(session, 2)
        assert row.flags == []


class TestBearing:
    """
    Row 03 — Bearing 6205 ZZ
    Expected: +1.3% · checked · no flags
    """

    def test_diff_pct(self, session):
        row = _get_row(session, 3)
        assert float(row.diff_pct) == pytest.approx(1.3, abs=0.05)

    def test_status_checked(self, session):
        row = _get_row(session, 3)
        assert row.status == "checked"

    def test_no_flags(self, session):
        row = _get_row(session, 3)
        assert row.flags == []

    def test_reference_price(self, session):
        row = _get_row(session, 3)
        assert row.reference_unit_price_idr == 38_000


class TestWorkGloves:
    """
    Row 04 — Work gloves, cotton dotted
    Expected: −2.0% · checked · no flags
    """

    def test_diff_pct(self, session):
        row = _get_row(session, 4)
        assert float(row.diff_pct) == pytest.approx(-2.0, abs=0.05)

    def test_status_checked(self, session):
        row = _get_row(session, 4)
        assert row.status == "checked"

    def test_no_flags(self, session):
        row = _get_row(session, 4)
        assert row.flags == []

    def test_reference_price(self, session):
        row = _get_row(session, 4)
        assert row.reference_unit_price_idr == 98_000


class TestPackingTape:
    """
    Row 05 — Packing tape 48mm, clear
    Expected: +2.4% · checked · no flags
    """

    def test_diff_pct(self, session):
        row = _get_row(session, 5)
        assert float(row.diff_pct) == pytest.approx(2.4, abs=0.05)

    def test_status_checked(self, session):
        row = _get_row(session, 5)
        assert row.status == "checked"

    def test_no_flags(self, session):
        row = _get_row(session, 5)
        assert row.flags == []

    def test_reference_price(self, session):
        row = _get_row(session, 5)
        assert row.reference_unit_price_idr == 205_000
