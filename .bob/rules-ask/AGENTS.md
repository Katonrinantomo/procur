# AGENTS.md — Ask mode

This file provides guidance to agents when working with code in this repository.

## Key context for answering questions

- The canonical design is `design/reference.html` — the inline styles there are the source of truth for colors, spacing, and radii (the plan's "UI spec" section mirrors them in a table).
- The canonical numbers are the "Today's demo rows" table in `plans/Procur.AI — Build Plan for IBM Bob.md` — those exact values (reference prices, diff_pct, flag messages) are what the tests check.
- Langflow flows are exported and committed to `langflow/organize.json` and `langflow/web_check.json` — consult those for the actual flow topology.
- The Claude API key is stored inside Langflow (Model Providers → Anthropic), not in `.env`. Only the Langflow API key and flow IDs are in `.env`.
- The Web Search component in Flow 2 uses DuckDuckGo and can be rate-limited — this is why web quotes are cached for 7 days in `web_quotes` table and demo quotes are seeded.
- "Web check" means fetching market prices via Flow 2; "history check" means computing a reference from the `purchases` table. These are distinct paths in `checker.py`.
