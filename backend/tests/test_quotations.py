"""
Tests for the vendor quotation check (M18): upload, extraction, the
extract + evidence join, evidence guards, Python-computed band /
recommendation / score, and to-queue.

maker_agent's Langflow call is mocked (app.services.maker.run_flow) with
the flow's three outputs; nothing calls Langflow.
"""
from __future__ import annotations

import io
import json
import os
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite:///./test_procur.db")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-procur-ai-tests-32chars!!")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.security import create_access_token, limiter  # noqa: E402
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


@pytest.fixture(autouse=True)
def _maker_flow_id(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "LANGFLOW_MAKER_FLOW_ID", "maker-test")


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

# Serper Multi Search output for line 1: three real product results.
SERPER_RAW = json.dumps([{"line_no": 1, "search_query": "sarung tangan nitril biru", "error": None, "results": [
    {"title": "Sarung Tangan Nitril Biru Rp480.000", "link": TOKO, "page_type": "product",
     "snippet": "", "price": None},
    {"title": "Sarung tangan nitril biru", "link": SHOPEE, "page_type": "product",
     "snippet": "Harga Rp 500.000 per box", "price": None},
    {"title": "Nitril biru premium", "link": LAZADA, "page_type": "product",
     "snippet": "", "price": "520rb"},
]}])


def _extract(quote_total: int | None = 5_200_000) -> dict:
    return {
        "mode": "PENAWARAN",
        "vendor": {"name": "CV Nitril Jaya", "doc_number": "Q-001", "doc_date": "30-10-2026",
                   "payment_terms": None},
        "currency": "IDR",
        "items": [{
            "line_no": 1, "name_as_written": "Sarung tangan nitril biru", "brand": None,
            "spec": None, "qty": 10, "unit": "box", "unit_price": 520_000,
            "line_total": 5_200_000, "division": None,
            "search_query": "sarung tangan nitril biru",
        }],
        "document_total": quote_total,
        "extraction_notes": [],
    }


def _evidence() -> dict:
    def m(url, price, title):
        return {"url": url, "title": title, "marketplace": "tokopedia", "price": price,
                "price_text": None, "pack_qty": None, "match": "exact", "reason": "Sama"}
    return {"items": [{"line_no": 1, "note": None, "matches": [
        m(TOKO, 480_000, "Sarung Tangan Nitril Biru"),
        m(SHOPEE, 500_000, "Sarung tangan nitril biru"),
        m(LAZADA, 520_000, "Nitril biru premium"),
        m(FAKE, 100_000, "Made up"),
    ]}]}


def _outputs(extract: dict | None = None, evidence: dict | None = None, serper: str = SERPER_RAW) -> dict:
    return {
        "extract_json": json.dumps(extract or _extract()),
        "maker_json": json.dumps(evidence or _evidence()),
        "serper_raw": serper,
    }


def _post(content: bytes = PDF, name: str = "q.pdf", role: str = "purchasing"):
    return client.post(
        "/api/quotations",
        files={"file": (name, content, "application/octet-stream")},
        headers=_headers(role, {"purchasing": 1, "owner": 2, "finance": 3}[role]),
    )


