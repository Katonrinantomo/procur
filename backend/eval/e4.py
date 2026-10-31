"""
E4 — name matching: does matcher.match_item() pick the right catalog item?

Each row of eval/data/e4_names.csv is a request name and the catalog item it
should match (expected_item blank = must not match anything, e.g. "valve").
Runs offline on the seeded throwaway DB.

    wrong match   = matched a different item, or matched when it should not
    missed match  = no match although a catalog item was expected
    wrong-match rate = wrong matches / rows   (missed matches reported apart:
                       a miss falls back to a web check, a wrong match uses
                       the wrong history)
"""
from __future__ import annotations

from eval.common import DATA_DIR, SuiteSkipped, data_label, load_rows, pct, seeded_session

NAMES_PATH = DATA_DIR / "e4_names.csv"


def classify(expected: str | None, got: str | None) -> str:
    """ok | wrong_item | false_match | missed."""
    if expected == got:
        return "ok"
    if got is None:
        return "missed"
    return "false_match" if expected is None else "wrong_item"


def run() -> dict:
    rows, example = load_rows(NAMES_PATH)
    if not rows:
        raise SuiteSkipped("eval/data/e4_names.csv has no rows")

    from app.models import Item
    from app.services.matcher import match_item

    session = seeded_session()
    try:
        catalog = {name for (name,) in session.query(Item.name)}
        unknown = {r["expected_item"] for r in rows if r["expected_item"]} - catalog
        if unknown:
            raise ValueError(f"expected_item not in the seeded catalog: {sorted(unknown)}")
        counts = {"ok": 0, "wrong_item": 0, "false_match": 0, "missed": 0}
        errors: list[list] = []
        for row in rows:
            item = match_item(row["request_name"], session)
            got = item.name if item else None
            kind = classify(row["expected_item"], got)
            counts[kind] += 1
            if kind != "ok":
                errors.append([row["request_name"], row["expected_item"] or "(no match)", got or "(no match)", kind])
    finally:
        session.close()

    n = len(rows)
    wrong = counts["wrong_item"] + counts["false_match"]
    return {
        "status": "ok",
        "data": data_label(NAMES_PATH, example),
        "summary": {
            "Names": n,
            "Wrong-match rate %": pct(wrong, n),
            "Wrong item": counts["wrong_item"],
            "Matched when it should not": counts["false_match"],
            "Missed match % (falls back to web)": pct(counts["missed"], n),
        },
        "tables": [{
            "title": "E4 rows that did not match as expected",
            "columns": ["Request name", "Expected", "Got", "Kind"],
            "rows": errors,
        }],
        "metrics": {"wrong_match_pct": pct(wrong, n), "missed_pct": pct(counts["missed"], n), **counts},
    }
