"""
POST /api:
 400 - undecodable image,
 422 - validation failure, the full extraction result (with failed checks) in the body
 502 - when the LLM call fails.
GET /api/samples: demo invoices from the dataset; the frontend is served from /
"""
from pathlib import Path

from fastapi import FastAPI, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import anthropic

from typing import Annotated

from image_to_json.model import ExtractionResult
from image_to_json.main import extract_invoice

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIRECTORY = PROJECT_ROOT / 'frontend'
DATASET_DIRECTORY = PROJECT_ROOT / 'eval' / 'dataset'
# invoices that show the pipeline well; 12-no-price shows a validation failure
SAMPLES = {
    "01.jpg": "Retail tax invoice",
    "02.png": "Colored-header invoice",
    "04.jpg": "Furniture invoice-receipt",
    "12-no-price.jpg": "Missing total (fails validation)",
}

app = FastAPI()

origins = ["http://localhost:3000","http://127.0.0.1:5500",]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api")
def upload_image(file: Annotated[bytes,File()]) -> ExtractionResult :
    """
    check if image is valid, check if AI api is working, image->json
    :return:
    json: success / failed
    """
    try:
        invoice = extract_invoice(file)
    except ValueError:
        raise HTTPException(400, "Could not decode file as an image")
    except anthropic.APIError as e:
        raise HTTPException(502, f"LLM provider error: {type(e).__name__}")
    if not invoice.success:
        raise HTTPException(status_code=422, detail={
            "reason": "Validation failure",
            **invoice.model_dump(mode="json"),
        })

    return invoice

@app.get("/api/samples")
def list_samples() -> list[dict]:
    return [{"name": name, "description": description, "url": f"/api/samples/{name}"}
            for name, description in SAMPLES.items()]

@app.get("/api/samples/{name}")
def get_sample(name: str) -> FileResponse:
    if name not in SAMPLES:
        raise HTTPException(404, "Unknown sample")
    return FileResponse(DATASET_DIRECTORY / name)

app.mount("/", StaticFiles(directory=FRONTEND_DIRECTORY, html=True), name="frontend")
