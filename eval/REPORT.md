# Evaluation report

Run `20261022-130109.json` · model `claude-opus-5` · 3 run(s) per invoice · 11 invoices

**How to read it**
- **score**: weighted share of correct fields per invoice, averaged over invoices and runs. Weights: invoice number, total and line items ×3; date, VAT, before-VAT and supplier ID ×2; other fields ×1. Fields empty in both the label and the extraction aren't counted.
- **missed / wrong / hallucinated**: a labeled value left empty / a different value / a value invented where the label is empty.
- **honest failures**: on invoices that should fail validation (blank template, missing total), how often the pipeline failed instead of inventing data.
- **consistency**: for repeated runs on the same invoice, the share of runs agreeing on each field.
- **draft labels** were written from the images and are not yet human-verified, so they are reported separately.

## Summary

| pipeline | score (verified) | score (draft labels) | correct | missed | wrong | hallucinated | honest failures | unexpected failures | consistency | avg time | avg tokens in / out |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ocr-claude | 71% | — | 459 (66%) | 136 (20%) | 80 (12%) | 16 (2%) | 6/6 | 0 | 95% | 9.6s | 4,822 / 550 |
| claude-vision | 87% | — | 600 (87%) | 7 (1%) | 68 (10%) | 13 (2%) | 6/6 | 0 | 95% | 6.9s | 4,212 / 489 |

## Accuracy per field (verified labels)

| field | ocr-claude | claude-vision |
|---|---|---|
| id | 84% | 100% |
| products.discount | 0% | 100% |
| products.id | 88% | 100% |
| products.name | 44% | 55% |
| products.price_for_unit | 71% | 100% |
| products.product_total_price | 64% | 100% |
| products.quantity | 78% | 100% |
| total_price | 78% | 100% |
| date | 90% | 100% |
| price_before_VAT | 88% | 100% |
| vat_amount | 44% | 100% |
| customer.address | 30% | 67% |
| customer.id | 55% | 71% |
| customer.name | 67% | 89% |
| customer.phone | 100% | 100% |
| discount | 0% | 100% |
| hour | 67% | 83% |
| price_before_rounding | 50% | 67% |
| rounding | 75% | 100% |
| supplier.address | 50% | 46% |
| supplier.id | 75% | 88% |
| supplier.name | 89% | 66% |
| supplier.phone | 50% | 79% |
| type_of_doc | 90% | 91% |

## Per image (score · consistency · failed validation)

| image | label | ocr-claude | claude-vision |
|---|---|---|---|
| 01.jpg | verified | 100% · 100% · 0/3 failed | 97% · 98% · 0/3 failed |
| 02.png | verified | 86% · 97% · 0/3 failed | 95% · 100% · 0/3 failed |
| 04.jpg | verified | 95% · 98% · 0/3 failed | 94% · 96% · 0/3 failed |
| 05-no-id.png | verified | 78% · 88% · 0/3 failed | 89% · 87% · 0/3 failed |
| 06.png | verified | 47% · 88% · 0/3 failed | 73% · 89% · 0/3 failed |
| 07.png | verified | 68% · 97% · 0/3 failed | 95% · 100% · 0/3 failed |
| 08-empty.jpg | verified | 46% · 94% · 3/3 failed | 48% · 93% · 3/3 failed |
| 09.png | verified | 63% · 96% · 0/3 failed | 82% · 87% · 0/3 failed |
| 10.jpg | verified | 93% · 98% · 0/3 failed | 95% · 100% · 0/3 failed |
| 11.jpg | verified | 10% · 87% · 0/3 failed | 96% · 100% · 0/3 failed |
| 12-no-price.jpg | verified | 95% · 100% · 3/3 failed | 97% · 95% · 3/3 failed |
