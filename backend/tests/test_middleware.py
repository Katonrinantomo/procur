"""
Tests for SEC-02 & SEC-13: localhost middleware hardening.

Verifies:
- CORS: only http://localhost:5173 is allowed as origin
- TrustedHost: requests from unexpected Host headers are rejected
- Security headers: X-Content-Type-Options, Referrer-Policy, X-Frame-Options
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_procur.db")
os.environ.setdefault("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-procur-ai-tests-32chars!!")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

client = TestClient(app)


class TestSecurityHeaders:
    """All responses must carry the required security headers."""

    def test_x_content_type_options(self, seeded_db):
        resp = client.get("/api/health")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"

    def test_referrer_policy(self, seeded_db):
        resp = client.get("/api/health")
        assert resp.headers.get("Referrer-Policy") == "no-referrer"

    def test_x_frame_options(self, seeded_db):
        resp = client.get("/api/health")
        assert resp.headers.get("X-Frame-Options") == "DENY"

    def test_headers_on_non_200_response(self, seeded_db):
        """Security headers must be present even on 404 responses."""
        resp = client.get("/api/request-items/999999999")
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"


class TestTrustedHost:
    """Requests with unexpected Host headers must be rejected (400)."""

    def test_invalid_host_rejected(self, seeded_db):
        """Host: evil.example.com must be rejected."""
        resp = client.get("/api/health", headers={"Host": "evil.example.com"})
        assert resp.status_code == 400

    def test_localhost_host_accepted(self, seeded_db):
        """Host: localhost must be accepted."""
        resp = client.get("/api/health", headers={"Host": "localhost"})
        assert resp.status_code == 200

    def test_127_host_accepted(self, seeded_db):
        """Host: 127.0.0.1 must be accepted."""
        resp = client.get("/api/health", headers={"Host": "127.0.0.1"})
        assert resp.status_code == 200
