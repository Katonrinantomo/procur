# Procur.AI — Project summary

_As of 30 Oct 2026 · branch `main` at `d90ddcd` ("Audit fixes: web price path, import checks, README")_

## What it is

Procur.AI is a web app that checks procurement prices. It was built as a hackathon demo for a manufacturing company that has no purchase database and unreliable stock records. Purchasing pastes the day's requests, often a messy WhatsApp message. The app turns that text into line items and checks each one against purchase history or live web prices. Rows that need a second look are flagged.

The core loop is **Organize → Check → Mark**:

1. **Organize.** Langflow Flow 1 uses Claude Haiku 5.5 to turn free text into structured rows: item, qty, unit, department, quoted price, and supplier.
2. **Check.** The backend fuzzy-matches each row to the catalog. A known item gets a reference price, which is the mean of its last 3 purchases. An unknown item goes to Langflow Flow 2, which searches the web; the reference price is then the **median** of the web quotes.
3. **Mark.** Backend rules set each row's status (`checked`, `new`, `flagged`, `pending`) and attach the reasons. A person then approves the row or returns it to the requester.

**Guiding rule:** the model handles language and the backend handles numbers. Python computes every price, percentage and flag. Money is always integer rupiah, and "today" means Asia/Jakarta time.

## Architecture

```
Browser (React) ──► FastAPI backend ──► PostgreSQL 16 (SQLite fallback)
                          │
                          ├──► Langflow Flow 1: Organize  ──► Claude Haiku 5.5
                          └──► Langflow Flow 2: Web Check ──► Claude Haiku 5.5 + DuckDuckGo
```

The browser talks only to the backend. Langflow is called only from `backend/app/services/langflow_client.py`.

| Layer | Stack |
|---|---|
| Frontend | React + Vite + TypeScript, Tailwind CSS v4, TanStack Query v5 |
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, httpx, rapidfuzz |
| Database | PostgreSQL 16 (Docker Compose); 8 tables: suppliers, items, purchases, stock, requests, request_items, web_quotes, flags |
| AI | Langflow (local, via `uv`), flows exported in `langflow/` |
| Tests | pytest, in-process SQLite: **189 passing** |

## Features (milestones M1–M15 shipped)

| Screen | What it does |
|---|---|
| **Today** | Queue of today's request rows, sorted Flagged → New → Checked, with filter chips. An inspector shows the reference price, diff %, flags, past purchases, web quotes and a supplier comparison. Each row can be approved, returned or rechecked. |
| **Add requests** | Paste text, preview the organized rows, then save. Saving runs the check engine. |
| **Quick check** | Dry-runs one item against history and web prices without saving anything. |
| **History** | Lists past request items, filtered by date range, status and supplier. Also shows purchase history per item. |
| **Excel import** | Uploads past purchases as `.xlsx` or `.csv` (5 MB max), with a downloadable template. |

### Flags (thresholds in `backend/app/config.py`)

| Code | Fires when |
|---|---|
| `PRICE_ABOVE_REF` | Quoted price is more than 15% above the reference |
| `STOCK_COVER_HIGH` | Stock on hand already covers more than 1 month of use |
| `QTY_UNUSUAL` | Qty is more than 2× the median past qty |
| `NEW_SUPPLIER` | The quoting supplier has never been used for this item |

Other settings: match threshold 85 (`token_set_ratio`), history window 3, web-quote cache 60 days.

### API

| Area | Endpoints |
|---|---|
| Requests and queue | `POST /api/requests/parse`, `POST /api/requests`, `GET /api/queue` |
| Request items | `GET /api/request-items[/{id}]`, `POST /api/request-items/{id}/approve`, `/return`, `/recheck` |
| Quick check | `POST /api/quick-check` |
| History and suppliers | `GET /api/purchases`, `/api/purchases/item/{id}`, `/api/items/{id}/suppliers`, `/api/suppliers` |
| Import | `POST /api/imports/purchases`, `GET /api/imports/purchases/template` |
| Health | `GET /api/health` |

## Code map

| Path | Role |
|---|---|
| `backend/app/services/checker.py` | Runs match → price → flags → status for each row, inside a savepoint |
| `backend/app/services/pricing.py` | Reference price and diff % |
| `backend/app/services/flags.py` | Pure flag functions |
| `backend/app/services/matcher.py` | Fuzzy catalog matching and unit normalization |
| `backend/app/services/web_check.py` | Web quotes (Flow 2) and the cache |
| `backend/app/services/organizer.py` | Text → line items (Flow 1) |
| `backend/app/services/xlsx_parser.py` | Excel/CSV purchase import |
| `backend/app/seed.py` | Demo data (`python -m app.seed --reset [--empty-today]`) |
| `frontend/src/components/` | Queue, Inspector, dialogs, and the History, Import and Quick check pages |
| `frontend/src/lib/format.ts` | Rupiah, signed %, and date formatting |
| `design/reference.html`, `design/quick-check.html` | Approved UI designs |
| `plans/` | Full build plan and per-milestone plans (M6, M7, M8) |
| `AUDIT.md` | Repo audit from 23 Oct 2026 |

## Demo story

Start from `python -m app.seed --reset --empty-today` and paste the 5-line WhatsApp message from the README.

- **Hydraulic oil** is flagged at **+29.5%**. It was quoted at Rp 1.450.000 against a last-3 average of Rp 1.120.000, which is Rp 1.320.000 over on 4 drums. It is also flagged for stock cover.
- **Solenoid valve** has no purchase history. It gets a web-quote median of Rp 425.000 and no flag.
- Return the oil row and approve the rest.

## Status against `AUDIT.md`

**Fixed in `d90ddcd`:**

- H1, H2, M1: the Quick check 500 error, the mismatched web-price lookups, and the Langflow config check
- M3: savepoint per row
- M2: import file type, size and decode checks
- H3: README rewrite
- M7: requirements pinned
- L1: cleanup of leftover frontend files
- L3: react-query moved to dependencies

**Still open:**

- **C2 (critical for the demo):** the seeded solenoid web quotes are still placeholder links (`tokopedia.com/a`, `shopee.co.id/b`, `lazada.co.id/c`) in `backend/app/seed.py` lines 593–595. Either capture real listings or label them as examples.
- **M4:** `token_set_ratio` alone lets short names like "valve" match the wrong item.
- **M5:** `dry_check_item` still duplicates `_do_check` in `checker.py`.
- **M6:** the Web Check flow's content length is very large, so calls are slow and costly.
- **L5:** `.bob/rules/procur.md` was not created; the rules live in `.bob/rules-{agent,ask,plan}/AGENTS.md` instead.
- **L6:** the Import page has no drag-and-drop zone (M16).
- **L7:** the Organize flow's unit list has no "yard".
- **Stretch goals not started:** Suppliers page, dark mode, mobile polish.
