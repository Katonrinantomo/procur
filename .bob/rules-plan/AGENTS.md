# AGENTS.md — Plan mode

This file provides guidance to agents when working with code in this repository.

## Architectural constraints

- **Stateless check pipeline.** `checker.py` runs match → price → flags → status → save in sequence. Each step is a pure service function; no step reads back what the previous step wrote mid-run.
- **Reference price sources are mutually exclusive per row.** A row gets either a history reference (≥1 past purchase) or a web reference (no history). It never mixes both. `checked_via` records which path was used.
- **Web quote cache is shared across requests.** Any row requesting the same normalized item name within 7 days reuses existing `web_quotes` rows — plan around this when modeling cache invalidation.
- **`flags` table is write-once per check run.** `checker.py` deletes old flags for the row before inserting new ones on recheck — plan migrations and tests accordingly.
- **No circular calls.** `organizer.py` → `langflow_client.py`. `web_check.py` → `langflow_client.py`. Neither calls the other. `checker.py` calls both services but never calls `langflow_client.py` directly.
- **Seed must be deterministic.** All demo-row numbers (reference prices, diff_pct, flag messages, stock figures) are fixed and tested. Plans that adjust thresholds must re-verify they don't silently change expected test output.
- **PostgreSQL is the default; SQLite is a fallback only.** Plans requiring JSON column features or window functions should note the SQLite limitation.
- **One milestone = one conversation.** Plan files for M3 and M6 are written in Plan mode, then handed off to Agent mode in a new conversation. Plans must be complete enough to implement without re-reading the full build plan.
