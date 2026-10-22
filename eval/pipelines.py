"""Extraction pipelines compared by the eval. Each one takes image bytes and returns a PipelineResult."""
import base64

import cv2
import numpy as np
from pydantic import BaseModel, ValidationError

from image_to_json.main import extract_invoice
from image_to_json.model import client, MODEL, MAX_TOKENS, EXTRACTION_RULES, add_usage, check_required
from image_to_json.schemas import Invoice


class PipelineResult(BaseModel):
    invoice: Invoice | None = None
    success: bool = False
    errors: list[str] = []
    input_tokens: int = 0
    output_tokens: int = 0


def ocr_claude(image: bytes) -> PipelineResult:
    """the project pipeline: preprocessing, OCR, Claude extraction with validation and retry"""
    result = extract_invoice(image)
    return PipelineResult(invoice=result.invoice, success=result.success, errors=result.errors,
                          input_tokens=result.input_tokens, output_tokens=result.output_tokens)


VISION_PROMPT = f"""
this is an image of an Israeli tax invoice/receipt in Hebrew.
{EXTRACTION_RULES}
"""


def to_jpeg(image: bytes) -> bytes:
    """Claude accepts jpeg/png/gif/webp only, and the dataset also has avif"""
    img = cv2.imdecode(np.frombuffer(image, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("unreadable image")
    ok, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return buf.tobytes()


def claude_vision(image: bytes) -> PipelineResult:
    """the same Claude model reading the image directly: one call, no OCR, no retry"""
    usage = {"input_tokens": 0, "output_tokens": 0}
    data = base64.b64encode(to_jpeg(image)).decode()
    try:
        response = client.messages.parse(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": data}},
                    {"type": "text", "text": VISION_PROMPT},
                ],
            }],
            output_format=Invoice,
        )
    except ValidationError as e:
        return PipelineResult(errors=[f"model output failed schema validation: {e.error_count()} error(s)"])
    add_usage(usage, response)
    inv = response.parsed_output
    if inv is None:
        return PipelineResult(errors=["model returned no structured output"], **usage)
    missing = check_required(inv)
    return PipelineResult(invoice=inv, success=not missing, errors=missing, **usage)


PIPELINES = {
    "ocr-claude": ocr_claude,
    "claude-vision": claude_vision,
}
