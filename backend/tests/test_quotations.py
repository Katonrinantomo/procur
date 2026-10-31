"""
Tests for the vendor quotation check (M18): upload, extraction, evidence
guards, Python-computed band/recommendation/score, and to-queue.

maker_agent is mocked (app.services.quotation.call_maker); nothing calls
Langflow.
"""
from __future__ import annotations

import io
import os
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_procur.db")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-procur-ai-tests-32chars!!")

from fastapi.testclient import TestClient  # noqa: E402

from app.flows.contracts import MakerOut  # noqa: E402
from app.main import app  # noqa: E402
from app.security import create_access_token, limiter  # noqa: E402
from app.services.evidence import SerperResult  # noqa: E402
from app.services.langflow_client import LangflowError  # noqa: E402
from app.services.quotation import extract_text  # noqa: E402

client = TestClient(app)

TOKO = "https://www.tokopedia.com/toko/sarung-tangan-nitril-biru"
SHOPEE = "https://shopee.co.id/sarung-tangan-nitril-biru-i.1.2"
LAZADA = "https://www.lazada.co.id/products/sarung-tangan-nitril-biru-i3.html"
FAKE = "https://www.tokopedia.com/made-up/sarung-nitril"


def _headers(role: str = "purchasing", user_id: int = 1) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user_id, role)}"}


@pytest.fixture(autouse=True)
def _reset_limiter():
    limiter.reset()
    yield
    limiter.reset()


def _pdf_bytes(text_lines: list[str]) -> bytes:
    """A minimal one-page PDF with a real text layer."""
    content = "BT /F1 11 Tf 50 750 Td 14 TL " + " ".join(
        "(" + line.replace("(", r"\(").replace(")", r"\)") + ") '" for line in text_lines
    ) + " ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{i} 0 obj\n{obj}\nendobj\n".encode("latin-1"))
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return out.getvalue()


def _xlsx_bytes() -> bytes:
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["No", "Barang", "Qty", "Harga", "Total"])
    ws.append([1, "Sarung tangan nitril biru", 10, 520000, 5200000])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


PDF = _pdf_bytes(["PENAWARAN HARGA Q-001", "1. Sarung tangan nitril biru 10 box @ Rp 520.000"])

# Three real listings for the web reference, one fabricated, one off-item.
SERPER = [
    SerperResult(url=TOKO, title="Sarung Tangan Nitril Biru Rp480.000", snippet=""),
    SerperResult(url=SHOPEE, title="Sarung tangan nitril biru", snippet="Harga Rp 500.000 per yard"),
    SerperResult(url=LAZADA, title="Nitril biru premium 520rb", snippet=""),
]


def _maker(extra_item_fields: dict | None = None, quote_total: int | None = 5_200_000) -> MakerOut:
    item = {
        "line_no": 1,
        "name": "Sarung tangan nitril biru",
        "qty": 10,
        "unit": "box",
        "unit_price_idr": 520_000,
        "line_total_idr": 5_200_000,
        "search_query": "harga sarung tangan nitril biru",
        "listings": [
            {"title": "Sarung Tangan Nitril Biru", "url": TOKO, "price_idr": 480_000, "matches_item": True},
            {"title": "Sarung tangan nitril biru", "url": SHOPEE, "price_idr": 500_000, "matches_item": True},
            {"title": "Nitril biru premium", "url": LAZADA, "price_idr": 520_000, "matches_item": True},
            {"title": "Made up", "url": FAKE, "price_idr": 100_000, "matches_item": True},
        ],
        **(extra_item_fields or {}),
    }
    return MakerOut.model_validate({
        "mode": "QUOTE",
        "vendor": {"name": "CV Nitril Jaya", "quote_no": "Q-001", "date": "2026-10-30"},
        "items": [item],
        "quote_total_idr": quote_total,
    })


