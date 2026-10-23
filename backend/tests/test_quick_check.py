"""
Tests for dry_check_item — verifies the dry-run path produces the expected
flags and writes nothing to the database.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models import Flag, RequestItem
from app.services.checker import DryCheckDraft, dry_check_item


class TestDryCheckOilItem:
    """
    Dry-check 'oli hidrolik 46 20L' at Rp 1,450,000 from CV Sinar Pelumas.
    Expected: status=flagged, PRICE_ABOVE_REF + STOCK_COVER_HIGH flags,
    no new RequestItem or Flag rows in the DB.
    """

    def _build_draft(self, session) -> DryCheckDraft:
        from app.models import Supplier
        sup = session.execute(
            select(Supplier).where(Supplier.name == "CV Sinar Pelumas")
        ).scalar_one_or_none()
        return DryCheckDraft(
            raw_name="oli hidrolik 46 20L",
            qty=4,
            unit="drum",
            quoted_unit_price_idr=1_450_000,
            quoting_supplier_name="CV Sinar Pelumas",
            supplier_id=sup.id if sup else None,
        )

    def test_status_flagged(self, session):
        draft = self._build_draft(session)
        result = dry_check_item(draft, session)
        assert result["status"] == "flagged"

    def test_flags_include_price_above_ref(self, session):
        draft = self._build_draft(session)
        result = dry_check_item(draft, session)
        codes = [f["code"] for f in result["flags"]]
        assert "PRICE_ABOVE_REF" in codes

    def test_flags_include_stock_cover_high(self, session):
        draft = self._build_draft(session)
        result = dry_check_item(draft, session)
        codes = [f["code"] for f in result["flags"]]
        assert "STOCK_COVER_HIGH" in codes

    def test_no_new_request_item_rows(self, session):
        before = session.execute(select(RequestItem)).scalars().all()
        before_count = len(before)
        draft = self._build_draft(session)
        dry_check_item(draft, session)
        after_count = len(session.execute(select(RequestItem)).scalars().all())
        assert after_count == before_count

    def test_no_new_flag_rows(self, session):
        before_count = len(session.execute(select(Flag)).scalars().all())
        draft = self._build_draft(session)
        dry_check_item(draft, session)
        after_count = len(session.execute(select(Flag)).scalars().all())
        assert after_count == before_count

    def test_checked_via_history(self, session):
        draft = self._build_draft(session)
        result = dry_check_item(draft, session)
        assert result["checked_via"] == "history"

    def test_last_purchases_populated(self, session):
        draft = self._build_draft(session)
        result = dry_check_item(draft, session)
        assert len(result["last_purchases"]) > 0

    def test_reference_price(self, session):
        draft = self._build_draft(session)
        result = dry_check_item(draft, session)
        assert result["reference_unit_price_idr"] == 1_120_000
