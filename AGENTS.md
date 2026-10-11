# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Project

Procur.AI — a procurement price-check web app for a manufacturing hackathon demo. See `plans/Procur.AI — Build Plan for IBM Bob.md` for the full spec and `design/reference.html` for the approved UI.

## Stack

- **Backend:** Python 3.11+, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, httpx, rapidfuzz, pytest
- **Frontend:** React + Vite + TypeScript, Tailwind CSS, TanStack Query
- **Database:** PostgreSQL 16 via `docker-compose.yml` (SQLite fallback via `DATABASE_URL`)
- **AI:** Langflow (local, `uv run langflow run`), calling Claude Haiku 5.5 (`claude-haiku-5-5`) via the Claude API

## Commands

```bash
# Database
docker compose up -d

# Backend (from backend/)
uvicorn app.main:app --reload
python -m app.seed --reset          # rebuild demo data with fixed seed
python -m app.seed --reset --empty-today  # seed without today's requests
pytest                               # run all tests
pytest tests/test_pricing.py        # run a single test file

# Frontend (from frontend/)
npm run dev
npm run build

# Langflow
uv run langflow run                  # opens at http://localhost:7860
```

## Non-negotiable rules

- **The model handles language; the backend handles numbers.** Never ask an LLM to compute prices, percentages, totals, or flags.
- **Money is always integer rupiah.** `BIGINT` in PostgreSQL, `int` in Python. Never use `float` for money.
- **"Today" means Asia/Jakarta timezone**, not UTC.
- **The frontend never calls Langflow or the Claude API directly.** All AI calls go through backend services only.
- **Secrets live only in `.env`.** Keep `.env.example` current; never commit `.env`.
- **`APP_NAME = "Procur.AI"` lives in one constant** in `backend/app/config.py`.

## Architecture

```
Browser → Backend (FastAPI) → PostgreSQL
                           → Langflow (Flow 1: Organize, Flow 2: Web check)
                           → Claude API (via Langflow only)
```

Langflow is called only from `backend/app/services/langflow_client.py` using the `run_flow(flow_id, text)` function.

## Key paths

| File | Purpose |
|---|---|
| `backend/app/services/checker.py` | Orchestrates match → price → flags → status per row |
| `backend/app/services/pricing.py` | Reference price (mean of last 3 purchases), diff_pct (1 decimal) |
| `backend/app/services/flags.py` | Pure flag functions with thresholds from config |
| `backend/app/services/matcher.py` | rapidfuzz `token_set_ratio`, threshold 85, normalizes units |
| `backend/app/services/langflow_client.py` | Only place that calls Langflow |
| `frontend/src/lib/format.ts` | Rupiah with `Intl.NumberFormat('id-ID')`, signed %, dates |

## Code style

- **Flag thresholds** live in config (not hardcoded in flag functions).
- **Every function in `pricing.py` and `flags.py` must have a pytest test.**
- **Never change seed numbers or test expectations** to make a test pass — fix the code.
- Web quotes are cached 7 days by normalized query; the backend returns the **median** (not mean) for web-sourced reference prices.
- Row status values: `pending`, `checked`, `new`, `flagged`, `approved`, `returned`.
- Flag codes: `PRICE_ABOVE_REF`, `STOCK_COVER_HIGH`, `QTY_UNUSUAL`, `NEW_SUPPLIER`.

## UI design

Match `design/reference.html` exactly. Token reference is in `plans/Procur.AI — Build Plan for IBM Bob.md`, section "UI spec". No gradients, shadows, emoji, or extra icons. Numbers always use **Geist Mono** with `font-variant-numeric: tabular-nums`.

## Scope per milestone

Work on one milestone at a time. For M3 (check engine) and M6 (Today screen), run Plan mode first, then open a new Agent conversation to implement. Start a new conversation for each milestone.
