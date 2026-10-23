# M7 — History Page Plan

## Overview

Build a real History page at `/history` (state-based routing, no React Router). The page has two tabs — **Purchases** and **Requests** — styled as filter chips. The Purchases tab surfaces the purchase database with filtering, pagination, item drill-down, and summary totals. The Requests tab shows request items from prior days with date/status filtering, reusing the existing `Inspector` component. Navigation is updated so Today, History, and Import each have their own route and show the active highlight correctly.

New seed data (10 past days of request items) is added for the Requests tab. Two new backend routers are added: `GET /api/purchases` and `GET /api/suppliers`. A new test file covers purchases filtering, paging, and totals.

---

## Sub-Tasks

### ST-1 — Seed 10 past request days

**Intent:** Populate the `requests` and `request_items` tables with 10 prior days of data (3–6 rows each, mixed statuses) so the Requests tab is non-empty without touching today's 5 demo rows.

**Expected Outcomes:**
- `python -m app.seed --reset` produces 10 new past Request rows with 3–6 RequestItems each, totalling 35–50 extra rows.
- Each row has a realistic mix of: `checked`, `flagged`, `approved`, `returned`, `new`.
- Statuses are set directly (not run through the check engine), using deterministic RNG.
- Today's 5 rows and all purchase/stock data are unchanged. All existing tests pass.

**Todo List:**
1. In `backend/app/seed.py`, add a new `_seed_past_requests(session, suppliers, items)` function.
2. Pick 10 dates spanning the last 90 days (e.g. today−5, −10, −18, −25, −32, −40, −50, −60, −72, −85).
3. For each date, create a `Request` record and 3–6 `RequestItem` rows using items from the existing catalog and suppliers.
4. Assign statuses directly using `RNG.choice(...)` from a weighted pool so all 6 statuses appear across the dataset (approved most common, then checked, then flagged, returned, new, pending rare).
5. For flagged rows, also insert a `Flag` record (code `PRICE_ABOVE_REF`, appropriate message).
6. Set `department`, `qty`, `unit`, `quoted_unit_price_idr`, `reference_unit_price_idr`, `diff_pct`, `checked_via`, `history_count`, `checked_at` on each item.
7. Call `_seed_past_requests(session, suppliers, items)` from the main `seed()` function, after `_seed_purchases_and_stock`.
8. Update `_print_summary` to show the new past request counts.
9. Run `python -m app.seed --reset` and verify total `request_items` count includes both past rows and today's 5.

**Relevant Context:**
- `backend/app/seed.py` — `_seed_today()` and `_seed_purchases_and_stock()` are the reference pattern.
- `backend/app/models.py` — `Request`, `RequestItem`, `Flag` models.
- `RNG = random.Random(42)` — use this for all random choices to keep seed deterministic.
- Status field: `pending | checked | new | flagged | approved | returned`.
- `jkt(d, hour, minute)` helper already exists for Jakarta-aware datetimes.

**Status:** [ ] pending

---

### ST-2 — Backend: `GET /api/purchases` and `GET /api/suppliers`

**Intent:** Add two new API endpoints that serve data for the History → Purchases tab.

**Expected Outcomes:**
- `GET /api/purchases?search=&supplier_id=&date_from=&date_to=&page=` returns `{ rows, total_count, total_amount_idr, page, page_size }` with 50 rows per page, newest first.
  - `search` matches against `items.name`, `items.aliases` (JSON contains), `suppliers.name`, and `purchases.po_number` (case-insensitive).
  - `supplier_id` filters by supplier FK.
  - `date_from` / `date_to` filter by `purchase_date` (Jakarta calendar day, inclusive).
  - Default date range is last 90 days.
  - Each row in `rows` includes: `id`, `purchase_date`, `po_number`, `item_id`, `item_name`, `supplier_id`, `supplier_name`, `qty`, `unit`, `unit_price_idr`, `total_idr` (qty × unit_price_idr).
- `GET /api/suppliers` returns `[{ id, name }]` sorted by name, for populating the dropdown.
- `GET /api/purchases/item/{item_id}` returns the last 10 purchases for that item plus a 3-buy average (`reference_price_idr`). This powers the side panel drill-down.

