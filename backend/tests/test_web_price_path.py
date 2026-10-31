"""
Tests for the web-price path bugs fixed in AUDIT.md items H1, H2, M1, M3.

Covers:
  - quick_check with unknown item + web flow returning [] → status "new", no reference, no 500
  - "Solenoid valve 24V DC 1/2 inch" via dry_check_item uses seeded solenoid
    cache quotes and their median (425,000)
  - "Solenoid valve 24V DC 1/2 inch" via POST /api/requests uses the same
    cached solenoid quotes and the same median
  - dry_check_item for Item A never uses web quotes seeded for Item B
  - M1: quick_check returns 502 with a friendly message when LANGFLOW_ORGANIZE_FLOW_ID
    is not configured
"""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_procur.db")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-procur-ai-tests-32chars!!")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.security import create_access_token  # noqa: E402
from app.services.checker import DryCheckDraft, dry_check_item  # noqa: E402
from app.services.langflow_client import LangflowError  # noqa: E402

client = TestClient(app)


def _auth_headers(role: str = "purchasing", user_id: int = 1) -> dict:
    token = create_access_token(user_id, role)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# H1 + H2: unknown item, web flow returns [] → status "new", no 500
# ---------------------------------------------------------------------------

class TestUnknownItemNoWebQuotes:
    """
    dry_check_item for an item with no purchase history and an empty web
    response must return status="new" with no reference price.
    It must NOT raise an exception (was previously 500 from session.refresh
    on an unsaved RequestItem shim).
    """

    _DRAFT: DryCheckDraft = {
        "raw_name": "Kain sutra putih, 10 yard",
        "qty": 10,
        "unit": "yard",
        "quoted_unit_price_idr": 500_000,
        "quoting_supplier_name": None,
        "supplier_id": None,
    }

    def test_returns_new_status(self, session):
        """Web flow returning [] should give status new, not 500."""
        with patch(
            "app.services.web_check._call_flow",
            return_value=[],
        ):
            result = dry_check_item(self._DRAFT, session)

        assert result["status"] == "new"

    def test_no_reference_price(self, session):
        with patch(
            "app.services.web_check._call_flow",
            return_value=[],
        ):
            result = dry_check_item(self._DRAFT, session)

        assert result["reference_unit_price_idr"] is None

    def test_no_check_error(self, session):
        with patch(
            "app.services.web_check._call_flow",
            return_value=[],
        ):
            result = dry_check_item(self._DRAFT, session)

        assert result["check_error"] is None

    def test_web_quotes_empty(self, session):
        with patch(
            "app.services.web_check._call_flow",
            return_value=[],
        ):
            result = dry_check_item(self._DRAFT, session)

        assert result["web_quotes"] == []


# ---------------------------------------------------------------------------
# H2: solenoid via dry_check_item uses cached quotes + correct median
# ---------------------------------------------------------------------------

class TestSolenoidDryCheck:
    """
    dry_check_item for "Solenoid valve 24V DC 1/2 inch" must find the
    seeded solenoid cache quotes (fuzzy match) and compute median = 425,000.
    Langflow must NOT be called (cache hit).
    """

    _DRAFT: DryCheckDraft = {
        "raw_name": "Solenoid valve 24V DC 1/2 inch",
        "qty": 2,
        "unit": "pcs",
        "quoted_unit_price_idr": 420_000,
        "quoting_supplier_name": None,
        "supplier_id": None,
    }

    def test_checked_via_web(self, session):
        with patch("app.services.web_check._call_flow") as mock_flow:
            result = dry_check_item(self._DRAFT, session)
        mock_flow.assert_not_called()
        assert result["checked_via"] == "web"

    def test_reference_price_is_median(self, session):
        """Median of 398_000, 425_000, 465_000 = 425_000."""
        with patch("app.services.web_check._call_flow") as mock_flow:
            result = dry_check_item(self._DRAFT, session)
        mock_flow.assert_not_called()
        assert result["reference_unit_price_idr"] == 425_000

    def test_web_quotes_are_the_three_seeded_quotes(self, session):
        with patch("app.services.web_check._call_flow") as mock_flow:
            result = dry_check_item(self._DRAFT, session)
        mock_flow.assert_not_called()
        prices = {wq["price_idr"] for wq in result["web_quotes"]}
        assert prices == {398_000, 425_000, 465_000}

    def test_status_new_no_flags(self, session):
        """Price 420k vs ref 425k → −1.2% → below threshold → no PRICE_ABOVE_REF."""
        with patch("app.services.web_check._call_flow"):
            result = dry_check_item(self._DRAFT, session)
        assert result["status"] == "new"
        assert result["flags"] == []


