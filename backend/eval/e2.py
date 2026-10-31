"""
E2 — request detection: do the four flags fire on the rows they should?

Each row of eval/data/e2_rows.json is a request line (name, qty, unit,
quoted price, supplier) with the flags a reviewer expects on it.  Rows go
through the checker (dry run on the seeded throwaway DB, web quotes from
the cache only), so this suite is offline and deterministic.

Per flag:
    detection rate       = rows where it fired and was expected / rows where it was expected
    false-positive rate  = rows where it fired but was not expected / rows where it was not expected
"""
from __future__ import annotations

from eval.common import DATA_DIR, SuiteSkipped, data_label, flag_codes, load_rows, offline_web, pct, seeded_session

ROWS_PATH = DATA_DIR / "e2_rows.json"
FLAGS = ("PRICE_ABOVE_REF", "STOCK_COVER_HIGH", "QTY_UNUSUAL", "NEW_SUPPLIER")


def confusion(results: list[tuple[set[str], set[str]]]) -> dict[str, dict[str, int]]:
    """Per flag: tp, fn, fp, tn over (expected, fired) pairs."""
    out = {code: {"tp": 0, "fn": 0, "fp": 0, "tn": 0} for code in FLAGS}
    for expected, fired in results:
        for code in FLAGS:
            key = ("tp" if code in fired else "fn") if code in expected else ("fp" if code in fired else "tn")
            out[code][key] += 1
    return out


def run() -> dict:
    rows, example = load_rows(ROWS_PATH)
    if not rows:
        raise SuiteSkipped("eval/data/e2_rows.json has no rows")
    unknown = {c for r in rows for c in r["expected_flags"]} - set(FLAGS)
    if unknown:
        raise ValueError(f"unknown flag code(s) in e2_rows.json: {sorted(unknown)}")

    session = seeded_session()
    results: list[tuple[set[str], set[str]]] = []
    misses: list[dict] = []
    try:
        with offline_web():
            for row in rows:
                expected, fired = set(row["expected_flags"]), flag_codes(row, session)
                results.append((expected, fired))
                if expected != fired:
                    misses.append({"id": row.get("id"), "name": row["name"],
                                   "expected": sorted(expected), "fired": sorted(fired)})
    finally:
        session.close()

    cm = confusion(results)
    table = []
    metrics = {}
    for code in FLAGS:
        c = cm[code]
        det, fpr = pct(c["tp"], c["tp"] + c["fn"]), pct(c["fp"], c["fp"] + c["tn"])
        table.append([code, c["tp"] + c["fn"], c["tp"], det, c["fp"], fpr])
        metrics[code] = {**c, "detection_pct": det, "false_positive_pct": fpr}
    planted = sum(1 for expected, _ in results if expected)
    return {
        "status": "ok",
        "data": data_label(ROWS_PATH, example),
        "summary": {
            "Rows": len(rows),
            "Rows with a planted anomaly": planted,
            "Rows where fired flags differ from expected": len(misses),
        },
        "tables": [{
            "title": "E2 per flag",
            "columns": ["Flag", "Expected", "Detected", "Detection %", "False positives", "False-positive %"],
            "rows": table,
        }],
        "metrics": metrics,
        "details": {"mismatched_rows": misses},
    }
