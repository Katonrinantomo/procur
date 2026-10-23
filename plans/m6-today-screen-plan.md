# M6 · Today Screen Plan

## Overview

Build the Today screen for Procur.AI so it matches `design/reference.html` exactly at 1280 px. The screen is a single page: a queue table on top and an inspector panel below. The existing frontend is a placeholder (`App.tsx` with a centered heading). The backend API (`GET /api/queue` and `GET /api/request-items/{id}`) is already implemented.

The work is split into five sequential sub-tasks:

1. **Formatters and types** — `lib/format.ts` and shared TypeScript types
2. **Design tokens** — Tailwind v4 CSS custom properties and global font import in `index.css`
3. **Shared components** — AppHeader, StatusChip, and skeleton primitives
4. **Queue section** — QueueHeader, FilterChips, QueueTable with row selection logic
5. **Inspector section** — Inspector, HistoryTable, WebQuotesTable, and wire-up in `App.tsx`

Each sub-task can be handed off independently; the next sub-task imports from the previous one.

---

## Sub-task 1 — Formatters and types

**Intent**  
Create the formatting utilities and shared TypeScript interfaces that every other component depends on. Getting these right first prevents drift.

**Expected Outcomes**
- `frontend/src/lib/format.ts` exists and exports `formatRupiah`, `formatRupiahWithPrefix`, `formatPct`, `formatDate`.
- `frontend/src/types/api.ts` exists with typed interfaces for `QueueRow`, `StatusCounts`, `QueueResponse`, `RequestItemDetail`, `PurchaseOut`, `WebQuoteOut`, `FlagOut`.

**Todo List**

- [ ] Create `frontend/src/lib/format.ts`
  - `formatRupiah(n: number): string` — `Intl.NumberFormat('id-ID', { maximumFractionDigits: 0 }).format(n)` → "1.450.000". No "Rp" prefix.
  - `formatRupiahWithPrefix(n: number): string` — prepends "Rp " to `formatRupiah`.
  - `formatPct(n: number): string` — sign + 1 decimal + "%", use `−` (U+2212) for negatives, e.g. "+29.5%" or "−2.0%".
  - `formatDate(d: string | Date): string` — "12 Aug 2026" via `toLocaleDateString('en-GB', { day:'numeric', month:'short', year:'numeric' })`.
- [ ] Create `frontend/src/types/api.ts` with interfaces matching the backend schemas:
  - `QueueRow` — id, request_id, line_no, raw_name, department, qty, unit, quoted_unit_price_idr, reference_unit_price_idr, diff_pct, checked_via, status, requested_by, requested_at, flag_codes
  - `StatusCounts` — flagged, new, checked, approved, returned, pending (all number)
  - `QueueResponse` — rows: QueueRow[], counts: StatusCounts
  - `FlagOut` — code, message
  - `PurchaseOut` — purchase_date, po_number, supplier_name, qty, unit_price_idr
  - `WebQuoteOut` — seller, title, url, price_idr
  - `RequestItemDetail` — all fields from `backend/app/schemas.py` `RequestItemDetail`

**Relevant Context**
- `backend/app/schemas.py` lines 14–130 — source of truth for all field names and types
- Design reference lines 102: "−2.0%" uses Unicode minus U+2212, not hyphen-minus
- Design reference line 300: "Rp" prefix only on inspector totals
- All monetary values are integer rupiah (never float)

**Status:** `[ ] pending`

---

## Sub-task 2 — Design tokens

**Intent**  
Declare every color, font, border-radius, and spacing value from the UI spec as CSS custom properties inside `index.css` (Tailwind v4 `@theme` block). Add the Google Fonts import. This gives all components a single source of truth for tokens — no hardcoded hex values in JSX.

**Expected Outcomes**
- `frontend/src/index.css` has `@import` for Geist + Geist Mono from Google Fonts.
- `frontend/src/index.css` has a `@theme` block defining all tokens from the UI spec table.
- Any component can use Tailwind utility classes like `text-[#9A3412]` or CSS vars like `var(--color-flagged-text)` for token-mapped values.
- `body` uses `font-family: var(--font-sans)` and `color: #1A1A1A`.

**Todo List**

