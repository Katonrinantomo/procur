"""
QA: evaluate the web price check (Serper via Langflow Flow 2).

For each hardcoded test item the script calls web_check._call_flow(), takes the
MEDIAN of the returned offer prices (same rule the backend uses for web-sourced
reference prices) and compares it with a manually collected ground-truth price.

    MAPE = mean(|ai_price - manual_price| / manual_price) * 100
    Coverage Rate = items with a usable AI price / total items * 100

MAPE is computed only over the items that were found. The result is merged
into qa/qa_report.json under the "web_price_check" key.

Run from the backend/ folder:

    .venv/bin/python qa/eval_serper.py

NOTE: MANUAL_PRICE_IDR values are rough marketplace estimates used as a
skeleton. Re-check each one by hand (Tokopedia / Shopee) before presenting the
numbers as a real evaluation.

Needs Langflow running with LANGFLOW_WEBCHECK_FLOW_ID set in backend/.env.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median

# Make `app` importable when running `python qa/eval_serper.py` from backend/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# This script never touches the database; importing web_check pulls in
# app.models -> app.db, which builds an engine from DATABASE_URL at import time.
os.environ["DATABASE_URL"] = "sqlite://"

from app.config import settings  # noqa: E402
from app.services.web_check import _call_flow, _flow_input  # noqa: E402

REPORT_PATH = Path(__file__).resolve().parent / "qa_report.json"
JAKARTA = timezone(timedelta(hours=7))

# (item name, manual reference price per unit in whole rupiah)
TEST_ITEMS: list[tuple[str, int]] = [
    ("Oli Shell Helix HX7 10W-40 4 liter", 330_000),
    ("Bearing SKF 6205", 65_000),
    ("Kabel listrik NYM 2x1.5 Eterna 50 meter", 600_000),
    ("Lakban bening 48mm x 100 yard", 20_000),
    ("Sarung tangan katun 1 lusin", 30_000),
    ("Mata bor besi HSS 10mm Bosch", 45_000),
    ("Gerinda tangan Bosch GWS 060", 650_000),
    ("Cat tembok Dulux Catylac 25 kg", 650_000),
    ("Kertas HVS A4 70gsm Sidu 1 rim", 52_000),
    ("Meteran Stanley 5 meter", 70_000),
]


def ai_price_from_offers(offers: list[dict]) -> int | None:
    """Median of valid offer prices, in whole rupiah. None if no valid offer."""
    prices = [
        o["price_idr"]
        for o in offers
        if isinstance(o, dict) and isinstance(o.get("price_idr"), int) and o["price_idr"] > 0
    ]
    if not prices:
        return None
    return round(median(prices))


def abs_pct_error(ai_price: int, manual_price: int) -> float:
    """Absolute percentage error of ai_price relative to manual_price."""
    return abs(ai_price - manual_price) / manual_price * 100


def mape(pairs: list[tuple[int, int]]) -> float | None:
    """Mean Absolute Percentage Error over (ai_price, manual_price) pairs."""
    if not pairs:
        return None
    return sum(abs_pct_error(a, m) for a, m in pairs) / len(pairs)


def coverage_rate(found: int, total: int) -> float | None:
    """Percentage of items for which the AI returned a usable price."""
    return found / total * 100 if total else None


def save_report(section: str, data: dict) -> None:
    """Merge *data* into qa_report.json under *section*, keeping other sections."""
    report: dict = {}
    if REPORT_PATH.exists():
        try:
            report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            report = {}
    report[section] = {**data, "generated_at": datetime.now(JAKARTA).isoformat(timespec="seconds")}
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    if not settings.LANGFLOW_WEBCHECK_FLOW_ID:
        msg = "LANGFLOW_WEBCHECK_FLOW_ID is not set in backend/.env; cannot call the web check flow."
        print(f"ERROR: {msg}")
        save_report("web_price_check", {"status": "not_run", "error": msg, "mape_pct": None, "coverage_rate_pct": None})
        return 1

    print(f"Evaluating web price check on {len(TEST_ITEMS)} items\n")
    header = f"{'Item':<42} {'Manual':>12} {'AI':>12} {'Error %':>9}  Offers"
    print(header)
    print("-" * len(header))

    pairs: list[tuple[int, int]] = []
    items_report: list[dict] = []
    for name, manual in TEST_ITEMS:
        try:
            offers = _call_flow(_flow_input(name))
        except Exception as exc:  # noqa: BLE001 - report and continue with the next item
            print(f"{name:<42} {manual:>12,} {'ERROR':>12} {'-':>9}  {type(exc).__name__}: {exc}")
            items_report.append({"name": name, "manual_price_idr": manual, "ai_price_idr": None,
                                 "error_pct": None, "error": f"{type(exc).__name__}: {exc}"})
            continue

        ai = ai_price_from_offers(offers)
        if ai is None:
            print(f"{name:<42} {manual:>12,} {'no price':>12} {'-':>9}  0")
            items_report.append({"name": name, "manual_price_idr": manual, "ai_price_idr": None,
                                 "error_pct": None, "error": "no usable price in offers"})
            continue

        pairs.append((ai, manual))
        n_offers = sum(1 for o in offers if isinstance(o, dict))
        err = abs_pct_error(ai, manual)
        print(f"{name:<42} {manual:>12,} {ai:>12,} {err:>8.1f}%  {n_offers}")
        items_report.append({"name": name, "manual_price_idr": manual, "ai_price_idr": ai,
                             "error_pct": round(err, 1), "error": None})

    total = len(TEST_ITEMS)
    found = len(pairs)
    coverage = coverage_rate(found, total)
    score = mape(pairs)

    print()
    print(f"Total Items: {total}")
    print(f"Items Found: {found}")
    print(f"Coverage Rate: {coverage:.1f}%")
    print(f"MAPE (found items only): {f'{score:.1f}%' if score is not None else 'N/A'}")

    save_report("web_price_check", {
        "status": "ok" if found else "failed",
        "total_items": total,
        "items_found": found,
        "coverage_rate_pct": round(coverage, 1) if coverage is not None else None,
        "mape_pct": round(score, 1) if score is not None else None,
        "items": items_report,
    })
    print(f"Report saved to {REPORT_PATH}")
    return 0 if found else 1


if __name__ == "__main__":
    sys.exit(main())
