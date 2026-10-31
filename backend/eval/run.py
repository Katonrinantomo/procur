"""
Eval harness entry point.  Run from backend/:

    python -m eval.run --suite E1,E2,E3,E4      (E5, E6 once M21–M22 land)

Runs each suite's run() -> dict and writes eval/results.json and a readable
eval/results.md (one section per suite), both stamped with the run date
(Asia/Jakarta), the git commit, the model ID(s) in the exported flows and
the sha256 of every langflow/*.json, so each number traces to the flow that
produced it.

A suite that cannot run here (no data yet, flow ID unset, Langflow down)
is reported as skipped with the reason.  Exit code 1 if any suite errored.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import subprocess
import sys
import traceback
from datetime import datetime, timedelta, timezone

from eval.common import EVAL_DIR, SuiteSkipped, skipped

SUITES = ("E1", "E2", "E3", "E4", "E5", "E6")
LANGFLOW_DIR = EVAL_DIR.parent.parent / "langflow"
JSON_PATH = EVAL_DIR / "results.json"
MD_PATH = EVAL_DIR / "results.md"
JAKARTA = timezone(timedelta(hours=7))


def flow_models(flow: dict) -> list[str]:
    """The model selected on each language-model node, as "provider: name"."""
    found: list[str] = []
    for node in flow.get("data", {}).get("nodes", []):
        field = node.get("data", {}).get("node", {}).get("template", {}).get("model")
        if isinstance(field, dict) and isinstance(field.get("value"), list):
            found += [f"{m.get('provider')}: {m.get('name')}" for m in field["value"] if isinstance(m, dict)]
    return sorted(set(found))


def stamp() -> dict:
    flows = sorted(LANGFLOW_DIR.glob("*.json"))
    models: dict[str, list[str]] = {}
    hashes: dict[str, str] = {}
    for path in flows:
        raw = path.read_bytes()
        hashes[path.name] = hashlib.sha256(raw).hexdigest()
        models[path.name] = flow_models(json.loads(raw))
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                                text=True, cwd=EVAL_DIR, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = None
    return {
        "run_at": datetime.now(JAKARTA).isoformat(timespec="seconds"),
        "git_commit": commit,
        "flow_models": models,
        "flow_sha256": hashes,
    }


def run_suite(name: str) -> dict:
    try:
        module = importlib.import_module(f"eval.{name.lower()}")
        return module.run()
    except SuiteSkipped as exc:
        return skipped(str(exc))
    except Exception as exc:  # noqa: BLE001 - one broken suite must not hide the others
        return {"status": "error", "reason": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc()}


def _cell(value) -> str:
    if value is None:
        return "–"
    return str(value).replace("|", "\\|").replace("\n", " ")


def _table(columns: list[str], rows: list[list]) -> list[str]:
    lines = ["| " + " | ".join(columns) + " |", "|" + " --- |" * len(columns)]
    lines += ["| " + " | ".join(_cell(v) for v in row) + " |" for row in rows]
    return lines


def render_md(meta: dict, results: dict[str, dict]) -> str:
    out = [
        "# Procur.AI eval results",
        "",
        f"- Run at: {meta['run_at']} (Asia/Jakarta)",
        f"- Git commit: `{meta['git_commit']}`",
        "- Exported flows (`langflow/*.json`): model ID and sha256",
    ]
    out += [f"  - `{name}`: {', '.join(f'`{m}`' for m in meta['flow_models'][name]) or 'no model node'}"
            f" — sha256 `{digest}`" for name, digest in meta["flow_sha256"].items()]
    out += ["", "Command: `python -m eval.run --suite " + ",".join(results) + "` (from `backend/`)", ""]
    for name, res in results.items():
        out += [f"## {name}", "", f"Status: **{res['status']}**" + (f" — {res['reason']}" if res.get("reason") else "")]
        if res.get("data"):
            out.append(f"Data: `{res['data']}`" if "EXAMPLE" not in res["data"]
                       else f"Data: **{res['data']}**")
        out.append("")
        if res.get("summary"):
            out += _table(["Metric", "Value"], [[k, v] for k, v in res["summary"].items()]) + [""]
        for t in res.get("tables", []):
            out += [f"**{t['title']}**", ""]
            out += (_table(t["columns"], t["rows"]) if t["rows"] else ["None."]) + [""]
    return "\n".join(out).rstrip() + "\n"


def parse_suites(arg: str) -> list[str]:
    names = [s.strip().upper() for s in arg.split(",") if s.strip()]
    bad = [s for s in names if s not in SUITES]
    if bad:
        raise SystemExit(f"unknown suite(s): {', '.join(bad)}; choose from {', '.join(SUITES)}")
    return names


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m eval.run", description=__doc__.split("\n\n")[0])
    parser.add_argument("--suite", default="E1,E2,E3,E4", help="comma-separated, e.g. E1,E2,E3,E4")
    args = parser.parse_args(argv)

    meta = stamp()
    results: dict[str, dict] = {}
    for name in parse_suites(args.suite):
        print(f"== {name} ...", flush=True)
        res = run_suite(name)
        results[name] = res
        print(f"   {res['status']}" + (f": {res['reason']}" if res.get("reason") else ""), flush=True)

    JSON_PATH.write_text(json.dumps({"meta": meta, "suites": results}, indent=2, ensure_ascii=False,
                                    default=str) + "\n", encoding="utf-8")
    MD_PATH.write_text(render_md(meta, results), encoding="utf-8")
    print(f"Wrote {JSON_PATH.relative_to(EVAL_DIR.parent)} and {MD_PATH.relative_to(EVAL_DIR.parent)}")
    return 1 if any(r["status"] == "error" for r in results.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
