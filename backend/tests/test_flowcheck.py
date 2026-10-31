"""
Tests for app.flowcheck with run_flow mocked — no live Langflow calls.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from app import flowcheck
from app.config import FLOW_ID_SETTINGS, settings

ORGANIZE_OK = json.dumps({"items": [{"name": "Bearing 6205 ZZ", "qty": 20}]})


@pytest.fixture
def only_organize(monkeypatch):
    """Configure the organize flow only."""
    for setting in FLOW_ID_SETTINGS.values():
        monkeypatch.setattr(settings, setting, "")
    monkeypatch.setattr(settings, "LANGFLOW_ORGANIZE_FLOW_ID", "organize-id")


@pytest.fixture
def fixtures_root(tmp_path):
    d = tmp_path / "fixtures" / "organize"
    d.mkdir(parents=True)
    (d / "01_clean.txt").write_text("bearing 20 pcs", encoding="utf-8")
    (d / "02_messy.txt").write_text("bearing 1/2 lusin", encoding="utf-8")
    return tmp_path / "fixtures"


@pytest.mark.asyncio
async def test_all_pass_exits_zero_and_writes_result(only_organize, fixtures_root, tmp_path, capsys):
    result_path = tmp_path / "last.json"
    with patch("app.flowcheck.run_flow", new=AsyncMock(return_value={"organize_json": ORGANIZE_OK})):
        code = await flowcheck.main(fixtures_root, result_path)

    assert code == 0
    data = json.loads(result_path.read_text(encoding="utf-8"))
    assert data["ok"] is True
    ran = [r for r in data["results"] if r["ok"] is not None]
    assert [r["fixture"] for r in ran] == ["01_clean.txt", "02_messy.txt"]
    skipped = {r["flow"] for r in data["results"] if r["ok"] is None}
    assert skipped == {"web_check", "maker", "checker", "narrator"}
    assert "PASS: 2/2" in capsys.readouterr().out


@pytest.mark.asyncio
async def test_bad_json_after_repair_exits_one(only_organize, fixtures_root, tmp_path):
    async def fake_run_flow(flow_id, text):
        if "lusin" in text:
            return {"organize_json": "not json"}
        return {"organize_json": ORGANIZE_OK}

    with patch("app.flowcheck.run_flow", new=fake_run_flow):
        code = await flowcheck.main(fixtures_root, tmp_path / "last.json")

    assert code == 1
    data = json.loads((tmp_path / "last.json").read_text(encoding="utf-8"))
    failed = [r["fixture"] for r in data["results"] if r["ok"] is False]
    assert failed == ["02_messy.txt"]


@pytest.mark.asyncio
async def test_repaired_fixture_passes_and_is_labelled(only_organize, fixtures_root):
    async def fake_run_flow(flow_id, text):
        if "Previous answer was invalid" in text:
            return {"organize_json": ORGANIZE_OK}
        return {"organize_json": "{}"}

    with patch("app.flowcheck.run_flow", new=fake_run_flow):
        results = await flowcheck.check_flows(fixtures_root)

    ran = [r for r in results if r.ok is not None]
    assert ran and all(r.ok for r in ran)
    assert all(r.error == "repaired" for r in ran)


@pytest.mark.asyncio
async def test_configured_flow_without_fixtures_fails(only_organize, tmp_path):
    with patch("app.flowcheck.run_flow", new=AsyncMock()) as mock_run:
        code = await flowcheck.main(tmp_path / "empty", tmp_path / "last.json")

    assert code == 1
    mock_run.assert_not_called()


@pytest.mark.asyncio
async def test_no_flow_configured_exits_one(monkeypatch, fixtures_root, tmp_path):
    for setting in FLOW_ID_SETTINGS.values():
        monkeypatch.setattr(settings, setting, "")

    with patch("app.flowcheck.run_flow", new=AsyncMock()) as mock_run:
        code = await flowcheck.main(fixtures_root, tmp_path / "last.json")

    assert code == 1
    mock_run.assert_not_called()


def test_repo_fixtures_exist_for_existing_flows():
    """Organize and Web Check each ship at least three fixtures."""
    for flow in ("organize", "web_check"):
        assert len(list((flowcheck.FIXTURES_ROOT / flow).glob("*.txt"))) >= 3
