"""
Decision log (M19): the rules for when a decision needs a reason, the snapshot
taken at decision time, and the one function that writes an audit_log row.

Rows are append-only. Nothing here (or anywhere else) updates or deletes one;
models._audit_log_append_only enforces that for the ORM.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Action, AuditLog, Flag, RequestItem

JAKARTA = timezone(timedelta(hours=7))

OUTCOME_TAGS = ("false_alarm", "risk_accepted")


class DecisionError(ValueError):
    """The decision is missing a required reason or outcome tag (HTTP 422)."""


def is_override(flag_codes: Iterable[str], risk_score: int, status: str) -> bool:
    """Approving this row overrides the checker: it is flagged or high-risk."""
    return (
        status == "flagged"
        or any(True for _ in flag_codes)
        or risk_score >= settings.OVERRIDE_RISK_SCORE
    )


def validate_decision(
    decision: str,
    override: bool,
    reason: str | None,
    outcome_tag: str | None,
) -> tuple[str | None, str | None]:
    """
    Return the cleaned (reason, outcome_tag) or raise DecisionError.

    - return: reason required; no outcome tag.
    - approve, override: reason and outcome tag (false_alarm | risk_accepted) required.
    - approve, no override: reason optional; no outcome tag.
    """
    reason = reason.strip() if reason else None
    reason = reason or None

    if outcome_tag is not None and outcome_tag not in OUTCOME_TAGS:
        raise DecisionError(f"outcome_tag must be one of {', '.join(OUTCOME_TAGS)}")

    if decision == "return":
        if reason is None:
            raise DecisionError("A reason is required to return a row")
        if outcome_tag is not None:
            raise DecisionError("outcome_tag applies only to approving a flagged or high-risk row")
        return reason, None

    if decision == "approve":
        if override:
            if reason is None:
                raise DecisionError("A reason is required to approve a flagged or high-risk row")
            if outcome_tag is None:
                raise DecisionError(
                    "Pick an outcome tag (false_alarm or risk_accepted) to approve a flagged or high-risk row"
                )
            return reason, outcome_tag
        if outcome_tag is not None:
            raise DecisionError("outcome_tag applies only to approving a flagged or high-risk row")
        return reason, None

    raise DecisionError(f"Unknown decision: {decision}")


def build_snapshot(ri: RequestItem, flags: list[Flag]) -> dict[str, Any]:
    """What the decider saw: flags, risk score, reference price and its source."""
    return {
        "status": ri.status,
        "flags": [{"code": f.code, "message": f.message} for f in flags],
        "risk_score": ri.risk_score,
        "quoted_unit_price_idr": ri.quoted_unit_price_idr,
        "reference_unit_price_idr": ri.reference_unit_price_idr,
        # history | web | none
        "reference_source": ri.checked_via,
        "history_count": ri.history_count,
        "diff_pct": float(ri.diff_pct) if ri.diff_pct is not None else None,
    }


def record_request_item_decision(
    db: Session,
    ri: RequestItem,
    *,
    decision: str,
    user_id: int,
    role: str,
    reason: str | None,
    outcome_tag: str | None,
) -> AuditLog:
    """
    Validate and record an approve/return on a request item: one audit_log row
    with the snapshot, plus the status change. Raises DecisionError (422).
    The caller commits.
    """
    flags = list(
        db.execute(select(Flag).where(Flag.request_item_id == ri.id)).scalars()
    )
    override = decision == "approve" and is_override(
        (f.code for f in flags), ri.risk_score, ri.status
    )
    reason, outcome_tag = validate_decision(decision, override, reason, outcome_tag)

    # Snapshot before the status changes, so it records what was decided on.
    snapshot = build_snapshot(ri, flags)

    entry = AuditLog(
        request_item_id=ri.id,
        user_id=user_id,
        action=decision,
        note=reason,
        subject_type="request_item",
        subject_id=ri.id,
        decision=decision,
        reason=reason,
        role=role,
        outcome_tag=outcome_tag,
        snapshot=snapshot,
    )
    db.add(entry)
    # Legacy actions row (read by older clients); the decider is in audit_log.
    db.add(Action(request_item_id=ri.id, action=decision, note=reason))
    ri.status = "approved" if decision == "approve" else "returned"
    return entry


# ---------------------------------------------------------------------------
# Review ordering
# ---------------------------------------------------------------------------

def review_sort_key(status: str, risk_score: int, requested_at: datetime, line_no: int):
    """Flagged first, then risk score descending, then oldest request first."""
    return (0 if status == "flagged" else 1, -risk_score, requested_at, line_no)


# ---------------------------------------------------------------------------
# CSV export
# ---------------------------------------------------------------------------

CSV_COLUMNS = [
    "id",
    "decided_at",
    "subject_type",
    "subject_id",
    "item_name",
    "decision",
    "reason",
    "outcome_tag",
    "decided_by",
    "role",
    "risk_score",
    "flags",
    "quoted_unit_price_idr",
    "reference_unit_price_idr",
    "reference_source",
    "diff_pct",
]


def _csv_safe(value: Any) -> Any:
    """Stop Excel from evaluating free text as a formula (CSV injection)."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def decisions_csv(rows: Iterable[dict[str, Any]]) -> str:
    """
    Render decision rows as CSV. Starts with a UTF-8 BOM so Excel reads
    Indonesian text correctly; times are Asia/Jakarta.
    """
    buf = io.StringIO()
    buf.write("﻿")
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(CSV_COLUMNS)
    for r in rows:
        snap = r.get("snapshot") or {}
        decided_at: datetime = r["created_at"]
        if decided_at.tzinfo is None:
            decided_at = decided_at.replace(tzinfo=timezone.utc)
        writer.writerow([
            r["id"],
            decided_at.astimezone(JAKARTA).strftime("%Y-%m-%d %H:%M:%S"),
            r["subject_type"],
            r["subject_id"],
            _csv_safe(r.get("item_name")),
            r["decision"],
            _csv_safe(r.get("reason")),
            r.get("outcome_tag"),
            _csv_safe(r.get("username")),
            r.get("role"),
            snap.get("risk_score"),
            ";".join(f["code"] for f in snap.get("flags", [])),
            snap.get("quoted_unit_price_idr"),
            snap.get("reference_unit_price_idr"),
            snap.get("reference_source"),
            snap.get("diff_pct"),
        ])
    return buf.getvalue()
