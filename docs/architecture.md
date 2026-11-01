# Architecture

## System overview

```
Browser (React SPA, :5173)
   │  /api/*  (Vite proxy, JWT bearer)
   ▼
Backend (FastAPI, :8000) ──────────────► PostgreSQL 16 (:5432)
   │
   │  services/langflow_client.py  (only module that talks to Langflow)
   ▼
Langflow (:7860)
   ├── Organize      → organize_json                      ──► Claude Haiku 5.5
   ├── maker_agent   → extract_json, maker_json, serper_raw ──► Claude Haiku 5.5 + Serper
   └── Web Check     → webcheck_json (legacy, flowcheck only)
```

All three services bind to localhost. The frontend never calls Langflow or the Claude API; the Claude API key lives in Langflow's Model Providers settings, not in the backend.

## Components

| Component | Responsibility |
|---|---|
| `frontend/` | Hash-routed SPA (`#today`, `#review`, `#quick-check`, `#vendor-quotes`, `#history`, `#import`, `#audit`). Shows tabs by role (`lib/roles.ts`) but the backend enforces every rule. `lib/api.ts` attaches the JWT and forces re-login on 401. |
| `app/main.py` | App factory: CORS (Vite origin only), `TrustedHostMiddleware`, security headers (CSP, `X-Frame-Options: DENY`, `nosniff`), slowapi rate limiter, router registration, startup validation of settings. |
| `app/routers/` | Thin HTTP layer: parse input, enforce role, call a service, shape the response. |
| `app/services/checker.py` | The check engine: match → reference price → diff → flags → risk score → status, per row. |
| `app/services/pricing.py` | Reference prices, `diff_pct`, price bands, recommendation, vendor score. |
| `app/services/flags.py` | Four pure flag rules plus the composite risk score. |
| `app/services/matcher.py` | Name normalization (units, punctuation) and fuzzy catalog matching. |
| `app/services/web_check.py` | Web reference for unmatched items: 60-day quote cache, else maker_agent in `MODE: BON`. |
| `app/services/maker.py` + `evidence.py` | Run maker_agent, join its two model outputs by `line_no`, and drop any listing the raw search results don't support. |
| `app/services/quotation.py` | Vendor quotation check: PDF/XLSX text extraction, maker_agent in `MODE: PENAWARAN`, per-line band and recommendation, vendor score. |
| `app/services/decisions.py` | Override rules, decision snapshot, the single writer of `audit_log` rows. |
| `app/flows/contracts.py` | Pydantic model per flow output, output component names, JSON parser with one repair retry. |
| `app/flowcheck.py` | Runs every fixture in `langflow/fixtures/<flow>/` through the live flows and validates against the contracts. |

## Data flow

### Adding requests (`#today` → Add requests)

1. `POST /api/requests/parse` sends the pasted text to the Organize flow. `organizer.parse_text` validates `{"items": [...]}` against `OrganizeOut`; if it fails, the flow is re-run once with the validation error appended. Nothing is saved.
2. The user reviews and edits the draft rows, then `POST /api/requests` saves a `Request` and its `RequestItem` rows, resolves supplier names to IDs and runs `check_request`.
3. For each row, `check_item` runs inside a savepoint:
   - **Match** — `match_item` normalizes the name (`"20 liter"` → `"20l"`) and requires `token_set_ratio ≥ 85` **and** `token_sort_ratio ≥ 70` against the item name and its aliases.
   - **Reference** — matched item with history → mean of the last `HISTORY_WINDOW` (3) purchases, `checked_via="history"`. Otherwise `get_web_quotes` → median of kept quotes, only if at least `WEB_MIN_QUOTES` (3) exist, `checked_via="web"`.
   - **Diff** — `(quoted − reference) / reference × 100`, 1 decimal.
   - **Flags** — `PRICE_ABOVE_REF` (> 15%), `STOCK_COVER_HIGH` (stock > 1 month of use), `QTY_UNUSUAL` (> 2× median past qty), `NEW_SUPPLIER` (named supplier with no purchases).
   - **Risk score** — flag weights (30/20/15/10) + up to 20 points from `|diff_pct|`, capped at 100.
   - **Status** — `flagged` if any flag, `checked` if history-based, else `new`. `approved` / `returned` are never overwritten.
   - On a Langflow failure the row is saved as `pending` with `check_error`; any other exception rolls back the savepoint and stores a generic message. Failures never propagate to the request.

### Web reference (`web_check.get_web_quotes`)

```
normalized name ──► cache: web_quotes with item_key match (exact or fuzzy ≥ 85),
                    a URL, fetched ≤ WEB_QUOTE_MAX_AGE_DAYS (60) ago
                      │ hit → reuse
                      │ miss
                      ▼
                    maker_agent "MODE: BON" ──► extract_json + maker_json + serper_raw
                      ▼
                    evidence guards (per line_no) ──► kept listings (max 5) saved as web_quotes
```

