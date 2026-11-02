# Technical decisions

## The model handles language; the backend handles numbers

**Decision:** Claude (via Langflow) only turns text into structured fields and reports listings it saw. Reference prices, `diff_pct`, bands, recommendations, flags, risk scores and vendor scores are computed in `pricing.py` / `flags.py`.

**Why:** an LLM that computes "+29.5%" can be wrong in ways nobody notices, and a procurement owner must be able to recompute every number shown. Python arithmetic on integers is deterministic and unit-tested; the model is only trusted for the part it is good at (reading `"1,45jt"`, `"1/2 lusin"`, mixed Indonesian/English).

**Trade-off:** more glue code (contracts, join by `line_no`, evidence guards) instead of one "analyze this quote" prompt.

## Integer rupiah everywhere

Money is `BIGINT` / `int`, including in flow contracts (`unit_price: int | None`; a fractional value fails validation). Rupiah has no minor unit in practice, so integers lose nothing and avoid float rounding in sums and comparisons. Averages and medians are rounded to whole rupiah at the point they are produced; `per_unit_price` uses `Fraction` to round half up exactly. `diff_pct` is the only non-integer and is stored as `NUMERIC(8,1)`.

## Reference price: mean of last 3 purchases, median of web quotes

- **History → mean of the last `HISTORY_WINDOW` (3).** Recent buys reflect current supplier pricing; three keeps one outlier from dominating without needing much history. The flag message says "3-buy average" so the user knows what was compared.
- **Web → median of ≥ `WEB_MIN_QUOTES` (3) kept listings.** Marketplace listings include bundles, wrong variants and bait prices; the median ignores a single extreme. With fewer than 3 listings the backend returns no reference rather than a weak one.
- **History wins over web** whenever the item matches the catalog and has purchases.

## Evidence guards instead of trusting model-reported listings

The maker_agent's second model returns listings with URL and price. `evidence.py` keeps a listing only if that URL is in the raw Serper results for the same line, is a product page, and its price appears in that result's text. This catches invented URLs and misread prices — the failure mode that produced fake quote links earlier (see `KNOWN_ISSUES.md` 1.1). Dropped listings are stored with a reason code and shown in the UI so a user can see why a price was ignored.

**Alternative discarded:** the legacy Web Check flow (Google Serper API + one model returning `webcheck_json` offers directly, with no check against the raw results). It is kept only so `flowcheck` can still exercise it.

## Two-step fuzzy matching

`match_item` requires `token_set_ratio ≥ 85` **and** `token_sort_ratio ≥ 70`. `token_set_ratio` alone scores a short name like "valve" as a perfect subset match of any valve item; the second score rejects matches where most tokens are missing. Unit normalization (`20 liter` / `20 ltr` / `20 L` → `20l`) runs first so units don't count against the score. The wrong-match rate is tracked by eval suite E4.

## Thresholds in config, flag functions pure

Every threshold (`FLAG_PRICE_ABOVE_REF_PCT=15`, `FLAG_STOCK_COVER_MONTHS=1`, `FLAG_QTY_UNUSUAL_MULTIPLIER=2`, bands, `OVERRIDE_RISK_SCORE=50`, …) lives in `config.py`, and flag functions receive the threshold as an argument. Tuning for a different plant is an `.env` change, and tests can exercise edges without monkeypatching globals.

## Web quote cache

Quotes are cached in `web_quotes` by normalized name (`item_key`) for `WEB_QUOTE_MAX_AGE_DAYS` (60), with a fuzzy key match so "Solenoid valve 24V" reuses quotes for "solenoid valve 24 V DC". Each maker_agent call costs two model calls plus a search; repeated requests for the same consumable are common. Rows without a URL are not cache hits, since they cannot be shown as evidence. On a flow failure, stale quotes are returned together with the error so the row is `pending` but still has context.

## Failures become `pending`, not errors

A Langflow timeout or contract failure on one row saves that row as `pending` with `check_error`; the rest of the request is still checked (savepoint per row). For a procurement queue, a partially checked request that can be rechecked is more useful than a failed save. Only `/api/requests/parse` and `/api/quick-check` return `502`, because without the Organize output there is nothing to save.

## One Langflow gateway, named outputs, repair retry

`langflow_client.run_flow` is the only caller of Langflow: one place for timeouts (60 s), retries (3, no retry on auth errors), API key and fresh `session_id` per call (no chat memory leaks between documents). Outputs are keyed by component name so one flow run can return `extract_json`, `maker_json` and `serper_raw` together — re-running for a repair re-runs the whole flow so all three outputs stay consistent. Invalid JSON gets one retry with the validation error appended; a second failure raises `FlowContractError`.

## Decisions are separated by role and logged append-only

- `purchasing` enters requests; only `owner` approves or returns, and never a request they created (four-eyes rule).
- Approving a flagged or high-risk row requires a reason and an outcome tag (`false_alarm` / `risk_accepted`) so the log can later measure false-positive rates per flag.
- The `audit_log` row stores a snapshot of what the decider saw, because flags and reference prices change on recheck. Updates and deletes are blocked by an ORM flush hook.

## Self-contained auth

JWT (HS256) and PBKDF2 are implemented with the standard library (`security.py`) rather than python-jose/passlib, keeping the dependency list short for a demo. Tokens last 1 hour and are stored in `localStorage`; on any 401 the SPA clears them and returns to login. A real deployment would want httpOnly cookies and refresh tokens.

## PostgreSQL in Docker, SQLite for tests

Production-shaped storage (`BIGINT`, `NUMERIC`, timezone-aware timestamps) runs in PostgreSQL 16; the test suite uses a file-based SQLite database seeded once per session, so `pytest` needs no Docker or Langflow. Code avoids PostgreSQL-only SQL to keep both working.

## "Today" in Asia/Jakarta

The users are in Indonesia. A request entered at 06:30 WIB is 23:30 UTC the previous day, so day boundaries for the queue, history and decision filters are computed in UTC+7 and converted for the query.

## Hash routing, no router library

The SPA switches pages on `window.location.hash`. With seven pages and no nested routes, a router dependency adds nothing; the backend never needs to serve deep links.
