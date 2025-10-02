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

def last_close(symbol: str, live_root: Path = Path("data/live")) -> Optional[float]:
    """Get last close price from live data if available."""
    days = sorted([p for p in live_root.glob("*") if p.is_dir()])
    if not days: return None
    p = days[-1] / f"bars1s_{symbol}.parquet"
    if not p.exists(): return None
    df = pd.read_parquet(p)
    if df.empty: return None
    return float(df["close"].iloc[-1])

def _round_strike(px: float) -> int:
    """Simple, fast strike rounding to keep strikes near ATM."""
    if px < 25:   step = 0.5
    elif px < 100: step = 1
    elif px < 200: step = 5
    else:          step = 5
    return int(round(px / step) * step)

def atm_call(symbol: str, next_friday_code: str = "NEXT_FRI", prem_usd: int = 400) -> Optional[OptIdea]:
    """Generate ATM call suggestion for quick scalp on M&A news."""
    px = last_close(symbol)
    if px is None: return None
    strike = _round_strike(px)
    qty = 1  # keep tiny to avoid IV risk; let user scale
    line = f"{symbol} +C{strike} {next_friday_code} x{qty} LMT=mid IOC TTL=10m"
    return OptIdea(line=line, score=0.45, rationale="ATM call quick scalp")

