import cv2
import numpy as np
import statistics
from cv2.typing import MatLike
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
TARGET_WIDTH = 2000

def load_image_to_matrix_gray(data:bytes) -> MatLike:
    if not data:
        raise ValueError("empty file")
    arr = np.frombuffer(data,np.uint8)
    img = cv2.imdecode(arr,cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise ValueError("unreadable image")
    return img

def upscale(img: MatLike) -> MatLike:
    w = img.shape[1]
    if w >= TARGET_WIDTH:
        return img
    scale = TARGET_WIDTH / w
    return cv2.resize(img, (TARGET_WIDTH, int(img.shape[0] * scale)),
                      interpolation=cv2.INTER_CUBIC)

def fix_inverted_regions(gray: MatLike, dark_max: int = 190, min_area_frac: float = 0.002) -> MatLike:
    """
    Find solid dark background blocks (e.g. a colored header or totals bar) and invert them
    when the text inside is lighter than the block, so all text ends up dark-on-light.
    """
    h, w = gray.shape
    k = max(15, w // 100)                      # wider than text strokes
    dark = (gray < dark_max).astype(np.uint8) * 255
    # opening removes text strokes and keeps only solid blocks
    blocks = cv2.morphologyEx(dark, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))
    # closing fills the holes the light text leaves inside a block
    filled = cv2.morphologyEx(blocks, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (3 * k, 3 * k)))

    n, labels, stats, _ = cv2.connectedComponentsWithStats(filled, 8)
    out = gray.copy()
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] < min_area_frac * h * w:
            continue
        region = labels == i
        background = region & (blocks > 0)
        text = region & (blocks == 0)
        if not text.any() or np.median(gray[text]) <= np.median(gray[background]):
            continue                           # dark text on a shaded block, leave as is
        out[region] = 255 - gray[region]
    return out

def estimate_skew(gray: MatLike, max_angle: float = 15.0) -> float:
    binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    h, w = binary.shape
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(15, w // 40), 3))
    dilated = cv2.dilate(binary, kernel)
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    angles = []
    for c in contours:
        _, (rw, rh), angle = cv2.minAreaRect(c)
        long_side, short_side = max(rw, rh), min(rw, rh)
        if short_side < 3 or long_side < 0.05 * w:      # speckle
            continue
        if long_side / max(short_side, 1) < 3:           # not line-shaped
            continue
        angle = ((angle + 45) % 90) - 45                 # -> (-45, 45]
        if abs(angle) <= max_angle:
            angles.append(angle)

    return statistics.median(angles) if len(angles) >= 3 else 0.0


def rotate_expand(img: MatLike, angle: float) -> MatLike:
    h, w = img.shape[:2]
    cx, cy = w / 2, h / 2
    m = cv2.getRotationMatrix2D((cx, cy), angle, 1.0)
    cos, sin = abs(m[0, 0]), abs(m[0, 1])
    nw, nh = int(h * sin + w * cos), int(h * cos + w * sin)
    m[0, 2] += nw / 2 - cx
    m[1, 2] += nh / 2 - cy
    return cv2.warpAffine(img, m, (nw, nh),
                          flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_REPLICATE)


def crop_to_content(gray: MatLike, pad: int = 10) -> MatLike:
    mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    coords = cv2.findNonZero(mask)
    if coords is None:
        return gray
    x, y, w_, h_ = cv2.boundingRect(coords)
    H, W = gray.shape[:2]
    return gray[max(0, y - pad):min(H, y + h_ + pad),
                max(0, x - pad):min(W, x + w_ + pad)]


def remove_lines(binary: MatLike) -> MatLike:
    H, W = binary.shape
    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(20, W // 30), 1))
    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(20, H // 20)))
    lines = cv2.bitwise_or(cv2.morphologyEx(binary, cv2.MORPH_OPEN, h_kernel),
                           cv2.morphologyEx(binary, cv2.MORPH_OPEN, v_kernel))
    if cv2.countNonZero(lines) == 0:
        return binary
    lines = cv2.dilate(lines, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
    return cv2.subtract(binary, lines)

def main_pre_process(data:bytes) -> MatLike:
    gray = load_image_to_matrix_gray(data)
    gray = cv2.fastNlMeansDenoising(gray)

    angle = estimate_skew(gray)
    if abs(angle) > 0.1:
        gray = rotate_expand(gray, angle)

    gray = crop_to_content(gray)
    gray = upscale(gray)

    gray = fix_inverted_regions(gray)
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY_INV, 25, 15)
    binary = remove_lines(binary)

    out = cv2.bitwise_not(binary)
    return out

