# Procur.AI — Repo audit

Audited 23 Oct 2026 by Claude, on the files in `C:\Users\Katon\OneDrive\Documents\Procur`.
Checks run: all backend tests (168 passed), frontend `npm run build` (passed), `oxlint` (0 errors, 4 warnings), secret scan of the git history and Langflow exports, and three reproduction tests against the API with Langflow mocked.

**Bottom line:** the app is in good shape. Tests pass, the build is clean, money is handled as integers, and no secrets are in git. But two things could sink the submission (nothing is committed or pushed, and the solenoid "real quotes" are still fake links), and the web-price path has three confirmed bugs that a juror can hit by typing an unfamiliar item into Quick check.

## Findings

| # | Severity | Where | Problem | Fix |
|---|---|---|---|---|
| C1 | Critical | git | Only one commit exists ("Project setup"). `backend/`, `frontend/`, `README.md`, the plans and `docker-compose.yml` have **never been committed**, and there is no GitHub remote. One bad edit or disk problem loses everything, and there is nothing to submit. | Commit and push now, before any fixes (see "Do this first"). |
| C2 | Critical | `backend/app/seed.py` lines 591–606 | The solenoid valve's 3 web quotes are still the placeholders: URLs `https://tokopedia.com/a`, `https://shopee.co.id/b`, `https://lazada.co.id/c`, shown as "Quotes captured 11 Oct 2026". A juror who clicks an offer gets a dead page, and the data is presented as real when it isn't. | Capture 3 real listings and put them in the seed (M12 prompt), or label them "Example quotes" until you do. |
| H1 | High | `services/web_check.py` line 141, `routers/quick_check.py` | **Quick check returns HTTP 500** for any item with no purchase history and no cached quote. Reproduced: "Kain sutra putih, 10 yard" gives 500 (`InvalidRequestError: Instance RequestItem is not persistent`, because `get_web_quotes` calls `session.refresh()` on the unsaved shim). Also, the live web check can never run from Quick check: `_call_flow` uses `asyncio.run()` inside the async endpoint, which raises "cannot be called from a running event loop". | Make `quick_check` a plain `def` endpoint (like `create_request`), and don't refresh/read relationships on unsaved rows in `get_web_quotes`. |
| H2 | High | `services/pricing.py` `reference_from_web`, `routers/request_items.py` lines 113–120, `checker.py` line 376 | Web-price lookups disagree. `get_web_quotes` finds cached quotes by fuzzy name match within 60 days, but the reference price and the inspector's quotes table use an **exact** name match with no age limit. Reproduced: Add requests with "Solenoid valve 24V DC 1/2 inch" gives reference **null**, status New, no quotes, even though quotes are cached. Worse, Quick check calls `reference_from_web(None, …)`, and `request_item_id == None` becomes `IS NULL`, which matches **every cached quote for every item**. Reproduced: the solenoid variant shows a 425.000 reference with 0 quotes listed. | Have `get_web_quotes` return the quotes it found, and compute the median and the quotes table from exactly that list. Never query by `request_item_id IS NULL`. |
| H3 | High | `README.md` | Out of date and partly wrong. It says to create `.env` in the project root, but the backend reads `backend/.env` (the exact problem you hit). It says "87 tests" (there are 168), mentions a 7-day cache (now 60), and doesn't cover History, Quick check or the Excel import. This is part of the Stage 2 documentation. | Rewrite setup and features (prompt C). |
| M1 | Medium | `routers/quick_check.py` | No Langflow configuration check, so a missing flow ID shows the raw "405 Method Not Allowed" instead of the friendly message `/api/requests/parse` gives. | Reuse the same check. |
| M2 | Medium | `routers/imports.py` lines 284–293 | Any non-`.xlsx` file is treated as CSV and decoded as UTF-8, so dropping a `.xls`, PDF or image gives HTTP 500. No file size limit. | Accept only `.xlsx` and `.csv` (400 otherwise), cap size at about 5 MB, and return a readable error for undecodable files. |
| M3 | Medium | `services/checker.py` lines 41–46 | If a database error happens mid-check, the except block calls `session.flush()` on a failed session, which raises again, so the whole request returns 500 instead of saving the row as "pending". | Run each row's check in a savepoint (`session.begin_nested()`) and roll it back before saving the error. |
| M4 | Medium | `services/matcher.py`, `services/web_check.py` line 68 | `token_set_ratio` scores 100 whenever all words of one name appear in the other. A short request like "valve" or "bearing" matches whichever catalog item contains that word, and gets compared against the wrong price history. | Also require `token_sort_ratio` ≥ 70 (or at least 2 shared words). Re-run the tests; change after the submission if it puts the demo numbers at risk. |
| M5 | Medium | `services/checker.py` | `dry_check_item` is a copy of `_do_check`, not a shared path, so a future change to one can silently diverge from the other. | Extract the shared steps into one function used by both. |
| M6 | Medium | `langflow/Web Check.json` | Web Search "Max Content Length" is 30000 per result × 5 results, roughly 150k characters per call: slow (the backend times out at 60 s) and costly. | Set it to 1500–3000 in Langflow and re-export the flow. |
| M7 | Medium | `backend/requirements.txt` | All versions are `>=`. A fresh install pulls whatever is newest (a Starlette deprecation warning already shows up), so the jury's install may differ from yours. | Pin versions with `pip freeze`. |
| M8 | Medium | project location | The repo lives in OneDrive. Syncing `.venv`, `node_modules` and `.git` causes file locks and can corrupt git. | Move it to e.g. `C:\dev\procur` after pushing to GitHub. |
| L1 | Low | `.gitignore`, `frontend/src/assets/` | `backend/.pytest_cache/` isn't ignored. Unused Vite template files remain (`hero.png`, `react.svg`, `vite.svg`, `App.css`). | Ignore it, delete the leftovers. |
| L2 | Low | `checker.py` line 45, `/api/request-items/{id}` | `check_error` stores full Python tracebacks and the API returns them, exposing internal paths. | Store a short message, log the traceback. |
| L3 | Low | `frontend/package.json` | `@tanstack/react-query` is under devDependencies though the app uses it at runtime. | Move it to dependencies. |
| L4 | Low | frontend | 4 lint warnings (setState inside an effect for the queue selection). | Optional. |
| L5 | Low | `.bob/` | The project rules file `.bob/rules/procur.md` was never created, and the plan file is named `Procur.AI — Build Plan for IBM Bob.md`, not `procur-plan.md` as the prompts reference. | Create both if you keep building with Bob. They also make good "how Bob was used" evidence for the jury. |
| L6 | Info | Import page | The M16 drag-and-drop zone isn't implemented; the page still uses a file picker. | Run M16 if you want it. |
| L7 | Info | Langflow Flow 1 | The System Message unit list has no "yard". | Add it in Langflow if fabric matters. |

