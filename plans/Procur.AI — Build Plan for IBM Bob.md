# Procur.AI — Build Plan for IBM Bob

Oct 10, 2026 · @Katon Rinantomo

## Overview

We build concept B, the daily queue with an inspector, as a working web app. Purchasing pastes the day's requests, Langflow turns the text into rows, the backend checks each row against the database, and the screen shows what needs a second look.

The reference case is a manufacturing company with no purchase database and unreliable warehouse stock records. Procur.AI gives it both: a clean purchase history, and a check on every new request.

**The core loop: organize, check, mark**

1. **Organize.** Someone pastes requests as messy text, such as a WhatsApp message from the warehouse. A Langflow flow running Claude Haiku through the Claude API turns it into line items: item, quantity, unit, department, quoted price, supplier.
2. **Check.** The backend matches each item to the catalog. A known item gets a reference price from its last 3 purchases. An unknown item goes to a second Langflow flow that searches the web for prices.
3. **Mark.** Plain backend rules set each row's status to Checked, New item or Flagged, and record the reasons.

**One rule for the whole build: the model handles language, the backend handles numbers.** Haiku reads messy text and summarizes web results. Every price, percentage and flag is computed in code from the database, so the demo is trustworthy and testable.

**Scope for the hackathon**

| Feature | Priority |
| --- | --- |
| Today screen: queue table + inspector, matching the design | Must ship |
| Add requests by pasting text | Must ship |
| Organize flow in Langflow (Claude Haiku via the Claude API) | Must ship |
| History check: match item, reference price, difference % | Must ship |
| Web check for new items (second Langflow flow) | Must ship |
| Flag rules: price, stock cover, unusual quantity | Must ship |
| Approve and Return to requester actions | Must ship |
| Flag box with reasons and numbers (M11) | Must ship |
| Real market quotes with capture dates (M12) | Must ship |
| Compare suppliers panel (from purchase history) | Should ship |
| Excel import of past purchases (M13) | Should ship |
| History page: purchases and past requests (M14) | Should ship |
| Quick check page (M15) | Should ship |
| Suppliers page | Stretch |
| Dark mode, mobile polish | Stretch |
| Login, user roles, PO generation | Out of scope |

The app is called Procur.AI (Procur for short). Keep the name in one constant, APP\_NAME, so any later rename is a one-line change.

## Architecture

&#91;embedded content: architecture · 6 parts\]

The browser only talks to the backend, and only the backend talks to the database and to Langflow. Use this diagram as the technical diagram in the Stage 2 documentation.

**One request, end to end**

1. Purchasing pastes text in the web app. The backend sends it to Flow 1, and Haiku returns line items as JSON.
2. The person checks the preview and saves. The backend stores the request and its rows in PostgreSQL.
3. For each row, the backend matches the catalog and computes the reference price from purchase history. It calls Flow 2 only for items with no history.
4. Flag rules set each row's status. The queue and the inspector read everything back from the database.

## Tech stack and repo layout

Python on the backend, React on the frontend, PostgreSQL for data, Langflow for the two AI flows. Python matches Langflow, and FastAPI gives free API docs at `/docs` for testing and the demo.

| Layer | Choice | Why |
| --- | --- | --- |
| Frontend | React + Vite + TypeScript, Tailwind CSS, TanStack Query | Quick to scaffold; Tailwind maps one-to-one to the design's values |
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, httpx, rapidfuzz | Same language as Langflow; typed shapes; fuzzy name matching |
| Database | PostgreSQL 16 in Docker Compose | A real relational store for purchase history; SQLite is the no-Docker fallback |
| AI flows | Langflow, run locally with uv | Visual flows judges can see; the Claude API key stays inside Langflow |
| Model | Claude Haiku 5.5 via the Claude API (`claude-haiku-5-5`) | Built for fast, low-cost extraction and classification; swap to Granite on watsonx.ai later by changing one component |
| Web search | Langflow Web Search component (DuckDuckGo) | No API key; results cached in the database |
| Tests | pytest + FastAPI TestClient | Locks the price and flag math to the demo numbers |

```text
procur/
├── .bob/rules/procur.md         # project rules Bob reads in every conversation
├── AGENTS.md                    # created by Bob's /init
├── plans/
│   └── procur-plan.md           # this doc, exported as Markdown
├── design/
│   └── reference.html           # the approved screen (static HTML)
├── docker-compose.yml           # PostgreSQL
├── .env.example
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py            # settings from .env, APP_NAME constant
│   │   ├── db.py
│   │   ├── models.py            # SQLAlchemy tables
│   │   ├── schemas.py           # Pydantic request/response shapes
│   │   ├── seed.py              # demo data: python -m app.seed --reset
│   │   ├── routers/             # requests, queue, items, imports, health
│   │   └── services/
│   │       ├── langflow_client.py
│   │       ├── organizer.py     # text -> line items (Flow 1)
│   │       ├── matcher.py       # line item -> catalog item
│   │       ├── pricing.py       # reference price, difference %
│   │       ├── web_check.py     # web quotes (Flow 2) + cache
│   │       ├── flags.py         # flag rules
│   │       └── checker.py       # runs match -> price -> flags
│   ├── alembic/
│   └── tests/
├── frontend/
│   └── src/  (api/, components/, pages/, lib/format.ts)
└── langflow/
    ├── organize.json            # exported flows, committed
    └── web_check.json
```

Two files carry the plan and the design into Bob: `plans/procur-plan.md` (export this doc as Markdown) and `design/reference.html` (the file attached in chat). Every prompt below points at them with `@`.

## Database

Nine tables in PostgreSQL. Money is always an integer number of rupiah (`BIGINT`), never a float. Timestamps are stored with time zone, and "today" means today in Asia/Jakarta.

| Table | Columns | Links to |
| --- | --- | --- |
| `suppliers` | id, name (unique), phone, city, created\_at | — |
| `items` | id, name (unique, clear English), aliases (JSON list of other names, e.g. "oli hidrolik 46"), category, unit, created\_at | — |
| `purchases` | id, po\_number, purchase\_date, item\_id, supplier\_id, qty, unit\_price\_idr, source (seed / csv / excel / manual) | items, suppliers |
| `stock` | item\_id (primary key), qty\_on\_hand, avg\_monthly\_use, updated\_at | items |
| `requests` | id, requested\_at, requested\_by, raw\_text, created\_at | — |
| `request_items` | id, request\_id, line\_no, raw\_name, item\_id (empty = new item), department, qty, unit, quoted\_unit\_price\_idr, quoting\_supplier\_name, supplier\_id, reference\_unit\_price\_idr, diff\_pct, checked\_via (history / web / none), history\_count, status, check\_error, checked\_at | requests, items, suppliers |
| `web_quotes` | id, request\_item\_id (empty for cached quotes), item\_key, query, title, url, seller, price\_idr, fetched\_at | request\_items |
| `flags` | id, request\_item\_id, code, message, created\_at | request\_items |
| `actions` | id, request\_item\_id, action (approve / return), note, actor, created\_at | request\_items |

