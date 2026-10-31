"""
E3 — web prices (maker_agent, MODE: BON, via Serper).

Each item in eval/data/e3_prices.csv carries a price checked by hand on a
marketplace, with the date and source URL.  The item name goes through
maker_agent exactly as web_check sends it; the evidence guards drop listings
whose URL or price is not in the Serper results; the reference is what the
backend would use, pricing.reference_from_quotes() (median of the kept
quotes, only with at least WEB_MIN_QUOTES of them).

Reports:
    MAPE           mean(|reference - manual| / manual) over items with a reference
    no quotes      share of items with no kept quote at all
    no reference   share of items with fewer than WEB_MIN_QUOTES kept quotes
    off > 30%      share of items with a reference more than 30% from manual
    dropped        listings dropped by the evidence guards

Rows without a manual price, date or URL are listed as unfilled and not
scored; the suite skips when no row is filled.  Needs Langflow running with
LANGFLOW_MAKER_FLOW_ID set in backend/.env; skips with a message otherwise.
"""
from __future__ import annotations

import asyncio

from eval.common import DATA_DIR, SuiteSkipped, data_label, load_rows, pct, require_flow

PRICES_PATH = DATA_DIR / "e3_prices.csv"
REQUIRED = ("item", "manual_price_idr", "checked_on", "source_url")
OFF_PCT = 30.0


def abs_pct_error(ai_price: int, manual_price: int) -> float:
    """Absolute percentage error of ai_price relative to manual_price."""
    return abs(ai_price - manual_price) / manual_price * 100


def mape(pairs: list[tuple[int, int]]) -> float | None:
    """Mean Absolute Percentage Error over (ai_price, manual_price) pairs."""
    if not pairs:
        return None
    return sum(abs_pct_error(a, m) for a, m in pairs) / len(pairs)


def filled_rows(rows: list[dict]) -> tuple[list[dict], list[str]]:
    """Split rows into (filled rows with an int manual price, names of unfilled rows)."""
    filled: list[dict] = []
    unfilled: list[str] = []
    for row in rows:
        if any(not row.get(k) for k in REQUIRED):
            unfilled.append(row.get("item") or "?")
            continue
        filled.append({**row, "manual_price_idr": int(row["manual_price_idr"].replace(".", "").replace(",", ""))})
    return filled, unfilled


def run() -> dict:
    rows, example = load_rows(PRICES_PATH)
    filled, unfilled = filled_rows(rows)
    if not filled:
        raise SuiteSkipped(
            f"no hand-checked prices yet in eval/data/e3_prices.csv "
            f"({len(rows)} item(s) listed, 0 with manual price, date and URL)"
        )
    require_flow("LANGFLOW_MAKER_FLOW_ID")

    from app.services import pricing
    from app.services.maker import call_maker
    from app.services.web_check import _flow_input

    pairs: list[tuple[int, int]] = []
    no_quotes = no_reference = off = dropped = errors = 0
    table: list[list] = []
    for row in filled:
        name, manual = row["item"], row["manual_price_idr"]
        try:
            result = asyncio.run(call_maker(_flow_input(name)))
        except Exception as exc:  # noqa: BLE001 - report and continue with the next item
            errors += 1
            table.append([name, manual, "error", None, 0, 0, f"{type(exc).__name__}: {exc}"])
            continue
        kept = [k.price_idr for line in result.lines for k in line.kept]
        n_dropped = sum(len(line.dropped) for line in result.lines)
        dropped += n_dropped
        ref = pricing.reference_from_quotes(kept)
        no_quotes += not kept
        if ref is None:
            no_reference += 1
            table.append([name, manual, None, None, len(kept), n_dropped, ""])
            continue
        err = abs_pct_error(ref, manual)
        off += err > OFF_PCT
        pairs.append((ref, manual))
        table.append([name, manual, ref, round(err, 1), len(kept), n_dropped, ""])

    scored = len(filled) - errors
    score = mape(pairs)
    return {
        "status": "ok" if scored else "error",
        "data": data_label(PRICES_PATH, example),
        "summary": {
            "Items scored": f"{scored}/{len(filled)}",
            "Unfilled rows (not scored)": len(unfilled),
            "MAPE % (items with a reference)": round(score, 1) if score is not None else None,
            "No quotes %": pct(no_quotes, scored),
            f"No reference (< {_min_quotes()} quotes) %": pct(no_reference, scored),
            f"Off by > {OFF_PCT:.0f}% (share of scored)": pct(off, scored),
            "Listings dropped by evidence guards": dropped,
        },
        "tables": [{
            "title": "E3 per item",
            "columns": ["Item", "Manual Rp", "Reference Rp", "Error %", "Kept", "Dropped", "Error"],
            "rows": table,
        }],
        "metrics": {
            "mape_pct": round(score, 1) if score is not None else None,
            "no_quotes_pct": pct(no_quotes, scored),
            "no_reference_pct": pct(no_reference, scored),
            "off_by_more_than_30_pct": pct(off, scored),
            "dropped_by_guards": dropped,
            "unfilled": unfilled,
        },
    }


def _min_quotes() -> int:
    from app.config import settings

    return settings.WEB_MIN_QUOTES
