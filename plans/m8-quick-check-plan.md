# M8 — Quick Check Page

## Overview

Add a `/quick-check` page (`#quick-check` hash route) that lets a procurement officer type one item line
and instantly see price, flags, and history — all without saving anything to the database.

**Scope:**
- `POST /api/quick-check` — dry-run check endpoint (no DB writes)
- `checker.py` dry-run path via a shared `_do_check_dry` function
- A new `QuickCheckPage` React component
- Nav update: add "Quick check" tab between "Today" and "History"
- One pytest test that calls the oil item text and asserts flagged + 2 flags + no DB writes

**Non-goals:** pagination, multi-item results, saving directly from the quick-check endpoint.

---

## Architecture

```
User types text
  → POST /api/quick-check { text }
      → organizer.parse_text(text)         (Organize flow → list[LineItemDraft])
      → for each draft:
            dry_check_item(draft, session)  (match → price → flags → status, no writes)
      → return list[QuickCheckResult]
  ← Frontend renders one ResultCard per item
```

`dry_check_item` lives in `checker.py` alongside `_do_check`.  It accepts a draft dict
(not a real `RequestItem` ORM row) and a read-only session, reuses the exact same service
calls (`match_item`, `reference_from_history`, `get_web_quotes`, `pricing`, `flag_rules`),
and returns a plain `QuickCheckResult` dataclass / dict — it never writes, never flushes.

The web-quote cache may still be read (and populated) because `get_web_quotes` writes
`WebQuote` rows.  That side effect is acceptable (it's a price-data cache, not a request
record) and is consistent with the "nothing is saved until you add it to the queue" promise
shown in the design.  Only `Request`, `RequestItem`, and `Flag` rows must NOT be created.

---

## Sub-Tasks

---

### ST-1 — Backend: `dry_check_item` in `checker.py`

**Status:** [ ] pending

**Intent**
Extract the logic of `_do_check` into a new public function `dry_check_item` that accepts
a plain data container instead of a live ORM row, runs the same pipeline, and returns a
result dict.  The existing `check_item` / `_do_check` flow must continue to work unchanged.

**Expected Outcomes**
- `dry_check_item(draft, session) → dict` exists in `checker.py`
- It performs: match → reference price (history or web) → diff_pct → flags → status
- It never calls `session.flush()` or `session.add(Flag(...))`  
- It never creates any ORM rows
- All existing check-engine tests still pass

**Todo List**
1. Define a `DryCheckDraft` typed dict or dataclass in `checker.py` with fields:
   `raw_name, qty, unit, quoted_unit_price_idr, quoting_supplier_name, supplier_id`
2. Write `dry_check_item(draft: DryCheckDraft, session: Session) -> dict`:
   - Match: call `match_item(draft["raw_name"], session)` → `item`
   - Reference: try `reference_from_history` (if item matched), else call `get_web_quotes`
     via a minimal shim: since `get_web_quotes` takes a `RequestItem`, create a
     **transient** (not added to session) `RequestItem` in-memory object to pass to it,
     then read back the `item_key` to call `pricing.reference_from_web`
   - diff_pct, flags (same 4 rules), status — no ORM writes
   - Return dict matching the `QuickCheckResult` Pydantic schema
3. Keep `_do_check` unchanged; it remains the path for saved rows.

**Relevant Context**
- [`backend/app/services/checker.py`](backend/app/services/checker.py) — `_do_check` is the template
- [`backend/app/services/web_check.py`](backend/app/services/web_check.py:120) — `get_web_quotes` takes a `RequestItem`; the transient trick works because the function only reads `raw_name` and `request_item_id` (the latter is `None` for new rows, which is valid)
- [`backend/app/services/pricing.py`](backend/app/services/pricing.py) — `reference_from_web` accepts `request_item_id=None` when an `item_key` is passed
- Flag rules in [`backend/app/services/flags.py`](backend/app/services/flags.py) are pure functions — safe to call without ORM rows

