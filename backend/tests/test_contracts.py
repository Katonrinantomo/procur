"""
Tests for app/flows/contracts.py — output models and parse_flow_json.
"""
from __future__ import annotations

import copy
import json

import pytest
from pydantic import ValidationError

from app.flows.contracts import (
    CheckerOut,
    FlowContractError,
    MakerOut,
    NarratorOut,
    OrganizeOut,
    WebCheckOut,
    parse_flow_json,
    parse_flow_json_once,
    strip_fences,
)
from app.services.langflow_client import LangflowError

MAKER = {
    "mode": "QUOTE",
    "vendor": {"name": "CV Sinar Pelumas", "quote_no": "Q-12", "date": "2026-10-30"},
    "items": [{
        "line_no": 1, "name": "Hydraulic oil ISO VG 46, 20L", "qty": 4, "unit": "drum",
        "unit_price_idr": 1450000, "line_total_idr": 5800000,
        "search_query": "oli hidrolik iso vg 46 20l",
        "listings": [{"title": "Oli VG46 20L", "url": "https://www.tokopedia.com/x/y",
                      "seller": "Toko A", "price_idr": 1395000,
                      "matches_item": True, "mismatch_reason": None}],
    }],
    "quote_total_idr": 5800000,
}

LINE = {"name": "Bearing 6205 ZZ", "qty": 20, "unit": "pcs", "unit_price_idr": 38500, "line_total_idr": 770000}

CHECKER = {
    "po": {"doc_no": "PO-1", "date": "2026-10-01", "vendor_name": "PT A", "vendor_npwp": "[NPWP_1]",
           "lines": [LINE], "subtotal_idr": 770000, "total_idr": 854700,
           "approvals": [{"name": "Budi", "level": 1}]},
    "gr": {"doc_no": "GR-1", "date": "2026-10-03", "po_ref": "PO-1", "lines": [LINE]},
    "invoice": {"doc_no": "INV-1", "date": "2026-10-04", "po_ref": "PO-1", "vendor_npwp": "[NPWP_1]",
                "lines": [LINE], "subtotal_idr": 770000, "ppn_idr": 84700, "total_idr": 854700},
    "tax_invoice": {"faktur_no": "010.000-26.00000001", "faktur_code": "010", "date": "2026-10-04",
                    "seller_npwp": "[NPWP_1]", "buyer_npwp": "[NPWP_2]", "invoice_ref": "INV-1",
                    "harga_jual_idr": 770000, "dpp_idr": 705833, "ppn_idr": 84700},
}

NARRATOR = {"summary": "Two invoices share a number.", "patterns": ["duplicate invoice"],
            "actions": ["Hold payment", "Ask vendor", "Check GR"]}


@pytest.mark.parametrize("model, payload", [
    (OrganizeOut, {"items": [{"name": "Bearing 6205 ZZ", "qty": 20}]}),
    (WebCheckOut, [{"title": "Bearing", "url": "https://shopee.co.id/x", "seller": None, "price_idr": 38000}]),
    (MakerOut, MAKER),
    (CheckerOut, CHECKER),
    (NarratorOut, NARRATOR),
])
def test_models_accept_valid_payloads(model, payload):
    model.model_validate(payload)


def test_maker_rejects_unknown_mode():
    with pytest.raises(ValidationError):
        MakerOut.model_validate({**MAKER, "mode": "BOTH"})


def test_maker_rejects_fractional_price():
    bad = copy.deepcopy(MAKER)
    bad["items"][0]["unit_price_idr"] = 1450000.5
    with pytest.raises(ValidationError):
        MakerOut.model_validate(bad)


def test_web_check_rejects_non_list():
    with pytest.raises(ValidationError):
        WebCheckOut.model_validate({"title": "x"})


def test_narrator_rejects_too_few_actions():
    with pytest.raises(ValidationError):
        NarratorOut.model_validate({**NARRATOR, "actions": ["a", "b"]})


def test_narrator_rejects_too_many_actions():
    with pytest.raises(ValidationError):
        NarratorOut.model_validate({**NARRATOR, "actions": ["a", "b", "c", "d", "e", "f"]})


def test_narrator_rejects_long_summary():
    with pytest.raises(ValidationError):
        NarratorOut.model_validate({**NARRATOR, "summary": "x" * 601})


def test_strip_fences():
    assert strip_fences('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert strip_fences('  {"a": 1} ') == '{"a": 1}'


def test_parse_flow_json_once_with_fences():
    out = parse_flow_json_once('```json\n{"items": []}\n```', OrganizeOut)
    assert out.items == []


@pytest.mark.asyncio
async def test_parse_flow_json_valid_does_not_rerun():
    async def rerun(hint):
        raise AssertionError("rerun called")

    out = await parse_flow_json(json.dumps(NARRATOR), NarratorOut, rerun)
    assert out.actions == NARRATOR["actions"]


@pytest.mark.asyncio
async def test_parse_flow_json_repairs_once():
    hints: list[str] = []

    async def rerun(hint):
        hints.append(hint)
        return json.dumps(NARRATOR)

    out = await parse_flow_json("not json", NarratorOut, rerun)

    assert out.summary == NARRATOR["summary"]
    assert len(hints) == 1
    assert "Previous answer was invalid" in hints[0]


@pytest.mark.asyncio
async def test_parse_flow_json_second_failure_raises_contract_error():
    calls = {"n": 0}

    async def rerun(hint):
        calls["n"] += 1
        return '{"summary": "x"}'

    with pytest.raises(FlowContractError) as exc_info:
        await parse_flow_json("{}", NarratorOut, rerun)

    assert calls["n"] == 1
    # Callers that already handle LangflowError (502 / pending row) catch this too.
    assert isinstance(exc_info.value, LangflowError)
