# Usage guide

Assumes the stack is running (see [installation](installation.md)) and the demo data is seeded. All seeded users share `DEMO_PASSWORD`.

## Roles and pages

| User | Lands on | Tabs |
|---|---|---|
| `purchasing` | Today | Today, Quick check, Vendor quotes, History, Import |
| `owner` | Review | Review, Today, History, Audit Log |
| `finance` | History | Today, History, Audit Log |

The UI hides what a role cannot use; the backend rejects it anyway.

## Main flows

### 1. Check the morning's requests (purchasing)

1. **Today → Add requests**, paste the message as received:
   ```
   1. Hydraulic oil ISO VG 46, 20L – 4 drum, Warehouse, Rp 1.450.000/drum, CV Sinar Pelumas
   2. Solenoid valve 24V DC, 1/2" – 2 pcs, Maintenance
   3. Bearing 6205 ZZ – 20 pcs, Maintenance, Rp 38.500/pcs
   4. Work gloves, cotton dotted – 10 doz, Production, Rp 96.000/doz
   5. Packing tape 48mm, clear – 3 box, Warehouse, Rp 210.000/box
   ```
2. **Organize** — the Organize flow returns one editable row per line. Fix anything misread, then **Save**.
3. The rows appear in the queue, already checked. Click a row to open the inspector:
   - **History reference**: last 3 purchases and their average, quoted vs reference total, Rp over reference.
   - **Web reference** (item never bought): the kept marketplace listings with links, their median, and how many listings were dropped and why.
   - **Flags** with plain-language messages, stock on hand and monthly use, usual order quantity.

What the status means:

| Status | Meaning |
|---|---|
| `flagged` | At least one flag fired — needs an owner decision with a reason |
| `checked` | Compared against purchase history, nothing unusual |
| `new` | No purchase history; compared against web prices, or no reference at all |
| `pending` | The check could not finish (e.g. Langflow down); see `check_error` and recheck through `POST /api/request-items/{id}/recheck` |
| `approved` / `returned` | Decided by the owner. The inspector shows **Recheck** on these rows (purchasing: own requests only; owner: any) |

When flags fire:

| Flag | Fires when (default) |
|---|---|
| `PRICE_ABOVE_REF` | Quoted price > 15% above the 3-buy average or web median |
| `STOCK_COVER_HIGH` | Stock on hand covers more than 1 month of average use |
| `QTY_UNUSUAL` | Quantity > 2× the median past order quantity |
| `NEW_SUPPLIER` | A supplier is named that has no purchases on record |

### 2. Decide (owner)

**Review** lists every undecided row across all dates — flagged first, then by risk score. For each row:

- **Approve** a clean row: reason optional.
- **Approve** a flagged row or one with risk score ≥ 50: write a reason and choose **False alarm** (the flag was wrong) or **Risk accepted** (the flag was right, buying anyway).
- **Return to requester**: reason required.

You cannot decide on a request you entered yourself. Every decision is recorded with a snapshot of what you saw and appears in **Audit Log** and in the row's decision history.

### 3. Quick check (purchasing)

Paste one or more lines on **Quick check** to see the reference, difference and flags without creating a request — useful while still negotiating on the phone. Nothing is saved except fetched web prices, which are cached for later checks.

### 4. Vendor quotation (purchasing)

1. **Vendor quotes → upload** a `.pdf` (must contain selectable text — scans are rejected) or `.xlsx` quotation, up to 10 MB.
2. The maker_agent reads vendor, quote number, date, lines and totals, and searches Tokopedia, Shopee, Blibli and Lazada for each line.
3. Each line shows its reference (history first, else web median), difference, band and recommendation:

   | Band (difference from reference) | Recommendation |
   |---|---|
   | KOMPETITIF ≤ −10% | SETUJU |
   | WAJAR ≤ +5% | SETUJU |
   | PERHATIAN ≤ +15% | NEGOSIASI |
   | TIDAK WAJAR > +15% | NEGOSIASI up to +30%, TOLAK above |

4. The vendor score (0–100) is 80% price (band points weighted by line value) + 20 points if every line total and the document total add up within Rp 1.
5. **Add to today's queue** turns the quotation into a request so it goes through the normal owner review. Only the uploader can do this, once.

### 5. Import purchase history (purchasing)

**Import → download template**, fill it (or use your own sheet with English or Indonesian headers), upload `.xlsx` or `.csv` up to 5 MB. The summary shows rows inserted, skipped as duplicates (same PO + item), new catalog items, new suppliers, and per-row errors with the spreadsheet row number. A sample is in `backend/sample_data/`.

More history makes the reference price available for more items, which moves rows from `new` to `checked`/`flagged`.

### 6. History and audit (all roles)

**History** has two tabs: **Purchases** (the ledger: search by item, alias, supplier or PO; filter by supplier and date) and **Requests** (past request items, filtered by date range and status). **Audit Log** (owner, finance) lists decisions with their reasons and exports the selected date range as CSV.

## Demo reset

```powershell
cd backend
python -m app.seed --reset               # full demo: today's 5-row request already checked
python -m app.seed --reset --empty-today # start the live demo from an empty queue
```

The expected demo numbers: hydraulic oil last-3 average Rp 1.120.000, quoted Rp 1.450.000 → **+29.5%**, Rp 1.320.000 over reference on 4 drums, stock covering ~6 weeks.

## Tuning

Thresholds are settings; put overrides in `backend/.env` and restart the backend:

```
FLAG_PRICE_ABOVE_REF_PCT=10
FLAG_STOCK_COVER_MONTHS=1.5
FLAG_QTY_UNUSUAL_MULTIPLIER=3
WEB_QUOTE_MAX_AGE_DAYS=30
OVERRIDE_RISK_SCORE=60
```

Existing rows keep their results until rechecked.

## Common errors

| Symptom | Cause | Fix |
|---|---|---|
| "The Organize flow isn't configured" | `LANGFLOW_ORGANIZE_FLOW_ID` empty | Set it in `backend/.env`, restart uvicorn |
| 502 on Organize / Quick check | Langflow down, wrong API key, or the model returned invalid JSON twice | Check `GET /api/health`; run `python -m app.flowcheck` |
| Row stuck in `pending` with "web_check failed" | maker_agent unreachable, `LANGFLOW_MAKER_FLOW_ID` empty, or Serper key missing | Fix the flow, then call `POST /api/request-items/{id}/recheck` (the UI button appears only on approved/returned rows) |
| New item shows no reference | Fewer than 3 listings survived the evidence guards | Expected; decide on judgement or import history for the item |
| "PDF tidak punya lapisan teks" | Scanned PDF | Upload the XLSX or a text PDF |
| "You cannot approve a request you created" | Four-eyes rule | Another owner must decide |
| Logged out with "Sesi berakhir, silakan masuk lagi" | Token expired (1 hour) | Sign in again |
| 429 Too Many Requests | 10/min limit on AI endpoints, 5/min on login | Wait a minute |
| Backend exits at startup | `DATABASE_URL` or `JWT_SECRET` missing, or secret < 32 chars | Fix `backend/.env` |