**Implementation note on the transient RequestItem shim**
`get_web_quotes` calls `request_item.raw_name` and later does `request_item.check_error = msg`
and `session.flush()`.  For the dry-run, pass `request_item_id=None` shim:
```python
shim = RequestItem(raw_name=draft["raw_name"])  # not added to session
# After the call, check shim.check_error for Langflow failure
```
Because the shim is never `session.add`-ed, `session.flush()` inside `get_web_quotes` will
not attempt to INSERT it.  The `check_error` field set on the shim is readable as a plain
Python attribute.

---

### ST-2 — Backend: `QuickCheckResult` schema + `/api/quick-check` router

**Status:** [ ] pending

**Intent**
Define a rich Pydantic response schema and a new FastAPI router that calls `parse_text`
then `dry_check_item` for each draft.

**Expected Outcomes**
- `POST /api/quick-check { text: str }` returns `list[QuickCheckResult]` (200) or 502 on Langflow error
- Each result contains all fields the frontend needs for the three-row card
- Router is registered in `main.py`
- No writes to `requests` or `request_items` tables

**Todo List**
1. Add `QuickCheckResult` to `backend/app/schemas.py`:
   ```
   raw_name: str
   name: str                        # catalog item name, or raw_name if unmatched
   catalog_item_id: int | None
   category: str | None             # catalog item category
   qty: int | None
   unit: str | None
   department: str | None
   quoted_unit_price_idr: int | None
   quoting_supplier_name: str | None
   history_count: int               # 0 if no history
   last_purchases: list[PurchaseOut]  # last 3 (empty if web/none)
   web_quotes: list[WebQuoteOut]    # (empty if history/none)
   reference_unit_price_idr: int | None
   checked_via: str                 # "history" | "web" | "none"
   diff_pct: float | None
   flags: list[FlagOut]
   status: str
   check_error: str | None
   ```
2. Create `backend/app/routers/quick_check.py` with `POST /api/quick-check`:
   - Body: `{ text: str }`
   - Call `await parse_text(text)` — returns `list[LineItemDraft]`
   - For each draft, resolve `supplier_id` from name (same pattern as `create_request`),
     build a `DryCheckDraft`, call `dry_check_item(draft, db)`
   - Build and return `list[QuickCheckResult]`
   - On `LangflowError` from `parse_text`: return HTTP 502
   - On `check_error` set during `dry_check_item`: include it in the result (not a 502);
     the frontend shows an inline "Retry" option
3. Register the router in `main.py`

**Relevant Context**
- [`backend/app/routers/requests.py`](backend/app/routers/requests.py) — exact pattern to follow for supplier resolution and error handling
- [`backend/app/schemas.py`](backend/app/schemas.py) — `PurchaseOut`, `WebQuoteOut`, `FlagOut` already exist and can be reused
- [`backend/app/main.py`](backend/app/main.py) — register with `app.include_router(quick_check.router)`

---

### ST-3 — Backend: populate `last_purchases` in `dry_check_item`

**Status:** [ ] pending

**Intent**
When `checked_via == "history"`, the result must include the last 3 purchase records
(supplier name, date, price) so the frontend can render the "Check" row.

**Expected Outcomes**
- `last_purchases` in `QuickCheckResult` contains up to 3 `PurchaseOut` items when `checked_via == "history"`
- `web_quotes` contains the quote records when `checked_via == "web"`
- Both are empty lists when `checked_via == "none"`

**Todo List**
1. After computing `ref_price` via history, query the last 3 purchases for `item.id` with their supplier names — same query pattern as in the `RequestItemDetail` endpoint in `request_items.py`
2. After computing `ref_price` via web, read the `WebQuote` rows for the item key from the session
3. Pack these into the return dict as `last_purchases` and `web_quotes`

**Relevant Context**
- [`backend/app/routers/request_items.py`](backend/app/routers/request_items.py) — see how `last_purchases` is built for `RequestItemDetail`
- [`backend/app/models.py`](backend/app/models.py:66) — `Purchase` model has `purchase_date`, `unit_price_idr`, `supplier_id`; join to `Supplier.name`

