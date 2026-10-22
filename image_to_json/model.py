import os
from dotenv import load_dotenv
import anthropic
from pydantic import BaseModel, Field, ValidationError

from image_to_json.schemas import Invoice

dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(dotenv_path=dotenv_path)

client = anthropic.Anthropic()
MODEL = "claude-opus-5"
MAX_TOKENS = 8192

REQUIRED_FIELDS = ("id","total_price")

def prompt_llm(ocr_text,output_scheme,previous_json,problems):
    checks = "\n".join(f"- {p}" for p in problems)
    prompt = f"""
                this is OCR hebrew text from an Israeli tax invoice/receipt, reconstructed for RTL reading order, and it may contains recognition errors.
                never calculate, infer, or reconcile a value that isn't legible on the page; emit None instead in the field.
                the amount sits to the left of its label except from tables and columns.
                <ocr_text>
                {ocr_text}
                </ocr_text>
            """
    if previous_json is not None:
            prompt += f"""
            a previous extraction attempt produced this:
            <previous_extraction>
            {previous_json}
            </previous_extraction>
            """
    if problems:
            prompt += f"""
            the previous attempt failed these checks:
            <failed_checks>
            {checks}
            </failed_checks>
            re-read the text and fix only what is actually legible. a field still not clearly labeled on the page stays null:
            never fill it with a value that belongs to another field (rounding, VAT, a line item, a date or an id).
            """

    response = client.messages.parse(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        output_format=output_scheme
    )
    return response.parsed_output

class ExtractionResult(BaseModel):
    invoice: Invoice | None = None
    success: bool
    errors: list[str] = []
    fixed_errors: list[str] = []
    warnings: list[str] = []
    attempts: int = 1
    raw_text: str | None = None
    preprocessed_image: str | None = Field(None, description="preprocessed image as a base64 PNG data URL, for display")
    @property
    def ok(self) -> bool:
        return self.invoice is not None and not self.errors

def check_required(inv: Invoice) -> list[str]:
    problems = []
    for f in REQUIRED_FIELDS:
        if getattr(inv,f) is None:
            problems.append(f"mandatory field '{f}' is missing")
    if not inv.products:
        problems.append("no line items were found")
    return problems

def check_arithmetic(inv:Invoice) -> list[str]:
    problems = []
    if (inv.price_before_VAT is not None
            and inv.price_before_rounding is not None
            and inv.rounding is not None):
        expected = inv.price_before_rounding - inv.rounding
        if inv.price_before_VAT != expected:
            problems.append(f"price_before_VAT ({inv.price_before_VAT}) != price_before_rounding ({inv.price_before_rounding}) - rounding ({inv.rounding}) = {expected}")

    if (inv.price_before_VAT is not None
            and inv.vat_amount is not None
            and inv.total_price is not None):
        expected = inv.price_before_VAT + inv.vat_amount
        if expected != inv.total_price:
            problems.append(f"total_price ({inv.total_price}) != price_before_VAT ({inv.price_before_VAT}) + vat_amount ({inv.vat_amount}) = {expected}")
    return problems

def extract(ocr_text: str, max_attempts: int = 2) -> ExtractionResult:
    previous_json = None
    problems: list[str] = []
    for attempt in range(1,max_attempts + 1):
        try:
            inv = prompt_llm(
                ocr_text,
                Invoice,
                previous_json=previous_json,
                problems=problems
            )
        except ValidationError as e:
            if attempt == max_attempts:
                return ExtractionResult(raw_text=ocr_text,errors =[f"model output failed schema validation: {e.error_count()} error(s)"],attempts=attempt,success=False)
            problems = [f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}"
                        for err in e.errors()]
            previous_json = None
            continue

        if inv is None:
            if attempt == max_attempts:
                return ExtractionResult(raw_text=ocr_text,errors=["model returned no structured output"],attempts=attempt,success=False)
            problems = ["previous attempt returned no structured output"]
            previous_json = None
            continue

        missing = check_required(inv)
        bad_math = check_arithmetic(inv)

        if not missing:
            return ExtractionResult(raw_text=ocr_text,invoice=inv,warnings=bad_math,attempts=attempt,
                                    fixed_errors=[p for p in problems if p not in bad_math],success=True)

        if attempt == max_attempts:
            # Return what we have, with the failures attached. Caller decides.
            return ExtractionResult(
                invoice=inv,
                raw_text=ocr_text,
                errors=missing,
                warnings=bad_math,
                attempts=attempt,
                success=False
            )

        previous_json = inv.model_dump_json(indent=2)
        problems = missing + bad_math

    raise AssertionError("unreachable")