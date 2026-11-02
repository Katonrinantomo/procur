"""
Structure checks on the committed Langflow exports (langflow/*.json).

These read the JSON files only; no Langflow server is involved.  They guard
the contract between Maker.json and services/maker.py: the backend reads three
Chat Outputs by display name, and pick_output() raises when a name is missing
from a multi-output flow, so a re-export that drops one breaks every web check
and vendor-quotation check.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.flows.contracts import EXTRACT_OUT, MAKER_OUT, SERPER_RAW_OUT

LANGFLOW_DIR = Path(__file__).resolve().parents[2] / "langflow"


@pytest.fixture(scope="module")
def maker_flow() -> dict:
    return json.loads((LANGFLOW_DIR / "Maker.json").read_text(encoding="utf-8"))["data"]


def _nodes_by_id(flow: dict) -> dict[str, dict]:
    return {n["id"]: n for n in flow["nodes"]}


def _display(node: dict) -> str:
    return node["data"]["node"].get("display_name", "")


def _chat_outputs(flow: dict) -> dict[str, dict]:
    """Chat Output display name -> node."""
    return {_display(n): n for n in flow["nodes"] if n["data"]["type"] == "ChatOutput"}


def _sources_into(flow: dict, target_id: str) -> list[str]:
    return [e["source"] for e in flow["edges"] if e["target"] == target_id]


class TestMakerExport:
    def test_has_exactly_the_three_named_outputs(self, maker_flow):
        names = [_display(n) for n in maker_flow["nodes"] if n["data"]["type"] == "ChatOutput"]
        assert sorted(names) == sorted([EXTRACT_OUT, MAKER_OUT, SERPER_RAW_OUT])

    def test_output_names_are_unique(self, maker_flow):
        names = [_display(n) for n in maker_flow["nodes"] if n["data"]["type"] == "ChatOutput"]
        assert len(names) == len(set(names))

    def test_extract_json_is_fed_by_the_extract_model(self, maker_flow):
        """extract_json must carry Language Model #1: the model that feeds Serper."""
        nodes = _nodes_by_id(maker_flow)
        serper_id = next(
            i for i, n in nodes.items() if n["data"]["type"] == "SerperMultiSearch"
        )
        extract_models = [
            s for s in _sources_into(maker_flow, serper_id)
            if nodes[s]["data"]["type"] == "LanguageModelComponent"
        ]
        assert len(extract_models) == 1

        outputs = _chat_outputs(maker_flow)
        assert _sources_into(maker_flow, outputs[EXTRACT_OUT]["id"]) == extract_models

    def test_maker_json_is_fed_by_the_evidence_model_not_the_extract_model(self, maker_flow):
        nodes = _nodes_by_id(maker_flow)
        outputs = _chat_outputs(maker_flow)
        extract_src = _sources_into(maker_flow, outputs[EXTRACT_OUT]["id"])
        maker_src = _sources_into(maker_flow, outputs[MAKER_OUT]["id"])
        assert len(maker_src) == 1
        assert nodes[maker_src[0]]["data"]["type"] == "LanguageModelComponent"
        assert maker_src != extract_src

    def test_every_edge_points_at_existing_nodes(self, maker_flow):
        ids = set(_nodes_by_id(maker_flow))
        for e in maker_flow["edges"]:
            assert e["source"] in ids and e["target"] in ids, e["id"]

    def test_ids_are_unique(self, maker_flow):
        node_ids = [n["id"] for n in maker_flow["nodes"]]
        edge_ids = [e["id"] for e in maker_flow["edges"]]
        assert len(node_ids) == len(set(node_ids))
        assert len(edge_ids) == len(set(edge_ids))
