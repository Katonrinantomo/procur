"""
E1 — Organize extraction accuracy (Langflow Flow 1), and E1b — error propagation.

Every eval/data/e1/*.txt message is sent through organizer.parse_text() and
compared with eval/data/e1/ground_truth.json.

E1 reports, per field (item, qty, unit, price, supplier, department), the
share of ground-truth rows the model got right.  A ground-truth row with no
matching prediction counts as wrong on every field.  Price is an exact match
on whole rupiah; "price exact" is also reported over the rows whose ground
truth has a price.  Rows missed = ground-truth rows with no prediction; rows
invented = predictions with no ground-truth row.

Predicted rows are paired with ground-truth rows by name similarity, then
leftovers in message order.  A ground-truth row may list "name_accept":
other names that also count as correct (e.g. an accepted translation).  Unit
and department are compared after lowercasing and a synonym map ("lusin" ==
"doz", "gudang" == "warehouse"); qty, price and None are exact.

E1b runs the parsed rows and the ground-truth rows through the checker (dry
run on the seeded throwaway DB, web quotes from the cache only) and counts
the flags that differ: those are wrong findings caused by misreading.

Needs Langflow running with LANGFLOW_ORGANIZE_FLOW_ID set in backend/.env;
skips with a message otherwise.
"""
from __future__ import annotations

import asyncio
import json
from difflib import SequenceMatcher

from eval.common import (
    DATA_DIR,
    SuiteSkipped,
    data_label,
    flag_codes,
    offline_web,
    pct,
    require_flow,
    seeded_session,
)

E1_DIR = DATA_DIR / "e1"
TRUTH_PATH = E1_DIR / "ground_truth.json"

# Report label -> LineItemDraft field.
FIELDS: dict[str, str] = {
    "item": "name",
    "qty": "qty",
    "unit": "unit",
    "price": "quoted_unit_price_idr",
    "supplier": "supplier",
    "department": "department",
}

# Synonym maps: lowercase variant -> canonical form. Applied to BOTH the LLM
# value and the ground-truth value, so either side may use any listed variant.
normalisasi_unit = {
    "lusin": "doz",
    "dozen": "doz",
    "dus": "box",
    "kotak": "box",
    "buah": "pcs",
    "pc": "pcs",
    "piece": "pcs",
    "pieces": "pcs",
}
normalisasi_dept = {
    "gudang": "warehouse",
    "produksi": "production",
    "pemeliharaan": "maintenance",
    "perawatan": "maintenance",
}
SYNONYMS_BY_FIELD = {"unit": normalisasi_unit, "department": normalisasi_dept}


def _norm(value: str | None) -> str:
    return " ".join(value.lower().split()) if isinstance(value, str) else ""


def normalize_value(field: str, value):
    """Lowercase a string value and map it through the field's synonym table."""
    if not isinstance(value, str):
        return value
    text = _norm(value)
    return SYNONYMS_BY_FIELD.get(field, {}).get(text, text)


def name_similarity(a: str | None, b: str | None) -> float:
    """1.0 if one normalized name contains the other, else difflib ratio."""
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return 0.0
    if na in nb or nb in na:
        return 1.0
    return SequenceMatcher(None, na, nb).ratio()


def best_name_score(exp: dict, name: str | None) -> float:
    """Best similarity to the ground-truth name or any of its name_accept variants."""
    return max(name_similarity(n, name) for n in [exp["name"], *exp.get("name_accept", [])])


def field_correct(field: str, expected, predicted: dict, exp_row: dict | None = None) -> bool:
    got = predicted.get(field)
    if field == "name":
        return best_name_score(exp_row or {"name": expected}, got) >= 0.8
    if isinstance(expected, str):
        return normalize_value(field, expected) == normalize_value(field, got)
    # ints and None: exact match (None expected means the model must not invent a value)
    return expected == got


def pair_items(expected: list[dict], predicted: list[dict]) -> list[dict | None]:
    """
    For each expected item, pick the unused predicted item with the best name
    match (similarity >= 0.5).  Rows still unpaired on both sides are then
    paired in message order, so a renamed or translated item counts as one
    row with a wrong item name, not as one row missed plus one invented.
    """
    used: set[int] = set()
    result: list[dict | None] = []
    for exp in expected:
        best_i, best_score = None, 0.0
        for i, pred in enumerate(predicted):
            if i in used:
                continue
            score = best_name_score(exp, pred.get("name"))
            if score > best_score:
                best_i, best_score = i, score
        if best_i is not None and best_score >= 0.5:
            used.add(best_i)
            result.append(predicted[best_i])
        else:
            result.append(None)
    leftovers = iter(i for i in range(len(predicted)) if i not in used)
    for k, pred in enumerate(result):
        if pred is None:
            i = next(leftovers, None)
            if i is None:
                break
            result[k] = predicted[i]
    return result


