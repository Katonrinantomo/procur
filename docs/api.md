# API

Base URL `http://localhost:8000`. Interactive OpenAPI docs at `/docs`. All bodies are JSON unless noted. Money fields (`*_idr`) are integer rupiah; `diff_pct` is a 1-decimal percentage.

## Authentication

```http
POST /api/auth/login
{"username": "owner", "password": "password123"}
```

```json
{"access_token": "eyJ...", "token_type": "bearer", "role": "owner", "username": "owner"}
```

Send `Authorization: Bearer <token>` on every other `/api` call except `/api/health`. Tokens expire after 1 hour. Login is limited to 5 requests/minute per IP.

| Role | Can |
|---|---|
| `purchasing` | Parse/add requests, quick check, upload quotations and queue them, import purchase history, recheck rows from requests they entered |
| `owner` | Add requests, recheck any row, approve/return (not on requests they entered), Review page, decision log, flow health |
| `finance` | Read queue/history/purchases, decision log, audit log |

Every role can read the queue, request items, purchases, suppliers and quotations.

## Endpoints

### Health

| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/api/health` | none | `{"status": "ok", "app": "Procur.AI", "langflow": "ok" \| "down" \| "not configured"}` |
| GET | `/api/health/flows` | owner | Langflow reachability, `configured` per flow, last `flowcheck` result (`at`, `ok`, `failed` fixtures) |

### Requests and the queue

| Method | Path | Role | Description |
|---|---|---|---|
| POST | `/api/requests/parse` | purchasing, owner | Organize pasted text into draft lines. Saves nothing. 10/min. |
| POST | `/api/requests` | purchasing, owner | Save a request, run the check engine, return the rows (201) |
| GET | `/api/queue?date=YYYY-MM-DD&status=` | any | Rows for one Jakarta day (default today), sorted flagged → new → checked → approved → returned → pending, plus counts per status |
| GET | `/api/request-items?date_from=&date_to=&status=&page=` | any | Paginated history (50/page, default last 90 days) |
| GET | `/api/request-items/{id}` | any | Full detail: reference, totals, stock, flags, last purchases or web quotes, decisions, `override_required` |
| POST | `/api/request-items/{id}/recheck` | purchasing (own), owner | Re-run the check engine on one row. 10/min. |
| POST | `/api/request-items/{id}/approve` | owner | `{"reason"?, "outcome_tag"?}` — both required when `override_required` |
| POST | `/api/request-items/{id}/return` | owner | `{"reason"}` required (`note` accepted as the old name) |
| GET | `/api/review` | owner | Every undecided row (`flagged`, `new`, `checked`) across dates: flagged first, then risk score descending |

**Parse**

```http
POST /api/requests/parse
{"text": "1. Hydraulic oil ISO VG 46, 20L – 4 drum, Warehouse, Rp 1.450.000/drum, CV Sinar Pelumas", "requested_by": "Budi"}
```

```json
[{"name": "Hydraulic oil ISO VG 46, 20L", "qty": 4, "unit": "drum", "department": "Warehouse",
  "quoted_unit_price_idr": 1450000, "supplier": "CV Sinar Pelumas"}]
```

`text` is limited to 10 000 characters.

**Save**

```http
POST /api/requests
{
  "requested_by": "Budi",
  "raw_text": "…original message…",
  "items": [
    {"line_no": 1, "raw_name": "Hydraulic oil ISO VG 46, 20L", "qty": 4, "unit": "drum",
     "department": "Warehouse", "quoted_unit_price_idr": 1450000,
     "quoting_supplier_name": "CV Sinar Pelumas"}
  ]
}
```

Response: a list of queue rows.

```json
[{"id": 41, "request_id": 9, "line_no": 1, "raw_name": "Hydraulic oil ISO VG 46, 20L",
  "qty": 4, "unit": "drum", "quoted_unit_price_idr": 1450000,
  "reference_unit_price_idr": 1120000, "diff_pct": 29.5, "checked_via": "history",
  "history_count": 3, "web_quote_count": null, "status": "flagged",
  "flag_codes": ["PRICE_ABOVE_REF", "STOCK_COVER_HIGH"], "risk_score": 70, "...": "..."}]
