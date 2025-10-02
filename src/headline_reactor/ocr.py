from __future__ import annotations
import re
from PIL import Image
import pytesseract

def ocr_topline(img: Image.Image) -> str:
    cfg = "--psm 7 -c tessedit_char_blacklist=|~`{}[]<>""''"
    raw = pytesseract.image_to_string(img, config=cfg)
    return re.sub(r"\s+", " ", raw).strip().upper()

