"""
Offline tests for the eval harness (backend/eval): the scoring functions,
the data loaders and the report writer.  No suite is run live here.
"""
from __future__ import annotations

import json
import os

import pytest

# eval.common points DATABASE_URL at a throwaway file for real eval runs;
# restore the test environment after importing it.
_saved_env = dict(os.environ)
from eval import common, e1, e2, e3, e4, run  # noqa: E402

os.environ.clear()
os.environ.update(_saved_env)


def _row(name, qty=1, unit="pcs", price=None, supplier=None, dept=None, **extra):
    return {"name": name, "qty": qty, "unit": unit, "quoted_unit_price_idr": price,
            "supplier": supplier, "department": dept, **extra}


# ---------------------------------------------------------------------------
# E1
# ---------------------------------------------------------------------------

def test_e1_normalize_value_uses_synonyms():
    assert e1.normalize_value("unit", " Lusin ") == "doz"
    assert e1.normalize_value("department", "Gudang") == "warehouse"
    assert e1.normalize_value("qty", 5) == 5


def test_e1_pair_items_by_name_then_order():
    expected = [_row("bearing 6205"), _row("sarung tangan katun")]
    predicted = [_row("Cotton gloves"), _row("Bearing 6205 ZZ")]
    pairs = e1.pair_items(expected, predicted)
    assert pairs[0]["name"] == "Bearing 6205 ZZ"
    # No name match: paired with the leftover row in message order.
    assert pairs[1]["name"] == "Cotton gloves"


def test_e1_name_accept_counts_as_correct():
    exp = _row("sarung tangan katun", name_accept=["cotton gloves"])
    assert e1.field_correct("name", exp["name"], _row("Cotton gloves"), exp)
    assert not e1.field_correct("name", "sarung tangan katun", _row("Cotton gloves"))


def test_e1_score_message_counts_fields_missed_invented():
    expected = [
        _row("oli", qty=4, unit="drum", price=1_450_000, supplier="CV Sinar", dept="produksi"),
        _row("masker", qty=200, price=None),
    ]
    predicted = [_row("oli", qty=4, unit="drum", price=1_450_000, supplier="CV Sinar", dept="Produksi")]
    s = e1.score_message(expected, predicted)
    assert s["correct"] == {f: 1 for f in e1.FIELDS}
    assert (s["missed"], s["invented"]) == (1, 0)
    assert (s["price_rows"], s["price_exact"]) == (1, 1)

    s = e1.score_message(expected[:1], predicted + [_row("x"), _row("y")])
    assert (s["missed"], s["invented"]) == (0, 2)


def test_e1_price_is_exact_match():
    expected = [_row("oli", price=1_450_000)]
    s = e1.score_message(expected, [_row("oli", price=1_449_999)])
    assert s["correct"]["price"] == 0
    assert s["price_exact"] == 0


def test_e1b_flag_diff_counts_gained_lost_and_unpaired():
    expected = [_row("a"), _row("b")]
    pa, extra = _row("a"), _row("z")
    flags = {"a": {"NEW_SUPPLIER"}, "b": {"QTY_UNUSUAL"}, "z": {"PRICE_ABOVE_REF"}}

    def codes(row):
        return flags[row["name"]] if row is not pa else {"PRICE_ABOVE_REF"}

    d = e1.flag_diff(expected, [pa, extra], [pa, None], codes)
    # a: +PRICE_ABOVE_REF -NEW_SUPPLIER; b missed: -QTY_UNUSUAL; z invented: +PRICE_ABOVE_REF
    assert (d["gained"], d["lost"], d["rows_changed"]) == (2, 2, 3)


# ---------------------------------------------------------------------------
# E2
# ---------------------------------------------------------------------------

def test_e2_confusion_per_flag():
    cm = e2.confusion([
        ({"PRICE_ABOVE_REF"}, {"PRICE_ABOVE_REF"}),
        ({"PRICE_ABOVE_REF"}, set()),
        (set(), {"PRICE_ABOVE_REF", "NEW_SUPPLIER"}),
        (set(), set()),
    ])
    assert cm["PRICE_ABOVE_REF"] == {"tp": 1, "fn": 1, "fp": 1, "tn": 1}
    assert cm["NEW_SUPPLIER"] == {"tp": 0, "fn": 0, "fp": 1, "tn": 3}


