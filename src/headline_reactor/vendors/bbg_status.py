from __future__ import annotations
from typing import List, Dict, Any
from pathlib import Path
import pandas as pd

try:
    import blpapi
except Exception:
    blpapi = None

HALT_FIELDS = [
    # Try several; keep what your entitlement returns
    "TRADING_STATUS",            # e.g., 'Trading', 'Halted'
    "HALT_RELATED_S",            # reason text (varies)
    "LULD_LOWER_PRICE_BAND",
    "LULD_UPPER_PRICE_BAND",
    "SHORT_SALE_RESTRICTION",    # boolean/flag if available
]

def _session():
    """Create Bloomberg session."""
    opts = blpapi.SessionOptions()
    opts.setServerHost("localhost")
    opts.setServerPort(8194)
    s = blpapi.Session(opts)
    if not s.start():
        raise RuntimeError("BLP session start failed")
    return s

def refdata(secs: List[str], fields: List[str]) -> pd.DataFrame:
    """Get reference/static data for securities."""
    if blpapi is None:
        return pd.DataFrame()
    
    s = _session()
    try:
        # Try static market data first
        if s.openService("//blp/staticmktdata"):
            service = s.getService("//blp/staticmktdata")
            req = service.createRequest("StaticMarketDataRequest")
        else:
            # Fallback to refdata
            if not s.openService("//blp/refdata"):
                raise RuntimeError("Failed to open refdata service")
            service = s.getService("//blp/refdata")
            req = service.createRequest("ReferenceDataRequest")

        # Populate request
        e_secs = req.getElement("securities")
        for sec in secs:
            e_secs.appendValue(sec)
        
        e_flds = req.getElement("fields")
        for f in fields:
            e_flds.appendValue(f)

        # Send and collect
        cid = blpapi.CorrelationId()
        s.sendRequest(req, correlationId=cid)
        
        rows = []
        while True:
            ev = s.nextEvent()
            for msg in ev:
                if not msg.hasElement("securityData"):
                    continue
                sd = msg.getElement("securityData")
                for i in range(sd.numValues()):
                    rec = sd.getValueAsElement(i)
                    sec = rec.getElementAsString("security")
                    fd = rec.getElement("fieldData")
                    row = {"bbg": sec}
                    for f in fields:
                        if fd.hasElement(f):
                            try:
                                row[f] = fd.getElement(f).getValueAsString()
                            except Exception:
                                row[f] = str(fd.getElement(f))
                    rows.append(row)
            if ev.eventType() == blpapi.Event.RESPONSE:
                break
        
        return pd.DataFrame(rows)
    finally:
        s.stop()

def status_snapshot(bbg_secs: List[str]) -> pd.DataFrame:
    """Get trading status snapshot for securities (halts, LULD, SSR)."""
    if blpapi is None:  # Degrade gracefully
        return pd.DataFrame(columns=["bbg", "TRADING_STATUS", "LULD_LOWER_PRICE_BAND", "LULD_UPPER_PRICE_BAND", "SHORT_SALE_RESTRICTION"])
    
    df = refdata(bbg_secs, HALT_FIELDS)
    
    # Normalize columns - add missing as None
    for c in HALT_FIELDS:
        if c not in df.columns:
            df[c] = None
    
    return df[["bbg", "TRADING_STATUS", "LULD_LOWER_PRICE_BAND", "LULD_UPPER_PRICE_BAND", "SHORT_SALE_RESTRICTION"]]

def is_halted(status_row: Dict[str, Any]) -> bool:
    """Check if security is currently halted."""
    status = str(status_row.get("TRADING_STATUS", "")).upper()
    return "HALT" in status or "SUSPEND" in status

def luld_guard(px: float, lower: str | None, upper: str | None) -> bool:
    """Check if price is within LULD bands (if available)."""
    try:
        lo = float(lower) if lower not in (None, "") else None
        hi = float(upper) if upper not in (None, "") else None
        if lo is not None and px < lo:
            return False
        if hi is not None and px > hi:
            return False
    except Exception:
        pass
    return True

def has_ssr(status_row: Dict[str, Any]) -> bool:
    """Check if short sale restriction is active."""
    ssr = status_row.get("SHORT_SALE_RESTRICTION")
    if ssr is None:
        return False
    # Handle boolean or string representation
    return str(ssr).upper() in ("TRUE", "YES", "1", "Y")