def _upload(content: bytes = PDF, name: str = "q.pdf", maker: MakerOut | None = None, role="purchasing"):
    with patch(
        "app.services.quotation.call_maker",
        new=AsyncMock(return_value=(maker or _maker(), SERPER)),
    ):
        return client.post(
            "/api/quotations",
            files={"file": (name, content, "application/octet-stream")},
            headers=_headers(role, {"purchasing": 1, "owner": 2, "finance": 3}[role]),
        )


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

class TestExtractText:
    def test_pdf_text_layer(self):
        assert "Sarung tangan nitril biru" in extract_text(PDF, "pdf")

    def test_xlsx_rows(self):
        text = extract_text(_xlsx_bytes(), "xlsx")
        assert "Sarung tangan nitril biru | 10 | 520000 | 5200000" in text


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

class TestUpload:
    def test_pdf_checked_with_python_band_and_score(self, seeded_db):
        resp = _upload()
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["status"] == "checked"
        assert body["vendor_name"] == "CV Nitril Jaya"
        line = body["lines"][0]
        # Web median of the 3 kept quotes (480k, 500k, 520k) = 500k; +4.0%.
        assert line["reference_source"] == "web"
        assert line["reference_unit_price_idr"] == 500_000
        assert line["diff_pct"] == 4.0
        assert line["band"] == "WAJAR"
        assert line["recommendation"] == "SETUJU"
        # 0.8 * 85 + 20 (arithmetic recomputes)
        assert body["vendor_score"] == 88
        assert body["arithmetic_ok"] is True
        assert (body["covered_lines"], body["total_lines"]) == (1, 1)

    def test_fabricated_listing_dropped(self, seeded_db):
        body = _upload().json()
        line = body["lines"][0]
        assert {e["url"] for e in line["evidence"]} == {TOKO, SHOPEE, LAZADA}
        assert line["dropped"][0]["url"] == FAKE
        assert line["dropped"][0]["reason"] == "url_not_in_search"
        assert body["dropped_count"] == 1
        assert body["dropped_summary"] == {"tidak ada di hasil pencarian": 1}

    def test_model_extra_keys_cannot_set_band_or_score(self, seeded_db):
        maker = _maker()
        # Even if the model tried to send its own verdict, it is ignored.
        data = maker.model_dump()
        data["items"][0]["band"] = "KOMPETITIF"
        data["vendor_score"] = 100
        body = _upload(maker=MakerOut.model_validate(data)).json()
        assert body["lines"][0]["band"] == "WAJAR"
        assert body["vendor_score"] == 88

    def test_arithmetic_mismatch_lowers_score(self, seeded_db):
        body = _upload(maker=_maker(quote_total=5_300_000)).json()
        assert body["arithmetic_ok"] is False
        assert body["vendor_score"] == 68

    def test_xlsx_upload(self, seeded_db):
        resp = _upload(content=_xlsx_bytes(), name="q.xlsx")
        assert resp.status_code == 201
        assert resp.json()["status"] == "checked"

    def test_bad_extension_400(self, seeded_db):
        assert _upload(content=b"hello", name="q.txt").status_code == 400

    def test_bad_magic_400(self, seeded_db):
        assert _upload(content=b"not a pdf", name="q.pdf").status_code == 400

    def test_too_large_413(self, seeded_db):
        big = b"%PDF-" + b"0" * (10 * 1024 * 1024)
        assert _upload(content=big, name="q.pdf").status_code == 413

    @pytest.mark.parametrize("role", ["owner", "finance"])
    def test_other_roles_403(self, seeded_db, role):
        assert _upload(role=role).status_code == 403

    def test_pdf_without_text_unreadable(self, seeded_db):
        resp = _upload(content=_pdf_bytes([]), name="scan.pdf")
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "unreadable"
        assert "manual" in body["check_error"]

    def test_langflow_failure_leaves_pending(self, seeded_db):
        with patch(
            "app.services.quotation.call_maker",
            new=AsyncMock(side_effect=LangflowError("connection refused")),
        ):
            resp = client.post(
                "/api/quotations",
                files={"file": ("q.pdf", PDF, "application/pdf")},
                headers=_headers(),
            )
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "pending"
        assert body["check_error"]
        assert body["vendor_score"] is None


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

