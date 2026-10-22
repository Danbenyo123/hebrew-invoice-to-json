# Open issues

Last updated 2026-10-22.

## Eval harness (blocks measuring anything)

- [ ] `eval/eval.py:12-25` — `fields_weights` is half-written, so the file is a `SyntaxError`. This also breaks `tests/eval_compare.py`, which imports `compare`.
- [ ] `eval/eval.py:64` — `json.load` is called on the same file handle inside the loop. The second image hits EOF and raises `JSONDecodeError`. Load the file once, before the loop.
- [ ] `eval/eval.py:66` — images without an expected entry raise `KeyError`. Only 5 of the 12 images are labeled (`06`–`12` are missing).
- [ ] `eval/eval.py:62` — when extraction fails, `.invoice` is `None` and `.model_dump()` crashes (this always happens for `08-empty.jpg`). Expected-failure cases need handling, e.g. by recording `success`/`errors`.
- [ ] `eval/eval.py:9` — `iterdir()` order isn't fixed, so sort it.
- [ ] `compare()` treats `products` all-or-nothing, so one wrong line item marks the whole list wrong. Consider comparing each item and the nested `supplier`/`customer` fields separately.
- [ ] `tests/eval_compare.py` is a script, not a test, and calls the LLM when the module is imported.

## Expected results data

- [ ] `expected_results.json` → `02.png`: `"id": 70581` is an int but the schema expects a `str`, so `Invoice.model_validate` fails.
- [ ] `02.png`: supplier name is labeled `כותרת משנה לדוגמה` (the page's subtitle). The business name is `אינטרסרף - חברה לבדיקה`, which the pipeline now extracts.
- [ ] Add labels for `06`–`12`.
- [ ] `05-no-id.png` is really an AVIF file; rename it to `.avif` or convert it.
- [ ] `03.jpg` / `invoices/green_invoice.jpg` contain real personal data (ID, phone, address). Decide whether to redact them or keep them out of the public repo.

## OCR known limitations

- [ ] A `₪` glued to the digits (`₪5,500.00`, see `03.jpg`) is read as `0` by the Hebrew model, and the English pass isn't confident enough to replace it. The totals on 03 come out as `0`.
- [ ] Bold white digits inside a colored header still OCR badly after inversion (`02.png` supplier phone comes out as `4`).
- [ ] Low-resolution images (~370px wide: `06.png`, `09.png`) produce wrong amounts from both OCR passes. Consider rejecting or warning on very small images.
- [ ] `10.jpg`: one line item's total comes out as `0`.

## Schema (`image_to_json/schemas.py`)

- [ ] `parse_prices` doesn't handle a trailing minus (`"0.43-"`) or spaces inside numbers (`"1 132.00"`). These values now fail validation and trigger a retry, but they should parse.
- [ ] `Product.quantity` is a plain `Decimal`, so it doesn't get the `CleanPrice` cleanup.

## Cleanup

- [ ] `ExtractionResult.ok` duplicates `success` and is never used; remove one of them.
- [ ] Unused `PROJECT_ROOT`/`Path` in `ocr.py` and `pre_process.py`.
- [ ] `main.py` uses `print` for timing; switch to `logging`.
- [ ] No upload size limit on `POST /api`.
- [ ] Duplicate images exist across `invoices/` and `eval/dataset/` (for example, `invoice-9.jpg` and `01.jpg` are the same file).