- [ ] Add Google Fonts `<link>` for `Geist:wght@400;500;600` and `Geist+Mono:wght@400;500` to `frontend/index.html`.
- [ ] In `frontend/src/index.css`, add an `@theme` block (Tailwind v4 syntax) defining:
  - `--font-sans: 'Geist', system-ui, sans-serif`
  - `--font-mono: 'Geist Mono', monospace`
  - All color tokens from the UI spec table (use descriptive names: `--color-flagged-text`, `--color-flagged-chip`, `--color-flagged-row`, `--color-border-panel`, `--color-border-row`, etc.)
  - Note: Tailwind v4 uses `@theme` not `tailwind.config.js`; custom properties defined in `@theme` are available as Tailwind utilities automatically.
- [ ] Keep `body { font-family: var(--font-sans); color: #1A1A1A; background: #FFFFFF; }` in global styles.

**Relevant Context**
- `frontend/src/index.css` — current file (3 lines, minimal, safe to extend)
- `frontend/index.html` — needs the Google Fonts `<link>` tags (same as `design/reference.html` lines 9–10)
- Tailwind v4 is used via `@tailwindcss/vite` (no `tailwind.config.js`); CSS vars in `@theme {}` are exposed as design tokens
- Token table is in `plans/Procur.AI — Build Plan for IBM Bob.md` lines 273–286

**Status:** `[ ] pending`

---

## Sub-task 3 — Shared components

**Intent**  
Build the three primitives used throughout the screen: `AppHeader` (always visible), `StatusChip` (used in every row and in the inspector), and a `SkeletonRow` (used for loading state). These have no data-fetch logic.

**Expected Outcomes**
- `frontend/src/components/AppHeader.tsx` renders header exactly as in design reference lines 19–29.
- `frontend/src/components/StatusChip.tsx` renders a chip for every status value with correct colors.
- `frontend/src/components/SkeletonRow.tsx` renders an animated placeholder `<tr>` with correct column count.

**Todo List**

- [ ] Create `frontend/src/components/AppHeader.tsx`:
  - `display: flex; align-items: center; justify-content: space-between; padding: 16px 28px; border-bottom: 1px solid #EDEDEA`
  - Left: "Procur.AI" (font-weight 600, 16px) + nav (Today active = `#F2F2EF` bg rounded-lg, History/Suppliers secondary color)
  - Right: "Add requests" button (height 40px, bg `#1A1A1A`, white text, radius 10px, font-size 14px)
  - Nav links: `padding: 8px 12px; border-radius: 8px`; active = `background: #F2F2EF`; inactive = `color: #4A4A46`
  - `activeTab` prop (default "Today"); buttons are `<button>` elements (not `<a>` — routing is out of scope for M6)
- [ ] Create `frontend/src/components/StatusChip.tsx`:
  - Props: `status: string`
  - Status → display label map: `flagged` → "Flagged", `new` → "New item", `checked` → "Checked", `approved` → "Approved", `returned` → "Returned", `pending` → "Pending"
  - Colors per status (from UI spec):
    - flagged: text `#9A3412`, bg `#FDEBDD`
    - new: text `#1E3A8A`, bg `#E8EEFB`
    - checked: text `#3F3F3B`, bg `#F0F0EC`
    - approved: text `#166534`, bg `#E7F4EC`
    - returned: text `#4A4A46`, bg white, border `1px solid #E0E0DB`
    - pending: text `#4A4A46`, bg `#F0F0EC`
  - Style: `font-size: 12px; font-weight: 500; padding: 4px 8px; border-radius: 6px`
- [ ] Create `frontend/src/components/SkeletonRow.tsx`:
  - Renders a `<tr>` with 9 `<td>` cells, each with an animated pulse `<div>` (gray bg, matching cell padding)
  - Export a `SkeletonRows` helper that renders N skeleton rows (default 4)

**Relevant Context**
- `design/reference.html` lines 19–29 (header), 71–116 (status chip usage)
- UI spec lines 279–283 (all status chip colors)
- The "Add requests" button action is out of scope for M6 (wired in M8); render it as a disabled or no-op button

**Status:** `[ ] pending`

---

## Sub-task 4 — Queue section

**Intent**  
Build the data-fetching layer and queue UI: header with date/counts/filter chips, and the scrollable table with row selection. Uses `GET /api/queue` via TanStack Query. Row selection state is owned here and passed to the inspector.

