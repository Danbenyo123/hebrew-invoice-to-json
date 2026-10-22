"""Dataset images and their hand-written labels."""
import json
from dataclasses import dataclass
from pathlib import Path

from image_to_json.schemas import Invoice

DATASET_DIRECTORY = Path(__file__).parent.resolve() / 'dataset'
LABEL_FILE = 'expected_results.json'
# labels for images kept out of the repo; loaded when present, left out of the committed report
PRIVATE_LABEL_FILE = 'expected_results.private.json'
IMAGE_SUFFIXES = {'.jpg', '.jpeg', '.png'}
META_KEYS = ('verified', 'expect_failure', 'notes')


@dataclass
class Label:
    invoice: Invoice
    verified: bool
    expect_failure: bool
    notes: str | None = None
    private: bool = False


def load_labels() -> dict[str, Label]:
    labels = {}
    for file_name in (LABEL_FILE, PRIVATE_LABEL_FILE):
        path = DATASET_DIRECTORY / file_name
        if not path.exists():
            continue
        with open(path, encoding='utf-8') as f:
            invoices = json.load(f)['invoices']
        for image_name, raw in invoices.items():
            fields = {k: v for k, v in raw.items() if k not in META_KEYS}
            labels[image_name] = Label(
                invoice=Invoice.model_validate(fields),
                verified=raw.get('verified', True),
                expect_failure=raw.get('expect_failure', False),
                notes=raw.get('notes'),
                private=file_name == PRIVATE_LABEL_FILE,
            )
    return labels


def image_paths(names: list[str] | None = None) -> list[Path]:
    paths = sorted(p for p in DATASET_DIRECTORY.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)
    if names:
        paths = [p for p in paths if p.name in names]
    return paths