def _upload(content: bytes = PDF, name: str = "q.pdf", outputs: dict | None = None, role="purchasing"):
    with patch("app.services.maker.run_flow", new=AsyncMock(return_value=outputs or _outputs())):
        return _post(content, name, role)


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

    def test_vendor_fields_and_date_parsed(self, seeded_db):
        body = _upload().json()
        assert (body["quote_no"], body["quote_date"]) == ("Q-001", "2026-10-30")
        assert body["quote_total_idr"] == 5_200_000

    def test_flow_input_format(self, seeded_db):
        run = AsyncMock(return_value=_outputs())
        with patch("app.services.maker.run_flow", new=run):
            _post(PDF, "q.pdf")
        assert run.call_args.args[1].startswith("MODE: PENAWARAN\nFILE: q.pdf\n---\n")

    def test_fabricated_listing_dropped(self, seeded_db):
        body = _upload().json()
        line = body["lines"][0]
        assert {e["url"] for e in line["evidence"]} == {TOKO, SHOPEE, LAZADA}
        assert line["dropped"][0]["url"] == FAKE
        assert line["dropped"][0]["reason"] == "url_not_in_search"
        assert body["dropped_count"] == 1
        assert body["dropped_summary"] == {"tidak ada di hasil pencarian": 1}

    def test_model_extra_keys_cannot_set_band_or_score(self, seeded_db):
        # Even if the model tried to send its own verdict, it is ignored.
        extract, evidence = _extract(), _evidence()
        extract["vendor_score"] = 100
        extract["items"][0]["band"] = "KOMPETITIF"
        evidence["items"][0]["recommendation"] = "SETUJU"
        body = _upload(outputs=_outputs(extract, evidence)).json()
        assert body["lines"][0]["band"] == "WAJAR"
        assert body["vendor_score"] == 88

    def test_pack_qty_divided_in_python(self, seeded_db):
        evidence = _evidence()
        # The Lazada listing is a pack of 10 boxes at 5.2 jt -> 520.000 per box.
        evidence["items"][0]["matches"][2].update(price=5_200_000, pack_qty=10)
        serper = SERPER_RAW.replace('"520rb"', '"Rp5.200.000"')
        line = _upload(outputs=_outputs(evidence=evidence, serper=serper)).json()["lines"][0]
        kept = {e["url"]: e for e in line["evidence"]}
        assert kept[LAZADA]["price_idr"] == 520_000
        assert (kept[LAZADA]["listing_price_idr"], kept[LAZADA]["pack_qty"]) == (5_200_000, 10)
        assert line["reference_unit_price_idr"] == 500_000

    def test_missing_serper_raw_gives_no_reference(self, seeded_db):
        line = _upload(outputs=_outputs(serper="")).json()["lines"][0]
        assert line["evidence"] == []
        assert line["reference_source"] == "none"
        assert line["band"] == "UNKNOWN"

    def test_repair_retry_then_checked(self, seeded_db):
        bad = {**_outputs(), "extract_json": "not json"}
        run = AsyncMock(side_effect=[bad, _outputs()])
        with patch("app.services.maker.run_flow", new=run):
            body = _post().json()
        assert body["status"] == "checked"
        assert run.call_count == 2
        assert "Previous answer was invalid" in run.call_args.args[1]

    def test_invalid_twice_leaves_pending(self, seeded_db):
        bad = {**_outputs(), "maker_json": '{"items": "x"}'}
        with patch("app.services.maker.run_flow", new=AsyncMock(return_value=bad)):
            body = _post().json()
        assert body["status"] == "pending"
        assert body["check_error"]

    def test_arithmetic_mismatch_lowers_score(self, seeded_db):
        body = _upload(outputs=_outputs(_extract(quote_total=5_300_000))).json()
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
            "app.services.maker.run_flow",
            new=AsyncMock(side_effect=LangflowError("connection refused")),
        ):
            resp = _post()
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
# Item names (web_check._call_flow, MODE: BON) also go through the guards
# ---------------------------------------------------------------------------

class TestItemsMode:
    def test_call_flow_returns_only_guarded_listings(self):
        from app.services import web_check

        run = AsyncMock(return_value=_outputs())
        with patch("app.services.maker.run_flow", new=run):
            offers = web_check._call_flow(web_check._flow_input("Sarung tangan nitril biru"))

        assert {o["url"] for o in offers} == {TOKO, SHOPEE, LAZADA}
        assert run.call_args.args[1].startswith("MODE: BON\nFILE: items.txt\n---\n1. ")

    def test_missing_serper_raw_drops_everything(self):
        from app.services import web_check

        outputs = {k: v for k, v in _outputs().items() if k != "serper_raw"}
        with patch("app.services.maker.run_flow", new=AsyncMock(return_value=outputs)):
            assert web_check._call_flow("MODE: BON") == []

    def test_quote_input_strips_newlines_from_filename(self):
        from app.services.maker import quote_input

        assert quote_input("a\nb.pdf", "TEXT") == "MODE: PENAWARAN\nFILE: a b.pdf\n---\nTEXT"
