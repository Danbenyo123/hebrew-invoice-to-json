import json
from pathlib import Path

from image_to_json.main import extract_invoice
from image_to_json.schemas import Invoice
from eval.eval import compare

MAIN_DIRECTORY = Path(__file__).resolve().parent.parent
expected_results_path = MAIN_DIRECTORY / 'eval' / 'dataset' / 'expected_results.json'
current_result_image_path = MAIN_DIRECTORY / 'eval' / 'dataset' / '01.jpg'

with open(expected_results_path,'r',encoding='utf-8') as json_file:
    expected_results_dict = json.loads(json_file.read())

expected_results = expected_results_dict['invoices']
expected_result_01 = expected_results['01.jpg']
expected_result_invoice = Invoice.model_validate(expected_result_01)
expected_result = expected_result_invoice.model_dump()
image_data = current_result_image_path.read_bytes()
current_extraction_result = extract_invoice(image_data)
current_result_invoice = current_extraction_result.invoice
current_result = current_result_invoice.model_dump()
results = compare(current_result,expected_result)
print(results)