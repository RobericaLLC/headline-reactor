from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import pandas as pd
import time

@dataclass
class LqGuard:
    """Liquidity guardrails for trading decisions."""
    min_adv_usd: float
    max_spread_bps: float
    max_quote_age_ms: int

def load_stats(path: Path) -> Optional[pd.DataFrame]:
    """Load liquidity statistics catalog."""
    if not path.exists(): 
        return None
    try:
        df = pd.read_parquet(path)
        if "symbol" not in df.columns: 
            return None
        return df
    except Exception:
        return None

def stats_ok(symbol: str, stats: Optional[pd.DataFrame], g: LqGuard) -> bool:
    """Check if symbol meets liquidity guardrails."""
    if stats is None: 
        return True  # permissive if you don't have stats yet
    
    r = stats.loc[stats["symbol"].str.upper() == symbol.upper()]
    if r.empty: 
        return True
    
    adv = float(r["adv_usd"].iloc[0]) if "adv_usd" in r else 1e9
    spd = float(r["avg_spread_bps"].iloc[0]) if "avg_spread_bps" in r else 10
    
    return adv >= g.min_adv_usd and spd <= g.max_spread_bps

def marketable_limit(side: str, bid: float, ask: float, offset_bps: int, max_slip_bps: int) -> float:
    """Calculate marketable limit price with band."""
    mid = (bid + ask) / 2 if bid > 0 and ask > 0 else (bid if side == "BUY" else ask)
    band = mid * (offset_bps / 10000.0)
    px = ask + band if side == "BUY" else bid - band
    
    # cap at max slippage
    worst = mid * (1 + (max_slip_bps / 10000.0)) if side == "BUY" else mid * (1 - (max_slip_bps / 10000.0))
    return round(min(px, worst), 4) if side == "BUY" else round(max(px, worst), 4)

def now_ms() -> int:
    """Current time in milliseconds."""
    return int(time.time() * 1000)

