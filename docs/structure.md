# Project structure

```
Procur/
├── AGENTS.md                     Rules for coding agents (numbers in Python, integer rupiah, Jakarta "today")
├── docker-compose.yml            PostgreSQL 16, bound to 127.0.0.1:5432
├── start.sh / stop.sh            Start/stop DB, Langflow, backend and frontend (bash, Linux)
├── .env.example                  Root env template (subset of backend/.env.example)
├── AUDIT.md, KNOWN_ISSUES.md, SECURITY_PROGRESS.md, TECHNICAL_ROADMAP.md,
│   PROGRESS_REPORT_*.md, DEMO_VIDEO_PLAN.md   Project tracking notes
│
├── backend/
│   ├── requirements.txt          Pinned Python dependencies
│   ├── .env.example              Backend settings template (the file the app reads)
│   ├── .coveragerc               Coverage over app/services
│   ├── alembic.ini, alembic/     Migrations (alembic/versions/*.py)
│   ├── sample_data/              purchases_sample.csv / .xlsx for the import page
│   ├── app/
│   │   ├── main.py               FastAPI app, middleware, router registration, /api/health
│   │   ├── config.py             Settings (APP_NAME, DB, JWT, flow IDs, every threshold)
│   │   ├── db.py                 Engine, SessionLocal, Base, get_db
│   │   ├── models.py             SQLAlchemy models + audit_log append-only guard
│   │   ├── schemas.py            Pydantic request/response models
│   │   ├── security.py           Rate limiter, safe_http_url, PBKDF2, JWT
│   │   ├── seed.py               Demo data: python -m app.seed --reset [--empty-today]
│   │   ├── flowcheck.py          Live flow check: python -m app.flowcheck
│   │   ├── flows/contracts.py    Output contracts + output names for every flow
│   │   ├── routers/              One module per resource (see docs/api.md)
│   │   └── services/
│   │       ├── checker.py        Check engine (check_item, check_request, dry_check_item)
│   │       ├── pricing.py        Reference prices, diff_pct, bands, recommend, vendor_score
│   │       ├── flags.py          Flag rules + calculate_risk_score
│   │       ├── matcher.py        normalize_name, match_item
│   │       ├── langflow_client.py  run_flow, pick_output, ping
│   │       ├── organizer.py      Organize flow → LineItemDraft list
│   │       ├── maker.py          maker_agent input builders, output join
│   │       ├── evidence.py       Evidence guards for marketplace listings
│   │       ├── web_check.py      Web quote cache + maker_agent MODE: BON
│   │       ├── quotation.py      PDF/XLSX text extraction + quotation check
│   │       ├── decisions.py      Override rules, snapshot, audit_log writer, CSV
│   │       └── xlsx_parser.py    Purchase-history workbook parser (EN/ID headers)
│   ├── eval/
│   │   ├── run.py                python -m eval.run --suite E1,E2,...
│   │   ├── e1.py … e6.py         One module per suite
│   │   ├── data/                 Ground truth (see data/README.md)
│   │   └── results.json / .md    Last run, stamped with commit, model and flow hashes
│   └── tests/                    pytest suite (conftest.py seeds a SQLite DB)
│
├── frontend/
│   ├── vite.config.ts            React + Tailwind plugins, /api proxy to :8000
│   └── src/
│       ├── App.tsx               Auth gate + hash router
│       ├── components/           One component per page/panel (QueueTable, Inspector, ReviewPage, …)
│       ├── hooks/                TanStack Query hooks, one per resource (useQueue, useReview, …)
│       ├── lib/
│       │   ├── api.ts            fetchWithAuth (JWT header, 401 → re-login)
│       │   ├── format.ts         Rupiah (id-ID), signed %, Jakarta dates
│       │   ├── roles.ts          Role → tabs / landing page
│       │   └── decisions.ts      Override rule mirrored for the dialog
│       └── types/api.ts          TypeScript types for API responses
│
├── langflow/
│   ├── Organize.json             Flow 1: pasted text → organize_json
│   ├── Maker.json                maker_agent: extract_json, maker_json, serper_raw
│   ├── Web Check.json            Legacy web price flow (replaced by maker_agent)
│   ├── maker_agent_prompts.md    Prompt source for the maker_agent models
│   └── fixtures/<flow>/*.txt     Clean, messy and prompt-injection inputs for flowcheck
│
├── design/                       reference.html (approved UI), quick-check.html
├── plans/                        Build plan, Phase 2 plan (M16–M26), per-milestone plans
└── scripts/
    ├── release_check.ps1         Full pre-push check (tests, coverage, build, flows, claims)
    ├── check_langflow_secrets.py Fails if an exported flow contains a secret
    └── check_claims.py           Fails if README test count / coverage disagree with the code
```

## Layer rules

| Folder | Owns | Must not contain |
|---|---|---|
| `app/routers/` | HTTP parsing, role and ownership checks, status codes | Pricing or flag arithmetic, direct Langflow calls |
| `app/services/` | Business logic, pure rules, orchestration | FastAPI imports, `HTTPException` |
| `app/services/langflow_client.py` | Every HTTP call to Langflow | Business logic |
| `app/flows/contracts.py` | Shapes of model output | Database access |
| `app/config.py` | Every threshold and `APP_NAME` | Hardcoded thresholds elsewhere (flag functions receive them as arguments) |
| `frontend/src/lib/format.ts` | All money/percent/date formatting | Calculations on money beyond display |
| `frontend/` (any) | UI | Calls to Langflow or the Claude API |
| `langflow/*.json` | Exported flows | API keys (enforced by `check_langflow_secrets.py`) |

Write-side note: `checker.check_item` and `quotation.check_quotation` flush but do not commit — the router owns the transaction.
