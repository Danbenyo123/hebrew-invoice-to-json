"""Tests for the eval scoring, labels and report, without API calls."""
import os

os.environ.setdefault("ANTHROPIC_API_KEY", "test")

from image_to_json.schemas import Invoice
from eval import scoring
from eval.dataset import load_labels, image_paths
from eval.report import render
from eval.scoring import (CORRECT, MISSED, WRONG, HALLUCINATED, normalize, score_invoice,
                          weighted_score, consistency, match_products)

BASE = dict(date="18/07/2011", hour=None, type_of_doc="חשבונית", id="66621",
            products=[{"id": "666", "name": "שישיית קולה", "quantity": 6, "price_for_unit": 33.98,
                       "product_total_price": 203.88}],
            price_before_rounding=None, rounding=None, price_before_VAT=204.31, vat_amount=32.69,
            total_price=237.0, supplier={"name": 'קריאטיב סופטוור בע"מ', "phone": "1-599-505019"},
            customer=None)


def inv(**kw):
    return Invoice.model_validate({**BASE, **kw})


def outcomes(results):
    return {r.field: r.outcome for r in results}


# --- normalize ---
def test_normalize_numbers_compare_by_value():
    assert normalize(237.0) == normalize("237") == normalize(237) == "237"
    assert normalize(1.50) == "1.5"

def test_normalize_hebrew_quotes_and_spaces():
    assert normalize('בע״מ') == normalize('בע"מ')
    assert normalize(' קוטג׳  9% ') == normalize("קוטג' 9%")
    assert normalize("אינטרסרף - חברה לבדיקה") == normalize("אינטרסרף חברה לבדיקה")

def test_normalize_ids_and_phones_ignore_dashes():
    assert normalize("050 77774852", "customer.phone") == normalize("05077774852", "customer.phone")
    assert normalize("00000000-0", "customer.id") == "000000000"
    assert normalize("02/000001", "id") == "02/000001"

def test_normalize_empty_is_none():
    assert normalize("  ") is None and normalize(None) is None


# --- score_invoice ---
def test_perfect_extraction_scores_one():
    results = score_invoice(inv(), inv())
    assert all(r.outcome == CORRECT for r in results)
    assert weighted_score(results) == 1

def test_outcome_kinds():
    got = inv(total_price=None, vat_amount=99, hour="10:00", date="18/07/2011")
    o = outcomes(score_invoice(inv(), got))
    assert o["total_price"] == MISSED
    assert o["vat_amount"] == WRONG
    assert o["hour"] == HALLUCINATED
    assert o["date"] == CORRECT

def test_fields_empty_on_both_sides_not_counted():
    fields = {r.field for r in score_invoice(inv(), inv())}
    assert "rounding" not in fields and "customer.name" not in fields

def test_no_extraction_misses_everything_labeled():
    results = score_invoice(inv(), None)
    assert results and all(r.outcome == MISSED for r in results)
    assert weighted_score(results) == 0

def test_weights_shared_within_group():
    many = [{"name": f"item {i}", "product_total_price": i} for i in range(10)]
    results = score_invoice(inv(products=many), inv(products=many))
    product_weight = sum(r.weight for r in results if r.group == "products")
    assert abs(product_weight - scoring.FIELD_WEIGHTS["products"]) < 1e-9

def test_wrong_total_costs_more_than_wrong_hour():
    labeled = inv(hour="15:41:14")
    wrong_total = weighted_score(score_invoice(labeled, inv(hour="15:41:14", total_price=1)))
    wrong_hour = weighted_score(score_invoice(labeled, inv(hour="10:00")))
    assert wrong_total < wrong_hour


# --- line items ---
def test_products_matched_regardless_of_order():
    a = {"name": "א", "product_total_price": 1}
    b = {"name": "ב", "product_total_price": 2}
    o = [r.outcome for r in score_invoice(inv(products=[a, b]), inv(products=[b, a])) if r.group == "products"]
    assert set(o) == {CORRECT}

def test_extra_and_missing_products():
    a = {"name": "א", "product_total_price": 1}
    extra = {"name": "ג", "product_total_price": 5}
    results = [r for r in score_invoice(inv(products=[a]), inv(products=[a, extra])) if r.group == "products"]
    assert {r.outcome for r in results} == {CORRECT, HALLUCINATED}
    results = [r for r in score_invoice(inv(products=[a, extra]), inv(products=[a])) if r.group == "products"]
    assert {r.outcome for r in results} == {CORRECT, MISSED}

def test_match_products_unmatched_get_none():
    pairs = match_products([{f: None for f in scoring.PRODUCT_FIELDS} | {"name": "x"}],
                           [{f: None for f in scoring.PRODUCT_FIELDS} | {"name": "y"}])
    assert len(pairs) == 2 and all(None in p for p in pairs)


# --- consistency ---
def test_consistency():
    assert consistency([inv()]) is None
    assert consistency([inv(), inv(), inv()]) == 1
    c = consistency([inv(), inv(), inv(total_price=1)])
    assert 0.9 < c < 1

def test_consistency_counts_failed_run_as_disagreement():
    assert consistency([inv(), None]) < 1


# --- labels and report ---
def test_dataset_labels_load_and_validate():
    labels = load_labels()
    assert {"01.jpg", "08-empty.jpg", "12-no-price.jpg"} <= set(labels)
    assert labels["08-empty.jpg"].expect_failure and labels["12-no-price.jpg"].expect_failure
    assert labels["01.jpg"].verified
    assert all(p.name in labels for p in image_paths() if p.name != "03.jpg")

def test_report_renders_from_saved_run():
    labels = load_labels()
    good = {"invoice": labels["01.jpg"].invoice.model_dump(mode="json"), "success": True,
            "errors": [], "input_tokens": 100, "output_tokens": 50}
    run = {"model": "m", "runs": 2, "images": ["01.jpg", "12-no-price.jpg"], "results": [
        {"pipeline": "p", "image": "01.jpg", "run": 1, "seconds": 1.0, "error": None, "result": good},
        {"pipeline": "p", "image": "01.jpg", "run": 2, "seconds": 1.0, "error": None, "result": good},
        {"pipeline": "p", "image": "12-no-price.jpg", "run": 1, "seconds": 1.0, "error": None,
         "result": {**good, "success": False}},
        {"pipeline": "p", "image": "12-no-price.jpg", "run": 2, "seconds": 1.0, "error": "APIError: x",
         "result": None},
    ]}
    text = render(run, labels)
    assert "1/2" in text      # one honest failure out of two expected-failure runs
    assert "100%" in text     # 01 extracted perfectly
    assert "|" in render(run, labels, markdown=True)

def test_written_report_leaves_out_private_images():
    from eval.dataset import Label
    from eval.report import public_run
    labels = {"a.jpg": Label(invoice=inv(), verified=True, expect_failure=False),
              "p.jpg": Label(invoice=inv(), verified=True, expect_failure=False, private=True)}
    run = {"images": ["a.jpg", "p.jpg"], "results": [{"image": "a.jpg"}, {"image": "p.jpg"}]}
    assert public_run(run, labels) == {"images": ["a.jpg"], "results": [{"image": "a.jpg"}]}
