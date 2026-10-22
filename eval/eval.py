from contextlib import ExitStack
from pathlib import Path
import json

from image_to_json.main import extract_invoice
from image_to_json.schemas import Invoice

DATASET_DIRECTORY = Path(__file__).parent.resolve() / 'dataset'
dataset_images_paths_array = [p for p in DATASET_DIRECTORY.iterdir() if p.suffix.lower() in {'.jpg','.png'}]
expected_results_path = DATASET_DIRECTORY / 'expected_results.json'
fields_weights = {
    "date": ,
    "hour": ,
    "type_of_doc": ,
    "id": 3
    "products": ,
    "price_before_rounding": ,
    "rounding": ,
    "price_before_VAT": ,
    "vat_amount": ,
    "discount": ,
    "total_price": ,
    "supplier": ,
    "customer": ,
}

def compare(current_output:dict,expected_output:dict):

    matched_fields = []
    missed_fields = []
    wrong_fields = []
    hallucinated_fields = []

    for field in expected_output:
        comparison_message = f""" {field}: 
        expected output - '{expected_output[field]}' 
        current output -  '{current_output[field]}'"""
        if expected_output[field] == current_output[field]:
            matched_fields.append(comparison_message)
        else:
            if expected_output[field] is None and current_output[field] is not None:
                hallucinated_fields.append(comparison_message)
            elif expected_output[field] is not None and current_output[field] is None:
                missed_fields.append(comparison_message)
            else:
                wrong_fields.append(comparison_message)
    return {
        'matched': matched_fields,
        'missed': missed_fields,
        'wrong': wrong_fields,
        'hallucinated': hallucinated_fields
    }

def main():
    results = {}
    with open(expected_results_path,"r",encoding="utf-8") as expected_results_json_data:
        for image_path in dataset_images_paths_array:
            with open(image_path,"rb") as image_data:
                image_bytes = image_data.read()
            current_extraction_result = extract_invoice(image_bytes)
            current_result_invoice = current_extraction_result.invoice
            current_result = current_result_invoice.model_dump()

            expected_results_dict = json.load(expected_results_json_data)['invoices']
            image_file_name = image_path.name
            single_image_expected_results = expected_results_dict[image_file_name]
            expected_result_invoice = Invoice.model_validate(single_image_expected_results)
            expected_result = expected_result_invoice.model_dump()

            comparison = compare(current_result,expected_result)
            results[image_file_name] = comparison
    print(results)



if __name__ == '__main__':
    main()