def score_message(expected: list[dict], predicted: list[dict]) -> dict:
    """Score one message: per-field correct counts, price exact, missed, invented."""
    pairs = pair_items(expected, predicted)
    correct = {label: 0 for label in FIELDS}
    price_rows = price_exact = 0
    mismatches: list[str] = []
    for exp, pred in zip(expected, pairs):
        has_price = exp["quoted_unit_price_idr"] is not None
        price_rows += has_price
        if pred is None:
            mismatches.append(f"missing row: {exp['name']!r}")
            continue
        for label, field in FIELDS.items():
            if field_correct(field, exp[field], pred, exp):
                correct[label] += 1
            else:
                mismatches.append(f"{exp['name']!r}.{label}: expected {exp[field]!r}, got {pred.get(field)!r}")
        if has_price and pred.get("quoted_unit_price_idr") == exp["quoted_unit_price_idr"]:
            price_exact += 1
    missed = sum(1 for p in pairs if p is None)
    invented = len(predicted) - (len(expected) - missed)
    if invented:
        mismatches.append(f"{invented} invented row(s) not in ground truth")
    return {
        "rows": len(expected),
        "correct": correct,
        "price_rows": price_rows,
        "price_exact": price_exact,
        "missed": missed,
        "invented": invented,
        "pairs": pairs,
        "mismatches": mismatches,
    }


def flag_diff(expected: list[dict], predicted: list[dict], pairs: list[dict | None], codes) -> dict:
    """
    E1b for one message.  *codes(row)* returns the checker's flag codes.

    Paired rows: flags gained (on parsed, not on truth) and lost (on truth,
    not on parsed).  A missed row loses all its truth flags; an invented row
    gains all its parsed flags.
    """
    gained = lost = rows_changed = 0
    changes: list[str] = []
    paired_ids = {id(p) for p in pairs if p is not None}
    for exp, pred in zip(expected, pairs):
        truth = codes(exp)
        parsed = codes(pred) if pred is not None else set()
        g, lo = parsed - truth, truth - parsed
        gained += len(g)
        lost += len(lo)
        if g or lo:
            rows_changed += 1
            changes.append(f"{exp['name']!r}: +{sorted(g)} -{sorted(lo)}")
    for pred in predicted:
        if id(pred) not in paired_ids:
            g = codes(pred)
            gained += len(g)
            if g:
                rows_changed += 1
                changes.append(f"invented {pred.get('name')!r}: +{sorted(g)}")
    return {"gained": gained, "lost": lost, "rows_changed": rows_changed, "changes": changes}


def run() -> dict:
    truth_doc = json.loads(TRUTH_PATH.read_text(encoding="utf-8"))
    truth: dict[str, dict] = truth_doc["messages"]
    example = bool(truth_doc.get("_meta", {}).get("example"))
    if not truth:
        raise SuiteSkipped("eval/data/e1/ground_truth.json has no messages")
    require_flow("LANGFLOW_ORGANIZE_FLOW_ID")

    from app.services.organizer import parse_text

    session = seeded_session()
    totals = {label: 0 for label in FIELDS}
    n_rows = price_rows = price_exact = missed = invented = errors = 0
    gained = lost = rows_changed = truth_flags = 0
    per_message: dict[str, dict] = {}
    try:
        with offline_web():
            for filename, spec in truth.items():
                text = (E1_DIR / filename).read_text(encoding="utf-8").strip()
                try:
                    predicted = [d.model_dump() for d in asyncio.run(parse_text(text))]
                except Exception as exc:  # noqa: BLE001 - report and continue with the next message
                    errors += 1
                    per_message[filename] = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
                    continue
                expected = spec["items"]
                s = score_message(expected, predicted)

                def codes(row: dict) -> set[str]:
                    return flag_codes(row, session)

                b = flag_diff(expected, predicted, s["pairs"], codes)
                truth_flags += sum(len(codes(e)) for e in expected)
                for label in FIELDS:
                    totals[label] += s["correct"][label]
                n_rows += s["rows"]
                price_rows += s["price_rows"]
                price_exact += s["price_exact"]
                missed += s["missed"]
                invented += s["invented"]
                gained += b["gained"]
                lost += b["lost"]
                rows_changed += b["rows_changed"]
                per_message[filename] = {
                    "status": "ok",
                    "parsed": predicted,
                    "mismatches": s["mismatches"],
                    "flag_changes": b["changes"],
                }
    finally:
        session.close()

    scored = len(truth) - errors
    if not scored:
        return {"status": "error", "reason": f"all {errors} message(s) failed in the Organize flow",
                "details": per_message}
    return {
        "status": "ok",
        "data": data_label(TRUTH_PATH, example),
        "summary": {
            "Messages scored": f"{scored}/{len(truth)}",
            "Ground-truth rows": n_rows,
            "Price exact match (rows with a price)": f"{pct(price_exact, price_rows)}% ({price_exact}/{price_rows})",
            "Rows missed": missed,
            "Rows invented": invented,
        },
        "tables": [
            {
                "title": "E1 accuracy per field (share of ground-truth rows)",
                "columns": ["Field", "Correct", "Rows", "Accuracy %"],
                "rows": [[label, totals[label], n_rows, pct(totals[label], n_rows)] for label in FIELDS],
            },
            {
                "title": "E1b flags that change because of misreading",
                "columns": ["Metric", "Value"],
                "rows": [
                    ["Flags on ground-truth rows", truth_flags],
                    ["Flags gained (parsed only)", gained],
                    ["Flags lost (ground truth only)", lost],
                    ["Rows whose flags changed", f"{rows_changed}/{n_rows}"],
                ],
            },
        ],
        "metrics": {
            "field_accuracy_pct": {label: pct(totals[label], n_rows) for label in FIELDS},
            "price_exact_pct": pct(price_exact, price_rows),
            "rows_missed": missed,
            "rows_invented": invented,
            "e1b": {"truth_flags": truth_flags, "flags_gained": gained, "flags_lost": lost,
                    "rows_changed": rows_changed},
        },
        "details": per_message,
    }
