# Procur.AI

## 📚 Documentation
| | |
|---|---|
| [⚙️ Architecture](docs/architecture.md) | System design, components and flow |
| [📁 Structure](docs/structure.md) | Project organization and responsibilities |
| [🚀 Installation](docs/installation.md) | Requirements and steps to run the project |
| [🧠 Technical decisions](docs/decisions.md) | Trade-offs and design justifications |
| [📖 Usage guide](docs/usage.md) | Screens, roles, demo flow and common errors |
| [🔌 API](docs/api.md) | Endpoints, request/response and examples |
| [🧪 Testing](docs/testing.md) | Tests, coverage, eval harness and release check |

---

## Description

Procur.AI is a procurement price-check web app built for a manufacturing hackathon demo.

- **What it does:** purchasing staff paste the day's purchase requests (a WhatsApp or email message) or upload a vendor quotation (PDF/XLSX). A Langflow flow running Claude Haiku 5.5 turns the messy text into structured line items. The backend then checks every line against the company's own purchase history — or, for items never bought before, against marketplace listings found on the web — and flags anything that looks overpriced, over-stocked, unusually large or from an unknown supplier.
- **What problem it solves:** small manufacturers buy daily from many small suppliers, with no purchase database and unreliable stock records. Overpaying goes unnoticed because nobody has the reference price at hand when the request arrives.
- **Real use case:** a request for 4 drums of hydraulic oil at Rp 1.450.000/drum arrives on WhatsApp. Procur.AI matches it to the catalog item, averages the last 3 purchases (Rp 1.120.000), shows the row is **+29.5%** above reference and that stock already covers ~6 weeks, and the owner returns it to the requester with a logged reason.

**Core rule: the model handles language; the backend handles numbers.** Claude only reads text and reports listings it saw. Every price, percentage, band, flag, risk score and vendor score is computed in Python from integer rupiah.

## Quick start

With PostgreSQL, the backend and the frontend running (see [installation](docs/installation.md)):

```powershell
cd backend
python -m app.seed --reset        # demo history, stock, users and today's flagged request
uvicorn app.main:app --reload
```

```powershell
cd frontend
npm run dev                       # http://localhost:5173
```

Sign in as `owner` with `DEMO_PASSWORD` from `backend/.env`. The Review page opens with the hydraulic oil row flagged at +29.5%. Or check it through the API:

```powershell
$t = (Invoke-RestMethod -Method Post http://localhost:8000/api/auth/login `
  -ContentType 'application/json' `
  -Body '{"username":"owner","password":"password123"}').access_token
Invoke-RestMethod http://localhost:8000/api/queue -Headers @{Authorization = "Bearer $t"}
```

## Technologies used

| Layer | Choice |
|---|---|
| Frontend | React 19, Vite, TypeScript, Tailwind CSS v4, TanStack Query v5 |
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, httpx, rapidfuzz, slowapi |
| Documents | openpyxl (XLSX), pdfplumber (PDF text layer) |
| Database | PostgreSQL 16 via Docker Compose (SQLite fallback via `DATABASE_URL`) |
| AI flows | Langflow (local, run with `uv`), Serper search for marketplace listings |
| Model | Claude Haiku 5.5 (`claude-haiku-5-5`) via the Claude API, called only from Langflow |
| Tests | pytest, 458 tests collected, SQLite in-process (no Langflow or PostgreSQL needed); 95% line coverage over `app/services` |

## Quick installation

1. `docker compose up -d` — PostgreSQL 16 on `127.0.0.1:5432`.
2. In `backend/`: create a venv, `pip install -r requirements.txt`, copy `.env.example` to `.env` (set `JWT_SECRET`), `alembic upgrade head`, `python -m app.seed --reset`, `uvicorn app.main:app --reload`.
3. In `frontend/`: `npm install`, `npm run dev`. Import the flows into Langflow and set their IDs in `backend/.env` to enable the AI features.

Full steps: [docs/installation.md](docs/installation.md).

## Architecture (summary)

A React SPA talks only to a FastAPI backend through `/api` (proxied by Vite). The backend owns all data and arithmetic: a check engine matches each request line to the catalog with rapidfuzz, computes a reference price (mean of the last 3 purchases, or the median of at least 3 evidence-checked web listings), the percentage difference, four rule-based flags and a 0–100 risk score. Language work — organizing pasted text, reading quotations, picking marketplace listings — is delegated to Langflow flows, called from one client module. Model output is validated against Pydantic contracts and listings are kept only if their URL and price appear in the raw search results. Decisions are written to an append-only audit log. Details: [docs/architecture.md](docs/architecture.md).

## Project structure

```
Procur/
├── backend/            FastAPI app, Alembic migrations, seed, eval harness, tests
│   ├── app/
│   │   ├── routers/    HTTP endpoints (one module per resource)
│   │   ├── services/   Check engine, pricing, flags, matcher, Langflow client
│   │   └── flows/      Output contracts for every Langflow flow
│   ├── eval/           Offline/live accuracy suites (E1–E6)
│   └── tests/          pytest suite
├── frontend/           React + Vite SPA
├── langflow/           Exported flows (Organize, Web Check, Maker) + fixtures
├── design/             Approved static UI references
├── plans/              Build plans per milestone
└── scripts/            Release check, secrets check, README claims check
```

Full tree: [docs/structure.md](docs/structure.md).
