"""
M16 auth tests.

Covers:
  - test_every_route_requires_auth: every protected route returns 401 without token
  - forged_token: a token signed with the old fallback secret returns 401
  - role_403: purchasing user gets 403 on approve/return
  - self_approval_403: owner gets 403 when approving their own request
  - password hashing: new per-user-salt format
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_procur.db")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-procur-ai-tests-32chars!!")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.main import app  # noqa: E402
from app.models import Request, RequestItem  # noqa: E402
from app.security import create_access_token, hash_password, verify_password  # noqa: E402

client = TestClient(app)


def _auth_headers(role: str = "purchasing", user_id: int = 1) -> dict:
    token = create_access_token(user_id, role)
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# SEC: every protected route requires a valid token
# ---------------------------------------------------------------------------

# Routes that are exempt from auth (login and health).
_AUTH_EXEMPT = {
    "/api/auth/login",
    "/api/health",
}

# Methods that are known to write state in the DB. We skip POST to
# /api/requests (needs a body) in the 401 test — the 401 fires before
# the body is parsed so it's fine, but we include it anyway by passing
# an empty body.


class TestEveryRouteRequiresAuth:
    """Walk app.routes and assert that all non-exempt endpoints return 401 without a token."""

    def test_every_route_returns_401_without_token(self, seeded_db):
        """
        Iterate over all routes registered in the app.  For each route that
        is NOT in the exempt list, send a request WITHOUT an Authorization
        header and assert HTTP 401.

        Routes that require a path parameter get a sentinel value (99999 for
        int params, "test" for string params) so that the path resolves but
        the 401 fires before any DB lookup.
        """
        from fastapi.routing import APIRoute
        from starlette.routing import Mount
        import re

        failures = []
        checked = 0

        # Collect all APIRoutes, including those on sub-routers.
        # FastAPI's include_router wraps routers as _IncludedRouter with an
        # original_router attribute; recurse through both patterns.
        def _collect_routes(routes):
            result = []
            for route in routes:
                if isinstance(route, APIRoute):
                    result.append(route)
                elif hasattr(route, 'original_router') and hasattr(route.original_router, 'routes'):
                    result.extend(_collect_routes(route.original_router.routes))
                elif hasattr(route, 'routes'):
                    result.extend(_collect_routes(route.routes))
            return result

        all_routes = _collect_routes(app.routes)

        for route in all_routes:
            if not isinstance(route, APIRoute):
                continue

            path = route.path
            # Skip exempt paths
            if path in _AUTH_EXEMPT:
                continue

            # Replace path params with sentinel values
            resolved = re.sub(r"\{[^}]+\}", "99999", path)

            for method in route.methods or ["GET"]:
                # For mutation methods, send an empty JSON body to avoid 422
                # from validation (the 401 check fires before schema validation
                # when the dependency is router-level).
                kwargs: dict = {}
                if method in ("POST", "PUT", "PATCH"):
                    kwargs["json"] = {}

                resp = getattr(client, method.lower())(resolved, **kwargs)
                if resp.status_code != 401:
                    failures.append(
                        f"{method} {path} → {resp.status_code} (expected 401)"
                    )
                else:
                    checked += 1

        assert not failures, (
            f"The following routes did not return 401 without auth:\n"
            + "\n".join(failures)
        )
        assert checked > 0, "No protected routes were found — check route registration"


# ---------------------------------------------------------------------------
# SEC: forged token with wrong secret returns 401
# ---------------------------------------------------------------------------

class TestForgedToken:
    """A JWT signed with the old fallback secret must be rejected."""

    def test_forged_token_returns_401(self, seeded_db):
        """Build a token using a different key and assert 401."""
        import base64
        import hashlib
        import hmac
        import json
        import time

        # Forge a token using the OLD hardcoded fallback secret
        old_secret = "procur.ai-dev-secret-change-me".encode()
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {"sub": "1", "role": "purchasing", "exp": int(time.time()) + 3600}

        def b64url(data: bytes) -> str:
            return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

        h = b64url(json.dumps(header, separators=(",", ":")).encode())
        p = b64url(json.dumps(payload, separators=(",", ":")).encode())
        sig = b64url(
            hmac.new(old_secret, f"{h}.{p}".encode(), hashlib.sha256).digest()
        )
        forged = f"{h}.{p}.{sig}"

        resp = client.get(
            "/api/queue",
            headers={"Authorization": f"Bearer {forged}"},
        )
        assert resp.status_code == 401, (
            f"Expected 401 for forged token, got {resp.status_code}"
        )


# ---------------------------------------------------------------------------
# Role 403: purchasing user cannot approve or return
# ---------------------------------------------------------------------------

class TestRole403:
    """purchasing role must get 403 on approve and return endpoints."""

    def _get_any_item_id(self, seeded_db) -> int:
        from app import db as db_module
        sess = db_module.SessionLocal()
        try:
            ri = sess.execute(select(RequestItem).limit(1)).scalar_one()
            return ri.id
        finally:
            sess.close()

    def test_purchasing_cannot_approve(self, seeded_db):
        item_id = self._get_any_item_id(seeded_db)
        resp = client.post(
            f"/api/request-items/{item_id}/approve",
            json={},
            headers=_auth_headers("purchasing", 1),
        )
        assert resp.status_code == 403

    def test_purchasing_cannot_return(self, seeded_db):
        item_id = self._get_any_item_id(seeded_db)
        resp = client.post(
            f"/api/request-items/{item_id}/return",
            json={"note": "test"},
            headers=_auth_headers("purchasing", 1),
        )
        assert resp.status_code == 403

    def test_finance_cannot_approve(self, seeded_db):
        item_id = self._get_any_item_id(seeded_db)
        resp = client.post(
            f"/api/request-items/{item_id}/approve",
            json={},
            headers=_auth_headers("finance", 3),
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Self-approval 403: owner cannot approve a request they created
# ---------------------------------------------------------------------------

class TestSelfApproval403:
    """Owner gets 403 when approving/returning a request they created."""

    def test_owner_cannot_approve_own_request(self, seeded_db):
        """
        Create a request as owner (user_id=2), then try to approve one of its
        items as the same owner — must get 403.
        """
        from app import db as db_module
        from app.models import User
        from sqlalchemy import select as sa_select

        # Find owner user id
        sess = db_module.SessionLocal()
        try:
            owner = sess.execute(
                sa_select(User).where(User.role == "owner")
            ).scalar_one()
            owner_id = owner.id
        finally:
            sess.close()

        # Create a request as owner
        resp = client.post(
            "/api/requests",
            json={
                "requested_by": "owner-self-test",
                "items": [{
                    "line_no": 997,
                    "raw_name": "Test item for self-approval",
                    "qty": 1,
                    "unit": "pcs",
                }],
            },
            headers=_auth_headers("owner", owner_id),
        )
        assert resp.status_code == 201, f"Failed to create: {resp.text}"
        item_id = resp.json()[0]["id"]

        # Try to approve the item as the same owner
        resp2 = client.post(
            f"/api/request-items/{item_id}/approve",
            json={},
            headers=_auth_headers("owner", owner_id),
        )
        assert resp2.status_code == 403, (
            f"Expected 403 for self-approval, got {resp2.status_code}"
        )

    def test_owner_cannot_return_own_request(self, seeded_db):
        """Same as above but for return."""
        from app import db as db_module
        from app.models import User
        from sqlalchemy import select as sa_select

        sess = db_module.SessionLocal()
        try:
            owner = sess.execute(
                sa_select(User).where(User.role == "owner")
            ).scalar_one()
            owner_id = owner.id
        finally:
            sess.close()

        resp = client.post(
            "/api/requests",
            json={
                "requested_by": "owner-self-return-test",
                "items": [{
                    "line_no": 998,
                    "raw_name": "Test item for self-return",
                    "qty": 1,
                    "unit": "pcs",
                }],
            },
            headers=_auth_headers("owner", owner_id),
        )
        assert resp.status_code == 201
        item_id = resp.json()[0]["id"]

        resp2 = client.post(
            f"/api/request-items/{item_id}/return",
            json={"note": "self-return test"},
            headers=_auth_headers("owner", owner_id),
        )
        assert resp2.status_code == 403, (
            f"Expected 403 for self-return, got {resp2.status_code}"
        )


# ---------------------------------------------------------------------------
# Password hashing: new per-user salt format
# ---------------------------------------------------------------------------

class TestPasswordHashing:
    """Verify the new PBKDF2 with per-user random salt."""

    def test_hash_format(self):
        h = hash_password("test")
        parts = h.split("$")
        assert len(parts) == 4
        assert parts[0] == "pbkdf2_sha256"
        # Iteration count — production uses 600000; tests override to 1000
        assert int(parts[1]) >= 1000

    def test_two_hashes_differ(self):
        """Same password → different salts → different hashes."""
        h1 = hash_password("password")
        h2 = hash_password("password")
        assert h1 != h2

    def test_verify_correct_password(self):
        h = hash_password("mypassword")
        assert verify_password("mypassword", h) is True

    def test_verify_wrong_password(self):
        h = hash_password("mypassword")
        assert verify_password("wrong", h) is False

    def test_legacy_format_rejected(self):
        """The old static-salt base64 blob must not verify successfully."""
        import base64
        import hashlib

        old_salt = b"procur.ai"
        dk = hashlib.pbkdf2_hmac("sha256", b"password123", old_salt, 100_000, dklen=32)
        legacy_hash = base64.urlsafe_b64encode(dk).decode()
        assert verify_password("password123", legacy_hash) is False


# ---------------------------------------------------------------------------
# Helpers for the role-map tests below
# ---------------------------------------------------------------------------

def _user_id(role: str) -> int:
    from app import db as db_module
    from app.models import User

    sess = db_module.SessionLocal()
    try:
        return sess.execute(select(User).where(User.role == role)).scalar_one().id
    finally:
        sess.close()


def _seeded_item_id() -> int:
    """A row from a seeded request (created by the purchasing user)."""
    from app import db as db_module

    sess = db_module.SessionLocal()
    try:
        return sess.execute(select(RequestItem.id).order_by(RequestItem.id).limit(1)).scalar_one()
    finally:
        sess.close()


# ---------------------------------------------------------------------------
# Bad tokens
# ---------------------------------------------------------------------------

class TestBadTokens:
    def _sign(self, payload: dict) -> str:
        import base64
        import hashlib
        import hmac
        import json

        from app.config import settings

        def b64url(data: bytes) -> str:
            return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

        h = b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
        p = b64url(json.dumps(payload).encode())
        sig = b64url(hmac.new(settings.JWT_SECRET.encode(), f"{h}.{p}".encode(), hashlib.sha256).digest())
        return f"{h}.{p}.{sig}"

    def test_token_without_sub_returns_401(self, seeded_db):
        import time

        token = self._sign({"role": "owner", "exp": int(time.time()) + 3600})
        resp = client.get("/api/queue", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    def test_expired_token_returns_401(self, seeded_db):
        import time

        token = self._sign({"sub": "1", "role": "owner", "exp": int(time.time()) - 10})
        resp = client.get("/api/queue", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401

    def test_garbage_token_returns_401(self, seeded_db):
        resp = client.get("/api/queue", headers={"Authorization": "Bearer not.a.jwt"})
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Role map: purchasing-only and entry endpoints
# ---------------------------------------------------------------------------

class TestRoleMap:
    def test_finance_cannot_add_request(self, seeded_db):
        resp = client.post(
            "/api/requests",
            json={"items": [{"line_no": 1, "raw_name": "x", "qty": 1, "unit": "pcs"}]},
            headers=_auth_headers("finance", _user_id("finance")),
        )
        assert resp.status_code == 403

    def test_finance_cannot_parse(self, seeded_db):
        resp = client.post(
            "/api/requests/parse",
            json={"text": "1. Bearing 6205 - 2 pcs"},
            headers=_auth_headers("finance", _user_id("finance")),
        )
        assert resp.status_code == 403

    @pytest.mark.parametrize("role", ["owner", "finance"])
    def test_only_purchasing_can_quick_check(self, seeded_db, role):
        resp = client.post(
            "/api/quick-check",
            json={"text": "Bearing 6205 - 2 pcs"},
            headers=_auth_headers(role, _user_id(role)),
        )
        assert resp.status_code == 403

    @pytest.mark.parametrize("role", ["owner", "finance"])
    def test_only_purchasing_can_import(self, seeded_db, role):
        resp = client.post(
            "/api/imports/purchases",
            files={"file": ("p.csv", b"date,po_number\n", "text/csv")},
            headers=_auth_headers(role, _user_id(role)),
        )
        assert resp.status_code == 403

    def test_purchasing_cannot_read_audit_log(self, seeded_db):
        resp = client.get("/api/audit-logs", headers=_auth_headers("purchasing", _user_id("purchasing")))
        assert resp.status_code == 403

    @pytest.mark.parametrize("role", ["owner", "finance"])
    def test_owner_and_finance_can_read_audit_log(self, seeded_db, role):
        resp = client.get("/api/audit-logs", headers=_auth_headers(role, _user_id(role)))
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Ownership: seed backfill, recheck, actor from token
# ---------------------------------------------------------------------------

class TestOwnership:
    def test_seeded_requests_belong_to_purchasing(self, seeded_db):
        from app import db as db_module

        purchasing_id = _user_id("purchasing")
        sess = db_module.SessionLocal()
        try:
            creators = set(sess.execute(
                select(Request.created_by_user_id).where(Request.raw_text.like("Past request%"))
            ).scalars())
        finally:
            sess.close()
        assert creators == {purchasing_id}

    def test_finance_cannot_recheck(self, seeded_db):
        resp = client.post(
            f"/api/request-items/{_seeded_item_id()}/recheck",
            headers=_auth_headers("finance", _user_id("finance")),
        )
        assert resp.status_code == 403

    def test_purchasing_cannot_recheck_other_users_request(self, seeded_db):
        owner_id = _user_id("owner")
        created = client.post(
            "/api/requests",
            json={"items": [{"line_no": 996, "raw_name": "Owner-entered item", "qty": 1, "unit": "pcs"}]},
            headers=_auth_headers("owner", owner_id),
        )
        assert created.status_code == 201
        item_id = created.json()[0]["id"]

        resp = client.post(
            f"/api/request-items/{item_id}/recheck",
            headers=_auth_headers("purchasing", _user_id("purchasing")),
        )
        assert resp.status_code == 403

    def test_approve_actor_comes_from_token_not_body(self, seeded_db):
        """A browser-supplied actor is ignored; the token user is recorded."""
        owner_id = _user_id("owner")
        item_id = _seeded_item_id()
        resp = client.post(
            f"/api/request-items/{item_id}/approve",
            json={"actor": "mallory"},
            headers=_auth_headers("owner", owner_id),
        )
        assert resp.status_code == 200
        actors = [a["actor"] for a in resp.json()["actions"] if a["action"] == "approve"]
        assert actors and actors[-1] == "owner"


# ---------------------------------------------------------------------------
# Login: rate limit and generic error
# ---------------------------------------------------------------------------

class TestLogin:
    def test_login_with_demo_password(self, seeded_db):
        from app.config import settings
        from app.security import limiter

        limiter.reset()
        resp = client.post("/api/auth/login", json={"username": "owner", "password": settings.DEMO_PASSWORD})
        assert resp.status_code == 200
        body = resp.json()
        assert body["role"] == "owner" and body["username"] == "owner"

    def test_unknown_user_and_wrong_password_share_one_message(self, seeded_db):
        from app.security import limiter

        limiter.reset()
        a = client.post("/api/auth/login", json={"username": "nobody", "password": "x"})
        b = client.post("/api/auth/login", json={"username": "owner", "password": "wrong"})
        assert a.status_code == b.status_code == 401
        assert a.json()["detail"] == b.json()["detail"]

    def test_login_rate_limited_after_5_per_minute(self, seeded_db):
        from app.security import limiter

        limiter.reset()
        codes = [
            client.post("/api/auth/login", json={"username": "owner", "password": "wrong"}).status_code
            for _ in range(6)
        ]
        limiter.reset()
        assert codes[:5] == [401] * 5
        assert codes[5] == 429
