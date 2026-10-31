"""
E5 — checker_agent extraction (and E5b, error propagation into the audit engine).

Lands with M21–M22: the 24 bundles in eval/data/e5_bundles/ and the checker
flow do not exist yet.  Until then the suite reports itself as skipped.
"""
from __future__ import annotations

from eval.common import SuiteSkipped


def run() -> dict:
    raise SuiteSkipped("E5 lands with M21–M22 (checker_agent and the audit engine are not built yet)")
