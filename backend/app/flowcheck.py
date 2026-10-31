"""
Live flow check: python -m app.flowcheck

For every flow whose ID is set, runs each fixture in
langflow/fixtures/<flow>/*.txt through the real Langflow, validates the
output against its contract (with the same repair retry production uses),
prints a table and writes the result to backend/.flowcheck_last.json for
GET /api/health/flows.

Exit code 0 when every fixture passes, 1 on any failure or when no flow is
configured.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from app.config import FLOW_ID_SETTINGS, settings
from app.flows.contracts import (
    CHECKER_OUT,
    MAKER_OUT,
    NARRATOR_OUT,
    ORGANIZE_OUT,
    WEBCHECK_OUT,
    CheckerOut,
    MakerOut,
    NarratorOut,
    OrganizeOut,
    WebCheckOut,
    parse_flow_json,
)
from app.services.langflow_client import pick_output, run_flow

BACKEND_DIR = Path(__file__).resolve().parents[1]
FIXTURES_ROOT = BACKEND_DIR.parent / "langflow" / "fixtures"
RESULT_PATH = BACKEND_DIR / ".flowcheck_last.json"


@dataclass(frozen=True)
class FlowSpec:
    name: str
    output_name: str
    model: type[BaseModel]

    @property
    def flow_id(self) -> str:
        return getattr(settings, FLOW_ID_SETTINGS[self.name])


FLOWS: list[FlowSpec] = [
    FlowSpec("organize", ORGANIZE_OUT, OrganizeOut),
    FlowSpec("web_check", WEBCHECK_OUT, WebCheckOut),
    FlowSpec("maker", MAKER_OUT, MakerOut),
    FlowSpec("checker", CHECKER_OUT, CheckerOut),
    FlowSpec("narrator", NARRATOR_OUT, NarratorOut),
]


@dataclass
class FixtureResult:
    flow: str
    fixture: str
    ok: bool | None  # None = skipped
    seconds: float | None
    error: str


async def _run_fixture(spec: FlowSpec, path: Path) -> FixtureResult:
    text = path.read_text(encoding="utf-8")
    repaired = False

    async def run(input_text: str) -> str:
        return pick_output(await run_flow(spec.flow_id, input_text), spec.output_name)

    async def rerun(hint: str) -> str:
        nonlocal repaired
        repaired = True
        return await run(f"{text}\n\n{hint}")

    start = time.perf_counter()
    try:
        await parse_flow_json(await run(text), spec.model, rerun)
    except Exception as exc:  # noqa: BLE001 — every failure is a red row
        return FixtureResult(spec.name, path.name, False, time.perf_counter() - start, str(exc))
    return FixtureResult(
        spec.name, path.name, True, time.perf_counter() - start,
        "repaired" if repaired else "",
    )


async def check_flows(fixtures_root: Path = FIXTURES_ROOT) -> list[FixtureResult]:
    results: list[FixtureResult] = []
    for spec in FLOWS:
        if not spec.flow_id:
            results.append(FixtureResult(spec.name, "-", None, None, f"{FLOW_ID_SETTINGS[spec.name]} is empty"))
            continue
        fixtures = sorted((fixtures_root / spec.name).glob("*.txt"))
        if not fixtures:
            results.append(FixtureResult(spec.name, "-", False, None, f"no fixtures in {fixtures_root / spec.name}"))
            continue
        for path in fixtures:
            result = await _run_fixture(spec, path)
            # Progress on stderr: a failing fixture can take minutes across 3 tries.
            print(
                f"{spec.name}/{path.name}: {'PASS' if result.ok else 'FAIL'} ({result.seconds:.1f}s)",
                file=sys.stderr,
                flush=True,
            )
            results.append(result)
    return results


def _print_table(results: list[FixtureResult]) -> None:
    rows = [("flow", "fixture", "ok", "seconds", "error")]
    for r in results:
        ok = "skip" if r.ok is None else ("PASS" if r.ok else "FAIL")
        secs = "-" if r.seconds is None else f"{r.seconds:.1f}"
        rows.append((r.flow, r.fixture, ok, secs, r.error.replace("\n", " ")[:80]))
    widths = [max(len(row[i]) for row in rows) for i in range(4)]
    for row in rows:
        print("  ".join(cell.ljust(w) for cell, w in zip(row[:4], widths)) + "  " + row[4])


async def main(fixtures_root: Path = FIXTURES_ROOT, result_path: Path = RESULT_PATH) -> int:
    results = await check_flows(fixtures_root)
    ran = [r for r in results if r.ok is not None]
    ok = bool(ran) and all(r.ok for r in ran)

    _print_table(results)
    if not ran:
        print("\nNo flow configured: set at least one LANGFLOW_*_FLOW_ID.")
    print(f"\n{'PASS' if ok else 'FAIL'}: {sum(1 for r in ran if r.ok)}/{len(ran)} fixtures passed")

    result_path.write_text(
        json.dumps(
            {
                "at": datetime.now(tz=timezone.utc).isoformat(),
                "ok": ok,
                "results": [asdict(r) for r in results],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