Row status is one of `pending`, `checked`, `new`, `flagged`, `approved`, `returned`. Flag code is one of `PRICE_ABOVE_REF`, `STOCK_COVER_HIGH`, `QTY_UNUSUAL`, `NEW_SUPPLIER`.

**Seed data.** One command, `python -m app.seed --reset`, rebuilds the demo state with a fixed random seed: 8 suppliers, about 40 catalog items in 5 categories (spare parts, lubricants, safety gear, packaging, office), about 300 purchase lines over 12 months with small price drift, and a stock row per item. Stock levels and past quantities are set so that only row 01 below gets flagged.

**Today's demo rows.** These reproduce the design exactly, and the tests check them.

| # | Item | Dept. | Qty | Quoted / unit (Rp) | Data to seed | Expected result |
| --- | --- | --- | --- | --- | --- | --- |
| 01 | Hydraulic oil ISO VG 46, 20L | Warehouse | 4 drum | 1.450.000, CV Sinar Pelumas, 08:12 | 3 buys: 18 Mar 2026 PO-0318 CV Sinar Pelumas 6 × 1.115.000 · 3 Jun 2026 PO-0603 PT Mitra Oli Jaya 4 × 1.115.000 · 12 Aug 2026 PO-0812 PT Mitra Oli Jaya 4 × 1.130.000. Stock 3 drum, use 2 drum/month | Reference 1.120.000, +29.5%, Flagged (price, stock cover) |
| 02 | Solenoid valve 24V DC, 1/2" | Maintenance | 2 pcs | none | Not in catalog. 3 cached web quotes: 398.000, 425.000, 465.000 | Reference 425.000 (median), New item |
| 03 | Bearing 6205 ZZ | Maintenance | 20 pcs | 38.500 | 6 buys, last 3 average 38.000 | +1.3%, Checked |
| 04 | Work gloves, cotton dotted | Production | 10 doz | 96.000 | 4 buys, last 3 average 98.000 | −2.0%, Checked |
| 05 | Packing tape 48mm, clear | Warehouse | 3 box | 210.000 | 9 buys, last 3 average 205.000 | +2.4%, Checked |

If the reference company can share even 2 to 3 months of purchase notes, fill them into the Excel template and import them (M13). Real history makes the demo far more convincing; rename suppliers if they prefer privacy.

## Backend logic

The backend owns every number: it matches items, computes reference prices, applies the flag rules and stores the result. Langflow is called only to read messy text and web pages.

**API**

| Endpoint | What it does |
| --- | --- |
| `POST /api/requests/parse` | Sends pasted text to Flow 1 (Organize) and returns draft line items. Saves nothing. |
| `POST /api/requests` | Saves a request and its line items, runs the check on each, returns the rows |
| `GET /api/queue?date=&status=` | Rows for the queue table, sorted flagged, new, checked, then approved/returned, plus counts per status |
| `GET /api/request-items/{id}` | Everything the inspector shows: totals, stock, flags, last 5 purchases or the web quotes |
| `POST /api/request-items/{id}/recheck` | Runs the check again, after an edit or a failed web check |
| `POST /api/request-items/{id}/approve` | Sets status `approved` and logs an action |
| `POST /api/request-items/{id}/return` | Sets status `returned` with a note and logs an action |
| `GET /api/items/{id}/suppliers` | Compare suppliers: each supplier's last price, last date and number of buys |
| `POST /api/imports/purchases` | CSV import of past purchases (M9) |
| `GET /api/health` | Database and Langflow status, for the header indicator |

**The check, step by step** (`checker.py`)

1. **Match.** Normalize the name: lowercase, strip punctuation, unify units ("20 liter", "20 ltr", "20 L" become "20l"). Compare it with every catalog name and alias using rapidfuzz `token_set_ratio`. A score of 85 or more is a match; anything lower makes the row a new item.
2. **Reference from history.** For a matched item, average the unit prices of its last 3 purchases by date. Fewer than 3 is fine; zero purchases sends the row to the web check.
3. **Reference from the web.** Reuse the newest cached quotes for the same item if they are at most 60 days old, and show when they were captured. Otherwise call Flow 2 (Web check) with "harga \<item name>". Drop quotes with no URL or a zero price, keep at most 5, and take the median.
4. **Difference.** `diff_pct = (quoted − reference) ÷ reference × 100`, rounded to 1 decimal. Empty when either price is missing.
5. **Flags.** Run every rule in the table below. Each rule is a small pure function with its threshold in config.
6. **Status.** Any flag makes the row `flagged`. Otherwise a reference from the web (or none) makes it `new`, and a reference from history makes it `checked`. Approve and Return override this.

| Flag code | Fires when | Message shown |
| --- | --- | --- |
| `PRICE_ABOVE_REF` | diff\_pct > 15 | Price > 15% above 3-buy average (or "above web median") |
| `STOCK_COVER_HIGH` | qty\_on\_hand ÷ avg\_monthly\_use > 1 month | Stock covers \~N weeks of use, with N = round(months × 4.3) |
| `QTY_UNUSUAL` | qty > 2 × the median quantity of past purchases | Quantity is about N× the usual order |
| `NEW_SUPPLIER` | a quoting supplier is named but has no purchases at all | Supplier not in purchase history |

**When something fails.** If Langflow is down or answers badly, the row is still saved with status `pending` and a `check_error`, and the UI shows Retry. Organize output is validated with Pydantic, and one retry sends the validation error back to the flow. The editable preview lets a person fix anything the model got wrong.

**Tests that must pass.** The 5 demo rows give exactly the expected results in the Database section. "oli hidrolik 46 20 liter" matches Hydraulic oil ISO VG 46, 20L. Tests never call Langflow; they mock the client.

## Langflow