**Todo List:**
1. Add `PurchaseRow`, `PurchasesResponse`, `SupplierOption`, and `ItemPurchaseHistory` Pydantic schemas to `backend/app/schemas.py`.
2. Create `backend/app/routers/purchases.py` with three route functions.
3. For `GET /api/purchases`: build a SQLAlchemy query joining `purchases → items → suppliers`. Apply filters conditionally. Compute `total_amount_idr` as `SUM(qty * unit_price_idr)` over the filtered result set before paging. Return paginated rows.
4. For alias search: use `LIKE` on the JSON text representation of `items.aliases` (compatible with both SQLite and PostgreSQL).
5. For `GET /api/suppliers`: simple `SELECT id, name FROM suppliers ORDER BY name`.
6. For `GET /api/purchases/item/{item_id}`: return last 10 purchases + compute 3-buy average using the same `mean_of_last_n` logic from `pricing.py`.
7. Register `purchases.router` in `backend/app/main.py`.
8. Manually test with `curl` or the FastAPI docs UI.

**Relevant Context:**
- `backend/app/routers/queue.py` — pattern for query construction, pagination is new.
- `backend/app/services/pricing.py` — `mean_of_last_n` for 3-buy average.
- `backend/app/schemas.py` — existing schema patterns to follow.
- `backend/app/models.py` — `Purchase.unit_price_idr` is `BIGINT`; total is computed, not stored.
- AGENTS.md: money is always integer rupiah; no float money.

**Status:** [ ] pending

---

### ST-3 — Backend: `GET /api/request-items` (paginated history endpoint)

**Intent:** Add a paginated endpoint to list request items from any date range, not just today, to power the History → Requests tab.

**Expected Outcomes:**
- `GET /api/request-items?date_from=&date_to=&status=&page=` returns `{ rows, total_count, page, page_size }` with 50 rows per page, newest first.
- `date_from` / `date_to` filter by the parent `Request.requested_at` (Jakarta calendar day, inclusive); default last 90 days.
- `status` filters by `request_items.status`; omitted or `all` returns all statuses.
- Each row in `rows` matches the existing `QueueRow` schema (reused on the frontend).
- The existing `GET /api/request-items/{id}` route must not be broken (route ordering: specific `GET /api/request-items/{id}` is already in `request_items.py`; the new list endpoint goes in a new router or is carefully ordered).

**Todo List:**
1. Add `RequestItemsListResponse` schema to `backend/app/schemas.py` wrapping `list[QueueRow]` with `total_count`, `page`, `page_size`.
2. Create `backend/app/routers/request_items_list.py` (separate file to avoid conflicts with the existing `request_items.py` router).
3. Implement `GET /api/request-items` in the new router with date range + status filtering and pagination. Reuse the flag-code and web-quote-count lookup pattern from `queue.py`.
4. Register `request_items_list.router` in `backend/app/main.py`.
5. Verify the existing `GET /api/request-items/{id}` still resolves correctly (no route shadowing).

**Relevant Context:**
- `backend/app/routers/queue.py` — template for building `QueueRow` objects; reuse the same logic.
- The new list endpoint must exclude today's rows from the default view (date_to is yesterday, or the frontend filters it). Actually, the spec says "earlier days" — let frontend pass explicit dates; backend returns whatever the date range covers.
- FastAPI route ordering: put the `/api/request-items` (list, no path param) route BEFORE `/api/request-items/{id}` at registration time. The safest approach is a separate router file included before `request_items` in `main.py`.

**Status:** [ ] pending

---

### ST-4 — Tests: purchases filtering, paging, and totals

**Intent:** Add pytest tests for the two new purchases-related endpoints and the `_seed_past_requests` seed data.

**Expected Outcomes:**
- `tests/test_purchases.py` exists and all tests pass.
- Tests cover: unfiltered list (page 1, 50 rows max), `supplier_id` filter, `search` filter (item name hit, supplier name hit, PO number hit), `date_from`/`date_to` filter, paging (`page=2`), `total_amount_idr` accuracy, `GET /api/suppliers` returns all 8 suppliers, `GET /api/purchases/item/{id}` returns last-10 and correct 3-buy average.

**Todo List:**
1. Create `backend/tests/test_purchases.py`.
2. Use the `client` fixture pattern from `test_api.py` or create an analogous FastAPI `TestClient` fixture in `conftest.py` if one doesn't already exist.
3. Write parametrized or individual tests for each filter combination.
4. For `total_amount_idr`: independently compute expected total from DB in the test and assert equality.
5. Run `pytest tests/test_purchases.py -v` and fix any failures.

