"""
Live flow check — runs python -m app.flowcheck against the real Langflow.

Skipped by default; run with `pytest -m live`.
"""
from __future__ import annotations

import pytest

from app import flowcheck


@pytest.mark.live
@pytest.mark.asyncio
async def test_all_configured_flows_pass_their_fixtures():
    assert await flowcheck.main() == 0
