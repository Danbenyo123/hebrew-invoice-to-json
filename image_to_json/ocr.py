
import pytesseract
from pytesseract import Output
from cv2.typing import MatLike
from pathlib import Path
import numpy as np
import re

PROJECT_ROOT = Path(__file__).resolve().parent

def process_image_to_data(pre_processed_image:MatLike) -> dict:
    return pytesseract.image_to_data(pre_processed_image,lang='heb+eng',config='--psm 3',output_type=Output.DICT)

# the Hebrew model misreads formatted amounts (e.g. '1,132.00' -> '0'), so numbers come from an English pass
# only money ('1,132.00', '-0.43', '0.43-') and times; plain ids/dates/percents read better in Hebrew
NUMBER_RE = re.compile(r'[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}-?|\d{1,2}:\d{2}(?::\d{2})?')
SHEKEL_MISREAD_RE = re.compile(r'^[mwW₪]+')  # '₪5,500.00' comes out as 'm5,500.00'
HEBREW_RE = re.compile(r'[\u0590-\u05FF]')
ENG_MIN_CONF = 50

def process_image_to_data_eng(pre_processed_image:MatLike) -> dict:
    return pytesseract.image_to_data(pre_processed_image,lang='eng',config='--psm 3',output_type=Output.DICT)

def _box(data, i):
    return data['left'][i], data['top'][i], data['left'][i] + data['width'][i], data['top'][i] + data['height'][i]

def _overlap_frac(a, b) -> float:
    """intersection area as a fraction of box a"""
    iw = min(a[2], b[2]) - max(a[0], b[0])
    ih = min(a[3], b[3]) - max(a[1], b[1])
    if iw <= 0 or ih <= 0:
        return 0.0
    return iw * ih / max(1, (a[2] - a[0]) * (a[3] - a[1]))

def merge_numbers(heb: dict, eng: dict) -> dict:
    """replace Hebrew-pass words with English-pass numbers where their boxes overlap"""
    keys = ('text', 'conf', 'left', 'top', 'width', 'height')
    heb_idx = [i for i in range(len(heb['text'])) if heb['text'][i].strip()]
    dropped = set()
    added = []
    for j in range(len(eng['text'])):
        t = SHEKEL_MISREAD_RE.sub('', eng['text'][j].strip())
        conf = float(eng['conf'][j])
        if not NUMBER_RE.fullmatch(t) or conf < ENG_MIN_CONF:
            continue
        eb = _box(eng, j)
        overlapping = [i for i in heb_idx if _overlap_frac(_box(heb, i), eb) > 0.3 or _overlap_frac(eb, _box(heb, i)) > 0.3]
        if not overlapping or any(HEBREW_RE.search(heb['text'][i]) for i in overlapping):
            continue  # only replace words the Hebrew pass found, never Hebrew text
        dropped.update(i for i in overlapping if heb['text'][i].strip() != '₪')
        added.append((j, t))
    merged = {k: [heb[k][i] for i in range(len(heb['text'])) if i not in dropped] for k in keys}
    for j, t in added:
        for k in keys:
            merged[k].append(t if k == 'text' else eng[k][j])
    return merged

def process_data_to_structured_data(data, conf_min=40, page_width=None, tol_frac=0.5) -> str:
    idx = [i for i in range(len(data['text']))
           if data['text'][i].strip() and int(data['conf'][i]) > conf_min]
    if not idx:
        return ''

    W = page_width or max(data['left'][i] + data['width'][i] for i in idx)
    char_px = float(np.median([data['width'][i] / len(data['text'][i]) for i in idx]))

    words = [{
        'x': W - (data['left'][i] + data['width'][i]),  # mirrored left edge
        'base': data['top'][i] + data['height'][i],  # baseline
        'h': data['height'][i],
        'txt': data['text'][i],
    } for i in idx]

    words.sort(key=lambda w: w['base'])

    lines, cur = [], []
    for w in words:
        if cur:
            ref_base = np.median([c['base'] for c in cur])
            ref_h = np.median([c['h'] for c in cur])
            if abs(w['base'] - ref_base) > tol_frac * min(w['h'], ref_h):
                lines.append(cur)
                cur = []
        cur.append(w)
    if cur:
        lines.append(cur)

    out = []
    for line in lines:
        row = []
        for w in sorted(line, key=lambda w: w['x']):
            col = int(w['x'] / char_px)
            row += [' '] * max(1 if row else 0, col - len(row))
            row += list(w['txt'])
        out.append(''.join(row).rstrip())
    return '\n'.join(out)

def main_ocr(pp_image:MatLike) -> str:
    data = merge_numbers(process_image_to_data(pp_image), process_image_to_data_eng(pp_image))
    spatial_text = process_data_to_structured_data(data,page_width=pp_image.shape[1])
    return spatial_text