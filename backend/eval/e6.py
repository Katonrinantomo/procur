"""
E6 — payment detection per audit rule.

Lands with M22: the 24 bundles in eval/data/e5_bundles/ and the checker
flow do not exist yet.  Until then the suite reports itself as skipped.
"""
from __future__ import annotations

from eval.common import SuiteSkipped


def run() -> dict:
    raise SuiteSkipped("E6 lands with M22 (checker_agent and the audit engine are not built yet)")
