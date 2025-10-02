from __future__ import annotations
from typing import Optional, Tuple
from PIL import Image, ImageGrab, ImageOps
import pygetwindow as gw
import win32gui  # type: ignore

WINDOW_HINT = "Alert Catcher"
ROI_TOP_PX = 115  # First alert row (below header)
ROI_HEIGHT_PX = 20  # Height of one alert row

def find_news_window_rect(title_part: str = WINDOW_HINT) -> Optional[Tuple[int,int,int,int]]:
    for w in gw.getAllWindows():
        t = (w.title or "").strip()
        if title_part.lower() in t.lower() and w.visible:
            try:
                hwnd = w._hWnd
                return win32gui.GetWindowRect(hwnd)  # (l,t,r,b)
            except Exception:
                continue
    return None

def grab_topline(rect: Tuple[int,int,int,int]) -> Image.Image:
    l,t,r,b = rect
    roi_top = t + ROI_TOP_PX
    roi_bot = roi_top + ROI_HEIGHT_PX
    img = ImageGrab.grab(bbox=(l + 10, roi_top, r - 10, roi_bot))
    img = ImageOps.grayscale(img)
    img = ImageOps.autocontrast(img)
    return img

