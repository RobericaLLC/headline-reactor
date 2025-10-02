from __future__ import annotations
import re
from PIL import Image
import pytesseract

# Set Tesseract path for Windows
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

def ocr_topline(img: Image.Image) -> str:
    # Keep it simple and fast; PSM 7 = single text line
    cfg = "--psm 7"
    raw = pytesseract.image_to_string(img, config=cfg)
    return re.sub(r"\s+", " ", raw).strip().upper()

