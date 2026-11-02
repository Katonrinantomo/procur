# Testing

## Running the tests

From `backend/` with the venv active:

```powershell
pytest                              # offline suite; live tests are collected but skipped
pytest tests/test_pricing.py        # one file
pytest tests/test_flags.py -k stock # one group
pytest -m live                      # also run the live Langflow check (needs Langflow + flow IDs)
pytest --cov --cov-report=term      # line coverage over app/services (.coveragerc)
```

No PostgreSQL or Langflow is needed. `tests/conftest.py` sets `DATABASE_URL` to a file-based SQLite database (`test_procur.db`), a fixed `JWT_SECRET`, `ALLOWED_HOSTS` including `testserver`, and lowers PBKDF2 iterations to 1 000 so seeding is fast. A session-scoped fixture creates the schema, runs the full demo seed (with today's request) and the check engine once; the file is removed at the end.

## What is covered

| Kind | Files | What they pin down |
|---|---|---|
| Pure rules | `test_pricing.py`, `test_flags.py`, `test_evidence.py`, `test_matcher.py` | Reference mean/median, `diff_pct` rounding, band edges (inclusive), recommendation, vendor score; each flag's threshold edge and message; listing guards and rupiah parsing (`1,45jt`, `1.450.000,00`); unit normalization and false matches on short names |
| Check engine | `test_check_engine.py`, `test_web_price_path.py` | The five seeded demo rows produce exactly the documented numbers (oil +29.5%, solenoid via web median); web cache and fallback behaviour |
| Flow boundary | `test_contracts.py`, `test_langflow_client.py`, `test_langflow.py`, `test_flowcheck.py`, `test_health_flows.py` | Contract validation, repair retry, named outputs, retry/no-retry rules, flowcheck reporting — Langflow is mocked |
| API | `test_api.py`, `test_quick_check.py`, `test_quotations.py`, `test_purchases.py`, `test_import.py`, `test_import_xlsx.py`, `test_decisions.py` | Endpoints through `TestClient`: queue order and counts, dry-run writes nothing, upload validation, import dedupe and EN/ID headers, override rules and append-only log |
| Security | `test_auth.py`, `test_security.py`, `test_middleware.py`, `test_rate_limit.py`, `test_config_validation.py`, `test_seed_guard.py` | Role and ownership checks, JWT tampering/expiry, `safe_http_url` SSRF cases, security headers and trusted hosts, rate limits, startup refusal without secrets, seed guard on non-local databases |
| Eval harness | `test_eval.py` | Scoring functions, data loaders and report writer (no suite run live) |
| Live | `test_live_flows.py` (`@pytest.mark.live`) | Runs `app.flowcheck` against the real Langflow |

Project rules the suite enforces: every function in `pricing.py` and `flags.py` has a test, and the seed numbers are the expected values — when a check-engine test fails, fix the code, not the seed or the expectation.

## Coverage

`backend/.coveragerc` measures line coverage over `app/services` only (business logic), with missing lines shown and JSON output to `coverage.json`. Routers are exercised by the API tests but not counted. The README states the current figure; `scripts/check_claims.py` fails if it disagrees with `coverage.json`.

## Live flow check

```powershell
python -m app.flowcheck
```

Runs every `langflow/fixtures/<flow>/*.txt` (clean, messy and prompt-injection inputs) through each flow whose ID is set, validates the output against `app/flows/contracts.py` with the same repair retry production uses, prints pass/fail and latency, and writes `backend/.flowcheck_last.json` (shown at `GET /api/health/flows`). Exit 1 on any failure or when no flow is configured.

## Eval harness

Measures accuracy, not correctness of code. From `backend/`:

```powershell
python -m eval.run --suite E1,E2,E3,E4
```

| Suite | Measures | Needs |
|---|---|---|
| E1 / E1b | Organize extraction per field, rows missed/invented, flags changed by misreading | Langflow + Organize |
| E2 | Detection and false-positive rate per flag | offline (throwaway seeded SQLite) |
| E3 | Web price MAPE, no-quote rate, share off by > 30%, listings dropped by guards | Langflow + maker_agent + Serper |
| E4 | Name-matching wrong-match rate | offline |
| E5, E6 | Checker extraction and payment detection | land with M21–M22 |

Results go to `eval/results.json` and `eval/results.md`, stamped with the date (Jakarta), git commit, model per exported flow and sha256 of every `langflow/*.json`. Suites without data, flow ID or Langflow are reported as skipped with the reason; data files marked as example are labelled "EXAMPLE DATA — not a measurement". See `eval/data/README.md` for what ground truth is still missing.

## Release check

From the repo root, before every push:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\release_check.ps1
```

Stops at the first failure: pytest with coverage → coverage report → `npm run build` → `check_langflow_secrets.py` + `python -m app.flowcheck` → `check_claims.py`. `-SkipFlowcheck` skips the live step when Langflow is down; that run is not a full release check.

## Frontend

There are no frontend unit tests. `npm run build` (`tsc -b && vite build`) type-checks the app and is part of the release check; `npm run lint` runs oxlint.