**Expected Outcomes**
- `frontend/src/components/QueueHeader.tsx` renders the title, subtitle, and filter chips.
- `frontend/src/components/FilterChips.tsx` renders four chips with correct active/inactive styles.
- `frontend/src/components/QueueTable.tsx` renders the 9-column table with correct row highlighting.
- `frontend/src/hooks/useQueue.ts` fetches `GET /api/queue` with TanStack Query.
- On load, the first `flagged` row is auto-selected.
- Clicking a row or pressing Enter on it selects it.

**Todo List**

- [ ] Set up TanStack Query: add `QueryClient` + `QueryClientProvider` to `frontend/src/main.tsx`.
- [ ] Create `frontend/src/hooks/useQueue.ts`:
  - Uses `useQuery` from `@tanstack/react-query`
  - Query key: `['queue']`
  - Fetches `GET /api/queue` via `fetch`; throws on non-2xx; returns typed `QueueResponse`
  - `staleTime: 30_000` (30 seconds)
- [ ] Create `frontend/src/components/FilterChips.tsx`:
  - Props: `counts: StatusCounts`, `active: string`, `onChange: (v: string) => void`
  - Chips: "All" (total = sum of all counts), "Flagged" (counts.flagged), "New" (counts.new), "Checked" (counts.checked)
  - Active chip: `background: #1A1A1A; color: #FFFFFF`
  - Inactive chip: `border: 1px solid #E0E0DB; background: transparent`
  - Chip style: `padding: 7px 12px; border-radius: 999px; font-size: 13px`
  - Chip label format: `"All 5"`, `"Flagged 1"`, etc.
- [ ] Create `frontend/src/components/QueueHeader.tsx`:
  - Props: `rows: QueueRow[]`, `counts: StatusCounts`, `activeFilter: string`, `onFilterChange: (v: string) => void`
  - Title: "Requests · {date}" where date is formatted from `rows[0]?.requested_at` (Jakarta day) or today; `font-size: 22px; font-weight: 600`
  - Subtitle: "{n} requests · {checked} checked · {new} new item · {flagged} flagged" using counts; `font-size: 13px; color: #6B6B66`
  - Layout: flex row, space-between, with FilterChips on the right
  - Show the subtitle only when there are rows
- [ ] Create `frontend/src/components/QueueTable.tsx`:
  - Props: `rows: QueueRow[]`, `selectedId: number | null`, `onSelect: (id: number) => void`
  - Table container: `border: 1px solid #E6E6E2; border-radius: 12px; overflow-x: auto`
  - `<table>` with `min-width: 980px`
  - Column order: #, Item, Dept., Qty, Quoted / unit, Reference / unit, Diff., Checked via, Status
  - Header row: `background: #F7F7F5; font-size: 12px; color: #5E5E59; font-weight: 500`
  - Header padding: `11px 16px`
  - Numeric columns (Qty, Quoted/unit, Reference/unit, Diff.) are right-aligned
  - Cell padding: `13px 16px`; number cells use `font-family: 'Geist Mono', monospace`
  - "Checked via" cell: show "History · N buys" or "Web · N quotes" or "—" based on `checked_via` and `history_count`
  - Row background:
    - Flagged + selected: `background: #FFF8F2; box-shadow: inset 3px 0 0 #9A3412`
    - Flagged + unselected: `background: #FFF8F2; box-shadow: inset 3px 0 0 #9A3412` (same — flagged always shows the bar)
    - Non-flagged + selected: `background: #F5F5F2`
    - Non-flagged + unselected: no extra background
  - Rows are `tabIndex={0}` and respond to `onKeyDown` Enter
  - `diff_pct` cell: color `#9A3412` for positive diff on flagged rows; `#6B6B66` for null/undefined; use `formatPct`
  - Null prices render as "—" (em dash)
  - `border-top: 1px solid #EDEDEA` on every row (the table uses `border-collapse: collapse`)
  - `tbody` has `font-variant-numeric: tabular-nums`
  - Line number cell: zero-padded two digits (`01`, `02`, …), `color: #6B6B66`

