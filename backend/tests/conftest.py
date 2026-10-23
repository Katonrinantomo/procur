"""
Shared pytest fixtures for backend tests.

Uses an in-memory SQLite database so tests run without PostgreSQL.
The full seed (including the check engine run) is executed once per test
session; each test gets its own session but shares the data.
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker

# Point the app at SQLite before importing anything that reads DATABASE_URL.
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_procur.db")

from app.db import Base  # noqa: E402 — must come after env override
from app.models import (  # noqa: E402
    Action,
    Flag,
    Item,
    Purchase,
    Request,
    RequestItem,
    Stock,
    Supplier,
    WebQuote,
)

# ---------------------------------------------------------------------------
# Engine and session factory pointing at a file-based SQLite test database.
# (File-based so that the same data persists across multiple sessions in the
# same test run; removed at the end of the session fixture.)
# ---------------------------------------------------------------------------
TEST_DB_URL = "sqlite:///./test_procur.db"
_engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
)
_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


@pytest.fixture(scope="session", autouse=True)
def seeded_db():
    """
    Create all tables, run the full seed (with today's rows), run the check
    engine, and hand control to the test session.  Drops the file afterward.
    """
    import app.db as db_module

    # Redirect the app's engine and session to our test database.
    db_module.engine = _engine
    db_module.SessionLocal = _TestSession

    # Create schema.
    Base.metadata.create_all(bind=_engine)

    # Run seed using the patched SessionLocal (no Langflow calls).
    from app.seed import seed
    seed(empty_today=False)

    yield

    # Teardown: drop all tables and remove the SQLite file.
    Base.metadata.drop_all(bind=_engine)
    _engine.dispose()
    import pathlib
    p = pathlib.Path("./test_procur.db")
    if p.exists():
        p.unlink()


@pytest.fixture()
def session(seeded_db):
    """Per-test read-only session (rolls back after each test)."""
    conn = _engine.connect()
    trans = conn.begin()
    sess = _TestSession(bind=conn)
    yield sess
    sess.close()
    trans.rollback()
    conn.close()