# ---------------------------------------------------------------------------
# H2: solenoid via POST /api/requests uses the same cache + same median
# ---------------------------------------------------------------------------

class TestSolenoidViaPostRequests:
    """
    POST /api/requests with a solenoid line item must produce the same
    reference price (425,000) as the dry-check path.
    """

    _PAYLOAD = {
        "requested_by": "audit-test",
        "items": [{
            "line_no": 98,
            "raw_name": "Solenoid valve 24V DC 1/2 inch",
            "qty": 2,
            "unit": "pcs",
            "quoted_unit_price_idr": 420_000,
        }],
    }

    def test_reference_price_is_median(self, seeded_db):
        resp = client.post("/api/requests", json=self._PAYLOAD, headers=_auth_headers("purchasing", 1))
        assert resp.status_code == 201
        row = resp.json()[0]
        assert row["reference_unit_price_idr"] == 425_000

    def test_checked_via_web(self, seeded_db):
        resp = client.post("/api/requests", json=self._PAYLOAD, headers=_auth_headers("purchasing", 1))
        row = resp.json()[0]
        assert row["checked_via"] == "web"

    def test_web_quote_count_three(self, seeded_db):
        resp = client.post("/api/requests", json=self._PAYLOAD, headers=_auth_headers("purchasing", 1))
        row = resp.json()[0]
        # The three seeded quotes (or their clones) should be linked to this row
        assert row["web_quote_count"] >= 3


# ---------------------------------------------------------------------------
# H2: quotes for Item A are never used for Item B
# ---------------------------------------------------------------------------

class TestQuoteIsolation:
    """
    A dry_check_item for an item whose normalized name does NOT match the
    solenoid key must not get solenoid quotes.
    """

    _DRAFT_BEARING: DryCheckDraft = {
        "raw_name": "Kain sutra putih, 10 yard",
        "qty": 5,
        "unit": "yard",
        "quoted_unit_price_idr": 100_000,
        "quoting_supplier_name": None,
        "supplier_id": None,
    }

    def test_no_solenoid_quotes_for_unrelated_item(self, session):
        with patch(
            "app.services.web_check._call_flow",
            return_value=[],
        ):
            result = dry_check_item(self._DRAFT_BEARING, session)

        # Must have no web quotes (solenoid quotes must not leak)
        assert result["web_quotes"] == []
        assert result["reference_unit_price_idr"] is None


# ---------------------------------------------------------------------------
# M1: quick_check returns 502 when LANGFLOW_ORGANIZE_FLOW_ID not configured
# ---------------------------------------------------------------------------

class TestQuickCheckM1:
    """
    POST /api/quick-check must return HTTP 502 with a friendly message when
    LANGFLOW_ORGANIZE_FLOW_ID is not set, matching the behaviour of
    POST /api/requests/parse.
    """

    def test_returns_502_when_flow_not_configured(self, seeded_db):
        import app.routers.quick_check as _qc_router

        with patch.object(_qc_router.settings, "LANGFLOW_ORGANIZE_FLOW_ID", ""):
            resp = client.post(
                "/api/quick-check",
                json={"text": "solenoid valve 2 pcs"},
                headers=_auth_headers(),
            )

        assert resp.status_code == 502
        assert "LANGFLOW_ORGANIZE_FLOW_ID" in resp.json()["detail"]

    def test_returns_502_on_langflow_error(self, seeded_db):
        import app.routers.quick_check as _qc_router

        with patch.object(
            _qc_router.settings, "LANGFLOW_ORGANIZE_FLOW_ID", "test-flow-id"
        ), patch(
            "app.routers.quick_check.parse_text",
            new=AsyncMock(side_effect=LangflowError("connection refused")),
        ):
            resp = client.post(
                "/api/quick-check",
                json={"text": "solenoid valve 2 pcs"},
                headers=_auth_headers(),
            )

        assert resp.status_code == 502
        assert "connection refused" in resp.json()["detail"]