**Relevant Context**
- `design/reference.html` lines 46–119 — exact table markup
- `backend/app/schemas.py` lines 14–30 — `QueueRow` field names
- `backend/app/routers/queue.py` line 20 — sort order: flagged → new → checked → approved → returned → pending
- TanStack Query v5 is installed (`@tanstack/react-query ^5.104.1`)
- Vite proxy routes `/api/*` → `http://localhost:8000` (already in `vite.config.ts`)
- `checked_via` values: "history" | "web" | "none" | null; `history_count` is on the `RequestItemDetail`, not on `QueueRow` — for the queue table, derive the text from `checked_via` only (the count isn't available in `QueueRow`); use `history_count` from the detail endpoint for the inspector
- The queue endpoint does not return `history_count` per row — show "History" or "Web" without the count number in the table; the detail inspector shows the count

**Status:** `[ ] pending`

---

## Sub-task 5 — Inspector section and final wire-up

**Intent**  
Build the inspector panel (left: item fields + flags + buttons; right: history or web-quotes table) and wire everything together in `App.tsx`. The inspector fetches `GET /api/request-items/{id}` on selection change.

**Expected Outcomes**
- `frontend/src/hooks/useRequestItem.ts` fetches the detail endpoint with TanStack Query.
- `frontend/src/components/HistoryTable.tsx` renders the purchase history table with the "3-buy average (reference)" footer.
- `frontend/src/components/WebQuotesTable.tsx` renders the web quotes table with the "Median of N quotes (reference)" footer.
- `frontend/src/components/Inspector.tsx` renders the full two-panel inspector.
- `frontend/src/App.tsx` is replaced with the Today page: AppHeader + QueueHeader + QueueTable + Inspector, with selection state.
- At 1280 px, the rendered screen matches `design/reference.html`.
- Loading skeletons, empty state "No requests yet today", and error banner with Retry are all handled.

**Todo List**

- [ ] Create `frontend/src/hooks/useRequestItem.ts`:
  - Uses `useQuery` from TanStack Query
  - Query key: `['request-item', id]`
  - Fetches `GET /api/request-items/{id}`; enabled only when `id != null`
  - Returns `RequestItemDetail`
- [ ] Create `frontend/src/components/HistoryTable.tsx`:
  - Props: `purchases: PurchaseOut[]`, `referencePrice: number | null`
  - Table columns: Date, PO no., Supplier, Qty, Price / unit
  - Header: `font-size: 12px; color: #5E5E59; font-weight: 500; border-bottom: 1px solid #EDEDEA; padding: 8px 10px 10px`
  - First column (`Date`) and last column (`Price / unit`) have asymmetric padding: first col `padding-left: 0`, last col `padding-right: 0`
  - Row divider: `border-bottom: 1px solid #F2F2EF`
  - PO number: Geist Mono, `color: #4A4A46`
  - `<tfoot>`: colspan=4 "3-buy average (reference)", right cell = formatted price, Geist Mono, `font-weight: 500`; `padding-top: 12px`
  - `font-size: 13px; color: #5E5E59` for footer label
  - `tbody` has `font-variant-numeric: tabular-nums`
- [ ] Create `frontend/src/components/WebQuotesTable.tsx`:
  - Props: `quotes: WebQuoteOut[]`, `referencePrice: number | null`
  - Table columns: Seller, Offer (linked), Price / unit
  - "Offer" cell: `<a href={url} target="_blank" rel="noopener">` wrapping title; show title or url if no title
  - Footer: "Median of N quotes (reference)" where N = quotes.length; right cell = `formatRupiah(referencePrice)`
  - Same padding and color conventions as HistoryTable
- [ ] Create `frontend/src/components/Inspector.tsx`:
  - Props: `detail: RequestItemDetail | undefined`, `isLoading: boolean`
  - Outer panel: `border: 1px solid #E6E6E2; border-radius: 12px; display: flex; flex-wrap: wrap`
  - **Left half** (`flex: 1 1 340px; padding: 24px; border-right: 1px solid #EDEDEA; gap: 18px`):
    - Requester line: "Row {NN} · Requested by {dept}, {HH:MM}" — `font-size: 12px; color: #6B6B66`
    - Item name: `font-size: 20px; font-weight: 600`
    - `<dl>` grid (2 columns, `gap: 14px 16px`): Quoted total, At reference price, Over reference, Quoting supplier, Stock on record, Avg. monthly use
      - Labels: `font-size: 12px; color: #6B6B66`
      - Values: `font-size: 14px`; money fields use Geist Mono + `formatRupiahWithPrefix`; "Over reference" is `color: #9A3412; font-weight: 500` when positive
    - Flag reasons section (only when `flags.length > 0`): label "Flag reasons" (`font-size: 12px; color: #6B6B66`), `<ul>` with `padding-left: 18px; font-size: 14px; line-height: 1.6`
    - Buttons row: "Compare suppliers" (primary), "Approve" (secondary), "Return to requester" (secondary)
      - Primary: `height: 44px; background: #1A1A1A; color: white; border: 0; border-radius: 10px; font-size: 14px`
      - Secondary: `height: 44px; background: white; border: 1px solid #E0E0DB; border-radius: 10px; font-size: 14px`
      - All three buttons are no-ops (wired in M8); they must be real `<button>` elements
  - **Right half** (`flex: 999 1 460px; min-width: 0; padding: 24px; gap: 12px`):
    - Title: "Purchase history" or "Web quotes" (`font-size: 14px; font-weight: 500`)
    - If `detail.checked_via === 'history'` and `detail.last_purchases`: render `HistoryTable`
    - Else if `detail.web_quotes`: render `WebQuotesTable`
    - Else: nothing (or an em-dash placeholder)
    - Loading state: show a simple skeleton (two placeholder rows)
- [ ] Rewrite `frontend/src/App.tsx` as the Today page:
  - Import `useQueue`, `useRequestItem`, all components
  - State: `selectedId: number | null` (init null)
  - On queue load success: if `selectedId === null`, auto-select the first `flagged` row's `id`; if no flagged row, select first row
  - Filter state: `activeFilter: string` (init "All"); filter `rows` by status before passing to `QueueTable`
    - "All" → show all; "Flagged" → status === "flagged"; "New" → status === "new"; "Checked" → status === "checked"
  - Layout: `min-height: 100vh; display: flex; flex-direction: column`
  - `<AppHeader />`
  - `<main>` with `max-width: 1240px; margin: 0 auto; padding: 28px 28px 40px; gap: 28px; display: flex; flex-direction: column`
  - Error state (queue error): inline banner with `color: #9A3412; border: 1px solid #FDEBDD` and a "Retry" button that calls `refetch()`
  - Loading state (queue loading): show `QueueHeader` skeleton + `SkeletonRows` in a table wrapper
  - Empty state (queue success, rows.length === 0): centered "No requests yet today" text + "Add requests" button
  - Normal state: `QueueHeader` + `QueueTable` + `Inspector`
  - The note "All prices in Rp. Sample data for the mockup." from the design reference should appear below the inspector right panel (match exactly)

**Relevant Context**
- `design/reference.html` lines 121–176 — inspector panel markup
- `design/reference.html` lines 150–174 — history table with asymmetric cell padding
- `backend/app/schemas.py` lines 87–130 — `RequestItemDetail` all fields
- `backend/app/routers/request_items.py` lines 80–119 — history vs web quotes logic: `checked_via == "history"` → `last_purchases`; else → `web_quotes`
- `history_count` on the detail tells you "3-buy average" (reference uses last 3; display count is `last_purchases.length`)
- `reference_unit_price_idr` on the detail is the computed reference price; use it for both footer labels
- For responsive: on narrow screens, inspector halves stack (already handled by `flex-wrap: wrap`)

**Status:** `[ ] pending`

---

## Cross-cutting constraints

- No new dependencies beyond what is already installed (TanStack Query v5, Tailwind v4, React 19, TypeScript 6).
- No hardcoded hex values in JSX/TSX — use Tailwind utility classes with inline values, or CSS variables.
- No gradients, drop-shadows, emoji, or icons not in the design.
- Every `<button>` is a real `<button>` element ≥ 44px tall.
- Money is always integer; never pass a float to a formatter.
- `diff_pct` color rule: use `#9A3412` for positive diffs only when the row is flagged; use default text color otherwise. In the inspector "Over reference" field, use `#9A3412` whenever `over_reference_idr > 0`.
- The design note says "All prices in Rp. Sample data for the mockup." — keep this footer text in the inspector right panel as-is.
