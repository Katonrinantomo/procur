# Procur.AI

Procurement price-check web app for a manufacturing demo. Purchasing pastes the day's requests, the Organize flow turns them into structured line items, and the backend checks each row against purchase history and live web prices — flagging anything that looks over budget. An owner approves or returns each row; every decision is written to an append-only decision log.

Three roles (Maker-Checker): `purchasing` raises and checks requests, `owner` approves or returns them (never their own), `finance` reads the queue, history and decision log.

> Full architecture, RBAC matrix, business-logic truth table, sequence diagrams and security notes: [`ARCHITECTURE.md`](ARCHITECTURE.md). Stale documents and open findings: [`DOCS_AUDIT.md`](DOCS_AUDIT.md).

---

## Architecture

```
Browser  ──►  Backend (FastAPI)  ──►  PostgreSQL
                     │
                     ├──►  Langflow Flow 1: Organize   ──►  LLM
                     └──►  Langflow maker_agent        ──►  LLM (extract)  ──►  Serper API
                                                       └──►  LLM (match listings)
```

**Key rule: the model handles language; the backend handles numbers.**
The model reads messy text and matches marketplace listings. Every price, percentage, flag and score is computed in Python from the database — never by the model. Web prices come only from listings whose URL and price are found in the Serper results (`services/evidence.py`).

`langflow/Web Check.json` is a legacy flow: web prices now run through `langflow/Maker.json` (`MODE: BON`).

### Tech stack

| Layer | Choice |
|---|---|
| Frontend | React + Vite + TypeScript, Tailwind CSS v4, TanStack Query v5 |
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, httpx, rapidfuzz |
| Database | PostgreSQL 16 via Docker Compose (SQLite fallback via `DATABASE_URL`) |
| AI flows | Langflow, run locally with `uv` |
| Model | `Maker.json`: Anthropic `claude-haiku-5-5`. `Organize.json` as last exported: an OpenAI-compatible gateway (`langflow`); select the model on each Language Model node before a demo (see Release steps) |
| Web search | Serper API (Google results restricted to Tokopedia, Shopee, Blibli, Lazada) |
| Auth | Username + password (PBKDF2-HMAC-SHA256), 1-hour HS256 JWT, three roles |
| Tests | pytest, 506 tests collected, SQLite in-process (no Langflow or PostgreSQL needed); 96% line coverage over `app/services` |

### Key source files

| File | Purpose |
|---|---|
| `backend/app/services/checker.py` | Orchestrates match → price → flags → status per row |
| `backend/app/services/pricing.py` | Reference price (mean of last 3 purchases) and diff_pct |
| `backend/app/services/flags.py` | Pure flag functions with thresholds from config |
| `backend/app/services/matcher.py` | rapidfuzz `token_set_ratio`, threshold 85, normalises units |
| `backend/app/services/langflow_client.py` | Only place that calls Langflow |
| `frontend/src/lib/format.ts` | Rupiah formatter, signed %, date formatting |

---

## Prerequisites