## What's solid

- 168 backend tests pass; the frontend builds with no errors.
- No secrets in git history or in the Langflow exports; `.env` files are ignored.
- Money is integer rupiah throughout; "today" uses Asia/Jakarta; flag thresholds live in config.
- Langflow errors (401/403, timeout, missing config) are mapped to readable messages on Add requests.
- Offer links open with `rel="noopener noreferrer"`.

## Do this first (by hand)

1. **Commit and push everything** (C1), in the project root:
   ```
   git add .
   git commit -m "Procur.AI M1-M15"
   git remote add origin https://github.com/YOUR-USERNAME/procur.git
   git branch -M main
   git push -u origin main
   ```
   Run `git status` first and make sure no `.env` file is listed.
2. **Fix the quotes** (C2): capture 3 real listings for "solenoid valve 24V DC 1/2 inch" and run the M12 prompt with them filled in.

## Fix prompts for Bob (new Agent chat each, commit after each)

**Prompt A — web price path (H1, H2, M1, M3)**
```text
Fix these confirmed bugs in the web-price path. See AUDIT.md items H1, H2, M1, M3.
1. POST /api/quick-check returns 500 for an item with no history and no cached quote: get_web_quotes calls session.refresh() on the unsaved RequestItem shim. Make quick_check a plain def endpoint, and make get_web_quotes work without a persisted row (no refresh, no relationship access when the row has no id).
2. get_web_quotes must return the quotes it actually used (fuzzy cache hit within WEB_QUOTE_MAX_AGE_DAYS, or fresh results). Compute the web reference median, web_quote_count and the inspector/quick-check quotes table from that same list. Remove the query on request_item_id IS NULL in pricing.reference_from_web. For saved rows, link the used quotes to the row (or store their ids) so the inspector shows the same quotes later.
3. Quick check must use the same Langflow configuration check and friendly errors as POST /api/requests/parse.
4. In checker.check_item, run each row inside session.begin_nested() and roll back before saving status "pending" with a short check_error; log the full traceback instead of storing it.
Add tests: quick check of an unknown item with the web flow returning [] gives status "new" and no reference (not 500); "Solenoid valve 24V DC 1/2 inch" via quick check and via POST /api/requests both get the cached solenoid quotes and their median; a quick check never uses quotes from a different item. Do not change existing expected numbers.
```

**Prompt B — import hardening (M2)**
```text
Harden POST /api/imports/purchases (AUDIT.md M2): accept only .xlsx and .csv (400 with "Only .xlsx and .csv files are supported" otherwise), reject files over 5 MB with a readable 413, and return a 400 instead of 500 when a CSV can't be decoded. Add tests for each case.
```

**Prompt C — docs and hygiene (H3, M7, L1, L3)**
```text
Update the repo for submission (AUDIT.md H3, M7, L1, L3):
- Rewrite README.md setup: backend/.env (not the root .env) holds DATABASE_URL and the LANGFLOW_ values; Windows PowerShell commands; Docker, Langflow (Claude API key under Model Providers), backend, frontend; the real test count; features (Today, Add requests, Quick check, History, Excel import with template); the demo script; known limits (purchase history is demo data, web check may be rate-limited).
- Pin backend/requirements.txt to the versions currently installed.
- Add backend/.pytest_cache/ to .gitignore; delete unused frontend/src/assets/hero.png, react.svg, vite.svg and App.css if nothing imports them.
- Move @tanstack/react-query to dependencies.
```

Leave M4 (matching) and M5 (shared check logic) until after the submission unless you have spare time; they touch the demo numbers.
