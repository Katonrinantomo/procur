# Procur.AI

Procurement price-check web app for a manufacturing demo. Purchasing pastes the day's requests, the Organize flow turns them into structured line items, and the backend checks each row against purchase history and live web prices — flagging anything that looks over budget.

---

## Architecture

```
Browser  ──►  Backend (FastAPI)  ──►  PostgreSQL
                     │
                     ├──►  Langflow Flow 1: Organize   ──►  Claude Haiku 5.5
                     └──►  Langflow maker_agent        ──►  Claude Haiku 5.5
```

**Key rule: the model handles language; the backend handles numbers.**
Claude reads messy text and summarises web results. Every price, percentage, and flag is computed in Python from the database — never by the model.

### Tech stack

| Layer | Choice |
|---|---|
| Frontend | React + Vite + TypeScript, Tailwind CSS v4, TanStack Query v5 |
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, httpx, rapidfuzz |
| Database | PostgreSQL 16 via Docker Compose (SQLite fallback via `DATABASE_URL`) |
| AI flows | Langflow, run locally with `uv` |
| Model | Claude Haiku 5.5 via the Claude API (`claude-haiku-5-5`) |
| Tests | pytest, 385 tests, SQLite in-process (no Langflow or PostgreSQL needed) |

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
- A **Claude API key** from [console.anthropic.com](https://console.anthropic.com)

---

## Setup

All commands below are **PowerShell** (Windows). Adapt as needed for macOS/Linux.

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

Open `backend\.env`, set `JWT_SECRET` (required, at least 32 characters — the API refuses to start without it) and `DEMO_PASSWORD`, then fill in the Langflow values — you will get them in step 4.

```
DATABASE_URL=postgresql+psycopg2://procur:procur@localhost:5432/procur
JWT_SECRET=                ← python -c "import secrets; print(secrets.token_hex(32))"
DEMO_PASSWORD=             ← password for the seeded purchasing / owner / finance users
LANGFLOW_URL=http://localhost:7860
LANGFLOW_API_KEY=          ← fill in after step 4
LANGFLOW_ORGANIZE_FLOW_ID= ← fill in after step 4
LANGFLOW_WEBCHECK_FLOW_ID= ← fill in after step 4
LANGFLOW_MAKER_FLOW_ID=    ← maker_agent: web prices + vendor quotes
LANGFLOW_CHECKER_FLOW_ID=  ← optional until M21 (checker_agent)
LANGFLOW_NARRATOR_FLOW_ID= ← optional until M24 (risk_narrator)
```

An empty flow ID only disables that flow; the backend logs a warning at startup.

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

Seed demo data (purchase history + stock levels + today's 5-row flagged request, plus the `purchasing`, `owner` and `finance` users, all with `DEMO_PASSWORD`). Re-seed after upgrading from a build before M16: old password hashes no longer verify.

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

1. **Add your Claude API key:**
   Go to **Profile → Settings → Model Providers → Anthropic**, paste your key, and save.
   Both flows call `claude-haiku-5-5` through this key.

2. **Import the two flows:**
   Click **+ New flow → Import** and load each file:
   - `langflow/Organize.json` — parses messy purchase text into structured line items
   - `langflow/Web Check.json` — searches the web for prices of unknown items

3. **Copy the flow IDs:**
   Open each flow. The UUID is in the URL:
   `http://localhost:7860/flow/<uuid>`
   Set the UUIDs in `backend\.env`:
   ```
   LANGFLOW_ORGANIZE_FLOW_ID=<uuid from Organize flow>
   LANGFLOW_WEBCHECK_FLOW_ID=<uuid from Web Check flow>
   ```

4. **Create a Langflow API key:**
   Go to **Profile → Settings → Langflow API Keys → Add New**, copy the key:
   ```
   LANGFLOW_API_KEY=<your-key>
   ```

5. **Restart the backend** so it picks up the new `.env` values:
   ```powershell
   # Ctrl+C the uvicorn process, then:
   uvicorn app.main:app --reload
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
| **Today** | Shows today's request queue sorted by status (Flagged → New → Checked). Click any row to open the inspector. |
| **Add requests** | Paste a WhatsApp/email message. The Organize flow parses it into line items; you review the preview and save. |
| **Quick check** | Dry-run a single item — checks it against history and web prices without saving anything. |
| **History** | Browse all past request items with filters for date range, status, and supplier. |
| **Excel import** | Upload a purchase history file (.xlsx or .csv, max 5 MB) to populate the reference-price database. Download the template from the import page. |

---

## Running tests

All tests use an in-process SQLite database — no PostgreSQL or Langflow required.

```powershell
cd backend
pytest                        # run all 385 tests
pytest tests/test_pricing.py  # run a single file
pytest -v                     # verbose output
pytest -m live                # live flow check against the real Langflow (skipped by default)
```

### Live flow check

`python -m app.flowcheck` (from `backend\`) runs every fixture in `langflow/fixtures/<flow>/*.txt` through each flow whose ID is set, validates the output against its contract in `app/flows/contracts.py`, and prints pass/fail with latency. It exits 1 on any failure. Owners can see the last result at `GET /api/health/flows`.

---

## Release steps

Run these whenever a flow changes, and before every demo:

1. In Langflow, check each flow's model component: provider **Anthropic**, model `claude-haiku-5-5`, temperature 0, API key from a Langflow global variable (never typed into the component).
2. Name each flow's Chat Output after its contract: `organize_json` (Organize), `webcheck_json` (Web Check).
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

Click **Organize** → Claude Haiku structures the text. Click **Save**.

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

Show the two Langflow flows in the browser. Point out that the model only reads text and summarises web results — every number is computed in Python.

---

## Known limits

| Limit | Detail |
|---|---|
| Purchase history | The database is seeded with demo data. Real history must be imported via the Excel import page or the CSV import endpoint. |
| Web check rate limits | The Web Check flow uses DuckDuckGo search (no API key). During a live demo it may be throttled. The 60-day quote cache and the seeded solenoid quotes mean this does not affect the demo item. |
| Langflow model providers | The Claude API key must be entered in Langflow's **Model Providers** settings, not in `backend\.env`. The backend `.env` holds the Langflow API key and flow IDs only. |
| Web check timeout | The backend allows 60 s for a Langflow call. Very slow web results return an error row with `status=pending`; recheck the row manually once the cache is warm. |