class TestRead:
    def test_get_and_list(self, seeded_db):
        qid = _upload().json()["id"]
        resp = client.get(f"/api/quotations/{qid}", headers=_headers("owner", 2))
        assert resp.status_code == 200
        assert resp.json()["lines"][0]["band"] == "WAJAR"
        listed = client.get("/api/quotations", headers=_headers("finance", 3)).json()
        assert listed[0]["id"] == qid

    def test_missing_404(self, seeded_db):
        assert client.get("/api/quotations/999999", headers=_headers()).status_code == 404


# ---------------------------------------------------------------------------
# To queue
# ---------------------------------------------------------------------------

class TestToQueue:
    def test_creates_rows_then_409(self, seeded_db):
        qid = _upload().json()["id"]
        resp = client.post(f"/api/quotations/{qid}/to-queue", headers=_headers())
        assert resp.status_code == 201, resp.text
        rows = resp.json()
        assert len(rows) == 1
        assert rows[0]["raw_name"] == "Sarung tangan nitril biru"
        assert rows[0]["quoted_unit_price_idr"] == 520_000
        # Re-check reuses the cached kept quotes: same web reference.
        assert rows[0]["reference_unit_price_idr"] == 500_000

        again = client.post(f"/api/quotations/{qid}/to-queue", headers=_headers())
        assert again.status_code == 409
        assert client.get(f"/api/quotations/{qid}", headers=_headers()).json()["status"] == "queued"

    def test_other_user_403(self, seeded_db):
        from app.models import User
        from app.security import hash_password
        from tests.conftest import _TestSession

        qid = _upload().json()["id"]
        with _TestSession() as s:
            user = s.query(User).filter_by(username="purchasing2").one_or_none()
            if user is None:
                user = User(username="purchasing2", hashed_password=hash_password("x"), role="purchasing")
                s.add(user)
                s.commit()
            other_id = user.id
        resp = client.post(f"/api/quotations/{qid}/to-queue", headers=_headers("purchasing", other_id))
        assert resp.status_code == 403

    def test_unchecked_422(self, seeded_db):
        qid = _upload(content=_pdf_bytes([]), name="scan.pdf").json()["id"]
        assert client.post(f"/api/quotations/{qid}/to-queue", headers=_headers()).status_code == 422


# ---------------------------------------------------------------------------
# MODE: ITEMS (web_check._call_flow) also goes through the guards
# ---------------------------------------------------------------------------

class TestItemsMode:
    def test_call_flow_returns_only_guarded_listings(self, monkeypatch):
        import json

        from app.config import settings
        from app.services import web_check

        monkeypatch.setattr(settings, "LANGFLOW_MAKER_FLOW_ID", "maker-test")
        maker = _maker().model_dump()
        maker["mode"] = "ITEMS"
        serper = json.dumps({"organic": [
            {"title": r.title, "link": r.url, "snippet": r.snippet} for r in SERPER
        ]})
        run = AsyncMock(return_value={"maker_json": json.dumps(maker), "serper_raw": serper})
        with patch("app.services.web_check.run_flow", new=run):
            offers = web_check._call_flow(web_check._flow_input("Sarung tangan nitril biru"))

        assert {o["url"] for o in offers} == {TOKO, SHOPEE, LAZADA}
        sent = run.call_args.args[1]
        assert sent.startswith("MODE: ITEMS\n<document>\n")

    def test_missing_serper_raw_drops_everything(self, monkeypatch):
        import json

        from app.config import settings
        from app.services import web_check

        monkeypatch.setattr(settings, "LANGFLOW_MAKER_FLOW_ID", "maker-test")
        run = AsyncMock(return_value={"maker_json": _maker().model_dump_json(), "other": "x"})
        with patch("app.services.web_check.run_flow", new=run):
            assert web_check._call_flow("MODE: ITEMS") == []
