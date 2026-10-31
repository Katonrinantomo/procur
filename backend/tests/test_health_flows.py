"""
Tests for GET /api/health/flows (owner only).
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import select

from app import flowcheck
from app.main import app
from app.models import User
from app.security import create_access_token


def _headers_for(role: str) -> dict:
    import app.db as db_module

    with db_module.SessionLocal() as sess:
        user = sess.execute(select(User).where(User.role == role)).scalars().first()
        token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


def test_owner_gets_flow_health(seeded_db, tmp_path, monkeypatch):
    result_path = tmp_path / "last.json"
    result_path.write_text(json.dumps({
        "at": "2026-10-31T01:00:00+00:00",
        "ok": False,
        "results": [
            {"flow": "organize", "fixture": "01_clean.txt", "ok": True, "seconds": 2.1, "error": ""},
            {"flow": "organize", "fixture": "02_messy.txt", "ok": False, "seconds": 3.0, "error": "bad"},
            {"flow": "maker", "fixture": "-", "ok": None, "seconds": None, "error": "empty"},
        ],
    }), encoding="utf-8")
    monkeypatch.setattr(flowcheck, "RESULT_PATH", result_path)

    client = TestClient(app)
    with patch("app.routers.health.langflow_client.ping", new=AsyncMock(return_value=True)):
        resp = client.get("/api/health/flows", headers=_headers_for("owner"))

    assert resp.status_code == 200
    body = resp.json()
    assert set(body["flows"]) == {"organize", "web_check", "maker", "checker", "narrator"}
    assert all(set(v) == {"configured"} for v in body["flows"].values())
    assert body["langflow"] in {"ok", "not configured"}
    assert body["last_flowcheck"] == {
        "at": "2026-10-31T01:00:00+00:00",
        "ok": False,
        "failed": ["organize/02_messy.txt"],
    }


def test_no_flowcheck_run_yet(seeded_db, tmp_path, monkeypatch):
    monkeypatch.setattr(flowcheck, "RESULT_PATH", tmp_path / "missing.json")

    client = TestClient(app)
    with patch("app.routers.health.langflow_client.ping", new=AsyncMock(return_value=False)):
        resp = client.get("/api/health/flows", headers=_headers_for("owner"))

    assert resp.status_code == 200
    assert resp.json()["last_flowcheck"] is None


def test_purchasing_gets_403(seeded_db):
    client = TestClient(app)
    resp = client.get("/api/health/flows", headers=_headers_for("purchasing"))
    assert resp.status_code == 403


def test_no_token_gets_401(seeded_db):
    client = TestClient(app)
    resp = client.get("/api/health/flows")
    assert resp.status_code == 401
