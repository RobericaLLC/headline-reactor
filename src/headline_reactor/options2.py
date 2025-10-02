from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import pandas as pd

@dataclass
class OptIdea:
    line: str
    score: float
    rationale: str

def _round_strike(px: float) -> float:
    """Round strike to standard increments."""
    if px < 25: 
        step = 0.5
    elif px < 100: 
        step = 1
    elif px < 200: 
        step = 5
    else: 
        step = 5
    return round(round(px / step) * step, 2)

def last_close(symbol: str, root: Path = Path("data/live")) -> Optional[float]:
    """Get last close price from live data cache."""
    p = root / f"bars1s_{symbol}.parquet"
    if not p.exists(): 
        return None
    try:
        df = pd.read_parquet(p)
        if df.empty: 
            return None
        return float(df["close"].iloc[-1])
    except Exception:
        return None

def atm_call(symbol: str, next_code: str = "NEXT_FRI", prem_usd: int = 300) -> Optional[OptIdea]:
    """Generate ATM call suggestion for quick scalp (M&A, positive pops)."""
    px = last_close(symbol)
    if px is None: 
        return None
    strike = _round_strike(px)
    qty = 1
    line = f"{symbol} +C{strike} {next_code} x{qty} LMT=mid IOC TTL=10m"
    return OptIdea(line=line, score=0.45, rationale="ATM call quick scalp")

def delta_put(symbol: str, delta: float = 0.30, next_code: str = "NEXT_FRI") -> Optional[OptIdea]:
    """Generate ~30 delta put for guidance cuts, downgrades."""
    px = last_close(symbol)
    if px is None: 
        return None
    # Fast proxy: ~30Δ often 7.5% OTM for large caps
    strike = _round_strike(px * (1 - 0.075))
    line = f"{symbol} +P{strike} {next_code} x1 LMT=mid IOC TTL=10m"
    return OptIdea(line=line, score=0.48, rationale="~0.30Δ put for down headlines")

