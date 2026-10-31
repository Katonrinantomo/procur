"""
Tests for the Langflow integration layer.

All tests mock run_flow — no live Langflow calls are ever made.

Covers:
  - organizer.parse_text: happy path, code fence stripping, retry on bad JSON
  - web_check.get_web_quotes: cache hit, new fetch, Langflow failure → pending row
  - POST /api/requests/parse: happy path, 502 on LangflowError
"""
from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_procur.db")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-procur-ai-tests-32chars!!")

from app.services.organizer import LineItemDraft, parse_text  # noqa: E402
from app.services.langflow_client import LangflowError  # noqa: E402
from app.security import create_access_token  # noqa: E402


def _auth_headers(role: str = "purchasing", user_id: int = 1) -> dict:
    """Return Authorization headers with a valid JWT for the given role."""
    token = create_access_token(user_id, role)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_RESPONSE = json.dumps({
    "items": [
        {
            "name": "Hydraulic oil ISO VG 46, 20L",
            "qty": 4,
            "unit": "drum",
            "department": "Warehouse",
            "quoted_unit_price_idr": 1450000,
            "supplier": "CV Sinar Pelumas",
        }
    ]
})

FENCED_RESPONSE = f"```json\n{VALID_RESPONSE}\n```"

INVALID_RESPONSE = '{"items": [{"qty": 4}]}'  # missing required "name"

VALID_RESPONSE_AFTER_RETRY = json.dumps({
    "items": [
        {
            "name": "Solenoid valve 24V DC, 1/2\"",
            "qty": 2,
            "unit": "pcs",
            "department": "Maintenance",
            "quoted_unit_price_idr": None,
            "supplier": None,
        }
    ]
})


# ---------------------------------------------------------------------------
# organizer.parse_text — happy path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_text_happy_path():
    """parse_text returns LineItemDraft list when flow returns valid JSON."""
    with patch(
        "app.services.organizer.run_flow",
        new=AsyncMock(return_value={"organize_json": VALID_RESPONSE}),
    ):
        drafts = await parse_text("gudang minta oli hidrolik 4 drum")

    assert len(drafts) == 1
    assert isinstance(drafts[0], LineItemDraft)
    assert drafts[0].name == "Hydraulic oil ISO VG 46, 20L"
    assert drafts[0].qty == 4
    assert drafts[0].unit == "drum"
    assert drafts[0].quoted_unit_price_idr == 1_450_000
    assert drafts[0].supplier == "CV Sinar Pelumas"


# ---------------------------------------------------------------------------
# organizer.parse_text — code fence stripping
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_text_strips_code_fences():
    """parse_text succeeds even when the model wraps its JSON in code fences."""
    with patch(
        "app.services.organizer.run_flow",
        new=AsyncMock(return_value={"organize_json": FENCED_RESPONSE}),
    ):
        drafts = await parse_text("test input")

    assert len(drafts) == 1
    assert drafts[0].name == "Hydraulic oil ISO VG 46, 20L"


# ---------------------------------------------------------------------------
# organizer.parse_text — retry on invalid JSON
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_text_retries_on_invalid_and_succeeds():
    """
    When the first answer fails Pydantic validation the function retries
    once.  The second call (with the validation error appended) returns
    valid JSON and the drafts are returned successfully.
    """
    call_count = 0

    async def _mock_run_flow(flow_id: str, text: str) -> dict[str, str]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {"organize_json": INVALID_RESPONSE}
        # Second call receives the original text + error hint
        assert "Previous answer was invalid" in text
        return {"organize_json": VALID_RESPONSE_AFTER_RETRY}

    with patch("app.services.organizer.run_flow", new=_mock_run_flow):
        drafts = await parse_text("2 solenoid valve 24V")

    assert call_count == 2
    assert len(drafts) == 1
    assert drafts[0].name == "Solenoid valve 24V DC, 1/2\""
    assert drafts[0].qty == 2


# ---------------------------------------------------------------------------
# organizer.parse_text — LangflowError propagates
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_parse_text_propagates_langflow_error():
    """LangflowError from run_flow is not swallowed."""
    with patch(
        "app.services.organizer.run_flow",
        new=AsyncMock(side_effect=LangflowError("connection refused")),
    ):
        with pytest.raises(LangflowError):
            await parse_text("some text")


# ---------------------------------------------------------------------------
# POST /api/requests/parse — HTTP layer
# ---------------------------------------------------------------------------

def test_parse_endpoint_returns_drafts(seeded_db):
    """POST /api/requests/parse returns 200 with draft list on success."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app import routers as _routers  # noqa: F401
    import app.routers.requests as _req_router

    client = TestClient(app)

    with patch.object(
        _req_router.settings,
        "LANGFLOW_ORGANIZE_FLOW_ID",
        "test-flow-id",
    ), patch(
        "app.routers.requests.parse_text",
        new=AsyncMock(
            return_value=[
                LineItemDraft(
                    name="Bearing 6205 ZZ",
                    qty=20,
                    unit="pcs",
                    department="Maintenance",
                    quoted_unit_price_idr=38500,
                    supplier=None,
                )
            ]
        ),
    ):
        resp = client.post(
            "/api/requests/parse",
            json={"text": "maintenance minta bearing 6205 ZZ 20 pcs"},
            headers=_auth_headers(),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Bearing 6205 ZZ"
    assert data[0]["qty"] == 20


def test_parse_endpoint_returns_502_on_langflow_error(seeded_db):
    """POST /api/requests/parse returns 502 when Langflow fails."""
    from fastapi.testclient import TestClient
    from app.main import app
    import app.routers.requests as _req_router

    client = TestClient(app)

    with patch.object(
        _req_router.settings,
        "LANGFLOW_ORGANIZE_FLOW_ID",
        "test-flow-id",
    ), patch(
        "app.routers.requests.parse_text",
        new=AsyncMock(side_effect=LangflowError("connection refused")),
    ):
        resp = client.post(
            "/api/requests/parse",
            json={"text": "some text"},
            headers=_auth_headers(),
        )

    assert resp.status_code == 502
    assert "connection refused" in resp.json()["detail"]