Two flows, both running Claude Haiku 5.5 through the Claude API, set up once in Langflow's Model Providers. The backend calls them with Langflow's run API; the browser never talks to Langflow directly.

**Setup, once**

1. Install and start Langflow: `uv pip install langflow`, then `uv run langflow run`. It opens in your browser (default `http://localhost:7860`).
2. In the Claude Console (platform.claude.com), create an API key. A monthly spend limit there keeps testing costs predictable.
3. In Langflow, open profile icon → Settings → Model Providers, choose Anthropic, paste the key into API Key, and click Save. Then enable `claude-haiku-5-5` so it appears in the Language Model component.
4. Open profile icon → Settings → Langflow API Keys → Add New. Put the key in the backend `.env` as `LANGFLOW_API_KEY`.

**Flow 1: Organize** (pasted text → line items)

Chat Input → Language Model → Chat Output. Provider Anthropic, model `claude-haiku-5-5`, temperature 0. The Anthropic bundle component works too and adds fields such as Max Tokens (default 4096).

Turn on System Message in the Language Model's inspection panel and paste these instructions there. Avoid the Prompt Template here: it reads every pair of curly braces as a variable, which breaks the JSON example. If your version has no System Message field, use a Prompt Template and describe the JSON in words, as Flow 2 does.

```text
You turn purchase requests into line items for a manufacturing company in Indonesia.
The text can be Indonesian or English, informal, with typos and abbreviations.

Reply with JSON only. No explanation, no code fences. Shape:
{"items": [{"name": "...", "qty": 1, "unit": "pcs", "department": null, "quoted_unit_price_idr": null, "supplier": null}]}

Rules:
- One object per distinct item. Keep specs in the name: size, grade, voltage, part number.
- Write the name in clear English. Keep brand names and part numbers as written.
- qty is a number. unit is one of: pcs, box, drum, doz, roll, pack, set, kg, liter, meter, yard.
- "lusin" means doz, "dus" means box.
- Prices become an integer in rupiah per unit: "1,45jt" = 1450000, "Rp 38.500" = 38500, "96rb" = 96000.
- department is one of: Warehouse, Maintenance, Production, Office, or null.
- Never invent a quantity, price or supplier. If the text does not say it, use null.

Example input:
gudang minta oli hidrolik 46 20L 4 drum, harga 1,45jt/drum dari CV Sinar Pelumas
Example output:
{"items": [{"name": "Hydraulic oil ISO VG 46, 20L", "qty": 4, "unit": "drum", "department": "Warehouse", "quoted_unit_price_idr": 1450000, "supplier": "CV Sinar Pelumas"}]}
```

**Flow 2: Web check** (item name → price offers)

Chat Input → Web Search (mode Web, Max Results 5, Max Content Length 1500) → Type Convert (to Message) → Prompt Template → Language Model (same settings) → Chat Output. Chat Input also feeds the template's `{item}` variable and the Web Search's Search Query field.

```plain
You check market prices for a purchasing team in Indonesia.

Item: {item}

Search results:
{results}

List the offers in the results that sell this exact item (same specs).
For each offer give four keys: title, url, seller, price_idr (an integer, rupiah per single unit).
Skip results with no clear price, used items, bundles and different specs.
Reply with only a JSON array of objects with those four keys.
Reply with an empty JSON array if nothing qualifies.
```

Test both flows in the Playground with the demo text first. Then copy each flow's ID (from its URL or API access panel) into `.env`, export both flows as JSON into `langflow/`, and commit them.

**How the backend calls a flow** (`services/langflow_client.py`)

```python
import httpx
from app.config import settings

class LangflowError(Exception):
    pass

async def run_flow(flow_id: str, text: str) -> str:
    url = f"{settings.LANGFLOW_URL}/api/v1/run/{flow_id}"
    payload = {"input_value": text, "input_type": "chat", "output_type": "chat"}
    headers = {"x-api-key": settings.LANGFLOW_API_KEY}
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(url, json=payload, headers=headers)
            r.raise_for_status()
            return r.json()["outputs"][0]["outputs"][0]["results"]["message"]["text"]
    except (httpx.HTTPError, KeyError, IndexError) as e:
        raise LangflowError(f"Langflow call failed: {e}") from e
```

```text
LANGFLOW_URL=http://localhost:7860
LANGFLOW_API_KEY=
LANGFLOW_ORGANIZE_FLOW_ID=
LANGFLOW_WEBCHECK_FLOW_ID=
```

The Web Search component scrapes DuckDuckGo. Langflow's docs warn it can be rate-limited and is not meant for production, which is why quotes are cached for 7 days and the demo quotes are seeded.

The hackathon page lists watsonx Orchestrate among the tools. Langflow flows can be imported into Orchestrate as agent tools, so these two flows could later back an Orchestrate agent; treat that as a stretch for the final.

