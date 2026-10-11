# AGENTS.md — Agent mode

This file provides guidance to agents when working with code in this repository.

## Before editing

List every file you will touch before making changes. Ask before adding a dependency not in the plan's stack list.

## Critical coding rules

- All Langflow calls go through `backend/app/services/langflow_client.py::run_flow()` — never call httpx or the Langflow API directly from routers or other services.
- `organizer.py` must validate flow output with Pydantic and retry once on failure, appending the validation error to the input — do not silently drop bad responses.
- If Langflow fails during a check, save the row with `status="pending"` and `check_error=<message>` — never raise an exception that aborts the whole request.
- Web quote cache lookup uses the **normalized** item name as the query key (same normalization as `matcher.py`), not the raw name.
- `diff_pct` is `(quoted − reference) / reference × 100`, rounded to 1 decimal. Compute in Python; never in SQL.
- Status rules: any flag → `flagged`; no flag + web/no reference → `new`; no flag + history reference → `checked`. Approve/Return override this.
- Tests never make live Langflow calls — always mock `run_flow`.
- Seed data has a fixed random seed; never change seed values or demo-row numbers to make tests pass.
