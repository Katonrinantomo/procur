"""
M19 decision log tests.

Covers:
  - validate_decision / is_override / build_snapshot / decisions_csv / review_sort_key
  - approve/return 422 cases (reason and outcome tag on overrides)
  - snapshot contents written at decision time
  - GET /api/decisions filters and roles, GET /api/decisions.csv columns
  - GET /api/review ordering and entered-by
  - the decision log is append-only: ORM guard, and no route issues UPDATE or
    DELETE on audit_log
  - the migration backfills pre-M19 rows
"""
from __future__ import annotations

import csv
import importlib.util
import io
import os
import pathlib
import re
from datetime import datetime, timedelta, timezone

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_procur.db")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-procur-ai-tests-32chars!!")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    Action,
    AuditLog,
    AuditLogImmutableError,
    Flag,
    Request,
    RequestItem,
    User,
)
from app.security import create_access_token, limiter  # noqa: E402
from app.services.decisions import (  # noqa: E402
    CSV_COLUMNS,
    DecisionError,
    build_snapshot,
    decisions_csv,
    is_override,
    review_sort_key,
    validate_decision,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def _no_web_check(monkeypatch):
    """Test rows are unknown items; skip the web path so no Langflow retries run."""
    monkeypatch.setattr("app.services.checker.get_web_quotes", lambda raw_name, session: ([], None))


def _user_id(role: str) -> int:
    from app import db as db_module

    sess = db_module.SessionLocal()
    try:
        return sess.execute(select(User).where(User.role == role)).scalar_one().id
    finally:
        sess.close()


def _headers(role: str) -> dict:
    return {"Authorization": f"Bearer {create_access_token(_user_id(role), role)}"}


_line_no = iter(range(5000, 6000))


def _new_row(*, status: str = "checked", risk_score: int = 0, flags: tuple[str, ...] = ()) -> int:
    """A fresh row entered by purchasing, with its check result set directly."""
    resp = client.post(
        "/api/requests",
        json={"items": [{
            "line_no": next(_line_no),
            "raw_name": "M19 test item",
            "qty": 4,
            "unit": "pcs",
            "quoted_unit_price_idr": 125_000,
        }]},
        headers=_headers("purchasing"),
    )
    assert resp.status_code == 201, resp.text
    item_id = resp.json()[0]["id"]

    from app import db as db_module

    sess = db_module.SessionLocal()
    try:
        ri = sess.get(RequestItem, item_id)
        sess.query(Flag).filter(Flag.request_item_id == item_id).delete()
        ri.status = status
        ri.risk_score = risk_score
        ri.reference_unit_price_idr = 100_000
        ri.diff_pct = 25.0
        ri.checked_via = "history"
        ri.history_count = 3
        for code in flags:
            sess.add(Flag(request_item_id=item_id, code=code, message=f"{code} message"))
        sess.commit()
    finally:
        sess.close()
    return item_id


def _approve(item_id: int, body: dict | None = None):
    return client.post(
        f"/api/request-items/{item_id}/approve", json=body or {}, headers=_headers("owner")
    )


def _return(item_id: int, body: dict):
    return client.post(
        f"/api/request-items/{item_id}/return", json=body, headers=_headers("owner")
    )


def _log_rows(item_id: int) -> list[AuditLog]:
    from app import db as db_module

    sess = db_module.SessionLocal()
    try:
        rows = list(sess.execute(
            select(AuditLog).where(AuditLog.subject_type == "request_item", AuditLog.subject_id == item_id)
        ).scalars())
        sess.expunge_all()
        return rows
    finally:
        sess.close()


# ---------------------------------------------------------------------------
# Pure rules
# ---------------------------------------------------------------------------

class TestRules:
    def test_is_override(self):
        assert is_override([], 0, "checked") is False
        assert is_override(["PRICE_ABOVE_REF"], 0, "checked") is True
        assert is_override([], 0, "flagged") is True
        assert is_override([], settings.OVERRIDE_RISK_SCORE, "checked") is True
        assert is_override([], settings.OVERRIDE_RISK_SCORE - 1, "checked") is False

    def test_return_needs_reason(self):
        with pytest.raises(DecisionError):
            validate_decision("return", False, None, None)
        with pytest.raises(DecisionError):
            validate_decision("return", False, "   ", None)
        assert validate_decision("return", False, "  too pricey ", None) == ("too pricey", None)

    def test_return_rejects_outcome_tag(self):
        with pytest.raises(DecisionError):
            validate_decision("return", False, "why", "false_alarm")

    def test_override_needs_reason_and_tag(self):
        with pytest.raises(DecisionError):
            validate_decision("approve", True, None, "false_alarm")
        with pytest.raises(DecisionError):
            validate_decision("approve", True, "ok", None)
        with pytest.raises(DecisionError):
            validate_decision("approve", True, "ok", "maybe")
        assert validate_decision("approve", True, "ok", "risk_accepted") == ("ok", "risk_accepted")

    def test_plain_approve(self):
        assert validate_decision("approve", False, None, None) == (None, None)
        assert validate_decision("approve", False, " fine ", None) == ("fine", None)
        with pytest.raises(DecisionError):
            validate_decision("approve", False, None, "false_alarm")

    def test_unknown_decision(self):
        with pytest.raises(DecisionError):
            validate_decision("pay", False, "x", None)

    def test_build_snapshot(self):
        ri = RequestItem(
            status="flagged", risk_score=62, quoted_unit_price_idr=130_000,
            reference_unit_price_idr=100_000, checked_via="web", history_count=None, diff_pct=30.0,
        )
        flags = [Flag(code="PRICE_ABOVE_REF", message="Price 30% above reference")]
        assert build_snapshot(ri, flags) == {
            "status": "flagged",
            "flags": [{"code": "PRICE_ABOVE_REF", "message": "Price 30% above reference"}],
            "risk_score": 62,
            "quoted_unit_price_idr": 130_000,
            "reference_unit_price_idr": 100_000,
            "reference_source": "web",
            "history_count": None,
            "diff_pct": 30.0,
        }

    def test_review_sort_key(self):
        t0 = datetime(2026, 10, 30, tzinfo=timezone.utc)
        t1 = t0 + timedelta(hours=1)
        rows = [
            ("checked", 80, t0, 1),
            ("flagged", 10, t1, 2),
            ("new", 40, t0, 3),
            ("flagged", 70, t1, 4),
            ("checked", 80, t1, 0),
        ]
        ordered = sorted(rows, key=lambda r: review_sort_key(*r))
        assert [r[3] for r in ordered] == [4, 2, 1, 0, 3]

    def test_decisions_csv(self):
        body = decisions_csv([{
            "id": 7,
            "created_at": datetime(2026, 10, 31, 3, 0, tzinfo=timezone.utc),
            "subject_type": "request_item",
            "subject_id": 42,
            "item_name": "Bearing 6205",
            "decision": "approve",
            "reason": "=HYPERLINK(\"x\")",
            "outcome_tag": "false_alarm",
            "username": "owner",
            "role": "owner",
            "snapshot": {
                "flags": [{"code": "PRICE_ABOVE_REF", "message": "m"}, {"code": "NEW_SUPPLIER", "message": "m"}],
                "risk_score": 55,
                "quoted_unit_price_idr": 120_000,
                "reference_unit_price_idr": 100_000,
                "reference_source": "history",
                "diff_pct": 20.0,
            },
        }])
        assert body.startswith("﻿")
        rows = list(csv.reader(io.StringIO(body.lstrip("﻿"))))
        assert rows[0] == CSV_COLUMNS
        rec = dict(zip(rows[0], rows[1]))
        assert rec["decided_at"] == "2026-10-31 10:00:00"  # Asia/Jakarta
        assert rec["reason"].startswith("'=")                # no formula injection
        assert rec["flags"] == "PRICE_ABOVE_REF;NEW_SUPPLIER"
        assert rec["reference_unit_price_idr"] == "100000"
        assert rec["outcome_tag"] == "false_alarm"


# ---------------------------------------------------------------------------
# Approve / return over HTTP
# ---------------------------------------------------------------------------

class TestDecisionEndpoints:
    def test_approve_flagged_without_reason_is_422(self, seeded_db):
        item_id = _new_row(status="flagged", risk_score=30, flags=("PRICE_ABOVE_REF",))
        assert _approve(item_id).status_code == 422
        assert _approve(item_id, {"reason": "ok"}).status_code == 422          # no tag
        assert _approve(item_id, {"outcome_tag": "false_alarm"}).status_code == 422  # no reason
        assert _approve(item_id, {"reason": "ok", "outcome_tag": "maybe"}).status_code == 422
        assert _log_rows(item_id) == []

    def test_approve_high_risk_without_reason_is_422(self, seeded_db):
        item_id = _new_row(status="checked", risk_score=settings.OVERRIDE_RISK_SCORE)
        assert _approve(item_id).status_code == 422
        resp = _approve(item_id, {"reason": "Urgent line stop", "outcome_tag": "risk_accepted"})
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "approved"

    def test_override_writes_one_row_with_snapshot(self, seeded_db):
        item_id = _new_row(status="flagged", risk_score=62, flags=("PRICE_ABOVE_REF", "NEW_SUPPLIER"))
        resp = _approve(item_id, {"reason": "Supplier price confirmed by phone", "outcome_tag": "false_alarm"})
        assert resp.status_code == 200, resp.text

        rows = _log_rows(item_id)
        assert len(rows) == 1
        log = rows[0]
        assert log.decision == "approve" and log.action == "approve"
        assert log.reason == "Supplier price confirmed by phone"
        assert log.outcome_tag == "false_alarm"
        assert log.role == "owner"
        assert log.user_id == _user_id("owner")
        assert log.subject_type == "request_item" and log.subject_id == item_id
        assert log.snapshot["status"] == "flagged"
        assert [f["code"] for f in log.snapshot["flags"]] == ["PRICE_ABOVE_REF", "NEW_SUPPLIER"]
        assert log.snapshot["risk_score"] == 62
        assert log.snapshot["reference_unit_price_idr"] == 100_000
        assert log.snapshot["reference_source"] == "history"

        history = resp.json()["decisions"]
        assert len(history) == 1
        assert history[0]["username"] == "owner"
        assert history[0]["reason"] == "Supplier price confirmed by phone"
        assert history[0]["snapshot"]["risk_score"] == 62

    def test_plain_approve_needs_no_reason(self, seeded_db):
        item_id = _new_row(status="checked", risk_score=0)
        detail = client.get(f"/api/request-items/{item_id}", headers=_headers("owner")).json()
        assert detail["override_required"] is False
        assert detail["entered_by"] == "purchasing"

        assert _approve(item_id, {"outcome_tag": "false_alarm"}).status_code == 422
        resp = _approve(item_id)
        assert resp.status_code == 200
        assert _log_rows(item_id)[0].reason is None

    def test_override_required_in_detail(self, seeded_db):
        item_id = _new_row(status="flagged", risk_score=20, flags=("QTY_UNUSUAL",))
        detail = client.get(f"/api/request-items/{item_id}", headers=_headers("owner")).json()
        assert detail["override_required"] is True

    def test_return_needs_reason(self, seeded_db):
        item_id = _new_row(status="flagged", flags=("PRICE_ABOVE_REF",))
        assert _return(item_id, {}).status_code == 422
        assert _return(item_id, {"reason": "   "}).status_code == 422
        assert _return(item_id, {"reason": "x", "outcome_tag": "false_alarm"}).status_code == 422
        resp = _return(item_id, {"reason": "Ask for a second quote"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "returned"
        log = _log_rows(item_id)[0]
        assert log.decision == "return" and log.reason == "Ask for a second quote"
        assert log.snapshot["flags"][0]["code"] == "PRICE_ABOVE_REF"

    def test_return_accepts_legacy_note(self, seeded_db):
        item_id = _new_row()
        resp = _return(item_id, {"note": "Wrong unit"})
        assert resp.status_code == 200
        assert _log_rows(item_id)[0].reason == "Wrong unit"

    def test_action_actor_not_written(self, seeded_db):
        item_id = _new_row()
        assert _approve(item_id).status_code == 200
        from app import db as db_module

        sess = db_module.SessionLocal()
        try:
            actions = list(sess.execute(select(Action).where(Action.request_item_id == item_id)).scalars())
        finally:
            sess.close()
        assert actions and all(a.actor is None for a in actions)


# ---------------------------------------------------------------------------
# GET /api/decisions, /api/decisions.csv
# ---------------------------------------------------------------------------

class TestDecisionsList:
    def test_roles(self, seeded_db):
        assert client.get("/api/decisions", headers=_headers("purchasing")).status_code == 403
        assert client.get("/api/decisions.csv", headers=_headers("purchasing")).status_code == 403
        for role in ("owner", "finance"):
            assert client.get("/api/decisions", headers=_headers(role)).status_code == 200

    def test_filters(self, seeded_db):
        item_id = _new_row()
        assert _return(item_id, {"reason": "filter test"}).status_code == 200
        today = datetime.now(timezone(timedelta(hours=7))).date()

        rows = client.get(
            f"/api/decisions?from={today}&to={today}&subject_type=request_item", headers=_headers("owner")
        ).json()
        assert any(r["subject_id"] == item_id and r["reason"] == "filter test" for r in rows)
        assert all(r["subject_type"] == "request_item" for r in rows)

        yesterday = today - timedelta(days=1)
        old = client.get(f"/api/decisions?to={yesterday}", headers=_headers("owner")).json()
        assert all(r["subject_id"] != item_id for r in old)

        assert client.get("/api/decisions?subject_type=bundle", headers=_headers("owner")).json() == []
        assert client.get("/api/decisions?subject_type=nope", headers=_headers("owner")).status_code == 422
        assert client.get(
            f"/api/decisions?from={today}&to={yesterday}", headers=_headers("owner")
        ).status_code == 422

    def test_csv_columns(self, seeded_db):
        item_id = _new_row(status="flagged", risk_score=70, flags=("STOCK_COVER_HIGH",))
        assert _approve(item_id, {"reason": "Stock count was wrong", "outcome_tag": "false_alarm"}).status_code == 200

        resp = client.get("/api/decisions.csv", headers=_headers("finance"))
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/csv")
        assert "attachment" in resp.headers["content-disposition"]
        text = resp.content.decode("utf-8")
        assert text.startswith("﻿")
        rows = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
        assert rows[0] == CSV_COLUMNS
        recs = [dict(zip(rows[0], r)) for r in rows[1:]]
        rec = next(r for r in recs if r["subject_id"] == str(item_id))
        assert rec["decision"] == "approve"
        assert rec["outcome_tag"] == "false_alarm"
        assert rec["decided_by"] == "owner"
        assert rec["risk_score"] == "70"
        assert rec["flags"] == "STOCK_COVER_HIGH"
        assert rec["reference_source"] == "history"


# ---------------------------------------------------------------------------
# GET /api/review
# ---------------------------------------------------------------------------

class TestReview:
    def test_owner_only(self, seeded_db):
        assert client.get("/api/review", headers=_headers("purchasing")).status_code == 403
        assert client.get("/api/review", headers=_headers("finance")).status_code == 403

    def test_order_and_entered_by(self, seeded_db):
        low = _new_row(status="flagged", risk_score=5, flags=("QTY_UNUSUAL",))
        high = _new_row(status="checked", risk_score=95)
        rows = client.get("/api/review", headers=_headers("owner")).json()["rows"]
        assert rows
        assert all(r["status"] in ("flagged", "new", "checked") for r in rows)

        statuses = [r["status"] for r in rows]
        n_flagged = statuses.count("flagged")
        assert all(s == "flagged" for s in statuses[:n_flagged])
        for group in (rows[:n_flagged], rows[n_flagged:]):
            risks = [r["risk_score"] for r in group]
            assert risks == sorted(risks, reverse=True)

        ids = [r["id"] for r in rows]
        assert ids.index(low) < ids.index(high)  # flagged beats higher risk
        assert next(r for r in rows if r["id"] == high)["entered_by"] == "purchasing"


# ---------------------------------------------------------------------------
# Append-only
# ---------------------------------------------------------------------------

_AUDIT_WRITE = re.compile(r"^\s*(UPDATE\s+\"?audit_log\"?|DELETE\s+FROM\s+\"?audit_log\"?)\b", re.I)


def _api_routes(routes):
    """APIRoutes, including those behind FastAPI's included-router wrappers."""
    from fastapi.routing import APIRoute

    out = []
    for route in routes:
        if isinstance(route, APIRoute):
            out.append(route)
        elif hasattr(route, "original_router") and hasattr(route.original_router, "routes"):
            out.extend(_api_routes(route.original_router.routes))
    return out


class TestAppendOnly:
    def test_orm_update_is_blocked(self, seeded_db):
        item_id = _new_row()
        assert _approve(item_id).status_code == 200
        from app import db as db_module

        sess = db_module.SessionLocal()
        try:
            log = sess.execute(select(AuditLog).where(AuditLog.subject_id == item_id)).scalars().first()
            log.reason = "rewritten"
            with pytest.raises(AuditLogImmutableError):
                sess.flush()
            sess.rollback()

            log = sess.execute(select(AuditLog).where(AuditLog.subject_id == item_id)).scalars().first()
            sess.delete(log)
            with pytest.raises(AuditLogImmutableError):
                sess.flush()
            sess.rollback()
        finally:
            sess.close()
        assert _log_rows(item_id)[0].reason is None

    def test_no_route_updates_or_deletes_audit_log(self, seeded_db, monkeypatch):
        """
        Call every route, as every role, with path params pointing at a row
        that already has a decision, and record every SQL statement. None may
        be an UPDATE or DELETE on audit_log.
        """
        import httpx
        from sqlalchemy import event

        from app import db as db_module

        async def _offline(*args, **kwargs):
            raise httpx.ConnectError("offline in tests")

        monkeypatch.setattr(httpx.AsyncClient, "send", _offline)
        monkeypatch.setattr(limiter, "enabled", False)

        decided = _new_row(status="flagged", flags=("PRICE_ABOVE_REF",))
        assert _return(decided, {"reason": "seed a decision"}).status_code == 200

        seen: list[str] = []

        def _record(conn, cursor, statement, params, context, executemany):
            seen.append(statement)

        event.listen(db_module.engine, "before_cursor_execute", _record)
        called = 0
        try:
            for route in _api_routes(app.routes):
                path = re.sub(r"\{[^}]+\}", str(decided), route.path)
                for method in route.methods - {"HEAD", "OPTIONS"}:
                    for role in ("purchasing", "owner", "finance"):
                        client.request(method, path, json={}, headers=_headers(role))
                        called += 1
            # Decision routes again with valid bodies, on the decided row.
            for body in ({"reason": "again"}, {"reason": "again", "outcome_tag": "false_alarm"}):
                _approve(decided, body)
                _return(decided, body)
            client.post(f"/api/request-items/{decided}/recheck", headers=_headers("owner"))
        finally:
            event.remove(db_module.engine, "before_cursor_execute", _record)

        assert called > 30
        offenders = [s for s in seen if _AUDIT_WRITE.search(s)]
        assert offenders == []
        assert _log_rows(decided), "the decision must still be there"

    def test_no_source_outside_seed_writes_audit_log(self):
        """Only the seed CLI's wipe may clear audit_log; no route module or service does."""
        app_dir = pathlib.Path(__file__).resolve().parents[1] / "app"
        pattern = re.compile(
            r"(UPDATE\s+\"?audit_log|DELETE\s+FROM\s+\"?audit_log|update\(\s*AuditLog|delete\(\s*AuditLog)",
            re.I,
        )
        hits = [
            str(p.relative_to(app_dir))
            for p in app_dir.rglob("*.py")
            if p.name != "seed.py" and pattern.search(p.read_text(encoding="utf-8"))
        ]
        assert hits == []


# ---------------------------------------------------------------------------
# Migration backfill
# ---------------------------------------------------------------------------

def test_migration_backfills_existing_rows(tmp_path):
    """Run the M19 upgrade on a pre-M19 audit_log and check the backfill."""
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'm19.db'}")
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE users (id INTEGER PRIMARY KEY, role VARCHAR(20))"))
        conn.execute(sa.text(
            "CREATE TABLE audit_log (id INTEGER PRIMARY KEY, request_item_id INTEGER, user_id INTEGER, "
            "action VARCHAR(50) NOT NULL, note TEXT, created_at DATETIME NOT NULL)"
        ))
        conn.execute(sa.text("INSERT INTO users VALUES (2, 'owner')"))
        conn.execute(sa.text(
            "INSERT INTO audit_log VALUES (1, 11, 2, 'approve', NULL, '2026-10-30 10:00:00'), "
            "(2, 12, 2, 'return', 'too expensive', '2026-10-30 11:00:00')"
        ))

    path = pathlib.Path(__file__).resolve().parents[1] / "alembic" / "versions" / "d8e9f0a1b2c3_decision_log_columns.py"
    spec = importlib.util.spec_from_file_location("m19_migration", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            mod.upgrade()

    with engine.connect() as conn:
        rows = conn.execute(sa.text(
            "SELECT id, subject_type, subject_id, decision, reason, role, outcome_tag, snapshot "
            "FROM audit_log ORDER BY id"
        )).all()
    assert [tuple(r) for r in rows] == [
        (1, "request_item", 11, "approve", None, "owner", None, None),
        (2, "request_item", 12, "return", "too expensive", "owner", None, None),
    ]
