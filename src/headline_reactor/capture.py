from __future__ import annotations
from typing import Optional, Tuple
from PIL import Image, ImageGrab, ImageOps
import pygetwindow as gw
import win32gui  # type: ignore

DEFAULT_WINDOW = "Alert Catcher"
ROI_TOP_PX = 115
ROI_HEIGHT_PX = 20

def find_news_window_rect(title_part: str = DEFAULT_WINDOW) -> Optional[Tuple[int,int,int,int]]:
    for w in gw.getAllWindows():
        t = (w.title or "").strip()
        if title_part.lower() in t.lower() and getattr(w, "visible", True):
            try:
                return win32gui.GetWindowRect(w._hWnd)  # (l,t,r,b)
            except Exception:
                continue
    return None

def grab_topline(rect: Tuple[int,int,int,int], roi_top_px: int = ROI_TOP_PX, roi_h_px: int = ROI_HEIGHT_PX) -> Image.Image:
    l,t,r,b = rect
    roi_top = t + roi_top_px
    roi_bot = roi_top + roi_h_px
    img = ImageGrab.grab(bbox=(l + 10, roi_top, r - 10, roi_bot))
    img = ImageOps.grayscale(img)
    img = ImageOps.autocontrast(img)
    return img