**Relevant Context:**
- `backend/tests/test_api.py` — see how the TestClient and session fixture are used together.
- `backend/tests/conftest.py` — `seeded_db` fixture; the test DB has the full seed including past requests from ST-1.

**Status:** [ ] pending

---

### ST-5 — Frontend: routing, nav highlight, and HistoryPage shell

**Intent:** Convert the tab-based navigation in `App.tsx` to URL-hash routing (`#today`, `#history`, `#import`) so each section has its own shareable URL, and create the `HistoryPage` component shell with its two sub-tabs.

**Expected Outcomes:**
- Navigating to `/#history` shows the History page; `/#today` shows Today; `/#import` shows Import.
- The active nav item in `AppHeader` is highlighted based on the URL hash, not an `activeTab` prop.
- Refreshing the page preserves the active tab.
- `HistoryPage` renders with two chip-style tabs: "Purchases" and "Requests"; default is Purchases.
- The page title row shows "History" in the same style as "Requests · {date}" on Today.
- No React Router dependency is added — use `window.location.hash` + `hashchange` event.

**Todo List:**
1. Update `AppHeader.tsx`: replace `activeTab` prop with hash-based detection (`window.location.hash === '#history'` etc.); `onTabChange` sets `window.location.hash`.
2. Update `App.tsx`: replace `activeTab` state with a `useHash()` hook that reads `window.location.hash` and listens for `hashchange`. Remove `activeTab` state. Map hash → rendered component. Set default hash to `#today` on first load if hash is empty.
3. Create `frontend/src/hooks/useHash.ts` — a minimal hook that returns the current hash and re-renders on change.
4. Create `frontend/src/components/HistoryPage.tsx` — outer shell with two chip tabs ("Purchases" / "Requests"), section title, and placeholder content panels for each.
5. Verify Import page still works (hash `#import`).

**Relevant Context:**
- `frontend/src/App.tsx` — current tab state; `activeTab === 'History'` maps to the (currently broken) history view.
- `frontend/src/components/AppHeader.tsx` — nav buttons loop over `['Today', 'History', 'Import']`; hash values are lowercase: `#today`, `#history`, `#import`.
- Chip tab style: border `1px solid #E0E0DB`, borderRadius `999px`, padding `6px 14px`, active state bg `#1A1A1A` text `#FFFFFF`, inactive bg transparent text `#4A4A46`.

**Status:** [ ] pending

---

### ST-6 — Frontend: Purchases tab

**Intent:** Build the Purchases tab UI — filters, summary line, paginated table, and item side-panel drill-down.

**Expected Outcomes:**
- Search box, supplier dropdown, date-range inputs (default last 90 days) render above the table.
- Summary line shows: "NNN purchases · N suppliers · Rp X total" for the current filter.
- Table columns: Date, PO no., Item, Supplier, Qty, Price/unit, Total. Newest first. 50 rows/page. Previous/Next pagination.
- Clicking an item name opens a right side panel showing that item's last 10 purchases and 3-buy average (using `GET /api/purchases/item/{item_id}`).
- All numbers in Geist Mono, `tabular-nums`. Amounts formatted with `formatRupiahWithPrefix`. Dates formatted with `formatDate`.
- Table and panel match the design: bordered container, `#F7F7F5` header row, 1px `#E6E6E2` border, 12px border-radius. Side panel uses the same split layout as `Inspector`.

**Todo List:**
1. Create `frontend/src/hooks/usePurchases.ts` — wraps `GET /api/purchases` with TanStack Query, accepts filter + page params.
2. Create `frontend/src/hooks/useSuppliers.ts` — wraps `GET /api/suppliers`.
3. Create `frontend/src/hooks/useItemPurchaseHistory.ts` — wraps `GET /api/purchases/item/{item_id}`, enabled only when an id is selected.
4. Add TypeScript interfaces for the new API responses to `frontend/src/types/api.ts`: `PurchaseRow`, `PurchasesResponse`, `SupplierOption`, `ItemPurchaseHistory`.
5. Create `frontend/src/components/PurchasesTab.tsx` — main Purchases tab component with state for filters (search, supplierId, dateFrom, dateTo, page) and selected itemId for the side panel.
6. Within `PurchasesTab`: render filter controls, summary line, purchases table, pagination row, and conditional side panel.
7. Create `frontend/src/components/ItemPurchasePanel.tsx` — right-side panel showing last 10 purchases in a table + 3-buy average row. Uses the same bordered split layout. Close button in top-right corner.
8. Wire `PurchasesTab` into `HistoryPage` as the default active sub-tab.