def test_e2_example_file_is_valid_and_marked():
    rows, example = common.load_rows(e2.ROWS_PATH)
    assert example is True
    assert rows and all(set(r["expected_flags"]) <= set(e2.FLAGS) for r in rows)


# ---------------------------------------------------------------------------
# E3
# ---------------------------------------------------------------------------

def test_e3_mape_and_error():
    assert e3.abs_pct_error(110, 100) == pytest.approx(10.0)
    assert e3.mape([(110, 100), (80, 100)]) == pytest.approx(15.0)
    assert e3.mape([]) is None


def test_e3_filled_rows_needs_price_date_and_url():
    rows = [
        {"item": "a", "manual_price_idr": "65.000", "checked_on": "2026-11-02", "source_url": "https://x"},
        {"item": "b", "manual_price_idr": "65000", "checked_on": None, "source_url": "https://x"},
    ]
    filled, unfilled = e3.filled_rows(rows)
    assert [r["manual_price_idr"] for r in filled] == [65_000]
    assert unfilled == ["b"]


def test_e3_example_file_has_no_invented_prices():
    rows, example = common.load_rows(e3.PRICES_PATH)
    assert example is True
    assert all(r["manual_price_idr"] is None for r in rows)
    with pytest.raises(common.SuiteSkipped, match="no hand-checked prices"):
        e3.run()


# ---------------------------------------------------------------------------
# E4
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("expected,got,kind", [
    ("Bearing 6205 ZZ", "Bearing 6205 ZZ", "ok"),
    (None, None, "ok"),
    ("Bearing 6205 ZZ", "Bearing 6206 ZZ", "wrong_item"),
    (None, "Bearing 6205 ZZ", "false_match"),
    ("Bearing 6205 ZZ", None, "missed"),
])
def test_e4_classify(expected, got, kind):
    assert e4.classify(expected, got) == kind


def test_e4_example_names_are_in_catalog():
    from app.seed import CATALOG

    rows, example = common.load_rows(e4.NAMES_PATH)
    assert example is True
    names = {c[0] for c in CATALOG}
    assert {r["expected_item"] for r in rows if r["expected_item"]} <= names


# ---------------------------------------------------------------------------
# Loader and runner
# ---------------------------------------------------------------------------

def test_load_rows_csv_comments_and_blanks(tmp_path):
    p = tmp_path / "x.csv"
    p.write_text("# EXAMPLE data\na,b\n1, \n", encoding="utf-8")
    assert common.load_rows(p) == ([{"a": "1", "b": None}], True)


def test_load_rows_missing_file_skips(tmp_path):
    with pytest.raises(common.SuiteSkipped):
        common.load_rows(common.EVAL_DIR / "data" / "nope.json")


def test_parse_suites():
    assert run.parse_suites("e1, E2") == ["E1", "E2"]
    with pytest.raises(SystemExit):
        run.parse_suites("E9")


def test_run_suite_reports_skips_and_errors(monkeypatch):
    assert run.run_suite("E5")["status"] == "skipped"

    def boom():
        raise RuntimeError("bad data")

    monkeypatch.setattr(e4, "run", boom)
    res = run.run_suite("E4")
    assert res["status"] == "error" and "bad data" in res["reason"]


def test_flow_models_reads_selected_model():
    flow = {"data": {"nodes": [{"data": {"node": {"template": {
        "model": {"value": [{"provider": "Anthropic", "name": "claude-haiku-5-5"}]}}}}}]}}
    assert run.flow_models(flow) == ["Anthropic: claude-haiku-5-5"]


def test_render_md_one_table_per_suite():
    meta = {"run_at": "2026-11-05T09:00:00+07:00", "git_commit": "abc", "flow_models": {"F.json": []},
            "flow_sha256": {"F.json": "0" * 64}}
    md = run.render_md(meta, {
        "E2": {"status": "ok", "data": "eval/data/e2_rows.json (EXAMPLE DATA — not a measurement)",
               "summary": {"Rows": 1}, "tables": [{"title": "T", "columns": ["a"], "rows": [["x|y"]]}]},
        "E3": {"status": "skipped", "reason": "no data"},
    })
    assert "## E2" in md and "## E3" in md and "skipped** — no data" in md
    assert "**eval/data/e2_rows.json (EXAMPLE DATA" in md
    assert "| x\\|y |" in md
    assert "0" * 64 in md
    json.dumps(meta)  # stamp stays JSON-serialisable