```

`checked_via` is `history`, `web` or `none`. Status values: `pending`, `checked`, `new`, `flagged`, `approved`, `returned`. Flag codes: `PRICE_ABOVE_REF`, `STOCK_COVER_HIGH`, `QTY_UNUSUAL`, `NEW_SUPPLIER`.

**Approve an override**

```http
POST /api/request-items/41/approve
{"reason": "Supplier price rose after fuel surcharge; confirmed by phone", "outcome_tag": "risk_accepted"}
```

`outcome_tag` is `false_alarm` or `risk_accepted`, and is rejected on non-override approvals and on returns.

### Quick check

| Method | Path | Role | Description |
|---|---|---|---|
| POST | `/api/quick-check` | purchasing | `{"text"}` (≤ 5 000 chars). Organize + dry-run check; writes no request rows (web quotes may be cached). 10/min. |

Returns one result per parsed line with `reference_unit_price_idr`, `checked_via`, `diff_pct`, `flags` (`[{code, message}]`), `status`, `last_purchases` (history path) or `web_quotes` (web path), and `check_error` if the web check failed.

### Vendor quotations

| Method | Path | Role | Description |
|---|---|---|---|
| POST | `/api/quotations` | purchasing | Multipart `file` (`.pdf` with a text layer or `.xlsx`, ≤ 10 MB). Runs the quotation check (201). 10/min. |
| GET | `/api/quotations` | any | Summaries: id, filename, status, vendor, `vendor_score`, created_at |
| GET | `/api/quotations/{id}` | any | Full result: vendor fields, `vendor_score`, `price_points`, `arithmetic_ok`, `covered_lines`/`total_lines`, `dropped_summary`, and per line `reference_source`, `diff_pct`, `band`, `recommendation`, `evidence`, `dropped` |
| POST | `/api/quotations/{id}/to-queue` | purchasing (uploader only) | Turn the checked lines into a request on the queue (201) |

```powershell
curl.exe -H "Authorization: Bearer $t" -F "file=@quote.pdf" http://localhost:8000/api/quotations
```

`band`: `KOMPETITIF`, `WAJAR`, `PERHATIAN`, `TIDAK WAJAR`, `UNKNOWN`. `recommendation`: `SETUJU`, `NEGOSIASI`, `TOLAK` or null.

### Purchases, items, suppliers

| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/api/purchases?search=&supplier_id=&date_from=&date_to=&page=` | any | Paginated purchase history (50/page); `search` matches item name, aliases, supplier, PO number |
| GET | `/api/purchases/item/{item_id}` | any | One item's purchase history |
| GET | `/api/suppliers` | any | Supplier options for filters |
| GET | `/api/items/{item_id}/suppliers` | any | Per supplier: last unit price, last purchase date, buy count; cheapest first |

### Import

| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/api/imports/purchases/template` | any | `procur-purchases-template.xlsx` (header + 2 example rows) |
| POST | `/api/imports/purchases` | purchasing | Multipart `file`, `.xlsx` or `.csv`, ≤ 5 MB |

Columns: `date, po_number, supplier, item, qty, unit, unit_price_idr`. XLSX also accepts Indonesian headers (`tanggal`, `no_po`, `pemasok`/`vendor`, `barang`/`nama_barang`, `jumlah`, `satuan`, `harga_satuan`/`harga`). Unknown items become new catalog items, unknown suppliers are created, and a line whose `po_number` + item already exists is skipped.

```json
{"inserted": 120, "skipped": 3, "new_items": 4, "new_suppliers": 1,
 "errors": [{"line": 17, "message": "..."}]}
```

`line` is the spreadsheet row number (header = row 1).

### Decision and audit logs

| Method | Path | Role | Description |
|---|---|---|---|
| GET | `/api/decisions?from=&to=&subject_type=` | owner, finance | Decision log, newest first; `from`/`to` are Jakarta days, inclusive. Each row has `decision`, `reason`, `outcome_tag`, `username`, `role`, `snapshot` |
| GET | `/api/decisions.csv?from=&to=&subject_type=` | owner, finance | Same rows as CSV (`decisions_<from>_<to>.csv`) |
| GET | `/api/audit-logs` | owner, finance | Request-item audit rows: item name, actor role, action, note, time |

## Errors

Errors use FastAPI's shape: `{"detail": "..."}` (validation errors: `{"detail": [ ... ]}`).

| Status | When |
|---|---|
| 400 | Wrong file extension, bad magic bytes, CSV not UTF-8 |
| 401 | Missing, invalid or expired token; inactive user; wrong login |
| 403 | Role not allowed; approving/returning your own request; recheck/to-queue on someone else's row |
| 404 | Unknown request item or quotation |
| 409 | Quotation already on the queue |
| 413 | Upload over 5 MB (import) or 10 MB (quotation) |
| 422 | Body validation; decision missing a required reason or outcome tag; quotation has no checked lines |
| 429 | Rate limit exceeded |
| 502 | Organize flow not configured, unreachable or returned invalid output after the repair retry (`/api/requests/parse`, `/api/quick-check`) |

A failed web check or quotation check is **not** an HTTP error: the row or quotation is saved with `status: "pending"` and `check_error`, and can be rechecked.
