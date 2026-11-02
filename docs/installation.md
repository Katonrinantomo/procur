# Installation

Commands are PowerShell (Windows) unless marked otherwise. On macOS/Linux replace `.venv\Scripts\Activate.ps1` with `source .venv/bin/activate` and `Copy-Item` with `cp`.

## Prerequisites

| Requirement | Used for |
|---|---|
| Docker Desktop | PostgreSQL 16 (`docker-compose.yml`). Optional with the SQLite fallback. |
| Python 3.11+ | Backend |
| Node.js 18+ | Frontend (Vite 8, React 19) |
| [uv](https://docs.astral.sh/uv/) (`pip install uv`) | Running Langflow locally |
| Claude API key ([console.anthropic.com](https://console.anthropic.com)) | Entered in Langflow, never in the backend |
| Serper API key ([serper.dev](https://serper.dev)) | Marketplace search inside the maker_agent flow |

The app runs without Langflow: history-based checks, the queue, history, import, review and the audit log all work. Organizing pasted text, web prices and vendor quotations need the flows.

## 1. Clone

```powershell
git clone <repo-url> Procur
cd Procur
```

## 2. Database

```powershell
docker compose up -d
```

PostgreSQL 16 on `127.0.0.1:5432`; user, password and database are all `procur`. Data persists in the `postgres_data` volume.

**SQLite instead:** skip Docker and set `DATABASE_URL=sqlite:///./procur.db` in step 4.

## 3. Backend dependencies

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 4. Environment variables

```powershell
Copy-Item .env.example .env
```

The backend reads `backend/.env` (relative to where uvicorn starts, so always start it from `backend/`).

| Variable | Required | Notes |
|---|---|---|
| `DATABASE_URL` | yes | `postgresql+psycopg2://procur:procur@localhost:5432/procur` or `sqlite:///./procur.db` |
| `JWT_SECRET` | yes, ≥ 32 chars | `python -c "import secrets; print(secrets.token_hex(32))"`. The API exits at startup without it. |
| `DEMO_PASSWORD` | no (default `password123`) | Password of the seeded `purchasing`, `owner`, `finance` users |
| `ALLOWED_HOSTS` | no (default `localhost,127.0.0.1`) | Host headers accepted by `TrustedHostMiddleware` |
| `LANGFLOW_URL` | no (default `http://localhost:7860`) | |
| `LANGFLOW_API_KEY` | for AI features | Langflow API key (step 7) |
| `LANGFLOW_ORGANIZE_FLOW_ID` | for Add requests / Quick check | |
| `LANGFLOW_MAKER_FLOW_ID` | for web prices / vendor quotes | |
| `LANGFLOW_WEBCHECK_FLOW_ID` | no | Legacy flow, only used by `flowcheck` |
| `LANGFLOW_CHECKER_FLOW_ID`, `LANGFLOW_NARRATOR_FLOW_ID` | no | Reserved for later milestones (contracts exist, no service uses them yet) |

Thresholds (`MATCH_THRESHOLD`, `FLAG_PRICE_ABOVE_REF_PCT`, `WEB_QUOTE_MAX_AGE_DAYS`, price bands, …) are also settings in `app/config.py` and can be overridden from `.env`. An empty flow ID only disables that flow; startup logs a warning per missing ID.

## 5. Migrate and seed

```powershell
alembic upgrade head
python -m app.seed --reset
```

The seed creates purchase history, stock levels, three users and today's 5-row demo request (the hydraulic oil row ends flagged at +29.5%). Use `--empty-today` to skip today's request. The seed refuses to reset a non-localhost database or `APP_ENV=production` unless `--i-know-what-i-am-doing` is passed.

Re-seed after upgrading from a build before M16: older password hashes no longer verify.

## 6. Run the backend

```powershell
uvicorn app.main:app --reload
```

- API: `http://localhost:8000`, OpenAPI UI: `http://localhost:8000/docs`
- Health: `http://localhost:8000/api/health`

## 7. Langflow and flows

In a second terminal, from the repo root:

```powershell
uv run langflow run
```

Then in `http://localhost:7860`, once:

1. **Profile → Settings → Model Providers → Anthropic**: paste the Claude API key.
2. **+ New flow → Import**: `langflow/Organize.json` and `langflow/Maker.json` (optionally `langflow/Web Check.json`).
3. In the Maker flow, set the **Serper Multi Search** component's `serper_api_key` (use a Langflow global variable; exported flows must not contain keys).
4. Copy each flow's UUID from its URL (`/flow/<uuid>`) into `LANGFLOW_ORGANIZE_FLOW_ID` and `LANGFLOW_MAKER_FLOW_ID`.
5. **Profile → Settings → Langflow API Keys → Add New**: copy it into `LANGFLOW_API_KEY`.
6. Restart uvicorn.

Each flow's model component should be provider Anthropic, model `claude-haiku-5-5`, temperature 0. Chat Output names must match the contracts: `organize_json` (Organize); `extract_json`, `maker_json`, `serper_raw` (Maker).

## 8. Frontend

In a third terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. Vite proxies `/api/*` to `http://localhost:8000`; the backend's CORS only allows this origin.

### All at once (Linux, bash)

`./start.sh` starts PostgreSQL, Langflow (`LANGFLOW_DIR`, default `~/langflow`), the backend from `backend/.venv` and the frontend, waits for each to answer and writes logs to `/tmp/procur-*.log`. `./stop.sh` stops them.

## Verify

```powershell
Invoke-RestMethod http://localhost:8000/api/health
# status: ok, app: Procur.AI, langflow: ok | down | not configured
```

From `backend/`, with Langflow running:

```powershell
python -m app.flowcheck     # every fixture through every configured flow; exit 1 on failure
pytest                      # offline suite, no Langflow or PostgreSQL needed
```

Sign in at `http://localhost:5173` as `owner` / `DEMO_PASSWORD`: the Review page lists the flagged hydraulic oil row.
