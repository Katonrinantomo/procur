# Procur.AI

Procurement price-check app for a manufacturing demo. Purchasing pastes the day's requests, Langflow turns the text into rows, the backend checks each row against the database, and the screen shows what needs a second look.

---

## Architecture

```
Browser  ──►  Backend (FastAPI)  ──►  PostgreSQL
                     │
                     ├──►  Langflow Flow 1: Organize   ──►  Claude Haiku 5.5
                     └──►  Langflow Flow 2: Web Check  ──►  Claude Haiku 5.5
```

**One request, end to end:**

1. Purchasing pastes messy text in the web app. The backend sends it to **Flow 1**, and Claude Haiku returns structured line items as JSON (item, qty, unit, department, quoted price, supplier).
2. The user checks the preview and saves. The backend stores the request and its rows in PostgreSQL.
3. For each row, the backend matches the item catalog using fuzzy name matching and computes a reference price from the last 3 purchases. Items with no purchase history go to **Flow 2**, which searches the web for current prices (cached 7 days).
4. Plain Python flag rules set each row's status: **Checked**, **New item**, or **Flagged** (with reasons). The queue table and inspector read everything back from the database.

**Key rule: the model handles language; the backend handles numbers.** Haiku reads messy text and summarises web results. Every price, percentage, and flag is computed in Python from the database — never by the model.

### Tech stack

| Layer | Choice |
|---|---|
| Frontend | React + Vite + TypeScript, Tailwind CSS v4, TanStack Query v5 |
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, httpx, rapidfuzz |
| Database | PostgreSQL 16 via Docker Compose (SQLite fallback via `DATABASE_URL`) |
| AI flows | Langflow, run locally with `uv` |
| Model | Claude Haiku 5.5 via the Claude API (`claude-haiku-5-5`) |
| Web search | Langflow Web Search component (DuckDuckGo, no API key) |
| Tests | pytest + FastAPI TestClient |

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

- **Docker** — for PostgreSQL
- **Python 3.11+**
- **Node.js 18+**
- **[uv](https://docs.astral.sh/uv/)** — for Langflow (`pip install uv` or `curl -LsSf https://astral.sh/uv/install.sh | sh`)

---

## Setup

### 1. Clone and configure environment

```bash
git clone <repo-url>
cd procur
cp .env.example .env
```

Open `.env` and fill in the values — you will get the Langflow IDs and API key in step 4 below.

```
DATABASE_URL=postgresql+psycopg2://procur:procur@localhost:5432/procur
LANGFLOW_URL=http://localhost:7860
LANGFLOW_API_KEY=        ← fill in after step 4
LANGFLOW_ORGANIZE_FLOW_ID=   ← fill in after step 4
LANGFLOW_WEBCHECK_FLOW_ID=   ← fill in after step 4
```

### 2. Start PostgreSQL

```bash
docker compose up -d
```

This starts a PostgreSQL 16 container on port 5432 with user/password/db all set to `procur`.

### 3. Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt

# Apply migrations
alembic upgrade head

# Seed demo data (full state with today's flagged request)
python -m app.seed --reset

# Start the API server
uvicorn app.main:app --reload
```

- API: `http://localhost:8000`
- Interactive docs: `http://localhost:8000/docs`
- Health check (shows Langflow status): `http://localhost:8000/api/health`

### 4. Langflow and flows

```bash
# In a separate terminal, from the repo root
uv run langflow run
```

Langflow opens at `http://localhost:7860`.

**One-time setup:**

1. **Add the Claude API key:**  
   Go to **Profile → Settings → Model Providers → Anthropic**, paste your Claude API key, and save. This lets both flows call `claude-haiku-5-5`.

2. **Import the flows:**  
   In Langflow, click **+ New flow → Import** and import both files:
   - `langflow/Organize.json` — parses messy text into line items
   - `langflow/Web Check.json` — searches the web for prices of unknown items

3. **Copy the flow IDs:**  
   Open each flow. The flow ID is in the URL: `http://localhost:7860/flow/<uuid>`. Copy the UUID for each flow and set it in `.env`:
   ```
   LANGFLOW_ORGANIZE_FLOW_ID=<uuid from Organize flow>
   LANGFLOW_WEBCHECK_FLOW_ID=<uuid from Web Check flow>
   ```

4. **Create a Langflow API key:**  
   Go to **Profile → Settings → Langflow API Keys → Add New**, copy the key, and set it in `.env`:
   ```
   LANGFLOW_API_KEY=<your-key>
   ```

5. **Restart the backend** so it picks up the new `.env` values:
   ```bash
   # Ctrl+C the uvicorn process, then:
   uvicorn app.main:app --reload
   ```

### 5. Frontend

```bash
cd frontend
npm install
npm run dev
```

The app is at `http://localhost:5173`. The Vite dev server proxies `/api/*` to `http://localhost:8000`.

---

## Running tests

All backend tests use an in-memory SQLite database — no PostgreSQL or Langflow required.

```bash
cd backend
pytest                           # run all 87 tests
pytest tests/test_pricing.py     # run a single file
pytest -v                        # verbose output
```

---

## Seeding demo data

```bash
cd backend

# Full demo state: seeds purchase history, stock levels, and today's 5-row
# request. The hydraulic oil row is automatically flagged at +29.5%.
python -m app.seed --reset

# Empty-today state: seeds history and stock but no today's request.
# Use this as the starting point for the demo video.
python -m app.seed --reset --empty-today
```

Both commands finish in under 2 seconds.

---

## Demo script

*Total: ~3 minutes*

### 1. The problem (20 s)

A manufacturer buys daily from small suppliers with no purchase database and unreliable warehouse stock records. Overpaying goes unnoticed.

### 2. Organize (40 s)

Start from the empty-today state:

```bash
python -m app.seed --reset --empty-today
```

In the app, click **Add requests** and paste the morning's WhatsApp message:

```
1. Hydraulic oil ISO VG 46, 20L – 4 drum, Warehouse, Rp 1.450.000/drum, CV Sinar Pelumas
2. Solenoid valve 24V DC, 1/2" – 2 pcs, Maintenance
3. Bearing 6205 ZZ – 20 pcs, Maintenance, Rp 38.500/pcs
4. Work gloves, cotton dotted – 10 doz, Production, Rp 96.000/doz
5. Packing tape 48mm, clear – 3 box, Warehouse, Rp 210.000/box
```

Click **Organize** — Claude Haiku turns the text into clean line items.

### 3. Check and mark (60 s)

Click **Save**. The queue fills. The hydraulic oil row is immediately flagged at **+29.5%**. Open it in the inspector:

- 3 past purchases, last-3 average = Rp 1.120.000
- Quoted at Rp 1.450.000 → **Rp 1.320.000 over reference** on 4 drums
- Stock already covers ~6 weeks (flag: stock cover high)

### 4. New item (30 s)

The solenoid valve has no purchase history. Procur.AI searched the web: 3 quotes, **median Rp 425.000**.

### 5. Decide (20 s)

Use **Compare suppliers**, **Return to requester** (oil), and **Approve** (rest).

### 6. Under the hood (20 s)

Show the two Langflow flows running on Claude Haiku. Point out: the model reads text; every number — price, percentage, flag — comes from the database.

---

## Fallbacks

| Situation | Fallback |
|---|---|
| Langflow or Claude API is down | The header shows **AI offline**. Seeded web quotes cover the solenoid valve demo row. |
| Web Search gets rate-limited | 7-day quote cache; seeded quotes are used for the demo item. |
| No Docker available | Set `DATABASE_URL=sqlite:///./procur.db` in `.env` to use SQLite. |
