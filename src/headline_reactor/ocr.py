from __future__ import annotations
import re
from PIL import Image
import pytesseract

# Set Tesseract path for Windows
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def ocr_topline(img: Image.Image) -> str:
    cfg = "--psm 7 -c tessedit_char_blacklist=|~`{}[]<>""''"
    raw = pytesseract.image_to_string(img, config=cfg)
    return re.sub(r"\s+", " ", raw).strip().upper()

