# Evaluation report

Run `20261022-125027.json` · model `claude-opus-5` · 3 run(s) per invoice · 11 invoices

**How to read it**
- **score**: weighted share of correct fields per invoice, averaged over invoices and runs. Weights: invoice number, total and line items ×3; date, VAT, before-VAT and supplier ID ×2; other fields ×1. Fields empty in both the label and the extraction aren't counted.
- **missed / wrong / hallucinated**: a labeled value left empty / a different value / a value invented where the label is empty.
- **honest failures**: on invoices that should fail validation (blank template, missing total), how often the pipeline failed instead of inventing data.
- **consistency**: for repeated runs on the same invoice, the share of runs agreeing on each field.
- **draft labels** were written from the images and are not yet human-verified, so they are reported separately.

## Summary

| pipeline | score (verified) | score (draft labels) | correct | missed | wrong | hallucinated | honest failures | unexpected failures | consistency | avg time | avg tokens in / out |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ocr-claude | 88% | 64% | 200 (78%) | 24 (9%) | 22 (9%) | 9 (4%) | 6/6 | 2 | 93% | 10.8s | 4,960 / 598 |
| claude-vision | 93% | 88% | 220 (87%) | 3 (1%) | 23 (9%) | 6 (2%) | 6/6 | 0 | 95% | 7.4s | 4,135 / 465 |

## Accuracy per field (verified labels)

| field | ocr-claude | claude-vision |
|---|---|---|
| id | 100% | 100% |
| products.discount | 0% | 100% |
| products.id | 80% | 100% |
| products.name | 46% | 39% |
| products.price_for_unit | 100% | 100% |
| products.product_total_price | 88% | 100% |
| products.quantity | 100% | 100% |
| total_price | 100% | 100% |
| date | 100% | 100% |
| price_before_VAT | 100% | 100% |
| vat_amount | 67% | 100% |
| customer.address | 100% | 100% |
| customer.id | 43% | 50% |
| customer.name | 100% | 100% |
| customer.phone | 100% | 100% |
| discount | 0% | 0% |
| hour | 100% | 100% |
| price_before_rounding | 100% | 67% |
| rounding | 100% | 100% |
| supplier.address | 100% | 44% |
| supplier.id | 100% | 100% |
| supplier.name | 67% | 100% |
| supplier.phone | 100% | 100% |
| type_of_doc | 89% | 100% |

## Per image (score · consistency · failed validation)

| image | label | ocr-claude | claude-vision |
|---|---|---|---|
| 01.jpg | verified | 96% · 100% · 0/3 failed | 94% · 98% · 0/3 failed |
| 02.png | draft | 83% · 100% · 0/3 failed | 93% · 100% · 0/3 failed |
| 04.jpg | verified | 94% · 98% · 0/3 failed | 93% · 94% · 0/3 failed |
| 05-no-id.png | verified | 74% · 89% · 0/3 failed | 91% · 85% · 0/3 failed |
| 06.png | draft | 46% · 88% · 0/3 failed | 83% · 92% · 0/3 failed |
| 07.png | draft | 74% · 97% · 0/3 failed | 98% · 97% · 0/3 failed |
| 08-empty.jpg | draft | 51% · 89% · 3/3 failed | 56% · 100% · 3/3 failed |
| 09.png | draft | 61% · 92% · 0/3 failed | 84% · 92% · 0/3 failed |
| 10.jpg | draft | 96% · 97% · 0/3 failed | 95% · 95% · 0/3 failed |
| 11.jpg | draft | 10% · 80% · 2/3 failed | 99% · 98% · 0/3 failed |
| 12-no-price.jpg | draft | 94% · 98% · 3/3 failed | 94% · 97% · 3/3 failed |
