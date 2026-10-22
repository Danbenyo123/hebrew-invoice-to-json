import base64
from time import perf_counter

import cv2

from image_to_json.model import extract,ExtractionResult

from image_to_json.pre_process import main_pre_process
from image_to_json.ocr import main_ocr


def to_png_data_url(image) -> str:
    ok, buf = cv2.imencode('.png', image)
    return "data:image/png;base64," + base64.b64encode(buf.tobytes()).decode()

def extract_invoice(image_data:bytes) -> ExtractionResult:
    start_time = perf_counter()
    pp = main_pre_process(image_data)
    structured_ocr = main_ocr(pp)
    if len(structured_ocr.strip()) < 1:
        return ExtractionResult(success=False, errors=["no text detected in image"],raw_text="",
                                preprocessed_image=to_png_data_url(pp))
    extracted_invoice = (extract(structured_ocr,2))
    extracted_invoice.preprocessed_image = to_png_data_url(pp)
    end_time = perf_counter()
    print(f"time took for request: {end_time - start_time}")
    return extracted_invoice