**Relevant Context:**
- `frontend/src/components/HistoryTable.tsx` — pattern for a purchases mini-table; reuse the same column/style approach.
- `frontend/src/hooks/useQueue.ts` — pattern for a TanStack Query hook.
- `frontend/src/lib/format.ts` — `formatRupiahWithPrefix`, `formatDate`.
- Design: filter row uses `<input type="date">` with `border: 1px solid #E0E0DB; borderRadius: 8px; height: 36px; padding: 0 10px; font: inherit; fontSize: 14px`.

**Status:** [ ] pending

---

### ST-7 — Frontend: Requests tab

**Intent:** Build the Requests tab UI — date filter, status chips, paginated table of prior-day request items, and Inspector integration.

**Expected Outcomes:**
- Date-range filter (default last 90 days) and status chips (All, Flagged, New, Checked, Approved, Returned) render above the table.
- Table columns: Date, Item, Dept., Qty, Quoted/unit, Reference/unit, Diff., Status. Newest first. 50 rows/page. Previous/Next pagination.
- Clicking a row opens the existing `Inspector` component (reused, not duplicated). The inspector appears below the table (full-width, same as Today screen).
- All formatting, chip styles, and table styles match Today screen exactly.
- Today's rows are excluded from the default view (date_to = yesterday).

**Todo List:**
1. Create `frontend/src/hooks/useRequestHistory.ts` — wraps `GET /api/request-items` (the new list endpoint from ST-3) with TanStack Query, accepts date range + status + page params. Default `date_to` = yesterday (Jakarta).
2. Add `RequestItemsListResponse` TypeScript interface to `frontend/src/types/api.ts`.
3. Create `frontend/src/components/RequestsTab.tsx` — component with state for dateFrom, dateTo, activeStatus, page, and selectedId.
4. Within `RequestsTab`: render date range inputs, status chips using the same `FilterChips` component (or inline chip style), a request items table, pagination, and the `Inspector` component below.
5. The request items table re-uses the same columns and row styles as `QueueTable`. Create a lightweight `RequestHistoryTable` component or reuse `QueueTable` (check if it can accept the same `QueueRow[]` type — it can).
6. Wire `RequestsTab` into `HistoryPage` as the second sub-tab.
7. On initial load, auto-select the first row (same as Today screen does).

**Relevant Context:**
- `frontend/src/components/QueueTable.tsx` — existing table component that accepts `QueueRow[]`; try to reuse it directly.
- `frontend/src/components/FilterChips.tsx` — existing chip component; the Requests tab adds Approved and Returned chips beyond today's All/Flagged/New/Checked set.
- `frontend/src/components/Inspector.tsx` — accepts `RequestItemDetail | undefined` and `isLoading: boolean`; no changes needed.
- `frontend/src/hooks/useRequestItem.ts` — used as-is for the detail fetch when a row is selected.

**Status:** [ ] pending

---

## Key Constraints

- **Money is always integer rupiah.** `total_idr` is computed as `qty * unit_price_idr` in Python (both integers). Never use float for money.
- **"Today" means Asia/Jakarta.** All date comparisons on `purchase_date` and `requested_at` use Jakarta midnight bounds.
- **No new npm dependencies.** Hash routing with `window.location.hash` only.
- **Reuse existing components.** `Inspector`, `QueueTable`, `FilterChips`, `StatusChip`, `HistoryTable`, `SkeletonRow` — do not duplicate.
- **Seed is deterministic.** `RNG = random.Random(42)` — all new `_seed_past_requests` choices use this RNG. Existing demo row numbers must not change.
- **Route ordering.** `GET /api/request-items` (list) must be registered before `GET /api/request-items/{id}` in FastAPI to avoid the list path being captured as an `item_id`.
- **Alias search on SQLite.** Use `LIKE '%"term"%'` on the JSON text column — full-text JSON search is not needed; simple LIKE works for the demo.

## Implementation Order

ST-1 → ST-2 → ST-3 → ST-4 → ST-5 → ST-6 → ST-7

Each ST is a single agent conversation turn. After ST-1, run `pytest` to confirm nothing breaks. After ST-4, all backend work is done. After ST-7, do a full end-to-end smoke test.
