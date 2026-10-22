"""Tests for image_to_json.model retry/validation logic with the LLM mocked out."""
import os
from decimal import Decimal
from unittest import mock

os.environ.setdefault("ANTHROPIC_API_KEY", "test")

import pytest
from pydantic import ValidationError

from image_to_json import model
from image_to_json.schemas import Invoice

BASE = dict(id="1", products=[{"name": "x", "product_total_price": "10"}],
            price_before_rounding=None, rounding=None, price_before_VAT=None,
            vat_amount=None, total_price="10")


def inv(**kw):
    return Invoice.model_validate({**BASE, **kw})


def schema_error():
    try:
        Invoice.model_validate({**BASE, "total_price": "abc"})
    except ValidationError as e:
        return e


def run(responses, **kw):
    calls = []
    def fake(ocr, scheme, previous_json, problems, usage=None):
        calls.append(dict(previous_json=previous_json, problems=list(problems)))
        r = responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
    with mock.patch.object(model, "prompt_llm", side_effect=fake):
        return model.extract("ocr", **kw), calls


# --- check_arithmetic ---
def test_arithmetic_ok_no_problems():
    i = inv(price_before_rounding="203.88", rounding="-0.43", price_before_VAT="204.31",
            vat_amount="32.69", total_price="237.0")
    assert model.check_arithmetic(i) == []

def test_arithmetic_messages_are_strings():
    i = inv(price_before_rounding="100", rounding="1", price_before_VAT="50",
            vat_amount="5", total_price="70")
    p = model.check_arithmetic(i)
    assert len(p) == 2 and all(isinstance(x, str) and "..." not in x and "Ellipsis" not in x for x in p)

def test_arithmetic_zero_values_checked():
    # vat_amount=0 must still be checked (not skipped as falsy)
    i = inv(price_before_VAT="100", vat_amount="0", total_price="117")
    assert len(model.check_arithmetic(i)) == 1

def test_arithmetic_skipped_when_missing():
    assert model.check_arithmetic(inv()) == []


# --- extract flow ---
def test_success_first_try():
    r, calls = run([inv()])
    assert r.success and r.attempts == 1 and r.warnings == [] and r.fixed_errors == []
    assert len(calls) == 1

def test_bad_math_attached_as_warnings_on_success_no_retry():
    bad = inv(price_before_VAT="100", vat_amount="17", total_price="200")
    r, calls = run([bad])
    assert r.success and r.attempts == 1 and len(calls) == 1
    assert len(r.warnings) == 1 and "total_price" in r.warnings[0]
    assert r.errors == []

def test_missing_then_fixed():
    r, calls = run([inv(id=None), inv()])
    assert r.success and r.attempts == 2
    assert r.fixed_errors == ["mandatory field 'id' is missing"]
    assert calls[1]["previous_json"] is not None
    assert calls[1]["problems"] == ["mandatory field 'id' is missing"]

def test_missing_twice_fails_with_warnings():
    bad = inv(id=None, price_before_VAT="100", vat_amount="17", total_price="200")
    r, _ = run([bad, bad])
    assert not r.success and r.attempts == 2
    assert r.errors == ["mandatory field 'id' is missing"]
    assert len(r.warnings) == 1
    assert r.invoice is not None

def test_persisting_bad_math_not_in_fixed_errors():
    bad_vals = dict(price_before_VAT="100", vat_amount="17", total_price="200")
    r, calls = run([inv(id=None, **bad_vals), inv(**bad_vals)])
    assert r.success
    assert r.fixed_errors == ["mandatory field 'id' is missing"]
    assert len(r.warnings) == 1
    assert len(calls[1]["problems"]) == 2  # model was told about both

def test_validation_error_feedback_sent_on_retry():
    r, calls = run([schema_error(), inv()])
    assert r.success and r.attempts == 2
    assert calls[1]["previous_json"] is None
    assert calls[1]["problems"] and "total_price" in calls[1]["problems"][0]
    assert r.fixed_errors == calls[1]["problems"]

def test_validation_error_twice_fails():
    r, _ = run([schema_error(), schema_error()])
    assert not r.success and r.invoice is None and r.raw_text == "ocr"
    assert "schema validation" in r.errors[0]

def test_none_output_retried_then_fails():
    r, calls = run([None, None])
    assert not r.success and r.errors == ["model returned no structured output"]
    assert calls[1]["problems"] == ["previous attempt returned no structured output"]