- **Docker Desktop** — for PostgreSQL
- **Python 3.11+**
- **Node.js 18+**
- **[uv](https://docs.astral.sh/uv/)** — to run Langflow  
  Install: `pip install uv`
- A **Claude API key** from [console.anthropic.com](https://console.anthropic.com) (used by `Maker.json`)
- A **Serper API key** from [serper.dev](https://serper.dev) (web price search in `Maker.json`)

---

## Setup

All commands below are **PowerShell** (Windows). Adapt as needed for macOS/Linux. On Linux, `./start.sh` and `./stop.sh` start and stop PostgreSQL, Langflow, the backend and the frontend together (all bound to `127.0.0.1`; set `LANGFLOW_DIR` to your Langflow install folder, default `~/langflow`).

### 1. Start PostgreSQL

From the repo root:

```powershell
docker compose up -d
```

Starts PostgreSQL 16 on port 5432. Username, password, and database are all `procur`.

### 2. Configure the backend environment

```powershell
cd backend
Copy-Item .env.example .env
```

Open `backend\.env`, set `DATABASE_URL`, `JWT_SECRET` and `DEMO_PASSWORD`, then fill in the Langflow values — you will get them in step 4. The API **refuses to start** without `DATABASE_URL` and a `JWT_SECRET` of at least 32 characters.

```
DATABASE_URL=postgresql+psycopg2://procur:procur@localhost:5432/procur   ← required
JWT_SECRET=                ← required, ≥ 32 chars: python -c "import secrets; print(secrets.token_hex(32))"
DEMO_PASSWORD=             ← password for the seeded purchasing / owner / finance users
LANGFLOW_URL=http://localhost:7860
LANGFLOW_API_KEY=          ← fill in after step 4
LANGFLOW_ORGANIZE_FLOW_ID= ← Organize flow: Add requests and Quick check
LANGFLOW_MAKER_FLOW_ID=    ← maker_agent: web prices (new items) and vendor quotations
LANGFLOW_WEBCHECK_FLOW_ID= ← legacy Web Check flow: not used for pricing; optional
LANGFLOW_CHECKER_FLOW_ID=  ← optional until M21 (checker_agent)
LANGFLOW_NARRATOR_FLOW_ID= ← optional until M24 (risk_narrator)
```

An empty flow ID only disables that flow; the backend logs a warning at startup. Without `LANGFLOW_MAKER_FLOW_ID`, items that have purchase history still check, and items that need a web price are saved as `pending` with an error message.

Optional: `ALLOWED_HOSTS` (default `localhost,127.0.0.1`) controls which `Host` headers the API accepts; `APP_ENV=production` makes `seed --reset` refuse to run.

> **SQLite fallback** — no Docker needed:
> set `DATABASE_URL=sqlite:///./procur.db` in `backend\.env`.

### 3. Install and migrate the backend

```powershell
# still inside backend\
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
alembic upgrade head
```

Seed demo data (purchase history + stock levels + today's 5-row flagged request, plus three users with `DEMO_PASSWORD`; `password123` if it is empty). Re-seed after upgrading from a build before M16: old password hashes no longer verify.

| Username | Role | Lands on | Can |
|---|---|---|---|
| `purchasing` | Maker | Today | Add requests, Quick check, Vendor quotes, Import history |
| `owner` | Checker | Review | Approve or return (not their own requests), Add requests, read the Audit Log |
| `finance` | Viewer | History | Read Today, History and the Audit Log |

```powershell
python -m app.seed --reset
```

Start the API server:

```powershell
uvicorn app.main:app --reload
```

- API root: `http://localhost:8000`
- Interactive docs: `http://localhost:8000/docs`
- Health / Langflow status: `http://localhost:8000/api/health`

### 4. Start Langflow and import the flows

Open a **second** PowerShell window from the repo root:

```powershell
uv run langflow run
```

Langflow opens at `http://localhost:7860`.

**One-time setup (do this once):**

1. **Add your API keys:**
   - **Profile → Settings → Model Providers → Anthropic**: paste your Claude key and save.
   - **Profile → Settings → Global Variables**: add `SERPER_API_KEY` with your Serper key. The Serper component reads it from there; never type a key into a component (`scripts\check_langflow_secrets.py` rejects exports that do).

2. **Import the flows:**
   Click **+ New flow → Import** and load each file:
   - `langflow/Organize.json` — parses messy purchase text into structured line items
   - `langflow/Maker.json` — maker_agent: reads a vendor quotation or an item list, searches Serper, and matches marketplace listings. It supplies web prices for new items and the vendor-quotation check.
   - `langflow/Web Check.json` — legacy, no longer used for pricing. Import it only if you want it in the health check.

   Then, on **every Language Model node** of each flow, select the provider and model (**Anthropic**, `claude-haiku-5-5`) and set temperature to 0. The committed exports do not all agree on the model (`Organize.json` was last exported with an OpenAI-compatible gateway), so check this before relying on any extraction result.

3. **Check that `Maker.json` has three Chat Outputs.** The backend reads outputs named `extract_json`, `maker_json` and `serper_raw` (`langflow/maker_agent_prompts.md`). The committed export has all three (`extract_json` is wired from Language Model #1, the extract model). If a flow in Langflow is missing one, every web check fails: the row is saved as `pending` and its error contains `Flow output 'extract_json' not found`. To re-add it by hand, follow "Adding the `extract_json` output by hand" in `langflow/maker_agent_prompts.md`. `pytest tests/test_langflow_exports.py` checks the committed file.

4. **Copy the flow IDs:**
   Open each flow. The UUID is in the URL:
   `http://localhost:7860/flow/<uuid>`
   Set the UUIDs in `backend\.env`:
   ```
   LANGFLOW_ORGANIZE_FLOW_ID=<uuid from Organize flow>
   LANGFLOW_MAKER_FLOW_ID=<uuid from Maker flow>
   LANGFLOW_WEBCHECK_FLOW_ID=<uuid from Web Check flow>   # optional, legacy
   ```

5. **Create a Langflow API key:**
   Go to **Profile → Settings → Langflow API Keys → Add New**, copy the key:
   ```
   LANGFLOW_API_KEY=<your-key>
   ```

6. **Restart the backend** so it picks up the new `.env` values, then check the flows are wired. `python -m app.flowcheck` (from `backend\`) runs the fixtures through every configured flow:
   ```powershell
   # Ctrl+C the uvicorn process, then:
   uvicorn app.main:app --reload

   # in a second shell, from backend\:
   python -m app.flowcheck
   ```

### 5. Start the frontend

Open a **third** PowerShell window:

```powershell
cd frontend
npm install
npm run dev
```

The app is at `http://localhost:5173`.
The Vite dev server proxies all `/api/*` requests to `http://localhost:8000`.

---

## Features

| Screen | What it does |
|---|---|
| **Today** | All roles. Shows today's request queue (Asia/Jakarta date) sorted by status (Flagged → New → Checked), with a risk score per row. Click any row to open the inspector. |
| **Add requests** | `purchasing`, `owner`. Paste a WhatsApp/email message. The Organize flow parses it into line items; you review the preview and save. |
| **Quick check** | `purchasing`. Dry-run check of pasted items against history and web prices without saving anything. |
| **Vendor quotes** | `purchasing`. Upload a vendor quotation (.pdf with a text layer, or .xlsx, max 10 MB). Each line gets a price band, a recommendation and an evidence list, plus a 0–100 vendor score. Queue the checked lines for review. |
| **Review** | `owner`. Every undecided row, flagged first and then by risk score. Approve or return. Approving a flagged or high-risk row (risk score 50 or more) needs a reason and an outcome tag; returning needs a reason. Owners cannot decide on a request they created. |
| **Audit Log** | `owner`, `finance`. Append-only decision log with the evidence snapshot taken at decision time. Filter by date and export CSV. |
| **History** | All roles. Browse past request items and purchases with filters for date range, status, and supplier. |
| **Excel import** | `purchasing`. Upload a purchase history file (.xlsx or .csv, max 5 MB) to populate the reference-price database. Download the template from the import page. |

The API enforces these roles; the UI only hides what a role cannot use. The full matrix is in [`ARCHITECTURE.md`](ARCHITECTURE.md#4-role-based-access-control-rbac-matrix).

---

## Running tests

All tests use an in-process SQLite database — no PostgreSQL or Langflow required.

```powershell
cd backend
pytest                        # run all 506 tests (the live one is skipped)
pytest tests/test_pricing.py  # run a single file
pytest -v                     # verbose output
pytest -m live                # live flow check against the real Langflow (skipped by default)
```

The README's test count is what `pytest --collect-only -q` reports (collected = passed + skipped; the live tests are collected but skipped unless `-m live`). `python scripts\check_claims.py` fails when the two differ.

Coverage (line, over `app/services`; `app/audit` is added once it exists) is configured in `backend/.coveragerc`:

```powershell
pytest --cov --cov-report=term
```

### Release check

From the repo root, before every push and before the freeze:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\release_check.ps1
```

It runs pytest with coverage, the coverage report, `npm run build`, the flow-export secrets check, `python -m app.flowcheck` and the claims check, and stops at the first failure. `-SkipFlowcheck` skips the live flow check when Langflow is down; that run is not a full release check.

### Eval harness

From `backend\` (writes `eval/results.json` and `eval/results.md`, stamped with the date, git commit, the model in each exported flow and the sha256 of every `langflow/*.json`):

```powershell
python -m eval.run --suite E1,E2,E3,E4
```

| Suite | Measures | Data | Needs |
| --- | --- | --- | --- |
| E1 / E1b | Organize extraction per field, price exact match, rows missed / invented; flags that change because of misreading | `eval/data/e1/` | Langflow + Organize flow |
| E2 | Detection and false-positive rate per flag | `eval/data/e2_rows.json` | offline |
| E3 | Web price MAPE, no-quote rate, share off by more than 30%, listings dropped by the evidence guards | `eval/data/e3_prices.csv` | Langflow + maker_agent + Serper |
| E4 | Name-matching wrong-match rate | `eval/data/e4_names.csv` | offline |
| E5, E6 | Checker extraction and payment detection | — | land with M21–M22 |

E2 and E4 run on a throwaway seeded SQLite database, never the dev database. A suite whose data, flow ID or Langflow is missing is reported as skipped with the reason. Data files marked as example are labelled "EXAMPLE DATA — not a measurement" in the results; see `eval/data/README.md` for what still has to be filled in.

### Live flow check

`python -m app.flowcheck` (from `backend\`) runs every fixture in `langflow/fixtures/<flow>/*.txt` through each flow whose ID is set, validates the output against its contract in `app/flows/contracts.py`, and prints pass/fail with latency. It exits 1 on any failure. Owners can see the last result at `GET /api/health/flows`.

---

## Release steps

Run these whenever a flow changes, and before every demo:

1. In Langflow, check each flow's model component: provider **Anthropic**, model `claude-haiku-5-5`, temperature 0, API key from a Langflow global variable (never typed into the component).
2. Name each flow's Chat Outputs after its contract (`backend/tests/test_langflow_exports.py` fails if a `Maker.json` re-export drops one): `organize_json` (Organize); `extract_json`, `maker_json` and `serper_raw` (Maker); `webcheck_json` (Web Check, legacy).
3. Export each flow to `langflow/` and commit the JSON.
4. Check the exports for secrets — this must pass before you commit:
   ```powershell
   python scripts\check_langflow_secrets.py
   ```
5. From `backend\`, run the live flow check and the unit tests:
   ```powershell
   python -m app.flowcheck
   pytest
   ```

---

## Seeding demo data

```powershell
cd backend

# Full demo state: purchase history, stock levels, and today's 5-row request.
# The hydraulic oil row is automatically flagged at +29.5%.
python -m app.seed --reset

# Empty-today state: history and stock only, no today's request.
# Use this as the starting point for the live demo.
python -m app.seed --reset --empty-today
```

Both commands complete in under 2 seconds.

---

## Demo script (~3 minutes)

### 1. The problem (20 s)

A manufacturer buys daily from small suppliers with no purchase database and unreliable stock records. Overpaying goes unnoticed.

### 2. Add a request (40 s)

Start from the empty-today state:

```powershell
python -m app.seed --reset --empty-today
```

In the app, open **Add requests** and paste the morning's WhatsApp message:

```
1. Hydraulic oil ISO VG 46, 20L – 4 drum, Warehouse, Rp 1.450.000/drum, CV Sinar Pelumas
2. Solenoid valve 24V DC, 1/2" – 2 pcs, Maintenance
3. Bearing 6205 ZZ – 20 pcs, Maintenance, Rp 38.500/pcs
4. Work gloves, cotton dotted – 10 doz, Production, Rp 96.000/doz
5. Packing tape 48mm, clear – 3 box, Warehouse, Rp 210.000/box
```

Click **Organize** → the model structures the text. Check the item names in the preview, then click **Save**.

### 3. Inspect a flagged row (60 s)

The queue fills. The hydraulic oil row is immediately flagged at **+29.5%**. Open it:

- 3 past purchases → last-3 average = Rp 1.120.000
- Quoted at Rp 1.450.000 → **Rp 1.320.000 over reference on 4 drums**
- Stock already covers ~6 weeks (STOCK_COVER_HIGH flag)

### 4. New item — web price (30 s)

The solenoid valve has no purchase history. Procur.AI searched the web: 3 quotes, **median Rp 425.000**. No flag — the quoted price is within range.

### 5. Decide (20 s)

Use **Return to requester** on the oil row and **Approve** the rest.

### 6. Under the hood (20 s)

Show the Organize and Maker flows in the browser. Point out that the model only reads text and matches marketplace listings — every number is computed in Python.

---

## Known limits

| Limit | Detail |
|---|---|
| Purchase history | The database is seeded with demo data. Real history must be imported via the Excel import page or the CSV import endpoint. |
| Web check quota | Web prices use the Serper API (paid, per-search quota, needs `SERPER_API_KEY`). Quotes are cached for 60 days by normalized item name, and the seeded solenoid quotes mean the demo item needs no search. The LLM endpoints are limited to 10 requests per minute per IP. |
| Item names from Organize | In the last eval run (3 messages, 5 rows) Organize returned English item names (`oli` → "Lubricating oil") instead of keeping Indonesian, so item-name accuracy was 20% while quantity, unit, price, supplier and department were 100%. Review the parsed names in the preview before saving. Details and fix: [`DOCS_AUDIT.md`](DOCS_AUDIT.md). |
| Web price accuracy | Not yet measured: the E3 suite has no hand-checked prices. Treat web references as a guide, not a benchmark. |
| Langflow model providers | The Claude API key must be entered in Langflow's **Model Providers** settings, not in `backend\.env`. The backend `.env` holds the Langflow API key and flow IDs only. |
| Web check timeout | The backend allows 60 s per Langflow attempt and tries up to 3 times. Very slow web results return an error row with `status=pending`; recheck the row manually once the cache is warm. |