**Switching back to watsonx.ai later.** Replace the Language Model in both flows with the IBM watsonx.ai component (Langflow's IBM bundle), fill in your project ID, API key and region URL, and pick `granite-4-h-small`. The instructions, the flow IDs and the backend stay the same.

## UI spec

The UI must match `design/reference.html` exactly: one Today screen, queue table on top, inspector below. Bob gets the file itself; the tokens and rules here are your checklist when reviewing its work.

| Token | Value | Used for |
| --- | --- | --- |
| Font | Geist 400/500/600; Geist Mono for numbers and PO numbers | All text; tabular figures in tables |
| Text | `#1A1A1A` primary, `#4A4A46` secondary, `#5E5E59` / `#6B6B66` muted | Body, labels, captions |
| Surfaces | `#FFFFFF` page, `#F7F7F5` table header, `#F2F2EF` active nav | Backgrounds |
| Lines | `#E6E6E2` table and panel border, `#EDEDEA` row dividers, `#E0E0DB` button and chip borders | Borders |
| Flagged | text `#9A3412`, chip `#FDEBDD`, row `#FFF8F2`, 3px left bar `#9A3412` | Flagged rows and chips; the flag box uses background #FFF4EC, border #F2C7A5 and reason text #7C2D12 |
| New item | text `#1E3A8A`, chip `#E8EEFB` | New item chips |
| Checked | text `#3F3F3B`, chip `#F0F0EC` | Checked chips |
| Approved | text `#166534`, chip `#E7F4EC` | After Approve (not in the mock) |
| Returned | text `#4A4A46`, white chip with `#E0E0DB` border | After Return (not in the mock) |
| Buttons | primary `#1A1A1A` with white text; secondary white with `#E0E0DB` border; radius 10px; height 44px (40px in header) | Actions |
| Radius | 12px table and inspector, 10px buttons, 999px filter chips, 6px status chips | Shapes |
| Spacing | max width 1240px, page padding 28px, 28px between blocks, cells 13px × 16px | Layout |

**Layout, top to bottom**

1. **Header.** App name, nav (Today, Quick check, History, Import), and the Add requests button on the right, over a 1px bottom border.
2. **Title row.** "Requests · Sat, 10 Oct 2026", a summary line ("5 requests · 3 checked · 1 new item · 1 flagged"), and filter chips with counts on the right.
3. **Queue table.** Columns in this order: #, Item, Dept., Qty, Quoted / unit, Reference / unit, Diff., Checked via, Status. Numbers are right-aligned in Geist Mono. Flagged rows come first; the first flagged row is selected on load. A click or Enter selects a row.
4. **Inspector.** One bordered panel in two halves.
   - Left: "Row 01 · Requested by Warehouse, 08:12", the item name, the flag box (when the row has flags), six fields (Quoted total, At reference price, Over reference, Quoting supplier, Stock on record, Avg. monthly use), and the buttons Compare suppliers, Approve, Return to requester.
   - Right: purchase history (Date, PO no., Supplier, Qty, Price / unit) with a "3-buy average (reference)" footer. For web-checked rows, a Web quotes table instead (Seller, Offer as a link, Price / unit) with a "Median of N quotes (reference)" footer.
5. **Add requests dialog** (not in the mock, same style). Textarea, then Organize, then an editable preview table, then Save and check.

**Formatting and states**

- Rupiah with `Intl.NumberFormat('id-ID')`, so 1.450.000. The "Rp" prefix appears only on the inspector totals.
- Percentages carry a sign and one decimal, with a real minus sign (−2.0%). Only flagged differences use the flag color.
- Dates read "12 Aug 2026".
- Loading shows skeleton rows. An empty day shows "No requests yet today" with the Add requests button. Errors show an inline banner with Retry.
- Status is always a word, never color alone. Rows are keyboard-focusable, and every button is a real `<button>` at least 44px tall.
- On narrow screens the table scrolls inside its box and the inspector halves stack.

## Working with IBM Bob

Run one milestone per conversation: plan it, check the plan, then build it. Bob has three modes: Plan writes Markdown plan files, Agent implements them, and Ask is for questions about the code.

**Set up the repo once**

1. Create the repo folder. Add `design/reference.html` (the file from chat) and export this doc as Markdown to `plans/procur-plan.md`.
2. Run `/init` in Bob. It creates `AGENTS.md` and per-mode rule files in `.bob`.
3. Create `.bob/rules/procur.md` with the rules below. Bob adds every file in `.bob/rules` to every conversation, in all modes.
4. Run `git init` and commit. Commit again after every milestone that passes its check.

```markdown
# Procur.AI project rules

## Stack
- Backend: Python 3.11+, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, httpx, rapidfuzz, pytest.
- Frontend: React + Vite + TypeScript, Tailwind CSS, TanStack Query.
- Database: PostgreSQL 16 via docker-compose.
- AI: Langflow flows, called only from backend/app/services/langflow_client.py.

## Non-negotiables
- The model handles language; code handles numbers. Never ask an LLM to compute prices, percentages, totals or flags.
- Money is integer rupiah (BIGINT in the database, int in Python). Never use floats for money.
- "Today" means today in Asia/Jakarta.
- The frontend never calls Langflow or the Claude API directly. The Claude API key lives only in Langflow.
- Secrets live only in .env. Keep .env.example current. Never commit .env.
- The app name lives in one constant: APP_NAME.

## Design
- design/reference.html is the approved design. Match its colors, font sizes, spacing, borders and column order exactly.
- Use only the colors listed in plans/procur-plan.md (UI spec). No gradients, shadows, emoji or extra icons.
- Fonts: Geist and Geist Mono. Numbers use Geist Mono with tabular figures.

## Working style
- Work only on the current milestone. List the files you will touch before editing.
- Ask before adding a dependency that is not listed above.
- Every function in pricing.py and flags.py has a pytest test.
- Never change seed numbers or test expectations to make a test pass.
- Code, comments and UI text in English.
```

**Habits that keep Bob on track**

- Point at files with `@`: `@plans/procur-plan.md`, `@design/reference.html`, `@backend/app/services/`.
- For the two hardest milestones, M3 (check engine) and M6 (Today screen), send the prompt in Plan mode first. Read the plan, fix it in the same conversation, then start a new conversation in Agent mode: "Implement @plans/\<file>".
- Read the to-do list Bob proposes before approving. Approve edits and commands one by one, especially migrations and anything that deletes files.
- Start a new conversation for each milestone so old context does not leak in.
- When something breaks, paste the exact error and the command you ran, and ask Bob to fix only that.
- The Enhance Prompt button (sparkle icon) can quietly add scope. Read its version before sending.
- The numbers in the Database section are the source of truth. If a test fails, the code is wrong, not the test.

## Prompt sequence

Fifteen prompts in build order; M11 to M15 come from the first review of the built app. Each one names its mode and ends with a check; don't start the next milestone until the check passes and you've committed. The prompts refer to sections of this doc by name, so they work once it's exported to `plans/procur-plan.md`.

### M1 · Scaffold the project

Mode: Agent.

```text
Read @plans/procur-plan.md (sections "Tech stack and repo layout" and "Langflow") and set up the monorepo skeleton.

backend/
- FastAPI app in app/main.py with GET /api/health returning {"status": "ok", "app": APP_NAME}.
- app/config.py: pydantic-settings reading .env: DATABASE_URL, LANGFLOW_URL, LANGFLOW_API_KEY, LANGFLOW_ORGANIZE_FLOW_ID, LANGFLOW_WEBCHECK_FLOW_ID, plus APP_NAME = "Procur.AI".
- app/db.py: SQLAlchemy 2 engine and a session dependency.
- requirements.txt with the backend stack from the rules file.

frontend/
- React + Vite + TypeScript + Tailwind. Load Geist and Geist Mono from Google Fonts in index.html.
- Vite dev proxy: /api -> http://localhost:8000.
- One placeholder page that shows APP_NAME.

Root
- docker-compose.yml with postgres:16 (database "procur"), a named volume, port 5432.
- .env.example with every variable above, and a .gitignore that excludes .env, node_modules, __pycache__ and .venv.
- README.md with the commands to start the database, backend and frontend.

Do not build screens or tables yet.
```

Done when `docker compose up -d`, `uvicorn app.main:app --reload` and `npm run dev` all start, and the frontend shows "Procur.AI" in Geist.

### M2 · Database and seed data

Mode: Agent.

```text
Implement the database in @plans/procur-plan.md, section "Database".

- backend/app/models.py: SQLAlchemy 2 models for suppliers, items, purchases, stock, requests, request_items, web_quotes, flags and actions, with the columns and links listed. Money columns are BIGINT rupiah. status, code, checked_via, action and source are string enums with the listed values. Timestamps with time zone.
- Alembic with an initial migration.
- backend/app/seed.py, run with `python -m app.seed --reset`: wipe and recreate all data with a fixed random seed. Create 8 suppliers, about 40 catalog items in 5 categories (each with 1 to 3 Indonesian aliases), about 300 purchase lines over the last 12 months with small price drift, and a stock row for every item.
- Seed today's 5 demo requests exactly as in the table "Today's demo rows", including the 3 hydraulic oil purchases, the 3 cached web quotes for the solenoid valve, and stock of 3 drum with use of 2 drum per month for the oil. The oil's aliases include "oli hidrolik 46 20L". Set every other stock level and past quantity so no other row can be flagged.
- Leave reference price, difference and flags empty, with status "pending". M3 fills them.
- Print a summary of row counts at the end. Also support --empty-today, which seeds everything except today's requests.
```

Done when the migration runs, the seed prints its counts, and the 3 oil purchases average exactly 1.120.000.

### M3 · The check engine

Mode: Plan first, then Agent in a new conversation.

```text
Implement the check engine in @plans/procur-plan.md, section "Backend logic" ("The check, step by step" and the flag table).

Files in backend/app/services/:
- matcher.py: normalize names (lowercase, strip punctuation, unify units so "20 liter", "20 ltr" and "20 L" become "20l") and match against item names and aliases with rapidfuzz token_set_ratio. Threshold 85, from config.
- pricing.py: reference = mean of the last 3 purchase prices, rounded to whole rupiah; median of web quotes; diff_pct rounded to 1 decimal.
- flags.py: PRICE_ABOVE_REF, STOCK_COVER_HIGH, QTY_UNUSUAL and NEW_SUPPLIER as pure functions, thresholds in config, messages exactly as in the plan.
- web_check.py: for now, return the row's cached web_quotes only (Langflow comes in M5).
- checker.py: check_item(row) runs match, reference, difference, flags and status, then saves. check_request(request_id) runs every row.

Call check_request at the end of seed.py.

Tests in backend/tests/, using the seeded data:
- Hydraulic oil: reference 1120000, diff +29.5, flags PRICE_ABOVE_REF and STOCK_COVER_HIGH, status flagged, message "Stock covers ~6 weeks of use".
- Solenoid valve: no catalog match, reference 425000 from 3 web quotes, status new.
- Bearing +1.3, gloves -2.0, tape +2.4, all checked with no flags.
- "oli hidrolik 46 20 liter" matches "Hydraulic oil ISO VG 46, 20L".
```

Done when `pytest` passes and re-running the seed gives the same five results.

### M4 · REST API

Mode: Agent.

```text
Add the endpoints in the "API" table of @plans/procur-plan.md, section "Backend logic", except /api/requests/parse and /api/imports/purchases (they come in M5 and M9).

- Pydantic response models in schemas.py. Money as integers, diff_pct as a number or null.
- GET /api/queue?date=YYYY-MM-DD&status=: the default date is today in Asia/Jakarta. Sort flagged, new, checked, then approved and returned; within a group, by line number. Include counts per status.
- GET /api/request-items/{id}: row fields, requester and time, quoted total, total at reference, amount over reference, stock on hand, average monthly use, flags with messages, and either the last 5 purchases (date, PO number, supplier, qty, unit price) or the web quotes (seller, title, url, price).
- POST /api/requests saves a request with its line items and runs check_request.
- The approve, return (with a note) and recheck endpoints log to actions.
- GET /api/items/{id}/suppliers: per supplier, last unit price, last date and number of buys, cheapest last price first.
- TestClient tests for the queue order and the oil detail totals (5800000, 4480000, 1320000).
```

Done when `http://localhost:8000/docs` lists the endpoints and the tests pass.

### M5 · Langflow flows and client

Mode: you in Langflow first, then Agent.

Before prompting, build Flow 1 and Flow 2 exactly as in the Langflow section. Test both in the Playground with this text, put the flow IDs and API key in `.env`, and export both flows to `langflow/`.

```text
Pagi pak, permintaan hari ini:
- gudang: oli hidrolik 46 20L 4 drum, harga 1,45jt/drum dari CV Sinar Pelumas
- maintenance: bearing 6205 ZZ 20 pcs @38.500, solenoid valve 24V DC 1/2" 2 pcs
- produksi: sarung tangan katun bintik 10 lusin @96rb
- gudang: lakban bening 48mm 3 dus @210rb
```

```text
Connect the backend to Langflow as described in @plans/procur-plan.md, section "Langflow".

- services/langflow_client.py: use the run_flow function from the plan as written (httpx, 60 s timeout, x-api-key header, LangflowError).
- services/organizer.py: call the Organize flow, strip code fences if present, and parse {"items": [...]} with a Pydantic model LineItemDraft (name, qty, unit, department, quoted_unit_price_idr, supplier; qty may be null in a draft). If parsing fails, retry once with the validation error appended to the input. Return the drafts.
- POST /api/requests/parse: body {text, requested_by}, returns the drafts. On LangflowError, return 502 with the message.
- services/web_check.py: first reuse web_quotes with the same normalized query from the last 7 days. Otherwise call the Web check flow with "harga <item name>", parse the JSON array, drop offers with no url or price_idr <= 0, keep at most 5, and save them. The reference stays the median, computed in Python.
- checker.py: use web_check for unmatched items. If Langflow fails, keep status "pending", store check_error, and never fail the whole request.
- GET /api/health: add "langflow": "ok" or "down", checked against LANGFLOW_URL with a 3 s timeout.
- Tests mock run_flow; no live calls in tests. Add one test where the model wraps its JSON in code fences, and one where the first answer is invalid and the retry succeeds.
```

Done when `POST /api/requests/parse` with the sample text returns the 5 items with the right quantities and prices, and an unknown item gets web quotes.

### M6 · Today screen

Mode: Plan first, then Agent in a new conversation.

```text
Build the Today screen so it matches @design/reference.html exactly. That file is the approved design: copy its colors, font sizes, weights, spacing, borders, radii and column order. The tokens are listed in @plans/procur-plan.md, section "UI spec". Turn the inline styles into Tailwind classes (or one CSS file) with the same values; do not invent new styles.

Data:
- GET /api/queue for the title row counts, the filter chips and the table rows.
- GET /api/request-items/{id} for the inspector. Use TanStack Query.

Behavior:
- Filter chips All / Flagged / New / Checked, with counts, filter the rows.
- The first flagged row is selected on load. Clicking a row or pressing Enter on it selects it. The selected row is highlighted: flag style when flagged, #F5F5F2 otherwise.
- Inspector left: requester line, item name, the six fields, flag reasons, and the three buttons (wired in M8).
- Inspector right: purchase history with the "3-buy average (reference)" footer, or for web-checked rows a Web quotes table (Seller, Offer as a link, Price / unit) with "Median of N quotes (reference)".
- lib/format.ts: rupiah with Intl.NumberFormat('id-ID'), signed percentages with one decimal and a real minus sign, dates like "12 Aug 2026".
- Loading skeleton rows, the empty state "No requests yet today", and an error banner with Retry.

Components: AppHeader, QueueHeader, FilterChips, QueueTable, StatusChip, Inspector, HistoryTable, WebQuotesTable.
```

Done when, at 1280 px wide, the screen and `design/reference.html` look the same side by side, and selecting each row updates the inspector.

### M7 · Add requests

Mode: Agent.

```text
Add the Add requests dialog described in @plans/procur-plan.md (section "UI spec", layout item 5), in the same visual style as @design/reference.html.

Step 1: a textarea "Paste requests", a "Requested by" field and a primary button "Organize". It calls POST /api/requests/parse and shows "Organizing…" while waiting.
Step 2: an editable preview table (Item, Qty, Unit, Dept., Quoted / unit, Supplier) with a delete button per row and "Add row". Qty is required before saving. "Save and check" calls POST /api/requests, closes the dialog, refreshes the queue and selects the first new row.

Langflow errors appear inline with Retry, and the pasted text is never lost. Esc closes the dialog and focus returns to the Add requests button.
```

Done when pasting the sample text into an empty day (seed with `--empty-today`) produces the same 5 results as the seed.

### M8 · Actions and Compare suppliers

Mode: Agent.

```text
Wire the inspector buttons to the endpoints from M4.

- Approve: the row's chip becomes "Approved" (text #166534 on #E7F4EC) and the counts update.
- Return to requester: a small dialog asks for a required note, then the chip becomes "Returned" (text #4A4A46, white with a #E0E0DB border).
- Compare suppliers: a right-side panel listing GET /api/items/{id}/suppliers (Supplier, Last price / unit, Last bought, Buys), cheapest first, with the quoting supplier marked. For new items, list the web quotes instead.
- Approved and returned rows keep their reference data and can be rechecked from the inspector.

Same visual style as @design/reference.html. No new colors besides the two chips above.
```

Done when approving and returning update the table without a page reload, and both appear in the actions table.

### M9 · CSV import

Mode: Agent.

```text
Add POST /api/imports/purchases for a CSV with columns date, po_number, supplier, item, qty, unit, unit_price_idr.

- Match items with matcher.py. When nothing matches, create a catalog item and save the raw name as an alias. Create suppliers by name.
- Skip a line when the same po_number and item already exist. Return a summary: inserted, skipped, new items, new suppliers, and errors with line numbers.
- Add an Import page reached from History: file picker, upload button, summary table. Same style as @design/reference.html.
- Put a 20-line sample CSV in backend/sample_data/ and a test that imports it twice; the second import skips every line.
```

Done when importing the sample twice reports 20 inserted, then 20 skipped.

### M10 · Demo hardening

Mode: Agent.

```text
Prepare the app for the demo video and the jury.

- Check that `python -m app.seed --reset` and `--reset --empty-today` both finish in under 10 seconds.
- Header: a small "AI offline" label when /api/health reports Langflow down.
- README: architecture (from the plan's Architecture section), setup for PostgreSQL, Langflow (with the Claude API key under Model Providers) and importing the two flows from langflow/, the demo script, and how to run the tests.
- Run all backend tests and a production build of the frontend, and fix any failures.
```

Done when a fresh clone runs by following the README alone.

### Before M11 · Fix these by hand

1. **Organize fails with "405 Method Not Allowed".** The URL ends in `/api/v1/run/` with no flow ID, so the backend isn't reading your flow IDs. It runs from `backend/`, so it reads `backend/.env`, not the root one. Open `backend/.env` (if it's missing, copy `.env.example` from the project root), fill in `LANGFLOW_API_KEY`, `LANGFLOW_ORGANIZE_FLOW_ID` and `LANGFLOW_WEBCHECK_FLOW_ID`, then restart uvicorn. It reads `.env` only at startup.
2. **Push the code to GitHub.** `git init` only creates a local repository. Create an empty private repository named `procur` on GitHub, without a README. Then run `git remote add origin https://github.com/YOUR-USERNAME/procur.git`, `git branch -M main` and `git push -u origin main`. After each milestone, commit and run `git push`.
3. **Update the design files.** Replace `design/reference.html` with the new version, add `design/quick-check.html`, and export this doc again to `plans/procur-plan.md`.
4. **Capture 3 real quotes** for "solenoid valve 24V DC 1/2 inch" from Tokopedia, Shopee, Lazada or a supplier's site. Write down each seller, listing title, URL and price per unit. M12 uses them in place of the placeholder quotes.
5. **Units.** If the company buys fabric, add `yard` to the unit list in Flow 1's System Message in Langflow. The Langflow section above already includes it.

