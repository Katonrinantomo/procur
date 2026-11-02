# Procur.AI — Documentation Audit

> **Date:** 2 November 2026 · **Code state audited:** branch `security`, HEAD `a81bc47` plus the uncommitted changes listed in [§5](#5-what-was-changed-alongside-this-audit).
> **Rule used:** the code and the measured results are the source of truth. A document is *stale* when a claim in it contradicts them. Dated reports (`PROGRESS_REPORT_*`, `AUDIT.md`) are snapshots, so they are marked **historical**, not "wrong".
> **Companion file:** [`ARCHITECTURE.md`](ARCHITECTURE.md) describes the system as it is today.

## Contents

1. [Priority finding: Organize item-name accuracy is 20%](#1-priority-finding-organize-item-name-accuracy-is-20)
2. [Stale-document register](#2-stale-document-register)
3. [Claims to correct before any demo or submission](#3-claims-to-correct-before-any-demo-or-submission)
4. [Open code and test gaps found on the way](#4-open-code-and-test-gaps-found-on-the-way)
5. [What was changed alongside this audit](#5-what-was-changed-alongside-this-audit)

---

## 1. Priority finding: Organize item-name accuracy is 20%

**Owner needed:** whoever maintains `langflow/Organize.json` (Langflow, not backend code).

### What was measured

Suite **E1** (`python -m eval.run --suite E1`), run 2026-10-31T22:00:55+07:00 at commit `2018f1b`. Source: `backend/eval/results.md` and `results.json`. Ground truth: `backend/eval/data/e1/ground_truth.json` (3 WhatsApp-style messages, **5** rows).

| Field | Correct / Rows | Accuracy |
|---|---:|---:|
| **`item` (name)** | **1 / 5** | **20.0 %** |
| `qty` | 5 / 5 | 100.0 % |
| `unit` | 5 / 5 | 100.0 % |
| `price` | 5 / 5 | 100.0 % |
| `supplier` | 5 / 5 | 100.0 % |
| `department` | 5 / 5 | 100.0 % |
| Rows missed / invented | 0 / 0 | n/a |

E1b (flag propagation): 1 of 5 rows changed its flags because of the misreading (`lakban bening 2 inch` gained `QTY_UNUSUAL`).

### Which rows failed

| Message text | Ground truth `item` | What the model returned | Result |
|---|---|---|---|
| `beli oli 4 drum ...` | `oli` | `Lubricating oil` | wrong |
| `bearing SKF 6205 10 pcs ...` | `bearing SKF 6205` | `Bearing SKF 6205` | **correct** (the only one) |
| `lakban bening 2 inch 24 roll ...` | `lakban bening 2 inch` | `Clear packing tape 2 inch` | wrong (+ false `QTY_UNUSUAL`) |
| `sarung tangan katun 5 lusin ...` | `sarung tangan katun` | `Cotton gloves` | wrong |
| `masker kain 200 pcs ...` | `masker kain` | `Cloth face mask` | wrong |

All four failures are the same defect: **the model translated the Indonesian item name into English.** Every number, unit, supplier and department was read correctly.

### Why this needs a fix (and what the fix is *not*)

1. **The prompt already forbids it.** The system message in `Organize.json` says *"KEEP THE ITEM NAME IN THE ORIGINAL LANGUAGE (Indonesian) ... Do NOT translate to English."* The model ignored the rule, so editing that sentence alone is unlikely to be enough. The likely levers, in order:
   - **Model.** `Organize.json` was exported with `OpenAI Compatible: langflow` (a local gateway), not the `claude-haiku-5-5` that `README.md` and `AGENTS.md` describe. Select the intended model on the node, set temperature to 0 (it is 0.1), re-export.
   - **Prompt examples.** The only example in the prompt has an English-looking, expanded output (`Oli hidrolik ISO VG 46, 20L`). Add two or three few-shot examples whose names stay terse and Indonesian (`lakban bening 2 inch` stays `lakban bening 2 inch`).
   - **Validation.** The backend cannot detect translation, because `LineItemDraft.name` is a free string. Do not rely on a post-check.
2. **The project is internally inconsistent about language.** The seeded catalog (`backend/app/seed.py`, `CATALOG`) uses **English** primary names (`Hydraulic oil ISO VG 46, 20L`, `Bearing 6205 ZZ`) with some Indonesian aliases, the Organize prompt demands **Indonesian**, and the README demo messages are **English**. The matcher compares normalized strings (`rapidfuzz`, threshold 85), so a translated name can match the wrong item or none. **Decide one convention** and make the catalog aliases, prompt and ground truth agree. Until then, E1 may be penalising a defensible output, and E1b shows the translation can already change a flag.
3. **How the metric works.** A name counts as correct at 0.8 string similarity to the ground-truth name *or any `name_accept` variant*, and containment counts as a match (`"oli"` is contained in `"oli hidrolik"`). So an expanded Indonesian name passes; an English one fails. If English names are acceptable, add them as `name_accept` entries instead of fixing the flow, but record that decision.

### Definition of done

| Step | Command or file | Pass criterion |
|---|---|---|
| Fix model and prompt | `langflow/Organize.json` (re-export) | Node shows the intended provider/model, temperature 0 |
| Secrets check | `python scripts\check_langflow_secrets.py` | exit 0 |
| Grow the data | `backend/eval/data/e1/` (target 30 messages in `eval/data/README.md`) | at least 30 messages, half real and anonymized |
| Re-measure | `python -m eval.run --suite E1` from `backend\` | `item` accuracy is at least 95% (proposed target, not an existing project threshold); other fields stay at least 95% |
| Record it | commit the new `eval/results.md` | flow sha256 in the file matches the exported flow |

### Caveats on the 20%

- **n = 5 rows.** Treat it as a strong signal, not a precise rate; the other five fields at 100% have the same small base.
- **Not re-run here.** Langflow was not available in this environment, so the number is the 2026-10-31 recorded value.
- **An earlier "100%" exists.** Commit `6be9dc2` (`backend/qa/eval_llm.py`, since deleted) reported 100% under *semantic* matching. That script is gone and its method differs from the current string-based one. Do not quote both figures side by side as if they measured the same thing.

---

## 2. Stale-document register

Ordered by the harm a wrong claim can do (public-facing first). "Verified against" names the file that disproves the claim.

| # | Document | Verdict | Stale or incorrect claims | Verified against | Action |
|---|---|---|---|---|---|
| 1 | `DEMO_VIDEO_PLAN.md` | ~~Incorrect~~ **Rewritten 2 Nov** | Previously: "100%" extraction claim citing deleted files, wrong Quick Check / Import roles, `NEW_SUPPLIER` "+25", and an owner-approve step that skipped the mandatory reason and outcome tag. All corrected; the QA scene now quotes the measured 20% item-name result and says MAPE is not yet measured. Numbers in the script (+29.5%, risk 70, flags, Rp 1.120.000, solenoid median Rp 425.000) were checked by running the check engine on a seeded database. The UI flow was not recorded or clicked through here. | `routers/quick_check.py`, `routers/imports.py`, `flags.py`, `services/decisions.py`, `eval/results.md` | Rehearse once; replace the Scene 6 numbers after the Organize fix (§1) |
| 2 | `SECURITY_PROGRESS.md` | **Stale (most of the open list is closed)** | Lists as open or not done: **SEC-01 no authentication** (JWT + 3 roles shipped in M16), **Fase 2 login / maker-checker / audit log** (done: `auth.py`, `decisions.py`, `audit_log`), **SEC-13 Content-Security-Policy** (set in `main.py`), **H1/H2 Quick Check 500 and cache mismatch** (fixed), **SEC-14/18/19** (strict matcher, `LIKE` escape in `purchases.py`, 3-attempt Langflow retry in `langflow_client.py` are all in the code). Test counts (232) and flow list (no `Maker.json`) are outdated. | `routers/auth.py`, `main.py`, `matcher.py`, `purchases.py`, `langflow_client.py` | Convert the "Belum dikerjakan" table into a dated history and link to [`ARCHITECTURE.md` §7](ARCHITECTURE.md#7-security--compliance-sector-1). Keep the genuinely open items: Fase 3 scanners/STRIDE, DB credentials, TLS |
| 3 | `KNOWN_ISSUES.md` | **Stale and over-confident** | §3.2 says `.xlsx` magic bytes are "not fully implemented" (they are, for both imports and quotations, with tests). §3.3 says CSP is open (it is set). §3.4 says the matcher is loose (strict `token_sort_ratio ≥ 70` is in; the E4 example run still shows `bearing` falsely matching, so it is *partially* open). Header says "core features 100% working" and the notes say all numbers are "100% accurate": numbers are computed in Python, but the **inputs the model reads are not 100% accurate** (§1). Says the backend forces the marketplace restriction; it is now done in the Langflow `Serper Multi Search` component. | `routers/imports.py`, `quotations.py`, `main.py`, `matcher.py`, `langflow/Maker.json` | Rewrite status; add §1 as a **High** issue |
| 4 | `TECHNICAL_ROADMAP.md` | **Stale (every row says "Todo")** | JWT login, RBAC, audit log, Python-side price status and vendor score, `mask_pii`, risk score, Review page, approve/return notes are implemented. The ground-truth dataset, accuracy script (E1), error-propagation test (E1b) and MAPE (E3) exist, but at example scale or without data. "72 tests" is obsolete (README states 506). **One roadmap item is only partly met:** `mask_pii` was specified for text "sent to the LLM *or* shown in the frontend"; it is applied only to the supplier name in the request-item detail response, never before an LLM call. | `security.py`, `routers/request_items.py`, `eval/` | Mark done / partial / open per row; keep PII-before-LLM as open |
| 5 | `AGENTS.md` (root) and `.bob/rules-*/AGENTS.md` | **Stale in specific rules** | "Web quotes are cached **7 days**": config is **60** (`WEB_QUOTE_MAX_AGE_DAYS`). `rules-plan`: "within 7 days". `rules-ask`: flows are `langflow/organize.json` and `web_check.json` (files are `Organize.json`, `Maker.json`, `Web Check.json`), "Web Search component uses DuckDuckGo" (pricing now uses Serper through `Maker.json`; `Web Check.json` is legacy), "Flow 2" for web check (now the Maker flow). `AGENTS.md` says all flows call Claude Haiku (`Organize.json` exports an OpenAI-compatible gateway). `rules-agent`: "tests never make live Langflow calls" (`test_live_flows.py` does, but is skipped unless `-m live`). | `config.py`, `web_check.py`, `eval/results.md` | Align or change the setting. These files steer coding agents, so stale rules produce wrong code |
| 6 | `PROGRESS_REPORT_20261030.md` | **Historical; two statements superseded** | Says `web_check._flow_input` injects `site:` operators; that logic now lives in the Maker flow's Serper component and `_flow_input` only formats `MODE: BON`. Risk-score weights omit `QTY_UNUSUAL` (+15). "232 tests passed" is now 506 collected. | `services/web_check.py`, `flags.py`, README | Add a one-line "superseded by" note; do not rewrite history |
| 7 | `PROGRESS_REPORT_20261024.md` | **Historical** | Describes the Web Check + 9router setup and the bugs found that day; all listed bugs are fixed. | `KNOWN_ISSUES.md` | Leave; add a "superseded" header |
| 8 | `AUDIT.md` | **Historical (23 Oct, 168 tests)** | Almost every finding is resolved: C2, H1, H2, M1, M2, M3, M4, L2. Open or partly open: M5 (`dry_check_item` still duplicates `_do_check`), M6 (flow `Max Content Length`, moot now that pricing uses `Maker.json`), M7 (requirements are now pinned). H3 (README) is addressed by this change. Refers to `C:\Users\Katon\OneDrive\...` paths. | `checker.py`, `requirements.txt` | Move to `docs/archive/` or add a resolved/open column |
| 9 | `langflow/maker_agent_prompts.md` | **Updated 2 Nov; one item still open** | The `extract_json` edit is done and a manual how-to was added. Still open: set temperature to 0 on both Language Model nodes (now 0.1). | `langflow/Maker.json` | Do the temperature edit with the §1 model fix, re-export |
| 10 | `plans/*.md`, `design/*.html` | **Specifications, not status** | Build plans describe the intended design (some still say DuckDuckGo, 7-day cache, Claude for all flows). Not wrong as history. | n/a | Add a "design intent, see ARCHITECTURE.md for current behaviour" line |
| 11 | `README.md` | **Updated 2 Nov (twice)** | Setup, flows, roles, features, counts; step 3 now says the `extract_json` output is in the export. | n/a | Done |
| 12 | `ARCHITECTURE.md` | **Current** | Counts and gap list refreshed on 2 Nov. | n/a | Keep in sync with `README.md` |

---

## 3. Claims to correct before any demo or submission

A short list for the team; each is a statement a juror could check.

| Claim as written | Where | Reality | Say instead |
|---|---|---|---|
| "LLM extraction accuracy reaches 100%" | old `DEMO_VIDEO_PLAN.md` (removed 2 Nov), commit `6be9dc2` message | Item-name accuracy is 20% on the current harness (5 rows); other fields 100% | Quote the per-field table with its sample size, or fix the flow first (§1) |
| "Web Check coverage is transparent" / any MAPE figure | old demo narration (removed 2 Nov) | E3 is **skipped**: no hand-checked prices exist, so **no MAPE has been measured** | "We built the MAPE harness; the price set is being collected" |
| "All numbers are 100% accurate because Python computes them" | `KNOWN_ISSUES.md` | Python arithmetic is exact, but it computes on what the model extracted (E1b: one flag changed from a misread name) and on web listings that passed the evidence guards | "Numbers are computed in Python from extracted inputs; extraction is measured separately" |
| "Quick Check and Import are available to all roles" | old `DEMO_VIDEO_PLAN.md` | `purchasing` only | Use the matrix in `ARCHITECTURE.md` §4 |
| "Anthropic Claude Haiku runs every flow" | `AGENTS.md`, older README | `Maker.json`: Claude Haiku. `Organize.json` / `Web Check.json`: OpenAI-compatible gateway | State the model per flow |

---

## 4. Open code and test gaps found on the way

None of these were changed except where §5 says so. They are listed so they do not get lost.

| # | Gap | Evidence | Impact | Suggested fix |
|---|---|---|---|---|
| 1 | ~~`langflow/Maker.json` lacked the `extract_json` output~~ **Fixed in the committed file, 2 Nov.** Added `ChatOutput-2FAR2` (display name `extract_json`) wired from Language Model #1. | The change is 339 added lines, 0 removed. Structure checks and `test_langflow_exports.py` pass; a simulated Langflow response parses through `services/maker.py` with 3 outputs and fails with `Flow output 'extract_json' not found` with 2. **Not opened in a live Langflow**, so import acceptance is unverified | A Langflow flow imported *before* this change still lacks the output until re-imported | Re-import `Maker.json`, update `LANGFLOW_MAKER_FLOW_ID`, run `python -m app.flowcheck` |
| 2 | ~~`pricing.reference_from_history` / `reference_from_web` untested~~ **Fixed 2 Nov.** `TestReferenceFromHistory` (12 cases: empty, unknown id, 1/2/3 purchases, only the 3 newest used, recency by date not insert order, window from settings, other items ignored, rounding, seeded oil = Rp 1.120.000). `reference_from_web` had no caller and was **deleted**, so it needs no test. | Five deliberately broken variants of `reference_from_history` (ascending order, hard-coded limit, no item filter, truncate instead of round, 0 instead of None) each failed at least one test | none | Note: `round()` is banker's rounding, so an exact `.5` mean rounds to the even rupiah. Only non-tie cases are pinned |
| 3 | `Organize.json` and `Web Check.json` export an OpenAI-compatible model; `Maker.json` exports Anthropic. Temperature is 0.1 everywhere. | `eval/results.md` flow stamp; node templates | Results are not reproducible by someone following the README | Standardize (§1) and re-export |
| 4 | Eval data is mostly placeholder: E2 and E4 are example data, E3 has no prices, E1 has 5 rows. | `eval/data/README.md`, `eval/results.md` | No headline accuracy number is currently defensible | Fill the sets as listed in `eval/data/README.md` |
| 5 | `audit_log` immutability is ORM-level only; JWT lives in `localStorage` and cannot be revoked early; `mask_pii` covers one field and not LLM input. | `models.py`, `frontend/src/lib/api.ts`, `security.py` | Acceptable for a demo; not for production | See `ARCHITECTURE.md` §9 |

---

## 5. What was changed alongside this audit

| Change | File | Verification |
|---|---|---|
| Added `TestCalculateRiskScore` (30 test cases: every weight, summation, unknown code, `int()` truncation, cap at 20, absolute value for negative diff, clamp at 100, the four worked examples from `ARCHITECTURE.md` §5.4, input not mutated) | `backend/tests/test_flags.py` | `pytest tests/test_flags.py` passes. Four deliberately broken copies of `flags.py` (no `abs`, `round` instead of `int`, no clamp, wrong weight) each made at least one test fail |
| Updated setup, flow import (Maker, Serper key, `extract_json` output), roles, seeded users, features, known limits; fixed the broken `release_check.ps1` path; corrected test and coverage counts | `README.md` | Full suite after all changes: **505 passed, 1 skipped** (the live-Langflow test). `pytest --collect-only` = **506**. Coverage over `app/services` = **95.6%**, which `check_claims.py` rounds to 96, so the README states 96%. `python scripts\check_claims.py` passes |
| Refreshed counts and removed the "no test" note | `ARCHITECTURE.md` | Same runs |
| Added `TestReferenceFromHistory` (12 cases); deleted dead `pricing.reference_from_web` and its unused `WebQuote` import | `backend/tests/test_pricing.py`, `backend/app/services/pricing.py` | Mutation checks as in §4 item 2; no other file referenced the function |
| Added the `extract_json` Chat Output to the export, plus `TestMakerExport` (6 structure tests) | `langflow/Maker.json`, `backend/tests/test_langflow_exports.py` | The new tests fail on the pre-change export (3 of 6) and pass on the new one; `check_langflow_secrets.py` clean |
| Rewrote the demo script and RBAC table; added a "claims you may and may not say" table and a fallback plan | `DEMO_VIDEO_PLAN.md` | Numbers re-checked on a seeded DB (see §2 row 1) |
| Added a manual how-to for the `extract_json` output; marked the done item | `langflow/maker_agent_prompts.md` | n/a |
| Created this register | `DOCS_AUDIT.md` | Claims cross-checked against the files named in the tables |

**Not done (needs a decision or Langflow):** the Organize model and prompt fix (§1), setting temperature 0 in the flows, re-running the eval suites (the `Maker.json` sha256 in `eval/results.md` no longer matches the edited file until E1 or E3 is re-run), opening the edited `Maker.json` in a live Langflow, and fixing the stale documents in §2 rows 2–8 and 10.

**How the verification ran:** a git-ignored `backend/.venv` was created from `backend/requirements.txt` (Python 3.14.4). It can be deleted without effect on the repository. The run also wrote git-ignored coverage files (`backend/.coverage`, `backend/coverage.json`), which were removed afterwards. `git status` lists only intended source and documentation changes (see the table above).
