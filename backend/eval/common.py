"""
Shared helpers for the eval suites.

Importing this module points the app at a throwaway SQLite file BEFORE any
app module is imported, so no suite ever touches the dev database.  Langflow
settings still come from backend/.env.

seeded_session()  — a session on a freshly seeded throwaway DB (seed() with
                    --empty-today), built once per process.
offline_web()     — patches the checker so web quotes come from the seeded
                    cache only; the checker never calls Langflow during
                    E1b/E2, so those suites are deterministic and offline.
require_flow()    — raises SuiteSkipped when a flow ID is unset or Langflow
                    does not answer, so live suites skip instead of hanging.
load_rows()       — reads a JSON or CSV data file and its "example" marker.
"""
from __future__ import annotations

import asyncio
import contextlib
import csv
import io
import json
import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

EVAL_DIR = Path(__file__).resolve().parent
DATA_DIR = EVAL_DIR / "data"

_TMP_DIR = Path(tempfile.mkdtemp(prefix="procur_eval_"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP_DIR / 'eval.db').as_posix()}"
os.environ.setdefault("JWT_SECRET", "eval-only-secret-not-used-for-any-real-login")

import app.security as _security  # noqa: E402 — must come after the env override

# Demo users are created by seed(); they never log in during an eval.
_security._ITERATIONS = 1_000

from sqlalchemy.orm import Session  # noqa: E402

from app.config import settings  # noqa: E402


class SuiteSkipped(Exception):
    """A suite cannot run here (no data, no flow, Langflow down)."""


def skipped(reason: str, **extra) -> dict:
    return {"status": "skipped", "reason": reason, **extra}


# ---------------------------------------------------------------------------
# Data files
# ---------------------------------------------------------------------------

def load_rows(path: Path) -> tuple[list[dict], bool]:
    """
    Return (rows, is_example).

    JSON files are {"_meta": {"example": bool, ...}, "rows": [...]}.
    CSV files may start with "#" comment lines; a comment containing
    "EXAMPLE" marks the file as example data.  Blank cells become None.
    """
    if not path.exists():
        raise SuiteSkipped(f"data file {path.relative_to(EVAL_DIR.parent)} does not exist")
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        doc = json.loads(text)
        return doc["rows"], bool(doc.get("_meta", {}).get("example"))

    comments = [ln for ln in text.splitlines() if ln.lstrip().startswith("#")]
    body = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
    rows = [
        {k.strip(): (v.strip() or None) if isinstance(v, str) else v for k, v in row.items()}
        for row in csv.DictReader(io.StringIO(body))
    ]
    return rows, any("EXAMPLE" in c for c in comments)


def data_label(path: Path, is_example: bool) -> str:
    rel = path.relative_to(EVAL_DIR.parent).as_posix()
    return f"{rel} (EXAMPLE DATA — not a measurement)" if is_example else rel


# ---------------------------------------------------------------------------
# Seeded throwaway database
# ---------------------------------------------------------------------------

_seeded = False


def seeded_session() -> Session:
    """Return a new session on the throwaway DB, seeding it on first use."""
    global _seeded
    from app.db import Base, SessionLocal, engine

    if not _seeded:
        import app.models  # noqa: F401 — register tables
        from app.seed import seed

        Base.metadata.create_all(bind=engine)
        with contextlib.redirect_stdout(io.StringIO()):
            seed(empty_today=True)
        _seeded = True
    return SessionLocal()


@contextlib.contextmanager
def offline_web() -> Iterator[None]:
    """Serve web quotes from the seeded cache only; never call Langflow."""
    from app.services import checker, web_check

    def cache_only(raw_name: str, session: Session):
        return web_check._fetch_cached(web_check._cache_key(raw_name), session), None

    original = checker.get_web_quotes
    checker.get_web_quotes = cache_only
    try:
        yield
    finally:
        checker.get_web_quotes = original


def supplier_id_for(name: str | None, session: Session) -> int | None:
    """Resolve a supplier name to its id, the way the request routers do."""
    from app.models import Supplier

    if not name:
        return None
    sup = session.query(Supplier).filter(Supplier.name == name).first()
    return sup.id if sup else None


def flag_codes(draft: dict, session: Session) -> set[str]:
    """Run one row through the checker (dry run, offline) and return its flag codes."""
    from app.services.checker import dry_check_item

    result = dry_check_item(
        {
            "raw_name": draft["name"],
            "qty": draft.get("qty"),
            "unit": draft.get("unit"),
            "quoted_unit_price_idr": draft.get("quoted_unit_price_idr"),
            "quoting_supplier_name": draft.get("supplier"),
            "supplier_id": supplier_id_for(draft.get("supplier"), session),
        },
        session,
    )
    return {f["code"] for f in result["flags"]}


# ---------------------------------------------------------------------------
# Live flows
# ---------------------------------------------------------------------------

def require_flow(setting_name: str) -> None:
    """Raise SuiteSkipped unless the flow ID is set and Langflow answers."""
    from app.services.langflow_client import ping

    if not getattr(settings, setting_name):
        raise SuiteSkipped(f"{setting_name} is not set in backend/.env")
    if not asyncio.run(ping(timeout=3)):
        raise SuiteSkipped(f"Langflow is not reachable at {settings.LANGFLOW_URL}")


def pct(num: int | float, den: int | float) -> float | None:
    return round(num / den * 100, 1) if den else None