### M11 · Today screen polish

Mode: Agent.

```text
Polish the Today screen to match the updated @design/reference.html. Change only the frontend, apart from the one API addition in step 3.

1. Remove every hard-coded "Sample data" or "mockup" text from the frontend (search the whole frontend folder). Under the purchase history table, show only "All prices in Rp."
2. Flag box: copy the box under the item name in @design/reference.html exactly: 1px border #F2C7A5, background #FFF4EC, radius 10px, padding 14px 16px, warning icon and the title "Flagged · N reasons to check" in #9A3412, reason text in #7C2D12. Place it directly under the item name. Show it whenever the row has flags, also after Approve or Return. Remove the old plain "Flag reasons" list.
3. Each reason shows the flag message from the API plus one detail line built from the row's real values with lib/format.ts:
   - PRICE_ABOVE_REF: "Rp 1.450.000 quoted vs Rp 1.120.000 reference (+29.5%)"
   - STOCK_COVER_HIGH: "3 drum on hand, about 2 drum used per month"
   - QTY_UNUSUAL: "8 drum requested, usually about 4" (add usual_qty, the median past quantity, to GET /api/request-items/{id})
   - NEW_SUPPLIER: "<supplier> has no purchases in history"
4. "Checked via" column: show counts like the design, "History · 3 buys" or "Web · 3 quotes".
5. Leave the nav as it is. M14 and M15 add the History and Quick check pages.

Do not change the flag messages in the backend; the tests depend on them.
```