A listing is kept only if its URL is a safe public http(s) URL, the URL appears in `serper_raw` for the same line, that result is a product page (not a marketplace search page), and the claimed price appears in that result's title/snippet/price. `pack_qty` converts a pack price to a per-unit price in Python. On Langflow failure, stale quotes are returned together with the error.

### Vendor quotation (`#vendor-quotes`)

`POST /api/quotations` accepts a `.pdf` or `.xlsx` (magic bytes checked, 10 MB max), extracts text (pdfplumber / openpyxl, capped at 30 000 chars) and runs maker_agent in `MODE: PENAWARAN`. For every line the backend picks a reference (history first, then web median), computes the band (`KOMPETITIF ≤ −10% < WAJAR ≤ +5% < PERHATIAN ≤ +15% < TIDAK WAJAR`), the recommendation (`SETUJU` / `NEGOSIASI` / `TOLAK` above +30%) and the vendor score (80% value-weighted band points + 20 points if every line total and the document total recompute within Rp 1). `POST /api/quotations/{id}/to-queue` turns the checked lines into a request on the queue.

### Decisions (`#review`)

Only `owner` approves or returns rows, and never on a request they created. Approving a flagged row or one with `risk_score ≥ 50` is an **override**: a reason and an outcome tag (`false_alarm` | `risk_accepted`) are required. Returning always needs a reason. Each decision writes one `audit_log` row with a snapshot of what the decider saw (flags, risk score, reference price and source). An ORM event (`models._audit_log_append_only`) rejects updates and deletes of audit rows.

## Patterns

- **Layered: routers → services → models.** Routers own HTTP and authorization; services own logic and never import FastAPI; `models.py` owns persistence.
- **Pure functions for rules.** `flags.py`, most of `pricing.py` and all of `evidence.py` take plain values and return plain values, so each rule is unit-tested without a database or network.
- **Contracts at the AI boundary.** Every flow output has a Pydantic model; money fields are `int`. One repair retry, then `FlowContractError` (a `LangflowError`), which callers already map to `502` or a `pending` row.
- **Single gateway.** `langflow_client.run_flow(flow_id, text)` is the only HTTP client for Langflow: fresh `session_id` per call, 60 s timeout, 3 attempts with backoff, no retry on 401/403. Outputs are returned as `{component display name: text}` so one flow can expose several named outputs.
- **Savepoint per row.** One bad row cannot fail a whole request.

## Database

PostgreSQL 16 (SQLite works through `DATABASE_URL` and is what the tests use). Schema is managed by Alembic (`backend/alembic/versions/`).

| Table | Holds |
|---|---|
| `items` | Catalog: name, JSON `aliases`, category, unit |
| `suppliers` | Supplier names (unique), phone, city |
| `purchases` | History: date, PO number, item, supplier, qty, `unit_price_idr` (`BIGINT`), source (`seed` / `excel` / `csv`) |
| `stock` | `qty_on_hand`, `avg_monthly_use` per item |
| `requests` / `request_items` | Incoming requests and their checked lines (reference, `diff_pct NUMERIC(8,1)`, `checked_via`, status, `risk_score`, `check_error`) |
| `flags` | Flag code + message per request item, rebuilt on every check |
| `web_quotes` | Marketplace listings; `item_key` is the normalized name used as the cache key; `request_item_id` is nullable so quotes can exist as cache rows |
| `quotations` / `quotation_lines` | Uploaded vendor quotes, per-line band/recommendation, JSON `evidence` and `dropped` listings |
| `users` | Username, PBKDF2 hash, role (`purchasing` / `owner` / `finance`) |
| `audit_log` | Append-only decision log with JSON `snapshot` |
| `actions` | One row per approve/return with its note, written alongside the audit row |

Money is always integer rupiah (`BIGINT` / `int`). "Today" is computed in Asia/Jakarta (UTC+7) for the queue, history filters and decision date ranges.

## Security

- JWT (HS256, stdlib implementation, 1 hour) signed with `JWT_SECRET` (≥ 32 chars, startup fails otherwise); passwords hashed with PBKDF2-HMAC-SHA256, 600 000 iterations.
- Role checks via `require_roles(...)`; ownership checks in handlers (recheck, to-queue, self-approval).
- Rate limits: login 5/min, every LLM-touching endpoint 10/min per IP.
- `safe_http_url` rejects non-http schemes, private/loopback/link-local IPs and `localhost` before any URL is stored or shown.
- Uploads: extension + magic bytes + size limit.
- `seed --reset` refuses to run against a non-localhost database or `APP_ENV=production` without `--i-know-what-i-am-doing`.
