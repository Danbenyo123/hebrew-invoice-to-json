# Open issues

Last updated 2026-10-22.

## Evaluation

- [ ] Run the vision baseline on the preprocessed image to test whether preprocessing destroys information (see README → Results → How to fix it).
- [ ] Add a hybrid pipeline: image and OCR text in one call.
- [ ] Route by input quality: photos and low-resolution images go to the vision path.
- [ ] Switch the API to whichever pipeline the eval ranks first.
- [ ] Add more pipelines, for example Gemini vision or OCR with a smaller Claude model (add a function to `eval/pipelines.py`).
- [ ] Report cost in money, not just tokens.

## Expected results data

- [ ] `05-no-id.png` is really an AVIF file; rename it to `.avif` or convert it.

## OCR known limitations

- [ ] A `₪` glued to the digits (`₪5,500.00`) is read as `0` by the Hebrew model, and the English pass isn't confident enough to replace it.
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