Done when, after `python -m app.seed --reset`, the hydraulic oil row shows the flag box with both reasons and their detail lines, and the word "mockup" appears nowhere in the app.

### M12 · Real market quotes and clear errors

Mode: Agent. Fill in the brackets with the quotes you captured; the new median is the middle of the 3 prices.

```text
Make every price on screen traceable to a real source, and make Langflow problems obvious.

Real quotes
- Let cached web quotes exist without a request: make web_quotes.request_item_id nullable and add item_key (the item name normalized with matcher.py). Add an Alembic migration.
- In seed.py, replace the 3 invented quotes for "Solenoid valve 24V DC, 1/2"" with these real listings captured on [CAPTURE DATE], with fetched_at set to that date. Seed them as cache rows on every run, including --empty-today:
  1. seller [SELLER 1], title [TITLE 1], url [URL 1], price_idr [PRICE 1]
  2. seller [SELLER 2], title [TITLE 2], url [URL 2], price_idr [PRICE 2]
  3. seller [SELLER 3], title [TITLE 3], url [URL 3], price_idr [PRICE 3]
- web_check.py: first reuse the newest cached quotes whose item_key matches (exactly, or token_set_ratio 85+ as in matcher.py) and that are at most WEB_QUOTE_MAX_AGE_DAYS old (config, default 60). Call the Web check flow only when none exist, and save its results as cache rows too.
- Inspector: under the web quotes table, show "All prices in Rp. Quotes captured 11 Oct 2026." using the newest fetched_at. Each Offer opens its real URL in a new tab.
- Update the one test that expects the solenoid reference 425000 to [NEW MEDIAN]. Change nothing else in the tests.

Clear errors
- At startup, log a clear error when LANGFLOW_API_KEY, LANGFLOW_ORGANIZE_FLOW_ID or LANGFLOW_WEBCHECK_FLOW_ID is empty.
- In that case, GET /api/health returns "langflow": "not configured" and the header shows "AI not configured".
- When a flow ID is missing, POST /api/requests/parse returns "The Organize flow isn't configured. Set LANGFLOW_ORGANIZE_FLOW_ID in backend/.env." instead of a raw 405.
- Show Langflow 401 and 403 as "Langflow rejected the API key", and timeouts as "Langflow took too long. Try again."
```

