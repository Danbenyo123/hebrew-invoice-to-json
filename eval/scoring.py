"""
Field-level scoring of an extracted invoice against its label.

Every field where the label or the extraction has a value gets one outcome:
  correct      - same value after normalization
  missed       - label has a value, extraction is empty
  wrong        - both have values and they differ
  hallucinated - label is empty, extraction invented a value
Fields empty on both sides are not counted.
"""
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum

from image_to_json.schemas import Invoice

CORRECT, MISSED, WRONG, HALLUCINATED = "correct", "missed", "wrong", "hallucinated"
OUTCOMES = (CORRECT, MISSED, WRONG, HALLUCINATED)

SCALAR_FIELDS = ("date", "hour", "type_of_doc", "id", "price_before_rounding", "rounding",
                 "price_before_VAT", "vat_amount", "discount", "total_price")
PARTIES = ("supplier", "customer")
PARTY_FIELDS = ("id", "name", "phone", "address")
PRODUCT_FIELDS = ("id", "name", "quantity", "price_for_unit", "discount", "product_total_price")

# a group's weight is shared by all of its outcomes, so many line items don't outweigh the total
FIELD_WEIGHTS = {"id": 3, "total_price": 3, "products": 3,
                 "date": 2, "vat_amount": 2, "price_before_VAT": 2, "supplier.id": 2}

QUOTES = str.maketrans({'״': '"', '“': '"', '”': '"', '„': '"', '׳': "'", '‘': "'", '’': "'", '`': "'"})
DIRECTION_MARKS = re.compile('[‎‏]')
DIGIT_FIELDS = {"id", "phone"}  # compared without spaces and dashes


@dataclass
class FieldOutcome:
    field: str    # e.g. 'total_price', 'supplier.name', 'products.name'
    group: str    # weighting group: the field, 'products', or 'supplier.id'
    outcome: str
    weight: float = 1.0


def normalize(value, field: str = ""):
    """canonical, comparable form of a value; None for empty"""
    if value is None:
        return None
    if isinstance(value, Enum):
        value = value.value
    if isinstance(value, (int, float, Decimal)):
        return format(Decimal(str(value)).normalize(), 'f')
    if isinstance(value, date):
        return value.isoformat()
    text = DIRECTION_MARKS.sub('', str(value)).translate(QUOTES)
    text = re.sub(r'\s+[-–]\s+', ' ', text)
    if field.rsplit('.', 1)[-1] in DIGIT_FIELDS:
        text = re.sub(r'[\s\-]', '', text)
    text = re.sub(r'\s+', ' ', text).strip().rstrip('.,;:')
    return text or None


def outcome(expected, got) -> str | None:
    if expected is None and got is None:
        return None
    if expected is None:
        return HALLUCINATED
    if got is None:
        return MISSED
    return CORRECT if expected == got else WRONG


def _product(item) -> dict:
    return {f: normalize(getattr(item, f), f) for f in PRODUCT_FIELDS}


def match_products(expected: list[dict], got: list[dict]) -> list[tuple[dict | None, dict | None]]:
    """pair line items greedily by the number of equal fields; unpaired items get None"""
    candidates = []
    for i, e in enumerate(expected):
        for j, g in enumerate(got):
            same = sum(1 for f in PRODUCT_FIELDS if e[f] is not None and e[f] == g[f])
            if same:
                candidates.append((same, i, j))
    pairs, used_e, used_g = [], set(), set()
    for same, i, j in sorted(candidates, reverse=True):
        if i not in used_e and j not in used_g:
            pairs.append((expected[i], got[j]))
            used_e.add(i)
            used_g.add(j)
    pairs += [(e, None) for i, e in enumerate(expected) if i not in used_e]
    pairs += [(None, g) for j, g in enumerate(got) if j not in used_g]
    return pairs


def score_invoice(expected: Invoice, got: Invoice | None) -> list[FieldOutcome]:
    results = []

    def add(field, group, e, g):
        o = outcome(e, g)
        if o:
            results.append(FieldOutcome(field, group, o))

    for f in SCALAR_FIELDS:
        add(f, f, normalize(getattr(expected, f), f), normalize(getattr(got, f), f) if got else None)
    for party in PARTIES:
        e_party, g_party = getattr(expected, party), getattr(got, party) if got else None
        for f in PARTY_FIELDS:
            path = f"{party}.{f}"
            add(path, path, normalize(getattr(e_party, f), path) if e_party else None,
                normalize(getattr(g_party, f), path) if g_party else None)

    empty = dict.fromkeys(PRODUCT_FIELDS)
    got_products = (got.products or []) if got else []
    for e, g in match_products([_product(p) for p in expected.products or []],
                               [_product(p) for p in got_products]):
        for f in PRODUCT_FIELDS:
            add(f"products.{f}", "products", (e or empty)[f], (g or empty)[f])

    group_sizes = Counter(r.group for r in results)
    for r in results:
        r.weight = FIELD_WEIGHTS.get(r.group, 1) / group_sizes[r.group]
    return results


def weighted_score(results: list[FieldOutcome]) -> float | None:
    total = sum(r.weight for r in results)
    if not total:
        return None
    return sum(r.weight for r in results if r.outcome == CORRECT) / total


def flatten(inv: Invoice | None) -> dict:
    """normalized field values, with line items as one sorted value, for comparing runs"""
    if inv is None:
        return {}
    flat = {f: normalize(getattr(inv, f), f) for f in SCALAR_FIELDS}
    for party in PARTIES:
        p = getattr(inv, party)
        for f in PARTY_FIELDS:
            flat[f"{party}.{f}"] = normalize(getattr(p, f), f) if p else None
    flat["products"] = tuple(sorted(tuple(str(v) for v in _product(p).values()) for p in inv.products or []))
    return flat


def consistency(runs: list[Invoice | None]) -> float | None:
    """mean share of runs agreeing with the most common value, over fields that any run filled"""
    if len(runs) < 2:
        return None
    flats = [flatten(inv) for inv in runs]
    fields = {f for flat in flats for f, v in flat.items() if v not in (None, ())}
    if not fields:
        return 1.0
    agreement = []
    for f in fields:
        values = Counter(flat.get(f) for flat in flats)
        agreement.append(values.most_common(1)[0][1] / len(runs))
    return sum(agreement) / len(agreement)