def test_none_then_success():
    r, _ = run([None, inv()])
    assert r.success and r.attempts == 2

def test_single_attempt():
    r, calls = run([inv(id=None)], max_attempts=1)
    assert not r.success and len(calls) == 1


# --- prompt construction ---
def capture_prompt(previous_json, problems):
    resp = mock.Mock(parsed_output=inv(), usage=mock.Mock(input_tokens=10, output_tokens=5))
    with mock.patch.object(model.client.messages, "parse", return_value=resp) as p:
        model.prompt_llm("TEXT", Invoice, previous_json, problems)
    return p.call_args.kwargs["messages"][0]["content"]

def test_prompt_first_attempt_has_no_feedback():
    pr = capture_prompt(None, [])
    assert "TEXT" in pr and "failed_checks" not in pr and "previous_extraction" not in pr

def test_prompt_includes_checks_without_previous_json():
    pr = capture_prompt(None, ["total_price: bad"])
    assert "- total_price: bad" in pr and "previous_extraction" not in pr

def test_prompt_includes_both():
    pr = capture_prompt('{"id": null}', ["mandatory field 'id' is missing"])
    assert '{"id": null}' in pr and "- mandatory field 'id' is missing" in pr


# --- API layer still serializes results ---
def test_api_success_and_failure():
    from fastapi.testclient import TestClient
    from api import api
    c = TestClient(api.app)
    ok = model.ExtractionResult(invoice=inv(), success=True, warnings=["w"])
    with mock.patch.object(api, "extract_invoice", return_value=ok):
        res = c.post("/api", files={"file": ("a.jpg", b"x")})
        assert res.status_code == 200 and res.json()["warnings"] == ["w"]
    bad = model.ExtractionResult(success=False, errors=["e"], raw_text="t")
    with mock.patch.object(api, "extract_invoice", return_value=bad):
        res = c.post("/api", files={"file": ("a.jpg", b"x")})
        assert res.status_code == 422 and res.json()["detail"]["errors"] == ["e"]


# --- OCR number merge ---
from image_to_json.ocr import merge_numbers

def words(*ws):
    """ws: (text, conf, left, top, width, height)"""
    keys = ('text', 'conf', 'left', 'top', 'width', 'height')
    return {k: [w[n] for w in ws] for n, k in enumerate(keys)}

def test_merge_replaces_misread_amount():
    heb = words(('0', 96, 100, 10, 80, 20), ('מחיר', 95, 300, 10, 60, 20))
    eng = words(('1,132.00', 90, 98, 10, 84, 20))
    m = merge_numbers(heb, eng)
    assert '1,132.00' in m['text'] and '0' not in m['text'] and 'מחיר' in m['text']

def test_merge_never_touches_hebrew_words():
    heb = words(('ובו', 90, 100, 10, 60, 20))
    eng = words(('100.00', 90, 100, 10, 60, 20))
    assert merge_numbers(heb, eng)['text'] == ['ובו']

def test_merge_ignores_plain_ids_dates_percents():
    heb = words(('023042145', 95, 100, 10, 120, 20), ('12/2010', 90, 300, 10, 80, 20), ('18%', 90, 500, 10, 40, 20))
    eng = words(('023062155', 90, 100, 10, 120, 20), ('32/2010', 90, 300, 10, 80, 20), ('1855', 90, 500, 10, 40, 20))
    assert merge_numbers(heb, eng)['text'] == heb['text']

def test_merge_ignores_low_confidence_and_unmatched():
    heb = words(('0', 96, 100, 10, 80, 20))
    eng = words(('15,500.00', 42, 100, 10, 80, 20), ('99.00', 95, 900, 10, 60, 20))
    assert merge_numbers(heb, eng)['text'] == ['0']

def test_merge_strips_misread_shekel_and_keeps_shekel_word():
    heb = words(('m5,500.00', 86, 100, 10, 160, 20), ('₪', 90, 270, 10, 20, 20))
    eng = words(('m5,500.00', 86, 100, 10, 160, 20))
    assert sorted(merge_numbers(heb, eng)['text']) == sorted(['5,500.00', '₪'])

def test_retry_prompt_forbids_borrowing_values():
    pr = capture_prompt('{"id": null}', ["mandatory field 'total_price' is missing"])
    assert "never fill it with a value that belongs to another field" in pr