---

### ST-4 — Backend: pytest test for dry-run

**Status:** [ ] pending

**Intent**
Verify that running `dry_check_item` on the oil item produces the expected flags and
writes nothing to the database.

**Expected Outcomes**
- Test: `dry_check_item` with oil item data → `status == "flagged"`, flags include `PRICE_ABOVE_REF` and `STOCK_COVER_HIGH`
- Test: no new `RequestItem` rows exist after the call (DB row count unchanged)
- Test: no new `Flag` rows exist after the call

**Todo List**
1. Add `tests/test_quick_check.py`
2. Use the existing `session` fixture from `conftest.py` (rollback after each test)
3. Seed the draft manually: `raw_name="oli hidrolik 46 20L"`, `qty=4`, `unit="drum"`, `quoted_unit_price_idr=1_450_000`, `quoting_supplier_name="CV Sinar Pelumas"`, `supplier_id=None`
4. Look up the real supplier_id from session if needed (same as seed data)
5. Call `dry_check_item(draft, session)` and assert `result["status"] == "flagged"`
6. Assert `"PRICE_ABOVE_REF"` and `"STOCK_COVER_HIGH"` in `[f["code"] for f in result["flags"]]`
7. Assert `session.query(RequestItem).count()` is unchanged from before the call
8. Assert `session.query(Flag).count()` is unchanged from before the call

**Relevant Context**
- [`backend/tests/conftest.py`](backend/tests/conftest.py) — `session` fixture pattern
- [`backend/tests/test_check_engine.py`](backend/tests/test_check_engine.py) — test patterns

---

### ST-5 — Frontend: `QuickCheckPage` component

**Status:** [ ] pending

**Intent**
Build the full Quick Check page matching `design/quick-check.html` exactly.

**Expected Outcomes**
- `frontend/src/components/QuickCheckPage.tsx` exists
- Form: pill-shaped input + "Check" button; Enter submits; example chips fill the input
- Chips: `bearing 6205 ZZ 20 pcs @38.500`, `solenoid valve 24V DC 1/2" 2 pcs`, `lakban bening 48mm 3 dus @210rb`
- While waiting: show "Checking…" text where the result cards will appear
- One result card per item returned from `POST /api/quick-check`
- Each card shows:
  - Header: "Bought N times before" (or "New item") · item name · status chip
  - Organize row: `category · qty unit · Rp price per unit · quoted by supplier`
  - Check row: history narrative OR web narrative OR "No price reference found"
  - Mark row: flag box (from `Inspector.tsx` pattern) OR "Looks normal" in Checked chip style
  - Buttons: "Add to today's queue" / "See purchase history"
- Langflow error: inline error message + Retry button (re-submits the form)
- No external data fetching libraries needed beyond `fetch`; plain `useState` + `useEffect` pattern

**Formatting rules (from `format.ts`)**
- Rupiah: `formatRupiahWithPrefix` for standalone prices, `formatRupiah` inside narrative text
- Percent: `formatPct`
- Date: `formatDate`
- Numbers: Geist Mono, `font-variant-numeric: tabular-nums`

**Check row narrative**
- `checked_via == "history"` and `last_purchases.length > 0`:
  `Last N buys averaged Rp X (SupA ×2, SupB ×1). Last bought D.`
  Where N = `history_count`, X = `reference_unit_price_idr`, supplier tallies from
  `last_purchases`, last date = most recent `purchase_date`.
- `checked_via == "web"` and `web_quotes.length > 0`:
  `Web median Rp X from N quotes. Data from D.`
  Where X = `reference_unit_price_idr`, N = `web_quotes.length`, D = most recent `fetched_at`.
- Otherwise: "No price reference found."

**"Add to today's queue" button**
- On click: `POST /api/requests` with `{ requested_by: "Quick check", items: [item] }`
  where `item` maps the draft fields to `RequestItemIn` format (same as `AddRequestsDialog`)
- On success: replace the button with a "View in Today" link that sets `window.location.hash = "#today"`
- On error: show inline error

