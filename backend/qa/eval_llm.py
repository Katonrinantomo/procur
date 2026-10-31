"""
QA: evaluate LLM extraction accuracy (Langflow Flow 1 - Organize).

Each data/*.txt WhatsApp message is sent through organizer.parse_text() and the
result is compared with qa/data/ground_truth.json.

Field-level accuracy = correct fields / expected fields, where every expected
item contributes 6 fields: name, qty, unit, department, quoted_unit_price_idr,
supplier. Predicted items are paired with expected items by name similarity.
An expected item with no matching prediction counts all 6 fields as wrong.
Extra predicted items are reported but do not change the denominator.

Unit and department values are compared semantically: both the LLM value and
the ground-truth value are lowercased and passed through a synonym map (e.g.
"lusin" == "doz", "gudang" == "warehouse") before comparing. Wrong values
(different qty, different item name, ...) are still reported as mismatches.

The result is merged into qa/qa_report.json under the "llm_extraction" key.

Run from the backend/ folder:

    .venv/bin/python qa/eval_llm.py

Needs Langflow running with LANGFLOW_ORGANIZE_FLOW_ID set in backend/.env.
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from pathlib import Path

# Make `app` importable when running `python qa/eval_llm.py` from backend/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.services.organizer import parse_text  # noqa: E402

QA_DIR = Path(__file__).resolve().parent
DATA_DIR = QA_DIR / "data"
REPORT_PATH = QA_DIR / "qa_report.json"
JAKARTA = timezone(timedelta(hours=7))
FIELDS = ["name", "qty", "unit", "department", "quoted_unit_price_idr", "supplier"]

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


def name_similarity(a: str | None, b: str | None) -> float:
    """1.0 if one normalized name contains the other, else difflib ratio."""
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return 0.0
    if na in nb or nb in na:
        return 1.0
    return SequenceMatcher(None, na, nb).ratio()


def field_correct(field: str, expected, predicted: dict) -> bool:
    got = predicted.get(field)
    if field == "name":
        return name_similarity(expected, got) >= 0.8
    if isinstance(expected, str):
        return normalize_value(field, expected) == normalize_value(field, got)
    # ints and None: exact match (None expected means the model must not invent a value)
    return expected == got


def pair_items(expected: list[dict], predicted: list[dict]) -> list[dict | None]:
    """For each expected item, pick the unused predicted item with the best name match."""
    used: set[int] = set()
    result: list[dict | None] = []
    for exp in expected:
        best_i, best_score = None, 0.0
        for i, pred in enumerate(predicted):
            if i in used:
                continue
            score = name_similarity(exp["name"], pred.get("name"))
            if score > best_score:
                best_i, best_score = i, score
        if best_i is not None and best_score >= 0.5:
            used.add(best_i)
            result.append(predicted[best_i])
        else:
            result.append(None)
    return result


def score_file(expected: list[dict], predicted: list[dict]) -> tuple[int, int, list[str]]:
    """Return (correct_fields, total_fields, list of mismatch descriptions)."""
    correct = 0
    total = len(expected) * len(FIELDS)
    mismatches: list[str] = []
    for exp, pred in zip(expected, pair_items(expected, predicted)):
        if pred is None:
            mismatches.append(f"  missing item: {exp['name']!r}")
            continue
        for field in FIELDS:
            if field_correct(field, exp[field], pred):
                correct += 1
            else:
                mismatches.append(
                    f"  {exp['name']!r}.{field}: expected {exp[field]!r}, got {pred.get(field)!r}"
                )
    extra = len(predicted) - sum(1 for p in pair_items(expected, predicted) if p is not None)
    if extra > 0:
        mismatches.append(f"  {extra} extra item(s) not in ground truth")
    return correct, total, mismatches


def main() -> int:
    if not settings.LANGFLOW_ORGANIZE_FLOW_ID:
        msg = "LANGFLOW_ORGANIZE_FLOW_ID is not set in backend/.env; cannot call the organize flow."
        print(f"ERROR: {msg}")
        save_report("llm_extraction", {"status": "not_run", "error": msg, "field_accuracy_pct": None})
        return 1

    truth: dict[str, dict] = json.loads((DATA_DIR / "ground_truth.json").read_text(encoding="utf-8"))

    sum_correct = sum_total = failures = 0
    per_file: dict[str, dict] = {}
    for filename, spec in truth.items():
        text = (DATA_DIR / filename).read_text(encoding="utf-8").strip()
        print(f"== {filename}")
        try:
            drafts = asyncio.run(parse_text(text))
        except Exception as exc:  # noqa: BLE001 - report and continue with the next file
            failures += 1
            print(f"  ERROR: {type(exc).__name__}: {exc}\n")
            per_file[filename] = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
            continue

        correct, total, mismatches = score_file(spec["items"], [d.model_dump() for d in drafts])
        sum_correct += correct
        sum_total += total
        print(f"  {correct}/{total} fields correct ({correct / total * 100:.1f}%)")
        for line in mismatches:
            print(line)
        print()
        per_file[filename] = {
            "status": "ok",
            "correct_fields": correct,
            "total_fields": total,
            "accuracy_pct": round(correct / total * 100, 1),
            "mismatches": [m.strip() for m in mismatches],
        }

    processed = len(truth) - failures
    print(f"Files processed: {processed}/{len(truth)} (failed: {failures})")
    accuracy = round(sum_correct / sum_total * 100, 1) if sum_total else None
    if accuracy is None:
        print("Field-level accuracy: N/A (no file was processed)")
    else:
        print(f"Field-level accuracy: {sum_correct}/{sum_total} = {accuracy:.1f}%")

    save_report("llm_extraction", {
        "status": "ok" if processed else "failed",
        "files_total": len(truth),
        "files_processed": processed,
        "correct_fields": sum_correct,
        "total_fields": sum_total,
        "field_accuracy_pct": accuracy,
        "files": per_file,
    })
    print(f"Report saved to {REPORT_PATH}")
    return 0 if accuracy is not None else 1


if __name__ == "__main__":
    sys.exit(main())