Done when the solenoid valve shows your 3 real listings with working links and the capture date, both after the normal seed and after `--empty-today` plus Add requests. Blanking a flow ID in `backend/.env` should show "AI not configured", not a 405.

### M13 · Excel import

Mode: Agent.

```text
Switch the purchase import from CSV to Excel, on the existing Import page and POST /api/imports/purchases.

- Accept .xlsx (first sheet). Keep .csv working as a fallback.
- Match header names case-insensitively, in English or Indonesian:
  date / tanggal · po_number / no_po · supplier / pemasok / vendor · item / barang / nama_barang · qty / jumlah · unit / satuan · unit_price_idr / harga_satuan / harga
- Dates: real Excel date cells, or text such as 12/08/2026 (day first) or 2026-08-12.
- Prices: numbers, or text such as "Rp 1.130.000" or "1.130.000" (dots are thousands separators). Store integer rupiah.
- Skip empty rows. Report errors with their Excel row numbers (the header is row 1).
- Save imported rows with source "excel" (add it to the enum with a migration).
- GET /api/imports/purchases/template returns procur-purchases-template.xlsx: the header row plus 2 example rows.
- Import page: the file picker accepts .xlsx and .csv, with a "Download template" link next to it. The text reads "Upload an Excel file (.xlsx) with columns: date, po_number, supplier, item, qty, unit, unit_price_idr." Keep the summary table (inserted, skipped, new items, new suppliers, errors with row numbers).
- Add openpyxl to requirements.txt, and add backend/sample_data/purchases_sample.xlsx with the same 20 rows as the CSV sample.
- Tests: the .xlsx imports 20 rows, then skips all 20 on a second import; Indonesian headers work; an Excel date cell parses; "Rp 1.130.000" becomes 1130000.
```

Done when the template downloads, the sample `.xlsx` imports 20 rows and then skips all 20, and the tests pass.

### M14 · History page

Mode: Plan first, then Agent in a new conversation.

```text
Build a real History page at /history. Right now the History link only shows the Today screen. Use the same look as @design/reference.html: header, title row, chips, bordered tables, Geist Mono numbers, id-ID formatting.

Two tabs at the top, styled like the filter chips: Purchases and Requests.

Purchases tab (the purchase database)
- Columns: Date, PO no., Item, Supplier, Qty, Price / unit, Total (qty × price). Newest first.
- A search box (item name or alias, supplier, PO number), a supplier dropdown and a date range (default: last 90 days). 50 rows per page with Previous and Next.
- A summary line above the table for the current filter: number of purchases, number of suppliers, total amount in Rp.
- Clicking an item name opens a side panel with that item's last 10 purchases and its 3-buy average.
- API: GET /api/purchases?search=&supplier_id=&date_from=&date_to=&page= (rows, total count, total amount) and GET /api/suppliers.

Requests tab (what was asked for on earlier days)
- Columns: Date, Item, Dept., Qty, Quoted / unit, Reference / unit, Diff., Status. Newest first.
- A date range filter and status chips: All, Flagged, New, Checked, Approved, Returned.
- Clicking a row opens the same inspector as the Today screen. Reuse the component.
- API: GET /api/request-items?date_from=&date_to=&status=&page=

Also
- Nav: Today, History and Import each get their own route, and the active one is highlighted.
- Seed: add 10 earlier request days with 3 to 6 rows each and a mix of statuses, so the Requests tab isn't empty. Keep today's 5 demo rows exactly as they are.
- Tests for the purchases filters, paging and totals.
```