**"See purchase history" button**
- Sets `window.location.hash = "#history"` (the HistoryPage will need to accept an initial
  search filter; if that's not implemented, just navigate to #history without a filter)

**Relevant Context**
- [`design/quick-check.html`](design/quick-check.html) — pixel-perfect reference
- [`frontend/src/components/Inspector.tsx`](frontend/src/components/Inspector.tsx:95) — flag box markup to reuse verbatim
- [`frontend/src/components/StatusChip.tsx`](frontend/src/components/StatusChip.tsx) — reuse directly
- [`frontend/src/lib/format.ts`](frontend/src/lib/format.ts) — formatting utilities
- [`frontend/src/components/AddRequestsDialog.tsx`](frontend/src/components/AddRequestsDialog.tsx) — pattern for POST /api/requests

---

### ST-6 — Frontend: Nav update + App.tsx routing

**Status:** [ ] pending

**Intent**
Add "Quick check" to the navigation and wire the hash route in `App.tsx`.

**Expected Outcomes**
- Nav shows: Today · Quick check · History · Import (in that order)
- `#quick-check` hash renders `QuickCheckPage`
- All other pages unaffected
- "Quick check" tab is active (highlighted) when on `#quick-check`

**Todo List**
1. In `AppHeader.tsx`: add `'Quick check'` to `NAV_TABS` between `'Today'` and `'History'`
2. Update `tabToHash` to map `'Quick check'` → `'#quick-check'`
3. Update `activeTab()` to return `'Quick check'` when `hash === '#quick-check'`
4. In `App.tsx`: import `QuickCheckPage`, add `const isQuickCheck = hash === '#quick-check'`
5. Render `{isQuickCheck && <QuickCheckPage />}` alongside the other page guards
6. Guard the Today main content block: also exclude `isQuickCheck`

**Relevant Context**
- [`frontend/src/components/AppHeader.tsx`](frontend/src/components/AppHeader.tsx:39) — `NAV_TABS` array and `tabToHash`
- [`frontend/src/App.tsx`](frontend/src/App.tsx:50) — `isImport`, `isHistory` pattern to follow

---

### ST-7 — Frontend: TypeScript type for `QuickCheckResult`

**Status:** [ ] pending

**Intent**
Add the TypeScript interface to `api.ts` so `QuickCheckPage` is fully typed.

**Expected Outcomes**
- `QuickCheckResult` interface added to `frontend/src/types/api.ts`
- No TypeScript errors in `QuickCheckPage.tsx`

**Todo List**
1. Add to `frontend/src/types/api.ts`:
   ```typescript
   export interface QuickCheckResult {
     raw_name: string
     name: string
     catalog_item_id: number | null
     category: string | null
     qty: number | null
     unit: string | null
     department: string | null
     quoted_unit_price_idr: number | null
     quoting_supplier_name: string | null
     history_count: number
     last_purchases: PurchaseOut[]
     web_quotes: WebQuoteOut[]
     reference_unit_price_idr: number | null
     checked_via: string
     diff_pct: number | null
     flags: FlagOut[]
     status: string
     check_error: string | null
   }
   ```

**Relevant Context**
- [`frontend/src/types/api.ts`](frontend/src/types/api.ts) — existing interfaces to mirror

---

## Implementation Order

```
ST-1  →  ST-2  →  ST-3  →  ST-4  (backend, sequential)
ST-7  →  ST-5  →  ST-6  (frontend, sequential)
```

Backend and frontend sub-tasks can be developed in parallel after ST-1 is done, but
ST-4 (test) must confirm the dry-run contract before frontend wires up the API.

---

## Key Constraints (from AGENTS.md)

- The model handles language; the backend handles numbers. No LLM math.
- Money is always integer rupiah (`int` in Python, `number` in TypeScript).
- `web_check.py` is used as-is — no modifications to it.
- `checker.py` logic is shared via `dry_check_item`, not copied.
- No new DB rows in `requests`, `request_items`, or `flags` during a quick-check run.
- Tests must not change seed numbers or expected values.
