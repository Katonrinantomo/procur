# Eval data

Ground truth for `python -m eval.run`.  Nothing here may be guessed: every
price, label and expected match is checked by a person.  A file marked as
example (`"_meta": {"example": true}` in JSON, a `# EXAMPLE` comment line in
CSV) is reported as "EXAMPLE DATA — not a measurement"; remove the marker
when the real set replaces it.

| File | Status | Still to do (plan, section Evaluation) |
| --- | --- | --- |
| `e1/*.txt` + `e1/ground_truth.json` | 3 real messages | Grow to 30 messages: half real and anonymized, half written with typos, slang, "1/2 lusin", "1,45jt", mixed units.  One `.txt` per message, one entry per file in `ground_truth.json`.  Optional `name_accept` per row lists other item names that also count as correct (e.g. an accepted translation). |
| `e2_rows.json` | EXAMPLE, 8 rows | About 100 request rows with about 20 planted anomalies spread over the four flags, each with the reviewer's `expected_flags`.  Rows are checked against the seeded demo catalog and history (`app/seed.py`), so write them against that data. |
| `e3_prices.csv` | EXAMPLE, item names only | 15 items, each with `manual_price_idr` (whole rupiah per unit), `checked_on` (YYYY-MM-DD) and `source_url`, read by hand on a marketplace.  Rows missing any of the three are not scored.  Replaces the rough estimates the old `qa/eval_serper.py` used. |
| `e4_names.csv` | EXAMPLE, 8 names | 40 request names vs the catalog, including short ones like "valve".  `expected_item` is the exact catalog name, blank when the name must not match anything. |
| E5 / E6 bundles | not started | 24 bundles (96 documents) with ground truth per field; land with M21–M22. |

## Schemas

**e1/ground_truth.json**

```json
{"_meta": {"example": false, "note": "..."},
 "messages": {"wa_01.txt": {"items": [
   {"name": "oli", "qty": 4, "unit": "drum", "department": "produksi",
    "quoted_unit_price_idr": 1450000, "supplier": "CV Sinar",
    "name_accept": ["optional other correct names"]}]}}}
```

`null` means the message gives no value and the model must not invent one.

**e2_rows.json**: `{"_meta": {...}, "rows": [{"id", "name", "qty", "unit", "quoted_unit_price_idr", "supplier", "expected_flags": [...], "note"}]}`

**e3_prices.csv**: `item,manual_price_idr,checked_on,source_url,notes`

**e4_names.csv**: `request_name,expected_item,note`