Done when History lists the purchases with working search, filters and paging, the Requests tab shows earlier days, and clicking a row opens the inspector.

### M15 · Quick check page

Mode: Agent (Plan first if you have time).

```text
Add a Quick check page at /quick-check that matches @design/quick-check.html: one input box, a Check button, example chips that fill the box, and one result card per item showing Organize, Check and Mark.

Backend
- POST /api/quick-check with {text}. Run the Organize flow, then run the same matching, pricing and flag rules as checker.py on each item WITHOUT saving anything. Add a dry-run path to checker.py so the logic is shared, not copied. Use web_check.py as it is for items with no history.
- Return per item: name, qty, unit, department, quoted price, supplier, catalog match and category, history count, last 3 purchases (date, supplier, price), reference and its source, diff_pct, flags with messages, status.

Frontend
- A result card per item, like the design: "Bought N times before" (or "New item"), the item name and a status chip, then three rows:
  Organize: category · qty · quoted price · supplier
  Check: the 3-buy average with suppliers and last date, or the web median with its capture date, or "No price reference found"
  Mark: the flag box from @design/reference.html, or "Looks normal" in the Checked chip style
- Buttons: "Add to today's queue" saves the item with POST /api/requests (requested_by "Quick check") and then shows a "View in Today" link. "See purchase history" opens /history filtered to that item.
- Example chips fill the input. Enter submits. While waiting, show "Checking…". Langflow errors appear inline with Retry.
- Nav: Today, Quick check, History, Import.
- Test: a quick check of the oil text returns flagged with PRICE_ABOVE_REF and STOCK_COVER_HIGH, and writes nothing to the database.
```

Done when `oli hidrolik 46 20L 4 drum @1,45jt dari CV Sinar Pelumas` shows Flagged with both reasons, and the Today queue changes only after Add to today's queue.

## Demo, schedule and risks

The demo tells one story in about 3 minutes: a messy morning message becomes a checked queue, and an overpriced item gets caught. If you reach the semifinal (announced 13 Oct), Stage 2 submissions run 14–31 Oct 2026 and ask for an MVP, a business model, a demo video, and documentation with a technical diagram.

Aim to finish M1 to M8 by 25 Oct, and keep the last week for import, polish and the video.

**Demo script**

1. **The problem** (20 s). A manufacturer buys daily from small suppliers with no purchase database and unreliable stock records, so overpaying goes unnoticed.
2. **Organize** (40 s). Start from an empty day (`--empty-today`). Paste the morning's WhatsApp message in Indonesian, click Organize, and show the clean preview.
3. **Check and mark** (60 s). Save. The queue fills and the hydraulic oil is flagged at +29.5%. Open it: 3 past purchases, Rp 1.320.000 over reference, and stock that already covers about 6 weeks.
4. **New item** (30 s). The solenoid valve has no purchase history, so Procur.AI shows market prices: 3 real listings with the date they were captured, median Rp \[NEW MEDIAN\]. Only call it a live web search if the Web check flow works on the day.
5. **Decide** (20 s). Compare suppliers, return the oil request with a note, approve the rest.
6. **Under the hood** (20 s). Show the two Langflow flows on Claude Haiku and the architecture diagram. The model reads text; every number comes from the database.

| Risk | Fallback |
| --- | --- |
| Langflow or the Claude API is slow or down while recording | Seeded web quotes and the "AI offline" label; record from a working run and keep a backup take |
| Web Search gets rate-limited | 60-day quote cache and real captured quotes for the demo item; swap to an API-based search component later |
| Haiku returns broken JSON | Pydantic check, one automatic retry, and the editable preview |
| Wrong catalog match | The matched name shows in the inspector; the threshold lives in config |
| Bob drifts from the design or the numbers | Rules file, `reference.html`, tests on the demo numbers, one milestone per conversation, a commit after each |
| IBM jurors expect an IBM model | Bob and Langflow stay central; the model is one component, so switch to Granite before the final if needed |
| API costs add up during testing | Haiku is the lowest-cost Claude model; set a spend limit in the Console and lean on the quote cache |
| Docker trouble on the laptop | Point `DATABASE_URL` at SQLite for local work |

## Sources

- [IBM SkillsBuild hackathon page](https://www.hacktiv8.com/projects/ibm/hackathon): tools, timeline, Stage 2 submission items
- [Bob docs: Plan and implement complex features](https://bob.ibm.com/docs/ide/tutorials/create-a-plan-and-implement-complex-features): Plan, Agent and Ask modes, `/init`, plan files
- [Bob docs: Standardize Bob's behavior](https://bob.ibm.com/docs/ide/tutorials/standardize-bobs-behavior): `.bob/rules`
- [IBM tutorial: AI documentation with IBM Bob](https://www.ibm.com/think/tutorials/ai-code-documentation-ibm-bob): Enhance Prompt, approvals, to-do lists
- [Claude models overview](https://platform.claude.com/docs/en/models/overview): Haiku 5.5 model ID and what it's built for
- [Langflow: Language Model component](https://docs.langflow.org/components-models): Model Providers, System Message
- [Langflow: Anthropic bundle](https://docs.langflow.org/bundles-anthropic): extra Anthropic fields
- [Langflow: Flow trigger endpoints](https://docs.langflow.org/api-flows-run): run API, `x-api-key`, response shape
- [Langflow: API keys and authentication](https://docs.langflow.org/api-keys-and-authentication)
- [Langflow: Web Search](https://docs.langflow.org/web-search): DuckDuckGo mode and its limits
- [Langflow: IBM bundle](https://docs.langflow.org/bundles-ibm): watsonx.ai component, for switching back
- [IBM foundation models in watsonx.ai](https://www.ibm.com/docs/SSLSRPV_latest/wsj/analyze-data/fm-models-ibm.html): Granite model IDs
- [watsonx Orchestrate: Langflow overview](https://developer.watson-orchestrate.ibm.com/langflow/overview): flows as Orchestrate tools
