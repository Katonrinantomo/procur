# Procur.AI eval results

- Run at: 2026-10-31T22:00:55+07:00 (Asia/Jakarta)
- Git commit: `2018f1b`
- Exported flows (`langflow/*.json`): model ID and sha256
  - `Maker.json`: `Anthropic: claude-haiku-5-5` — sha256 `242ce2da2c9d50a6b21bfc8ae2f47369832f4eda8dce7b8a088b4aab3c0e439a`
  - `Organize.json`: `OpenAI Compatible: langflow` — sha256 `d656c49495a26846cc8d0ccc0e07acf55cae577186dd245327d7615d943ee43d`
  - `Web Check.json`: `OpenAI Compatible: langflow` — sha256 `fb673e591597c7c1299a1152e0709fe29fcce34a2e5207a94f2cdd9b2b40c040`

Command: `python -m eval.run --suite E1,E2,E3,E4` (from `backend/`)

## E1

Status: **ok**
Data: `eval/data/e1/ground_truth.json`

| Metric | Value |
| --- | --- |
| Messages scored | 3/3 |
| Ground-truth rows | 5 |
| Price exact match (rows with a price) | 100.0% (3/3) |
| Rows missed | 0 |
| Rows invented | 0 |

**E1 accuracy per field (share of ground-truth rows)**

| Field | Correct | Rows | Accuracy % |
| --- | --- | --- | --- |
| item | 1 | 5 | 20.0 |
| qty | 5 | 5 | 100.0 |
| unit | 5 | 5 | 100.0 |
| price | 5 | 5 | 100.0 |
| supplier | 5 | 5 | 100.0 |
| department | 5 | 5 | 100.0 |

**E1b flags that change because of misreading**

| Metric | Value |
| --- | --- |
| Flags on ground-truth rows | 4 |
| Flags gained (parsed only) | 1 |
| Flags lost (ground truth only) | 0 |
| Rows whose flags changed | 1/5 |

## E2

Status: **ok**
Data: **eval/data/e2_rows.json (EXAMPLE DATA — not a measurement)**

| Metric | Value |
| --- | --- |
| Rows | 8 |
| Rows with a planted anomaly | 5 |
| Rows where fired flags differ from expected | 0 |

**E2 per flag**

| Flag | Expected | Detected | Detection % | False positives | False-positive % |
| --- | --- | --- | --- | --- | --- |
| PRICE_ABOVE_REF | 2 | 2 | 100.0 | 0 | 0.0 |
| STOCK_COVER_HIGH | 1 | 1 | 100.0 | 0 | 0.0 |
| QTY_UNUSUAL | 1 | 1 | 100.0 | 0 | 0.0 |
| NEW_SUPPLIER | 2 | 2 | 100.0 | 0 | 0.0 |

## E3

Status: **skipped** — no hand-checked prices yet in eval/data/e3_prices.csv (10 item(s) listed, 0 with manual price, date and URL)

## E4

Status: **ok**
Data: **eval/data/e4_names.csv (EXAMPLE DATA — not a measurement)**

| Metric | Value |
| --- | --- |
| Names | 8 |
| Wrong-match rate % | 12.5 |
| Wrong item | 0 |
| Matched when it should not | 1 |
| Missed match % (falls back to web) | 0.0 |

**E4 rows that did not match as expected**

| Request name | Expected | Got | Kind |
| --- | --- | --- | --- |
| bearing | (no match) | Bearing 6205 ZZ | false_match |
